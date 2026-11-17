"""Haalt de prijzen op en rekent per uur uit wat nu geldt."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import PrijzenFout, haal_prijzen
from .const import (
    ALLEEN_BEURS,
    CONF_LEVERANCIER,
    DOMAIN,
    SNEL_INTERVAL,
    SNEL_TOT_UUR,
    SNEL_VAN_UUR,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Uur:
    """Een prijsblok: van start tot eind, in euro."""

    start: datetime
    eind: datetime
    prijs: float

    def als_dict(self) -> dict[str, Any]:
        return {
            "start": dt_util.as_local(self.start).isoformat(),
            "eind": dt_util.as_local(self.eind).isoformat(),
            "prijs": self.prijs,
        }


def _tijd(stempel: str) -> datetime | None:
    return dt_util.parse_datetime(stempel) if stempel else None


def _reeks(uren: list[dict[str, Any]], prijzen_ct: list[Any] | None) -> list[Uur]:
    """Zet de uren van de server om in blokken met een prijs in euro.

    Met prijzen_ct horen de prijzen op dezelfde plek als de uren. Zonder
    nemen we de kale beursprijs van het uur zelf.
    """
    starts = [_tijd(u.get("t", "")) for u in uren]
    uit: list[Uur] = []
    for i, (u, start) in enumerate(zip(uren, starts)):
        if start is None:
            continue
        if prijzen_ct is not None:
            if i >= len(prijzen_ct) or prijzen_ct[i] is None:
                continue
            ct = prijzen_ct[i]
        else:
            ct = u.get("markt_ct")
            if ct is None:
                continue
        volgende = starts[i + 1] if i + 1 < len(starts) else None
        eind = volgende if volgende and volgende > start else start + timedelta(hours=1)
        uit.append(Uur(start, eind, round(float(ct) / 100, 5)))
    return uit


class PrijzenCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Een verzoek per kwartier, gedeeld door alle sensoren."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.leverancier: str = entry.options.get(
            CONF_LEVERANCIER, entry.data.get(CONF_LEVERANCIER, ALLEEN_BEURS)
        )
        self._stop_tik: Callable[[], None] | None = None
        self._mislukt_gemeld = False

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await haal_prijzen(async_get_clientsession(self.hass))
            if self._mislukt_gemeld:
                _LOGGER.info("Prijzen ophalen lukt weer")
                self._mislukt_gemeld = False
            self.update_interval = self._volgende_interval(data)
            return data
        except PrijzenFout as err:
            # De prijzen staan al uren vooruit vast. Een keer niet kunnen
            # ophalen, door een haperende DNS of wifi, is dus geen reden om
            # alles op niet beschikbaar te zetten: zolang wat we hebben het
            # huidige uur nog dekt, rekenen we daarmee door.
            if self.data and self.op_moment(_reeks(self.data.get("uren") or [], None)):
                if not self._mislukt_gemeld:
                    _LOGGER.warning(
                        "Prijzen ophalen mislukt (%s), de laatst opgehaalde prijzen blijven gelden", err
                    )
                    self._mislukt_gemeld = True
                return self.data
            raise UpdateFailed(f"Prijzen ophalen mislukt: {err}") from err

    def _volgende_interval(self, data: dict[str, Any] | None) -> timedelta:
        """Hoe lang tot het volgende verzoek.

        Een keer per uur, behalve tussen 13:00 en 15:00 zolang de prijzen van
        morgen er nog niet zijn: dan elk kwartier. Vlak voor 13:00 wachten we
        niet een vol uur, anders begint het snelle kijken pas laat.
        """
        nu = dt_util.now()
        morgen_binnen = bool(self.van_dag(_reeks((data or {}).get("uren") or [], None), 1))
        if SNEL_VAN_UUR <= nu.hour < SNEL_TOT_UUR:
            return UPDATE_INTERVAL if morgen_binnen else SNEL_INTERVAL
        start_snel = nu.replace(hour=SNEL_VAN_UUR, minute=0, second=0, microsecond=0)
        tot_start = start_snel - nu
        if not morgen_binnen and timedelta(0) < tot_start < UPDATE_INTERVAL:
            return tot_start + timedelta(seconds=30)
        return UPDATE_INTERVAL

    # --- elk heel uur de sensoren bijwerken, ook zonder nieuw verzoek ------

    def start_uurtik(self) -> None:
        @callback
        def _tik(_now: datetime) -> None:
            self.async_update_listeners()

        self._stop_tik = async_track_utc_time_change(self.hass, _tik, minute=0, second=1)

    def stop_uurtik(self) -> None:
        if self._stop_tik:
            self._stop_tik()
            self._stop_tik = None

    # --- waar de sensoren op leunen ---------------------------------------

    @property
    def alleen_beurs(self) -> bool:
        return self.leverancier == ALLEEN_BEURS

    @property
    def gegevens_leverancier(self) -> dict[str, Any] | None:
        if self.alleen_beurs:
            return None
        return next(
            (l for l in (self.data or {}).get("leveranciers") or [] if l.get("naam") == self.leverancier),
            None,
        )

    def stroom(self) -> list[Uur]:
        uren = (self.data or {}).get("uren") or []
        if self.alleen_beurs:
            return _reeks(uren, None)
        lev = self.gegevens_leverancier
        if lev is None:
            return []
        return _reeks(uren, lev.get("prijzen_ct") or [])

    def gas(self) -> list[Uur]:
        uren = (self.data or {}).get("gas_uren") or []
        if self.alleen_beurs:
            return _reeks(uren, None)
        lev = self.gegevens_leverancier
        if lev is None or lev.get("gas_opslag_ct") is None:
            return []
        return _reeks(uren, lev.get("gas_prijzen_ct") or [])

    def beurs(self) -> list[Uur]:
        return _reeks((self.data or {}).get("uren") or [], None)

    @staticmethod
    def op_moment(reeks: list[Uur], moment: datetime | None = None) -> Uur | None:
        moment = moment or dt_util.utcnow()
        return next((u for u in reeks if u.start <= moment < u.eind), None)

    @staticmethod
    def van_dag(reeks: list[Uur], dagen_verder: int = 0) -> list[Uur]:
        dag = (dt_util.now() + timedelta(days=dagen_verder)).date()
        return [u for u in reeks if dt_util.as_local(u.start).date() == dag]

    @staticmethod
    def vanaf_nu(reeks: list[Uur]) -> list[Uur]:
        nu = dt_util.utcnow()
        return [u for u in reeks if u.eind > nu]

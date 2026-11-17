"""De prijssensoren."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PrijzenCoordinator, Uur

EUR_KWH = "EUR/kWh"
EUR_M3 = "EUR/m³"


def _gem(reeks: list[Uur]) -> float | None:
    return round(sum(u.prijs for u in reeks) / len(reeks), 5) if reeks else None


def _min(reeks: list[Uur]) -> Uur | None:
    return min(reeks, key=lambda u: u.prijs) if reeks else None


def _max(reeks: list[Uur]) -> Uur | None:
    return max(reeks, key=lambda u: u.prijs) if reeks else None


def _prijs(u: Uur | None) -> float | None:
    return u.prijs if u else None


def _start(u: Uur | None) -> datetime | None:
    return u.start if u else None


def _reeks_attributen(c: PrijzenCoordinator, reeks: list[Uur]) -> dict[str, Any]:
    """Vandaag en morgen per uur, voor grafieken en automatiseringen."""
    vandaag = c.van_dag(reeks)
    morgen = c.van_dag(reeks, 1)
    return {
        "vandaag": [u.als_dict() for u in vandaag],
        "morgen": [u.als_dict() for u in morgen],
        "morgen_beschikbaar": bool(morgen),
        "laagste_vandaag": _prijs(_min(vandaag)),
        "hoogste_vandaag": _prijs(_max(vandaag)),
        "gemiddeld_vandaag": _gem(vandaag),
    }


@dataclass(frozen=True, kw_only=True)
class PrijsSensorBeschrijving(SensorEntityDescription):
    waarde: Callable[[PrijzenCoordinator], Any]
    attributen: Callable[[PrijzenCoordinator], dict[str, Any] | None] = lambda c: None
    alleen_met_gas: bool = False


SENSOREN: tuple[PrijsSensorBeschrijving, ...] = (
    PrijsSensorBeschrijving(
        key="stroomprijs",
        translation_key="stroomprijs",
        native_unit_of_measurement=EUR_KWH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        icon="mdi:flash",
        waarde=lambda c: _prijs(c.op_moment(c.stroom())),
        attributen=lambda c: _reeks_attributen(c, c.stroom()),
    ),
    PrijsSensorBeschrijving(
        key="stroomprijs_volgend_uur",
        translation_key="stroomprijs_volgend_uur",
        native_unit_of_measurement=EUR_KWH,
        suggested_display_precision=3,
        icon="mdi:flash-outline",
        waarde=lambda c: _prijs(
            next(iter(c.vanaf_nu(c.stroom())[1:2]), None)
        ),
    ),
    PrijsSensorBeschrijving(
        key="stroomprijs_laagste_vandaag",
        translation_key="stroomprijs_laagste_vandaag",
        native_unit_of_measurement=EUR_KWH,
        suggested_display_precision=3,
        icon="mdi:arrow-down-bold",
        waarde=lambda c: _prijs(_min(c.van_dag(c.stroom()))),
    ),
    PrijsSensorBeschrijving(
        key="stroomprijs_hoogste_vandaag",
        translation_key="stroomprijs_hoogste_vandaag",
        native_unit_of_measurement=EUR_KWH,
        suggested_display_precision=3,
        icon="mdi:arrow-up-bold",
        waarde=lambda c: _prijs(_max(c.van_dag(c.stroom()))),
    ),
    PrijsSensorBeschrijving(
        key="stroomprijs_gemiddeld_vandaag",
        translation_key="stroomprijs_gemiddeld_vandaag",
        native_unit_of_measurement=EUR_KWH,
        suggested_display_precision=3,
        icon="mdi:approximately-equal",
        waarde=lambda c: _gem(c.van_dag(c.stroom())),
    ),
    PrijsSensorBeschrijving(
        key="goedkoopste_uur",
        translation_key="goedkoopste_uur",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-check-outline",
        waarde=lambda c: _start(_min(c.vanaf_nu(c.stroom()))),
        attributen=lambda c: {"prijs": _prijs(_min(c.vanaf_nu(c.stroom())))},
    ),
    PrijsSensorBeschrijving(
        key="duurste_uur",
        translation_key="duurste_uur",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-alert-outline",
        waarde=lambda c: _start(_max(c.vanaf_nu(c.stroom()))),
        attributen=lambda c: {"prijs": _prijs(_max(c.vanaf_nu(c.stroom())))},
    ),
    PrijsSensorBeschrijving(
        key="beursprijs",
        translation_key="beursprijs",
        native_unit_of_measurement=EUR_KWH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        icon="mdi:chart-line",
        waarde=lambda c: _prijs(c.op_moment(c.beurs())),
        attributen=lambda c: _reeks_attributen(c, c.beurs()),
    ),
    PrijsSensorBeschrijving(
        key="gasprijs",
        translation_key="gasprijs",
        native_unit_of_measurement=EUR_M3,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        icon="mdi:fire",
        alleen_met_gas=True,
        waarde=lambda c: _prijs(c.op_moment(c.gas())),
        attributen=lambda c: _reeks_attributen(c, c.gas()),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: PrijzenCoordinator = entry.runtime_data
    # Opgeruimd in 0.1.4: haal hem weg bij wie hem nog heeft staan.
    register = er.async_get(hass)
    if oud := register.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_goedkoopste_leverancier"):
        register.async_remove(oud)
    heeft_gas = coordinator.alleen_beurs or bool(coordinator.gas())
    async_add_entities(
        PrijsSensor(coordinator, entry, b)
        for b in SENSOREN
        if heeft_gas or not b.alleen_met_gas
    )


class PrijsSensor(CoordinatorEntity[PrijzenCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_attribution = "Beursprijs via EnergyZero, inkoopopslag via energieprijzen-nl (CC BY 4.0)"
    entity_description: PrijsSensorBeschrijving

    def __init__(
        self, coordinator: PrijzenCoordinator, entry: ConfigEntry, beschrijving: PrijsSensorBeschrijving
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = beschrijving
        self._attr_unique_id = f"{entry.entry_id}_{beschrijving.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Beursprijzen {entry.title}" if entry.title != "Beursprijs" else "Beursprijzen",
            manufacturer="SolarBuffer",
            model="Energieprijzen",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://hub.solarbuffer.nl/energieprijzen",
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.waarde(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attrs = self.entity_description.attributen(self.coordinator)
        if self.entity_description.key == "stroomprijs":
            lev = self.coordinator.gegevens_leverancier
            attrs = dict(attrs or {})
            attrs["leverancier"] = lev.get("naam") if lev else None
            attrs["inkoopopslag_ct_excl_btw"] = lev.get("opslag_ct") if lev else None
            attrs["energiebelasting_ct"] = (
                None if self.coordinator.alleen_beurs else (self.coordinator.data or {}).get("energiebelasting_ct")
            )
            attrs["all_in"] = not self.coordinator.alleen_beurs
        return attrs

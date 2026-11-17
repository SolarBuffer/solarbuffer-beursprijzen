"""Instellen: kies je energieleverancier, of alleen de beursprijs."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector, SelectSelectorConfig, SelectSelectorMode

from .api import PrijzenFout, haal_prijzen
from .const import ALLEEN_BEURS, CONF_LEVERANCIER, DOMAIN


async def _keuzes(hass) -> list[SelectOptionDict]:
    data = await haal_prijzen(async_get_clientsession(hass))
    namen = sorted({l["naam"] for l in data.get("leveranciers") or [] if l.get("naam")}, key=str.lower)
    return [SelectOptionDict(value=ALLEEN_BEURS, label="Alleen de beursprijs")] + [
        SelectOptionDict(value=n, label=n) for n in namen
    ]


def _schema(keuzes: list[SelectOptionDict], standaard: str | None = None) -> vol.Schema:
    sleutel = vol.Required(CONF_LEVERANCIER, default=standaard) if standaard else vol.Required(CONF_LEVERANCIER)
    return vol.Schema(
        {sleutel: SelectSelector(SelectSelectorConfig(options=keuzes, mode=SelectSelectorMode.DROPDOWN))}
    )


def _titel(leverancier: str) -> str:
    return "Beursprijs" if leverancier == ALLEEN_BEURS else leverancier


class BeursprijzenConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            lev = user_input[CONF_LEVERANCIER]
            await self.async_set_unique_id(lev)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=_titel(lev), data={CONF_LEVERANCIER: lev})
        try:
            keuzes = await _keuzes(self.hass)
        except PrijzenFout:
            return self.async_abort(reason="cannot_connect")
        return self.async_show_form(step_id="user", data_schema=_schema(keuzes))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return BeursprijzenOptionsFlow()


class BeursprijzenOptionsFlow(OptionsFlow):
    """Van leverancier wisselen zonder alles opnieuw in te stellen."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        try:
            keuzes = await _keuzes(self.hass)
        except PrijzenFout:
            return self.async_abort(reason="cannot_connect")
        huidig = self.config_entry.options.get(
            CONF_LEVERANCIER, self.config_entry.data.get(CONF_LEVERANCIER)
        )
        return self.async_show_form(step_id="init", data_schema=_schema(keuzes, huidig))

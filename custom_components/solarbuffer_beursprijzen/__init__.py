"""SolarBuffer Beursprijzen: stroom- en gasprijs per uur, per leverancier."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import ALLEEN_BEURS, CONF_LEVERANCIER
from .coordinator import PrijzenCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = PrijzenCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    coordinator.start_uurtik()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_opnieuw_laden))
    return True


async def _opnieuw_laden(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Na het wisselen van leverancier: nieuwe titel en opnieuw opbouwen."""
    lev = entry.options.get(CONF_LEVERANCIER, entry.data.get(CONF_LEVERANCIER))
    titel = "Beursprijs" if lev == ALLEEN_BEURS else lev
    if titel and titel != entry.title:
        hass.config_entries.async_update_entry(entry, title=titel)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry.runtime_data.stop_uurtik()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

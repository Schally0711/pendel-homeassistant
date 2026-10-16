"""Pendel – work time tracking for home office and office days."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PendelClient
from .const import CONF_HOME_ZONE, CONF_OFFICE_ZONE, CONF_PERSON, CONF_TRACK_LOCATION
from .coordinator import PendelCoordinator
from .tracker import LocationTracker

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]


@dataclass
class PendelRuntime:
    client: PendelClient
    coordinator: PendelCoordinator
    tracker: LocationTracker | None


type PendelConfigEntry = ConfigEntry[PendelRuntime]


async def async_setup_entry(hass: HomeAssistant, entry: PendelConfigEntry) -> bool:
    client = PendelClient(async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN])
    coordinator = PendelCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    options = {**entry.data, **entry.options}
    tracker = None
    if options.get(CONF_TRACK_LOCATION, True) and options.get(CONF_PERSON):
        zones = {z for z in (options.get(CONF_HOME_ZONE), options.get(CONF_OFFICE_ZONE)) if z}
        tracker = LocationTracker(
            hass, entry.entry_id, client, options[CONF_PERSON], zones, coordinator.async_request_refresh
        )
        await tracker.async_start()
        entry.async_on_unload(tracker.async_stop)

    entry.runtime_data = PendelRuntime(client, coordinator, tracker)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass: HomeAssistant, entry: PendelConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PendelConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

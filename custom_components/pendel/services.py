"""Actions (services) of the integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import PendelError
from .const import DOMAIN

ATTR_CONFIG_ENTRY = "config_entry_id"
ATTR_PLACE = "place"

DEVICE_ACTIVE_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_CONFIG_ENTRY): cv.string, vol.Optional(ATTR_PLACE): cv.string}
)


def _entry(hass: HomeAssistant, entry_id: str | None):
    entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED]
    if entry_id:
        entries = [e for e in entries if e.entry_id == entry_id]
    if len(entries) != 1:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="choose_account")
    return entries[0]


async def _device_active(call: ServiceCall) -> ServiceResponse:
    entry = _entry(call.hass, call.data.get(ATTR_CONFIG_ENTRY))
    try:
        actions = await entry.runtime_data.client.device_active(call.data.get(ATTR_PLACE))
    except PendelError as err:
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="cannot_connect") from err
    await entry.runtime_data.coordinator.async_request_refresh()
    return {"actions": actions, "started": "device_session_started" in actions}


def async_setup_services(hass: HomeAssistant) -> None:
    hass.services.async_register(
        DOMAIN,
        "device_active",
        _device_active,
        schema=DEVICE_ACTIVE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

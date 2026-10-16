"""Diagnostics download (Settings → Devices & services → Pendel → ⋮ → Download diagnostics)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant

from . import PendelConfigEntry

TO_REDACT = {CONF_TOKEN, CONF_URL, "note", "unique_id", "title"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: PendelConfigEntry) -> dict[str, Any]:
    runtime = entry.runtime_data
    tracker = runtime.tracker
    data = runtime.coordinator.data
    return {
        "entry": async_redact_data({"data": dict(entry.data), "options": dict(entry.options)}, TO_REDACT),
        "last_update_success": runtime.coordinator.last_update_success,
        "status": data.status if data else None,
        "pendel": async_redact_data(asdict(data), TO_REDACT) if data else None,
        "tracker": (
            {"person": tracker.person, "queued_events": len(tracker._queue)} if tracker is not None else None
        ),
    }

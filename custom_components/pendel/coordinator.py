"""Polls Pendel for today's state and the vacation account."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import PendelAuthError, PendelClient, PendelError
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class PendelData:
    today: dict[str, Any]
    vacation: dict[str, Any]
    next_absence: dict[str, Any] | None

    @property
    def status(self) -> str:
        if commute := self.today.get("running_commute"):
            return "commute_to_work" if commute["direction"] == "to_work" else "commute_from_work"
        if self.today.get("running_break"):
            return "break"
        if session := self.today.get("running_session"):
            return f"working_{session['kind']}"
        return "idle"

    @property
    def status_since(self) -> str | None:
        t = self.today
        for key in ("running_commute", "running_break", "running_session"):
            if t.get(key):
                return t[key]["start"]
        return None


class PendelCoordinator(DataUpdateCoordinator[PendelData]):
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: PendelClient) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.client = client

    async def _async_update_data(self) -> PendelData:
        year = dt_util.now().year
        try:
            today = await self.client.today()
            vacation = await self.client.vacation(year)
            absences = await self.client.absences(year)
        except PendelAuthError as err:
            raise ConfigEntryAuthFailed("Pendel rejected the API token") from err
        except PendelError as err:
            raise UpdateFailed(f"Pendel not reachable: {err}") from err
        local_today = date.fromisoformat(today["day"]["day"])
        upcoming = [p for p in absences.get("periods", []) if date.fromisoformat(p["end"]) >= local_today]
        return PendelData(today=today, vacation=vacation, next_absence=upcoming[0] if upcoming else None)

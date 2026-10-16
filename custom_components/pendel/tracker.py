"""Reports zone changes of a person to Pendel; queues them while Pendel is unreachable."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import PendelAuthError, PendelClient, PendelConflictError, PendelError
from .const import DOMAIN, MAX_EVENT_AGE, NOT_HOME, RETRY_INTERVAL

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1


def zone_for_state(hass: HomeAssistant, state: str, zones: set[str]) -> str:
    """Map a person state ("home", "Arbeit", "not_home") to a configured zone entity id.

    States that are not one of the configured zones count as "not_home".
    """
    if state == "home":
        entity_id = "zone.home"
    else:
        entity_id = next(
            (
                z.entity_id
                for z in hass.states.async_all("zone")
                if z.name == state or z.entity_id == f"zone.{state.lower()}"
            ),
            None,
        )
    return entity_id if entity_id in zones else NOT_HOME


class LocationTracker:
    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        client: PendelClient,
        person: str,
        zones: set[str],
        on_sent: Callable[[], Any],
    ) -> None:
        self.hass = hass
        self.client = client
        self.person = person
        self.zones = zones
        self._on_sent = on_sent
        self._store: Store[list[dict[str, str]]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.queue")
        self._queue: list[dict[str, str]] = []
        self._unsubs: list[Callable[[], None]] = []
        self._flushing = False

    async def async_start(self) -> None:
        self._queue = await self._store.async_load() or []
        self._unsubs.append(async_track_state_change_event(self.hass, [self.person], self._handle_change))
        self._unsubs.append(async_track_time_interval(self.hass, self._retry, RETRY_INTERVAL))
        if self._queue:
            self.hass.async_create_task(self._flush())

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    @property
    def pending(self) -> int:
        return len(self._queue)

    @callback
    def _handle_change(self, event: Event[EventStateChangedData]) -> None:
        old: State | None = event.data["old_state"]
        new: State | None = event.data["new_state"]
        if old is None or new is None:
            return
        if {old.state, new.state} & {STATE_UNKNOWN, STATE_UNAVAILABLE}:
            return
        src = zone_for_state(self.hass, old.state, self.zones)
        dst = zone_for_state(self.hass, new.state, self.zones)
        if src == dst:
            return
        self._queue.append({"from": src, "to": dst, "at": new.last_changed.isoformat()})
        self.hass.async_create_task(self._flush())

    async def _retry(self, _now: datetime) -> None:
        if self._queue:
            await self._flush()

    async def _flush(self) -> None:
        if self._flushing:
            return
        self._flushing = True
        sent = False
        try:
            while self._queue:
                item = self._queue[0]
                if dt_util.parse_datetime(item["at"]) < dt_util.utcnow() - MAX_EVENT_AGE:
                    _LOGGER.warning("Dropping outdated zone change %s", item)
                    self._queue.pop(0)
                    continue
                try:
                    await self.client.send_zone_change(item["from"], item["to"], item["at"])
                except PendelConflictError as err:
                    _LOGGER.warning("Pendel rejected zone change %s: %s", item, err.detail)
                except PendelAuthError:
                    _LOGGER.error("Pendel rejected the API token; zone changes are queued")
                    break
                except PendelError as err:
                    _LOGGER.debug("Pendel unreachable, %d zone change(s) queued: %s", len(self._queue), err)
                    break
                else:
                    sent = True
                self._queue.pop(0)
        finally:
            self._flushing = False
            await self._store.async_save(self._queue)
        if sent:
            await self._on_sent()

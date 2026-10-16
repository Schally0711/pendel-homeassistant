"""Buttons for quick actions (e.g. NFC tag at the desk, a Zigbee button, automations)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PendelConfigEntry
from .api import PendelConflictError, PendelError
from .const import DOMAIN
from .entity import PendelEntity


@dataclass(frozen=True, kw_only=True)
class PendelButtonDescription(ButtonEntityDescription):
    action: str
    body: dict[str, Any] | None = None


BUTTONS: tuple[PendelButtonDescription, ...] = (
    PendelButtonDescription(key="start_home", action="start", body={"kind": "home"}),
    PendelButtonDescription(key="start_office", action="start", body={"kind": "office"}),
    PendelButtonDescription(key="start_break", action="break/start"),
    PendelButtonDescription(key="end_break", action="break/stop"),
    PendelButtonDescription(key="stop_work", action="stop"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PendelConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(PendelButton(coordinator, description) for description in BUTTONS)


class PendelButton(PendelEntity, ButtonEntity):
    entity_description: PendelButtonDescription

    def __init__(self, coordinator, description: PendelButtonDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        body = dict(self.entity_description.body or {})
        if "kind" in body:
            place = await self._place_id(body["kind"])
            if place is not None:
                body["place_id"] = place
        try:
            await self.coordinator.client.clock(self.entity_description.action, body)
        except PendelConflictError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="action_rejected",
                translation_placeholders={"detail": err.detail},
            ) from err
        except PendelError as err:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="cannot_connect") from err
        await self.coordinator.async_request_refresh()

    async def _place_id(self, kind: str) -> int | None:
        try:
            places = await self.coordinator.client.places()
        except PendelError:
            return None
        return next((p["id"] for p in places if p["kind"] == kind and not p["archived"]), None)

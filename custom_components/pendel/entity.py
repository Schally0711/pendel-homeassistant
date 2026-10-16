"""Base entity: one Pendel device per config entry."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PendelCoordinator


class PendelEntity(CoordinatorEntity[PendelCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: PendelCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Pendel",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.client.url,
        )

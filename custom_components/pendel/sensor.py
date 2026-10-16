"""Sensors: status, worked time, flexitime balance, vacation."""

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
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import PendelConfigEntry
from .coordinator import PendelData
from .entity import PendelEntity

STATUS_OPTIONS = [
    "idle",
    "working_home",
    "working_office",
    "working_other",
    "break",
    "commute_to_work",
    "commute_from_work",
]


def _minutes(value: float) -> float:
    return round(value)


@dataclass(frozen=True, kw_only=True)
class PendelSensorDescription(SensorEntityDescription):
    value: Callable[[PendelData], Any]
    attributes: Callable[[PendelData], dict[str, Any]] | None = None


def _ts(value: str | None) -> datetime | None:
    return dt_util.parse_datetime(value) if value else None


MINUTES = {
    "device_class": SensorDeviceClass.DURATION,
    "native_unit_of_measurement": UnitOfTime.MINUTES,
    "suggested_unit_of_measurement": UnitOfTime.HOURS,
    "suggested_display_precision": 2,
    "state_class": SensorStateClass.MEASUREMENT,
}

SENSORS: tuple[PendelSensorDescription, ...] = (
    PendelSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=STATUS_OPTIONS,
        value=lambda d: d.status,
        attributes=lambda d: {"since": d.status_since},
    ),
    PendelSensorDescription(
        key="status_since", device_class=SensorDeviceClass.TIMESTAMP, value=lambda d: _ts(d.status_since)
    ),
    PendelSensorDescription(
        key="worked_today", value=lambda d: _minutes(d.today["day"]["actual"]), **MINUTES
    ),
    PendelSensorDescription(
        key="target_today", value=lambda d: _minutes(d.today["day"]["target"]), **MINUTES
    ),
    PendelSensorDescription(
        key="remaining_today",
        value=lambda d: max(d.today["day"]["target"] - d.today["day"]["actual"], 0),
        **MINUTES,
    ),
    PendelSensorDescription(key="balance", value=lambda d: _minutes(d.today["balance"]), **MINUTES),
    PendelSensorDescription(key="worked_week", value=lambda d: _minutes(d.today["week_actual"]), **MINUTES),
    PendelSensorDescription(key="target_week", value=lambda d: _minutes(d.today["week_target"]), **MINUTES),
    PendelSensorDescription(
        key="breaks_today", value=lambda d: _minutes(d.today["day"]["breaks_effective"]), **MINUTES
    ),
    PendelSensorDescription(
        key="commute_today", value=lambda d: _minutes(d.today["day"]["commute"]), **MINUTES
    ),
    PendelSensorDescription(
        key="vacation_remaining",
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=1,
        value=lambda d: d.vacation["remaining"],
        attributes=lambda d: {
            "year": d.vacation["year"],
            "entitlement": d.vacation["days"],
            "carried_over": d.vacation["carried_over"],
            "taken": d.vacation["taken"],
            "planned": d.vacation["planned"],
        },
    ),
    PendelSensorDescription(
        key="next_absence",
        device_class=SensorDeviceClass.DATE,
        value=lambda d: dt_util.parse_date(d.next_absence["start"]) if d.next_absence else None,
        attributes=lambda d: (
            {
                "end": d.next_absence["end"],
                "kind": d.next_absence["kind"],
                "note": d.next_absence["note"],
                "workdays": d.next_absence["workdays"],
            }
            if d.next_absence
            else {}
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PendelConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(PendelSensor(coordinator, description) for description in SENSORS)


class PendelSensor(PendelEntity, SensorEntity):
    entity_description: PendelSensorDescription

    def __init__(self, coordinator, description: PendelSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes is None:
            return None
        return self.entity_description.attributes(self.coordinator.data)

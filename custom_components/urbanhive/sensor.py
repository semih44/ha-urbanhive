"""Sensors of the urbanhive homefarm."""

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
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CLEANING_INTERVAL, FLAG_CLEANING
from .coordinator import UrbanhiveConfigEntry, UrbanhiveCoordinator
from .entity import UrbanhiveEntity


def last_cleaning(data: dict[str, Any]) -> datetime | None:
    """Time of the last cleaning confirmed in the app (or via the button)."""
    for flag in data.get("flags", []):
        if flag.get("key") == FLAG_CLEANING and flag.get("value"):
            return dt_util.parse_datetime(flag["value"])
    return None


def _next_cleaning(data: dict[str, Any]) -> datetime | None:
    last = last_cleaning(data)
    return last + CLEANING_INTERVAL if last else None


@dataclass(frozen=True, kw_only=True)
class UrbanhiveSensorDescription(SensorEntityDescription):
    """Describes a sensor and where its value comes from."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[UrbanhiveSensorDescription, ...] = (
    UrbanhiveSensorDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda d: d.get("details", {}).get("humidity"),
    ),
    UrbanhiveSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda d: d.get("details", {}).get("temperature"),
    ),
    UrbanhiveSensorDescription(
        key="signal_strength",
        translation_key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("details", {}).get("signalStrength"),
    ),
    # Key kept from earlier versions so the entity ID stays the same.
    UrbanhiveSensorDescription(
        key="cleaning_date",
        translation_key="last_cleaning",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=last_cleaning,
    ),
    UrbanhiveSensorDescription(
        key="next_cleaning",
        translation_key="next_cleaning",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_next_cleaning,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrbanhiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(UrbanhiveSensor(coordinator, d) for d in SENSORS)


class UrbanhiveSensor(UrbanhiveEntity, SensorEntity):
    """A single value of the farm."""

    entity_description: UrbanhiveSensorDescription

    def __init__(
        self,
        coordinator: UrbanhiveCoordinator,
        description: UrbanhiveSensorDescription,
    ) -> None:
        """Create with coordinator and description."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.farm_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Current value."""
        return self.entity_description.value_fn(self.coordinator.data)

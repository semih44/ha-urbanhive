"""Sensoren der urbanhive-homefarm."""

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

from .coordinator import UrbanhiveConfigEntry, UrbanhiveCoordinator
from .entity import UrbanhiveEntity


def _cleaning_date(data: dict[str, Any]) -> datetime | None:
    for flag in data.get("flags", []):
        if flag.get("key") == "farm.cleaning-date" and flag.get("value"):
            return dt_util.parse_datetime(flag["value"])
    return None


@dataclass(frozen=True, kw_only=True)
class UrbanhiveSensorDescription(SensorEntityDescription):
    """Beschreibt einen Sensor und woher sein Wert kommt."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[UrbanhiveSensorDescription, ...] = (
    UrbanhiveSensorDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.get("details", {}).get("humidity"),
    ),
    UrbanhiveSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
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
    UrbanhiveSensorDescription(
        key="cleaning_date",
        translation_key="cleaning_date",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_cleaning_date,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrbanhiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Die Sensoren einrichten."""
    coordinator = entry.runtime_data
    async_add_entities(
        UrbanhiveSensor(coordinator, description) for description in SENSORS
    )


class UrbanhiveSensor(UrbanhiveEntity, SensorEntity):
    """Ein einzelner Messwert der Farm."""

    entity_description: UrbanhiveSensorDescription

    def __init__(
        self,
        coordinator: UrbanhiveCoordinator,
        description: UrbanhiveSensorDescription,
    ) -> None:
        """Mit Koordinator und Beschreibung anlegen."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.farm_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Aktueller Messwert."""
        return self.entity_description.value_fn(self.coordinator.data)

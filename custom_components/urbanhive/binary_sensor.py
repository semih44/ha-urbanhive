"""Binärsensoren der urbanhive-homefarm: Wasser leer je Ebene."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import WATER_EMPTY
from .coordinator import UrbanhiveConfigEntry, UrbanhiveCoordinator
from .entity import UrbanhiveEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrbanhiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Je Ebene einen Wasser-leer-Sensor einrichten."""
    coordinator = entry.runtime_data
    async_add_entities(
        UrbanhiveWaterEmpty(coordinator, row["id"], index)
        for index, row in enumerate(coordinator.data.get("rows", []), start=1)
    )


class UrbanhiveWaterEmpty(UrbanhiveEntity, BinarySensorEntity):
    """Meldet, wenn der Wassertank einer Ebene leer ist."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "water_empty"

    def __init__(
        self, coordinator: UrbanhiveCoordinator, row_id: str, index: int
    ) -> None:
        """Für eine Ebene anlegen."""
        super().__init__(coordinator, row_id, index)
        self._row_id = row_id
        self._attr_unique_id = f"{coordinator.farm_id}_{row_id}_water_empty"

    @property
    def available(self) -> bool:
        """Nur verfügbar, solange die Ebene in den Daten steht."""
        return super().available and self.coordinator.row(self._row_id) is not None

    @property
    def is_on(self) -> bool | None:
        """True, wenn der Tank leer ist."""
        row = self.coordinator.row(self._row_id)
        if row is None or "waterLevel" not in row:
            return None
        return row["waterLevel"] == WATER_EMPTY

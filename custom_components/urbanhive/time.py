"""Times of the urbanhive homefarm: light schedule and dimming windows."""

from __future__ import annotations

from datetime import time
from typing import Any

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import UrbanhiveError
from .coordinator import UrbanhiveConfigEntry, UrbanhiveCoordinator
from .entity import MAX_DIM_WINDOWS, UrbanhiveEntity, dim_entry, with_dim_entry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrbanhiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up light on/off times and the from/until times of each dimming window."""
    coordinator = entry.runtime_data
    entities: list[TimeEntity] = [
        UrbanhiveLightTime(coordinator, "start"),
        UrbanhiveLightTime(coordinator, "end"),
    ]
    for index in range(MAX_DIM_WINDOWS):
        entities += [
            UrbanhiveDimTime(coordinator, index, "start"),
            UrbanhiveDimTime(coordinator, index, "end"),
        ]
    async_add_entities(entities)


def _read(source: dict[str, Any], prefix: str) -> time:
    return time(
        int(source.get(f"{prefix}Hour", 0)), int(source.get(f"{prefix}Minute", 0))
    )


class UrbanhiveLightTime(UrbanhiveEntity, TimeEntity):
    """Time the plant light switches on ("start") or off ("end")."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: UrbanhiveCoordinator, prefix: str) -> None:
        """Create for start or end."""
        super().__init__(coordinator)
        self._prefix = prefix
        self._attr_translation_key = f"light_{prefix}"
        self._attr_unique_id = f"{coordinator.farm_id}_light_{prefix}"

    @property
    def native_value(self) -> time | None:
        """Configured time."""
        light_time = self._details.get("lightTime")
        return _read(light_time, self._prefix) if light_time else None

    async def async_set_value(self, value: time) -> None:
        """Change the time."""
        light_time = {
            **self._details.get("lightTime", {}),
            f"{self._prefix}Hour": value.hour,
            f"{self._prefix}Minute": value.minute,
        }
        try:
            await self.coordinator.async_set_details({"lightTime": light_time})
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Time not changed: {err}") from err


class UrbanhiveDimTime(UrbanhiveEntity, TimeEntity):
    """Start ("start") or end ("end") of a dimming window."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: UrbanhiveCoordinator, index: int, prefix: str
    ) -> None:
        """Create for window number index (0-based)."""
        super().__init__(coordinator)
        self._index = index
        self._prefix = prefix
        self._attr_translation_key = f"dim_{prefix}"
        self._attr_translation_placeholders = {"window": str(index + 1)}
        # Window 1 keeps the unique IDs of earlier versions.
        window = "dim" if index == 0 else f"dim_{index + 1}"
        self._attr_unique_id = f"{coordinator.farm_id}_{window}_{prefix}"

    @property
    def available(self) -> bool:
        """Only while the window exists."""
        return super().available and dim_entry(self._details, self._index) is not None

    @property
    def native_value(self) -> time | None:
        """Configured time."""
        entry = dim_entry(self._details, self._index)
        return _read(entry, self._prefix) if entry else None

    async def async_set_value(self, value: time) -> None:
        """Change the time."""
        entry = dim_entry(self._details, self._index)
        if entry is None:
            raise HomeAssistantError("This dimming window is off")
        changed = {
            **entry,
            f"{self._prefix}Hour": value.hour,
            f"{self._prefix}Minute": value.minute,
        }
        try:
            await self.coordinator.async_set_details(
                {"dimTimeList": with_dim_entry(self._details, self._index, changed)}
            )
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Time not changed: {err}") from err

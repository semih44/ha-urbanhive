"""Switches of the urbanhive homefarm: dimming windows and water check per level."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import UrbanhiveError
from .const import DEFAULT_DIM
from .coordinator import UrbanhiveConfigEntry, UrbanhiveCoordinator
from .entity import (
    MAX_DIM_WINDOWS,
    UrbanhiveEntity,
    dim_entry,
    with_dim_entry,
    without_dim_entry,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrbanhiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the dimming windows and the water check of each level."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = [
        UrbanhiveDimWindow(coordinator, index) for index in range(MAX_DIM_WINDOWS)
    ]
    entities.extend(
        UrbanhiveWaterCheck(coordinator, row["id"], number)
        for number, row in enumerate(coordinator.data.get("rows", []), start=1)
    )
    async_add_entities(entities)


def dim_unique_suffix(index: int) -> str:
    """Unique ID suffix of a dimming window (window 1 keeps its original ID)."""
    return "dimming" if index == 0 else f"dim_{index + 1}"


class UrbanhiveDimWindow(UrbanhiveEntity, SwitchEntity):
    """A dimming window ("dim light" in the app): on = window exists."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "dimming"

    def __init__(self, coordinator: UrbanhiveCoordinator, index: int) -> None:
        """Create for window number index (0-based)."""
        super().__init__(coordinator)
        self._index = index
        self._attr_unique_id = f"{coordinator.farm_id}_{dim_unique_suffix(index)}"
        self._attr_translation_placeholders = {"window": str(index + 1)}

    @property
    def available(self) -> bool:
        """Windows are added in order: window n needs window n-1."""
        return super().available and (
            self._index == 0 or dim_entry(self._details, self._index - 1) is not None
        )

    @property
    def is_on(self) -> bool:
        """True while this dimming window exists."""
        return dim_entry(self._details, self._index) is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Add the window (two hours at 50 %, adjustable afterwards)."""
        if self.is_on:
            return
        start = 12 + 3 * self._index
        new = {**DEFAULT_DIM, "startHour": start, "endHour": start + 2}
        await self._async_set(with_dim_entry(self._details, self._index, new))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Remove the window; later windows move up."""
        await self._async_set(without_dim_entry(self._details, self._index))

    async def _async_set(self, entries: list[dict[str, Any]]) -> None:
        try:
            await self.coordinator.async_set_details({"dimTimeList": entries})
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Dimming not changed: {err}") from err


class UrbanhiveWaterCheck(UrbanhiveEntity, SwitchEntity):
    """Monitor the water level of a level (off = no "water empty" alerts)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "water_check"

    def __init__(
        self, coordinator: UrbanhiveCoordinator, row_id: str, number: int
    ) -> None:
        """Create for one level."""
        super().__init__(coordinator, row_id, number)
        self._row_id = row_id
        self._attr_unique_id = f"{coordinator.farm_id}_{row_id}_water_check"

    @property
    def available(self) -> bool:
        """Only while the level is part of the data."""
        return super().available and self.coordinator.row(self._row_id) is not None

    @property
    def is_on(self) -> bool | None:
        """True if the water level is monitored."""
        row = self.coordinator.row(self._row_id)
        return None if row is None else bool(row.get("waterCheckActive"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn monitoring on."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn monitoring off."""
        await self._async_set(False)

    async def _async_set(self, active: bool) -> None:
        row = self.coordinator.row(self._row_id)
        if row is None:
            raise HomeAssistantError("Level not found")
        try:
            await self.coordinator.client.async_set_row(
                {**row, "waterCheckActive": active}
            )
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Water check not changed: {err}") from err
        await self.coordinator.async_apply_row(self._row_id, {"waterCheckActive": active})

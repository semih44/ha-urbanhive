"""Plant light per level of the urbanhive homefarm."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import UrbanhiveError
from .coordinator import UrbanhiveConfigEntry, UrbanhiveCoordinator
from .entity import UrbanhiveEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrbanhiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one light per level."""
    coordinator = entry.runtime_data
    async_add_entities(
        UrbanhiveRowLight(coordinator, row["id"], number)
        for number, row in enumerate(coordinator.data.get("rows", []), start=1)
    )


class UrbanhiveRowLight(UrbanhiveEntity, LightEntity):
    """The plant light of a level, with brightness."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_translation_key = "row_light"

    def __init__(
        self, coordinator: UrbanhiveCoordinator, row_id: str, number: int
    ) -> None:
        """Create for one level."""
        super().__init__(coordinator, row_id, number)
        self._row_id = row_id
        self._attr_unique_id = f"{coordinator.farm_id}_{row_id}_light"

    @property
    def _row(self) -> dict[str, Any] | None:
        return self.coordinator.row(self._row_id)

    @property
    def available(self) -> bool:
        """Only while the level is part of the data."""
        return super().available and self._row is not None

    @property
    def is_on(self) -> bool | None:
        """True if the light of the level is on."""
        row = self._row
        return None if row is None else bool(row.get("lightOn"))

    @property
    def brightness(self) -> int | None:
        """Brightness 0-255 (the farm works in percent)."""
        row = self._row
        if row is None or row.get("rowBrightness") is None:
            return None
        return round(row["rowBrightness"] * 255 / 100)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, optionally with a brightness."""
        changes: dict[str, Any] = {"lightOn": True}
        if ATTR_BRIGHTNESS in kwargs:
            changes["rowBrightness"] = max(1, round(kwargs[ATTR_BRIGHTNESS] * 100 / 255))
        await self._async_change(changes)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._async_change({"lightOn": False})

    async def _async_change(self, changes: dict[str, Any]) -> None:
        row = self._row
        if row is None:
            raise HomeAssistantError("Level not found")
        try:
            await self.coordinator.client.async_set_row({**row, **changes})
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Light not switched: {err}") from err
        await self.coordinator.async_apply_row(self._row_id, changes)

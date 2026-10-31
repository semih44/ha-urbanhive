"""Numbers of the urbanhive homefarm: brightness and dimming brightness."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
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
    """Set up the brightness and the brightness of each dimming window."""
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = [UrbanhiveBrightness(coordinator)]
    entities += [UrbanhiveDimBrightness(coordinator, i) for i in range(MAX_DIM_WINDOWS)]
    async_add_entities(entities)


class _PercentNumber(UrbanhiveEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER


class UrbanhiveBrightness(_PercentNumber):
    """Base brightness of the plant light."""

    _attr_translation_key = "brightness"
    _attr_native_min_value = 10

    def __init__(self, coordinator: UrbanhiveCoordinator) -> None:
        """Create with the coordinator."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.farm_id}_brightness"

    @property
    def native_value(self) -> float | None:
        """Brightness in percent."""
        return self._details.get("brightness")

    async def async_set_native_value(self, value: float) -> None:
        """Change the brightness."""
        try:
            await self.coordinator.async_set_details({"brightness": int(value)})
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Brightness not changed: {err}") from err


class UrbanhiveDimBrightness(_PercentNumber):
    """Brightness during a dimming window."""

    _attr_translation_key = "dim_brightness"

    def __init__(self, coordinator: UrbanhiveCoordinator, index: int) -> None:
        """Create for window number index (0-based)."""
        super().__init__(coordinator)
        self._index = index
        self._attr_translation_placeholders = {"window": str(index + 1)}
        # Window 1 keeps the unique ID of earlier versions.
        window = "dim" if index == 0 else f"dim_{index + 1}"
        self._attr_unique_id = f"{coordinator.farm_id}_{window}_brightness"

    @property
    def available(self) -> bool:
        """Only while the window exists."""
        return super().available and dim_entry(self._details, self._index) is not None

    @property
    def native_value(self) -> float | None:
        """Brightness of the window in percent."""
        entry = dim_entry(self._details, self._index)
        return None if entry is None else entry.get("brightness")

    async def async_set_native_value(self, value: float) -> None:
        """Change the brightness of the window."""
        entry = dim_entry(self._details, self._index)
        if entry is None:
            raise HomeAssistantError("This dimming window is off")
        changed = {**entry, "brightness": int(value)}
        try:
            await self.coordinator.async_set_details(
                {"dimTimeList": with_dim_entry(self._details, self._index, changed)}
            )
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Dimming brightness not changed: {err}") from err

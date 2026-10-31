"""Zahlenwerte der urbanhive-homefarm: Helligkeit und Dimm-Helligkeit."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import UrbanhiveError
from .coordinator import UrbanhiveConfigEntry, UrbanhiveCoordinator
from .entity import UrbanhiveEntity, dim_entry, with_dim_entry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrbanhiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Helligkeit und Dimm-Helligkeit einrichten."""
    coordinator = entry.runtime_data
    async_add_entities(
        [UrbanhiveBrightness(coordinator), UrbanhiveDimBrightness(coordinator)]
    )


class _PercentNumber(UrbanhiveEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER


class UrbanhiveBrightness(_PercentNumber):
    """Grundhelligkeit des Pflanzenlichts."""

    _attr_translation_key = "brightness"
    _attr_native_min_value = 10

    def __init__(self, coordinator: UrbanhiveCoordinator) -> None:
        """Mit dem Koordinator anlegen."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.farm_id}_brightness"

    @property
    def native_value(self) -> float | None:
        """Eingestellte Helligkeit in Prozent."""
        return self._details.get("brightness")

    async def async_set_native_value(self, value: float) -> None:
        """Helligkeit ändern."""
        try:
            await self.coordinator.async_set_details({"brightness": int(value)})
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Helligkeit nicht geändert: {err}") from err


class UrbanhiveDimBrightness(_PercentNumber):
    """Helligkeit während der Dimmzeit."""

    _attr_translation_key = "dim_brightness"

    def __init__(self, coordinator: UrbanhiveCoordinator) -> None:
        """Mit dem Koordinator anlegen."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.farm_id}_dim_brightness"

    @property
    def available(self) -> bool:
        """Nur, solange Dimmen eingeschaltet ist."""
        return super().available and dim_entry(self._details) is not None

    @property
    def native_value(self) -> float | None:
        """Helligkeit der Dimmzeit in Prozent."""
        entry = dim_entry(self._details)
        return None if entry is None else entry.get("brightness")

    async def async_set_native_value(self, value: float) -> None:
        """Dimm-Helligkeit ändern."""
        entry = dim_entry(self._details)
        if entry is None:
            raise HomeAssistantError("Dimmen ist ausgeschaltet")
        try:
            await self.coordinator.async_set_details(
                {"dimTimeList": with_dim_entry(self._details, {**entry, "brightness": int(value)})}
            )
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Dimm-Helligkeit nicht geändert: {err}") from err

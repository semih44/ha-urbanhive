"""Buttons of the urbanhive homefarm."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import UrbanhiveError, iso_utc
from .const import FLAG_CLEANING
from .coordinator import UrbanhiveConfigEntry, UrbanhiveCoordinator
from .entity import UrbanhiveEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrbanhiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons."""
    async_add_entities([UrbanhiveCleaned(entry.runtime_data)])


class UrbanhiveCleaned(UrbanhiveEntity, ButtonEntity):
    """Record that the farm was cleaned (like confirming it in the app)."""

    _attr_translation_key = "cleaned"

    def __init__(self, coordinator: UrbanhiveCoordinator) -> None:
        """Create with the coordinator."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.farm_id}_cleaned"

    async def async_press(self) -> None:
        """Store now as the last cleaning."""
        now = dt_util.utcnow()
        try:
            await self.coordinator.client.async_set_cleaned(self.coordinator.farm_id, now)
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Cleaning not recorded: {err}") from err
        self.coordinator.async_refresh_tasks_soon()
        await self.coordinator.async_apply_flag(FLAG_CLEANING, iso_utc(now))

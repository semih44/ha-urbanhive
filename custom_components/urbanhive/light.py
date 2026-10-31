"""Licht je Ebene der urbanhive-homefarm."""

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
    """Je Ebene ein Licht einrichten."""
    coordinator = entry.runtime_data
    async_add_entities(
        UrbanhiveRowLight(coordinator, row["id"], index)
        for index, row in enumerate(coordinator.data.get("rows", []), start=1)
    )


class UrbanhiveRowLight(UrbanhiveEntity, LightEntity):
    """Das Pflanzenlicht einer Ebene, mit Helligkeit."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_translation_key = "row_light"

    def __init__(
        self, coordinator: UrbanhiveCoordinator, row_id: str, index: int
    ) -> None:
        """Für eine Ebene anlegen."""
        super().__init__(coordinator)
        self._row_id = row_id
        self._attr_unique_id = f"{coordinator.farm_id}_{row_id}_light"
        self._attr_translation_placeholders = {"row": str(index)}

    @property
    def _row(self) -> dict[str, Any] | None:
        return self.coordinator.row(self._row_id)

    @property
    def available(self) -> bool:
        """Nur verfügbar, solange die Ebene in den Daten steht."""
        return super().available and self._row is not None

    @property
    def is_on(self) -> bool | None:
        """True, wenn das Licht der Ebene an ist."""
        row = self._row
        return None if row is None else bool(row.get("lightOn"))

    @property
    def brightness(self) -> int | None:
        """Helligkeit 0–255 (die Farm rechnet in Prozent)."""
        row = self._row
        if row is None or row.get("rowBrightness") is None:
            return None
        return round(row["rowBrightness"] * 255 / 100)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Licht einschalten, optional mit Helligkeit."""
        row = self._row
        if row is None:
            raise HomeAssistantError("Ebene nicht gefunden")
        changes: dict[str, Any] = {"lightOn": True}
        if ATTR_BRIGHTNESS in kwargs:
            changes["rowBrightness"] = max(1, round(kwargs[ATTR_BRIGHTNESS] * 100 / 255))
        try:
            await self.coordinator.client.async_set_row_light(
                self.coordinator.farm_id, {**row, **changes}, True
            )
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Licht nicht geschaltet: {err}") from err
        await self.coordinator.async_apply_row(self._row_id, changes)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Licht ausschalten."""
        row = self._row
        if row is None:
            raise HomeAssistantError("Ebene nicht gefunden")
        try:
            await self.coordinator.client.async_set_row_light(
                self.coordinator.farm_id, row, False
            )
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Licht nicht geschaltet: {err}") from err
        await self.coordinator.async_apply_row(self._row_id, {"lightOn": False})

"""Uhrzeiten der urbanhive-homefarm: Lichtzeit und Dimmzeit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Any

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import UrbanhiveError
from .coordinator import UrbanhiveConfigEntry, UrbanhiveCoordinator
from .entity import UrbanhiveEntity, dim_entry, with_dim_entry


@dataclass(frozen=True, kw_only=True)
class UrbanhiveTimeDescription(TimeEntityDescription):
    """Beschreibt eine Uhrzeit und wo sie in den Farm-Einstellungen steht."""

    prefix: str  # "start" oder "end"
    dim: bool  # True: erste Dimmzeit, False: Lichtzeit


TIMES = (
    UrbanhiveTimeDescription(key="light_start", translation_key="light_start", prefix="start", dim=False),
    UrbanhiveTimeDescription(key="light_end", translation_key="light_end", prefix="end", dim=False),
    UrbanhiveTimeDescription(key="dim_start", translation_key="dim_start", prefix="start", dim=True),
    UrbanhiveTimeDescription(key="dim_end", translation_key="dim_end", prefix="end", dim=True),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrbanhiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Licht- und Dimmzeiten einrichten."""
    coordinator = entry.runtime_data
    async_add_entities(UrbanhiveTime(coordinator, d) for d in TIMES)


class UrbanhiveTime(UrbanhiveEntity, TimeEntity):
    """Beginn oder Ende der Licht- bzw. Dimmzeit."""

    _attr_entity_category = EntityCategory.CONFIG

    entity_description: UrbanhiveTimeDescription

    def __init__(
        self, coordinator: UrbanhiveCoordinator, description: UrbanhiveTimeDescription
    ) -> None:
        """Mit Koordinator und Beschreibung anlegen."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.farm_id}_{description.key}"

    def _source(self) -> dict[str, Any] | None:
        if self.entity_description.dim:
            return dim_entry(self._details)
        return self._details.get("lightTime")

    @property
    def available(self) -> bool:
        """Dimmzeiten nur, solange Dimmen eingeschaltet ist."""
        return super().available and self._source() is not None

    @property
    def native_value(self) -> time | None:
        """Eingestellte Uhrzeit."""
        source = self._source()
        if source is None:
            return None
        p = self.entity_description.prefix
        return time(int(source.get(f"{p}Hour", 0)), int(source.get(f"{p}Minute", 0)))

    async def async_set_value(self, value: time) -> None:
        """Uhrzeit ändern."""
        p = self.entity_description.prefix
        change = {f"{p}Hour": value.hour, f"{p}Minute": value.minute}
        if self.entity_description.dim:
            entry = dim_entry(self._details)
            if entry is None:
                raise HomeAssistantError("Dimmen ist ausgeschaltet")
            changes = {"dimTimeList": with_dim_entry(self._details, {**entry, **change})}
        else:
            changes = {"lightTime": {**self._details.get("lightTime", {}), **change}}
        try:
            await self.coordinator.async_set_details(changes)
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Uhrzeit nicht geändert: {err}") from err

"""Schalter der urbanhive-homefarm: Dimmen und Wasserprüfung je Ebene."""

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
from .entity import UrbanhiveEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrbanhiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Dimmen und je Ebene die Wasserprüfung einrichten."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = [UrbanhiveDimming(coordinator)]
    entities.extend(
        UrbanhiveWaterCheck(coordinator, row["id"], index)
        for index, row in enumerate(coordinator.data.get("rows", []), start=1)
    )
    async_add_entities(entities)


class UrbanhiveDimming(UrbanhiveEntity, SwitchEntity):
    """Licht zu einer festen Zeit dimmen (wie „Licht dimmen“ in der App)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "dimming"

    def __init__(self, coordinator: UrbanhiveCoordinator) -> None:
        """Mit dem Koordinator anlegen."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.farm_id}_dimming"

    @property
    def is_on(self) -> bool:
        """True, solange eine Dimmzeit eingestellt ist."""
        return bool(self._details.get("dimTimeList"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Eine Dimmzeit anlegen (12–14 Uhr, 30 %; danach anpassbar)."""
        if self.is_on:
            return
        await self._async_set([dict(DEFAULT_DIM)])

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Alle Dimmzeiten löschen."""
        await self._async_set([])

    async def _async_set(self, entries: list[dict[str, Any]]) -> None:
        try:
            await self.coordinator.async_set_details({"dimTimeList": entries})
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Dimmen nicht geändert: {err}") from err


class UrbanhiveWaterCheck(UrbanhiveEntity, SwitchEntity):
    """Wasserstand einer Ebene überwachen (aus = keine Leer-Meldung)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "water_check"

    def __init__(
        self, coordinator: UrbanhiveCoordinator, row_id: str, index: int
    ) -> None:
        """Für eine Ebene anlegen."""
        super().__init__(coordinator, row_id, index)
        self._row_id = row_id
        self._attr_unique_id = f"{coordinator.farm_id}_{row_id}_water_check"

    @property
    def available(self) -> bool:
        """Nur verfügbar, solange die Ebene in den Daten steht."""
        return super().available and self.coordinator.row(self._row_id) is not None

    @property
    def is_on(self) -> bool | None:
        """True, wenn der Wasserstand überwacht wird."""
        row = self.coordinator.row(self._row_id)
        return None if row is None else bool(row.get("waterCheckActive"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Überwachung einschalten."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Überwachung ausschalten."""
        await self._async_set(False)

    async def _async_set(self, active: bool) -> None:
        row = self.coordinator.row(self._row_id)
        if row is None:
            raise HomeAssistantError("Ebene nicht gefunden")
        try:
            await self.coordinator.client.async_set_row(
                {**row, "waterCheckActive": active}
            )
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Wasserprüfung nicht geändert: {err}") from err
        await self.coordinator.async_apply_row(self._row_id, {"waterCheckActive": active})

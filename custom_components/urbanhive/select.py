"""Selects of the urbanhive homefarm: light mode and the plant of each slot."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import UrbanhiveError
from .const import LIGHT_MODES
from .coordinator import UrbanhiveConfigEntry, UrbanhiveCoordinator
from .entity import UrbanhiveEntity

SERVICE_SET_PLANT_DATE = "set_plant_date"
ATTR_PLANTED_AT = "planted_at"


def _empty_label(hass: HomeAssistant) -> str:
    return "— leer —" if hass.config.language.startswith("de") else "— empty —"


def parse_backend_time(value: str | None) -> datetime | None:
    """Parse a backend timestamp; without a time zone it is UTC."""
    if not value:
        return None
    parsed = dt_util.parse_datetime(value)
    if parsed is not None and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.UTC)
    return parsed


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrbanhiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the light mode and one select per plant slot."""
    coordinator = entry.runtime_data
    entities: list[SelectEntity] = [UrbanhiveLightMode(coordinator)]
    for number, row in enumerate(coordinator.data.get("rows", []), start=1):
        for slot in row.get("plantSlots", []):
            entities.append(
                UrbanhiveSlotSelect(
                    coordinator, slot["id"], row["id"], number, slot.get("slotPlace", 0)
                )
            )
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_PLANT_DATE,
        {vol.Required(ATTR_PLANTED_AT): cv.datetime},
        "async_set_plant_date",
    )


class UrbanhiveLightMode(UrbanhiveEntity, SelectEntity):
    """Light mode: custom or grow mode."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = LIGHT_MODES
    _attr_translation_key = "light_mode"

    def __init__(self, coordinator: UrbanhiveCoordinator) -> None:
        """Create with the coordinator."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.farm_id}_light_mode"

    @property
    def current_option(self) -> str | None:
        """Active mode."""
        mode = self._details.get("lightTime", {}).get("lightMode")
        return mode if mode in LIGHT_MODES else None

    async def async_select_option(self, option: str) -> None:
        """Switch the mode."""
        light_time = {**self._details.get("lightTime", {}), "lightMode": option}
        try:
            await self.coordinator.async_set_details({"lightTime": light_time})
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Mode not changed: {err}") from err


class UrbanhiveSlotSelect(UrbanhiveEntity, SelectEntity):
    """A plant slot: shows the plant and lets you plant, swap or harvest."""

    _attr_translation_key = "slot"

    def __init__(
        self,
        coordinator: UrbanhiveCoordinator,
        slot_id: str,
        row_id: str,
        row_number: int,
        place: int,
    ) -> None:
        """Create for one slot."""
        super().__init__(coordinator, row_id, row_number)
        self._slot_id = slot_id
        self._attr_unique_id = f"{coordinator.farm_id}_{slot_id}_slot"
        self._attr_translation_placeholders = {"slot": str(place)}

    @property
    def _slot(self) -> dict[str, Any] | None:
        found = self.coordinator.slot(self._slot_id)
        return found[1] if found else None

    @property
    def _plant(self) -> dict[str, Any] | None:
        slot = self._slot
        if not slot or not slot.get("plantId"):
            return None
        return self.coordinator.plants.get(str(slot["plantId"]))

    @property
    def available(self) -> bool:
        """Only while the slot is part of the data."""
        return super().available and self._slot is not None

    @property
    def options(self) -> list[str]:
        """Empty plus every plant of the catalog."""
        names = sorted({p.get("name", "") for p in self.coordinator.plants.values()} - {""})
        current = self.current_option
        if current and current not in names and current != _empty_label(self.hass):
            names.append(current)
        return [_empty_label(self.hass), *names]

    @property
    def current_option(self) -> str | None:
        """Name of the plant, or empty."""
        slot = self._slot
        if slot is None:
            return None
        if not slot.get("plantId"):
            return _empty_label(self.hass)
        plant = self._plant
        return plant.get("name") if plant else f"#{slot['plantId']}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Planting date, harvest window and progress."""
        slot = self._slot or {}
        planted = parse_backend_time(slot.get("plantedAt"))
        if planted is None:
            return {}
        days = (dt_util.utcnow() - planted).days
        attrs: dict[str, Any] = {
            "plant_id": slot.get("plantId"),
            "planted_at": planted.isoformat(),
            "days_planted": days,
        }
        plant = self._plant
        if plant:
            grow = plant.get("daysToGrow") or {}
            if grow.get("min"):
                minimum = int(grow["min"])
                attrs["harvest_from"] = (planted + timedelta(days=minimum)).date().isoformat()
                attrs["progress"] = min(100, round(days * 100 / minimum))
            if grow.get("max"):
                attrs["harvest_until"] = (
                    planted + timedelta(days=int(grow["max"]))
                ).date().isoformat()
            if plant.get("plantType"):
                attrs["plant_type"] = plant["plantType"]
        return attrs

    async def async_select_option(self, option: str) -> None:
        """Plant, swap or (with "empty") harvest."""
        slot = self._slot
        if slot is None:
            raise HomeAssistantError("Plant slot not found")
        try:
            if slot.get("plantId"):
                await self.coordinator.client.async_harvest(slot)
                slot = {
                    k: v
                    for k, v in slot.items()
                    if k not in ("plantId", "plantedAt", "harvestedAt")
                }
            if option != _empty_label(self.hass):
                plant_id = next(
                    (pid for pid, p in self.coordinator.plants.items() if p.get("name") == option),
                    None,
                )
                if plant_id is None:
                    raise HomeAssistantError(f"Unknown plant: {option}")
                now = dt_util.utcnow()
                await self.coordinator.client.async_plant(slot, plant_id, now)
                slot = {**slot, "plantId": plant_id, "plantedAt": now.isoformat()}
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Planting not changed: {err}") from err
        self.coordinator.async_refresh_tasks_soon()
        await self.coordinator.async_apply_slot(self._slot_id, slot)

    async def async_set_plant_date(self, planted_at: datetime) -> None:
        """Change the planting date (action urbanhive.set_plant_date)."""
        slot = self._slot
        if not slot or not slot.get("plantId"):
            raise HomeAssistantError("There is no plant in this slot")
        if planted_at.tzinfo is None:
            planted_at = planted_at.replace(tzinfo=dt_util.get_default_time_zone())
        when = dt_util.as_utc(planted_at)
        try:
            await self.coordinator.client.async_set_plant_date(slot, when)
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Date not changed: {err}") from err
        await self.coordinator.async_apply_slot(
            self._slot_id, {**slot, "plantedAt": when.isoformat()}
        )

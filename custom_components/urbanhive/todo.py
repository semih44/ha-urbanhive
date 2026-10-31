"""Tasks of the urbanhive homefarm as a to-do list."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import UrbanhiveError, iso_utc
from .coordinator import UrbanhiveConfigEntry, UrbanhiveCoordinator
from .entity import UrbanhiveEntity
from .select import parse_backend_time

# Deleting an item hides the task for a week (like "ignore" in the app).
IGNORE_FOR = timedelta(days=7)

_TEXTS = {
    "de": {
        "CLEANING": "Farm reinigen",
        "FERTILIZER": "Düngen",
        "HARVEST_MIN": "Ernte möglich",
        "HARVEST_MAX": "Spätestens jetzt ernten",
        "TEMPERATURE": "Temperatur prüfen",
        "UPDATE_FARM": "Firmware-Update für die Farm",
        "WATERLEVEL_LOW": "Wasser nachfüllen",
        "row": "Ebene {row}",
        "slot": "Platz {slot}",
    },
    "en": {
        "CLEANING": "Clean the farm",
        "FERTILIZER": "Fertilize",
        "HARVEST_MIN": "Ready to harvest",
        "HARVEST_MAX": "Harvest now at the latest",
        "TEMPERATURE": "Check temperature",
        "UPDATE_FARM": "Firmware update for the farm",
        "WATERLEVEL_LOW": "Refill water",
        "row": "level {row}",
        "slot": "slot {slot}",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrbanhiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the task list."""
    async_add_entities([UrbanhiveTasks(entry.runtime_data)])


class UrbanhiveTasks(UrbanhiveEntity, TodoListEntity):
    """Open tasks of the farm (clean, harvest, water, ...)."""

    _attr_translation_key = "tasks"
    _attr_supported_features = (
        TodoListEntityFeature.UPDATE_TODO_ITEM | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(self, coordinator: UrbanhiveCoordinator) -> None:
        """Create with the coordinator."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.farm_id}_tasks"

    def _open_tasks(self) -> list[dict[str, Any]]:
        now = dt_util.utcnow()
        open_tasks = []
        for task in self.coordinator.tasks:
            if task.get("completedAt"):
                continue
            until = parse_backend_time(task.get("ignoreUntil"))
            if until and until > now:
                continue
            open_tasks.append(task)
        return open_tasks

    def _summary(self, task: dict[str, Any]) -> str:
        texts = _TEXTS["de" if self.hass.config.language.startswith("de") else "en"]
        kind = task.get("taskType") or task.get("taskTypeString") or ""
        parts = [texts.get(kind, kind.replace("_", " ").capitalize())]
        row_id, slot_id = task.get("farmRowId"), task.get("plantSlotId")
        for index, row in enumerate(self.coordinator.data.get("rows", []), start=1):
            if row.get("id") == row_id or any(s.get("id") == slot_id for s in row.get("plantSlots", [])):
                where = texts["row"].format(row=index)
                slot = next((s for s in row.get("plantSlots", []) if s.get("id") == slot_id), None)
                if slot:
                    where += ", " + texts["slot"].format(slot=slot.get("slotPlace"))
                    plant = self.coordinator.plants.get(str(slot.get("plantId")))
                    if plant:
                        parts.append(plant.get("name", ""))
                parts.append(f"({where})")
                break
        return " ".join(p for p in parts if p)

    @property
    def todo_items(self) -> list[TodoItem]:
        """Open tasks as to-do items."""
        return [
            TodoItem(
                uid=str(task["id"]),
                summary=self._summary(task),
                status=TodoItemStatus.NEEDS_ACTION,
            )
            for task in self._open_tasks()
            if task.get("id")
        ]

    def _task(self, uid: str) -> dict[str, Any]:
        task = next((t for t in self.coordinator.tasks if str(t.get("id")) == uid), None)
        if task is None:
            raise HomeAssistantError("Task not found")
        return task

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Checking an item marks the task as done."""
        if item.status != TodoItemStatus.COMPLETED or item.uid is None:
            return
        try:
            await self.coordinator.client.async_complete_task(self._task(item.uid))
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Task not completed: {err}") from err
        await self._async_after_change()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Deleting hides tasks for a week."""
        until = iso_utc(dt_util.utcnow() + IGNORE_FOR)
        try:
            for uid in uids:
                await self.coordinator.client.async_ignore_task(self._task(uid), until)
        except UrbanhiveError as err:
            raise HomeAssistantError(f"Task not hidden: {err}") from err
        await self._async_after_change()

    async def _async_after_change(self) -> None:
        self.coordinator.async_refresh_tasks_soon()
        await self.coordinator.async_request_refresh()

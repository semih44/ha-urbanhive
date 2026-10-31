"""Base entity and shared helpers for the urbanhive homefarm."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import UrbanhiveCoordinator

# Home Assistant offers this many dimming windows; the app allows more, extra windows
# set there are kept untouched.
MAX_DIM_WINDOWS = 3


class UrbanhiveEntity(CoordinatorEntity[UrbanhiveCoordinator]):
    """Base with device info: the farm itself or (with row_id) one of its levels.

    Every level is a sub-device of the farm. The farm's device page then only shows
    measurements, settings and tasks, while each level groups its light, water and
    plant slots.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UrbanhiveCoordinator,
        row_id: str | None = None,
        row_index: int | None = None,
    ) -> None:
        """Create for the farm, or for a level when row_id/row_index are given."""
        super().__init__(coordinator)
        if row_id is None:
            self._attr_device_info = farm_device_info(coordinator)
        else:
            farm_name = coordinator.data.get("details", {}).get("name") or "homefarm"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{coordinator.farm_id}_{row_id}")},
                manufacturer=MANUFACTURER,
                model=f"{MODEL} level",
                translation_key="level",
                translation_placeholders={"farm": farm_name, "row": str(row_index)},
                via_device_id=coordinator.device_id,
            )

    @property
    def _details(self) -> dict[str, Any]:
        return self.coordinator.data.get("details", {})


def farm_device_info(coordinator: UrbanhiveCoordinator) -> DeviceInfo:
    """Device info of the farm itself."""
    details = coordinator.data.get("details", {})
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.farm_id)},
        manufacturer=MANUFACTURER,
        model=MODEL,
        name=details.get("name") or "homefarm",
        sw_version=f"{details.get('version')}-{details.get('batchVersion')}",
        connections=({("mac", details["mac"])} if details.get("mac") else set()),
    )


def dim_entry(details: dict[str, Any], index: int) -> dict[str, Any] | None:
    """Dimming window number index (0-based), if set."""
    entries = details.get("dimTimeList") or []
    return entries[index] if index < len(entries) else None


def with_dim_entry(
    details: dict[str, Any], index: int, entry: dict[str, Any]
) -> list[dict[str, Any]]:
    """Dimming list with window index replaced (or appended as the next window)."""
    entries = list(details.get("dimTimeList") or [])
    if index < len(entries):
        entries[index] = entry
    else:
        entries.append(entry)
    return entries


def without_dim_entry(details: dict[str, Any], index: int) -> list[dict[str, Any]]:
    """Dimming list without window index; later windows move up."""
    entries = list(details.get("dimTimeList") or [])
    return [e for i, e in enumerate(entries) if i != index]

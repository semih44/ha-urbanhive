"""Gemeinsame Basis für alle homefarm-Entitäten."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import UrbanhiveCoordinator


class UrbanhiveEntity(CoordinatorEntity[UrbanhiveCoordinator]):
    """Basis mit Geräteinfo für alle Entitäten der Farm."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: UrbanhiveCoordinator) -> None:
        """Mit dem Koordinator anlegen."""
        super().__init__(coordinator)
        details = coordinator.data.get("details", {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.farm_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=details.get("name") or "homefarm",
            sw_version=f"{details.get('version')}-{details.get('batchVersion')}",
            connections=(
                {("mac", details["mac"])} if details.get("mac") else set()
            ),
        )

    @property
    def _details(self) -> dict[str, Any]:
        return self.coordinator.data.get("details", {})

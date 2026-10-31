"""Gemeinsame Basis für alle homefarm-Entitäten."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import UrbanhiveCoordinator


class UrbanhiveEntity(CoordinatorEntity[UrbanhiveCoordinator]):
    """Basis mit Geräteinfo: die Farm selbst oder (mit row_id) eine ihrer Ebenen.

    Jede Ebene ist ein eigenes Untergerät der Farm. So zeigt die Geräteseite der Farm
    nur Messwerte, Einstellungen und Aufgaben, und jede Ebene bündelt Licht, Wasser
    und ihre Pflanzplätze.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UrbanhiveCoordinator,
        row_id: str | None = None,
        row_index: int | None = None,
    ) -> None:
        """Mit dem Koordinator anlegen; row_id/row_index für Entitäten einer Ebene."""
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
    """Geräteinfo der Farm selbst."""
    details = coordinator.data.get("details", {})
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.farm_id)},
        manufacturer=MANUFACTURER,
        model=MODEL,
        name=details.get("name") or "homefarm",
        sw_version=f"{details.get('version')}-{details.get('batchVersion')}",
        connections=({("mac", details["mac"])} if details.get("mac") else set()),
    )


def dim_entry(details: dict[str, Any]) -> dict[str, Any] | None:
    """Die erste Dimmzeit der Farm (die App erlaubt mehrere; HA bearbeitet die erste)."""
    entries = details.get("dimTimeList") or []
    return entries[0] if entries else None


def with_dim_entry(details: dict[str, Any], entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Die Dimmliste mit geänderter erster Dimmzeit; weitere bleiben erhalten."""
    entries = list(details.get("dimTimeList") or [])
    return [entry, *entries[1:]] if entries else [entry]

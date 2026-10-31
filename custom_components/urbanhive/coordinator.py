"""Datenkoordinator für die urbanhive-homefarm."""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import UrbanhiveAuthError, UrbanhiveClient, UrbanhiveError
from .const import (
    CATALOG_REFRESH,
    CONF_FARM_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    TASK_REFRESH,
)

_LOGGER = logging.getLogger(__name__)

type UrbanhiveConfigEntry = ConfigEntry[UrbanhiveCoordinator]


class UrbanhiveCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Holt die Farm-Daten lokal; Pflanzenkatalog und Aufgaben aus der Cloud.

    Die Farm selbst kennt Licht, Wasser, Messwerte und die Bepflanzung. Den Katalog
    (Namen, Wachstumszeiten) und die Aufgaben hat nur die Cloud; fällt sie aus, laufen
    die lokalen Werte trotzdem weiter.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: UrbanhiveConfigEntry,
        client: UrbanhiveClient,
    ) -> None:
        """Mit Client und Konfigurationseintrag anlegen."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
            config_entry=entry,
        )
        self.client = client
        self.farm_id: str = entry.data[CONF_FARM_ID]
        self.device_id: str | None = None
        self.plants: dict[str, dict[str, Any]] = {}
        self.tasks: list[dict[str, Any]] = []
        self._catalog_at = 0.0
        self._tasks_at = 0.0

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            farm = await self.client.async_get_farm(self.farm_id)
        except UrbanhiveAuthError as err:
            raise UpdateFailed(f"Anmeldung abgelehnt: {err}") from err
        except UrbanhiveError as err:
            raise UpdateFailed(f"homefarm nicht erreichbar: {err}") from err
        if self.client.host_changed:
            self.client.host_changed = False
            self._async_store_host(self.client.host)

        now = time.monotonic()
        if now - self._catalog_at > CATALOG_REFRESH.total_seconds() or not self.plants:
            try:
                catalog = await self.client.async_get_plants()
            except UrbanhiveError as err:
                _LOGGER.debug("Pflanzenkatalog nicht geladen: %s", err)
            else:
                self.plants = {str(p["id"]): p for p in catalog if p.get("id")}
                self._catalog_at = now
        if now - self._tasks_at > TASK_REFRESH.total_seconds():
            try:
                cloud = await self.client.async_get_cloud_farm(self.farm_id)
            except UrbanhiveError as err:
                _LOGGER.debug("Aufgaben nicht geladen: %s", err)
            else:
                self.tasks = list((cloud or {}).get("tasks") or [])
                self._tasks_at = now
        return farm

    def _async_store_host(self, host: str | None) -> None:
        """Eine neu gefundene Adresse im Eintrag (und ggf. den Optionen) merken."""
        entry = self.config_entry
        options = dict(entry.options)
        if CONF_HOST in options:
            options[CONF_HOST] = host
        self.hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_HOST: host}, options=options
        )

    def async_refresh_tasks_soon(self) -> None:
        """Aufgaben beim nächsten Abruf neu aus der Cloud holen."""
        self._tasks_at = 0.0

    def row(self, row_id: str) -> dict[str, Any] | None:
        """Die aktuellen Daten einer Ebene anhand ihrer ID liefern."""
        for row in self.data.get("rows", []):
            if row.get("id") == row_id:
                return row
        return None

    def slot(self, slot_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Ebene und Pflanzplatz zu einer Platz-ID liefern."""
        for row in self.data.get("rows", []):
            for slot in row.get("plantSlots", []):
                if slot.get("id") == slot_id:
                    return row, slot
        return None

    async def async_apply_row(self, row_id: str, changes: dict[str, Any]) -> None:
        """Eine bestätigte Änderung an einer Ebene übernehmen und später nachprüfen.

        Die Farm übernimmt eine Änderung erst nach ein paar Sekunden in ihre Daten;
        ein sofortiges Neuladen würde noch den alten Zustand zeigen.
        """
        rows = [
            {**row, **changes} if row.get("id") == row_id else row
            for row in self.data.get("rows", [])
        ]
        self._apply({**self.data, "rows": rows})

    async def async_apply_slot(self, slot_id: str, slot: dict[str, Any]) -> None:
        """Einen geänderten Pflanzplatz übernehmen und später nachprüfen."""
        rows = []
        for row in self.data.get("rows", []):
            slots = [slot if s.get("id") == slot_id else s for s in row.get("plantSlots", [])]
            rows.append({**row, "plantSlots": slots})
        self._apply({**self.data, "rows": rows})

    async def async_set_details(self, changes: dict[str, Any]) -> None:
        """Farm-Einstellungen ändern (Lichtzeiten, Modus, Dimmen, Helligkeit)."""
        details = {**self.data.get("details", {}), **changes}
        await self.client.async_update_details(self.farm_id, details)
        self._apply({**self.data, "details": details})

    def _apply(self, data: dict[str, Any]) -> None:
        self.async_set_updated_data(data)
        async_call_later(self.hass, 10, self._async_delayed_refresh)

    async def _async_delayed_refresh(self, _now: Any) -> None:
        await self.async_request_refresh()

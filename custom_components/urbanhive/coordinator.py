"""Data update coordinator for the urbanhive homefarm."""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
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
    """Reads the farm locally; plant catalog and tasks come from the cloud.

    The farm itself knows light, water, measurements, settings and what is planted.
    Only the cloud has the plant catalog (names, growing times) and the tasks; if it is
    unavailable, the local values keep working.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: UrbanhiveConfigEntry,
        client: UrbanhiveClient,
    ) -> None:
        """Create with client and config entry."""
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
            raise ConfigEntryAuthFailed(f"sign-in rejected: {err}") from err
        except UrbanhiveError as err:
            raise UpdateFailed(f"homefarm not reachable: {err}") from err
        if self.client.host_changed:
            self.client.host_changed = False
            self._async_store_host(self.client.host)

        now = time.monotonic()
        if not self.plants or now - self._catalog_at > CATALOG_REFRESH.total_seconds():
            try:
                catalog = await self.client.async_get_plants()
            except UrbanhiveError as err:
                _LOGGER.debug("Plant catalog not loaded: %s", err)
            else:
                self.plants = {str(p["id"]): p for p in catalog if p.get("id")}
                self._catalog_at = now
        if now - self._tasks_at > TASK_REFRESH.total_seconds():
            try:
                cloud = await self.client.async_get_cloud_farm(self.farm_id)
            except UrbanhiveError as err:
                _LOGGER.debug("Tasks not loaded: %s", err)
            else:
                self.tasks = list(cloud.get("tasks") or [])
                self._tasks_at = now
        return farm

    def _async_store_host(self, host: str | None) -> None:
        """Remember a newly found address in the entry (and its options, if set)."""
        entry = self.config_entry
        options = dict(entry.options)
        if CONF_HOST in options:
            options[CONF_HOST] = host
        self.hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_HOST: host}, options=options
        )

    def async_refresh_tasks_soon(self) -> None:
        """Fetch tasks from the cloud on the next update."""
        self._tasks_at = 0.0

    def row(self, row_id: str) -> dict[str, Any] | None:
        """Return the current data of a level."""
        for row in self.data.get("rows", []):
            if row.get("id") == row_id:
                return row
        return None

    def slot(self, slot_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Return level and plant slot for a slot ID."""
        for row in self.data.get("rows", []):
            for slot in row.get("plantSlots", []):
                if slot.get("id") == slot_id:
                    return row, slot
        return None

    async def async_apply_row(self, row_id: str, changes: dict[str, Any]) -> None:
        """Apply a confirmed change to a level now and re-check it shortly after.

        The farm takes a few seconds before a change shows up in its data; refreshing
        immediately would still return the old state.
        """
        rows = [
            {**row, **changes} if row.get("id") == row_id else row
            for row in self.data.get("rows", [])
        ]
        self._apply({**self.data, "rows": rows})

    async def async_apply_slot(self, slot_id: str, slot: dict[str, Any]) -> None:
        """Apply a changed plant slot now and re-check it shortly after."""
        rows = []
        for row in self.data.get("rows", []):
            slots = [slot if s.get("id") == slot_id else s for s in row.get("plantSlots", [])]
            rows.append({**row, "plantSlots": slots})
        self._apply({**self.data, "rows": rows})

    async def async_apply_flag(self, key: str, value: str) -> None:
        """Apply a changed flag now; the farm takes it over from the cloud shortly."""
        flags = [f for f in self.data.get("flags") or [] if f.get("key") != key]
        self._apply({**self.data, "flags": [*flags, {"key": key, "value": value}]})

    async def async_set_details(self, changes: dict[str, Any]) -> None:
        """Change farm settings (light times, mode, dimming, brightness)."""
        details = {**self.data.get("details", {}), **changes}
        await self.client.async_update_details(self.farm_id, details)
        self._apply({**self.data, "details": details})

    def _apply(self, data: dict[str, Any]) -> None:
        self.async_set_updated_data(data)
        async_call_later(self.hass, 10, self._async_delayed_refresh)

    async def _async_delayed_refresh(self, _now: Any) -> None:
        await self.async_request_refresh()

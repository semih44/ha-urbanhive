"""Datenkoordinator für die urbanhive-homefarm."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import UrbanhiveAuthError, UrbanhiveClient, UrbanhiveError
from .const import CONF_FARM_ID, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type UrbanhiveConfigEntry = ConfigEntry[UrbanhiveCoordinator]


class UrbanhiveCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Holt regelmäßig die Farm-Daten und stellt sie den Entitäten bereit."""

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

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.async_get_farm(self.farm_id)
        except UrbanhiveAuthError as err:
            raise UpdateFailed(f"Anmeldung abgelehnt: {err}") from err
        except UrbanhiveError as err:
            raise UpdateFailed(f"homefarm nicht erreichbar: {err}") from err

    def row(self, row_id: str) -> dict[str, Any] | None:
        """Die aktuellen Daten einer Ebene anhand ihrer ID liefern."""
        for row in self.data.get("rows", []):
            if row.get("id") == row_id:
                return row
        return None

    async def async_apply_row(self, row_id: str, changes: dict[str, Any]) -> None:
        """Eine bestätigte Änderung sofort übernehmen und später nachprüfen.

        Die Farm übernimmt eine Änderung erst nach ein paar Sekunden in ihre Daten;
        ein sofortiges Neuladen würde noch den alten Zustand zeigen.
        """
        rows = [
            {**row, **changes} if row.get("id") == row_id else row
            for row in self.data.get("rows", [])
        ]
        self.async_set_updated_data({**self.data, "rows": rows})
        self.hass.loop.call_later(
            10, lambda: self.hass.async_create_task(self.async_request_refresh())
        )

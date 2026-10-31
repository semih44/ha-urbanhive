"""Diagnostics for the urbanhive homefarm (download from the device page)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import CONF_EMAIL, CONF_PASSWORD, CONF_REFRESH_TOKEN
from .coordinator import UrbanhiveConfigEntry

TO_REDACT = {
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_HOST,
    "localIP",
    "mac",
    "userId",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: UrbanhiveConfigEntry
) -> dict[str, Any]:
    """Return redacted entry data, farm data and tasks."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "local_access": bool(coordinator.client.host)
        and not coordinator.client.prefer_cloud,
        "last_update_success": coordinator.last_update_success,
        "farm": async_redact_data(coordinator.data or {}, TO_REDACT),
        "tasks": async_redact_data(coordinator.tasks, TO_REDACT),
        "plant_catalog_size": len(coordinator.plants),
    }

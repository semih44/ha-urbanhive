"""Die urbanhive-homefarm-Integration – lokal zuerst, Cloud optional."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import UrbanhiveAuth, UrbanhiveClient
from .const import CONF_EMAIL, CONF_PASSWORD, CONF_PREFER_CLOUD
from .coordinator import UrbanhiveConfigEntry, UrbanhiveCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.LIGHT, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: UrbanhiveConfigEntry
) -> bool:
    """Einen Konfigurationseintrag einrichten."""
    session = async_get_clientsession(hass)
    auth = UrbanhiveAuth(session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])

    host = entry.options.get(CONF_HOST) or entry.data.get(CONF_HOST)
    prefer_cloud = entry.options.get(CONF_PREFER_CLOUD, False)
    client = UrbanhiveClient(session, auth, host=host or None, prefer_cloud=prefer_cloud)

    coordinator = UrbanhiveCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: UrbanhiveConfigEntry
) -> bool:
    """Einen Konfigurationseintrag entladen."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: UrbanhiveConfigEntry) -> None:
    """Nach Änderung der Optionen neu laden."""
    await hass.config_entries.async_reload(entry.entry_id)

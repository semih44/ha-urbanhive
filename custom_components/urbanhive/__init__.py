"""The urbanhive homefarm integration - local first, cloud optional."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import UrbanhiveAuth, UrbanhiveClient
from .const import CONF_EMAIL, CONF_PASSWORD, CONF_PREFER_CLOUD, CONF_REFRESH_TOKEN
from .coordinator import UrbanhiveConfigEntry, UrbanhiveCoordinator
from .entity import farm_device_info

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
    Platform.TODO,
]


async def async_setup_entry(hass: HomeAssistant, entry: UrbanhiveConfigEntry) -> bool:
    """Set up a config entry."""
    session = async_get_clientsession(hass)

    @callback
    def _store_refresh_token(token: str) -> None:
        # Keep only the refresh token; drop a password left by older versions.
        data = {k: v for k, v in entry.data.items() if k != CONF_PASSWORD}
        hass.config_entries.async_update_entry(
            entry, data={**data, CONF_REFRESH_TOKEN: token}
        )

    auth = UrbanhiveAuth(
        session,
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
        email=entry.data.get(CONF_EMAIL),
        password=entry.data.get(CONF_PASSWORD),
        on_refresh_token=_store_refresh_token,
    )
    host = entry.options.get(CONF_HOST) or entry.data.get(CONF_HOST)
    client = UrbanhiveClient(
        session,
        auth,
        host=host or None,
        prefer_cloud=entry.options.get(CONF_PREFER_CLOUD, False),
    )

    coordinator = UrbanhiveCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    if CONF_PASSWORD in entry.data and auth.refresh_token:
        _store_refresh_token(auth.refresh_token)

    # Create the farm device first so that the levels can point to it as sub-devices.
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **farm_device_info(coordinator)
    )
    coordinator.device_id = device.id

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: UrbanhiveConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(
    hass: HomeAssistant, entry: UrbanhiveConfigEntry
) -> None:
    """Reload when the user changed the options."""
    coordinator = entry.runtime_data
    host = entry.options.get(CONF_HOST) or entry.data.get(CONF_HOST)
    prefer_cloud = entry.options.get(CONF_PREFER_CLOUD, False)
    # Updates of the stored token or a followed address need no reload.
    if (
        host == coordinator.client.host
        and prefer_cloud == coordinator.client.prefer_cloud
    ):
        return
    await hass.config_entries.async_reload(entry.entry_id)

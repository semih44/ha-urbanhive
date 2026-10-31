"""Config flow for the urbanhive homefarm."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    UrbanhiveAuth,
    UrbanhiveAuthError,
    UrbanhiveClient,
    UrbanhiveConnectionError,
    UrbanhiveError,
)
from .const import (
    CONF_EMAIL,
    CONF_FARM_ID,
    CONF_PASSWORD,
    CONF_PREFER_CLOUD,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class UrbanhiveConfigFlow(ConfigFlow, domain=DOMAIN):
    """Sign in and pick the farm."""

    VERSION = 1

    def __init__(self) -> None:
        """Prepare the flow state."""
        self._auth: UrbanhiveAuth | None = None
        self._client: UrbanhiveClient | None = None
        self._email: str | None = None
        self._host: str | None = None
        self._farms: list[dict[str, Any]] = []

    async def _async_sign_in(
        self, email: str, password: str, host: str | None = None
    ) -> dict[str, str]:
        """Sign in and load the farms; return form errors, if any."""
        session = async_get_clientsession(self.hass)
        auth = UrbanhiveAuth(session, email=email, password=password)
        client = UrbanhiveClient(session, auth, host=host)
        try:
            await auth.async_sign_in()
            self._farms = await client.async_list_farms()
        except UrbanhiveAuthError:
            return {"base": "invalid_auth"}
        except UrbanhiveConnectionError:
            return {"base": "cannot_connect"}
        except UrbanhiveError:
            return {"base": "unknown"}
        if not self._farms:
            return {"base": "no_farms"}
        self._auth, self._client, self._email, self._host = auth, client, email, host
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the urbanhive account."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_sign_in(
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
                user_input.get(CONF_HOST) or None,
            )
            if not errors:
                if len(self._farms) == 1:
                    return await self._async_create(self._farms[0])
                return await self.async_step_farm()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_HOST): str,
                }
            ),
            errors=errors,
        )

    async def async_step_farm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the farm if the account has more than one."""
        if user_input is not None:
            farm = next(
                f for f in self._farms if f.get("id") == user_input[CONF_FARM_ID]
            )
            return await self._async_create(farm)

        options = {
            f["id"]: f.get("details", {}).get("name", f["id"]) for f in self._farms
        }
        return self.async_show_form(
            step_id="farm",
            data_schema=vol.Schema({vol.Required(CONF_FARM_ID): vol.In(options)}),
        )

    async def _async_create(self, farm: dict[str, Any]) -> ConfigFlowResult:
        """Create the entry and confirm the farm's local address, if possible."""
        assert self._auth is not None and self._client is not None
        farm_id = farm["id"]
        await self.async_set_unique_id(farm_id)
        self._abort_if_unique_id_configured()

        host = self._host or farm.get("details", {}).get("localIP")
        verified_host: str | None = None
        if host:
            try:
                await self._client.async_get_info(host)
                verified_host = host
            except UrbanhiveError:
                _LOGGER.debug("Farm not reachable locally at %s", host)

        return self.async_create_entry(
            title=farm.get("details", {}).get("name") or "homefarm",
            data={
                CONF_EMAIL: self._email,
                CONF_REFRESH_TOKEN: self._auth.refresh_token,
                CONF_HOST: verified_host,
                CONF_FARM_ID: farm_id,
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start re-authentication after the stored token stopped working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the password again."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_sign_in(
                entry.data[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if not errors:
                assert self._auth is not None
                data = {k: v for k, v in entry.data.items() if k != CONF_PASSWORD}
                return self.async_update_reload_and_abort(
                    entry, data={**data, CONF_REFRESH_TOKEN: self._auth.refresh_token}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        """Return the options flow."""
        return UrbanhiveOptionsFlow()


class UrbanhiveOptionsFlow(OptionsFlow):
    """Change the local address or force cloud access."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        data = self.config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_HOST,
                        default=options.get(CONF_HOST, data.get(CONF_HOST) or ""),
                    ): str,
                    vol.Optional(
                        CONF_PREFER_CLOUD,
                        default=options.get(CONF_PREFER_CLOUD, False),
                    ): bool,
                }
            ),
        )

"""Einrichtungsdialog für die urbanhive-homefarm."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
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
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class UrbanhiveConfigFlow(ConfigFlow, domain=DOMAIN):
    """Führt durch Anmeldung und Auswahl der Farm."""

    VERSION = 1

    def __init__(self) -> None:
        """Zwischenstand der Einrichtung vorbereiten."""
        self._auth: UrbanhiveAuth | None = None
        self._client: UrbanhiveClient | None = None
        self._data: dict[str, Any] = {}
        self._farms: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Zugangsdaten abfragen und anmelden."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            auth = UrbanhiveAuth(
                session, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            client = UrbanhiveClient(session, auth, host=user_input.get(CONF_HOST))
            try:
                self._farms = await client.async_list_farms()
            except UrbanhiveAuthError:
                errors["base"] = "invalid_auth"
            except UrbanhiveConnectionError:
                errors["base"] = "cannot_connect"
            except UrbanhiveError:
                errors["base"] = "unknown"
            else:
                if not self._farms:
                    errors["base"] = "no_farms"
                else:
                    self._auth = auth
                    self._client = client
                    self._data = {
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_HOST: user_input.get(CONF_HOST),
                    }
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
        """Bei mehreren Farmen die gewünschte auswählen."""
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
        """Den Eintrag anlegen und, wenn möglich, die lokale Adresse bestätigen."""
        farm_id = farm["id"]
        await self.async_set_unique_id(farm_id)
        self._abort_if_unique_id_configured()

        host = self._data.get(CONF_HOST) or farm.get("details", {}).get("localIP")
        verified_host: str | None = None
        if host and self._client is not None:
            self._client.set_host(host)
            try:
                await self._client.async_get_info(host)
                verified_host = host
            except UrbanhiveError:
                _LOGGER.debug("Farm lokal unter %s nicht erreichbar", host)

        name = farm.get("details", {}).get("name") or "homefarm"
        return self.async_create_entry(
            title=name,
            data={
                CONF_EMAIL: self._data[CONF_EMAIL],
                CONF_PASSWORD: self._data[CONF_PASSWORD],
                CONF_HOST: verified_host,
                CONF_FARM_ID: farm_id,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        """Optionen (Cloud erzwingen, Adresse ändern) bereitstellen."""
        return UrbanhiveOptionsFlow()


class UrbanhiveOptionsFlow(OptionsFlow):
    """Erlaubt, die lokale Adresse zu ändern oder die Cloud zu erzwingen."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Optionen anzeigen und speichern."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options
        data = self.config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_HOST,
                        default=current.get(CONF_HOST, data.get(CONF_HOST) or ""),
                    ): str,
                    vol.Optional(
                        CONF_PREFER_CLOUD,
                        default=current.get(CONF_PREFER_CLOUD, False),
                    ): bool,
                }
            ),
        )

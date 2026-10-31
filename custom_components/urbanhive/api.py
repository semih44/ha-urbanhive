"""Client für die urbanhive-homefarm: lokal zuerst, Cloud optional.

Die Farm bietet im Heimnetz eine HTTP-Schnittstelle, die dieselben Daten liefert wie die
urbanhive-Cloud — und zwar in Echtzeit, während die Cloud zuletzt gespeicherte Werte zeigt.
Darum fragt dieser Client die Farm bevorzugt direkt an und greift nur bei Bedarf (oder auf
Wunsch) auf die Cloud zurück. Angemeldet wird über Firebase mit E-Mail und Passwort des
Nutzers; der Pflanzenkatalog kommt ausschließlich aus der Cloud.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import (
    APP_VERSION,
    CHANNEL,
    CLOUD_BASE,
    CLOUD_TIMEOUT,
    DEFAULT_LANG,
    FIREBASE_API_KEY,
    FIREBASE_REFRESH_URL,
    FIREBASE_SIGNIN_URL,
    LOCAL_PORT,
    LOCAL_TIMEOUT,
    LOCAL_TOKEN_MARKER,
    LOCAL_TOKEN_MARKER_INDEX,
)

_LOGGER = logging.getLogger(__name__)

# An jede Backend-Anfrage angehängte Parameter, die die App ebenfalls mitschickt.
_APP_PARAMS = {"appVersion": APP_VERSION, "channel": CHANNEL, "lng": DEFAULT_LANG}


class UrbanhiveError(Exception):
    """Allgemeiner Fehler beim Zugriff auf die homefarm."""


class UrbanhiveAuthError(UrbanhiveError):
    """Anmeldung fehlgeschlagen (falsche Zugangsdaten)."""


class UrbanhiveConnectionError(UrbanhiveError):
    """Farm bzw. Backend nicht erreichbar."""


class UrbanhiveAuth:
    """Hält ein gültiges Firebase-ID-Token und erneuert es bei Bedarf."""

    def __init__(self, session: ClientSession, email: str, password: str) -> None:
        """Mit Sitzung und Zugangsdaten anlegen."""
        self._session = session
        self._email = email
        self._password = password
        self._id_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0
        self.local_id: str | None = None

    async def async_get_token(self) -> str:
        """Ein gültiges ID-Token liefern (anmelden oder erneuern, wenn nötig)."""
        if self._id_token and time.time() < self._expires_at - 120:
            return self._id_token
        if self._refresh_token:
            try:
                await self._async_refresh()
                return self._id_token  # type: ignore[return-value]
            except UrbanhiveAuthError:
                _LOGGER.debug("Token-Erneuerung fehlgeschlagen, melde neu an")
        await self._async_sign_in()
        return self._id_token  # type: ignore[return-value]

    async def _async_sign_in(self) -> None:
        data = await self._async_identity_call(
            FIREBASE_SIGNIN_URL,
            {
                "email": self._email,
                "password": self._password,
                "returnSecureToken": True,
            },
        )
        self._id_token = data["idToken"]
        self._refresh_token = data["refreshToken"]
        self._expires_at = time.time() + int(data["expiresIn"])
        self.local_id = data.get("localId")

    async def _async_refresh(self) -> None:
        data = await self._async_identity_call(
            FIREBASE_REFRESH_URL,
            {"grant_type": "refresh_token", "refresh_token": self._refresh_token},
            form=True,
        )
        self._id_token = data["id_token"]
        self._refresh_token = data["refresh_token"]
        self._expires_at = time.time() + int(data["expires_in"])
        self.local_id = data.get("user_id", self.local_id)

    async def _async_identity_call(
        self, url: str, payload: dict[str, Any], form: bool = False
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"params": {"key": FIREBASE_API_KEY}}
        if form:
            kwargs["data"] = payload
        else:
            kwargs["json"] = payload
        try:
            async with self._session.post(
                url, timeout=CLOUD_TIMEOUT, **kwargs
            ) as resp:
                body = await resp.json(content_type=None)
                if resp.status != 200:
                    message = (body or {}).get("error", {}).get("message", "")
                    if resp.status in (400, 401, 403):
                        raise UrbanhiveAuthError(message or "Anmeldung abgelehnt")
                    raise UrbanhiveConnectionError(f"HTTP {resp.status}: {message}")
                return body
        except ClientError as err:
            raise UrbanhiveConnectionError(str(err)) from err


class UrbanhiveClient:
    """Liest und steuert die homefarm – lokal zuerst, Cloud optional."""

    def __init__(
        self,
        session: ClientSession,
        auth: UrbanhiveAuth,
        host: str | None = None,
        prefer_cloud: bool = False,
    ) -> None:
        """Mit Sitzung, Anmeldung und optionaler lokaler Adresse anlegen."""
        self._session = session
        self._auth = auth
        self._host = host
        self._prefer_cloud = prefer_cloud

    @property
    def host(self) -> str | None:
        """Lokale Adresse der Farm, falls bekannt."""
        return self._host

    def set_host(self, host: str | None) -> None:
        """Lokale Adresse setzen (z. B. nach erneuter Erkennung)."""
        self._host = host

    @staticmethod
    def _local_token(token: str) -> str:
        """Das von der Farm lokal erwartete Token bilden."""
        if len(token) <= LOCAL_TOKEN_MARKER_INDEX:
            return token
        i = LOCAL_TOKEN_MARKER_INDEX
        return token[:i] + LOCAL_TOKEN_MARKER + token[i:]

    async def async_get_info(self, host: str) -> dict[str, Any]:
        """Das offene /info der Farm lesen (ohne Anmeldung) – auch zur Erkennung."""
        url = f"http://{host}:{LOCAL_PORT}/info"
        try:
            async with self._session.get(url, timeout=LOCAL_TIMEOUT) as resp:
                if resp.status != 200:
                    raise UrbanhiveConnectionError(f"HTTP {resp.status}")
                return await resp.json(content_type=None)
        except ClientError as err:
            raise UrbanhiveConnectionError(str(err)) from err

    async def async_get_farm(self, farm_id: str) -> dict[str, Any]:
        """Alle Farm-Daten holen – bevorzugt lokal, sonst aus der Cloud."""
        if self._host and not self._prefer_cloud:
            try:
                return await self._async_local_get(f"/v2/farms?id={farm_id}")
            except UrbanhiveConnectionError as err:
                _LOGGER.debug("Lokaler Abruf fehlgeschlagen (%s), nutze Cloud", err)
        farms = await self._async_cloud_get("/farms")
        farm = next((f for f in farms if f.get("id") == farm_id), None)
        if farm is None:
            raise UrbanhiveConnectionError("Farm nicht im Konto gefunden")
        return farm

    async def async_list_farms(self) -> list[dict[str, Any]]:
        """Alle Farmen des Kontos aus der Cloud auflisten (für die Einrichtung)."""
        return await self._async_cloud_get("/farms")

    async def async_get_plants(self) -> list[dict[str, Any]]:
        """Den Pflanzenkatalog aus der Cloud holen."""
        return await self._async_cloud_get("/plants")

    async def async_set_row_light(
        self, farm_id: str, row: dict[str, Any], on: bool
    ) -> None:
        """Das Licht einer Ebene schalten (lokal, sonst Cloud)."""
        payload = {**row, "lightOn": on}
        await self._async_put_row(farm_id, payload)

    async def async_set_row_brightness(
        self, farm_id: str, row: dict[str, Any], brightness: int
    ) -> None:
        """Die Helligkeit einer Ebene setzen (0–100)."""
        payload = {**row, "rowBrightness": max(0, min(100, brightness))}
        await self._async_put_row(farm_id, payload)

    async def _async_put_row(self, farm_id: str, row: dict[str, Any]) -> None:
        row_id = row["id"]
        if self._host and not self._prefer_cloud:
            try:
                await self._async_local_put(f"/v2/rows?id={row_id}", row)
                return
            except UrbanhiveConnectionError as err:
                _LOGGER.debug("Lokales Schalten fehlgeschlagen (%s), nutze Cloud", err)
        await self._async_cloud_put(f"/rows?id={row_id}", row)

    # -- lokale Aufrufe -------------------------------------------------------

    async def _async_local_headers(self) -> dict[str, str]:
        token = self._local_token(await self._auth.async_get_token())
        return {"Authorization": token, "User-Agent": "urbanhive-App"}

    async def _async_local_get(self, path: str) -> Any:
        url = f"http://{self._host}:{LOCAL_PORT}{path}"
        sep = "&" if "?" in path else "?"
        try:
            async with self._session.get(
                url + sep + _query(),
                headers=await self._async_local_headers(),
                timeout=LOCAL_TIMEOUT,
            ) as resp:
                return await _handle(resp)
        except ClientError as err:
            raise UrbanhiveConnectionError(str(err)) from err

    async def _async_local_put(self, path: str, payload: dict[str, Any]) -> Any:
        url = f"http://{self._host}:{LOCAL_PORT}{path}"
        sep = "&" if "?" in path else "?"
        try:
            async with self._session.put(
                url + sep + _query(),
                headers=await self._async_local_headers(),
                json=payload,
                timeout=LOCAL_TIMEOUT,
            ) as resp:
                return await _handle(resp)
        except ClientError as err:
            raise UrbanhiveConnectionError(str(err)) from err

    # -- Cloud-Aufrufe --------------------------------------------------------

    async def _async_cloud_headers(self) -> dict[str, str]:
        token = await self._auth.async_get_token()
        return {"Authorization": token, "User-Agent": "urbanhive-App"}

    async def _async_cloud_get(self, path: str) -> Any:
        try:
            async with self._session.get(
                CLOUD_BASE + path,
                headers=await self._async_cloud_headers(),
                params=_APP_PARAMS,
                timeout=CLOUD_TIMEOUT,
            ) as resp:
                return await _handle(resp)
        except ClientError as err:
            raise UrbanhiveConnectionError(str(err)) from err

    async def _async_cloud_put(self, path: str, payload: dict[str, Any]) -> Any:
        try:
            async with self._session.put(
                CLOUD_BASE + path,
                headers=await self._async_cloud_headers(),
                params=_APP_PARAMS,
                json=payload,
                timeout=CLOUD_TIMEOUT,
            ) as resp:
                return await _handle(resp)
        except ClientError as err:
            raise UrbanhiveConnectionError(str(err)) from err


def _query() -> str:
    from urllib.parse import urlencode

    return urlencode(_APP_PARAMS)


async def _handle(resp: Any) -> Any:
    if resp.status in (401, 403):
        raise UrbanhiveAuthError(f"HTTP {resp.status}")
    if resp.status >= 400:
        raise UrbanhiveConnectionError(f"HTTP {resp.status}")
    if resp.status == 204 or resp.content_length == 0:
        return None
    return await resp.json(content_type=None)

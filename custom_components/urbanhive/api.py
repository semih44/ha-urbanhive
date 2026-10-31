"""Client for the urbanhive homefarm: local first, cloud optional.

The farm serves an HTTP API on the local network that returns the same data as the
urbanhive cloud, but live - the cloud may hold values that are months old. This client
therefore reads and controls the farm directly and only uses the cloud for sign-in, the
plant catalog, plant slots, tasks and flags (or everything, if the user asks for it).
Authentication uses Firebase with the user's urbanhive account; only the refresh token
is kept.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
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
    FLAG_CLEANING,
    LOCAL_PORT,
    LOCAL_TIMEOUT,
    LOCAL_TOKEN_MARKER,
    LOCAL_TOKEN_MARKER_INDEX,
)

_LOGGER = logging.getLogger(__name__)

# Parameters the app appends to every backend request.
_APP_PARAMS = {"appVersion": APP_VERSION, "channel": CHANNEL, "lng": DEFAULT_LANG}

# Fields the app sends when writing (its data objects, without display-only extras).
_DETAILS_KEYS = (
    "brightness", "humidity", "localIP", "signalStrength", "temperature", "version",
    "batchVersion", "farmEnv", "name", "mac", "timezone", "lightTime", "dimTimeList",
)
_ROW_KEYS = (
    "id", "lightOn", "waterLevel", "plantSlots", "factorLED", "rowLightTime",
    "waterCheckActive", "rowBrightness",
)
_SLOT_KEYS = ("id", "slotPlace", "plantId", "plantedAt", "harvestedAt", "customAttributes")
_TASK_KEYS = (
    "id", "taskType", "farmId", "farmRowId", "plantSlotId", "createdAt",
    "completedAt", "ignoreUntil",
)


class UrbanhiveError(Exception):
    """Generic error talking to the homefarm."""


class UrbanhiveAuthError(UrbanhiveError):
    """Sign-in rejected (wrong credentials or revoked token)."""


class UrbanhiveConnectionError(UrbanhiveError):
    """Farm or backend not reachable."""


def iso_utc(when: datetime) -> str:
    """Format a point in time the way the app sends it (UTC with "Z").

    The backend reads timestamps without a time zone as UTC.
    """
    when = when.astimezone(UTC)
    return when.strftime("%Y-%m-%dT%H:%M:%S.") + f"{when.microsecond // 1000:03d}Z"


def _slot_dto(slot: dict[str, Any]) -> dict[str, Any]:
    return {k: slot.get(k) for k in _SLOT_KEYS}


def _task_dto(task: dict[str, Any]) -> dict[str, Any]:
    return {k: task.get(k) for k in _TASK_KEYS}


class UrbanhiveAuth:
    """Keeps a valid Firebase ID token and renews it when needed.

    Normally only the refresh token is known. Email and password are only passed during
    setup, re-authentication or when migrating an older config entry.
    """

    def __init__(
        self,
        session: ClientSession,
        refresh_token: str | None = None,
        email: str | None = None,
        password: str | None = None,
        on_refresh_token: Callable[[str], None] | None = None,
    ) -> None:
        """Create with a refresh token or with email and password."""
        self._session = session
        self._email = email
        self._password = password
        self._on_refresh_token = on_refresh_token
        self._id_token: str | None = None
        self._expires_at = 0.0
        self.refresh_token = refresh_token

    async def async_get_token(self) -> str:
        """Return a valid ID token (refreshing or signing in when necessary)."""
        if self._id_token and time.time() < self._expires_at - 120:
            return self._id_token
        if self.refresh_token:
            try:
                await self._async_refresh()
            except UrbanhiveAuthError:
                if not (self._email and self._password):
                    raise
                _LOGGER.debug("Token refresh failed, signing in again")
            else:
                return self._id_token  # type: ignore[return-value]
        if not (self._email and self._password):
            raise UrbanhiveAuthError("No credentials available")
        await self.async_sign_in()
        return self._id_token  # type: ignore[return-value]

    async def async_sign_in(self) -> None:
        """Sign in with email and password."""
        data = await self._async_identity_call(
            FIREBASE_SIGNIN_URL,
            {
                "email": self._email,
                "password": self._password,
                "returnSecureToken": True,
            },
        )
        self._store(data["idToken"], data["refreshToken"], data["expiresIn"])

    async def _async_refresh(self) -> None:
        data = await self._async_identity_call(
            FIREBASE_REFRESH_URL,
            {"grant_type": "refresh_token", "refresh_token": self.refresh_token},
            form=True,
        )
        self._store(data["id_token"], data["refresh_token"], data["expires_in"])

    def _store(self, id_token: str, refresh_token: str, expires_in: str) -> None:
        self._id_token = id_token
        self._expires_at = time.time() + int(expires_in)
        if refresh_token != self.refresh_token:
            self.refresh_token = refresh_token
            if self._on_refresh_token:
                self._on_refresh_token(refresh_token)

    async def _async_identity_call(
        self, url: str, payload: dict[str, Any], form: bool = False
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"params": {"key": FIREBASE_API_KEY}}
        kwargs["data" if form else "json"] = payload
        try:
            async with self._session.post(url, timeout=CLOUD_TIMEOUT, **kwargs) as resp:
                body = await resp.json(content_type=None)
                if resp.status != 200:
                    message = (body or {}).get("error", {}).get("message", "")
                    if resp.status in (400, 401, 403):
                        raise UrbanhiveAuthError(message or "sign-in rejected")
                    raise UrbanhiveConnectionError(f"HTTP {resp.status}: {message}")
                return body
        except ClientError as err:
            raise UrbanhiveConnectionError(str(err)) from err


class UrbanhiveClient:
    """Reads and controls the homefarm - local first, cloud optional."""

    def __init__(
        self,
        session: ClientSession,
        auth: UrbanhiveAuth,
        host: str | None = None,
        prefer_cloud: bool = False,
    ) -> None:
        """Create with session, auth and the farm's local address (if known)."""
        self._session = session
        self._auth = auth
        self._host = host
        self._prefer_cloud = prefer_cloud
        # Set when the farm was found at a new address.
        self.host_changed = False

    @property
    def host(self) -> str | None:
        """Local address of the farm, if known."""
        return self._host

    def set_host(self, host: str | None) -> None:
        """Set the local address (for example after setup verified it)."""
        self._host = host

    @property
    def prefer_cloud(self) -> bool:
        """True if the user chose cloud access instead of the local API."""
        return self._prefer_cloud

    @property
    def _local(self) -> bool:
        return bool(self._host) and not self._prefer_cloud

    @staticmethod
    def _local_token(token: str) -> str:
        """Build the token the farm expects locally."""
        if len(token) <= LOCAL_TOKEN_MARKER_INDEX:
            return token
        i = LOCAL_TOKEN_MARKER_INDEX
        return token[:i] + LOCAL_TOKEN_MARKER + token[i:]

    # -- reading ----------------------------------------------------------------

    async def async_get_info(self, host: str) -> dict[str, Any]:
        """Read the farm's open /info endpoint (no sign-in) - also used for discovery."""
        url = f"http://{host}:{LOCAL_PORT}/info"
        try:
            async with self._session.get(url, timeout=LOCAL_TIMEOUT) as resp:
                if resp.status != 200:
                    raise UrbanhiveConnectionError(f"HTTP {resp.status}")
                return await resp.json(content_type=None)
        except (ClientError, TimeoutError) as err:
            raise UrbanhiveConnectionError(str(err)) from err

    async def async_get_farm(self, farm_id: str) -> dict[str, Any]:
        """Return the farm's live data.

        Locally if possible. If the farm does not answer, the cloud is only asked for
        the farm's current address (DHCP may have changed it); its other values can be
        months old and are not shown as live data. Without a local address, or when the
        user prefers the cloud, the cloud data is used as is.
        """
        if not self._local:
            return await self._async_cloud_farm(farm_id)
        try:
            return await self._async_local_get(f"/v2/farms?id={farm_id}")
        except UrbanhiveConnectionError as err:
            local_error = err
        farm = await self._async_cloud_farm(farm_id)
        new_host = farm.get("details", {}).get("localIP")
        if new_host and new_host != self._host:
            try:
                await self.async_get_info(new_host)
            except UrbanhiveError:
                pass
            else:
                _LOGGER.info("homefarm found at new address %s", new_host)
                self._host = new_host
                self.host_changed = True
                return await self._async_local_get(f"/v2/farms?id={farm_id}")
        raise UrbanhiveConnectionError(f"farm not reachable locally: {local_error}")

    async def _async_cloud_farm(self, farm_id: str) -> dict[str, Any]:
        farms = await self._async_cloud_get("/farms")
        farm = next((f for f in farms if f.get("id") == farm_id), None)
        if farm is None:
            raise UrbanhiveConnectionError("farm not found in this account")
        return farm

    async def async_get_cloud_farm(self, farm_id: str) -> dict[str, Any]:
        """Return the cloud copy of a farm (plant slots, tasks, flags)."""
        return await self._async_cloud_farm(farm_id)

    async def async_list_farms(self) -> list[dict[str, Any]]:
        """List all farms of the account (used during setup)."""
        return await self._async_cloud_get("/farms")

    async def async_get_plants(self) -> list[dict[str, Any]]:
        """Return the plant catalog."""
        return await self._async_cloud_get("/plants")

    # -- levels and settings (local first, mirrored to the cloud like the app) --------

    async def async_set_row_light(
        self, farm_id: str, row: dict[str, Any], on: bool
    ) -> None:
        """Switch the light of a level."""
        await self.async_set_row({**row, "lightOn": on})

    async def async_set_row(self, row: dict[str, Any]) -> None:
        """Write a level with changed fields (light, brightness, water check)."""
        payload = {k: row.get(k) for k in _ROW_KEYS}
        await self._async_write(
            f"/v2/rows?id={row['id']}", f"/rows?id={row['id']}", payload
        )

    async def async_update_details(
        self, farm_id: str, details: dict[str, Any]
    ) -> None:
        """Write farm settings (light times, mode, dimming, brightness)."""
        payload = {k: details.get(k) for k in _DETAILS_KEYS}
        await self._async_write(
            f"/v2/farms/details?id={farm_id}", f"/farms/details?id={farm_id}", payload
        )

    async def _async_write(
        self, local_path: str, cloud_path: str, payload: dict[str, Any]
    ) -> None:
        """Write to the farm and mirror to the cloud (as the app does)."""
        if self._local:
            try:
                await self._async_local_put(local_path, payload)
            except UrbanhiveConnectionError as err:
                _LOGGER.debug("Local write failed (%s), using the cloud", err)
            else:
                try:
                    await self._async_cloud_put(cloud_path, payload)
                except UrbanhiveError as err:
                    _LOGGER.debug("Cloud copy not updated: %s", err)
                return
        await self._async_cloud_put(cloud_path, payload)

    # -- plant slots, tasks and flags (cloud only) -------------------------------

    async def async_plant(
        self, slot: dict[str, Any], plant_id: str, planted_at: datetime
    ) -> None:
        """Put a plant into a slot."""
        payload = {
            **_slot_dto(slot),
            "plantId": plant_id,
            "plantedAt": iso_utc(planted_at),
            "harvestedAt": None,
        }
        await self._async_cloud_put(f"/plantSlots/{slot['id']}/plant", payload)

    async def async_harvest(
        self, slot: dict[str, Any], harvested_at: datetime | None = None
    ) -> None:
        """Harvest a plant, i.e. clear the slot.

        The backend needs a harvest time after the planting time; otherwise it answers
        HTTP 500.
        """
        when = harvested_at or datetime.now(UTC)
        payload = {**_slot_dto(slot), "harvestedAt": iso_utc(when)}
        await self._async_cloud_put(f"/plantSlots/{slot['id']}/harvest", payload)

    async def async_set_plant_date(
        self, slot: dict[str, Any], planted_at: datetime
    ) -> None:
        """Change the planting date of a slot."""
        payload = {**_slot_dto(slot), "plantedAt": iso_utc(planted_at)}
        await self._async_cloud_put(f"/plantSlots/{slot['id']}/date", payload)

    async def async_complete_task(self, task: dict[str, Any]) -> None:
        """Mark a task as done.

        Not verified against the backend yet (no task existed while building this);
        the payload follows what the app sends.
        """
        payload = {**_task_dto(task), "completedAt": iso_utc(datetime.now(UTC))}
        await self._async_cloud_put("/farm/tasks/complete", payload)

    async def async_ignore_task(self, task: dict[str, Any], until: str) -> None:
        """Hide a task until a point in time (not verified yet, see above)."""
        payload = {**_task_dto(task), "ignoreUntil": until}
        await self._async_cloud_put("/farm/tasks/ignore", payload)

    async def async_set_cleaned(self, farm_id: str, when: datetime) -> None:
        """Record a cleaning (like confirming "farm cleaned" in the app).

        The app sends the whole farm with the updated flag list.
        """
        farm = await self._async_cloud_farm(farm_id)
        flags = [f for f in farm.get("flags") or [] if f.get("key") != FLAG_CLEANING]
        flags.append({"key": FLAG_CLEANING, "value": iso_utc(when)})
        await self._async_cloud_put(
            f"/farms/flags?farmId={farm_id}", {**farm, "flags": flags}
        )

    # -- local calls --------------------------------------------------------------

    async def _async_local_headers(self) -> dict[str, str]:
        token = self._local_token(await self._auth.async_get_token())
        return {"Authorization": token, "User-Agent": "urbanhive-App"}

    async def _async_local_get(self, path: str) -> Any:
        return await self._async_local("get", path)

    async def _async_local_put(self, path: str, payload: dict[str, Any]) -> Any:
        return await self._async_local("put", path, payload)

    async def _async_local(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        url = f"http://{self._host}:{LOCAL_PORT}{path}"
        try:
            async with self._session.request(
                method,
                url,
                params=_APP_PARAMS,
                headers=await self._async_local_headers(),
                json=payload,
                timeout=LOCAL_TIMEOUT,
            ) as resp:
                return await _handle(resp)
        except (ClientError, TimeoutError) as err:
            raise UrbanhiveConnectionError(str(err)) from err

    # -- cloud calls --------------------------------------------------------------

    async def _async_cloud_get(self, path: str) -> Any:
        return await self._async_cloud("get", path)

    async def _async_cloud_put(self, path: str, payload: dict[str, Any]) -> Any:
        return await self._async_cloud("put", path, payload)

    async def _async_cloud(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        token = await self._auth.async_get_token()
        try:
            async with self._session.request(
                method,
                CLOUD_BASE + path,
                params=_APP_PARAMS,
                headers={"Authorization": token, "User-Agent": "urbanhive-App"},
                json=payload,
                timeout=CLOUD_TIMEOUT,
            ) as resp:
                return await _handle(resp)
        except (ClientError, TimeoutError) as err:
            raise UrbanhiveConnectionError(str(err)) from err


async def _handle(resp: Any) -> Any:
    if resp.status in (401, 403):
        raise UrbanhiveAuthError(f"HTTP {resp.status}")
    if resp.status >= 400:
        raise UrbanhiveConnectionError(f"HTTP {resp.status}")
    if resp.status == 204 or resp.content_length == 0:
        return None
    return await resp.json(content_type=None)

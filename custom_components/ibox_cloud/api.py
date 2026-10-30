"""Thin async client for the iBOX cloud API.

The endpoint map was recovered from the iBOX Assist app. Response field names
marked "TODO confirm" still need to be checked against live responses; the
coordinator tolerates missing keys so the integration loads either way.
"""
from __future__ import annotations

import logging
import struct
import time
from typing import Any

import aiohttp
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .const import (
    API_BASE,
    AUTH_SMS,
    CLOUD_BASE,
    DEFAULT_COUNTRY,
    TRIPS_BASE,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

# Cloud recordings are AES-GCM encrypted with the per-video "videoKey" and this fixed IV
# (IV_JUNAN in the app's BuildConfig).
CLOUD_VIDEO_IV = bytes.fromhex("2b7e151628aed2a6abf71588")


def decrypt_cloud_file(data: bytes, video_key: str) -> bytes:
    """Decrypt a cloud video or snapshot; videos lose the zero padding after their last box."""
    plain = AESGCM(bytes.fromhex(video_key)).decrypt(CLOUD_VIDEO_IV, data, None)
    if plain[4:8] != b"ftyp":
        return plain
    pos = 0
    while pos + 8 <= len(plain):
        size = struct.unpack_from(">I", plain, pos)[0]
        if size < 8 or pos + size > len(plain):
            break
        pos += size
    return plain[:pos] if pos else plain


class IboxError(Exception):
    """Generic API error."""


class IboxAuthError(IboxError):
    """Authentication failed or token rejected."""


class IboxApiClient:
    """Minimal client covering auth, device list, tracking and trips."""

    def __init__(self, session: aiohttp.ClientSession, token: str | None = None) -> None:
        self._session = session
        self._token = token

    @property
    def token(self) -> str | None:
        return self._token

    def _headers(self, auth: bool = True) -> dict[str, str]:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _request(
        self, method: str, base: str, path: str, *, auth: bool = True, **kwargs: Any
    ) -> Any:
        url = f"{base}{path}"
        try:
            async with self._session.request(
                method, url, headers=self._headers(auth), timeout=aiohttp.ClientTimeout(total=30), **kwargs
            ) as resp:
                text = await resp.text()
                if resp.status in (401, 403):
                    raise IboxAuthError(f"{resp.status} on {path}: {text[:200]}")
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise IboxError(f"request to {url} failed: {err}") from err
        if isinstance(data, dict) and data.get("success") is False:
            raise IboxError(data.get("message") or data.get("description") or str(data))
        return data

    # --- auth ---------------------------------------------------------------

    async def request_code(self, phone: str, is_sms: bool = True, country: str = DEFAULT_COUNTRY) -> Any:
        """POST /auth/login — sends an SMS code or triggers a verification call."""
        body = {"phone": phone, "country": country, "is_sms": 1 if is_sms else 0}
        return await self._request("POST", API_BASE, "/auth/login", auth=False, json=body)

    async def verify_code(self, phone: str, code: str, auth_type: int = AUTH_SMS) -> str:
        """POST /auth/check — returns and stores the session token."""
        body = {"phone": phone, "code": code, "type": auth_type}
        data = await self._request("POST", API_BASE, "/auth/check", auth=False, json=body)
        token = self._extract_token(data)
        if not token:
            raise IboxAuthError(f"no token in response: {str(data)[:200]}")
        self._token = token
        return token

    @staticmethod
    def _extract_token(data: Any) -> str | None:
        if not isinstance(data, dict):
            return None
        for container in (data.get("data"), data):
            if isinstance(container, dict):
                for key in ("token", "access_token", "accessToken"):
                    if container.get(key):
                        return container[key]
        return None

    async def check_token(self) -> bool:
        """POST /api/auth/check-token — validate the stored token."""
        try:
            await self._request("POST", API_BASE, "/api/auth/check-token")
            return True
        except IboxAuthError:
            return False

    # --- devices ------------------------------------------------------------

    async def get_devices(self) -> list[dict[str, Any]]:
        """Devices bound to the account (cloud devices)."""
        data = await self._request("GET", CLOUD_BASE, "/api/customer-devices/devices")
        return self._as_list(data)

    # --- device attributes (junan cloud) -------------------------------------

    async def read_attrs(self, did: str, attrs: list[str]) -> dict[str, str]:
        """Current attribute values as cached by the cloud: {attr: value}."""
        return {attr: value for attr, (value, _ts) in (await self.read_attrs_timed(did, attrs)).items()}

    async def read_attrs_timed(self, did: str, attrs: list[str]) -> dict[str, tuple[str, int]]:
        """{attr: (value, timestamp in ms of the dashcam's last report of it)}."""
        body = {"readAttrs": [{"deviceId": did, "attrs": attrs}]}
        data = await self._request("POST", CLOUD_BASE, "/api/junan/attr/read", json=body)
        message = ((data or {}).get("data") or {}).get("message") or {}
        items = (message.get("result") or {}).get(did) or []
        return {
            item["attr"]: (item.get("value"), int(item.get("timeStamp") or 0))
            for item in items
            if "attr" in item
        }

    async def write_attrs(self, did: str, values: dict[str, str]) -> None:
        # Key order matters: with "deviceId" before "data" the cloud answers ok but never
        # forwards the write to the dashcam (data.message stays null), as the app's body shows.
        body = {"writeAttrs": [{"data": values, "deviceId": did}]}
        data = await self._request("POST", CLOUD_BASE, "/api/junan/attr/write", json=body)
        message = ((data or {}).get("data") or {}).get("message")
        if not isinstance(message, dict) or not message.get("result"):
            raise IboxError(f"dashcam did not accept the setting: {str(data)[:200]}")

    async def junan_credentials(self) -> dict[str, str]:
        """Sub-user credentials for the Junan gateway: {"junan_id", "token"}."""
        data = await self._request("POST", CLOUD_BASE, "/api/junan/create_sub_user_token")
        creds = (data or {}).get("data") or {}
        if not creds.get("junan_id") or not creds.get("token"):
            raise IboxError(f"no junan credentials in response: {str(data)[:100]}")
        return creds

    async def settings_schema(self, cloud_type: str) -> dict[str, Any]:
        """Settings description used by the app (tabs + attributes with options)."""
        data = await self._request(
            "GET", CLOUD_BASE, "/api/device/settings-cloud", params={"type": cloud_type}
        )
        url = ((data or {}).get("data") or {}).get("file")
        if not url:
            return {}
        try:
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise IboxError(f"settings file download failed: {err}") from err

    # --- cloud recordings (uploaded by the dashcam after a shock) -------------

    async def cloud_videos(
        self,
        did: str,
        channel: int,
        video_type: int = 0,
        start_ms: int = 0,
        end_ms: int | None = None,
        size: int = 50,
    ) -> list[dict[str, Any]]:
        """Cloud recordings of one camera, newest first, start <= trigger time < end.

        video_type: 0 all, 1 parking motion, 2 parking shock, 3 driving shock, 4 manual lock
        (EEventS3Videos in the app). The storage links inside are valid for an hour.
        """
        body = {
            "deviceId": did,
            "endTime": end_ms if end_ms is not None else int(time.time() * 1000) + 86_400_000,
            "startTime": start_ms,
            "videoType": video_type,
            "channel": channel,
            "size": size,
        }
        data = await self._request("POST", CLOUD_BASE, "/api/junan/device/video/list", json=body)
        answers = [item for item in (data or {}).get("data") or [] if isinstance(item, dict)]
        if not answers:
            return []
        if answers[0].get("code") not in (0, None):
            raise IboxError(f"cloud video list: {answers[0].get('message')}")
        return answers[0].get("result") or []

    async def delete_cloud_videos(self, did: str, video_type: int, trigger_times: list[int]) -> None:
        """Delete cloud recordings of one type, addressed by trigger time (ms).

        The cloud answers "Success" even for unknown times, so callers re-list to confirm.
        """
        body = {"deviceId": did, "type": video_type, "triggerTimeList": trigger_times}
        data = await self._request("POST", CLOUD_BASE, "/api/junan/device/video/delete", json=body)
        message = ((data or {}).get("data") or {}).get("message")
        if isinstance(message, dict) and message.get("code") not in (0, None):
            raise IboxError(f"cloud video delete: {message.get('message')}")

    async def download(self, url: str) -> bytes:
        """Fetch a pre-signed storage link (no API headers)."""
        try:
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    raise IboxError(f"download failed: HTTP {resp.status}")
                return await resp.read()
        except aiohttp.ClientError as err:
            raise IboxError(f"download failed: {err}") from err

    # --- tracking / trips ---------------------------------------------------

    # Tracking calls take the cloud "did" (e.g. d.ib.0.<serial>) and the cloud
    # type ("junan", "istar", "wanma"); the payload is in "data", null when empty.

    async def _tracking(self, path: str, did: str, cloud_type: str, **params: Any) -> Any:
        query = {"device_identifier": did, "type": cloud_type, **params}
        data = await self._request("GET", TRIPS_BASE, path, params=query)
        return data.get("data") if isinstance(data, dict) else data

    async def last_position(self, did: str, cloud_type: str) -> Any:
        return await self._tracking("/api/v1/tracking/trips/last-position", did, cloud_type)

    async def last_online(self, did: str, cloud_type: str) -> Any:
        """Unix timestamp (seconds) of the last connection, or None."""
        return await self._tracking("/api/v1/tracking/trips/last-online", did, cloud_type)

    async def trips(self, did: str, cloud_type: str, limit: int = 20, offset: int = 0) -> Any:
        return await self._tracking(
            "/api/v1/tracking/trips/list", did, cloud_type, limit=limit, offset=offset
        )

    @staticmethod
    def _as_list(data: Any) -> list[dict[str, Any]]:
        if isinstance(data, dict):
            inner = data.get("data", data)
            if isinstance(inner, list):
                return inner
            if isinstance(inner, dict):
                for value in inner.values():
                    if isinstance(value, list):
                        return value
                return [inner]
        if isinstance(data, list):
            return data
        return []

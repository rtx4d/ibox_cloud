"""Junan (app.iot.yigtech.com) gateway used by the dashcam SDK: MQTT push + file lists.

The gateway answers file-list and thumbnail requests with a task id only; the
dashcam sends the actual result through MQTT, together with live attribute reports.
"""
from __future__ import annotations

import json
import logging
import random
from collections.abc import Callable
from typing import Any

import aiohttp
import paho.mqtt.client as mqtt

from .api import IboxError

_LOGGER = logging.getLogger(__name__)

JUNAN_BASE = "https://app.iot.yigtech.com"
TOPICS = ("/v1.0/down/attr/", "/v1.0/down/event/")

URL_ATTR_REPORT = "/v1.0/device/attr/report"
URL_RADAR_INFO = "/v1.0/device/upload/radar/info"
URL_FILE_LIST = "/v1.0/device/video/file/list/get"
URL_THUMBNAIL = "/v1.0/device/video/thumbnail/get"

# ETypeVideoP2PPlayer / EChannelP2PPlayer in the app
FILE_NORMAL, FILE_EVENT, FILE_PARKING = 1, 2, 3
CHANNEL_FRONT, CHANNEL_REAR = 1, 2


class JunanClient:
    """HTTP side of the gateway, authenticated with the sub-user credentials."""

    def __init__(self, session: aiohttp.ClientSession, user_id: str, token: str) -> None:
        self._session = session
        self._headers = {"userId": user_id, "token": token, "lang": "en"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            async with self._session.request(
                method,
                JUNAN_BASE + path,
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=30),
                **kwargs,
            ) as resp:
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, ValueError, RuntimeError) as err:  # RuntimeError: session closed
            raise IboxError(f"junan {path} failed: {err}") from err
        if not isinstance(data, dict) or data.get("code") != 0:
            raise IboxError(f"junan {path}: {str(data)[:200]}")
        return data.get("result")

    async def mqtt_info(self) -> dict[str, Any]:
        """Broker address and the MQTT account for this user."""
        return await self._request("POST", "/v1.0/iot/user/mqtt/info", data="")

    async def p2p_info(self, did: str) -> dict[str, Any]:
        """{"p2pId", "initStringApp", "devP2pPublicKey"} for the CS2 session."""
        return await self._request("GET", "/v1.0/iot/p2p/info", params={"did": did})

    async def p2p_sign(self, did: str, app_public_key: str) -> dict[str, Any]:
        """Server signature of our ephemeral key: {"sign", "time", "p2pDevPublicKey"}."""
        body = {"did": did, "devPwd": "", "p2pAppPublicKey": app_public_key}
        return await self._request("POST", "/v1.0/iot/p2p/sign", json=body)

    async def request_file_list(
        self, did: str, file_type: int, channel: int, limit: int = 10, offset: int = 0, sort: int = 0
    ) -> str:
        """Ask the dashcam for a file list; returns the task id its MQTT reply carries.

        sort: 0 newest first, 1 oldest first.
        """
        params = {
            "deviceId": did,
            "type": file_type,
            "channel": channel,
            "limit": limit,
            "sort": sort,
            "offset": offset,
        }
        return await self._request("GET", "/v1.0/iot/device/get/file/push/list", params=params)

    async def request_thumbnails(self, did: str, files: list[dict[str, Any]]) -> None:
        body = {
            "list": [
                {
                    "deviceId": did,
                    "fileId": f["fileName"],
                    "fileName": f["fileName"],
                    "pathName": f.get("pathName", ""),
                }
                for f in files
            ]
        }
        await self._request("POST", "/v1.0/iot/device/get/file/pic/batch", json=body)


class JunanMqtt:
    """Paho client running in its own thread; messages are handed to `on_message`."""

    def __init__(self, info: dict[str, Any], on_message: Callable[[str, dict[str, Any]], None]) -> None:
        self._account = info["account"]
        self._host = info["brokerIp"]
        self._port = int(info.get("port") or 1883)
        self._on_message = on_message
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"aos-{random.randint(1, 2**31)}",
        )
        self._client.username_pw_set(self._account, info["password"])
        self._client.on_connect = self._handle_connect
        self._client.on_message = self._handle_message
        self._client.reconnect_delay_set(5, 300)

    def start(self) -> None:
        """Blocking connect + background loop; run in an executor."""
        self._client.connect_async(self._host, self._port, keepalive=60)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()

    def _handle_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        if reason_code.is_failure:
            _LOGGER.warning("iBOX MQTT connection refused: %s", reason_code)
            return
        for topic in TOPICS:
            client.subscribe(topic + self._account, 0)

    def _handle_message(self, client, userdata, msg) -> None:
        try:
            message = json.loads(msg.payload)
        except ValueError:
            return
        if isinstance(message, dict):
            self._on_message(msg.topic, message)

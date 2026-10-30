"""WebSocket commands used by the iBOX sidebar panel."""
from __future__ import annotations

import base64
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .live import WS_PREFIX


def _hubs(hass: HomeAssistant) -> dict[str, tuple[Any, Any]]:
    return hass.data.get(DOMAIN, {}).get("hubs", {})


def _hub(hass: HomeAssistant, dev_id: str) -> tuple[Any, Any]:
    hub = _hubs(hass).get(dev_id)
    if hub is None:
        raise HomeAssistantError(f"unknown iBOX device {dev_id}")
    return hub


def _entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)


def _device_state(hass: HomeAssistant, dev_id: str) -> dict[str, Any]:
    coordinator, stream = _hub(hass, dev_id)
    device = (coordinator.data or {}).get("devices", {}).get(dev_id, {})
    info = device.get("info") or {}
    cloud = info.get("cloudInfoDevice") or {}
    fw = (info.get("fwVersion") or "").split(",")
    return {
        "device_id": dev_id,
        "name": info.get("customName") or info.get("name") or dev_id,
        "model": info.get("name"),
        "serial": (cloud.get("sn") or "").removeprefix("ibox."),
        "firmware": fw[1] if len(fw) > 1 else None,
        "attrs": device.get("attrs") or {},
        "position": device.get("position"),
        "last_seen": device.get("last_seen"),
        "push": coordinator.junan is not None,
        "live": {
            "quality": stream.quality,
            "camera": stream.camera,
            "ws_path": f"{WS_PREFIX}/{dev_id}",
            "camera_entity": _entity_id(hass, "camera", f"{dev_id}_live"),
        },
        "latest": {
            str(t): coordinator.files(dev_id, t)[:1] for t in (1, 2, 3)
        },
        "events": list(coordinator.events)[:50],
    }


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/devices"})
@callback
def ws_devices(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Devices with their state and the settings description (sent once, it is large)."""
    devices = []
    for dev_id, (coordinator, _stream) in _hubs(hass).items():
        state = _device_state(hass, dev_id)
        cloud_type = ((coordinator.data or {}).get("devices", {}).get(dev_id, {})).get("cloud_type", "")
        state["schema"] = coordinator.schemas.get(cloud_type) or {}
        devices.append(state)
    connection.send_result(msg["id"], {"devices": devices})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe", vol.Required("device_id"): str})
@callback
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Device state now and after every coordinator update (polls and MQTT pushes)."""
    coordinator, _stream = _hub(hass, msg["device_id"])

    @callback
    def _send() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], _device_state(hass, msg["device_id"])))

    connection.subscriptions[msg["id"]] = coordinator.async_add_listener(_send)
    connection.send_result(msg["id"])
    _send()


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/set_attr",
        vol.Required("device_id"): str,
        vol.Required("attr"): str,
        vol.Required("value"): vol.Coerce(str),
    }
)
@websocket_api.async_response
async def ws_set_attr(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    coordinator, _stream = _hub(hass, msg["device_id"])
    await coordinator.async_write_attr(msg["device_id"], msg["attr"], msg["value"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/files",
        vol.Required("device_id"): str,
        vol.Required("file_type"): vol.In([1, 2, 3, 4]),
        vol.Optional("channel", default=1): vol.In([1, 2]),
        vol.Optional("offset", default=0): vol.All(int, vol.Range(min=0)),
        vol.Optional("limit", default=20): vol.All(int, vol.Range(min=1, max=50)),
        vol.Optional("sort", default=0): vol.In([0, 1]),
    }
)
@websocket_api.async_response
async def ws_files(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    coordinator, _stream = _hub(hass, msg["device_id"])
    files = await coordinator.async_list_files(
        msg["device_id"], msg["file_type"], msg["channel"], msg["offset"], msg["limit"], msg["sort"]
    )
    connection.send_result(msg["id"], {"files": files})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/thumbnails",
        vol.Required("device_id"): str,
        vol.Required("files"): [{vol.Required("fileName"): str, vol.Optional("pathName", default=""): str}],
    }
)
@websocket_api.async_response
async def ws_thumbnails(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    coordinator, _stream = _hub(hass, msg["device_id"])
    images = await coordinator.async_thumbnails(msg["device_id"], msg["files"][:20])
    connection.send_result(msg["id"], {"images": {k: base64.b64encode(v).decode() for k, v in images.items()}})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/cloud_videos",
        vol.Required("device_id"): str,
        vol.Optional("channel", default=1): vol.In([1, 2]),
        # 0 all, 1 parking motion, 2 parking shock, 3 driving shock, 4 manual lock
        vol.Optional("video_type", default=0): vol.In([0, 1, 2, 3, 4]),
        vol.Optional("start", default=0): vol.Coerce(float),
        vol.Optional("end"): vol.Coerce(float),
        vol.Optional("limit", default=30): vol.All(int, vol.Range(min=1, max=100)),
    }
)
@websocket_api.async_response
async def ws_cloud_videos(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """One page of the recordings the dashcam uploaded to the cloud; page on with end = last trigger_time."""
    coordinator, _stream = _hub(hass, msg["device_id"])
    videos = await coordinator.async_cloud_videos(
        msg["device_id"], msg["channel"], msg["video_type"], msg["start"], msg.get("end"), msg["limit"]
    )
    connection.send_result(msg["id"], {"videos": videos})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/cloud_delete",
        vol.Required("device_id"): str,
        vol.Required("ids"): vol.All([int], vol.Length(min=1, max=100)),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_cloud_delete(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    coordinator, _stream = _hub(hass, msg["device_id"])
    deleted = await coordinator.async_delete_cloud_videos(msg["device_id"], msg["ids"])
    connection.send_result(msg["id"], {"deleted": deleted})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/live_options",
        vol.Required("device_id"): str,
        vol.Optional("quality"): vol.In([1, 2]),
        vol.Optional("camera"): vol.In([1, 2]),
    }
)
@callback
def ws_live_options(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Change live quality (on the fly) or camera (restarts the stream)."""
    _coordinator, stream = _hub(hass, msg["device_id"])
    if "quality" in msg:
        stream.set_quality(msg["quality"])
    if "camera" in msg and msg["camera"] != stream.camera:
        stream.camera = msg["camera"]
        stream.restart()
    _coordinator.async_update_listeners()  # refresh the quality/camera select entities
    connection.send_result(msg["id"], {"quality": stream.quality, "camera": stream.camera})


@callback
def async_register(hass: HomeAssistant) -> None:
    for command in (ws_devices, ws_subscribe, ws_set_attr, ws_files, ws_thumbnails, ws_cloud_videos, ws_cloud_delete, ws_live_options):
        websocket_api.async_register_command(hass, command)

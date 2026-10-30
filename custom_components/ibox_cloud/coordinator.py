"""Data update coordinator for iBOX Cloud."""
from __future__ import annotations

import asyncio
import base64
from functools import partial
import logging
import time
from collections import OrderedDict, deque
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IboxApiClient, IboxAuthError, IboxError
from .const import DOMAIN, EVENT_FILE_INTERVAL, FILE_REFRESH_INTERVAL, STATUS_ATTRS, UPDATE_INTERVAL
from .junan import (
    CHANNEL_FRONT,
    CHANNEL_REAR,
    FILE_EVENT,
    FILE_NORMAL,
    FILE_PARKING,
    URL_ATTR_REPORT,
    URL_FILE_LIST,
    URL_RADAR_INFO,
    URL_THUMBNAIL,
    JunanClient,
    JunanMqtt,
)

EVENT_IBOX = f"{DOMAIN}_event"

_LOGGER = logging.getLogger(__name__)


class IboxCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the account's devices, their attributes, positions and trips."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: IboxApiClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="iBOX Cloud",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.entry = entry
        self.client = client
        # cloud type -> settings description ({"tabs_settings", "attributes_settings"})
        self.schemas: dict[str, dict[str, Any]] = {}
        # Pushed over MQTT, kept apart from the polled data:
        # did -> {"files": {(type, channel): [file, …]}, "thumbs": {file name: jpeg bytes}}
        self.media: dict[str, dict[str, Any]] = {}
        self.junan: JunanClient | None = None
        self.live: dict[str, Any] = {}  # did -> live.LiveStream
        self._mqtt: JunanMqtt | None = None
        self._unsub_files: Any = None
        # panel requests answered through MQTT
        self._list_waiters: dict[str, asyncio.Future] = {}
        self._thumb_waiters: dict[tuple[str, str], list[asyncio.Future]] = {}
        self.thumb_cache: OrderedDict[tuple[str, str], bytes] = OrderedDict()
        self.events: deque[dict[str, Any]] = deque(maxlen=200)
        # did -> callbacks of the event entities: callback(event_type, attributes)
        self.event_callbacks: dict[str, set] = {}
        self._unsub_event_files: Any = None

    def settings(self, cloud_type: str) -> list[dict[str, Any]]:
        """Flat list of setting descriptions for a cloud type."""
        groups = (self.schemas.get(cloud_type) or {}).get("attributes_settings") or {}
        return [item for items in groups.values() for item in items]

    async def _schema(self, cloud_type: str) -> None:
        if cloud_type in self.schemas:
            return
        try:
            self.schemas[cloud_type] = await self.client.settings_schema(cloud_type)
        except IboxError as err:
            _LOGGER.warning("settings description for %s unavailable: %s", cloud_type, err)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            devices = await self.client.get_devices()
        except IboxAuthError as err:
            raise UpdateFailed(f"auth rejected: {err}") from err
        except IboxError as err:
            raise UpdateFailed(str(err)) from err

        result: dict[str, Any] = {"devices": {}}
        for dev in devices:
            info = dev.get("data") or {}
            cloud = info.get("cloudInfoDevice") or {}
            dev_id = str(cloud.get("did") or dev.get("device_id") or "")
            if not dev_id:
                continue
            cloud_type = dev.get("type") or "junan"
            await self._schema(cloud_type)
            entry: dict[str, Any] = {"info": info, "cloud_type": cloud_type}

            setting_ids = [
                item["id"] for item in self.settings(cloud_type) if item.get("type") != "function"
            ]
            try:
                timed = await self.client.read_attrs_timed(dev_id, STATUS_ATTRS + setting_ids)
            except IboxError as err:
                _LOGGER.debug("attributes for %s failed: %s", dev_id, err)
                timed = {}
            entry["attrs"] = {attr: value for attr, (value, _ts) in timed.items()}
            entry["last_seen"] = self._last_seen(dev_id, timed)

            try:
                entry["position"] = await self.client.last_position(dev_id, cloud_type)
            except IboxError as err:
                _LOGGER.debug("position for %s failed: %s", dev_id, err)
                entry["position"] = None
            result["devices"][dev_id] = entry
        return result

    async def async_write_attr(self, dev_id: str, attr: str, value: str) -> None:
        """Write one setting and reflect it locally until the next poll."""
        try:
            await self.client.write_attrs(dev_id, {attr: value})
        except IboxError as err:
            raise HomeAssistantError(f"iBOX: failed to set {attr}: {err}") from err
        device = (self.data or {}).get("devices", {}).get(dev_id)
        if device is not None:
            device.setdefault("attrs", {})[attr] = value
            self.async_set_updated_data(self.data)

    # --- push channel (Junan gateway + MQTT) --------------------------------

    async def async_start_push(self) -> None:
        """Connect to the dashcam's MQTT channel; the integration still works by polling without it."""
        try:
            creds = await self.client.junan_credentials()
            self.junan = JunanClient(
                async_get_clientsession(self.hass), creds["junan_id"], creds["token"]
            )
            info = await self.junan.mqtt_info()
        except IboxError as err:
            _LOGGER.warning("iBOX push channel unavailable, polling only: %s", err)
            self.junan = None
            return
        self._mqtt = JunanMqtt(info, self._on_mqtt_message)
        await self.hass.async_add_executor_job(self._mqtt.start)
        self._unsub_files = async_track_time_interval(
            self.hass, self._async_refresh_files, timedelta(seconds=FILE_REFRESH_INTERVAL)
        )
        # driving shocks only show up as new protected files, so look for those more often
        self._unsub_event_files = async_track_time_interval(
            self.hass, partial(self._async_refresh_files, (FILE_EVENT,)), timedelta(seconds=EVENT_FILE_INTERVAL)
        )
        # give the broker a moment to accept our subscriptions before asking for files
        async_call_later(self.hass, 5, self._async_refresh_files)

    async def async_stop_push(self) -> None:
        self.junan = None  # late MQTT messages are ignored from here on
        for unsub in (self._unsub_files, self._unsub_event_files):
            if unsub:
                unsub()
        self._unsub_files = self._unsub_event_files = None
        if self._mqtt:
            await self.hass.async_add_executor_job(self._mqtt.stop)
            self._mqtt = None

    def files(self, dev_id: str, file_type: int, channel: int = CHANNEL_FRONT) -> list[dict[str, Any]]:
        return self.media.get(dev_id, {}).get("files", {}).get((file_type, channel), [])

    def thumbnail(self, dev_id: str, file_name: str) -> bytes | None:
        return self.media.get(dev_id, {}).get("thumbs", {}).get(file_name)

    async def _async_refresh_files(
        self, file_types: tuple[int, ...] = (FILE_NORMAL, FILE_EVENT, FILE_PARKING), _now: Any = None
    ) -> None:
        if not self.junan or not self.data:
            return
        if not isinstance(file_types, tuple):  # called by a timer with only the time argument
            file_types = (FILE_NORMAL, FILE_EVENT, FILE_PARKING)
        for dev_id in self.data.get("devices", {}):
            for file_type in file_types:
                for channel in (CHANNEL_FRONT, CHANNEL_REAR):
                    try:
                        await self.junan.request_file_list(dev_id, file_type, channel)
                    except IboxError as err:
                        _LOGGER.debug("file list request for %s failed: %s", dev_id, err)
                        return

    def _on_mqtt_message(self, topic: str, message: dict[str, Any]) -> None:
        """Called from the paho thread."""
        self.hass.loop.call_soon_threadsafe(self._handle_push, message)

    @callback
    def _handle_push(self, message: dict[str, Any]) -> None:
        if not self.junan:
            return
        url = message.get("url")
        outer = message.get("payload") or {}
        payload = outer.get("payload") if isinstance(outer.get("payload"), dict) else outer
        dev_id = payload.get("deviceId") or outer.get("deviceId") or outer.get("gatewayId")
        devices = (self.data or {}).get("devices", {})
        if dev_id not in devices:
            return
        media = self.media.setdefault(dev_id, {"files": {}, "thumbs": {}})

        if url in (URL_ATTR_REPORT, URL_RADAR_INFO):
            data = payload.get("data") or {}
            attrs = devices[dev_id].setdefault("attrs", {})
            was_recording = attrs.get("record_status") == "1"
            attrs.update({k: str(v) for k, v in data.items()})
            # With the ignition off the dashcam only records when parking mode is triggered
            # (shock or motion): that is the instant signal, the file shows up a few seconds later.
            if str(data.get("record_status")) == "1" and not was_recording and attrs.get("acc_status") == "0":
                self._dashcam_event(dev_id, "parking_activity", {})
                async_call_later(self.hass, 25, partial(self._async_refresh_files, (FILE_PARKING, FILE_EVENT)))
            if payload.get("time"):
                devices[dev_id]["last_seen"] = max(devices[dev_id].get("last_seen") or 0, payload["time"] / 1000)
            if url == URL_RADAR_INFO and str(data.get("radar_type", "0")) != "0":
                self._add_event(dev_id, url, data)
        elif url == URL_FILE_LIST:
            files = payload.get("fileList") or []
            waiter = self._list_waiters.pop(payload.get("requestId") or outer.get("requestId"), None)
            if waiter is not None:
                if not waiter.done():
                    waiter.set_result(files)
                return  # panel paging must not replace the "latest" lists below
            key = (payload.get("type"), payload.get("channel"))
            previous = media["files"].get(key)
            media["files"][key] = files
            kind = {FILE_EVENT: "event_recording", FILE_PARKING: "parking_recording"}.get(key[0])
            if kind and previous is not None:  # the first listing only sets the baseline
                known = {f.get("fileName") for f in previous}
                for file in reversed([f for f in files if f.get("fileName") not in known]):
                    self._dashcam_event(dev_id, kind, {
                        "file_name": file.get("fileName"),
                        "path": file.get("pathName"),
                        "camera": "rear" if key[1] == CHANNEL_REAR else "front",
                        "duration_s": round((file.get("duration") or 0) / 1000),
                    })
            previous = previous or []
            if files and (not previous or previous[0].get("fileName") != files[0].get("fileName")):
                self.entry.async_create_background_task(
                    self.hass, self._async_request_thumbnail(dev_id, files[0]), "ibox thumbnail"
                )
        elif url == URL_THUMBNAIL:
            name, data = payload.get("fileId"), payload.get("byteStr")
            if name and data:
                image = base64.b64decode(data)
                self.thumb_cache[(dev_id, name)] = image
                while len(self.thumb_cache) > 400:
                    self.thumb_cache.popitem(last=False)
                for waiter in self._thumb_waiters.pop((dev_id, name), []):
                    if not waiter.done():
                        waiter.set_result(image)
                wanted = {f[0]["fileName"] for f in media["files"].values() if f}
                media["thumbs"] = {k: v for k, v in media["thumbs"].items() if k in wanted}
                media["thumbs"][name] = base64.b64decode(data)
        else:
            self._add_event(dev_id, url, payload)
            self.hass.bus.async_fire(
                EVENT_IBOX, {"device_id": dev_id, "type": url, "data": payload}
            )
        self.async_update_listeners()

    async def _async_request_thumbnail(self, dev_id: str, file: dict[str, Any]) -> None:
        if not self.junan:
            return
        try:
            await self.junan.request_thumbnails(dev_id, [file])
        except IboxError as err:
            _LOGGER.debug("thumbnail request for %s failed: %s", file.get("fileName"), err)

    @callback
    def _dashcam_event(self, dev_id: str, event_type: str, attributes: dict[str, Any]) -> None:
        """Parking trigger / new protected or parking recording: event entity, bus event, panel feed."""
        self._add_event(dev_id, event_type, attributes)
        self.hass.bus.async_fire(EVENT_IBOX, {"device_id": dev_id, "type": event_type, "data": attributes})
        for notify in list(self.event_callbacks.get(dev_id, ())):
            notify(event_type, attributes)

    @callback
    def _add_event(self, dev_id: str, url: str | None, data: dict[str, Any]) -> None:
        self.events.appendleft({"time": time.time(), "device_id": dev_id, "type": url, "data": data})

    async def async_list_files(
        self, dev_id: str, file_type: int, channel: int, offset: int = 0, limit: int = 20, sort: int = 0
    ) -> list[dict[str, Any]]:
        """One page of the memory card listing, as answered by the dashcam over MQTT."""
        if not self.junan:
            raise HomeAssistantError("iBOX push channel is not connected")
        future = self.hass.loop.create_future()
        try:
            task = await self.junan.request_file_list(dev_id, file_type, channel, limit, offset, sort)
        except IboxError as err:
            raise HomeAssistantError(f"iBOX: file list request failed: {err}") from err
        self._list_waiters[task] = future
        try:
            return await asyncio.wait_for(future, 20)
        except TimeoutError as err:
            raise HomeAssistantError("iBOX: the dashcam did not answer (offline?)") from err
        finally:
            self._list_waiters.pop(task, None)

    async def async_thumbnails(self, dev_id: str, files: list[dict[str, Any]]) -> dict[str, bytes]:
        """Thumbnails by file name; cached ones are returned without asking the dashcam."""
        result = {f["fileName"]: self.thumb_cache[(dev_id, f["fileName"])] for f in files if (dev_id, f["fileName"]) in self.thumb_cache}
        missing = [f for f in files if f["fileName"] not in result]
        if not missing or not self.junan:
            return result
        waiters = {}
        for f in missing:
            future = self.hass.loop.create_future()
            self._thumb_waiters.setdefault((dev_id, f["fileName"]), []).append(future)
            waiters[f["fileName"]] = future
        try:
            await self.junan.request_thumbnails(dev_id, missing)
        except IboxError as err:
            _LOGGER.debug("thumbnail request failed: %s", err)
        await asyncio.wait(waiters.values(), timeout=15)
        for name, future in waiters.items():
            if future.done() and not future.cancelled():
                result[name] = future.result()
            else:
                future.cancel()
        return result

    def _last_seen(self, dev_id: str, timed: dict[str, tuple[str, int]]) -> float | None:
        """Last time the dashcam was heard from, in seconds.

        trips/last-online stays empty for junan dashcams, so use the attribute reports instead:
        while online it is the poll time; offline, the newest report the dashcam sent.
        connection_status is left out: the cloud refreshes its timestamp on every read.
        """
        if timed.get("connection_status", ("",))[0] == "1":
            return time.time()
        reports = [ts for attr, (_v, ts) in timed.items() if attr != "connection_status" and ts]
        previous = ((self.data or {}).get("devices", {}).get(dev_id) or {}).get("last_seen") or 0
        newest = max(reports) / 1000 if reports else 0
        return max(newest, previous) or None

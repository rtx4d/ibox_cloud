"""Live view and SD-card playback over P2P: MPEG-TS for HA's stream worker, WebSocket for the panel player."""
from __future__ import annotations

import asyncio
import json
import logging
import queue
import secrets
import struct
import threading
from collections.abc import Callable
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from nacl import bindings as nacl

from .api import IboxError
from .ppcs import CODEC_AAC, CODEC_H264, CODEC_H265, PpcsError, run_session

_LOGGER = logging.getLogger(__name__)

URL_PREFIX = "/api/ibox_cloud/live"
WS_PREFIX = "/api/ibox_cloud/ws"
IDLE_TIMEOUT = 15  # seconds without viewers before the P2P session is closed

PID_PMT, PID_VIDEO, PID_AUDIO = 0x1000, 0x100, 0x101


def _crc32(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for b in data:
        crc ^= b << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) if crc & 0x80000000 else crc << 1
            crc &= 0xFFFFFFFF
    return crc


def _pts_bytes(marker: int, pts: int) -> bytes:
    return bytes([
        (marker << 4) | (((pts >> 30) & 0x07) << 1) | 1,
        (pts >> 22) & 0xFF,
        (((pts >> 15) & 0x7F) << 1) | 1,
        (pts >> 7) & 0xFF,
        ((pts & 0x7F) << 1) | 1,
    ])


class TsMuxer:
    """Tiny MPEG-TS muxer for one HEVC/H.264 stream plus ADTS AAC."""

    def __init__(self, video_codec: int) -> None:
        self._video_type = 0x24 if video_codec == CODEC_H265 else 0x1B
        self._cc: dict[int, int] = {}

    def _packets(self, pid: int, payload: bytes, pcr: int | None = None) -> bytes:
        out = bytearray()
        first = True
        pos = 0
        while pos < len(payload):
            cc = self._cc.get(pid, 0)
            self._cc[pid] = (cc + 1) & 0x0F
            header = bytearray([0x47, (0x40 if first else 0) | (pid >> 8), pid & 0xFF, 0])
            adaptation = b""
            if first and pcr is not None:
                base = pcr & ((1 << 33) - 1)
                adaptation = bytes([0x10]) + struct.pack(">IH", base >> 1, ((base & 1) << 15) | 0x7E00)
            room = 184 - (len(adaptation) + 1 if adaptation else 0)
            chunk = payload[pos:pos + room]
            if len(chunk) < room:  # pad with adaptation-field stuffing
                fill = room - len(chunk)
                if adaptation:
                    adaptation += b"\xff" * fill
                elif fill == 1:
                    adaptation, room = None, 183
                else:
                    adaptation = bytes([0x00]) + b"\xff" * (fill - 2)
            if adaptation is None:  # single stuffing byte: zero-length adaptation field
                header[3] = 0x30 | cc
                out += header + b"\x00" + chunk
            elif adaptation:
                header[3] = 0x30 | cc
                out += header + bytes([len(adaptation)]) + adaptation + chunk
            else:
                header[3] = 0x10 | cc
                out += header + chunk
            pos += len(chunk)
            first = False
        return bytes(out)

    def _section(self, pid: int, table: bytes) -> bytes:
        body = table + struct.pack(">I", _crc32(table))
        return self._packets(pid, b"\x00" + body)

    def tables(self) -> bytes:
        pat = bytes([0x00, 0xB0, 0x0D, 0x00, 0x01, 0xC1, 0x00, 0x00, 0x00, 0x01]) + struct.pack(">H", 0xE000 | PID_PMT)
        streams = (
            bytes([self._video_type]) + struct.pack(">HH", 0xE000 | PID_VIDEO, 0xF000)
            + bytes([0x0F]) + struct.pack(">HH", 0xE000 | PID_AUDIO, 0xF000)
        )
        length = 9 + len(streams) + 4
        pmt = (
            bytes([0x02]) + struct.pack(">H", 0xB000 | length) + bytes([0x00, 0x01, 0xC1, 0x00, 0x00])
            + struct.pack(">HH", 0xE000 | PID_VIDEO, 0xF000) + streams
        )
        return self._section(0, pat) + self._section(PID_PMT, pmt)

    def video(self, pts: int, data: bytes, keyframe: bool) -> bytes:
        pes = b"\x00\x00\x01\xe0\x00\x00\x80\x80\x05" + _pts_bytes(2, pts) + data
        return (self.tables() if keyframe else b"") + self._packets(PID_VIDEO, pes, pcr=pts)

    def audio(self, pts: int, data: bytes) -> bytes:
        size = len(data) + 8
        pes = b"\x00\x00\x01\xc0" + struct.pack(">H", size) + b"\x80\x80\x05" + _pts_bytes(2, pts) + data
        return self._packets(PID_AUDIO, pes)


Frame = tuple[int, bool, int, bytes]  # codec, keyframe, pts in ms, payload
VIDEO_CODECS = (CODEC_H264, CODEC_H265)


async def prepare_session(coordinator: Any, dev_id: str) -> tuple[dict, dict, bytes]:
    """CS2 parameters plus a server-signed ephemeral key for one P2P session."""
    junan = coordinator.junan
    if not junan:
        raise IboxError("Junan gateway not available")
    info = await junan.p2p_info(dev_id)
    app_pk, app_sk = nacl.crypto_box_keypair()
    sign = await junan.p2p_sign(dev_id, app_pk.hex())
    share = nacl.crypto_box_beforenm(bytes.fromhex(sign["p2pDevPublicKey"]), app_sk)
    auth = {"app_public_key": app_pk.hex(), "timestamp": str(sign["time"]), "app_sign": sign["sign"]}
    return info, auth, share


class LiveStream:
    """One dashcam's live stream, shared by all viewers; runs only while somebody watches."""

    def __init__(self, hass: HomeAssistant, coordinator: Any, dev_id: str) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.dev_id = dev_id
        self.token = secrets.token_hex(16)
        self.quality = 1  # 1280x720
        self.camera = 1  # front
        self._viewers: set[Callable[[Frame | None], None]] = set()
        self._gop: list[Frame] = []  # frames since the last keyframe, for instant start
        self._stop: threading.Event | None = None
        self._controls: queue.Queue | None = None
        self._task: asyncio.Task | None = None
        self._idle_handle: asyncio.TimerHandle | None = None

    def url(self) -> str | None:
        # The stream worker runs inside HA, so loopback always works (and avoids TLS name checks)
        api = self.hass.config.api
        if api is None:
            return None
        scheme = "https" if api.use_ssl else "http"
        return f"{scheme}://127.0.0.1:{api.port}{URL_PREFIX}/{self.token}.ts"

    def restart(self) -> None:
        """Apply a new camera: viewers reconnect to a fresh session."""
        if self._stop:
            self._stop.set()

    def set_quality(self, quality: int) -> None:
        """Switch quality on the fly; also remembered for the next session."""
        self.quality = quality
        if self._controls is not None:
            self._controls.put({"quality": quality})

    def subscribe(self, viewer: Callable[[Frame | None], None]) -> None:
        self._viewers.add(viewer)
        for frame in self._gop:
            viewer(frame)
        if self._idle_handle:
            self._idle_handle.cancel()
            self._idle_handle = None
        if not self._task or self._task.done():
            self._task = self.hass.async_create_background_task(self._run(), f"ibox live {self.dev_id}")

    def unsubscribe(self, viewer: Callable[[Frame | None], None]) -> None:
        self._viewers.discard(viewer)
        if not self._viewers and not self._idle_handle:
            self._idle_handle = self.hass.loop.call_later(IDLE_TIMEOUT, self._idle_stop)

    def _idle_stop(self) -> None:
        self._idle_handle = None
        if not self._viewers and self._stop:
            self._stop.set()

    def _publish(self, frame: Frame | None) -> None:
        if frame is not None:
            if frame[0] in VIDEO_CODECS and frame[1]:
                self._gop = [frame]
            elif self._gop and len(self._gop) < 300:
                self._gop.append(frame)
        for viewer in list(self._viewers):
            viewer(frame)

    async def _run(self) -> None:
        try:
            info, auth, share = await prepare_session(self.coordinator, self.dev_id)
        except IboxError as err:
            _LOGGER.warning("iBOX live: cannot prepare session: %s", err)
            self._publish(None)
            return
        stop = self._stop = threading.Event()
        controls = self._controls = queue.Queue()
        loop = self.hass.loop
        request = {"mode": "live", "quality": self.quality, "camera": self.camera}

        def on_frame(*frame: Any) -> None:
            loop.call_soon_threadsafe(self._publish, frame)

        try:
            await self.hass.async_add_executor_job(
                run_session, info, auth, share, request, on_frame, stop, controls
            )
        except (PpcsError, TimeoutError, OSError) as err:
            _LOGGER.warning("iBOX live stream ended: %s", err)
        finally:
            self._stop = self._controls = None
            self._gop = []
            self._publish(None)


def _queue_viewer(frames: asyncio.Queue) -> Callable[[Frame | None], None]:
    def viewer(frame: Frame | None) -> None:
        try:
            frames.put_nowait(frame)
        except asyncio.QueueFull:
            pass  # a slow consumer drops frames rather than stalling the dashcam

    return viewer


class IboxLiveView(HomeAssistantView):
    """MPEG-TS endpoint for HA's stream worker; the random token is the only credential."""

    url = URL_PREFIX + "/{token}.ts"
    name = "api:ibox_cloud:live"
    requires_auth = False

    def __init__(self, streams: dict[str, LiveStream]) -> None:
        self._streams = streams

    async def get(self, request: web.Request, token: str) -> web.StreamResponse:
        stream = self._streams.get(token)
        if stream is None:
            raise web.HTTPNotFound
        response = web.StreamResponse(headers={"Content-Type": "video/mp2t", "Cache-Control": "no-cache"})
        await response.prepare(request)
        frames: asyncio.Queue[Frame | None] = asyncio.Queue(maxsize=600)
        viewer = _queue_viewer(frames)
        stream.subscribe(viewer)
        mux: TsMuxer | None = None
        t0 = 0
        try:
            while True:
                frame = await frames.get()
                if frame is None:
                    break
                codec, keyframe, pts_ms, data = frame
                if mux is None:
                    if codec not in VIDEO_CODECS or not keyframe:
                        continue  # every connection starts on a keyframe
                    mux, t0 = TsMuxer(codec), pts_ms
                pts = ((pts_ms - t0) * 90 + 90000) & ((1 << 33) - 1)
                if codec in VIDEO_CODECS:
                    await response.write(mux.video(pts, data, keyframe))
                elif codec == CODEC_AAC:
                    await response.write(mux.audio(pts, data))
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            stream.unsubscribe(viewer)
        return response


def _binary_frame(frame: Frame) -> bytes:
    """Panel player wire format: kind (1 video, 2 audio), codec, keyframe, pad, pts ms (u64 LE), payload."""
    codec, keyframe, pts_ms, data = frame
    kind = 1 if codec in VIDEO_CODECS else 2
    return struct.pack("<BBBxQ", kind, codec & 0xFF, int(keyframe), pts_ms & 0xFFFFFFFFFFFFFFFF) + data


def _status(state: str, **extra: Any) -> str:
    return json.dumps({"type": "status", "state": state, **extra})


class IboxStreamWebSocketView(HomeAssistantView):
    """WebSocket for the panel's native player: live view (shared) or playback of one file.

    Opened with a signed path; the client then sends {"cmd": "live"} or
    {"cmd": "playback", "path": ..., "file": ...}, later {"cmd": "speed", "value": n}
    or {"cmd": "quality", "value": n}. Frames arrive as binary messages.
    """

    url = WS_PREFIX + "/{dev_id}"
    name = "api:ibox_cloud:ws"
    requires_auth = True

    def __init__(self, hubs: dict[str, tuple[Any, LiveStream]]) -> None:
        self._hubs = hubs

    async def get(self, request: web.Request, dev_id: str) -> web.WebSocketResponse:
        hub = self._hubs.get(dev_id)
        if hub is None:
            raise web.HTTPNotFound
        coordinator, stream = hub
        ws = web.WebSocketResponse(heartbeat=20, max_msg_size=1 << 20)
        await ws.prepare(request)
        try:
            first = await ws.receive_json(timeout=10)
        except (TimeoutError, ValueError, TypeError):
            await ws.close()
            return ws
        if first.get("cmd") == "playback":
            await self._playback(ws, request.app["hass"], coordinator, dev_id, first)
        else:
            await self._live(ws, stream)
        return ws

    @staticmethod
    async def _send_loop(ws: web.WebSocketResponse, frames: asyncio.Queue) -> None:
        streaming = False
        while True:
            frame = await frames.get()
            if frame is None:
                await ws.send_str(_status("ended"))
                break
            if not streaming:
                streaming = True
                await ws.send_str(_status("streaming"))
            await ws.send_bytes(_binary_frame(frame))

    async def _live(self, ws: web.WebSocketResponse, stream: LiveStream) -> None:
        frames: asyncio.Queue[Frame | None] = asyncio.Queue(maxsize=600)
        viewer = _queue_viewer(frames)
        await ws.send_str(_status("connecting"))
        stream.subscribe(viewer)
        sender = asyncio.ensure_future(self._send_loop(ws, frames))
        try:
            async for msg in ws:
                if msg.type != web.WSMsgType.TEXT:
                    continue
                cmd = json.loads(msg.data)
                if cmd.get("cmd") == "quality":
                    stream.set_quality(int(cmd["value"]))
        finally:
            sender.cancel()
            stream.unsubscribe(viewer)

    async def _playback(
        self, ws: web.WebSocketResponse, hass: HomeAssistant, coordinator: Any, dev_id: str, cmd: dict
    ) -> None:
        await ws.send_str(_status("connecting"))
        try:
            info, auth, share = await prepare_session(coordinator, dev_id)
        except IboxError as err:
            await ws.send_str(_status("error", message=str(err)))
            return
        frames: asyncio.Queue[Frame | None] = asyncio.Queue(maxsize=900)
        viewer = _queue_viewer(frames)
        stop, controls = threading.Event(), queue.Queue()
        loop = hass.loop
        req = {"mode": "playback", "path": cmd.get("path", ""), "file": cmd.get("file", "")}

        def on_frame(*frame: Any) -> None:
            loop.call_soon_threadsafe(viewer, frame)

        async def run() -> None:
            try:
                await hass.async_add_executor_job(run_session, info, auth, share, req, on_frame, stop, controls)
            except (PpcsError, TimeoutError, OSError) as err:
                if not ws.closed:
                    await ws.send_str(_status("error", message=str(err)))
            finally:
                viewer(None)

        worker = hass.async_create_background_task(run(), f"ibox playback {dev_id}")
        sender = asyncio.ensure_future(self._send_loop(ws, frames))
        try:
            async for msg in ws:
                if msg.type != web.WSMsgType.TEXT:
                    continue
                data = json.loads(msg.data)
                if data.get("cmd") == "speed":
                    controls.put({"speed": int(data["value"])})
                elif data.get("cmd") == "quality":
                    controls.put({"quality": int(data["value"])})
                elif data.get("cmd") == "stop":
                    break
        finally:
            stop.set()
            sender.cancel()
            await asyncio.wait([worker], timeout=5)

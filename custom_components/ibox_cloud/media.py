"""Decrypted cloud recordings for the panel and automations (auth required)."""
from __future__ import annotations

from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.exceptions import HomeAssistantError

from .const import CLOUD_MEDIA_URL


class IboxCloudMediaView(HomeAssistantView):
    """GET <CLOUD_MEDIA_URL>/<did>/<video id>/video (MP4) or …/snapshot (JPEG)."""

    url = CLOUD_MEDIA_URL + r"/{dev_id}/{video_id:\d+}/{kind:(video|snapshot)}"
    name = "api:ibox_cloud:cloud"
    requires_auth = True

    def __init__(self, hubs: dict[str, tuple[Any, Any]]) -> None:
        self._hubs = hubs

    async def get(self, request: web.Request, dev_id: str, video_id: str, kind: str) -> web.Response:
        hub = self._hubs.get(dev_id)
        if hub is None:
            raise web.HTTPNotFound
        try:
            data, name = await hub[0].async_cloud_file(dev_id, int(video_id), kind)
        except HomeAssistantError as err:
            raise web.HTTPNotFound(text=str(err)) from err
        return web.Response(
            body=data,
            content_type="video/mp4" if kind == "video" else "image/jpeg",
            headers={"Content-Disposition": f'inline; filename="{name}"', "Cache-Control": "private, max-age=3600"},
        )

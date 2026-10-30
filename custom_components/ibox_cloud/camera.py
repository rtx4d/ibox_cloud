"""Camera entity: live view over the dashcam's P2P relay session."""
from __future__ import annotations

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IboxConfigEntry
from .coordinator import IboxCoordinator
from .entity import IboxDeviceEntity
from .junan import FILE_NORMAL


async def async_setup_entry(
    hass: HomeAssistant, entry: IboxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(IboxCamera(coordinator, device_id) for device_id in coordinator.live)


class IboxCamera(IboxDeviceEntity, Camera):
    """Live stream on demand; the still image is the newest recording's thumbnail."""

    _attr_translation_key = "live"
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, coordinator: IboxCoordinator, device_id: str) -> None:
        IboxDeviceEntity.__init__(self, coordinator, device_id)
        Camera.__init__(self)
        self._attr_unique_id = f"{device_id}_live"

    async def stream_source(self) -> str | None:
        return self.coordinator.live[self._device_id].url()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        files = self.coordinator.files(self._device_id, FILE_NORMAL)
        return self.coordinator.thumbnail(self._device_id, files[0]["fileName"]) if files else None

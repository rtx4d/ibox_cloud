"""Image entities: thumbnail of the newest recording of each kind (front camera)."""
from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IboxConfigEntry
from .coordinator import IboxCoordinator
from .entity import IboxDeviceEntity
from .junan import FILE_EVENT, FILE_NORMAL, FILE_PARKING

# file type -> translation key
KINDS = {FILE_NORMAL: "latest_video", FILE_EVENT: "latest_event", FILE_PARKING: "latest_parking"}


async def async_setup_entry(
    hass: HomeAssistant, entry: IboxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        IboxThumbnail(hass, coordinator, device_id, file_type)
        for device_id in coordinator.data.get("devices", {})
        for file_type in KINDS
    )


class IboxThumbnail(IboxDeviceEntity, ImageEntity):
    """JPEG preview the dashcam sends over MQTT for its newest file."""

    _attr_content_type = "image/jpeg"
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, hass: HomeAssistant, coordinator: IboxCoordinator, device_id: str, file_type: int
    ) -> None:
        IboxDeviceEntity.__init__(self, coordinator, device_id)
        ImageEntity.__init__(self, hass)
        self._file_type = file_type
        self._attr_translation_key = KINDS[file_type]
        self._attr_unique_id = f"{device_id}_{KINDS[file_type]}_image"
        self._shown: str | None = None

    def _newest(self) -> dict | None:
        files = self.coordinator.files(self._device_id, self._file_type)
        return files[0] if files else None

    @property
    def available(self) -> bool:
        newest = self._newest()
        return super().available and newest is not None and (
            self.coordinator.thumbnail(self._device_id, newest["fileName"]) is not None
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        newest = self._newest()
        name = newest["fileName"] if newest else None
        if name != self._shown and name and self.coordinator.thumbnail(self._device_id, name):
            self._shown = name
            self._attr_image_last_updated = datetime.fromtimestamp(
                newest.get("time", 0) / 1000, tz=timezone.utc
            )
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        newest = self._newest()
        return self.coordinator.thumbnail(self._device_id, newest["fileName"]) if newest else None

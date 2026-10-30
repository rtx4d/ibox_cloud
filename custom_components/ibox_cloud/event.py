"""Event entity: parking triggers (shock / motion), new protected or parking recordings, new cloud clips."""
from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IboxConfigEntry
from .coordinator import IboxCoordinator
from .entity import IboxDeviceEntity

EVENT_TYPES = ["parking_activity", "parking_recording", "event_recording", "cloud_recording"]


async def async_setup_entry(
    hass: HomeAssistant, entry: IboxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        IboxDashcamEvent(coordinator, device_id) for device_id in coordinator.data.get("devices", {})
    )


class IboxDashcamEvent(IboxDeviceEntity, EventEntity):
    """Fired by the coordinator; the dashcam itself sends no dedicated "shock" message."""

    _attr_translation_key = "dashcam_event"
    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator: IboxCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_dashcam_event"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        callbacks = self.coordinator.event_callbacks.setdefault(self._device_id, set())
        callbacks.add(self._on_event)
        self.async_on_remove(lambda: callbacks.discard(self._on_event))

    @callback
    def _on_event(self, event_type: str, attributes: dict[str, Any]) -> None:
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()

"""Select entities for multi-choice dashcam settings (radar mode, volume, …)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import IboxConfigEntry
from .coordinator import IboxCoordinator
from .entity import IboxDeviceEntity, IboxSettingEntity, settings_of_type


async def async_setup_entry(
    hass: HomeAssistant, entry: IboxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SelectEntity] = [
        IboxSettingSelect(coordinator, device_id, setting)
        for device_id in coordinator.data.get("devices", {})
        for setting in settings_of_type(coordinator, device_id, "select_input")
    ]
    entities += [
        IboxLiveOptionSelect(coordinator, device_id, key)
        for device_id in coordinator.live
        for key in LIVE_OPTIONS
    ]
    async_add_entities(entities)


class IboxSettingSelect(IboxSettingEntity, SelectEntity):
    """One select_input setting."""

    @property
    def options(self) -> list[str]:
        return list(self._labels.values())

    @property
    def current_option(self) -> str | None:
        return self._labels.get(self._value)

    async def async_select_option(self, option: str) -> None:
        key = next(key for key, label in self._labels.items() if label == option)
        await self._write(key)


# option key -> value sent to the dashcam (SET_STREAM_INFO channel / STREAM_START camera).
# The F5 PRO accepts channel 1 (1280x720) and 2 (640x360); 0 ("FullHD" in the SDK) is rejected.
LIVE_OPTIONS = {
    "live_quality": {"high": 1, "low": 2},
    "live_camera": {"front": 1, "rear": 2},
}


class IboxLiveOptionSelect(IboxDeviceEntity, RestoreEntity, SelectEntity):
    """Quality / camera used for the live view; mirrors the stream, which the panel can change too."""

    def __init__(self, coordinator: IboxCoordinator, device_id: str, key: str) -> None:
        super().__init__(coordinator, device_id)
        self._key = key
        self._attr = "quality" if key == "live_quality" else "camera"
        self._attr_translation_key = key
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_options = list(LIVE_OPTIONS[key])

    @property
    def _stream(self):
        return self.coordinator.live.get(self._device_id)

    @property
    def current_option(self) -> str | None:
        value = getattr(self._stream, self._attr, None)
        return next((k for k, v in LIVE_OPTIONS[self._key].items() if v == value), None)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state in self._attr_options and self._stream:
            setattr(self._stream, self._attr, LIVE_OPTIONS[self._key][last.state])

    async def async_select_option(self, option: str) -> None:
        stream = self._stream
        if not stream:
            return
        value = LIVE_OPTIONS[self._key][option]
        if self._attr == "quality":
            stream.set_quality(value)
        elif value != stream.camera:
            stream.camera = value
            stream.restart()
        self.async_write_ha_state()

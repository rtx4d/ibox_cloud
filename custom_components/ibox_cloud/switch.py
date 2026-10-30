"""Switch entities for on/off dashcam settings (audio recording, bands, …)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IboxConfigEntry
from .entity import IboxSettingEntity, settings_of_type


async def async_setup_entry(
    hass: HomeAssistant, entry: IboxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        IboxSettingSwitch(coordinator, device_id, setting)
        for device_id in coordinator.data.get("devices", {})
        for setting in settings_of_type(coordinator, device_id, "toggle")
    )


class IboxSettingSwitch(IboxSettingEntity, SwitchEntity):
    """One toggle setting: "1" on, "0" off."""

    @property
    def is_on(self) -> bool | None:
        value = self._value
        return None if value is None else value == "1"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._write("1")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._write("0")

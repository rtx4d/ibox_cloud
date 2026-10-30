"""Binary sensors: cloud connection, recording, ignition and GPS fix."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IboxConfigEntry
from .coordinator import IboxCoordinator
from .entity import IboxDeviceEntity

DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="connection_status",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key="record_status",
        translation_key="recording",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key="acc_status",
        translation_key="ignition",
        device_class=BinarySensorDeviceClass.POWER,
    ),
    BinarySensorEntityDescription(
        key="gps_status",
        translation_key="gps",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: IboxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        IboxBinarySensor(coordinator, device_id, description)
        for device_id in coordinator.data.get("devices", {})
        for description in DESCRIPTIONS
    )


class IboxBinarySensor(IboxDeviceEntity, BinarySensorEntity):
    """A "0"/"1" status attribute."""

    def __init__(
        self,
        coordinator: IboxCoordinator,
        device_id: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, device_id)
        self.entity_description = description
        # keep the original unique id of the connectivity sensor
        suffix = "online" if description.key == "connection_status" else description.key
        self._attr_unique_id = f"{device_id}_{suffix}"

    @property
    def is_on(self) -> bool | None:
        value = self._attrs.get(self.entity_description.key)
        if value is None:
            return None
        if self.entity_description.key != "connection_status" and not self._online:
            return False  # recording/ignition/GPS values are stale once the dashcam is off
        return str(value) not in ("0", "")

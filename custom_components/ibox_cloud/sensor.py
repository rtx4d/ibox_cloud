"""Sensors: last online, signal, temperature and memory card."""
from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IboxConfigEntry
from .coordinator import IboxCoordinator
from .entity import IboxDeviceEntity
from .junan import FILE_EVENT, FILE_NORMAL, FILE_PARKING

# readings the cloud keeps stale after the dashcam goes offline
LIVE_ONLY = {"device_signal_quality", "device_temp", "radar_strength"}

FILE_KINDS = {FILE_NORMAL: "latest_video", FILE_EVENT: "latest_event", FILE_PARKING: "latest_parking"}

DESCRIPTIONS = (
    SensorEntityDescription(
        key="radar_strength",
        translation_key="radar_strength",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="device_signal_quality",
        translation_key="signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="device_temp",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="sdcard_freesize",
        translation_key="sd_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="sdcard_totalsize",
        translation_key="sd_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: IboxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for device_id in coordinator.data.get("devices", {}):
        entities.append(IboxLastOnlineSensor(coordinator, device_id))
        entities.extend(IboxFileSensor(coordinator, device_id, kind) for kind in FILE_KINDS)
        entities.extend(
            IboxAttrSensor(coordinator, device_id, description) for description in DESCRIPTIONS
        )
    async_add_entities(entities)


class IboxAttrSensor(IboxDeviceEntity, SensorEntity):
    """A numeric status attribute."""

    def __init__(
        self, coordinator: IboxCoordinator, device_id: str, description: SensorEntityDescription
    ) -> None:
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def available(self) -> bool:
        # live readings are meaningless once the dashcam is off; the memory card size stays useful
        if self.entity_description.key in LIVE_ONLY:
            return super().available and self._online
        return super().available

    @property
    def native_value(self) -> float | None:
        try:
            return float(self._attrs[self.entity_description.key])
        except (KeyError, TypeError, ValueError):
            return None


class IboxFileSensor(IboxDeviceEntity, SensorEntity):
    """Time of the newest recording of one kind; the recent list is in the attributes."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: IboxCoordinator, device_id: str, file_type: int) -> None:
        super().__init__(coordinator, device_id)
        self._file_type = file_type
        self._attr_translation_key = FILE_KINDS[file_type]
        self._attr_unique_id = f"{device_id}_{FILE_KINDS[file_type]}"

    def _files(self) -> list[dict]:
        return self.coordinator.files(self._device_id, self._file_type)

    @property
    def native_value(self) -> datetime | None:
        files = self._files()
        return _parse_dt(files[0].get("time")) if files else None

    @property
    def extra_state_attributes(self) -> dict:
        files = self._files()
        if not files:
            return {}
        newest = files[0]
        return {
            "file_name": newest.get("fileName"),
            "duration_s": round(newest.get("duration", 0) / 1000),
            "size_mb": round(newest.get("size", 0) / 1_000_000, 1),
            "resolution": newest.get("resolution"),
            "recent": [
                {
                    "file_name": f.get("fileName"),
                    "time": (dt := _parse_dt(f.get("time"))) and dt.isoformat(),
                    "duration_s": round(f.get("duration", 0) / 1000),
                }
                for f in files[:10]
            ],
        }


class IboxLastOnlineSensor(IboxDeviceEntity, SensorEntity):
    """Last time the device was online."""

    _attr_translation_key = "last_online"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def unique_id(self) -> str:
        return f"{self._device_id}_last_online"

    @property
    def native_value(self) -> datetime | None:
        return _parse_dt(self._device.get("last_seen"))


def _parse_dt(raw) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        ts = raw / 1000 if raw > 1e12 else raw
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(raw, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f%z"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None

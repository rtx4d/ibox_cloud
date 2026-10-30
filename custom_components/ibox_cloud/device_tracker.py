"""Device tracker: the car's last known position."""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IboxConfigEntry
from .entity import IboxDeviceEntity, pick


async def async_setup_entry(
    hass: HomeAssistant, entry: IboxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        IboxDeviceTracker(coordinator, device_id)
        for device_id in coordinator.data.get("devices", {})
    )


class IboxDeviceTracker(IboxDeviceEntity, TrackerEntity):
    """Position of the vehicle from trips/last-position."""

    _attr_translation_key = "car"
    _attr_entity_category = None  # trackers default to diagnostic; this is the car itself

    @property
    def unique_id(self) -> str:
        return f"{self._device_id}_tracker"

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    def _pos(self) -> dict:
        pos = self._device.get("position")
        if isinstance(pos, dict) and pick(pos, "lat", "latitude") is not None:
            return pos
        # Fall back to the coordinates the dashcam reports itself; 0/0 means no fix
        lat, lon = self._attrs.get("radar_lat"), self._attrs.get("radar_lon")
        try:
            if float(lat) or float(lon):
                return {"lat": lat, "lon": lon}
        except (TypeError, ValueError):
            pass
        return {}

    @property
    def latitude(self) -> float | None:
        val = pick(self._pos(), "lat", "latitude")
        return float(val) if val is not None else None

    @property
    def longitude(self) -> float | None:
        val = pick(self._pos(), "lon", "lng", "longitude")
        return float(val) if val is not None else None

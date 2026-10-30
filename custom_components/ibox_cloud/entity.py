"""Shared base entity for iBOX Cloud."""
from __future__ import annotations

from typing import Any

from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PRIMARY_SETTINGS, SETTING_ICONS, TITLE_OVERRIDES
from .coordinator import IboxCoordinator


def pick(data: Any, *keys: str, default: Any = None) -> Any:
    """Return the first present key from a dict (response shapes vary)."""
    if isinstance(data, dict):
        for key in keys:
            if data.get(key) is not None:
                return data[key]
    return default


class IboxDeviceEntity(CoordinatorEntity[IboxCoordinator]):
    """Base entity tied to one cloud device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IboxCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id

    @property
    def _device(self) -> dict[str, Any]:
        return self.coordinator.data.get("devices", {}).get(self._device_id, {})

    @property
    def _info(self) -> dict[str, Any]:
        return self._device.get("info", {}) or {}

    @property
    def available(self) -> bool:
        return super().available and bool(self._device)

    @property
    def _online(self) -> bool:
        """The cloud keeps the last reported values after the dashcam goes offline."""
        return str(self._attrs.get("connection_status")) == "1"

    @property
    def device_info(self) -> DeviceInfo:
        info = self._info
        model = info.get("name") or "iBOX"
        cloud = info.get("cloudInfoDevice") or {}
        serial = cloud.get("sn", "").removeprefix("ibox.") or None
        # fwVersion looks like "<brand>,GRSF.2.9.3,25/06/2026,…"
        fw = (info.get("fwVersion") or "").split(",")
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=info.get("customName") or model,
            manufacturer="iBOX",
            model=model,
            serial_number=serial,
            sw_version=fw[1] if len(fw) > 1 else None,
        )

    @property
    def _attrs(self) -> dict[str, Any]:
        return self._device.get("attrs", {}) or {}


class IboxSettingEntity(IboxDeviceEntity):
    """A device setting described by the cloud settings file."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: IboxCoordinator, device_id: str, setting: dict[str, Any]) -> None:
        super().__init__(coordinator, device_id)
        self._setting_id: str = setting["id"]
        lang = "ru" if coordinator.hass.config.language.startswith("ru") else "en"
        title = TITLE_OVERRIDES.get(self._setting_id) or setting.get("title")
        self._attr_name = localized(title, lang) or self._setting_id
        cloud_type = self._device.get("cloud_type", "")
        same_title = [
            item
            for item in coordinator.settings(cloud_type)
            if localized(item.get("title"), lang) == self._attr_name
        ]
        if len(same_title) > 1:  # e.g. "Стрелка" is both a radar band and a GPS camera type
            tabs = (coordinator.schemas.get(cloud_type) or {}).get("tabs_settings") or []
            tab = next((t for t in tabs if t.get("id") == setting.get("id_tab")), {})
            if tab_title := localized(tab.get("title"), lang):
                self._attr_name = f"{self._attr_name} ({tab_title})"
        # option key (as sent to the device) -> label; the vendor's English labels
        # are often copy-pasted ("Off", "On", "Off"), so fall back to Russian
        values = setting.get("values") or {}
        for label_lang in (lang, "ru"):
            labels = {key: localized(label, label_lang) or key for key, label in values.items()}
            if len(set(labels.values())) == len(labels):
                break
        else:
            labels = {key: f"{label} ({key})" for key, label in labels.items()}
        self._labels = labels
        self._attr_unique_id = f"{device_id}_{self._setting_id}"
        if icon := SETTING_ICONS.get(self._setting_id):
            self._attr_icon = icon
        if self._setting_id not in PRIMARY_SETTINGS:
            self._attr_entity_registry_enabled_default = False

    @property
    def _value(self) -> str | None:
        value = self._attrs.get(self._setting_id)
        return None if value is None else str(value)

    async def _write(self, value: str) -> None:
        await self.coordinator.async_write_attr(self._device_id, self._setting_id, value)


def localized(text: Any, lang: str) -> str | None:
    if isinstance(text, dict):
        return text.get(lang) or text.get("en") or text.get("ru")
    return text if isinstance(text, str) else None


def settings_of_type(coordinator: IboxCoordinator, device_id: str, kind: str) -> list[dict[str, Any]]:
    device = coordinator.data.get("devices", {}).get(device_id, {})
    attrs = device.get("attrs", {})
    return [
        item
        for item in coordinator.settings(device.get("cloud_type", ""))
        if item.get("type") == kind and item.get("id") in attrs
    ]

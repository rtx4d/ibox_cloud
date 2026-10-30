"""The iBOX Cloud integration."""
from __future__ import annotations

import os

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IboxApiClient
from .const import CONF_SHOW_PANEL, CONF_TOKEN, DOMAIN
from .coordinator import IboxCoordinator
from .live import IboxLiveView, IboxStreamWebSocketView, LiveStream
from .ws_api import async_register as async_register_ws

PANEL_URL_PATH = "ibox"
PANEL_COMPONENT = "ibox-panel"
PANEL_STATIC_URL = f"/{DOMAIN}_frontend"
PANEL_FILE = os.path.join(os.path.dirname(__file__), "frontend", f"{PANEL_COMPONENT}.js")

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.DEVICE_TRACKER,
    Platform.EVENT,
    Platform.IMAGE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type IboxConfigEntry = ConfigEntry[IboxCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: IboxConfigEntry) -> bool:
    client = IboxApiClient(async_get_clientsession(hass), token=entry.data[CONF_TOKEN])
    coordinator = IboxCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    domain_data = hass.data.setdefault(DOMAIN, {})
    streams: dict[str, LiveStream] = domain_data.setdefault("streams", {})  # TS token -> stream
    hubs: dict[str, tuple] = domain_data.setdefault("hubs", {})  # did -> (coordinator, stream)
    if not domain_data.get("http"):
        domain_data["http"] = True
        hass.http.register_view(IboxLiveView(streams))
        hass.http.register_view(IboxStreamWebSocketView(hubs))
        async_register_ws(hass)
        await hass.http.async_register_static_paths(
            [StaticPathConfig(PANEL_STATIC_URL, os.path.dirname(PANEL_FILE), False)]
        )
    for dev_id in coordinator.data.get("devices", {}):
        stream = LiveStream(hass, coordinator, dev_id)
        coordinator.live[dev_id] = stream
        streams[stream.token] = stream
        hubs[dev_id] = (coordinator, stream)
    if entry.options.get(CONF_SHOW_PANEL, True):
        domain_data.setdefault("panel_entries", set()).add(entry.entry_id)
    await _async_update_panel(hass)

    _disable_recording_entities_once(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await coordinator.async_start_push()

    async def _stop_push(_event: Event) -> None:
        await coordinator.async_stop_push()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_push))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IboxConfigEntry) -> bool:
    coordinator = entry.runtime_data
    await coordinator.async_stop_push()
    domain_data = hass.data.get(DOMAIN, {})
    streams, hubs = domain_data.get("streams", {}), domain_data.get("hubs", {})
    for dev_id, stream in coordinator.live.items():
        stream.restart()
        streams.pop(stream.token, None)
        hubs.pop(dev_id, None)
    domain_data.get("panel_entries", set()).discard(entry.entry_id)
    await _async_update_panel(hass)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: IboxConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_update_panel(hass: HomeAssistant) -> None:
    """Show the sidebar panel while at least one entry wants it."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    wanted = bool(domain_data.get("panel_entries"))
    if wanted and not domain_data.get("panel"):
        domain_data["panel"] = True
        version = int(await hass.async_add_executor_job(os.path.getmtime, PANEL_FILE))
        await panel_custom.async_register_panel(
            hass,
            webcomponent_name=PANEL_COMPONENT,
            frontend_url_path=PANEL_URL_PATH,
            sidebar_title="iBOX Cloud",
            sidebar_icon="mdi:car-connected",
            module_url=f"{PANEL_STATIC_URL}/{PANEL_COMPONENT}.js?v={version}",
            require_admin=False,
        )
    elif not wanted and domain_data.get("panel"):
        domain_data["panel"] = False
        frontend.async_remove_panel(hass, PANEL_URL_PATH)


@callback
def _disable_recording_entities_once(hass: HomeAssistant, entry: IboxConfigEntry) -> None:
    """Recording sensors/images became disabled by default; apply that once to existing installs."""
    if entry.options.get("recording_entities_disabled"):
        return
    registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.disabled_by is None and any(
            reg_entry.unique_id.endswith(suffix) for suffix in ("_latest_video", "_latest_event", "_latest_parking",
                                                                 "_latest_video_image", "_latest_event_image",
                                                                 "_latest_parking_image")
        ):
            registry.async_update_entity(reg_entry.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
    hass.config_entries.async_update_entry(entry, options={**entry.options, "recording_entities_disabled": True})

"""Constants for the iBOX Cloud integration."""

DOMAIN = "ibox_cloud"

API_BASE = "https://ibox-api.iboxapi.ru"
CLOUD_BASE = "https://cloud-api.iboxrucloud.ru"
TRIPS_BASE = "https://dds.iboxrucloud.ru"

USER_AGENT = "okhttp/4.9.2"

# Auth channel types (ETypeAuth in the app)
AUTH_SMS = 1
AUTH_TELEGRAM = 2
AUTH_WAIT_CALL = 3
CALL_CODE = "000000"  # fixed code used for call verification

CONF_PHONE = "phone"
CONF_COUNTRY = "country"
CONF_TOKEN = "token"
CONF_AUTH_TYPE = "auth_type"
CONF_SHOW_PANEL = "show_panel"

DEFAULT_COUNTRY = "RU"

UPDATE_INTERVAL = 60  # seconds

# Live status attributes reported by the device (EAttributesMstar in the app)
STATUS_ATTRS = [
    "connection_status",
    "record_status",
    "acc_status",
    "gps_status",
    "device_signal_quality",
    "device_temp",
    "sdcard_status",
    "sdcard_freesize",
    "sdcard_totalsize",
    "current_storage",
    "radar_lat",
    "radar_lon",
    "radar_type",
    "radar_strength",
]

# Settings shown on the app's remote control screen; all others start disabled
PRIMARY_SETTINGS = {"radar_mode", "volume", "record_with_audio"}

# Icons for settings built from the vendor's description (they have no translation key)
SETTING_ICONS = {
    "radar_mode": "mdi:target-variant",
    "volume": "mdi:volume-high",
    "record_with_audio": "mdi:record-rec",
}

# Clearer names than the vendor's settings description
TITLE_OVERRIDES = {
    "video_quality": {"ru": "Уровень качества сохраняемого видео", "en": "Recorded video quality"},
    "volume": {"ru": "Громкость оповещений", "en": "Alert volume"},
    "record_with_audio": {"ru": "Запись звука на видео", "en": "Record audio with video"},
}

FILE_REFRESH_INTERVAL = 600  # seconds between memory card file list requests
EVENT_FILE_INTERVAL = 120  # seconds between checks for new protected (shock) recordings

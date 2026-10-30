# iBOX Cloud for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![Version](https://img.shields.io/github/v/release/rtx4d/ibox_cloud?label=version)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.10%2B-41BDF5)

<p align="center">
  <img src="https://media.giphy.com/media/YiNsruV2DYC7UVHv06/giphy.gif" alt="I made-" width="220">
</p>

**[Русский](#русский) · [English](#english)**

---

## Русский

Неофициальная интеграция видеорегистраторов **iBOX** c облачным доступом - то же, что умеет приложение iBOX Assist, только в Home Assistant.

### Возможности

- **Прямой эфир** с регистратора со звуком (720p / 360p, передняя / задняя камера)
- **Записи с карты памяти**: обычные, защищённые, парковка
- **Статус**: подключение, запись, зажигание, сигнал 4G, температура, карта памяти, GPS
- **Пульт и все настройки** регистратора (режим радара, громкость, штампы, парковка, G-сенсор и т.д.)
- **Мгновенные обновления** через MQTT и события `ibox_cloud_event` для автоматизаций
- **Своя панель «iBOX Cloud»** в боковом меню: эфир, записи, пульт, настройки, события

### Установка

**Через HACS:** *HACS → ⋮ → Пользовательские репозитории* → `https://github.com/rtx4d/ibox_cloud`, тип *Интеграция* → *Добавить* → Найти в поиске *iBOX Cloud* и установить.

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rtx4d&repository=ibox_cloud&category=integration)

**Вручную:** скопируйте `custom_components/ibox_cloud` в `config/custom_components/` и перезапустите Home Assistant.

### Настройка

[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ibox_cloud)

Нажмите кнопку выше (или *Настройки → Устройства и службы → Добавить интеграцию → iBOX Cloud*) и введите номер телефона из приложения iBOX Assist.
Подтверждение обычно идёт **звонком**: мастер покажет номер, на который нужно позвонить - вызов сбросится сам.
Если токен уже есть, вставьте его в поле «Токен»

> Регистратор должен быть уже подключён к облаку в приложении iBOX Assist.

### Важно

- Интеграция **неофициальная** и не связана с iBOX. Протокол облака может измениться в любой момент.
- Эфир и воспроизведение расходуют **мобильный трафик SIM** регистратора.
- Видео идёт в **H.265**: нативный плеер работает в Chrome / Edge / Safari; в остальных браузерах переключите плеер на HLS.

---

## English

Unofficial integration for **iBOX** cloud dashcams - what the iBOX Assist app does, inside Home Assistant.

### Features

- **Live view** with audio (720p / 360p, front / rear camera)
- **Memory card recordings**: normal, protected, parking
- **Status**: connection, recording, ignition, 4G signal, temperature, memory card, GPS
- **Remote control and all dashcam settings** (radar mode, volume, stamps, parking, G‑sensor, …)
- **Instant updates** over MQTT and `ibox_cloud_event` events for automations
- **"iBOX Cloud" sidebar panel**: live, recordings, remote, settings, events

### Installation

**HACS:** *HACS → ⋮ → Custom repositories* → `https://github.com/rtx4d/ibox_cloud`, type *Integration* → *Add* → search for *iBOX Cloud* and install it.

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rtx4d&repository=ibox_cloud&category=integration)

**Manual:** copy `custom_components/ibox_cloud` to `config/custom_components/` and restart Home Assistant.

### Setup

[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ibox_cloud)

Press the button above (or *Settings → Devices & services → Add integration → iBOX Cloud*) and enter the phone number used in iBOX Assist.
Verification is usually a **call**: the wizard shows a number to call, and the call is dropped automatically.
If you already have a token, paste it into the "Token" field.

> The dashcam must already be connected to the cloud in the iBOX Assist app.

### Notes

- This integration is **unofficial** and not affiliated with iBOX. The cloud protocol may change at any time.
- Live view and playback use the dashcam's **mobile data**.
- Video is **H.265**: the native player works in Chrome / Edge / Safari; in other browsers switch the player to HLS.

---

Дизайн панели вдохновлён [hass-xmeye](https://github.com/Moxnatiy/hass-xmeye) · Panel layout inspired by [hass-xmeye](https://github.com/Moxnatiy/hass-xmeye)

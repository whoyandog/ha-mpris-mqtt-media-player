# ha-mpris-mqtt-media-player

Пользовательская интеграция Home Assistant, которая создает нативную сущность media_player и использует MQTT-транспорт, совместимый с mpris-mqtt-adapter.

## Что делает интеграция

- Подписывается на состояние: workstation/media/state
- Подписывается на возможности: workstation/media/capabilities
- Подписывается на доступность: workstation/media/availability
- Публикует команды: workstation/media/cmd
- Маппит поля из payload:
  - state -> состояние media_player в Home Assistant
  - title -> media_title
  - artist -> media_artist
  - album -> media_album_name
  - art_url -> media_image_url
  - volume -> volume_level
  - position_seconds -> media_position
  - duration_seconds -> media_duration
  - loop_status -> repeat
  - shuffle -> shuffle

Поддерживаемые команды:

- play_pause (основное действие для UI play/pause)
- play
- pause
- next
- previous
- stop
- volume_set
- position_set (seek)
- shuffle_on / shuffle_off
- loop_none / loop_track / loop_playlist

Доступность отдельных функций в UI (громкость, seek, shuffle, repeat и т.д.) определяется по флагам can_* из topic workstation/media/capabilities.

Интеграция использует optimistic update: после отправки команды UI обновляется сразу, а затем синхронизируется по фактическому payload из topic состояния.

## Установка

1. Скопировать папку custom_components/mpris_mqtt_media_player в каталог конфигурации Home Assistant, в custom_components/.
2. Добавить конфигурацию в файла configuration.yaml
3. Перезапустите Home Assistant.

## Конфигурация (configuration.yaml)

```yaml
media_player:
  - platform: mpris_mqtt_media_player
    name: Workstation Media
    state_topic: workstation/media/state
    command_topic: workstation/media/cmd
    capabilities_topic: workstation/media/capabilities
    availability_topic: workstation/media/availability
    qos: 0
    retain: false
    unique_id: workstation_media_player
```

Все параметры опциональны, значения по умолчанию показаны выше.

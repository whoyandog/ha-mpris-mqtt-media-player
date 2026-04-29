# ha-mpris-mqtt-media-player

Пользовательская интеграция Home Assistant, которая создает нативную сущность media_player и использует MQTT-транспорт, совместимый с mpris-mqtt-adapter.

## Что делает интеграция

- Подписывается на состояние: workstation/media/state
- Подписывается на доступность: workstation/media/availability
- Публикует команды: workstation/media/cmd
- Маппит поля из payload:
  - state -> состояние media_player в Home Assistant
  - title -> media_title
  - artist -> media_artist
  - album -> media_album_name
  - volume -> volume_level

Поддерживаемые команды:

- play
- pause
- next
- previous
- stop
- volume_set

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
    availability_topic: workstation/media/availability
    qos: 0
    retain: false
    unique_id: workstation_media_player
```

Все параметры опциональны, значения по умолчанию показаны выше.

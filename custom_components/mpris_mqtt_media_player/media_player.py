"""Media player platform for MPRIS over MQTT."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player.const import MediaPlayerState, RepeatMode
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_STATE_TOPIC = "state_topic"
CONF_CMD_TOPIC = "command_topic"
CONF_CAPABILITIES_TOPIC = "capabilities_topic"
CONF_AVAILABILITY_TOPIC = "availability_topic"
CONF_QOS = "qos"
CONF_RETAIN = "retain"
CONF_UNIQUE_ID = "unique_id"

DEFAULT_NAME = "Workstation Media"
DEFAULT_STATE_TOPIC = "workstation/media/state"
DEFAULT_CMD_TOPIC = "workstation/media/cmd"
DEFAULT_CAPABILITIES_TOPIC = "workstation/media/capabilities"
DEFAULT_AVAILABILITY_TOPIC = "workstation/media/availability"
DEFAULT_UNIQUE_ID = "workstation_media_player"

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_STATE_TOPIC, default=DEFAULT_STATE_TOPIC): cv.string,
        vol.Optional(CONF_CMD_TOPIC, default=DEFAULT_CMD_TOPIC): cv.string,
        vol.Optional(CONF_CAPABILITIES_TOPIC, default=DEFAULT_CAPABILITIES_TOPIC): cv.string,
        vol.Optional(CONF_AVAILABILITY_TOPIC, default=DEFAULT_AVAILABILITY_TOPIC): cv.string,
        vol.Optional(CONF_QOS, default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=2)),
        vol.Optional(CONF_RETAIN, default=False): cv.boolean,
        vol.Optional(CONF_UNIQUE_ID, default=DEFAULT_UNIQUE_ID): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MQTT MPRIS media player platform from YAML."""
    entity = MprisMqttMediaPlayer(
        name=config[CONF_NAME],
        state_topic=config[CONF_STATE_TOPIC],
        cmd_topic=config[CONF_CMD_TOPIC],
        capabilities_topic=config[CONF_CAPABILITIES_TOPIC],
        availability_topic=config[CONF_AVAILABILITY_TOPIC],
        qos=config[CONF_QOS],
        retain=config[CONF_RETAIN],
        unique_id=config[CONF_UNIQUE_ID],
    )

    async_add_entities([entity])


class MprisMqttMediaPlayer(MediaPlayerEntity):
    """Representation of a media player controlled via MQTT."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.VOLUME_SET
    )

    def __init__(
        self,
        *,
        name: str,
        state_topic: str,
        cmd_topic: str,
        capabilities_topic: str,
        availability_topic: str,
        qos: int,
        retain: bool,
        unique_id: str,
    ) -> None:
        self._attr_name = name
        self._attr_unique_id = unique_id

        self._state_topic = state_topic
        self._cmd_topic = cmd_topic
        self._capabilities_topic = capabilities_topic
        self._availability_topic = availability_topic
        self._qos = qos
        self._retain = retain

        self._attr_state = MediaPlayerState.OFF
        self._attr_available = False
        self._attr_media_title = None
        self._attr_media_artist = None
        self._attr_media_album_name = None
        self._attr_media_image_url = None
        self._attr_media_position = None
        self._attr_media_duration = None
        self._attr_media_position_updated_at = None
        self._attr_repeat = RepeatMode.OFF
        self._attr_shuffle = None
        self._attr_volume_level = None
        self._unsubscribers: list[Callable[[], None]] = []
        self._set_default_supported_features()

    def _set_default_supported_features(self) -> None:
        self._attr_supported_features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.VOLUME_SET
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT topics when entity is added."""

        @callback
        def state_message_received(msg: mqtt.ReceiveMessage) -> None:
            self._handle_state_message(msg.payload)

        @callback
        def availability_received(msg: mqtt.ReceiveMessage) -> None:
            payload = msg.payload.strip().lower()
            self._attr_available = payload == "online"
            self.async_write_ha_state()

        @callback
        def capabilities_received(msg: mqtt.ReceiveMessage) -> None:
            self._handle_capabilities_message(msg.payload)

        self._unsubscribers.append(
            await mqtt.async_subscribe(
                self.hass,
                self._state_topic,
                state_message_received,
                qos=self._qos,
                encoding="utf-8",
            )
        )
        self._unsubscribers.append(
            await mqtt.async_subscribe(
                self.hass,
                self._availability_topic,
                availability_received,
                qos=self._qos,
                encoding="utf-8",
            )
        )
        self._unsubscribers.append(
            await mqtt.async_subscribe(
                self.hass,
                self._capabilities_topic,
                capabilities_received,
                qos=self._qos,
                encoding="utf-8",
            )
        )

        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from MQTT topics when entity is removed."""
        while self._unsubscribers:
            unsub = self._unsubscribers.pop()
            unsub()

    async def async_media_play(self) -> None:
        """Send play command."""
        await self._publish_action("play_pause")
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._publish_action("play_pause")
        self._attr_state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._publish_action("stop")
        self._attr_state = MediaPlayerState.IDLE
        self.async_write_ha_state()

    async def async_media_next_track(self) -> None:
        """Send next-track command."""
        await self._publish_action("next")

    async def async_media_previous_track(self) -> None:
        """Send previous-track command."""
        await self._publish_action("previous")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level via volume_set action."""
        await self._publish_action("volume_set", value=volume)
        self._attr_volume_level = _parse_volume(volume)
        self.async_write_ha_state()

    async def async_media_seek(self, position: float) -> None:
        """Seek to absolute position in seconds."""
        await self._publish_action("position_set", value=position)
        self._attr_media_position = _parse_positive_float(position)
        self._attr_media_position_updated_at = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable or disable shuffle mode."""
        await self._publish_action("shuffle_on" if shuffle else "shuffle_off")
        self._attr_shuffle = shuffle
        self.async_write_ha_state()

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        action_map = {
            RepeatMode.OFF: "loop_none",
            RepeatMode.ONE: "loop_track",
            RepeatMode.ALL: "loop_playlist",
        }
        action = action_map.get(repeat)
        if action is not None:
            await self._publish_action(action)
            self._attr_repeat = repeat
            self.async_write_ha_state()

    async def _publish_action(self, action: str, value: float | None = None) -> None:
        payload: dict[str, Any] = {"action": action}
        if value is not None:
            payload["value"] = value

        await mqtt.async_publish(
            self.hass,
            self._cmd_topic,
            json.dumps(payload, ensure_ascii=True),
            qos=self._qos,
            retain=self._retain,
        )

    def _handle_state_message(self, payload: str) -> None:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            _LOGGER.warning("Invalid JSON in state topic: %s", payload)
            return

        self._attr_state = _map_state(data.get("state"))
        self._attr_media_title = _nullable_str(data.get("title"))
        self._attr_media_artist = _nullable_str(data.get("artist"))
        self._attr_media_album_name = _nullable_str(data.get("album"))
        self._attr_media_image_url = _nullable_str(data.get("art_url"))
        self._attr_volume_level = _parse_volume(data.get("volume"))
        self._attr_media_position = _parse_positive_float(data.get("position_seconds"))
        self._attr_media_duration = _parse_positive_float(data.get("duration_seconds"))
        self._attr_media_position_updated_at = dt_util.utcnow()
        self._attr_shuffle = _parse_shuffle(data.get("shuffle"))
        self._attr_repeat = _parse_repeat(data.get("loop_status"))

        # A valid state payload means the bridge is alive even if availability lags.
        self._attr_available = True
        self.async_write_ha_state()

    def _handle_capabilities_message(self, payload: str) -> None:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            _LOGGER.warning("Invalid JSON in capabilities topic: %s", payload)
            return

        features = MediaPlayerEntityFeature(0)
        if _parse_bool(data.get("can_play")):
            features |= MediaPlayerEntityFeature.PLAY
        if _parse_bool(data.get("can_pause")):
            features |= MediaPlayerEntityFeature.PAUSE
        if _parse_bool(data.get("can_stop")):
            features |= MediaPlayerEntityFeature.STOP
        if _parse_bool(data.get("can_next")):
            features |= MediaPlayerEntityFeature.NEXT_TRACK
        if _parse_bool(data.get("can_previous")):
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
        if _parse_bool(data.get("can_set_volume")):
            features |= MediaPlayerEntityFeature.VOLUME_SET
        if _parse_bool(data.get("can_seek")):
            features |= MediaPlayerEntityFeature.SEEK
        if _parse_bool(data.get("can_shuffle")):
            features |= MediaPlayerEntityFeature.SHUFFLE_SET
        if _parse_bool(data.get("can_loop")):
            features |= MediaPlayerEntityFeature.REPEAT_SET

        self._attr_supported_features = features
        self.async_write_ha_state()


def _nullable_str(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _parse_volume(value: Any) -> float | None:
    if value is None:
        return None

    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None

    if parsed < 0:
        return 0.0
    if parsed > 1:
        return 1.0
    return parsed


def _parse_positive_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None

    if parsed < 0:
        return None
    return parsed


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        return lowered in {"true", "1", "yes", "on"}
    return bool(value)


def _parse_repeat(value: Any) -> RepeatMode:
    loop_status = str(value or "").strip().lower()
    if loop_status == "track":
        return RepeatMode.ONE
    if loop_status == "playlist":
        return RepeatMode.ALL
    return RepeatMode.OFF


def _parse_shuffle(value: Any) -> bool | None:
    text = str(value or "").strip().lower()
    if text in {"on", "true", "1", "yes"}:
        return True
    if text in {"off", "false", "0", "no"}:
        return False
    return None


def _map_state(raw_state: Any) -> MediaPlayerState:
    state = str(raw_state or "").strip().lower()
    if state == "playing":
        return MediaPlayerState.PLAYING
    if state == "paused":
        return MediaPlayerState.PAUSED
    if state == "stopped":
        return MediaPlayerState.IDLE
    return MediaPlayerState.OFF

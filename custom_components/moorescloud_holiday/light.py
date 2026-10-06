"""Light platform for the MooresCloud Holiday integration."""
from __future__ import annotations

import asyncio
import colorsys
import logging
import random
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)

from . import DOMAIN
from .holiday_api import HolidayAPI, HolidayAPIError

_LOGGER = logging.getLogger(__name__)

NUM_GLOBES = 50

EFFECT_GRADIENT_WARM = "Gradient Warm"
EFFECT_GRADIENT_COOL = "Gradient Cool"
EFFECT_RAINBOW = "Rainbow"
EFFECT_CANDLE = "Candle"

EFFECTS = [EFFECT_RAINBOW, EFFECT_CANDLE, EFFECT_GRADIENT_WARM, EFFECT_GRADIENT_COOL]

CANDLE_FPS = 10


def _scale_rgb(r: int, g: int, b: int, brightness: int) -> tuple[int, int, int]:
    f = brightness / 255.0
    return round(r * f), round(g * f), round(b * f)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _gradient_colours(
    begin: tuple[int, int, int], end: tuple[int, int, int], n: int = NUM_GLOBES
) -> list[str]:
    colours = []
    for i in range(n):
        t = i / max(n - 1, 1)
        r = round(begin[0] + (end[0] - begin[0]) * t)
        g = round(begin[1] + (end[1] - begin[1]) * t)
        b = round(begin[2] + (end[2] - begin[2]) * t)
        colours.append(_rgb_to_hex(r, g, b))
    return colours


def _candle_base() -> list[tuple[int, int, int]]:
    return [
        (
            min(255, 220 + random.randint(-10, 10)),
            min(255, max(0, 90 + random.randint(-20, 20))),
            0,
        )
        for _ in range(NUM_GLOBES)
    ]


def _candle_frame(base: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    return [
        (
            min(255, max(0, r + random.randint(-15, 15))),
            min(255, max(0, g + random.randint(-20, 10))),
            0,
        )
        for r, g, _ in base
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    api: HolidayAPI = hass.data[DOMAIN][entry.entry_id]["api"]
    host = entry.data[CONF_HOST]
    name = entry.data.get(CONF_NAME, "Holiday")
    entity = HolidayLightEntity(api=api, name=name, host=host, entry_id=entry.entry_id)
    async_add_entities([entity])

    platform = async_get_current_platform()
    platform.async_register_entity_service(
        "set_pattern",
        {"lights": list},
        "async_set_pattern",
    )


class HolidayLightEntity(LightEntity):
    """Representation of the MooresCloud Holiday as a HA light."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = EFFECTS

    def __init__(self, api: HolidayAPI, name: str, host: str, entry_id: str) -> None:
        self._api = api
        self._attr_unique_id = f"{DOMAIN}_{entry_id}"
        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_rgb_color: tuple[int, int, int] = (255, 255, 255)
        self._attr_effect: str | None = None
        self._animation_task: asyncio.Task | None = None
        self._rainbow_running = False

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=name,
            manufacturer="MooresCloud",
            model="Holiday",
            configuration_url=f"http://{host}/",
        )

    # ------------------------------------------------------------------
    # Animation task management
    # ------------------------------------------------------------------

    def _stop_animation(self) -> None:
        if self._animation_task and not self._animation_task.done():
            self._animation_task.cancel()
        self._animation_task = None

    def _start_animation(self, coro) -> None:
        self._stop_animation()
        self._animation_task = asyncio.get_event_loop().create_task(coro)

    async def _stop_rainbow_firmware(self) -> None:
        """Stop the firmware rainbow if it was running."""
        if self._rainbow_running:
            try:
                await self._api.rainbow_stop()
            except HolidayAPIError as exc:
                _LOGGER.warning("Failed to stop firmware rainbow: %s", exc)
            self._rainbow_running = False

    async def _animate_candle(self) -> None:
        interval = 1.0 / CANDLE_FPS
        base = _candle_base()
        try:
            while True:
                self._api.send_udp_frame(_candle_frame(base))
                if random.random() < 0.1:
                    base = _candle_base()
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass

    # ------------------------------------------------------------------
    # HA commands
    # ------------------------------------------------------------------

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_RGB_COLOR in kwargs:
            self._attr_rgb_color = kwargs[ATTR_RGB_COLOR]
        if ATTR_BRIGHTNESS in kwargs:
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]
        if ATTR_EFFECT in kwargs:
            self._attr_effect = kwargs[ATTR_EFFECT]

        self._attr_is_on = True
        try:
            await self._apply_state()
        except HolidayAPIError as exc:
            _LOGGER.error("Error communicating with Holiday: %s", exc)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._stop_animation()
        await self._stop_rainbow_firmware()
        self._attr_is_on = False
        self._attr_effect = None
        try:
            await self._api.turn_off()
        except HolidayAPIError as exc:
            _LOGGER.error("Error communicating with Holiday: %s", exc)
        self.async_write_ha_state()

    async def async_set_pattern(self, lights: list[str]) -> None:
        """Set each globe individually (up to 50 hex strings)."""
        self._stop_animation()
        await self._stop_rainbow_firmware()
        padded = (list(lights) + ["#000000"] * NUM_GLOBES)[:NUM_GLOBES]
        try:
            await self._api.set_lights(padded)
            self._attr_is_on = True
            self._attr_effect = None
            self.async_write_ha_state()
        except HolidayAPIError as exc:
            _LOGGER.error("Error setting pattern on Holiday: %s", exc)

    async def async_will_remove_from_hass(self) -> None:
        self._stop_animation()
        await self._stop_rainbow_firmware()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _apply_state(self) -> None:
        # Stop whatever was previously running
        self._stop_animation()
        await self._stop_rainbow_firmware()

        effect = self._attr_effect
        brightness = self._attr_brightness or 255
        r, g, b = self._attr_rgb_color or (255, 255, 255)
        sr, sg, sb = _scale_rgb(r, g, b, brightness)

        if effect == EFFECT_RAINBOW:
            await self._api.rainbow_start()
            self._rainbow_running = True
        elif effect == EFFECT_CANDLE:
            self._start_animation(self._animate_candle())
        elif effect == EFFECT_GRADIENT_WARM:
            await self._api.set_lights(_gradient_colours((200, 60, 0), (255, 220, 80)))
        elif effect == EFFECT_GRADIENT_COOL:
            await self._api.set_lights(_gradient_colours((0, 0, 200), (0, 200, 255)))
        else:
            await self._api.set_all(sr, sg, sb)

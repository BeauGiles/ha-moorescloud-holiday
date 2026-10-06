"""Switch platform for the MooresCloud Holiday integration (developer mode toggle)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .coordinator import HolidayCoordinator
from .holiday_api import HolidayAPIError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HolidayCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    host = entry.data[CONF_HOST]
    name = entry.data.get(CONF_NAME, "Holiday")
    async_add_entities([HolidayDevModeSwitch(coordinator, entry.entry_id, name, host)])


class HolidayDevModeSwitch(CoordinatorEntity[HolidayCoordinator], SwitchEntity):
    """Toggle SSH / developer mode on the Holiday."""

    _attr_has_entity_name = True
    _attr_name = "Developer Mode"
    _attr_icon = "mdi:console"

    def __init__(
        self,
        coordinator: HolidayCoordinator,
        entry_id: str,
        device_name: str,
        host: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_devmode"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=device_name,
            manufacturer="MooresCloud",
            model="Holiday",
            configuration_url=f"http://{host}/",
        )

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("devmode", False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_devmode(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_devmode(False)

    async def _set_devmode(self, enabled: bool) -> None:
        try:
            await self.coordinator.api.set_devmode(enabled)
            # Update cache optimistically so the UI reflects the change immediately
            self.coordinator.data["devmode"] = enabled
            self.async_write_ha_state()
        except HolidayAPIError as exc:
            _LOGGER.error("Failed to set devmode on Holiday: %s", exc)

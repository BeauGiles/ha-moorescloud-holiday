"""MooresCloud Holiday integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import HolidayCoordinator
from .holiday_api import HolidayAPI, HolidayAPIError

_LOGGER = logging.getLogger(__name__)

DOMAIN = "moorescloud_holiday"
PLATFORMS = [Platform.LIGHT, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MooresCloud Holiday from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 80)

    api = HolidayAPI(host=host, port=port)

    try:
        reachable = await api.ping()
        if not reachable:
            await api.close()
            raise ConfigEntryNotReady(f"Holiday at {host}:{port} did not respond")
    except HolidayAPIError as exc:
        await api.close()
        raise ConfigEntryNotReady(
            f"Could not connect to Holiday at {host}:{port}: {exc}"
        ) from exc
    except ConfigEntryNotReady:
        raise
    except Exception as exc:  # noqa: BLE001
        await api.close()
        _LOGGER.exception("Unexpected error setting up Holiday at %s:%s", host, port)
        raise ConfigEntryNotReady(f"Unexpected error: {exc}") from exc

    coordinator = HolidayCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["api"].close()
    return unload_ok

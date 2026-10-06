"""Config flow for the MooresCloud Holiday integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .holiday_api import HolidayAPI, HolidayAPIError

_LOGGER = logging.getLogger(__name__)

DOMAIN = "moorescloud_holiday"
DEFAULT_PORT = 80


class HolidayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the UI config flow for a MooresCloud Holiday device."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input.get(CONF_PORT, DEFAULT_PORT))

            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            errors = await _test_connection(host, port)

            if not errors:
                name = (user_input.get(CONF_NAME) or "").strip() or f"Holiday ({host})"
                return self.async_create_entry(
                    title=name,
                    data={CONF_HOST: host, CONF_PORT: port, CONF_NAME: name},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
                vol.Optional(CONF_NAME, default="Holiday"): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input.get(CONF_PORT, DEFAULT_PORT))

            errors = await _test_connection(host, port)

            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, CONF_HOST: host, CONF_PORT: port},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST, "")): str,
                vol.Optional(CONF_PORT, default=entry.data.get(CONF_PORT, DEFAULT_PORT)): vol.Coerce(int),
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )


async def _test_connection(host: str, port: int) -> dict[str, str]:
    """Return an errors dict; empty means success."""
    api = HolidayAPI(host=host, port=port)
    errors: dict[str, str] = {}
    try:
        reachable = await api.ping()
        if not reachable:
            errors["base"] = "cannot_connect"
    except HolidayAPIError:
        errors["base"] = "cannot_connect"
    except aiohttp.ClientError:
        errors["base"] = "cannot_connect"
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected error connecting to Holiday at %s:%s", host, port)
        errors["base"] = "unknown"
    finally:
        await api.close()
    return errors

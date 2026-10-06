"""Data update coordinator for the MooresCloud Holiday integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .holiday_api import HolidayAPI, HolidayAPIError

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(hours=1)


class HolidayCoordinator(DataUpdateCoordinator[dict]):
    """Polls the Holiday for slow-changing state (e.g. devmode) once per hour."""

    def __init__(self, hass: HomeAssistant, api: HolidayAPI) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="MooresCloud Holiday",
            update_interval=POLL_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> dict:
        try:
            devmode = await self.api.get_devmode()
            return {"devmode": devmode}
        except HolidayAPIError as exc:
            raise UpdateFailed(f"Error fetching Holiday state: {exc}") from exc

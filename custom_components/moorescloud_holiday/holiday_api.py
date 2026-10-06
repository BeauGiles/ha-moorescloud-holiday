"""Client for the MooresCloud Holiday IoTAS REST API + UDP Secret API."""
from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

SETLIGHTS_PATH = "/iotas/0.1/device/moorescloud.holiday/localhost/setlights"
GRADIENT_PATH = "/iotas/0.1/device/moorescloud.holiday/localhost/gradient"
RAINBOW_PATH = "/iotas/0.1/device/moorescloud.holiday/localhost/rainbow"
NUM_GLOBES = 50
DEFAULT_PORT = 80
UDP_PORT = 9988
TIMEOUT = aiohttp.ClientTimeout(total=10)

_UDP_HEADER = b"\x00" * 10


class HolidayAPIError(Exception):
    """Raised when communication with the Holiday device fails."""


class HolidayAPI:
    """Async HTTP + UDP client for the MooresCloud Holiday."""

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        self._host = host
        self._port = port
        self._base = f"http://{host}:{port}"
        self._session: aiohttp.ClientSession | None = None
        self._udp_sock: socket.socket | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=TIMEOUT)
        return self._session

    def _get_udp_sock(self) -> socket.socket:
        if self._udp_sock is None:
            self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return self._udp_sock

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        if self._udp_sock:
            self._udp_sock.close()
            self._udp_sock = None

    async def _put(self, path: str, payload: dict[str, Any]) -> bool:
        session = await self._get_session()
        url = self._base + path
        try:
            async with session.put(url, json=payload) as resp:
                if resp.status != 200:
                    raise HolidayAPIError(f"HTTP {resp.status} from {url}")
                data = await resp.json(content_type=None)
                return bool(data.get("value", data.get("success", False)))
        except aiohttp.ClientError as exc:
            raise HolidayAPIError(f"Connection error to {url}: {exc}") from exc

    def send_udp_frame(self, colours: list[tuple[int, int, int]]) -> None:
        """Send a single frame of 50 RGB tuples over UDP. Non-blocking."""
        if len(colours) != NUM_GLOBES:
            raise ValueError(f"Expected {NUM_GLOBES} colours, got {len(colours)}")
        rgb_bytes = bytearray()
        for r, g, b in colours:
            rgb_bytes += bytes([r, g, b])
        packet = _UDP_HEADER + bytes(rgb_bytes)
        try:
            self._get_udp_sock().sendto(packet, (self._host, UDP_PORT))
        except OSError as exc:
            _LOGGER.warning("UDP send failed: %s", exc)

    async def set_lights(self, colours: list[str]) -> bool:
        if len(colours) != NUM_GLOBES:
            raise ValueError(f"set_lights requires {NUM_GLOBES} colours, got {len(colours)}")
        return await self._put(SETLIGHTS_PATH, {"lights": colours})

    async def set_all(self, r: int, g: int, b: int) -> bool:
        hex_colour = f"#{r:02x}{g:02x}{b:02x}"
        return await self.set_lights([hex_colour] * NUM_GLOBES)

    async def turn_off(self) -> bool:
        return await self.set_all(0, 0, 0)

    async def gradient(
        self,
        begin_rgb: tuple[int, int, int],
        end_rgb: tuple[int, int, int],
        steps: int = 128,
    ) -> bool:
        payload = {"begin": list(begin_rgb), "end": list(end_rgb), "steps": steps}
        return await self._put(GRADIENT_PATH, payload)

    async def rainbow_start(self) -> bool:
        """Start the firmware rainbow app."""
        return await self._put(RAINBOW_PATH, {"isStart": True})

    async def rainbow_stop(self) -> bool:
        """Stop the firmware rainbow app."""
        return await self._put(RAINBOW_PATH, {"isStart": False})

    async def ping(self) -> bool:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=8,
            )
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return True
        except (OSError, asyncio.TimeoutError) as exc:
            _LOGGER.debug("Holiday at %s:%s not reachable: %s", self._host, self._port, exc)
            return False

    async def get_devmode(self) -> bool:
        """Return whether developer mode (SSH) is enabled."""
        session = await self._get_session()
        url = self._base + "/iotas/0.1/device/moorescloud.holiday/localhost/devmode"
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise HolidayAPIError(f"HTTP {resp.status} from {url}")
                data = await resp.json(content_type=None)
                return bool(data.get("devmode", False))
        except aiohttp.ClientError as exc:
            raise HolidayAPIError(f"Connection error to {url}: {exc}") from exc

    async def set_devmode(self, enabled: bool) -> bool:
        """Enable or disable developer mode (SSH)."""
        return await self._put(
            "/iotas/0.1/device/moorescloud.holiday/localhost/devmode",
            {"devmode": enabled},
        )

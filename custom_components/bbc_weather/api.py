"""Async API client for BBC Weather."""

from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any
from urllib.parse import quote, quote_plus

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import (
    BBC_LOCATOR_API_KEY,
    FORECAST_URL,
    LOCATION_SEARCH_URL,
    MAX_RESPONSE_SIZE,
    OBSERVATION_URL,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 1  # seconds


class BBCWeatherAPIError(Exception):
    """Raised when an API request fails after retries."""


def _validate_location_id(location_id: str) -> None:
    """Raise if location_id is not a numeric GeoNames ID."""
    if not isinstance(location_id, str) or not location_id.isdigit():
        raise BBCWeatherAPIError(f"Invalid location ID: {location_id!r}")


class BBCWeatherAPI:
    """Async client for BBC Weather public APIs."""

    def __init__(
        self, session: ClientSession, api_key: str | None = None
    ) -> None:
        """Initialise with an aiohttp session and optional API key override."""
        self._session = session
        self._api_key = api_key or BBC_LOCATOR_API_KEY
        self._timeout = ClientTimeout(total=REQUEST_TIMEOUT)

    async def _request(self, url: str) -> dict[str, Any]:
        """Make a GET request with retry, exponential backoff, and jitter."""
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                async with self._session.get(
                    url, timeout=self._timeout
                ) as resp:
                    resp.raise_for_status()
                    body = await resp.content.read(MAX_RESPONSE_SIZE + 1)
                    if len(body) > MAX_RESPONSE_SIZE:
                        raise BBCWeatherAPIError(
                            f"Response too large (exceeded "
                            f"{MAX_RESPONSE_SIZE} byte limit)"
                        )
                    result = json.loads(body)
                    if not isinstance(result, dict):
                        raise BBCWeatherAPIError(
                            f"Unexpected response type: "
                            f"{type(result).__name__}, expected dict"
                        )
                    return result
            except BBCWeatherAPIError:
                raise
            except (TimeoutError, ClientError, ValueError) as err:
                last_error = err
                if attempt < MAX_RETRIES - 1:
                    wait = INITIAL_BACKOFF * (2 ** attempt) + random.uniform(
                        0, 1
                    )
                    _LOGGER.debug(
                        "BBC Weather API request failed (attempt %d/%d), "
                        "retrying in %.1fs: %r",
                        attempt + 1,
                        MAX_RETRIES,
                        wait,
                        type(err).__name__,
                    )
                    await asyncio.sleep(wait)
        raise BBCWeatherAPIError(
            f"BBC Weather API request failed after {MAX_RETRIES} attempts: "
            f"{type(last_error).__name__}"
        ) from last_error

    async def search_location(self, query: str) -> dict[str, Any]:
        """Search for a location by name. Returns the raw API response dict."""
        url = LOCATION_SEARCH_URL.format(
            api_key=quote_plus(self._api_key), query=quote(query)
        )
        return await self._request(url)

    async def get_forecast(self, location_id: str) -> dict[str, Any]:
        """Get aggregated forecast (14-day with hourly detail) for a location."""
        _validate_location_id(location_id)
        url = FORECAST_URL.format(location_id=location_id)
        return await self._request(url)

    async def get_observations(self, location_id: str) -> dict[str, Any]:
        """Get current observations for a location."""
        _validate_location_id(location_id)
        url = OBSERVATION_URL.format(location_id=location_id)
        return await self._request(url)

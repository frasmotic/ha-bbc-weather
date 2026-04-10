"""Data update coordinator for BBC Weather."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BBCWeatherAPI
from .const import (
    BBC_TO_HA_CONDITION,
    FORECAST_UPDATE_INTERVAL,
    WIND_DIRECTION_DEGREES,
)

_LOGGER = logging.getLogger(__name__)


def _safe_numeric(value: Any) -> float | int | None:
    """Return *value* only if it is a real number (int or float), else None.

    Rejects booleans, strings, and other non-numeric types that could slip
    through untyped JSON responses.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _map_condition(weather_type: int | None, is_night: bool = False) -> str | None:
    """Map a BBC weatherType code to a Home Assistant condition string."""
    if weather_type is None:
        return None
    condition = BBC_TO_HA_CONDITION.get(weather_type)
    # For daytime clear codes (1=Sunny), return sunny.
    # For night-time, override sunny -> clear-night.
    if condition == "sunny" and is_night:
        return "clear-night"
    # Code 0 already maps to clear-night; during day treat as sunny.
    if condition == "clear-night" and not is_night:
        return "sunny"
    return condition


def _wind_bearing(direction: str | None) -> float | None:
    """Convert a wind direction abbreviation to degrees."""
    if direction is None:
        return None
    return WIND_DIRECTION_DEGREES.get(direction.upper())


class BBCWeatherDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches forecast and observation data from BBC Weather."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: BBCWeatherAPI,
        location_id: str,
        location_name: str,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"BBC Weather {location_name}",
            update_interval=timedelta(seconds=FORECAST_UPDATE_INTERVAL),
        )
        self.api = api
        self.location_id = location_id
        self.location_name = location_name

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch forecast and observations in parallel."""
        forecast_result, observation_result = await asyncio.gather(
            self.api.get_forecast(self.location_id),
            self.api.get_observations(self.location_id),
            return_exceptions=True,
        )

        # Forecast is required — raise if it failed.
        if isinstance(forecast_result, Exception):
            raise UpdateFailed(
                f"Failed to fetch forecast for {self.location_name}: {forecast_result}"
            ) from forecast_result

        # Observations are optional — log and continue without them.
        observations: dict[str, Any] | None = None
        if isinstance(observation_result, Exception):
            _LOGGER.debug(
                "Failed to fetch observations for %s, using forecast data only: %s",
                self.location_name,
                observation_result,
            )
        else:
            observations = observation_result

        current = self._parse_current(forecast_result, observations)
        daily_forecast = self._parse_daily_forecast(forecast_result)
        hourly_forecast = self._parse_hourly_forecast(forecast_result)

        return {
            "current": current,
            "daily_forecast": daily_forecast,
            "hourly_forecast": hourly_forecast,
            "location": {
                "id": self.location_id,
                "name": self.location_name,
            },
        }

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_current(
        self,
        forecast: dict[str, Any],
        observations: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build current-conditions dict, preferring observations when available."""
        # Start with forecast data from the first hourly timeslot of today.
        fc = self._first_hourly_timeslot(forecast)

        is_night = bool(fc.get("isNight")) if fc else False

        current: dict[str, Any] = {
            "temperature": _safe_numeric(fc.get("temperatureC")) if fc else None,
            "feels_like_temperature": (
                _safe_numeric(fc.get("feelsLikeTemperatureC")) if fc else None
            ),
            "humidity": _safe_numeric(fc.get("humidity")) if fc else None,
            "pressure": _safe_numeric(fc.get("pressure")) if fc else None,
            "wind_speed": _safe_numeric(fc.get("windSpeedMph")) if fc else None,
            "wind_bearing": _wind_bearing(
                fc.get("windDirectionAbbreviation") if fc else None
            ),
            "wind_direction": fc.get("windDirectionAbbreviation") if fc else None,
            "visibility": fc.get("visibility") if fc else None,
            "condition": _map_condition(
                fc.get("weatherType") if fc else None, is_night
            ),
            "description": fc.get("weatherTypeText") if fc else None,
        }

        # Override with observation data where available.
        obs = self._latest_observation(observations)
        if obs is not None:
            obs_temp = obs.get("temperature")
            if isinstance(obs_temp, dict):
                current["temperature"] = _safe_numeric(obs_temp.get("C"))
            obs_hum = obs.get("humidity")
            if isinstance(obs_hum, dict):
                current["humidity"] = _safe_numeric(obs_hum.get("value"))
            obs_wind = obs.get("wind")
            if isinstance(obs_wind, dict):
                speed = _safe_numeric(obs_wind.get("speedMph"))
                if speed is not None:
                    current["wind_speed"] = speed
                if obs_wind.get("directionAbbreviation") is not None:
                    current["wind_direction"] = obs_wind[
                        "directionAbbreviation"
                    ]
                    current["wind_bearing"] = _wind_bearing(
                        obs_wind["directionAbbreviation"]
                    )
            obs_pres = obs.get("pressure")
            if isinstance(obs_pres, dict):
                val = _safe_numeric(obs_pres.get("mb"))
                if val is not None:
                    current["pressure"] = val
            if obs.get("visibility") is not None:
                current["visibility"] = obs["visibility"]

        return current

    def _parse_daily_forecast(
        self, forecast: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract up to 14 daily forecast summaries."""
        days: list[dict[str, Any]] = []
        for day in forecast.get("forecasts", []):
            summary = day.get("summary", {})
            report = summary.get("report", {})
            if not report:
                continue

            is_night = bool(report.get("isNight"))
            weather_type = report.get("weatherType")

            entry: dict[str, Any] = {
                "date": report.get("localDate"),
                "condition": _map_condition(weather_type, is_night),
                "temperature_high": _safe_numeric(report.get("maxTempC")),
                "temperature_low": _safe_numeric(report.get("minTempC")),
                "precipitation_probability": _safe_numeric(
                    report.get("precipitationProbabilityInPercent")
                ),
                "wind_speed": _safe_numeric(report.get("windSpeedMph")),
                "wind_bearing": _wind_bearing(
                    report.get("windDirectionAbbreviation")
                ),
                "wind_direction": report.get("windDirectionAbbreviation"),
                "uv_index": _safe_numeric(report.get("uvIndex")),
                "sunrise": report.get("sunrise"),
                "sunset": report.get("sunset"),
            }
            days.append(entry)
        return days

    def _parse_hourly_forecast(
        self, forecast: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract hourly forecasts from detailed reports."""
        hours: list[dict[str, Any]] = []
        for day in forecast.get("forecasts", []):
            for slot in day.get("detailed", {}).get("reports", []):
                local_date = slot.get("localDate")
                timeslot = slot.get("timeslot")
                dt = self._combine_date_time(local_date, timeslot)

                is_night = bool(slot.get("isNight"))
                weather_type = slot.get("weatherType")

                entry: dict[str, Any] = {
                    "datetime": dt,
                    "condition": _map_condition(weather_type, is_night),
                    "temperature": _safe_numeric(slot.get("temperatureC")),
                    "precipitation_probability": _safe_numeric(
                        slot.get("precipitationProbabilityInPercent")
                    ),
                    "wind_speed": _safe_numeric(slot.get("windSpeedMph")),
                    "wind_bearing": _wind_bearing(
                        slot.get("windDirectionAbbreviation")
                    ),
                    "humidity": _safe_numeric(slot.get("humidity")),
                    "pressure": _safe_numeric(slot.get("pressure")),
                }
                hours.append(entry)
        return hours

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _first_hourly_timeslot(
        forecast: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Return the first hourly report from today's forecast."""
        forecasts = forecast.get("forecasts", [])
        if not forecasts:
            return None
        reports = forecasts[0].get("detailed", {}).get("reports", [])
        return reports[0] if reports else None

    @staticmethod
    def _latest_observation(
        observations: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Return the most recent observation record, or None."""
        if observations is None:
            return None
        obs_list = observations.get("observations", [])
        if not obs_list:
            return None
        return obs_list[0]

    @staticmethod
    def _combine_date_time(
        local_date: str | None, timeslot: str | None
    ) -> str | None:
        """Combine a date string and timeslot into an ISO datetime string."""
        if local_date is None or timeslot is None:
            return None
        try:
            dt = datetime.strptime(f"{local_date} {timeslot}", "%Y-%m-%d %H:%M")
            return dt.isoformat()
        except (ValueError, TypeError):
            return None

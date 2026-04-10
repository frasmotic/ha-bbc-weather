"""Tests for the BBC Weather entity."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.bbc_weather.const import VISIBILITY_KM
from custom_components.bbc_weather.coordinator import (
    BBCWeatherDataCoordinator,
    _map_condition,
    _wind_bearing,
)
from custom_components.bbc_weather.weather import BBCWeatherEntity

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity(data, location_id="2643743", location_name="London"):
    """Create a BBCWeatherEntity backed by a mock coordinator."""
    coordinator = MagicMock(spec=BBCWeatherDataCoordinator)
    coordinator.data = data
    coordinator.location_id = location_id
    coordinator.location_name = location_name
    return BBCWeatherEntity(coordinator)


# ---------------------------------------------------------------------------
# Current conditions
# ---------------------------------------------------------------------------


class TestEntityProperties:
    """Test weather entity current-condition properties."""

    def test_temperature(self, coordinator_data):
        entity = _make_entity(coordinator_data)
        assert entity.native_temperature == 17

    def test_apparent_temperature(self, coordinator_data):
        entity = _make_entity(coordinator_data)
        assert entity.native_apparent_temperature == 13

    def test_humidity(self, coordinator_data):
        entity = _make_entity(coordinator_data)
        assert entity.humidity == 68

    def test_pressure(self, coordinator_data):
        entity = _make_entity(coordinator_data)
        assert entity.native_pressure == 1015

    def test_wind_speed(self, coordinator_data):
        entity = _make_entity(coordinator_data)
        assert entity.native_wind_speed == 9

    def test_wind_bearing(self, coordinator_data):
        entity = _make_entity(coordinator_data)
        assert entity.wind_bearing == 247.5

    def test_condition(self, coordinator_data):
        entity = _make_entity(coordinator_data)
        assert entity.condition == "sunny"

    def test_visibility_good(self, coordinator_data):
        entity = _make_entity(coordinator_data)
        assert entity.native_visibility == 10  # "Good" -> 10 km

    def test_unique_id(self, coordinator_data):
        entity = _make_entity(coordinator_data, location_id="2643743")
        assert entity.unique_id == "bbc_weather_2643743"

    def test_attribution(self, coordinator_data):
        entity = _make_entity(coordinator_data)
        assert entity.attribution == "Data provided by BBC Weather"


# ---------------------------------------------------------------------------
# Missing / None data
# ---------------------------------------------------------------------------


class TestMissingData:
    """Test graceful handling when data is missing or None."""

    def test_none_coordinator_data(self):
        """All properties return None when coordinator.data is None."""
        entity = _make_entity(None)
        assert entity.native_temperature is None
        assert entity.native_apparent_temperature is None
        assert entity.humidity is None
        assert entity.native_pressure is None
        assert entity.native_wind_speed is None
        assert entity.wind_bearing is None
        assert entity.native_visibility is None
        assert entity.condition is None

    def test_empty_current(self):
        """Properties return None when current dict is empty."""
        entity = _make_entity({
            "current": {},
            "daily_forecast": [],
            "hourly_forecast": [],
            "location": {"id": "1", "name": "Test"},
        })
        assert entity.native_temperature is None
        assert entity.condition is None

    async def test_daily_forecast_none_data(self):
        """Daily forecast returns None when coordinator.data is None."""
        entity = _make_entity(None)
        assert await entity.async_forecast_daily() is None

    async def test_hourly_forecast_none_data(self):
        """Hourly forecast returns None when coordinator.data is None."""
        entity = _make_entity(None)
        assert await entity.async_forecast_hourly() is None

    async def test_daily_forecast_empty_list(self):
        """Daily forecast returns None when list is empty."""
        entity = _make_entity({
            "current": {},
            "daily_forecast": [],
            "hourly_forecast": [],
            "location": {"id": "1", "name": "Test"},
        })
        assert await entity.async_forecast_daily() is None


# ---------------------------------------------------------------------------
# Forecasts
# ---------------------------------------------------------------------------


class TestForecasts:
    """Test daily and hourly forecast methods."""

    async def test_daily_forecast_count_and_conditions(self, coordinator_data):
        entity = _make_entity(coordinator_data)
        daily = await entity.async_forecast_daily()

        assert daily is not None
        assert len(daily) == 2

        day1 = daily[0]
        assert day1["datetime"] == "2024-06-15"
        assert day1["condition"] == "partlycloudy"
        assert day1["native_temperature"] == 22
        assert day1["native_templow"] == 14
        assert day1["precipitation_probability"] == 10
        assert day1["native_wind_speed"] == 12
        assert day1["wind_bearing"] == 225.0

        day2 = daily[1]
        assert day2["condition"] == "cloudy"
        assert day2["native_temperature"] == 19

    async def test_hourly_forecast_structure(self, coordinator_data):
        entity = _make_entity(coordinator_data)
        hourly = await entity.async_forecast_hourly()

        assert hourly is not None
        assert len(hourly) == 3

        hour1 = hourly[0]
        assert hour1["datetime"] == "2024-06-15T06:00:00"
        assert hour1["condition"] == "sunny"
        assert hour1["native_temperature"] == 15
        assert hour1["precipitation_probability"] == 5
        assert hour1["native_wind_speed"] == 8
        assert hour1["humidity"] == 72


# ---------------------------------------------------------------------------
# Night condition mapping
# ---------------------------------------------------------------------------


class TestNightConditionMapping:
    """Test clear-night vs sunny based on isNight flag."""

    def test_night_entity_condition(self, coordinator_data_night):
        entity = _make_entity(coordinator_data_night)
        assert entity.condition == "clear-night"

    def test_map_condition_sunny_daytime(self):
        """Code 1 (Sunny) during day returns 'sunny'."""
        assert _map_condition(1, is_night=False) == "sunny"

    def test_map_condition_sunny_nighttime(self):
        """Code 1 (Sunny) at night returns 'clear-night'."""
        assert _map_condition(1, is_night=True) == "clear-night"

    def test_map_condition_clear_sky_night(self):
        """Code 0 (Clear Sky) at night returns 'clear-night'."""
        assert _map_condition(0, is_night=True) == "clear-night"

    def test_map_condition_clear_sky_day(self):
        """Code 0 (Clear Sky) during day returns 'sunny'."""
        assert _map_condition(0, is_night=False) == "sunny"

    def test_map_condition_none_returns_none(self):
        assert _map_condition(None) is None

    def test_map_condition_unknown_code_returns_none(self):
        """Unknown weather type code returns None."""
        assert _map_condition(99) is None

    def test_map_condition_non_clear_unaffected_by_night(self):
        """Non-clear codes are unaffected by isNight flag."""
        assert _map_condition(7, is_night=False) == "cloudy"
        assert _map_condition(7, is_night=True) == "cloudy"
        assert _map_condition(14, is_night=True) == "pouring"
        assert _map_condition(22, is_night=True) == "snowy"


# ---------------------------------------------------------------------------
# Visibility text → km conversion
# ---------------------------------------------------------------------------


class TestVisibilityConversion:
    """Test BBC visibility descriptions mapped to km values."""

    @pytest.mark.parametrize(
        "text,expected_km",
        [
            ("Very Good", 20),
            ("Good", 10),
            ("Moderate", 5),
            ("Poor", 2),
            ("Very Poor", 1),
            ("Fog", 0.1),
        ],
    )
    def test_visibility_mapping(self, text, expected_km):
        data = {
            "current": {"visibility": text},
            "daily_forecast": [],
            "hourly_forecast": [],
            "location": {"id": "1", "name": "Test"},
        }
        entity = _make_entity(data)
        assert entity.native_visibility == expected_km

    def test_visibility_unknown_text_returns_none(self):
        data = {
            "current": {"visibility": "Excellent"},
            "daily_forecast": [],
            "hourly_forecast": [],
            "location": {"id": "1", "name": "Test"},
        }
        entity = _make_entity(data)
        assert entity.native_visibility is None

    def test_visibility_none_returns_none(self):
        data = {
            "current": {"visibility": None},
            "daily_forecast": [],
            "hourly_forecast": [],
            "location": {"id": "1", "name": "Test"},
        }
        entity = _make_entity(data)
        assert entity.native_visibility is None

    def test_visibility_dict_covers_all_expected_values(self):
        """Verify the VISIBILITY_KM dict has all expected BBC strings."""
        expected_keys = {"Very Good", "Good", "Moderate", "Poor", "Very Poor", "Fog"}
        assert set(VISIBILITY_KM.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Wind direction abbreviation → degrees
# ---------------------------------------------------------------------------


class TestWindDirectionConversion:
    """Test all 16 compass point abbreviations to degree values."""

    @pytest.mark.parametrize(
        "abbr,degrees",
        [
            ("N", 0),
            ("NNE", 22.5),
            ("NE", 45),
            ("ENE", 67.5),
            ("E", 90),
            ("ESE", 112.5),
            ("SE", 135),
            ("SSE", 157.5),
            ("S", 180),
            ("SSW", 202.5),
            ("SW", 225),
            ("WSW", 247.5),
            ("W", 270),
            ("WNW", 292.5),
            ("NW", 315),
            ("NNW", 337.5),
        ],
    )
    def test_compass_to_degrees(self, abbr, degrees):
        assert _wind_bearing(abbr) == degrees

    def test_case_insensitive(self):
        assert _wind_bearing("sw") == 225
        assert _wind_bearing("Nne") == 22.5

    def test_none_returns_none(self):
        assert _wind_bearing(None) is None

    def test_unknown_abbreviation_returns_none(self):
        assert _wind_bearing("XYZ") is None


# ---------------------------------------------------------------------------
# Observation fallback
# ---------------------------------------------------------------------------


class TestObservationFallback:
    """Test that forecast data is used when observations are absent."""

    def test_forecast_only_current_conditions(self):
        """When no observation overlay, forecast values are used directly."""
        data = {
            "current": {
                "temperature": 15,
                "feels_like_temperature": 13,
                "humidity": 72,
                "pressure": 1013,
                "wind_speed": 8,
                "wind_bearing": 225.0,
                "wind_direction": "SW",
                "visibility": "Good",
                "condition": "sunny",
                "description": "Sunny",
            },
            "daily_forecast": [],
            "hourly_forecast": [],
            "location": {"id": "2643743", "name": "London"},
        }
        entity = _make_entity(data)

        assert entity.native_temperature == 15
        assert entity.native_apparent_temperature == 13
        assert entity.humidity == 72
        assert entity.native_pressure == 1013
        assert entity.native_wind_speed == 8
        assert entity.wind_bearing == 225.0
        assert entity.native_visibility == 10
        assert entity.condition == "sunny"

    def test_observation_overrides_forecast(self, coordinator_data):
        """Observation data overlays forecast data for current conditions."""
        entity = _make_entity(coordinator_data)
        # coordinator_data fixture has observation overrides:
        # obs temp=17 vs forecast temp=15, obs humidity=68 vs forecast=72
        assert entity.native_temperature == 17
        assert entity.humidity == 68
        assert entity.native_pressure == 1015
        assert entity.native_wind_speed == 9
        assert entity.wind_bearing == 247.5  # WSW from observation

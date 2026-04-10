"""Tests for the BBC Weather data coordinator parsing logic."""

from __future__ import annotations

import pytest

from custom_components.bbc_weather.coordinator import (
    BBCWeatherDataCoordinator,
    _safe_numeric,
)


# ---------------------------------------------------------------------------
# Helpers — instantiate coordinator without __init__ for parse-only testing
# ---------------------------------------------------------------------------


def _make_coordinator() -> BBCWeatherDataCoordinator:
    """Create a coordinator instance without calling __init__."""
    return BBCWeatherDataCoordinator.__new__(BBCWeatherDataCoordinator)


# ---------------------------------------------------------------------------
# _safe_numeric
# ---------------------------------------------------------------------------


class TestSafeNumeric:
    """Test the _safe_numeric helper."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            (42, 42),
            (3.14, 3.14),
            (0, 0),
            (0.0, 0.0),
            (-5, -5),
            (-2.7, -2.7),
        ],
    )
    def test_valid_numbers(self, value, expected):
        assert _safe_numeric(value) == expected

    @pytest.mark.parametrize(
        "value",
        [True, False],
    )
    def test_booleans_rejected(self, value):
        assert _safe_numeric(value) is None

    @pytest.mark.parametrize(
        "value",
        ["42", "hello", "", None, {}, [], {"C": 17}],
    )
    def test_non_numeric_rejected(self, value):
        assert _safe_numeric(value) is None


# ---------------------------------------------------------------------------
# Static helpers
# ---------------------------------------------------------------------------


class TestFirstHourlyTimeslot:
    """Test _first_hourly_timeslot extraction."""

    def test_returns_first_report(self, forecast_response):
        coord = _make_coordinator()
        slot = coord._first_hourly_timeslot(forecast_response)
        assert slot is not None
        assert slot["timeslot"] == "06:00"
        assert slot["temperatureC"] == 15

    def test_empty_forecasts(self):
        coord = _make_coordinator()
        assert coord._first_hourly_timeslot({"forecasts": []}) is None

    def test_missing_forecasts_key(self):
        coord = _make_coordinator()
        assert coord._first_hourly_timeslot({}) is None

    def test_empty_reports(self):
        coord = _make_coordinator()
        data = {"forecasts": [{"detailed": {"reports": []}}]}
        assert coord._first_hourly_timeslot(data) is None


class TestLatestObservation:
    """Test _latest_observation extraction."""

    def test_returns_first_observation(self, observation_response):
        coord = _make_coordinator()
        obs = coord._latest_observation(observation_response)
        assert obs is not None
        assert obs["temperature"]["C"] == 17

    def test_none_observations(self):
        coord = _make_coordinator()
        assert coord._latest_observation(None) is None

    def test_empty_observations(self, observation_response_empty):
        coord = _make_coordinator()
        assert coord._latest_observation(observation_response_empty) is None


class TestCombineDateTime:
    """Test _combine_date_time ISO datetime construction."""

    def test_valid_date_and_time(self):
        coord = _make_coordinator()
        assert coord._combine_date_time("2024-06-15", "09:00") == "2024-06-15T09:00:00"

    def test_none_date(self):
        coord = _make_coordinator()
        assert coord._combine_date_time(None, "09:00") is None

    def test_none_time(self):
        coord = _make_coordinator()
        assert coord._combine_date_time("2024-06-15", None) is None

    def test_invalid_format(self):
        coord = _make_coordinator()
        assert coord._combine_date_time("not-a-date", "not-a-time") is None


# ---------------------------------------------------------------------------
# _parse_current
# ---------------------------------------------------------------------------


class TestParseCurrent:
    """Test current conditions parsing."""

    def test_forecast_only(self, forecast_response):
        """Current conditions from forecast when no observations."""
        coord = _make_coordinator()
        current = coord._parse_current(forecast_response, None)

        assert current["temperature"] == 15
        assert current["feels_like_temperature"] == 13
        assert current["humidity"] == 72
        assert current["pressure"] == 1013
        assert current["wind_speed"] == 8
        assert current["wind_bearing"] == 225.0
        assert current["visibility"] == "Good"
        assert current["condition"] == "sunny"

    def test_observations_override(self, forecast_response, observation_response):
        """Observation data overrides forecast for current conditions."""
        coord = _make_coordinator()
        current = coord._parse_current(forecast_response, observation_response)

        # These should come from observation
        assert current["temperature"] == 17
        assert current["humidity"] == 68
        assert current["pressure"] == 1015
        assert current["wind_speed"] == 9
        assert current["wind_direction"] == "WSW"
        assert current["visibility"] == "Good"

    def test_empty_forecast(self):
        """Gracefully handles empty forecast data."""
        coord = _make_coordinator()
        current = coord._parse_current({"forecasts": []}, None)

        assert current["temperature"] is None
        assert current["condition"] is None

    def test_scalar_observation_fields_ignored(self, forecast_response):
        """Scalar (non-dict) observation sub-fields are safely ignored."""
        coord = _make_coordinator()
        obs = {
            "observations": [
                {
                    "temperature": 17,  # scalar, not dict — should be ignored
                    "humidity": 68,  # scalar, not dict — should be ignored
                    "wind": "strong",  # string, not dict — should be ignored
                    "pressure": 1015,  # scalar, not dict — should be ignored
                }
            ]
        }
        current = coord._parse_current(forecast_response, obs)

        # Should fall back to forecast values since obs fields aren't dicts
        assert current["temperature"] == 15
        assert current["humidity"] == 72
        assert current["pressure"] == 1013
        assert current["wind_speed"] == 8

    def test_night_condition(self, forecast_response_night):
        """Night-time forecast produces clear-night condition."""
        coord = _make_coordinator()
        current = coord._parse_current(forecast_response_night, None)
        assert current["condition"] == "clear-night"


# ---------------------------------------------------------------------------
# _parse_daily_forecast
# ---------------------------------------------------------------------------


class TestParseDailyForecast:
    """Test daily forecast parsing."""

    def test_two_days(self, forecast_response):
        coord = _make_coordinator()
        days = coord._parse_daily_forecast(forecast_response)

        assert len(days) == 2

        day1 = days[0]
        assert day1["date"] == "2024-06-15"
        assert day1["condition"] == "partlycloudy"
        assert day1["temperature_high"] == 22
        assert day1["temperature_low"] == 14
        assert day1["precipitation_probability"] == 10
        assert day1["wind_speed"] == 12
        assert day1["wind_bearing"] == 225.0
        assert day1["uv_index"] == 6

        day2 = days[1]
        assert day2["date"] == "2024-06-16"
        assert day2["condition"] == "cloudy"

    def test_empty_forecasts(self):
        coord = _make_coordinator()
        assert coord._parse_daily_forecast({"forecasts": []}) == []

    def test_missing_report_skipped(self):
        """Days with empty report dicts are skipped."""
        coord = _make_coordinator()
        data = {
            "forecasts": [
                {"summary": {"report": {}}},
                {"summary": {}},
            ]
        }
        assert coord._parse_daily_forecast(data) == []


# ---------------------------------------------------------------------------
# _parse_hourly_forecast
# ---------------------------------------------------------------------------


class TestParseHourlyForecast:
    """Test hourly forecast parsing."""

    def test_hourly_slots(self, forecast_response):
        coord = _make_coordinator()
        hours = coord._parse_hourly_forecast(forecast_response)

        # 2 slots from day 1 + 1 slot from day 2
        assert len(hours) == 3

        hour1 = hours[0]
        assert hour1["datetime"] == "2024-06-15T06:00:00"
        assert hour1["condition"] == "sunny"
        assert hour1["temperature"] == 15
        assert hour1["precipitation_probability"] == 5
        assert hour1["wind_speed"] == 8
        assert hour1["humidity"] == 72
        assert hour1["pressure"] == 1013

    def test_empty_forecasts(self):
        coord = _make_coordinator()
        assert coord._parse_hourly_forecast({"forecasts": []}) == []

    def test_night_condition_in_hourly(self, forecast_response_night):
        coord = _make_coordinator()
        hours = coord._parse_hourly_forecast(forecast_response_night)
        assert len(hours) == 1
        assert hours[0]["condition"] == "clear-night"

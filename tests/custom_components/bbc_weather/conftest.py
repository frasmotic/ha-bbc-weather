"""Shared fixtures for BBC Weather tests."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def verify_cleanup(
    event_loop: asyncio.AbstractEventLoop,
    expected_lingering_tasks: bool,
    expected_lingering_timers: bool,
) -> Generator[None]:
    """Override the default verify_cleanup to allow HA's _run_safe_shutdown_loop thread.

    The default fixture from pytest-homeassistant-custom-component fails when
    HA core starts its safe-shutdown thread during integration setup. This is
    not caused by our integration and cannot be prevented.
    """
    threads_before = frozenset(threading.enumerate())
    yield

    # Check for unexpected threads, but allow _run_safe_shutdown_loop
    threads = frozenset(threading.enumerate()) - threads_before
    for thread in threads:
        assert (
            isinstance(thread, threading._DummyThread)
            or thread.name.startswith("waitpid-")
            or "_run_safe_shutdown_loop" in thread.name
        )

# ---------------------------------------------------------------------------
# Parsed location dicts (as returned by config_flow._search_locations)
# ---------------------------------------------------------------------------

PARSED_LOCATION_LONDON = {
    "id": "2643743",
    "name": "London",
    "container": "Greater London",
    "country": "United Kingdom",
    "latitude": 51.50853,
    "longitude": -0.12574,
}

PARSED_LOCATION_LONDON_OHIO = {
    "id": "4517009",
    "name": "London",
    "container": "Ohio",
    "country": "United States",
    "latitude": 39.88645,
    "longitude": -83.44825,
}

PARSED_LOCATION_MANCHESTER = {
    "id": "2643123",
    "name": "Manchester",
    "container": "Greater Manchester",
    "country": "United Kingdom",
    "latitude": 53.48095,
    "longitude": -2.23743,
}


# ---------------------------------------------------------------------------
# Enable custom integrations for all tests in this directory
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    yield


# ---------------------------------------------------------------------------
# BBC API raw response fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def search_response_single():
    """BBC location search returning one result."""
    return {
        "response": {
            "results": {
                "results": [
                    {
                        "id": 2643743,
                        "name": "London",
                        "container": "Greater London",
                        "country": "United Kingdom",
                        "latitude": 51.50853,
                        "longitude": -0.12574,
                    }
                ]
            }
        }
    }


@pytest.fixture
def search_response_multiple():
    """BBC location search returning two results."""
    return {
        "response": {
            "results": {
                "results": [
                    {
                        "id": 2643743,
                        "name": "London",
                        "container": "Greater London",
                        "country": "United Kingdom",
                        "latitude": 51.50853,
                        "longitude": -0.12574,
                    },
                    {
                        "id": 4517009,
                        "name": "London",
                        "container": "Ohio",
                        "country": "United States",
                        "latitude": 39.88645,
                        "longitude": -83.44825,
                    },
                ]
            }
        }
    }


@pytest.fixture
def search_response_empty():
    """BBC location search returning no results."""
    return {"response": {"results": {"results": []}}}


@pytest.fixture
def forecast_response():
    """Realistic BBC aggregated forecast with 2 days, each with hourly detail."""
    return {
        "forecasts": [
            {
                "summary": {
                    "report": {
                        "localDate": "2024-06-15",
                        "weatherType": 3,
                        "weatherTypeText": "Sunny Intervals",
                        "maxTempC": 22,
                        "minTempC": 14,
                        "precipitationProbabilityInPercent": 10,
                        "windSpeedMph": 12,
                        "windDirectionAbbreviation": "SW",
                        "uvIndex": 6,
                        "sunrise": "04:42",
                        "sunset": "21:10",
                        "isNight": False,
                    }
                },
                "detailed": {
                    "reports": [
                        {
                            "localDate": "2024-06-15",
                            "timeslot": "06:00",
                            "temperatureC": 15,
                            "feelsLikeTemperatureC": 13,
                            "weatherType": 1,
                            "weatherTypeText": "Sunny",
                            "humidity": 72,
                            "pressure": 1013,
                            "windSpeedMph": 8,
                            "windDirectionAbbreviation": "SW",
                            "precipitationProbabilityInPercent": 5,
                            "visibility": "Good",
                            "isNight": False,
                        },
                        {
                            "localDate": "2024-06-15",
                            "timeslot": "09:00",
                            "temperatureC": 18,
                            "feelsLikeTemperatureC": 16,
                            "weatherType": 3,
                            "weatherTypeText": "Sunny Intervals",
                            "humidity": 65,
                            "pressure": 1014,
                            "windSpeedMph": 10,
                            "windDirectionAbbreviation": "SW",
                            "precipitationProbabilityInPercent": 10,
                            "visibility": "Very Good",
                            "isNight": False,
                        },
                    ]
                },
            },
            {
                "summary": {
                    "report": {
                        "localDate": "2024-06-16",
                        "weatherType": 7,
                        "weatherTypeText": "Cloudy",
                        "maxTempC": 19,
                        "minTempC": 12,
                        "precipitationProbabilityInPercent": 30,
                        "windSpeedMph": 15,
                        "windDirectionAbbreviation": "W",
                        "uvIndex": 4,
                        "sunrise": "04:42",
                        "sunset": "21:10",
                        "isNight": False,
                    }
                },
                "detailed": {
                    "reports": [
                        {
                            "localDate": "2024-06-16",
                            "timeslot": "06:00",
                            "temperatureC": 13,
                            "feelsLikeTemperatureC": 11,
                            "weatherType": 7,
                            "weatherTypeText": "Cloudy",
                            "humidity": 80,
                            "pressure": 1010,
                            "windSpeedMph": 14,
                            "windDirectionAbbreviation": "W",
                            "precipitationProbabilityInPercent": 25,
                            "visibility": "Moderate",
                            "isNight": False,
                        }
                    ]
                },
            },
        ]
    }


@pytest.fixture
def forecast_response_night():
    """Forecast with night-time data for clear-night condition testing."""
    return {
        "forecasts": [
            {
                "summary": {
                    "report": {
                        "localDate": "2024-06-15",
                        "weatherType": 0,
                        "weatherTypeText": "Clear Sky",
                        "maxTempC": 22,
                        "minTempC": 14,
                        "precipitationProbabilityInPercent": 0,
                        "windSpeedMph": 5,
                        "windDirectionAbbreviation": "N",
                        "uvIndex": 0,
                        "sunrise": "04:42",
                        "sunset": "21:10",
                        "isNight": True,
                    }
                },
                "detailed": {
                    "reports": [
                        {
                            "localDate": "2024-06-15",
                            "timeslot": "23:00",
                            "temperatureC": 14,
                            "feelsLikeTemperatureC": 12,
                            "weatherType": 0,
                            "weatherTypeText": "Clear Sky",
                            "humidity": 85,
                            "pressure": 1015,
                            "windSpeedMph": 5,
                            "windDirectionAbbreviation": "N",
                            "precipitationProbabilityInPercent": 0,
                            "visibility": "Very Good",
                            "isNight": True,
                        }
                    ]
                },
            }
        ]
    }


@pytest.fixture
def observation_response():
    """Realistic BBC observation response with one observation."""
    return {
        "station": {
            "name": "London Weather Centre",
            "latitude": 51.5,
            "longitude": -0.1,
        },
        "observations": [
            {
                "temperature": {"C": 17, "F": 63},
                "humidity": {"value": 68},
                "wind": {
                    "speedMph": 9,
                    "speedKph": 14,
                    "directionAbbreviation": "WSW",
                    "directionFull": "West South Westerly",
                },
                "pressure": {"mb": 1015, "direction": "Rising"},
                "visibility": "Good",
                "updateTimestamp": "2024-06-15T12:00:00.000Z",
            }
        ],
    }


@pytest.fixture
def observation_response_empty():
    """Observation response with no observation records."""
    return {"station": {"name": "Remote Station"}, "observations": []}


# ---------------------------------------------------------------------------
# Pre-parsed coordinator data fixtures (what weather.py consumes)
# ---------------------------------------------------------------------------


@pytest.fixture
def coordinator_data():
    """Coordinator data with observations merged into current conditions."""
    return {
        "current": {
            "temperature": 17,
            "feels_like_temperature": 13,
            "humidity": 68,
            "pressure": 1015,
            "wind_speed": 9,
            "wind_bearing": 247.5,
            "wind_direction": "WSW",
            "visibility": "Good",
            "condition": "sunny",
            "description": "Sunny",
        },
        "daily_forecast": [
            {
                "date": "2024-06-15",
                "condition": "partlycloudy",
                "temperature_high": 22,
                "temperature_low": 14,
                "precipitation_probability": 10,
                "wind_speed": 12,
                "wind_bearing": 225.0,
                "wind_direction": "SW",
                "uv_index": 6,
                "sunrise": "04:42",
                "sunset": "21:10",
            },
            {
                "date": "2024-06-16",
                "condition": "cloudy",
                "temperature_high": 19,
                "temperature_low": 12,
                "precipitation_probability": 30,
                "wind_speed": 15,
                "wind_bearing": 270.0,
                "wind_direction": "W",
                "uv_index": 4,
                "sunrise": "04:42",
                "sunset": "21:10",
            },
        ],
        "hourly_forecast": [
            {
                "datetime": "2024-06-15T06:00:00",
                "condition": "sunny",
                "temperature": 15,
                "precipitation_probability": 5,
                "wind_speed": 8,
                "wind_bearing": 225.0,
                "humidity": 72,
                "pressure": 1013,
            },
            {
                "datetime": "2024-06-15T09:00:00",
                "condition": "partlycloudy",
                "temperature": 18,
                "precipitation_probability": 10,
                "wind_speed": 10,
                "wind_bearing": 225.0,
                "humidity": 65,
                "pressure": 1014,
            },
            {
                "datetime": "2024-06-16T06:00:00",
                "condition": "cloudy",
                "temperature": 13,
                "precipitation_probability": 25,
                "wind_speed": 14,
                "wind_bearing": 270.0,
                "humidity": 80,
                "pressure": 1010,
            },
        ],
        "location": {
            "id": "2643743",
            "name": "London, Greater London, United Kingdom",
        },
    }


@pytest.fixture
def coordinator_data_night():
    """Coordinator data with night-time clear-night condition."""
    return {
        "current": {
            "temperature": 14,
            "feels_like_temperature": 12,
            "humidity": 85,
            "pressure": 1015,
            "wind_speed": 5,
            "wind_bearing": 0.0,
            "wind_direction": "N",
            "visibility": "Very Good",
            "condition": "clear-night",
            "description": "Clear Sky",
        },
        "daily_forecast": [
            {
                "date": "2024-06-15",
                "condition": "clear-night",
                "temperature_high": 22,
                "temperature_low": 14,
                "precipitation_probability": 0,
                "wind_speed": 5,
                "wind_bearing": 0.0,
                "wind_direction": "N",
                "uv_index": 0,
                "sunrise": "04:42",
                "sunset": "21:10",
            },
        ],
        "hourly_forecast": [
            {
                "datetime": "2024-06-15T23:00:00",
                "condition": "clear-night",
                "temperature": 14,
                "precipitation_probability": 0,
                "wind_speed": 5,
                "wind_bearing": 0.0,
                "humidity": 85,
                "pressure": 1015,
            },
        ],
        "location": {
            "id": "2643743",
            "name": "London, Greater London, United Kingdom",
        },
    }

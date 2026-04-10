"""Tests for BBC Weather config flow and options flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bbc_weather.const import DOMAIN

from .conftest import (
    PARSED_LOCATION_LONDON,
    PARSED_LOCATION_LONDON_OHIO,
    PARSED_LOCATION_MANCHESTER,
)

MODULE = "custom_components.bbc_weather.config_flow"


@pytest.fixture
def mock_setup_entry():
    """Prevent async_setup_entry from running during config flow tests."""
    with patch(
        "custom_components.bbc_weather.async_setup_entry", return_value=True
    ) as mock:
        yield mock


# ---------------------------------------------------------------------------
# Config flow tests
# ---------------------------------------------------------------------------


@patch(f"{MODULE}._validate_forecast", return_value=True)
@patch(f"{MODULE}._search_locations")
async def test_single_result_completes_immediately(
    mock_search, mock_validate, hass: HomeAssistant, mock_setup_entry
):
    """Single search result skips selection and creates entry."""
    mock_search.return_value = [PARSED_LOCATION_LONDON]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"location_1": "London", "location_2": "", "api_key": ""},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "London, Greater London, United Kingdom"
    locations = result["data"]["locations"]
    assert len(locations) == 1
    assert locations[0]["id"] == "2643743"
    assert locations[0]["latitude"] == 51.50853


@patch(f"{MODULE}._validate_forecast", return_value=True)
@patch(f"{MODULE}._search_locations")
async def test_multiple_results_shows_selection(
    mock_search, mock_validate, hass: HomeAssistant, mock_setup_entry
):
    """Multiple results show a selection dropdown."""
    mock_search.return_value = [PARSED_LOCATION_LONDON, PARSED_LOCATION_LONDON_OHIO]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"location_1": "London", "location_2": "", "api_key": ""},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_locations"

    # Select the UK London
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"location_1": "2643743"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["locations"][0]["id"] == "2643743"


@patch(f"{MODULE}._search_locations", return_value=[])
async def test_location_not_found_shows_error(mock_search, hass: HomeAssistant):
    """Empty search results show a location_not_found error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"location_1": "xyznonexistent", "location_2": "", "api_key": ""},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"location_1": "location_not_found"}


@patch(f"{MODULE}._validate_forecast", return_value=True)
@patch(f"{MODULE}._search_locations")
async def test_two_locations(
    mock_search, mock_validate, hass: HomeAssistant, mock_setup_entry
):
    """Both location fields filled creates entry with two locations."""

    async def _search_side_effect(_api, query):
        if "London" in query:
            return [PARSED_LOCATION_LONDON]
        if "Manchester" in query:
            return [PARSED_LOCATION_MANCHESTER]
        return []

    mock_search.side_effect = _search_side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"location_1": "London", "location_2": "Manchester", "api_key": ""},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    locations = result["data"]["locations"]
    assert len(locations) == 2
    assert locations[0]["id"] == "2643743"
    assert locations[1]["id"] == "2643123"


async def test_single_instance_rejected(hass: HomeAssistant):
    """A second config entry is rejected when one already exists."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={
            "locations": [
                {
                    "id": "2643743",
                    "name": "London, Greater London, United Kingdom",
                    "latitude": 51.50853,
                    "longitude": -0.12574,
                }
            ]
        },
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


# ---------------------------------------------------------------------------
# Options flow tests
# ---------------------------------------------------------------------------


@patch(f"{MODULE}._validate_forecast", return_value=True)
@patch(f"{MODULE}._search_locations")
async def test_options_flow_updates_locations(
    mock_search, mock_validate, hass: HomeAssistant
):
    """Options flow updates entry data and triggers reload."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "locations": [
                {
                    "id": "2643743",
                    "name": "London, Greater London, United Kingdom",
                    "latitude": 51.50853,
                    "longitude": -0.12574,
                }
            ]
        },
    )
    entry.add_to_hass(hass)

    mock_search.return_value = [PARSED_LOCATION_MANCHESTER]

    # Patch reload so it doesn't try to actually set up the integration.
    with patch.object(hass.config_entries, "async_reload"):
        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"location_1": "Manchester", "location_2": "", "api_key": ""},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Verify entry data was updated to the new location.
    updated_locations = entry.data["locations"]
    assert len(updated_locations) == 1
    assert updated_locations[0]["id"] == "2643123"
    assert updated_locations[0]["name"] == "Manchester, Greater Manchester, United Kingdom"


@patch(f"{MODULE}._search_locations", return_value=[])
async def test_options_flow_not_found_shows_error(mock_search, hass: HomeAssistant):
    """Options flow shows error when location not found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "locations": [
                {
                    "id": "2643743",
                    "name": "London, Greater London, United Kingdom",
                    "latitude": 51.50853,
                    "longitude": -0.12574,
                }
            ]
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"location_1": "xyznonexistent", "location_2": "", "api_key": ""},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"location_1": "location_not_found"}

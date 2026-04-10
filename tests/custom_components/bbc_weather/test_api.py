"""Tests for the BBC Weather API client."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientResponseError, ClientSession

from custom_components.bbc_weather.api import BBCWeatherAPI, BBCWeatherAPIError
from custom_components.bbc_weather.const import MAX_RESPONSE_SIZE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockStreamReader:
    """Minimal mock of aiohttp StreamReader (resp.content)."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    async def read(self, n: int = -1) -> bytes:
        if n < 0:
            return self._data
        return self._data[:n]


class MockResponse:
    """Minimal mock of an aiohttp ClientResponse."""

    def __init__(self, json_data=None, raise_error=None, body: bytes | None = None):
        self._raise_error = raise_error
        if body is not None:
            self._body = body
        elif json_data is not None:
            self._body = json.dumps(json_data).encode()
        else:
            self._body = b""
        self.content = MockStreamReader(self._body)

    def raise_for_status(self):
        if self._raise_error:
            raise self._raise_error


class MockContextManager:
    """Async context manager wrapping a MockResponse."""

    def __init__(self, response=None, enter_error=None):
        self._response = response
        self._enter_error = enter_error

    async def __aenter__(self):
        if self._enter_error:
            raise self._enter_error
        return self._response

    async def __aexit__(self, *args):
        return False


def _ok(json_data):
    """Return a context manager yielding a successful response."""
    return MockContextManager(response=MockResponse(json_data=json_data))


def _server_error():
    """Return a context manager whose response raises a 500 error."""
    err = ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=500,
        message="Internal Server Error",
    )
    return MockContextManager(response=MockResponse(raise_error=err))


def _timeout():
    """Return a context manager that raises TimeoutError on enter."""
    return MockContextManager(enter_error=asyncio.TimeoutError())


def _oversized_response():
    """Return a context manager yielding a response exceeding MAX_RESPONSE_SIZE."""
    body = b"x" * (MAX_RESPONSE_SIZE + 1)
    return MockContextManager(response=MockResponse(body=body))


def _bad_json_response():
    """Return a context manager yielding a response with invalid JSON."""
    body = b"not valid json {{"
    return MockContextManager(response=MockResponse(body=body))


def _non_dict_response():
    """Return a context manager yielding a valid JSON list (not a dict)."""
    body = b'[1, 2, 3]'
    return MockContextManager(response=MockResponse(body=body))


def _make_session(*side_effects):
    """Create a MagicMock ClientSession with ordered get() responses."""
    session = MagicMock(spec=ClientSession)
    if len(side_effects) == 1:
        session.get.return_value = side_effects[0]
    else:
        session.get.side_effect = list(side_effects)
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_search_location(search_response_single):
    """Test search_location returns parsed JSON dict."""
    session = _make_session(_ok(search_response_single))
    api = BBCWeatherAPI(session)

    result = await api.search_location("London")

    assert result is not None
    results = result["response"]["results"]["results"]
    assert len(results) == 1
    assert results[0]["name"] == "London"


async def test_search_location_url_encodes_query():
    """Test that spaces and special characters are percent-encoded."""
    session = _make_session(_ok({"response": {"results": {"results": []}}}))
    api = BBCWeatherAPI(session)

    await api.search_location("New York")

    url = session.get.call_args[0][0]
    assert "New%20York" in url


async def test_get_forecast(forecast_response):
    """Test get_forecast returns parsed forecast data."""
    session = _make_session(_ok(forecast_response))
    api = BBCWeatherAPI(session)

    result = await api.get_forecast("2643743")

    assert "forecasts" in result
    assert len(result["forecasts"]) == 2
    first_day = result["forecasts"][0]
    assert first_day["summary"]["report"]["maxTempC"] == 22


async def test_get_observations(observation_response):
    """Test get_observations returns parsed observation data."""
    session = _make_session(_ok(observation_response))
    api = BBCWeatherAPI(session)

    result = await api.get_observations("2643743")

    assert "observations" in result
    assert len(result["observations"]) == 1
    assert result["observations"][0]["temperature"]["C"] == 17


@patch("custom_components.bbc_weather.api.random.uniform", return_value=0.5)
@patch("custom_components.bbc_weather.api.asyncio.sleep", new_callable=AsyncMock)
async def test_retry_on_500_then_success(mock_sleep, mock_uniform):
    """Test that a 500 error is retried and succeeds on the third attempt."""
    data = {"forecasts": []}
    session = _make_session(_server_error(), _server_error(), _ok(data))
    api = BBCWeatherAPI(session)

    result = await api.get_forecast("2643743")

    assert result == data
    assert session.get.call_count == 3
    assert mock_sleep.call_count == 2
    # Backoff: 1*2^0 + 0.5 = 1.5s, 1*2^1 + 0.5 = 2.5s
    mock_sleep.assert_any_call(1.5)
    mock_sleep.assert_any_call(2.5)


@patch("custom_components.bbc_weather.api.random.uniform", return_value=0.5)
@patch("custom_components.bbc_weather.api.asyncio.sleep", new_callable=AsyncMock)
async def test_all_retries_exhausted_raises(mock_sleep, mock_uniform):
    """Test BBCWeatherAPIError raised after 3 consecutive failures."""
    session = _make_session(_server_error(), _server_error(), _server_error())
    api = BBCWeatherAPI(session)

    with pytest.raises(BBCWeatherAPIError, match="failed after 3 attempts"):
        await api.get_forecast("2643743")

    assert session.get.call_count == 3


@patch("custom_components.bbc_weather.api.random.uniform", return_value=0.5)
@patch("custom_components.bbc_weather.api.asyncio.sleep", new_callable=AsyncMock)
async def test_timeout_retried_then_raises(mock_sleep, mock_uniform):
    """Test TimeoutError is retried and eventually raises BBCWeatherAPIError."""
    session = _make_session(_timeout(), _timeout(), _timeout())
    api = BBCWeatherAPI(session)

    with pytest.raises(BBCWeatherAPIError, match="failed after 3 attempts"):
        await api.get_observations("2643743")

    assert session.get.call_count == 3


@patch("custom_components.bbc_weather.api.random.uniform", return_value=0.5)
@patch("custom_components.bbc_weather.api.asyncio.sleep", new_callable=AsyncMock)
async def test_malformed_json_retried(mock_sleep, mock_uniform):
    """Test ValueError (bad JSON) is retried like other transient errors."""
    data = {"observations": []}
    session = _make_session(_bad_json_response(), _ok(data))
    api = BBCWeatherAPI(session)

    result = await api.get_observations("2643743")

    assert result == data
    assert session.get.call_count == 2


# ---------------------------------------------------------------------------
# Location ID validation
# ---------------------------------------------------------------------------


async def test_get_forecast_rejects_non_numeric_id():
    """Test that non-numeric location IDs raise BBCWeatherAPIError."""
    session = MagicMock(spec=ClientSession)
    api = BBCWeatherAPI(session)

    with pytest.raises(BBCWeatherAPIError, match="Invalid location ID"):
        await api.get_forecast("abc123")

    session.get.assert_not_called()


async def test_get_observations_rejects_non_numeric_id():
    """Test that non-numeric location IDs raise BBCWeatherAPIError."""
    session = MagicMock(spec=ClientSession)
    api = BBCWeatherAPI(session)

    with pytest.raises(BBCWeatherAPIError, match="Invalid location ID"):
        await api.get_observations("../admin")

    session.get.assert_not_called()


async def test_get_forecast_rejects_empty_id():
    """Test that empty string location ID raises BBCWeatherAPIError."""
    session = MagicMock(spec=ClientSession)
    api = BBCWeatherAPI(session)

    with pytest.raises(BBCWeatherAPIError, match="Invalid location ID"):
        await api.get_forecast("")

    session.get.assert_not_called()


# ---------------------------------------------------------------------------
# Response size limit
# ---------------------------------------------------------------------------


async def test_oversized_response_raises():
    """Test that responses exceeding MAX_RESPONSE_SIZE raise immediately."""
    session = _make_session(_oversized_response())
    api = BBCWeatherAPI(session)

    with pytest.raises(BBCWeatherAPIError, match="Response too large"):
        await api.get_forecast("2643743")


# ---------------------------------------------------------------------------
# Response type validation
# ---------------------------------------------------------------------------


async def test_non_dict_response_raises():
    """Test that a valid JSON response that is not a dict raises."""
    session = _make_session(_non_dict_response())
    api = BBCWeatherAPI(session)

    with pytest.raises(BBCWeatherAPIError, match="Unexpected response type"):
        await api.get_forecast("2643743")


# ---------------------------------------------------------------------------
# API key handling
# ---------------------------------------------------------------------------


async def test_custom_api_key_used_in_search():
    """Test that a custom API key is used in location search URL."""
    session = _make_session(_ok({"response": {"results": {"results": []}}}))
    api = BBCWeatherAPI(session, api_key="custom_key_123")

    await api.search_location("London")

    url = session.get.call_args[0][0]
    assert "api_key=custom_key_123" in url


async def test_api_key_url_encoded_in_search():
    """Test that special characters in api_key are URL-encoded."""
    session = _make_session(_ok({"response": {"results": {"results": []}}}))
    api = BBCWeatherAPI(session, api_key="key&inject=bad")

    await api.search_location("London")

    url = session.get.call_args[0][0]
    # The & should be encoded, not injecting a new query parameter
    assert "key&inject=bad" not in url
    assert "key%26inject%3Dbad" in url

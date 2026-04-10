"""Config flow and options flow for BBC Weather."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BBCWeatherAPI, BBCWeatherAPIError
from .const import CONF_API_KEY, DOMAIN, MAX_LOCATION_NAME_LENGTH

_LOGGER = logging.getLogger(__name__)

CONF_LOCATION_1 = "location_1"
CONF_LOCATION_2 = "location_2"
CONF_LOCATIONS = "locations"

MAX_QUERY_LENGTH = 200


def _location_label(loc: dict[str, Any]) -> str:
    """Format a location result as 'Name, Container, Country'."""
    parts = [loc.get("name", "")]
    if loc.get("container"):
        parts.append(loc["container"])
    if loc.get("country"):
        parts.append(loc["country"])
    label = ", ".join(parts)
    return label[:MAX_LOCATION_NAME_LENGTH]


async def _search_locations(
    api: BBCWeatherAPI, query: str
) -> list[dict[str, Any]]:
    """Search BBC API and return a list of location dicts."""
    try:
        data = await api.search_location(query[:MAX_QUERY_LENGTH])
    except BBCWeatherAPIError:
        return []
    results = data.get("response", {}).get("results", {}).get("results", [])
    return [
        {
            "id": str(r["id"]),
            "name": r.get("name", ""),
            "container": r.get("container", ""),
            "country": r.get("country", ""),
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
        }
        for r in results
        if r.get("id")
    ]


async def _validate_forecast(api: BBCWeatherAPI, location_id: str) -> bool:
    """Check that a location ID returns valid forecast data."""
    try:
        data = await api.get_forecast(location_id)
        return bool(data.get("forecasts"))
    except BBCWeatherAPIError:
        return False


# ---------------------------------------------------------------------------
# Shared helpers for config flow and options flow
# ---------------------------------------------------------------------------


def _build_selection_schema(
    search_results: dict[str, list[dict[str, Any]]],
) -> vol.Schema | None:
    """Build a vol.Schema for disambiguation dropdowns, or None if all single-result."""
    schema_fields: dict[Any, Any] = {}
    for key, results in search_results.items():
        if len(results) == 1:
            continue
        options = {r["id"]: _location_label(r) for r in results}
        schema_fields[vol.Required(key)] = vol.In(options)
    if not schema_fields:
        return None
    return vol.Schema(schema_fields)


def _auto_selections(
    search_results: dict[str, list[dict[str, Any]]],
) -> dict[str, str]:
    """Return {key: id} for every search key that had exactly one result."""
    return {k: v[0]["id"] for k, v in search_results.items()}


async def _resolve_locations(
    api: BBCWeatherAPI,
    search_results: dict[str, list[dict[str, Any]]],
    selections: dict[str, str],
) -> tuple[list[dict[str, Any]], str | None]:
    """Validate forecasts and build the locations list.

    Returns (locations, error_key) — error_key is the CONF_LOCATION key that
    failed forecast validation, or None on success.
    """
    locations: list[dict[str, Any]] = []

    for key in (CONF_LOCATION_1, CONF_LOCATION_2):
        loc_id = selections.get(key)
        if not loc_id:
            results = search_results.get(key)
            if results and len(results) == 1:
                loc_id = results[0]["id"]
        if not loc_id:
            continue

        loc_record = next(
            (r for r in search_results.get(key, []) if r["id"] == loc_id), None
        )
        if loc_record is None:
            continue

        if not await _validate_forecast(api, loc_id):
            return [], key

        locations.append(
            {
                "id": loc_record["id"],
                "name": _location_label(loc_record),
                "latitude": loc_record.get("latitude"),
                "longitude": loc_record.get("longitude"),
            }
        )

    return locations, None


def _entry_data(
    locations: list[dict[str, Any]], api_key: str | None
) -> dict[str, Any]:
    """Build the config entry data dict."""
    data: dict[str, Any] = {CONF_LOCATIONS: locations}
    if api_key:
        data[CONF_API_KEY] = api_key
    return data


# ---------------------------------------------------------------------------
# Config flow
# ---------------------------------------------------------------------------


class BBCWeatherConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle initial configuration of BBC Weather."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise flow state."""
        self._api: BBCWeatherAPI | None = None
        self._api_key: str | None = None
        self._search_results: dict[str, list[dict[str, Any]]] = {}

    def _get_api(self, api_key: str | None = None) -> BBCWeatherAPI:
        if self._api is None or api_key is not None:
            session = async_get_clientsession(self.hass)
            self._api = BBCWeatherAPI(session, api_key=api_key or None)
        return self._api

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> BBCWeatherOptionsFlow:
        """Return the options flow handler."""
        return BBCWeatherOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: user enters location queries."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._api_key = user_input.get(CONF_API_KEY, "").strip() or None
            api = self._get_api(api_key=self._api_key)
            query1 = user_input.get(CONF_LOCATION_1, "").strip()
            query2 = user_input.get(CONF_LOCATION_2, "").strip()

            if not query1:
                errors[CONF_LOCATION_1] = "no_location"
            else:
                results1 = await _search_locations(api, query1)
                if not results1:
                    errors[CONF_LOCATION_1] = "location_not_found"
                else:
                    self._search_results[CONF_LOCATION_1] = results1

            if query2 and not errors:
                results2 = await _search_locations(api, query2)
                if not results2:
                    errors[CONF_LOCATION_2] = "location_not_found"
                else:
                    self._search_results[CONF_LOCATION_2] = results2

            if not errors:
                all_single = all(
                    len(v) == 1 for v in self._search_results.values()
                )
                if all_single:
                    return await self._async_finish(_auto_selections(self._search_results))
                return await self.async_step_select_locations()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCATION_1): str,
                    vol.Optional(CONF_LOCATION_2, default=""): str,
                    vol.Optional(CONF_API_KEY, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_select_locations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: pick from multiple search results."""
        if user_input is not None:
            return await self._async_finish(user_input)

        schema = _build_selection_schema(self._search_results)
        if schema is None:
            return await self._async_finish(_auto_selections(self._search_results))

        return self.async_show_form(
            step_id="select_locations",
            data_schema=schema,
        )

    async def _async_finish(
        self, selections: dict[str, str]
    ) -> ConfigFlowResult:
        """Validate forecasts and create the config entry."""
        api = self._get_api()
        locations, error_key = await _resolve_locations(
            api, self._search_results, selections
        )

        if error_key is not None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_LOCATION_1): str,
                        vol.Optional(CONF_LOCATION_2, default=""): str,
                    }
                ),
                errors={error_key: "forecast_unavailable"},
            )

        title = locations[0]["name"] if locations else "BBC Weather"
        return self.async_create_entry(
            title=title,
            data=_entry_data(locations, self._api_key),
        )


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


class BBCWeatherOptionsFlow(OptionsFlow):
    """Handle options (reconfigure locations) for BBC Weather."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise options flow."""
        self._config_entry = config_entry
        self._api: BBCWeatherAPI | None = None
        self._api_key: str | None = None
        self._search_results: dict[str, list[dict[str, Any]]] = {}

    def _get_api(self, api_key: str | None = None) -> BBCWeatherAPI:
        if self._api is None or api_key is not None:
            session = async_get_clientsession(self.hass)
            self._api = BBCWeatherAPI(session, api_key=api_key or None)
        return self._api

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the location form, pre-filled with current names."""
        errors: dict[str, str] = {}
        existing: list[dict[str, Any]] = self._config_entry.data.get(
            CONF_LOCATIONS, []
        )
        default_1 = existing[0]["name"] if len(existing) > 0 else ""
        default_2 = existing[1]["name"] if len(existing) > 1 else ""
        default_api_key = self._config_entry.data.get(CONF_API_KEY, "")

        if user_input is not None:
            self._api_key = user_input.get(CONF_API_KEY, "").strip() or None
            api = self._get_api(api_key=self._api_key)
            query1 = user_input.get(CONF_LOCATION_1, "").strip()
            query2 = user_input.get(CONF_LOCATION_2, "").strip()

            if not query1:
                errors[CONF_LOCATION_1] = "no_location"
            else:
                results1 = await _search_locations(api, query1)
                if not results1:
                    errors[CONF_LOCATION_1] = "location_not_found"
                else:
                    self._search_results[CONF_LOCATION_1] = results1

            if query2 and not errors:
                results2 = await _search_locations(api, query2)
                if not results2:
                    errors[CONF_LOCATION_2] = "location_not_found"
                else:
                    self._search_results[CONF_LOCATION_2] = results2

            if not errors:
                all_single = all(
                    len(v) == 1 for v in self._search_results.values()
                )
                if all_single:
                    return await self._async_finish_options(
                        _auto_selections(self._search_results)
                    )
                return await self.async_step_select_locations()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCATION_1, default=default_1): str,
                    vol.Optional(CONF_LOCATION_2, default=default_2): str,
                    vol.Optional(CONF_API_KEY, default=default_api_key): str,
                }
            ),
            errors=errors,
        )

    async def async_step_select_locations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick from multiple search results."""
        if user_input is not None:
            return await self._async_finish_options(user_input)

        schema = _build_selection_schema(self._search_results)
        if schema is None:
            return await self._async_finish_options(
                _auto_selections(self._search_results)
            )

        return self.async_show_form(
            step_id="select_locations",
            data_schema=schema,
        )

    async def _async_finish_options(
        self, selections: dict[str, str]
    ) -> ConfigFlowResult:
        """Validate and update the config entry with new locations."""
        api = self._get_api()
        locations, error_key = await _resolve_locations(
            api, self._search_results, selections
        )

        if error_key is not None:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_LOCATION_1): str,
                        vol.Optional(CONF_LOCATION_2, default=""): str,
                    }
                ),
                errors={error_key: "forecast_unavailable"},
            )

        self.hass.config_entries.async_update_entry(
            self._config_entry,
            data=_entry_data(locations, self._api_key),
            title=locations[0]["name"] if locations else "BBC Weather",
        )

        return self.async_create_entry(title="", data={})

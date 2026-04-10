"""BBC Weather integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BBCWeatherAPI
from .const import CONF_API_KEY, DOMAIN, MAX_LOCATIONS
from .coordinator import BBCWeatherDataCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BBC Weather from a config entry."""
    session = async_get_clientsession(hass)
    api_key = entry.data.get(CONF_API_KEY) or None
    api = BBCWeatherAPI(session, api_key=api_key)

    locations: list[dict] = entry.data.get("locations", [])[:MAX_LOCATIONS]
    coordinators: list[BBCWeatherDataCoordinator] = []

    for loc in locations:
        loc_id = loc["id"]
        if not isinstance(loc_id, str) or not loc_id.isdigit():
            _LOGGER.error(
                "Invalid location ID %r in config entry, skipping", loc_id
            )
            continue

        coordinator = BBCWeatherDataCoordinator(
            hass,
            api,
            location_id=loc_id,
            location_name=loc.get("name", "Unknown"),
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators.append(coordinator)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Unload a BBC Weather config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok

"""Weather platform for BBC Weather."""

from __future__ import annotations

from typing import Any

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VISIBILITY_KM
from .coordinator import BBCWeatherDataCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BBC Weather entities from a config entry."""
    coordinators: list[BBCWeatherDataCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        BBCWeatherEntity(coordinator) for coordinator in coordinators
    )


class BBCWeatherEntity(CoordinatorEntity[BBCWeatherDataCoordinator], WeatherEntity):
    """A weather entity for a single BBC Weather location."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.MILES_PER_HOUR
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_attribution = "Data provided by BBC Weather"
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(self, coordinator: BBCWeatherDataCoordinator) -> None:
        """Initialise the weather entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"bbc_weather_{coordinator.location_id}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.location_id)},
            manufacturer="BBC",
            model="BBC Weather",
            name=coordinator.location_name,
        )

    @property
    def _current(self) -> dict[str, Any]:
        """Return the current conditions dict, or empty dict if unavailable."""
        if self.coordinator.data is None:
            return {}
        return self.coordinator.data.get("current", {})

    # ------------------------------------------------------------------
    # Current conditions
    # ------------------------------------------------------------------

    @property
    def native_temperature(self) -> float | None:
        """Return the current temperature in °C."""
        return self._current.get("temperature")

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the feels-like temperature in °C."""
        return self._current.get("feels_like_temperature")

    @property
    def humidity(self) -> float | None:
        """Return the current humidity in %."""
        return self._current.get("humidity")

    @property
    def native_pressure(self) -> float | None:
        """Return the current pressure in hPa/mb."""
        return self._current.get("pressure")

    @property
    def native_wind_speed(self) -> float | None:
        """Return the current wind speed in mph."""
        return self._current.get("wind_speed")

    @property
    def wind_bearing(self) -> float | None:
        """Return the current wind bearing in degrees."""
        return self._current.get("wind_bearing")

    @property
    def native_visibility(self) -> float | None:
        """Return visibility in km, mapped from BBC text description."""
        vis = self._current.get("visibility")
        if vis is None:
            return None
        if isinstance(vis, str):
            return VISIBILITY_KM.get(vis)
        return None

    @property
    def condition(self) -> str | None:
        """Return the current HA condition string."""
        return self._current.get("condition")

    # ------------------------------------------------------------------
    # Forecasts (modern service-call approach)
    # ------------------------------------------------------------------

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return daily forecasts for up to 14 days."""
        if self.coordinator.data is None:
            return None
        days = self.coordinator.data.get("daily_forecast", [])
        if not days:
            return None
        return [
            Forecast(
                datetime=day.get("date"),
                condition=day.get("condition"),
                native_temperature=day.get("temperature_high"),
                native_templow=day.get("temperature_low"),
                precipitation_probability=day.get("precipitation_probability"),
                native_wind_speed=day.get("wind_speed"),
                wind_bearing=day.get("wind_bearing"),
            )
            for day in days
        ]

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return hourly forecasts."""
        if self.coordinator.data is None:
            return None
        hours = self.coordinator.data.get("hourly_forecast", [])
        if not hours:
            return None
        return [
            Forecast(
                datetime=hour.get("datetime"),
                condition=hour.get("condition"),
                native_temperature=hour.get("temperature"),
                precipitation_probability=hour.get("precipitation_probability"),
                native_wind_speed=hour.get("wind_speed"),
                humidity=hour.get("humidity"),
            )
            for hour in hours
        ]

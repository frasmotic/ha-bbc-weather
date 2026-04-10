"""Constants for the BBC Weather integration."""

DOMAIN = "bbc_weather"

# BBC's public API key for the locator service. This is NOT a user credential.
# It is embedded in BBC's own web pages and is required for location search only.
# Users can override this via the config flow if BBC rotates the key before an
# integration update is released.
BBC_LOCATOR_API_KEY = "AGbFAKx58hyjQScCXIYrxuEwJh2W2cmv"

# Config entry data keys
CONF_API_KEY = "api_key"

# API endpoints — {api_key} is substituted at runtime so it can be overridden.
LOCATION_SEARCH_URL = (
    "https://locator-service.api.bbci.co.uk/locations"
    "?api_key={api_key}"
    "&s={query}&stack=aws&locale=en&filter=international"
    "&place-types=settlement,airport,district&order=importance&a=true&format=json"
)
FORECAST_URL = (
    "https://weather-broker-cdn.api.bbci.co.uk/en/forecast/aggregated/{location_id}"
)
OBSERVATION_URL = (
    "https://weather-broker-cdn.api.bbci.co.uk/en/observation/{location_id}"
)

# Update intervals (seconds)
FORECAST_UPDATE_INTERVAL = 900  # 15 minutes

# Security limits
MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5 MB
REQUEST_TIMEOUT = 30  # seconds per request

# Maximum number of configured locations
MAX_LOCATIONS = 2

# Maximum location name length stored in config entry
MAX_LOCATION_NAME_LENGTH = 200

# BBC weatherType code -> Home Assistant condition
# Codes that differ between day/night are handled: 0=Clear Sky (night),
# 1=Sunny (day). Both map appropriately.
BBC_TO_HA_CONDITION: dict[int, str] = {
    0: "clear-night",
    1: "sunny",
    2: "partlycloudy",
    3: "partlycloudy",
    # 4: not used
    5: "fog",
    6: "fog",
    7: "cloudy",
    8: "cloudy",
    9: "rainy",
    10: "rainy",
    11: "rainy",
    12: "rainy",
    13: "pouring",
    14: "pouring",
    15: "snowy",
    16: "snowy",
    17: "hail",
    18: "hail",
    19: "snowy",
    20: "snowy",
    21: "snowy",
    22: "snowy",
    23: "lightning-rainy",
    24: "lightning",
    25: "exceptional",
    # 26: not used
    27: "pouring",
    28: "pouring",
    29: "lightning",
    30: "lightning",
}

# Wind direction abbreviation -> degrees
WIND_DIRECTION_DEGREES: dict[str, float] = {
    "N": 0,
    "NNE": 22.5,
    "NE": 45,
    "ENE": 67.5,
    "E": 90,
    "ESE": 112.5,
    "SE": 135,
    "SSE": 157.5,
    "S": 180,
    "SSW": 202.5,
    "SW": 225,
    "WSW": 247.5,
    "W": 270,
    "WNW": 292.5,
    "NW": 315,
    "NNW": 337.5,
}

# BBC visibility text -> approximate km
VISIBILITY_KM: dict[str, float] = {
    "Very Good": 20,
    "Good": 10,
    "Moderate": 5,
    "Poor": 2,
    "Very Poor": 1,
    "Fog": 0.1,
}

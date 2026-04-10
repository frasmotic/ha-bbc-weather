# BBC Weather for Home Assistant

A custom integration that provides BBC Weather data for Home Assistant using BBC's public JSON APIs.

## Disclaimer

This integration uses **unofficial, undocumented BBC Weather APIs**. No API key is required and the data is free, but the endpoints could change or be removed by the BBC at any time, which would break this integration.

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Click the three-dot menu in the top right and select **Custom repositories**
3. Add this repository URL and select **Integration** as the category
4. Click **Add**, then find "BBC Weather" in the HACS integration list and install it
5. Restart Home Assistant

### Manual

Copy the `custom_components/bbc_weather` folder into your Home Assistant `custom_components` directory and restart.

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **BBC Weather**
3. Enter one or two location names (city names, postcodes, or place names)
4. If multiple results are found, select the correct one from the dropdown
5. The integration will verify it can fetch forecast data before completing setup

An optional **API key** field is available in case the BBC rotates its public locator key before an integration update is released. Leave it blank under normal circumstances.

### Changing locations

Click **Configure** on the BBC Weather integration card to update your locations. The integration will reload automatically with the new locations.

## What you get

Each configured location creates a **weather entity** providing:

- **Current conditions** — temperature, feels-like temperature, humidity, pressure, wind speed and direction, visibility, and weather condition
- **14-day daily forecast** — high/low temperatures, precipitation probability, wind, UV index
- **Hourly forecast** — temperature, precipitation probability, wind, humidity

Current conditions use live observation data when available (primarily UK locations), falling back to forecast data for the current hour.

## Notes

- Observation data may be limited or unavailable for locations outside the UK. The integration will still work using forecast data for current conditions.
- Data updates every 15 minutes.
- You can configure a maximum of 2 locations (e.g. "home" and "work").
- Visibility is reported by the BBC as a text description (Good, Poor, etc.) and converted to approximate kilometre values.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]" pytest pytest-asyncio pytest-homeassistant-custom-component ruff

# Run tests
python -m pytest tests/ -v

# Lint
ruff check .
```

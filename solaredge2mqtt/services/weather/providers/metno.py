from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from aiohttp import ClientResponseError

from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.services.http_async import HTTPClientAsync
from solaredge2mqtt.services.weather.models.unified import (
    WeatherData,
    WeatherForecast,
)
from solaredge2mqtt.services.weather.providers.base import WeatherProvider

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings import ServiceSettings

LOCATIONFORECAST_URL = (
    "https://api.met.no/weatherapi/locationforecast/2.0/complete"
)

# Mapping from MET Norway symbol codes to OpenWeatherMap-style weather IDs
# This ensures ML models trained on OpenWeatherMap data continue to work
SYMBOL_CODE_MAP = {
    # Clear sky
    "clearsky_day": {"id": 800, "main": "Clear"},
    "clearsky_night": {"id": 800, "main": "Clear"},
    "clearsky_polartwilight": {"id": 800, "main": "Clear"},
    # Fair (few clouds)
    "fair_day": {"id": 801, "main": "Clouds"},
    "fair_night": {"id": 801, "main": "Clouds"},
    "fair_polartwilight": {"id": 801, "main": "Clouds"},
    # Partly cloudy
    "partlycloudy_day": {"id": 802, "main": "Clouds"},
    "partlycloudy_night": {"id": 802, "main": "Clouds"},
    "partlycloudy_polartwilight": {"id": 802, "main": "Clouds"},
    # Cloudy
    "cloudy": {"id": 804, "main": "Clouds"},
    # Rain
    "rain": {"id": 500, "main": "Rain"},
    "rainshowers_day": {"id": 520, "main": "Rain"},
    "rainshowers_night": {"id": 520, "main": "Rain"},
    "rainshowers_polartwilight": {"id": 520, "main": "Rain"},
    "heavyrain": {"id": 502, "main": "Rain"},
    "heavyrainshowers_day": {"id": 522, "main": "Rain"},
    "heavyrainshowers_night": {"id": 522, "main": "Rain"},
    "heavyrainshowers_polartwilight": {"id": 522, "main": "Rain"},
    "lightrain": {"id": 500, "main": "Rain"},
    "lightrainshowers_day": {"id": 520, "main": "Rain"},
    "lightrainshowers_night": {"id": 520, "main": "Rain"},
    "lightrainshowers_polartwilight": {"id": 520, "main": "Rain"},
    # Snow
    "snow": {"id": 601, "main": "Snow"},
    "snowshowers_day": {"id": 621, "main": "Snow"},
    "snowshowers_night": {"id": 621, "main": "Snow"},
    "snowshowers_polartwilight": {"id": 621, "main": "Snow"},
    "heavysnow": {"id": 602, "main": "Snow"},
    "heavysnowshowers_day": {"id": 622, "main": "Snow"},
    "heavysnowshowers_night": {"id": 622, "main": "Snow"},
    "heavysnowshowers_polartwilight": {"id": 622, "main": "Snow"},
    "lightsnow": {"id": 600, "main": "Snow"},
    "lightsnowshowers_day": {"id": 620, "main": "Snow"},
    "lightsnowshowers_night": {"id": 620, "main": "Snow"},
    "lightsnowshowers_polartwilight": {"id": 620, "main": "Snow"},
    # Sleet
    "sleet": {"id": 611, "main": "Snow"},
    "sleetshowers_day": {"id": 615, "main": "Snow"},
    "sleetshowers_night": {"id": 615, "main": "Snow"},
    "sleetshowers_polartwilight": {"id": 615, "main": "Snow"},
    "heavysleet": {"id": 612, "main": "Snow"},
    "heavysleetshowers_day": {"id": 616, "main": "Snow"},
    "heavysleetshowers_night": {"id": 616, "main": "Snow"},
    "heavysleetshowers_polartwilight": {"id": 616, "main": "Snow"},
    "lightsleet": {"id": 611, "main": "Snow"},
    "lightsleetshowers_day": {"id": 615, "main": "Snow"},
    "lightsleetshowers_night": {"id": 615, "main": "Snow"},
    "lightsleetshowers_polartwilight": {"id": 615, "main": "Snow"},
    # Thunder
    "thunder": {"id": 211, "main": "Thunderstorm"},
    "thunderstorm": {"id": 211, "main": "Thunderstorm"},
    "heavyrainshowersandthunder_day": {"id": 202, "main": "Thunderstorm"},
    "heavyrainshowersandthunder_night": {"id": 202, "main": "Thunderstorm"},
    "heavyrainshowersandthunder_polartwilight": {
        "id": 202,
        "main": "Thunderstorm",
    },
    "heavyrainandthunder": {"id": 202, "main": "Thunderstorm"},
    "lightrainshowersandthunder_day": {"id": 200, "main": "Thunderstorm"},
    "lightrainshowersandthunder_night": {"id": 200, "main": "Thunderstorm"},
    "lightrainshowersandthunder_polartwilight": {
        "id": 200,
        "main": "Thunderstorm",
    },
    "lightrainandthunder": {"id": 200, "main": "Thunderstorm"},
    "heavysnowshowersandthunder_day": {"id": 622, "main": "Snow"},
    "heavysnowshowersandthunder_night": {"id": 622, "main": "Snow"},
    "heavysnowshowersandthunder_polartwilight": {"id": 622, "main": "Snow"},
    "heavysnowandthunder": {"id": 622, "main": "Snow"},
    "lightsnowshowersandthunder_day": {"id": 620, "main": "Snow"},
    "lightsnowshowersandthunder_night": {"id": 620, "main": "Snow"},
    "lightsnowshowersandthunder_polartwilight": {"id": 620, "main": "Snow"},
    "lightsnowandthunder": {"id": 620, "main": "Snow"},
    "lightssleetshowersandthunder_day": {"id": 615, "main": "Snow"},
    "lightssleetshowersandthunder_night": {"id": 615, "main": "Snow"},
    "lightssleetshowersandthunder_polartwilight": {"id": 615, "main": "Snow"},
    "lightssleetandthunder": {"id": 615, "main": "Snow"},
    "heavysleetshowersandthunder_day": {"id": 616, "main": "Snow"},
    "heavysleetshowersandthunder_night": {"id": 616, "main": "Snow"},
    "heavysleetshowersandthunder_polartwilight": {"id": 616, "main": "Snow"},
    "heavysleetandthunder": {"id": 616, "main": "Snow"},
    # Fog
    "fog": {"id": 741, "main": "Fog"},
    # Default fallback
    "_default": {"id": 800, "main": "Clear"},
}


def map_symbol_code(symbol_code: str | None) -> dict:
    """Map MET Norway symbol code to OpenWeatherMap-style weather info."""
    if symbol_code is None:
        return SYMBOL_CODE_MAP["_default"]
    return SYMBOL_CODE_MAP.get(symbol_code, SYMBOL_CODE_MAP["_default"])


class METNorwayProvider(WeatherProvider, HTTPClientAsync):
    """MET Norway (api.met.no) weather provider."""

    def __init__(self, settings: ServiceSettings) -> None:
        WeatherProvider.__init__(self, settings)
        HTTPClientAsync.__init__(self, "MET Norway")

    @property
    def name(self) -> str:
        return "metno"

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with User-Agent."""
        headers = {}
        if self.provider_settings.user_agent:
            headers["User-Agent"] = self.provider_settings.user_agent
        return headers

    async def fetch_weather(self) -> WeatherForecast:
        """Fetch weather from MET Norway API."""
        try:
            logger.info("Reading weather data from MET Norway")

            async with asyncio.timeout(7):
                result = await self._get(
                    LOCATIONFORECAST_URL,
                    params={
                        "lat": self.location.latitude,
                        "lon": self.location.longitude,
                        "altitude": int(self.settings.location.altitude)
                        if hasattr(self.settings.location, "altitude")
                        else None,
                    },
                    headers=self._get_headers(),
                )

            logger.trace(result)

            if result is None:
                raise InvalidDataException(
                    "Unable to read weather data from MET Norway"
                )

            return self._convert_to_unified(result)

        except ClientResponseError as error:
            status_code = error.status
            if status_code == 403:
                error_msg = (
                    "MET Norway API rejected the request. "
                    "Please configure a unique User-Agent in settings."
                )
            else:
                error_msg = (
                    f"Unable to read weather data from MET Norway "
                    f"(HTTP {status_code})"
                )
            raise InvalidDataException(error_msg) from error
        except asyncio.TimeoutError as error:
            raise InvalidDataException(
                "Unable to read weather data from MET Norway (timeout)"
            ) from error

    def _convert_to_unified(self, data: dict) -> WeatherForecast:
        """Convert MET Norway response to unified format."""

        def parse_timestamp(ts: str) -> datetime:
            """Parse ISO timestamp string to datetime."""
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))

        def convert_timeseries_entry(
            entry: dict, lat: float, lon: float
        ) -> WeatherData:
            """Convert a single timeseries entry to WeatherData."""
            time = entry.get("time", "")
            instant = (
                entry.get("data", {}).get("instant", {}).get("details", {})
            )
            next_1h = (
                entry.get("data", {})
                .get("next_1_hours", {})
                .get("details", {})
            )
            next_1h_summary = (
                entry.get("data", {})
                .get("next_1_hours", {})
                .get("summary", {})
            )
            next_6h = (
                entry.get("data", {})
                .get("next_6_hours", {})
                .get("details", {})
            )

            # Get symbol code (for weather condition mapping)
            symbol_code = next_1h_summary.get("symbol_code") or next_6h.get(
                "symbol_code"
            )
            weather_info = map_symbol_code(symbol_code)

            # Determine precipitation type from symbol code
            rain_amount = 0.0
            snow_amount = 0.0
            precip = next_1h.get("precipitation_amount") or next_6h.get(
                "precipitation_amount", 0.0
            )

            if symbol_code and (
                "snow" in symbol_code or "sleet" in symbol_code
            ):
                snow_amount = precip
            elif symbol_code and "rain" in symbol_code:
                rain_amount = precip

            return WeatherData(
                latitude=lat,
                longitude=lon,
                timestamp=parse_timestamp(time),
                temperature=instant.get("air_temperature"),
                feels_like=None,  # Not available in MET API
                dew_point=instant.get("dew_point_temperature"),
                pressure=instant.get("air_pressure_at_sea_level"),
                humidity=instant.get("relative_humidity"),
                cloud_coverage=instant.get("cloud_area_fraction"),
                visibility=None,  # Not available in MET API
                uv_index=instant.get("ultraviolet_index_clear_sky"),
                wind_speed=instant.get("wind_speed"),
                wind_direction=instant.get("wind_from_direction"),
                wind_gust=instant.get("wind_speed_of_gust"),
                precipitation_probability=next_1h.get(
                    "probability_of_precipitation", 0.0
                )
                / 100.0,
                rain_amount=rain_amount if rain_amount > 0 else None,
                snow_amount=snow_amount if snow_amount > 0 else None,
                weather_id=weather_info["id"],
                weather_main=weather_info["main"],
                weather_description=symbol_code,
                sunrise=None,  # Not available, use Sunrise API if needed
                sunset=None,
            )

        geometry = data.get("geometry", {})
        lat = (
            geometry.get("coordinates", [None, None])[1]
            or self.location.latitude
        )
        lon = (
            geometry.get("coordinates", [None, None])[0]
            or self.location.longitude
        )

        timeseries = data.get("properties", {}).get("timeseries", [])

        if not timeseries:
            raise InvalidDataException(
                "No weather data available from MET Norway"
            )

        # First entry is current weather
        current = convert_timeseries_entry(timeseries[0], lat, lon)

        # Rest are hourly forecasts
        hourly = [
            convert_timeseries_entry(entry, lat, lon)
            for entry in timeseries[1:]
        ]

        return WeatherForecast(current=current, hourly=hourly)

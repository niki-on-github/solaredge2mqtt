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

ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"


class OpenWeatherMapProvider(WeatherProvider, HTTPClientAsync):
    """OpenWeatherMap API provider."""

    def __init__(self, settings: ServiceSettings) -> None:
        WeatherProvider.__init__(self, settings)
        HTTPClientAsync.__init__(self, "OpenWeatherMap")

    @property
    def name(self) -> str:
        return "openweathermap"

    async def fetch_weather(self) -> WeatherForecast:
        """Fetch weather from OpenWeatherMap API."""
        try:
            logger.info("Reading weather data from OpenWeatherMap")

            async with asyncio.timeout(7):
                result = await self._get(
                    ONECALL_URL,
                    params={
                        "lat": self.location.latitude,
                        "lon": self.location.longitude,
                        "exclude": "minutely,daily,alerts",
                        "units": "metric",
                        "lang": self.provider_settings.language,
                        "appid": self.provider_settings.api_key.get_secret_value(),
                    },
                )

            logger.trace(result)

            if result is None:
                raise InvalidDataException(
                    "Unable to read weather data from OpenWeatherMap"
                )

            return self._convert_to_unified(result)

        except ClientResponseError as error:
            status_code = error.status
            if status_code == 401:
                error_msg = "Invalid OpenWeatherMap API key or no subscription to OneCall-API"
            else:
                error_msg = (
                    f"Unable to read weather data from OpenWeatherMap "
                    f"(HTTP {status_code})"
                )
            raise InvalidDataException(error_msg) from error
        except asyncio.TimeoutError as error:
            raise InvalidDataException(
                "Unable to read weather data from OpenWeatherMap (timeout)"
            ) from error

    def _convert_to_unified(self, data: dict) -> WeatherForecast:
        """Convert OpenWeatherMap response to unified format."""

        def parse_timestamp(ts: int) -> datetime:
            return datetime.fromtimestamp(ts, tz=timezone.utc)

        def convert_weather_item(
            item: dict,
            lat: float,
            lon: float,
            tz: str | None = None,
            tz_offset: int | None = None,
        ) -> WeatherData:
            weather = item.get("weather", [{}])[0]
            rain_data = item.get("rain", {})
            snow_data = item.get("snow", {})

            return WeatherData(
                latitude=lat,
                longitude=lon,
                timestamp=parse_timestamp(item["dt"]),
                timezone=tz,
                timezone_offset=tz_offset,
                temperature=item.get("temp"),
                feels_like=item.get("feels_like"),
                dew_point=item.get("dew_point"),
                pressure=item.get("pressure"),
                humidity=item.get("humidity"),
                cloud_coverage=item.get("clouds"),
                visibility=item.get("visibility"),
                uv_index=item.get("uvi"),
                wind_speed=item.get("wind_speed"),
                wind_direction=item.get("wind_deg"),
                wind_gust=item.get("wind_gust"),
                precipitation_probability=item.get("pop"),
                rain_amount=rain_data.get("1h")
                if isinstance(rain_data, dict)
                else None,
                snow_amount=snow_data.get("1h")
                if isinstance(snow_data, dict)
                else None,
                weather_id=weather.get("id"),
                weather_main=weather.get("main"),
                weather_description=weather.get("description"),
                sunrise=parse_timestamp(item["sunrise"])
                if "sunrise" in item
                else None,
                sunset=parse_timestamp(item["sunset"])
                if "sunset" in item
                else None,
            )

        lat = data["lat"]
        lon = data["lon"]
        tz = data.get("timezone")
        tz_offset = data.get("timezone_offset")

        current = convert_weather_item(
            data["current"], lat, lon, tz, tz_offset
        )

        hourly = [
            convert_weather_item(h, lat, lon, tz, tz_offset)
            for h in data.get("hourly", [])
        ]

        return WeatherForecast(current=current, hourly=hourly)

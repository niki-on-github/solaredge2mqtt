from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_serializer

from solaredge2mqtt.core.models import Solaredge2MQTTBaseModel


class WeatherData(Solaredge2MQTTBaseModel):
    """Unified weather data model for both OpenWeatherMap and MET Norway.

    This model normalizes data from both providers into a common format
    for ML training and MQTT publishing.
    """

    # Location and time
    latitude: float
    longitude: float
    timestamp: datetime = Field(alias="dt")
    timezone: str | None = None
    timezone_offset: int | None = None

    # Temperature
    temperature: float | None = None  # temp (OWM) / air_temperature (MET)
    feels_like: float | None = None  # Only available in OWM
    dew_point: float | None = None

    # Atmospheric conditions
    pressure: int | None = None  # sea level pressure
    humidity: int | None = None  # relative humidity (%)
    cloud_coverage: int | None = None  # clouds (%) / cloud_area_fraction (%)
    visibility: int | None = None  # Only available in OWM (meters)
    uv_index: float | None = None  # uvi / ultraviolet_index_clear_sky

    # Wind
    wind_speed: float | None = None  # m/s
    wind_direction: int | None = None  # degrees (0°=N, 90°=E)
    wind_gust: float | None = None  # m/s

    # Precipitation
    precipitation_probability: float | None = (
        None  # pop / probability_of_precipitation (0-1)
    )
    rain_amount: float | None = None  # mm (last hour)
    snow_amount: float | None = None  # mm (last hour)

    # Weather condition
    weather_id: int | None = None  # Mapped from symbol_code for MET
    weather_main: str | None = (
        None  # Main condition (Rain, Snow, Clouds, etc.)
    )
    weather_description: str | None = None

    # Sun (may be None for MET unless Sunrise API is used)
    sunrise: datetime | None = None
    sunset: datetime | None = None

    @property
    def localtime(self) -> datetime:
        return self.timestamp.astimezone()

    @property
    def year(self) -> int:
        return self.localtime.year

    @property
    def month(self) -> int:
        return self.localtime.month

    @property
    def day(self) -> int:
        return self.localtime.day

    @property
    def hour(self) -> int:
        return self.localtime.hour

    @field_serializer("timestamp")
    def serialize_timestamp(self, timestamp: datetime, _info) -> str:
        return timestamp.astimezone().isoformat()

    @field_serializer("sunrise")
    def serialize_sunrise(self, sunrise: datetime | None, _info) -> str | None:
        return sunrise.astimezone().isoformat() if sunrise else None

    @field_serializer("sunset")
    def serialize_sunset(self, sunset: datetime | None, _info) -> str | None:
        return sunset.astimezone().isoformat() if sunset else None

    def model_dump_estimation_data(self) -> dict[str, Any]:
        """Dump data in format expected by forecast ML models."""
        data = self.model_dump(
            exclude=[
                "weather_description",
                "sunrise",
                "sunset",
                "timezone",
                "timezone_offset",
            ],
            exclude_none=True,
        )

        # Rename fields to match expected ML feature names
        field_mapping = {
            "temperature": "temp",
            "cloud_coverage": "clouds",
            "precipitation_probability": "pop",
            "rain_amount": "rain",
            "snow_amount": "snow",
            "wind_direction": "wind_deg",
            "uv_index": "uvi",
        }

        for new_name, old_name in field_mapping.items():
            if new_name in data:
                data[old_name] = data.pop(new_name)

        return data


class WeatherForecast(Solaredge2MQTTBaseModel):
    """Complete weather forecast containing current conditions and hourly forecast."""

    current: WeatherData
    hourly: list[WeatherData]

    @property
    def latitude(self) -> float:
        return self.current.latitude

    @property
    def longitude(self) -> float:
        return self.current.longitude

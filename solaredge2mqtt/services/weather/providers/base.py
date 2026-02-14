from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from solaredge2mqtt.services.weather.models.unified import WeatherForecast

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings import ServiceSettings


class WeatherProvider(ABC):
    """Abstract base class for weather providers."""

    def __init__(self, settings: ServiceSettings) -> None:
        self.settings = settings
        self.provider_settings = settings.weather.get_provider_settings()

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        pass

    @abstractmethod
    async def fetch_weather(self) -> WeatherForecast:
        """Fetch weather data and return unified format."""
        pass

    @property
    def location(self):
        """Return location settings."""
        return self.settings.location

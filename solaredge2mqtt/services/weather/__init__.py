from __future__ import annotations

from typing import TYPE_CHECKING

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.core.timer.events import Interval10MinTriggerEvent
from solaredge2mqtt.services.weather.events import WeatherUpdateEvent
from solaredge2mqtt.services.weather.providers import (
    METNorwayProvider,
    OpenWeatherMapProvider,
    WeatherProvider,
)
from solaredge2mqtt.services.weather.settings import WeatherProviderEnum

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings import ServiceSettings


class WeatherService:
    """Weather service that supports multiple providers."""

    def __init__(self, settings: ServiceSettings, event_bus: EventBus) -> None:
        if settings.weather is None:
            raise InvalidDataException("Weather settings not configured")

        self.settings = settings.weather
        self.event_bus = event_bus
        self.provider = self._create_provider(settings)
        self._subscribe_events()

    def _create_provider(self, settings: ServiceSettings) -> WeatherProvider:
        """Factory method to create the appropriate provider."""
        if self.settings.provider == WeatherProviderEnum.OPENWEATHERMAP:
            return OpenWeatherMapProvider(settings)
        elif self.settings.provider == WeatherProviderEnum.METNO:
            return METNorwayProvider(settings)
        else:
            raise ValueError(
                f"Unknown weather provider: {self.settings.provider}"
            )

    def _subscribe_events(self):
        self.event_bus.subscribe(Interval10MinTriggerEvent, self.loop)

    async def loop(self, _):
        weather = await self.provider.fetch_weather()
        await self.event_bus.emit(WeatherUpdateEvent(weather))
        await self.event_bus.emit(
            MQTTPublishEvent(
                "weather/current",
                weather.current,
                self.settings.retain,
            )
        )


# Keep backward compatibility - WeatherClient is now WeatherService
WeatherClient = WeatherService

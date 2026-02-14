from __future__ import annotations

import asyncio
import traceback
from typing import TYPE_CHECKING

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
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
        self._task: asyncio.Task | None = None

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

    def start(self):
        """Start the weather polling loop."""
        self._task = asyncio.create_task(self._run_loop())

    def stop(self):
        """Stop the weather polling loop."""
        if self._task and not self._task.done():
            self._task.cancel()

    async def _run_loop(self):
        """Run the weather polling loop with configurable interval."""
        interval_seconds = self.settings.interval * 60
        while True:
            try:
                await self._fetch_and_publish()
            except Exception as e:
                logger.error(
                    f"Error fetching weather data: {e}\n{traceback.format_exc()}"
                )
            await asyncio.sleep(interval_seconds)

    async def _fetch_and_publish(self):
        """Fetch weather data and publish events."""
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

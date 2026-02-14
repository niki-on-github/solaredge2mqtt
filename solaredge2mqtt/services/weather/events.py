from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.services.weather.models import WeatherForecast


class WeatherUpdateEvent(BaseEvent):
    """Event emitted when weather data is updated from any provider."""

    def __init__(self, weather: WeatherForecast) -> None:
        self._weather = weather

    @property
    def weather(self) -> WeatherForecast:
        return self._weather

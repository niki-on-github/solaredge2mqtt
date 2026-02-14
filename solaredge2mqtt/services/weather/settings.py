from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, SecretStr, model_validator


class WeatherProviderEnum(str, Enum):
    """Available weather providers."""

    OPENWEATHERMAP = "openweathermap"
    METNO = "metno"


class OpenWeatherMapSettings(BaseModel):
    """OpenWeatherMap specific settings."""

    api_key: SecretStr | None = Field(None)
    language: str = Field("en")

    @property
    def is_configured(self) -> bool:
        return self.api_key is not None


class METNorwaySettings(BaseModel):
    """MET Norway specific settings."""

    user_agent: str | None = Field(
        None,
        description="Custom User-Agent header. Recommended to identify your application.",
    )

    @property
    def is_configured(self) -> bool:
        # MET Norway doesn't require configuration, but User-Agent is recommended
        return True


class WeatherSettings(BaseModel):
    """Weather service configuration supporting multiple providers."""

    provider: WeatherProviderEnum = Field(
        WeatherProviderEnum.OPENWEATHERMAP, description="Weather data provider"
    )

    # Provider-specific settings
    openweathermap: OpenWeatherMapSettings = Field(
        default_factory=OpenWeatherMapSettings
    )
    metno: METNorwaySettings = Field(default_factory=METNorwaySettings)

    # Common settings
    retain: bool = Field(False)

    @model_validator(mode="after")
    def validate_provider_config(self) -> "WeatherSettings":
        """Validate that the selected provider is properly configured."""
        if self.provider == WeatherProviderEnum.OPENWEATHERMAP:
            if not self.openweathermap.is_configured:
                raise ValueError(
                    "OpenWeatherMap provider selected but api_key is not configured. "
                    "Please set weather.openweathermap.api_key"
                )
        return self

    @property
    def is_configured(self) -> bool:
        """Check if weather service is properly configured."""
        if self.provider == WeatherProviderEnum.OPENWEATHERMAP:
            return self.openweathermap.is_configured
        elif self.provider == WeatherProviderEnum.METNO:
            return self.metno.is_configured
        return False

    def get_provider_settings(
        self,
    ) -> OpenWeatherMapSettings | METNorwaySettings:
        """Get settings for the selected provider."""
        if self.provider == WeatherProviderEnum.OPENWEATHERMAP:
            return self.openweathermap
        elif self.provider == WeatherProviderEnum.METNO:
            return self.metno
        raise ValueError(f"Unknown provider: {self.provider}")

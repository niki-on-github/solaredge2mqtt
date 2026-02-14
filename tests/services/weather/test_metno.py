"""Tests for MET Norway weather provider."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientResponseError, RequestInfo

from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.services.weather.providers.metno import (
    METNorwayProvider,
    map_symbol_code,
)


@pytest.fixture
def mock_service_settings_metno():
    """Create mock service settings for MET Norway."""
    settings = MagicMock()
    settings.location = MagicMock()
    settings.location.latitude = 52.52
    settings.location.longitude = 13.405
    settings.location.altitude = None

    settings.weather = MagicMock()
    settings.weather.provider = "metno"
    settings.weather.retain = False
    settings.weather.interval = 10
    settings.weather.get_provider_settings.return_value = MagicMock()
    settings.weather.get_provider_settings.return_value.user_agent = (
        "TestApp/1.0"
    )

    return settings


@pytest.fixture
def mock_metno_response():
    """Create mock MET Norway API response."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [13.405, 52.52, 0],
        },
        "properties": {
            "meta": {
                "updated_at": "2024-01-15T12:00:00Z",
                "units": {
                    "air_pressure_at_sea_level": "hPa",
                    "air_temperature": "celsius",
                    "cloud_area_fraction": "%",
                    "precipitation_amount": "mm",
                    "relative_humidity": "%",
                    "wind_from_direction": "degrees",
                    "wind_speed": "m/s",
                },
            },
            "timeseries": [
                {
                    "time": "2024-01-15T12:00:00Z",
                    "data": {
                        "instant": {
                            "details": {
                                "air_pressure_at_sea_level": 1013,
                                "air_temperature": 5.5,
                                "cloud_area_fraction": 75.0,
                                "dew_point_temperature": 2.5,
                                "relative_humidity": 80,
                                "ultraviolet_index_clear_sky": 0.5,
                                "wind_from_direction": 220,
                                "wind_speed": 5.5,
                                "wind_speed_of_gust": 10.2,
                            }
                        },
                        "next_1_hours": {
                            "summary": {"symbol_code": "cloudy"},
                            "details": {"precipitation_amount": 0.0},
                        },
                    },
                },
                {
                    "time": "2024-01-15T13:00:00Z",
                    "data": {
                        "instant": {
                            "details": {
                                "air_pressure_at_sea_level": 1012,
                                "air_temperature": 6.0,
                                "cloud_area_fraction": 80.0,
                                "dew_point_temperature": 3.0,
                                "relative_humidity": 82,
                                "wind_from_direction": 225,
                                "wind_speed": 6.0,
                            }
                        },
                        "next_1_hours": {
                            "summary": {"symbol_code": "rain"},
                            "details": {"precipitation_amount": 1.2},
                        },
                    },
                },
            ],
        },
    }


class TestMapSymbolCode:
    """Tests for symbol code mapping function."""

    def test_map_clearsky_day(self):
        """Test mapping clear sky day symbol."""
        result = map_symbol_code("clearsky_day")
        assert result["id"] == 800
        assert result["main"] == "Clear"

    def test_map_rain(self):
        """Test mapping rain symbol."""
        result = map_symbol_code("rain")
        assert result["id"] == 500
        assert result["main"] == "Rain"

    def test_map_snow(self):
        """Test mapping snow symbol."""
        result = map_symbol_code("snow")
        assert result["id"] == 601
        assert result["main"] == "Snow"

    def test_map_unknown_symbol(self):
        """Test mapping unknown symbol falls back to default."""
        result = map_symbol_code("unknown_symbol")
        assert result["id"] == 800
        assert result["main"] == "Clear"

    def test_map_none_symbol(self):
        """Test mapping None symbol falls back to default."""
        result = map_symbol_code(None)
        assert result["id"] == 800
        assert result["main"] == "Clear"


class TestMETNorwayProviderInit:
    """Tests for METNorwayProvider initialization."""

    def test_provider_init(self, mock_service_settings_metno):
        """Test METNorwayProvider initialization."""
        provider = METNorwayProvider(mock_service_settings_metno)

        assert provider.location is mock_service_settings_metno.location
        assert provider.name == "metno"

    def test_provider_headers_with_user_agent(
        self, mock_service_settings_metno
    ):
        """Test headers include User-Agent when configured."""
        provider = METNorwayProvider(mock_service_settings_metno)
        headers = provider._get_headers()

        assert "User-Agent" in headers
        assert headers["User-Agent"] == "TestApp/1.0"

    def test_provider_headers_without_user_agent(
        self, mock_service_settings_metno
    ):
        """Test headers are empty when User-Agent not configured."""
        mock_service_settings_metno.weather.get_provider_settings.return_value.user_agent = None
        provider = METNorwayProvider(mock_service_settings_metno)
        headers = provider._get_headers()

        assert headers == {}


class TestMETNorwayProviderFetchWeather:
    """Tests for METNorwayProvider fetch_weather."""

    @pytest.mark.asyncio
    async def test_fetch_weather_success(
        self, mock_service_settings_metno, mock_metno_response
    ):
        """Test successful weather retrieval from MET Norway."""
        provider = METNorwayProvider(mock_service_settings_metno)
        provider._get = AsyncMock(return_value=mock_metno_response)

        result = await provider.fetch_weather()

        assert result.current is not None
        assert result.current.latitude == 52.52
        assert result.current.longitude == 13.405
        assert result.current.temperature == 5.5
        assert result.current.weather_main == "Clouds"
        assert len(result.hourly) == 1

    @pytest.mark.asyncio
    async def test_fetch_weather_params_no_altitude(
        self, mock_service_settings_metno, mock_metno_response
    ):
        """Test that altitude is NOT included in API request params."""
        provider = METNorwayProvider(mock_service_settings_metno)
        provider._get = AsyncMock(return_value=mock_metno_response)

        await provider.fetch_weather()

        # Check that _get was called with correct params (no altitude)
        call_args = provider._get.call_args
        params = call_args[1]["params"]

        assert "lat" in params
        assert "lon" in params
        assert "altitude" not in params
        assert params["lat"] == 52.52
        assert params["lon"] == 13.405

    @pytest.mark.asyncio
    async def test_fetch_weather_none_response(
        self, mock_service_settings_metno
    ):
        """Test fetch_weather raises when response is None."""
        provider = METNorwayProvider(mock_service_settings_metno)
        provider._get = AsyncMock(return_value=None)

        with pytest.raises(InvalidDataException) as exc_info:
            await provider.fetch_weather()

        assert "Unable to read weather data" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_fetch_weather_403_error(self, mock_service_settings_metno):
        """Test fetch_weather handles 403 error (missing User-Agent)."""
        provider = METNorwayProvider(mock_service_settings_metno)

        mock_request_info = MagicMock(spec=RequestInfo)
        mock_request_info.real_url = "https://api.met.no/"

        error = ClientResponseError(
            request_info=mock_request_info,
            history=(),
            status=403,
        )
        provider._get = AsyncMock(side_effect=error)

        with pytest.raises(InvalidDataException) as exc_info:
            await provider.fetch_weather()

        assert "User-Agent" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_fetch_weather_other_http_error(
        self, mock_service_settings_metno
    ):
        """Test fetch_weather handles other HTTP errors."""
        provider = METNorwayProvider(mock_service_settings_metno)

        mock_request_info = MagicMock(spec=RequestInfo)
        mock_request_info.real_url = "https://api.met.no/"

        error = ClientResponseError(
            request_info=mock_request_info,
            history=(),
            status=500,
        )
        provider._get = AsyncMock(side_effect=error)

        with pytest.raises(InvalidDataException) as exc_info:
            await provider.fetch_weather()

        assert "Unable to read weather data" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_fetch_weather_timeout(self, mock_service_settings_metno):
        """Test fetch_weather handles timeout."""
        provider = METNorwayProvider(mock_service_settings_metno)
        provider._get = AsyncMock(side_effect=asyncio.TimeoutError())

        with pytest.raises(InvalidDataException) as exc_info:
            await provider.fetch_weather()

        assert "timeout" in exc_info.value.message


class TestMETNorwayConvertToUnified:
    """Tests for _convert_to_unified method."""

    @pytest.mark.asyncio
    async def test_convert_rain_precipitation(
        self, mock_service_settings_metno, mock_metno_response
    ):
        """Test rain precipitation is correctly identified."""
        # Modify response to have rain
        mock_metno_response["properties"]["timeseries"][0]["data"][
            "next_1_hours"
        ]["summary"]["symbol_code"] = "rain"
        mock_metno_response["properties"]["timeseries"][0]["data"][
            "next_1_hours"
        ]["details"]["precipitation_amount"] = 2.5

        provider = METNorwayProvider(mock_service_settings_metno)
        provider._get = AsyncMock(return_value=mock_metno_response)

        result = await provider.fetch_weather()

        assert result.current.rain_amount == 2.5
        assert result.current.snow_amount is None

    @pytest.mark.asyncio
    async def test_convert_snow_precipitation(
        self, mock_service_settings_metno, mock_metno_response
    ):
        """Test snow precipitation is correctly identified."""
        # Modify response to have snow
        mock_metno_response["properties"]["timeseries"][0]["data"][
            "next_1_hours"
        ]["summary"]["symbol_code"] = "snow"
        mock_metno_response["properties"]["timeseries"][0]["data"][
            "next_1_hours"
        ]["details"]["precipitation_amount"] = 5.0

        provider = METNorwayProvider(mock_service_settings_metno)
        provider._get = AsyncMock(return_value=mock_metno_response)

        result = await provider.fetch_weather()

        assert result.current.snow_amount == 5.0
        assert result.current.rain_amount is None

    @pytest.mark.asyncio
    async def test_convert_empty_timeseries(
        self, mock_service_settings_metno, mock_metno_response
    ):
        """Test empty timeseries raises error."""
        mock_metno_response["properties"]["timeseries"] = []

        provider = METNorwayProvider(mock_service_settings_metno)
        provider._get = AsyncMock(return_value=mock_metno_response)

        with pytest.raises(InvalidDataException) as exc_info:
            await provider.fetch_weather()

        assert "No weather data available" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_convert_missing_symbol_code(
        self, mock_service_settings_metno, mock_metno_response
    ):
        """Test handling missing symbol code (uses default)."""
        # Remove symbol_code from response
        del mock_metno_response["properties"]["timeseries"][0]["data"][
            "next_1_hours"
        ]["summary"]["symbol_code"]

        provider = METNorwayProvider(mock_service_settings_metno)
        provider._get = AsyncMock(return_value=mock_metno_response)

        result = await provider.fetch_weather()

        # Should use default mapping
        assert result.current.weather_id == 800
        assert result.current.weather_main == "Clear"

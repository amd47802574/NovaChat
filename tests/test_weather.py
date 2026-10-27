from __future__ import annotations

import unittest

import requests
from unittest.mock import Mock, patch

from backend.tools.weather import (
    OPEN_METEO_FORECAST_API,
    OPEN_METEO_GEOCODING_API,
    UAPIS_WEATHER_API,
    get_current_weather,
)


class WeatherToolTests(unittest.TestCase):
    def test_primary_weather_source_success(self) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "province": "广东省",
            "city": "深圳市",
            "weather": "多云",
            "temperature": 29,
            "humidity": 80,
            "wind_direction": "东南风",
            "wind_power": "2级",
            "report_time": "刚刚发布",
        }

        with patch("backend.tools.weather.requests.get", return_value=response) as request_get:
            result = get_current_weather("深圳")

        self.assertIn("广东省深圳市", result)
        self.assertIn("多云", result)
        self.assertEqual(request_get.call_args.args[0], UAPIS_WEATHER_API)

    def test_fallback_to_open_meteo_when_primary_fails(self) -> None:
        primary_response = Mock()
        primary_response.raise_for_status.side_effect = requests.RequestException("主源异常")

        geocoding_response = Mock()
        geocoding_response.raise_for_status.return_value = None
        geocoding_response.json.return_value = {
            "results": [{
                "name": "深圳",
                "admin1": "广东",
                "latitude": 22.54,
                "longitude": 114.06,
            }]
        }

        forecast_response = Mock()
        forecast_response.raise_for_status.return_value = None
        forecast_response.json.return_value = {
            "current": {
                "time": "2026-08-26T19:30",
                "temperature_2m": 26.6,
                "relative_humidity_2m": 92,
                "weather_code": 95,
                "wind_speed_10m": 8.5,
                "wind_direction_10m": 174,
            }
        }

        def request_side_effect(url, **kwargs):
            if url == UAPIS_WEATHER_API:
                return primary_response
            if url == OPEN_METEO_GEOCODING_API:
                return geocoding_response
            if url == OPEN_METEO_FORECAST_API:
                return forecast_response
            raise AssertionError(f"未知 URL：{url}")

        with patch("backend.tools.weather.requests.get", side_effect=request_side_effect):
            result = get_current_weather("深圳")

        self.assertIn("广东深圳", result)
        self.assertIn("雷暴", result)
        self.assertIn("Open-Meteo（备用）", result)


if __name__ == "__main__":
    unittest.main()

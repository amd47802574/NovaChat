import logging
from typing import Any

import requests

try:
    from langchain_core.tools import tool
except ImportError:
    from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# 主天气源：免费接口，无需 API Key。
UAPIS_WEATHER_API = "https://uapis.cn/api/v1/misc/weather"

# 备用天气源：Open-Meteo 免费接口，无需 API Key。
OPEN_METEO_GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_API = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODE_TEXT = {
    0: "晴",
    1: "大部晴朗",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "小毛毛雨",
    53: "毛毛雨",
    55: "强毛毛雨",
    56: "轻微冻毛毛雨",
    57: "强冻毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "轻微冻雨",
    67: "强冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "米雪",
    80: "小阵雨",
    81: "中阵雨",
    82: "强阵雨",
    85: "小阵雪",
    86: "强阵雪",
    95: "雷暴",
    96: "雷暴伴小冰雹",
    99: "雷暴伴强冰雹",
}


def _format_uapis_weather(city: str, data: dict[str, Any]) -> str | None:
    """校验并格式化主天气源响应。"""
    if not data or "city" not in data or "weather" not in data:
        return None

    region = data.get("city", city)
    if data.get("province"):
        region = f"{data.get('province')}{region}"
    if data.get("district"):
        region = f"{region}{data.get('district')}"

    return "\n".join([
        f"【{region} 实时天气】",
        f"天气状况：{data.get('weather', '未知')}",
        f"温度：{data.get('temperature', '未知')}℃",
        f"湿度：{data.get('humidity', '未知')}%",
        f"风向：{data.get('wind_direction', '未知')}",
        f"风力：{data.get('wind_power', '未知')}",
        f"更新时间：{data.get('report_time', '未知')}",
    ])


def _wind_direction_from_degrees(degrees: Any) -> str:
    """把风向角度转换为中文方位。"""
    try:
        normalized = float(degrees) % 360
    except (TypeError, ValueError):
        return "未知"
    directions = ("北风", "东北风", "东风", "东南风", "南风", "西南风", "西风", "西北风")
    index = int((normalized + 22.5) // 45) % len(directions)
    return directions[index]


def _get_open_meteo_weather(city: str) -> str:
    """通过 Open-Meteo 查询城市坐标与实时天气。"""
    geocoding_response = requests.get(
        OPEN_METEO_GEOCODING_API,
        params={
            "name": city,
            "count": 1,
            "language": "zh",
            "countryCode": "CN",
            "format": "json",
        },
        timeout=10,
    )
    geocoding_response.raise_for_status()
    geocoding_data = geocoding_response.json()
    locations = geocoding_data.get("results") or []
    if not locations:
        raise ValueError(f"未找到城市 {city} 的地理位置")

    location = locations[0]
    forecast_response = requests.get(
        OPEN_METEO_FORECAST_API,
        params={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current": (
                "temperature_2m,relative_humidity_2m,weather_code,"
                "wind_speed_10m,wind_direction_10m"
            ),
            "timezone": "auto",
        },
        timeout=10,
    )
    forecast_response.raise_for_status()
    forecast_data = forecast_response.json()
    current = forecast_data.get("current") or {}
    if "temperature_2m" not in current or "weather_code" not in current:
        raise ValueError("备用天气源未返回实时天气数据")

    province = location.get("admin1") or ""
    city_name = location.get("name") or city
    region = f"{province}{city_name}"
    weather_code = current.get("weather_code")
    weather_text = WEATHER_CODE_TEXT.get(weather_code, f"天气代码 {weather_code}")
    wind_direction = _wind_direction_from_degrees(current.get("wind_direction_10m"))

    return "\n".join([
        f"【{region} 实时天气】",
        f"天气状况：{weather_text}",
        f"温度：{current.get('temperature_2m', '未知')}℃",
        f"湿度：{current.get('relative_humidity_2m', '未知')}%",
        f"风向：{wind_direction}",
        f"风速：{current.get('wind_speed_10m', '未知')} km/h",
        f"更新时间：{current.get('time', '未知')}",
        "数据源：Open-Meteo（备用）",
    ])


def get_current_weather(city: str) -> str:
    """获取中国城市实时天气，主天气源失败时自动使用备用源。"""
    if not city or not city.strip():
        return "错误：city 参数不能为空"

    normalized_city = city.strip()
    primary_error = ""
    try:
        response = requests.get(
            UAPIS_WEATHER_API,
            params={"city": normalized_city},
            timeout=8,
        )
        response.raise_for_status()
        result = _format_uapis_weather(normalized_city, response.json())
        if result:
            return result
        primary_error = "主天气源返回数据不完整"
    except requests.exceptions.RequestException as exc:
        primary_error = f"主天气源请求失败：{exc}"
    except (TypeError, ValueError) as exc:
        primary_error = f"主天气源数据解析失败：{exc}"

    logger.warning("%s，正在切换备用天气源", primary_error)
    try:
        return _get_open_meteo_weather(normalized_city)
    except requests.exceptions.RequestException as exc:
        fallback_error = f"备用天气源请求失败：{exc}"
    except (KeyError, TypeError, ValueError) as exc:
        fallback_error = f"备用天气源数据解析失败：{exc}"

    logger.error("天气查询全部失败：%s；%s", primary_error, fallback_error)
    return f"错误：天气查询失败（{primary_error}；{fallback_error}）"


@tool("get_current_weather")
def get_current_weather_tool(city: str) -> str:
    """获取中国某城市的实时天气。主天气源异常时会自动使用备用源。"""
    return get_current_weather(city)

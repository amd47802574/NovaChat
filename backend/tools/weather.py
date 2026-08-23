import requests

try:
    from langchain_core.tools import tool
except ImportError:
    from langchain_core.tools import tool

# uapis.cn 公共天气接口（免费，无需 API Key）
UAPIS_WEATHER_API = "https://uapis.cn/api/v1/misc/weather"


def get_current_weather(city: str) -> str:
    """获取天气信息"""
    if not city or not city.strip():
        return "city 参数不能为空"

    params = {"city": city.strip()}

    try:
        resp = requests.get(UAPIS_WEATHER_API, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # 成功响应应包含 city / weather 字段
        if not data or "city" not in data or "weather" not in data:
            return f"未查询到 {city} 的天气数据"

        region = data.get("city", city)
        if data.get("province"):
            region = f"{data.get('province')}{region}"
        if data.get("district"):
            region = f"{region}{data.get('district')}"

        return (
            f"【{region} 实时天气】\n"
            f"天气状况：{data.get('weather', '未知')}\n"
            f"温度：{data.get('temperature', '未知')}℃\n"
            f"湿度：{data.get('humidity', '未知')}%\n"
            f"风向：{data.get('wind_direction', '未知')}\n"
            f"风力：{data.get('wind_power', '未知')}\n"
            f"更新时间：{data.get('report_time', '未知')}"
        )

    except requests.exceptions.Timeout:
        return "错误：请求天气服务超时"
    except requests.exceptions.RequestException as e:
        return f"错误：天气服务请求失败 - {e}"
    except Exception as e:
        return f"错误：解析天气数据失败 - {e}"


@tool("get_current_weather")
def get_current_weather_tool(city: str) -> str:
    """获取中国某城市的实时天气。"""
    return get_current_weather(city)

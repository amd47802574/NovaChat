"""当前时间工具"""
from datetime import datetime
from typing import Optional

try:
    from langchain_core.tools import tool
except ImportError:
    from langchain_core.tools import tool

try:
    import pytz
    HAS_PYTZ = True
except ImportError:
    HAS_PYTZ = False


@tool("get_current_time")
def get_current_time(timezone: Optional[str] = "Asia/Shanghai") -> str:
    """
    获取指定时区的当前日期、时间和星期。
    当用户询问当前时间、日期或需要与时间相关的信息时使用此工具。

    Args:
        timezone: 时区名称（例如 'Asia/Shanghai'、'America/New_York'、'Europe/London'）。
                  默认为 'Asia/Shanghai'（北京时间）。

    Returns:
        包含当前日期、时间和星期的格式化字符串。
    """
    try:
        # Define weekday names
        weekday_names = {
            0: "星期一", 1: "星期二", 2: "星期三", 
            3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"
        }
        
        # Get current time
        if HAS_PYTZ and timezone:
            try:
                tz = pytz.timezone(timezone)
                now = datetime.now(tz)
                tz_name = tz.zone
            except Exception:
                # Fallback to local time if timezone is invalid
                now = datetime.now()
                tz_name = "本地时间"
        else:
            now = datetime.now()
            tz_name = "本地时间"
        
        # Format output
        output = (
            f"当前时间信息\n"
            f"时间：{now.strftime('%H:%M:%S')}\n"
            f"日期：{now.strftime('%Y年%m月%d日')}\n"
            f"星期：{weekday_names[now.weekday()]}\n"
            f"时区：{tz_name}"
        )
        
        return output
        
    except Exception as e:
        return f"获取时间失败：{str(e)}"
"""东八区（UTC+8）时区单一基准。

项目全局时间约定：
- 所有「当前时间」的生成都必须经过本模块，禁止在业务代码里散落 ``datetime.utcnow()``
  / ``datetime.now()`` 等不显式带时区的调用，确保基准时区唯一且明确为东八区。
- 落库（PostgreSQL ``TIMESTAMP`` 无时区列）统一以「东八区朴素时间」存储，即把东八区
  的年月日时分秒直接写入，不携带时区偏移；这样物理存储值本身就是北京时间。
- 所有对外输出的时间字符串统一带 ``+08:00`` 偏移（ISO 8601），前端据此显式按东八区展示，
  无论浏览器/服务器身处哪个时区都不会偏差。

历史数据：早期版本以 UTC 朴素时间落库，``database.init_db`` 在首次启动时会对存量数据
执行一次性 ``+8 小时`` 迁移（见 ``database._ensure_utc8_timezone_migration``），迁移后
全库时间即统一为东八区基准。
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# 东八区时区（Asia/Shanghai），是所有时间换算的唯一基准。
BEIJING_TZ = ZoneInfo("Asia/Shanghai")

# 兼容别名，语义更直白。
UTC8_TZ = BEIJING_TZ


def now_utc8() -> datetime:
    """当前东八区（UTC+8）时间，带时区信息。供展示、计算、瞬时标记使用。"""
    return datetime.now(BEIJING_TZ)


def now_for_db() -> datetime:
    """落库使用的当前时间：以东八区为基准，去时区后以朴素时间写入。

    物理存储值即为北京时间（例如北京时间 2024-01-01 10:00 直接存为 2024-01-01 10:00），
    与既有 ``TIMESTAMP`` 列（无时区）完全兼容，且全库统一。
    """
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)


def as_utc8(dt: datetime | None) -> datetime | None:
    """把（可能朴素、假定为东八区的）时间规整为带东八区时区的时间。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # 库中以朴素时间存储，物理值即为东八区墙钟时间。
        return dt.replace(tzinfo=BEIJING_TZ)
    return dt.astimezone(BEIJING_TZ)


def to_utc8_iso(dt: datetime | None) -> str | None:
    """序列化为东八区 ISO 字符串（含 ``+08:00`` 偏移），用于对外输出。

    朴素时间按东八区墙钟解释（与落库约定一致）；带时区时间则换算到东八区。
    """
    converted = as_utc8(dt)
    return converted.isoformat() if converted is not None else None


def utc8_now_iso() -> str:
    """当前东八区时间的 ISO 字符串（含 ``+08:00`` 偏移）。"""
    return now_utc8().isoformat()

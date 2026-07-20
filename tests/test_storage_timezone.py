import importlib
import unittest
from datetime import datetime, timezone

storage_module = importlib.import_module("backend.chat.storage")
_isoformat_utc = storage_module._isoformat_utc


class IsoformatUtcTest(unittest.TestCase):
    """校验时间戳序列化统一带上 UTC 时区标记，避免前端东8区少算 8 小时。"""

    def test_naive_datetime_gets_utc_marker(self):
        # 数据库里以 naive UTC 存储（datetime.utcnow），序列化后必须带上 +00:00 标记。
        naive = datetime(2026, 7, 20, 8, 30, 0)
        result = _isoformat_utc(naive)

        self.assertEqual(result, "2026-07-20T08:30:00+00:00")
        # 前端 new Date() 解析该字符串应还原为同一时刻的 UTC 时间。
        self.assertEqual(
            datetime.fromisoformat(result).astimezone(timezone.utc),
            naive.replace(tzinfo=timezone.utc),
        )

    def test_aware_datetime_preserves_instant(self):
        # 已带时区的时间戳不应被改写为另一时刻。
        aware = datetime(2026, 7, 20, 8, 30, 0, tzinfo=timezone.utc)
        result = _isoformat_utc(aware)

        self.assertEqual(datetime.fromisoformat(result), aware)


if __name__ == "__main__":
    unittest.main()

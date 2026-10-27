"""从项目根目录加载 .env；由应用入口或独立脚本在 import 其它 backend 模块前调用一次。"""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOADED = False


def load_env() -> None:
    global _LOADED
    if _LOADED:
        return
    load_dotenv(PROJECT_ROOT / ".env")
    # 模型已下载到本地缓存后，默认走离线模式，避免 HuggingFaceEmbeddings 实例化时
    # 联网检查模型更新导致启动卡死（连接 hf-mirror.com 或 huggingface.co 超时）。
    # 如需下载新模型，在 .env 中设置 HF_HUB_OFFLINE=0 或临时删除此行。
    if "HF_HUB_OFFLINE" not in os.environ:
        os.environ["HF_HUB_OFFLINE"] = "1"
    _LOADED = True

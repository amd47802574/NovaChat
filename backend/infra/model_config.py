"""模型配置（存储于 .env）的读取、写入、校验与生效。

涉及 5 个配置项：
- ARK_API_KEY        ：大模型服务商的 API 密钥（敏感信息，不回显明文）
- BASE_URL           ：OpenAI 兼容接口地址
- MODEL              ：通用主力模型
- GRADE_MODEL        ：打分/评测用高精度模型
- FAST_MODEL         ：快速低成本轻量模型（留空则回退到 MODEL）

设计要点：
- 读取以 .env 文件为权威来源，写回时尽量保留注释与原有其它配置。
- 敏感字段（API Key）读取时仅告知「是否已配置」，不返回明文；
  写入时仅当传入非空新值才覆盖，传空表示沿用现有值。
- 「生效」= 把新值写入 .env 并刷新运行进程内的模型单例，无需重启即可对新请求生效。
"""
import os
import re
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

from backend.env import PROJECT_ROOT

# 受本模块管理的配置键（顺序即写入/展示顺序）
CONFIG_KEYS = ("ARK_API_KEY", "BASE_URL", "MODEL", "GRADE_MODEL", "FAST_MODEL")

# 前端展示所需的字段元信息：用途说明、是否为敏感字段、是否必填。
MODEL_CONFIG_FIELDS: List[Dict[str, object]] = [
    {
        "key": "ARK_API_KEY",
        "label": "API 密钥（ARK_API_KEY）",
        "description": "大模型服务商的 API Key，用于接口身份认证。属于敏感信息，"
        "页面仅显示是否已配置，不会明文回显；留空表示沿用当前值。",
        "is_secret": True,
        "required": True,
    },
    {
        "key": "BASE_URL",
        "label": "API 地址（BASE_URL）",
        "description": "大模型服务的 OpenAI 兼容接口地址（例如 https://api.deepseek.com/v1）。"
        "对话、检索与评测请求均通过该地址发起。",
        "is_secret": False,
        "required": True,
    },
    {
        "key": "MODEL",
        "label": "通用主力模型（MODEL）",
        "description": "日常对话与知识库问答使用的高性价比主力模型，承担绝大多数推理任务。",
        "is_secret": False,
        "required": True,
    },
    {
        "key": "GRADE_MODEL",
        "label": "打分/评测模型（GRADE_MODEL）",
        "description": "用于 RAG 证据评分、答案质量评测等高精度场景的强模型，要求结果稳定可靠。",
        "is_secret": False,
        "required": True,
    },
    {
        "key": "FAST_MODEL",
        "label": "快速轻量模型（FAST_MODEL）",
        "description": "用于问题复杂度分类、子问题分解等高频轻量任务的低成本快速模型；"
        "留空则自动回退到通用主力模型。",
        "is_secret": False,
        "required": False,
    },
]

_ENV_PATH = PROJECT_ROOT / ".env"
_ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"

# 内存中记录最近一次「生效」时间（进程重启后归零，仅作即时反馈用途）。
_last_applied_at: str | None = None


def _read_env_lines() -> List[str]:
    """读取 .env 原始行；文件不存在时尝试以 .env.example 作为基础，避免写到空文件破坏其它配置。"""
    if _ENV_PATH.exists():
        with open(_ENV_PATH, encoding="utf-8") as f:
            return f.read().splitlines()
    if _ENV_EXAMPLE_PATH.exists():
        with open(_ENV_EXAMPLE_PATH, encoding="utf-8") as f:
            return f.read().splitlines()
    return []


def _parse_env() -> Dict[str, str]:
    """解析 .env 中的键值（仅取首个等号分隔的活跃赋值行，注释行忽略）。"""
    result: Dict[str, str] = {}
    for line in _read_env_lines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$", stripped)
        if m:
            result[m.group(1)] = m.group(2).strip()
    return result


def get_model_config() -> List[Dict[str, object]]:
    """返回当前配置（含展示元信息）。

    敏感字段（API Key）不回显明文：value 固定为空字符串，is_set 指示是否已配置。
    """
    env = _parse_env()
    out: List[Dict[str, object]] = []
    for meta in MODEL_CONFIG_FIELDS:
        key = meta["key"]  # type: ignore[assignment]
        raw = env.get(key, "")
        is_secret = bool(meta["is_secret"])
        out.append(
            {
                "key": key,
                "label": meta["label"],
                "description": meta["description"],
                "is_secret": is_secret,
                "required": bool(meta["required"]),
                "is_set": bool(raw),
                "value": "" if is_secret else raw,
            }
        )
    return out


def _validate(values: Dict[str, str], existing: Dict[str, str]) -> Dict[str, str]:
    """校验前端提交的值，返回 {field_label: error_message}。

    values 键为友好字段名（ark_api_key / base_url / model / grade_model / fast_model）。
    """
    errors: Dict[str, str] = {}

    # BASE_URL 必须为合法 http/https 地址
    base_url = (values.get("base_url") or "").strip()
    if not base_url:
        errors["base_url"] = "API 地址不能为空"
    else:
        parsed = urlparse(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            errors["base_url"] = "必须是合法的 http(s) 地址，例如 https://api.deepseek.com/v1"

    # MODEL / GRADE_MODEL 必填且长度受限
    for field, label in (("model", "通用主力模型"), ("grade_model", "打分/评测模型")):
        val = (values.get(field) or "").strip()
        if not val:
            errors[field] = f"{label}不能为空"
        elif len(val) > 256:
            errors[field] = f"{label}长度不能超过 256 个字符"

    # FAST_MODEL 选填，但填写后同样约束长度
    fast = (values.get("fast_model") or "").strip()
    if fast and len(fast) > 256:
        errors["fast_model"] = "快速轻量模型长度不能超过 256 个字符"

    # ARK_API_KEY 必填：要么已有值，要么本次提交了新值
    new_key = (values.get("ark_api_key") or "").strip()
    if not new_key and not existing.get("ARK_API_KEY"):
        errors["ark_api_key"] = "API 密钥尚未配置，且本次未提供新值"
    elif new_key and len(new_key) < 8:
        errors["ark_api_key"] = "API 密钥长度过短，请检查是否完整粘贴"

    return errors


def save_model_config(values: Dict[str, str]) -> Dict[str, str]:
    """校验并落盘到 .env，返回校验错误（为空表示成功）。

    - 写回时保留注释与文件中其它配置项；缺失的键追加到末尾。
    - 敏感字段：仅当传入非空新值才覆盖，空值表示沿用现有值。
    - 成功写入后同步刷新 os.environ。
    """
    existing = _parse_env()
    errors = _validate(values, existing)
    if errors:
        return errors

    # 计算各键最终写入值
    to_write: Dict[str, str] = {}
    for meta in MODEL_CONFIG_FIELDS:
        key = meta["key"]  # type: ignore[assignment]
        if key == "ARK_API_KEY":
            new_key = (values.get("ark_api_key") or "").strip()
            # 空值 => 沿用现有；非空 => 覆盖
            to_write[key] = new_key if new_key else existing.get(key, "")
        elif key == "FAST_MODEL":
            # 允许显式设为空（回退到 MODEL）
            to_write[key] = (values.get("fast_model") or "").strip()
        else:
            to_write[key] = (values.get(key.lower()) or "").strip()

    _write_env_file(to_write)
    return {}


def _write_env_file(to_write: Dict[str, str]) -> None:
    lines = _read_env_lines()
    updated: set[str] = set()
    new_lines: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$", stripped)
            if m and m.group(1) in CONFIG_KEYS:
                key = m.group(1)
                new_lines.append(f"{key}={to_write.get(key, '')}")
                updated.add(key)
                continue
        new_lines.append(line)
    # 文件中缺失的受管键追加到末尾
    for key in CONFIG_KEYS:
        if key not in updated:
            new_lines.append(f"{key}={to_write.get(key, '')}")

    with open(_ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines).rstrip("\n") + "\n")

    # 同步刷新进程内环境变量，供后续「生效」读取
    for key in CONFIG_KEYS:
        os.environ[key] = to_write.get(key, "")


def apply_model_config() -> None:
    """把最新配置刷新到运行进程内的模型单例，无需重启即可对新请求生效。

    覆盖 chat.runtime（主对话模型）、rag.pipeline / rag.utils（评测与检索模型）、
    tools.text_analyzer（文本分析模型）。各模型实例的重建包裹在独立 try 中，
    即使某个模型构建失败也不影响其余配置落地。
    """
    global _last_applied_at
    from datetime import datetime

    from langchain.chat_models import init_chat_model

    from backend.chat import runtime as chat_runtime
    from backend.rag import pipeline as rag_pipeline
    from backend.rag import utils as rag_utils
    from backend.tools import text_analyzer as text_analyzer_mod

    api_key = os.getenv("ARK_API_KEY")
    base_url = os.getenv("BASE_URL")
    model = os.getenv("MODEL")
    grade_model = os.getenv("GRADE_MODEL") or "gpt-4.1"
    fast_model = os.getenv("FAST_MODEL") or model

    # ---- chat.runtime 主对话模型单例 ----
    chat_runtime.API_KEY = api_key
    chat_runtime.MODEL = model
    chat_runtime.FAST_MODEL = fast_model
    chat_runtime.BASE_URL = base_url
    if model:
        try:
            chat_runtime.model = init_chat_model(
                model=model,
                model_provider="openai",
                api_key=api_key,
                base_url=base_url,
                temperature=0.3,
                stream_usage=True,
            )
        except Exception as exc:  # 构造失败不应阻断其余配置生效
            print(f"[model_config] 重建主模型失败: {exc}")
    if fast_model:
        try:
            chat_runtime.fast_model = init_chat_model(
                model=fast_model,
                model_provider="openai",
                api_key=api_key,
                base_url=base_url,
                temperature=0.2,
                stream_usage=True,
            )
        except Exception as exc:
            print(f"[model_config] 重建快速模型失败: {exc}")

    # ---- rag.pipeline 评测 / 路由 / 复杂度模型（惰性缓存，重置后下次调用重建）----
    rag_pipeline.API_KEY = api_key
    rag_pipeline.MODEL = model
    rag_pipeline.BASE_URL = base_url
    rag_pipeline.GRADE_MODEL = grade_model
    rag_pipeline.FAST_MODEL = fast_model
    rag_pipeline._grader_model = None
    rag_pipeline._router_model = None
    rag_pipeline._complexity_model = None

    # ---- rag.utils 步骤回溯模型 ----
    rag_utils.ARK_API_KEY = api_key
    rag_utils.MODEL = model
    rag_utils.BASE_URL = base_url
    rag_utils._stepback_model = None

    # ---- tools.text_analyzer 文本分析模型 ----
    text_analyzer_mod.API_KEY = api_key
    text_analyzer_mod.FAST_MODEL = fast_model
    text_analyzer_mod.BASE_URL = base_url

    _last_applied_at = datetime.utcnow().isoformat()


def get_last_applied_at() -> str | None:
    return _last_applied_at

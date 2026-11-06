"""向量模型配置与安全迁移知识库向量。"""
import os
import re
import threading
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

import requests

from backend.env import PROJECT_ROOT

CONFIG_DEFAULTS = {
    "EMBEDDING_PROVIDER": "huggingface",
    "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2",
    "DENSE_EMBEDDING_DIM": "384",
    "EMBEDDING_DEVICE": "cpu",
    "DASHSCOPE_API_KEY": "",
    "DASHSCOPE_EMBEDDING_URL": "",
    "DASHSCOPE_RERANK_API_KEY": "",
    "RERANK_PROVIDER": "custom",
    "RERANK_MODEL": "BAAI/bge-reranker-v2-m3",
    "RERANK_BINDING_HOST": "https://api.siliconflow.cn/v1",
    "RERANK_API_KEY": "",
}
EMBEDDING_KEYS = ("EMBEDDING_PROVIDER", "EMBEDDING_MODEL", "DENSE_EMBEDDING_DIM", "EMBEDDING_DEVICE")
DASHSCOPE_EMBEDDING_KEYS = ("DASHSCOPE_API_KEY", "DASHSCOPE_EMBEDDING_URL")
CONFIG_KEYS = (
    *EMBEDDING_KEYS,
    *DASHSCOPE_EMBEDDING_KEYS,
    "DASHSCOPE_RERANK_API_KEY",
    "RERANK_PROVIDER",
    "RERANK_MODEL",
    "RERANK_BINDING_HOST",
    "RERANK_API_KEY",
)
SECRET_KEYS = {"DASHSCOPE_API_KEY", "DASHSCOPE_RERANK_API_KEY", "RERANK_API_KEY"}
_ENV_PATH = PROJECT_ROOT / ".env"
_ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"
_jobs: dict[str, dict[str, Any]] = {}
_job_lock = threading.Lock()
_active_migration = False
_last_applied_at: str | None = None


def _mark_applied() -> None:
    global _last_applied_at
    from backend.infra.timezone import now_utc8

    _last_applied_at = now_utc8().isoformat()


def _env_lines() -> list[str]:
    path = _ENV_PATH if _ENV_PATH.exists() else _ENV_EXAMPLE_PATH
    if path.exists():
        return path.read_text(encoding="utf-8").splitlines()
    return []


def _stored_values() -> dict[str, str]:
    values = dict(CONFIG_DEFAULTS)
    parsed: dict[str, str] = {}
    for line in _env_lines():
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$", line)
        if match and not line.lstrip().startswith("#"):
            parsed[match.group(1)] = match.group(2).strip()
    for key in CONFIG_KEYS:
        if key in parsed:
            values[key] = parsed[key]
        if key in os.environ:
            values[key] = os.environ[key]
    base_url = os.getenv("BASE_URL", parsed.get("BASE_URL", "")).strip().rstrip("/")
    if ".maas.aliyuncs.com/compatible-mode/v1" in base_url:
        if not values["DASHSCOPE_EMBEDDING_URL"].endswith("/compatible-mode/v1"):
            values["DASHSCOPE_EMBEDDING_URL"] = base_url
        if not values["DASHSCOPE_API_KEY"]:
            values["DASHSCOPE_API_KEY"] = os.getenv("ARK_API_KEY", parsed.get("ARK_API_KEY", ""))
    return values


def get_vector_config() -> dict[str, Any]:
    values = _stored_values()
    return {
        "config": [
            {
                "key": key,
                "value": "" if key in SECRET_KEYS else values[key],
                "is_secret": key in SECRET_KEYS,
                "is_set": bool(values[key]) or (
                    key == "DASHSCOPE_RERANK_API_KEY"
                    and bool(
                        values["DASHSCOPE_API_KEY"]
                        or (
                            values["RERANK_PROVIDER"] == "dashscope"
                            and values["RERANK_API_KEY"]
                        )
                    )
                ),
            }
            for key in CONFIG_KEYS
        ],
        "migration_running": _active_migration,
        "applied_at": _last_applied_at,
    }


def _write_env(values: dict[str, str]) -> None:
    lines = _env_lines()
    updated: set[str] = set()
    output: list[str] = []
    for line in lines:
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if match and not line.lstrip().startswith("#") and match.group(1) in values:
            key = match.group(1)
            output.append(f"{key}={values[key]}")
            updated.add(key)
        else:
            output.append(line)
    for key, value in values.items():
        if key not in updated:
            output.append(f"{key}={value}")
    _ENV_PATH.write_text("\n".join(output).rstrip("\n") + "\n", encoding="utf-8")
    for key, value in values.items():
        os.environ[key] = value


def _validate_embedding(values: dict[str, str], existing: dict[str, str]) -> None:
    if values.get("EMBEDDING_PROVIDER") not in ("huggingface", "dashscope"):
        raise ValueError("向量服务商必须是 huggingface 或 dashscope")
    if not values.get("EMBEDDING_MODEL", "").strip():
        raise ValueError("向量模型名称不能为空")
    if values.get("EMBEDDING_PROVIDER") == "dashscope":
        try:
            dim = int(values.get("DENSE_EMBEDDING_DIM", ""))
        except ValueError as exc:
            raise ValueError("百炼向量维度必须是 256、512、768 或 1024") from exc
        if dim != 1024:
            raise ValueError("qwen3.7-text-embedding-flash 兼容模式固定返回 1024 维向量")
        if not values.get("DASHSCOPE_API_KEY") and not existing.get("DASHSCOPE_API_KEY"):
            raise ValueError("请先配置阿里云百炼 API Key")
        embedding_url = values.get("DASHSCOPE_EMBEDDING_URL", "").strip().rstrip("/")
        if not embedding_url.startswith("https://") or not embedding_url.endswith("/compatible-mode/v1"):
            raise ValueError("百炼 Base URL 应以 /compatible-mode/v1 结尾")


def _validate_rerank(values: dict[str, str]) -> None:
    if values.get("RERANK_PROVIDER") not in ("custom", "dashscope"):
        raise ValueError("重排服务商必须是 custom 或 dashscope")
    if not values.get("RERANK_MODEL", "").strip():
        raise ValueError("重排模型名称不能为空")
    if values.get("RERANK_PROVIDER") == "dashscope":
        if not values.get("_EFFECTIVE_RERANK_API_KEY"):
            raise ValueError("请先配置阿里云百炼 Rerank API Key")
        embedding_url = values.get("DASHSCOPE_EMBEDDING_URL", "").strip().rstrip("/")
        if not embedding_url.startswith("https://") or not embedding_url.endswith("/compatible-mode/v1"):
            raise ValueError("百炼 rerank 需要有效的百炼 Base URL（以 /compatible-mode/v1 结尾）")


def _normalized_payload(payload: dict[str, Any], existing: dict[str, str]) -> dict[str, str]:
    values = dict(existing)
    for key in CONFIG_KEYS:
        if key not in payload or payload[key] is None:
            continue
        value = str(payload[key]).strip()
        if key in SECRET_KEYS and not value:
            continue
        values[key] = value
    if values["RERANK_PROVIDER"] == "dashscope":
        legacy_dashscope_key = (
            existing["RERANK_API_KEY"]
            if existing["RERANK_PROVIDER"] == "dashscope"
            else ""
        )
        values["_EFFECTIVE_RERANK_API_KEY"] = (
            values["DASHSCOPE_RERANK_API_KEY"]
            or legacy_dashscope_key
            or values["DASHSCOPE_API_KEY"]
        )
        if not values["DASHSCOPE_RERANK_API_KEY"] and values["_EFFECTIVE_RERANK_API_KEY"]:
            values["DASHSCOPE_RERANK_API_KEY"] = values["_EFFECTIVE_RERANK_API_KEY"]
    else:
        values["_EFFECTIVE_RERANK_API_KEY"] = values["RERANK_API_KEY"]
    return values


def _apply_rerank(values: dict[str, str]) -> None:
    from backend.rag import utils

    utils.RERANK_PROVIDER = values["RERANK_PROVIDER"]
    utils.DASHSCOPE_BASE_URL = values["DASHSCOPE_EMBEDDING_URL"]
    utils.RERANK_MODEL = values["RERANK_MODEL"]
    utils.RERANK_BINDING_HOST = values["RERANK_BINDING_HOST"]
    utils.RERANK_API_KEY = values["_EFFECTIVE_RERANK_API_KEY"]


def apply_rerank_config(payload: dict[str, Any]) -> dict[str, str]:
    existing = _stored_values()
    values = _normalized_payload(payload, existing)
    _validate_rerank(values)
    keys_to_save = [key for key in CONFIG_KEYS if key.startswith("RERANK_")]
    if values["RERANK_PROVIDER"] == "dashscope":
        keys_to_save.extend(("DASHSCOPE_EMBEDDING_URL", "DASHSCOPE_RERANK_API_KEY"))
    _write_env({key: values[key] for key in keys_to_save})
    _apply_rerank(values)
    _mark_applied()
    return values


def embedding_config_changed(values: dict[str, str], existing: dict[str, str]) -> bool:
    keys = EMBEDDING_KEYS
    if (
        values["EMBEDDING_PROVIDER"] == "dashscope"
        or existing["EMBEDDING_PROVIDER"] == "dashscope"
    ):
        keys = (*keys, *DASHSCOPE_EMBEDDING_KEYS)
    return any(values[key] != existing[key] for key in keys)


def _embed_config(values: dict[str, str]) -> dict[str, Any]:
    return {
        "provider": values["EMBEDDING_PROVIDER"],
        "model": values["EMBEDDING_MODEL"],
        "device": values["EMBEDDING_DEVICE"],
        "dimension": int(values["DENSE_EMBEDDING_DIM"]),
        "api_key": values["DASHSCOPE_API_KEY"],
        "url": values["DASHSCOPE_EMBEDDING_URL"],
    }


def _set_job(job_id: str, **updates: Any) -> None:
    with _job_lock:
        _jobs[job_id].update(updates)


def get_migration_job(job_id: str) -> dict[str, Any] | None:
    with _job_lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def is_migration_running() -> bool:
    with _job_lock:
        return _active_migration


def start_migration(payload: dict[str, Any]) -> str:
    global _active_migration
    existing = _stored_values()
    values = _normalized_payload(payload, existing)
    _validate_embedding(values, existing)
    rerank_changed = any(key.startswith("RERANK_") for key in payload)
    dashscope_changed_for_rerank = (
        values["RERANK_PROVIDER"] == "dashscope"
        and any(
            key in payload
            for key in (
                "DASHSCOPE_API_KEY",
                "DASHSCOPE_EMBEDDING_URL",
                "DASHSCOPE_RERANK_API_KEY",
            )
        )
    )
    if rerank_changed or dashscope_changed_for_rerank:
        _validate_rerank(values)
    with _job_lock:
        if _active_migration:
            raise RuntimeError("已有向量迁移任务正在运行")
        _active_migration = True
        job_id = uuid.uuid4().hex
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "message": "正在准备新的 Milvus 集合",
            "processed_files": 0,
            "total_files": 0,
            "collection": "",
        }
    threading.Thread(target=_run_migration, args=(job_id, values), daemon=True).start()
    return job_id


def _run_migration(job_id: str, values: dict[str, str]) -> None:
    global _active_migration
    target_store = None
    try:
        from backend.api.resources import UPLOAD_DIR, loader, parent_chunk_store
        from backend.indexing.embedding import EmbeddingService, embedding_service
        from backend.indexing.milvus_client import MilvusSettings, MilvusStore, get_milvus_store
        from backend.indexing.milvus_writer import MilvusWriter

        active_store = get_milvus_store()
        source_collection_exists = active_store.has_collection()
        source_rows = (
            active_store.query_all(output_fields=["filename", "chunk_id"])
            if source_collection_exists
            else []
        )
        source_snapshot = {
            (row.get("filename", ""), row.get("chunk_id", ""))
            for row in source_rows
        }
        indexed_names = {filename for filename, _ in source_snapshot if filename}
        source_files = sorted(
            path for path in Path(UPLOAD_DIR).iterdir()
            if path.is_file() and path.name in indexed_names
        ) if Path(UPLOAD_DIR).exists() else []
        missing = indexed_names - {path.name for path in source_files}
        if missing:
            raise RuntimeError("以下已入库文档缺少服务器原文件，无法安全迁移：" + ", ".join(sorted(missing)[:5]))

        current_collection = os.getenv("MILVUS_COLLECTION", "embeddings_collection")
        suffix = re.sub(r"[^A-Za-z0-9_]+", "_", values["EMBEDDING_MODEL"]).strip("_")[-24:]
        target_collection = f"{current_collection[:150]}_m_{suffix}_{uuid.uuid4().hex[:8]}"
        settings = replace(MilvusSettings.from_env(), collection_name=target_collection)
        target_store = MilvusStore(settings)
        candidate_embedder = EmbeddingService(config=_embed_config(values))
        dimension = candidate_embedder.get_embedding_dimension()
        expected_dimension = int(values["DENSE_EMBEDDING_DIM"])
        if values["EMBEDDING_PROVIDER"] == "dashscope" and dimension != expected_dimension:
            raise RuntimeError("百炼 embedding 配置维度校验失败")
        candidate_embedder.get_embeddings(["NovaChat embedding connectivity check"])
        target_store.init_collection(dimension)
        writer = MilvusWriter(candidate_embedder, target_store)
        _set_job(job_id, message="正在重新解析并向量化知识库文档", total_files=len(source_files), collection=target_collection)

        for index, path in enumerate(source_files, 1):
            docs = loader.load_document(str(path), path.name)
            parent_docs = [doc for doc in docs if int(doc.get("chunk_level", 0) or 0) in (1, 2)]
            leaf_docs = [doc for doc in docs if int(doc.get("chunk_level", 0) or 0) == 3]
            if not leaf_docs:
                raise RuntimeError(f"文档 {path.name} 未生成可检索叶子分块")
            if parent_docs:
                parent_chunk_store.upsert_documents(parent_docs)
            writer.write_documents(leaf_docs)
            _set_job(job_id, processed_files=index, message=f"已迁移 {index}/{len(source_files)} 个文档：{path.name}")

        latest_rows = (
            active_store.query_all(output_fields=["filename", "chunk_id"])
            if source_collection_exists
            else []
        )
        latest_snapshot = {(row.get("filename", ""), row.get("chunk_id", "")) for row in latest_rows}
        if latest_snapshot != source_snapshot:
            raise RuntimeError("迁移期间知识库文档发生变化；为避免遗漏，本次迁移已取消，请稍后重新开始。")

        values_to_save = {key: values[key] for key in CONFIG_KEYS}
        values_to_save["MILVUS_COLLECTION"] = target_collection
        _write_env(values_to_save)
        embedding_service.reset()
        shared_store = get_milvus_store()
        shared_store._settings = replace(shared_store._settings, collection_name=target_collection)
        _apply_rerank(values)
        _mark_applied()
        _set_job(job_id, status="completed", message="向量模型已切换，旧 Milvus 集合已保留，可用于回滚。")
    except Exception as exc:
        if target_store is not None:
            try:
                target_store.drop_collection()
            except Exception:
                pass
        _set_job(job_id, status="failed", message=str(exc))
    finally:
        with _job_lock:
            _active_migration = False

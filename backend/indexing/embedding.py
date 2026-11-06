"""本地与阿里云百炼稠密向量模型适配。"""
import os
import threading

import requests

from backend.env import load_env

load_env()


class EmbeddingService:
    def __init__(self, state_path=None, config: dict | None = None):
        self._embedder = None
        self._dimension: int | None = None
        self._config_signature = None
        self._lock = threading.RLock()
        self._config_override = config

    def _config(self) -> tuple[str, str, str, str, str, int]:
        override = self._config_override or {}
        return (
            str(override.get("provider", os.getenv("EMBEDDING_PROVIDER", "huggingface"))).strip().lower(),
            str(override.get("model", os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))).strip(),
            str(override.get("device", os.getenv("EMBEDDING_DEVICE", "cpu"))).strip(),
            str(override.get("api_key", os.getenv("DASHSCOPE_API_KEY", ""))).strip(),
            str(override.get("url", os.getenv("DASHSCOPE_EMBEDDING_URL", "").strip() or os.getenv("BASE_URL", ""))).strip(),
            int(override.get("dimension", os.getenv("DENSE_EMBEDDING_DIM", "384"))),
        )

    def _ensure_current_config(self):
        signature = self._config()
        if signature != self._config_signature:
            with self._lock:
                if signature != self._config_signature:
                    self._embedder = None
                    self._dimension = None
                    self._config_signature = signature
        return signature

    def _create_dense_embedder(self):
        provider, model_name, device, _, _, _ = self._config()
        if provider == "dashscope":
            return None
        if provider != "huggingface":
            raise ValueError(f"不支持的向量模型服务商: {provider}")

        # 延迟导入，避免服务启动时加载 torch 和 transformers。
        from langchain_huggingface import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True},
        )

    def _dashscope_embeddings(self, texts: list[str], config: tuple[str, str, str, str, str, int]) -> list[list[float]]:
        _, model_name, _, api_key, endpoint, dimension = config
        if not api_key:
            raise RuntimeError("尚未配置阿里云百炼 API Key")
        vectors: list[list[float]] = []
        endpoint = f"{endpoint.rstrip('/')}/embeddings"
        for offset in range(0, len(texts), 20):
            batch = texts[offset : offset + 20]
            response = requests.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model_name,
                    "input": batch,
                    "encoding_format": "float",
                },
                timeout=60,
            )
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error = error_data.get("error", error_data)
                    error_code = error.get("code") or error.get("type") or ""
                    error_message = error.get("message") or response.text
                except (ValueError, AttributeError):
                    error_code = ""
                    error_message = response.text
                suffix = f" [{error_code}]" if error_code else ""
                raise RuntimeError(f"百炼 embedding API 返回 HTTP {response.status_code}{suffix}: {error_message}")
            data = response.json()
            items = data.get("data", [])
            items.sort(key=lambda item: item.get("index", 0))
            batch_vectors = [item.get("embedding", []) for item in items]
            if len(batch_vectors) != len(batch) or any(len(vector) != dimension for vector in batch_vectors):
                raise RuntimeError("百炼 embedding 返回的向量数量或维度与配置不符")
            vectors.extend(batch_vectors)
        return vectors

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            config = self._ensure_current_config()
            if config[0] == "dashscope":
                return self._dashscope_embeddings(texts, config)
            if self._embedder is None:
                with self._lock:
                    if self._embedder is None:
                        self._embedder = self._create_dense_embedder()
            return self._embedder.embed_documents(texts)
        except Exception as exc:
            raise Exception(f"failed to generate embeddings: {str(exc)}") from exc

    def get_embedding_dimension(self) -> int:
        config = self._ensure_current_config()
        if self._dimension is None:
            if config[0] == "dashscope":
                self._dimension = config[5]
            else:
                embeddings = self.get_embeddings(["dimension probe"])
                if not embeddings or not embeddings[0]:
                    raise RuntimeError("failed to determine embedding dimension")
                self._dimension = len(embeddings[0])
        return self._dimension

    def reset(self) -> None:
        with self._lock:
            self._embedder = None
            self._dimension = None
            self._config_signature = None


embedding_service = EmbeddingService()

import os

from backend.env import load_env

load_env()


def _create_dense_embedder():
    # 延迟导入：langchain_huggingface 会拉起 torch/transformers 等重型依赖，
    # 仅在实际需要生成嵌入（首个文档入库或首次问答）时才加载，避免拖慢服务启动。
    from langchain_huggingface import HuggingFaceEmbeddings

    model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    device = os.getenv("EMBEDDING_DEVICE", "cpu")
    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )


class EmbeddingService:
    def __init__(self, state_path=None):
        # 不在构造时加载模型，改为首次使用时惰性初始化，显著缩短启动时间。
        self._embedder = None
        self._dimension: int | None = None

    def _ensure_embedder(self):
        if self._embedder is None:
            self._embedder = _create_dense_embedder()
        return self._embedder

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            return self._ensure_embedder().embed_documents(texts)
        except Exception as e:
            raise Exception(f"failed to generate embeddings: {str(e)}") from e

    def get_embedding_dimension(self) -> int:
        if self._dimension is None:
            embeddings = self.get_embeddings(["dimension probe"])
            if not embeddings or not embeddings[0]:
                raise RuntimeError("failed to determine embedding dimension")
            self._dimension = len(embeddings[0])
        return self._dimension


embedding_service = EmbeddingService()

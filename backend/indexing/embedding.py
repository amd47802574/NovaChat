import os

from langchain_huggingface import HuggingFaceEmbeddings

from backend.env import load_env

load_env()


def _create_dense_embedder() -> HuggingFaceEmbeddings:
    model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    device = os.getenv("EMBEDDING_DEVICE", "cpu")
    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )


class EmbeddingService:
    def __init__(self, state_path=None):
        self._embedder = _create_dense_embedder()
        self._dimension: int | None = None

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            return self._embedder.embed_documents(texts)
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

from functools import lru_cache
from typing import Protocol

from app.config import settings


class Embeddings(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


@lru_cache
def get_embeddings() -> Embeddings:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY chưa được cấu hình.")

    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        api_key=settings.openai_api_key,
    )


def validate_vector(vector: list[float]) -> list[float]:
    if len(vector) != settings.embedding_dimensions:
        raise ValueError(
            "Số chiều embedding không khớp cấu hình: "
            f"nhận {len(vector)}, cần {settings.embedding_dimensions}."
        )
    return vector

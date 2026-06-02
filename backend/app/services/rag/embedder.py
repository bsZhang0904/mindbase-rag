import hashlib
import math

import httpx
from openai import AsyncOpenAI

from app.core.config import settings


def _mock_embed_text(text: str, dim: int = settings.EMBEDDING_DIMENSION) -> list[float]:
    """无 API Key 时使用确定性伪向量，便于本地演示。"""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    seed = int.from_bytes(digest[:8], "big")
    while len(values) < dim:
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        values.append((seed / 0x7FFFFFFF) * 2 - 1)
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


class Embedder:
    def __init__(self) -> None:
        self.use_mock = settings.MOCK_MODE or not settings.EMBEDDING_API_KEY
        if not self.use_mock:
            self.client = AsyncOpenAI(
                api_key=settings.EMBEDDING_API_KEY,
                base_url=settings.EMBEDDING_BASE_URL,
            )

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.use_mock:
            return [_mock_embed_text(t) for t in texts]

        batch_size = 16
        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = await self.client.embeddings.create(model=settings.EMBEDDING_MODEL, input=batch)
            all_vectors.extend([item.embedding for item in response.data])
        return all_vectors

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_texts([text])
        return vectors[0]

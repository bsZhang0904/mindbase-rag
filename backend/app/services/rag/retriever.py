import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Document, DocumentChunk


class RetrievedChunk:
    def __init__(
        self,
        chunk_id: uuid.UUID,
        document_id: uuid.UUID,
        document_title: str,
        content: str,
        page_number: int | None,
        score: float,
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.document_title = document_title
        self.content = content
        self.page_number = page_number
        self.score = score


class Retriever:
    async def retrieve(
        self,
        db: AsyncSession,
        kb_id: uuid.UUID,
        query_vector: list[float],
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        k = top_k or settings.RETRIEVAL_TOP_K
        vector_literal = "[" + ",".join(str(v) for v in query_vector) + "]"

        sql = text(
            """
            SELECT c.id, c.document_id, c.content, c.page_number,
                   d.title AS document_title,
                   1 - (c.embedding <=> CAST(:query_vector AS vector)) AS score
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.kb_id = :kb_id
            ORDER BY c.embedding <=> CAST(:query_vector AS vector)
            LIMIT :top_k
            """
        )
        result = await db.execute(
            sql,
            {"query_vector": vector_literal, "kb_id": str(kb_id), "top_k": k},
        )
        rows = result.mappings().all()

        chunks: list[RetrievedChunk] = []
        for row in rows:
            score = float(row["score"] or 0)
            if score < settings.MIN_RELEVANCE_SCORE:
                continue
            chunks.append(
                RetrievedChunk(
                    chunk_id=row["id"],
                    document_id=row["document_id"],
                    document_title=row["document_title"],
                    content=row["content"],
                    page_number=row["page_number"],
                    score=score,
                )
            )

        # 伪向量模式下相似度分数不可靠，若无结果则回退返回 Top-K
        if not chunks and rows:
            for row in rows:
                chunks.append(
                    RetrievedChunk(
                        chunk_id=row["id"],
                        document_id=row["document_id"],
                        document_title=row["document_title"],
                        content=row["content"],
                        page_number=row["page_number"],
                        score=float(row["score"] or 0),
                    )
                )
        return chunks

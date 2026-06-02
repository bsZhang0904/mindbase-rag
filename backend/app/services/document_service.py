import uuid
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Document, DocumentChunk, DocumentStatus
from app.services.rag.chunker import split_text
from app.services.rag.embedder import Embedder


def parse_pdf(file_path: Path) -> list[tuple[str, int | None]]:
    reader = PdfReader(str(file_path))
    pages: list[tuple[str, int | None]] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((text.strip(), i))
    return pages


def parse_text_file(file_path: Path) -> list[tuple[str, int | None]]:
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    return [(content, None)] if content.strip() else []


def parse_markdown(file_path: Path) -> list[tuple[str, int | None]]:
    return parse_text_file(file_path)


class IngestService:
    def __init__(self) -> None:
        self.embedder = Embedder()

    async def ingest_document(self, db: AsyncSession, document_id: uuid.UUID) -> None:
        result = await db.get(Document, document_id)
        if result is None:
            return

        document = result
        document.status = DocumentStatus.PROCESSING
        document.error_message = None
        await db.commit()

        try:
            file_path = Path(document.file_path)
            if document.file_type == "pdf":
                page_texts = parse_pdf(file_path)
            elif document.file_type == "md":
                page_texts = parse_markdown(file_path)
            else:
                page_texts = parse_text_file(file_path)

            if not page_texts:
                raise ValueError("未能从文件中提取文本，可能是扫描版 PDF 或空文件")

            await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))

            all_chunks = []
            for page_text, page_number in page_texts:
                chunks = split_text(
                    page_text,
                    chunk_size=settings.CHUNK_SIZE,
                    overlap=settings.CHUNK_OVERLAP,
                )
                for chunk in chunks:
                    chunk.page_number = page_number
                    all_chunks.append(chunk)

            if not all_chunks:
                raise ValueError("切块结果为空")

            texts = [c.text for c in all_chunks]
            vectors = await self.embedder.embed_texts(texts)

            db_chunks: list[DocumentChunk] = []
            for chunk, vector in zip(all_chunks, vectors, strict=True):
                db_chunks.append(
                    DocumentChunk(
                        document_id=document.id,
                        kb_id=document.kb_id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.text,
                        token_count=len(chunk.text),
                        page_number=chunk.page_number,
                        embedding=vector,
                    )
                )

            db.add_all(db_chunks)
            document.chunk_count = len(db_chunks)
            document.status = DocumentStatus.READY
            await db.commit()
        except Exception as exc:
            document.status = DocumentStatus.FAILED
            document.error_message = str(exc)
            await db.commit()
            raise

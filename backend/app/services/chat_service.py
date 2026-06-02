import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import Conversation, Message, MessageCitation


class ChatService:
    def __init__(self) -> None:
        from app.services.rag.embedder import Embedder
        from app.services.rag.generator import Generator
        from app.services.rag.retriever import Retriever

        self.embedder = Embedder()
        self.retriever = Retriever()
        self.generator = Generator()

    async def _get_conversation(
        self, db: AsyncSession, conv_id: uuid.UUID, user_id: uuid.UUID
    ) -> Conversation:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id)
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            raise ValueError("Conversation not found")
        return conv

    async def chat(
        self,
        db: AsyncSession,
        conv_id: uuid.UUID,
        user_id: uuid.UUID,
        question: str,
        top_k: int | None = None,
    ):
        import time

        from app.models.models import Message, MessageCitation
        from app.schemas.chat import CitationOut

        start = time.perf_counter()
        conv = await self._get_conversation(db, conv_id, user_id)

        db.add(Message(conversation_id=conv.id, role="user", content=question))
        await db.flush()

        query_vector = await self.embedder.embed_query(question)
        retrieved = await self.retriever.retrieve(db, conv.kb_id, query_vector, top_k)
        answer = await self.generator.generate(question, retrieved)

        assistant_msg = Message(conversation_id=conv.id, role="assistant", content=answer)
        db.add(assistant_msg)
        await db.flush()

        citations = self._build_citations(assistant_msg.id, retrieved)
        for cite in citations:
            db.add(
                MessageCitation(
                    message_id=assistant_msg.id,
                    chunk_id=uuid.UUID(cite.chunk_id),
                    citation_index=cite.index,
                    score=cite.score,
                )
            )

        if not conv.title:
            conv.title = question[:50]

        latency_ms = int((time.perf_counter() - start) * 1000)
        await db.commit()
        await db.refresh(assistant_msg)
        return assistant_msg, citations, latency_ms

    async def chat_stream(
        self,
        db: AsyncSession,
        conv_id: uuid.UUID,
        user_id: uuid.UUID,
        question: str,
        top_k: int | None = None,
    ):
        from app.models.models import Message

        conv = await self._get_conversation(db, conv_id, user_id)

        db.add(Message(conversation_id=conv.id, role="user", content=question))
        await db.flush()

        query_vector = await self.embedder.embed_query(question)
        retrieved = await self.retriever.retrieve(db, conv.kb_id, query_vector, top_k)
        citations = []

        assistant_msg = Message(conversation_id=conv.id, role="assistant", content="")
        db.add(assistant_msg)
        await db.flush()

        citations = self._build_citations(assistant_msg.id, retrieved)
        for cite in citations:
            db.add(
                MessageCitation(
                    message_id=assistant_msg.id,
                    chunk_id=uuid.UUID(cite.chunk_id),
                    citation_index=cite.index,
                    score=cite.score,
                )
            )

        if not conv.title:
            conv.title = question[:50]
        await db.commit()

        msg_id = assistant_msg.id
        generator = self.generator

        async def stream():
            async for token in generator.generate_stream(question, retrieved):
                yield token

        return stream(), msg_id, citations

    def _build_citations(self, message_id: uuid.UUID, retrieved: list) -> list:
        from app.schemas.chat import CitationOut

        citations: list[CitationOut] = []
        for i, chunk in enumerate(retrieved, start=1):
            citations.append(
                CitationOut(
                    index=i,
                    chunk_id=str(chunk.chunk_id),
                    document_title=chunk.document_title,
                    page_number=chunk.page_number,
                    excerpt=chunk.content[:200],
                    score=chunk.score,
                )
            )
        return citations

    async def list_messages(self, db: AsyncSession, conv_id: uuid.UUID, user_id: uuid.UUID) -> list[Message]:
        await self._get_conversation(db, conv_id, user_id)
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .options(selectinload(Message.citations).selectinload(MessageCitation.chunk))
            .order_by(Message.created_at)
        )
        return list(result.scalars().all())

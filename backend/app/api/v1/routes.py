import json
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal, get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models.models import Conversation, Document, KnowledgeBase, Message, MessageCitation, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenData, UserOut
from app.schemas.common import ApiResponse
from app.schemas.chat import ChatRequest, ChatResponse, ConversationCreate, ConversationOut, MessageList, MessageOut, CitationOut
from app.schemas.document import DocumentOut, DocumentUploadResponse
from app.schemas.kb import KnowledgeBaseCreate, KnowledgeBaseList, KnowledgeBaseOut, KnowledgeBaseUpdate
from app.services.chat_service import ChatService
from app.services.document_service import IngestService
from app.services.upload import save_upload_file

router = APIRouter()
chat_service = ChatService()


async def run_ingest(document_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        service = IngestService()
        await service.ingest_document(session, document_id)


# ── Auth ──────────────────────────────────────────────────────────

@router.post("/auth/register", response_model=ApiResponse[UserOut], status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    exists = await db.execute(select(User).where((User.email == body.email) | (User.username == body.username)))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email or username already exists")

    user = User(email=body.email, username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return ApiResponse(data=UserOut(user_id=str(user.id), email=user.email, username=user.username))


@router.post("/auth/login", response_model=ApiResponse[TokenData])
async def login(body: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(str(user.id))
    return ApiResponse(data=TokenData(access_token=token, expires_in=7200))


@router.get("/auth/me", response_model=ApiResponse[UserOut])
async def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    return ApiResponse(
        data=UserOut(user_id=str(current_user.id), email=current_user.email, username=current_user.username)
    )


# ── Knowledge Bases ───────────────────────────────────────────────

async def _get_user_kb(db: AsyncSession, kb_id: uuid.UUID, user_id: uuid.UUID) -> KnowledgeBase:
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id, KnowledgeBase.user_id == user_id)
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb


@router.get("/knowledge-bases", response_model=ApiResponse[KnowledgeBaseList])
async def list_knowledge_bases(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = 1,
    page_size: int = 20,
):
    offset = (page - 1) * page_size
    total_result = await db.execute(
        select(func.count()).select_from(KnowledgeBase).where(KnowledgeBase.user_id == current_user.id)
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.user_id == current_user.id)
        .order_by(KnowledgeBase.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    kbs = result.scalars().all()

    items: list[KnowledgeBaseOut] = []
    for kb in kbs:
        count_result = await db.execute(select(func.count()).select_from(Document).where(Document.kb_id == kb.id))
        doc_count = count_result.scalar() or 0
        items.append(
            KnowledgeBaseOut(
                id=str(kb.id),
                name=kb.name,
                description=kb.description,
                document_count=doc_count,
                created_at=kb.created_at,
            )
        )
    return ApiResponse(data=KnowledgeBaseList(items=items, total=total))


@router.post("/knowledge-bases", response_model=ApiResponse[KnowledgeBaseOut], status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    body: KnowledgeBaseCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    kb = KnowledgeBase(user_id=current_user.id, name=body.name, description=body.description)
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return ApiResponse(
        data=KnowledgeBaseOut(
            id=str(kb.id), name=kb.name, description=kb.description, document_count=0, created_at=kb.created_at
        )
    )


@router.get("/knowledge-bases/{kb_id}", response_model=ApiResponse[KnowledgeBaseOut])
async def get_knowledge_base(
    kb_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    kb = await _get_user_kb(db, kb_id, current_user.id)
    count_result = await db.execute(select(func.count()).select_from(Document).where(Document.kb_id == kb.id))
    return ApiResponse(
        data=KnowledgeBaseOut(
            id=str(kb.id),
            name=kb.name,
            description=kb.description,
            document_count=count_result.scalar() or 0,
            created_at=kb.created_at,
        )
    )


@router.put("/knowledge-bases/{kb_id}", response_model=ApiResponse[KnowledgeBaseOut])
async def update_knowledge_base(
    kb_id: uuid.UUID,
    body: KnowledgeBaseUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    kb = await _get_user_kb(db, kb_id, current_user.id)
    if body.name is not None:
        kb.name = body.name
    if body.description is not None:
        kb.description = body.description
    await db.commit()
    await db.refresh(kb)
    count_result = await db.execute(select(func.count()).select_from(Document).where(Document.kb_id == kb.id))
    return ApiResponse(
        data=KnowledgeBaseOut(
            id=str(kb.id),
            name=kb.name,
            description=kb.description,
            document_count=count_result.scalar() or 0,
            created_at=kb.created_at,
        )
    )


@router.delete("/knowledge-bases/{kb_id}", response_model=ApiResponse[None])
async def delete_knowledge_base(
    kb_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    kb = await _get_user_kb(db, kb_id, current_user.id)
    await db.delete(kb)
    await db.commit()
    return ApiResponse(data=None, message="deleted")


# ── Documents ─────────────────────────────────────────────────────

@router.get("/knowledge-bases/{kb_id}/documents", response_model=ApiResponse[list[DocumentOut]])
async def list_documents(
    kb_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await _get_user_kb(db, kb_id, current_user.id)
    result = await db.execute(
        select(Document).where(Document.kb_id == kb_id).order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return ApiResponse(
        data=[
            DocumentOut(
                id=str(d.id),
                title=d.title,
                file_type=d.file_type,
                file_size=d.file_size,
                status=d.status.value if hasattr(d.status, "value") else d.status,
                chunk_count=d.chunk_count,
                error_message=d.error_message,
                created_at=d.created_at,
            )
            for d in docs
        ]
    )


@router.post(
    "/knowledge-bases/{kb_id}/documents",
    response_model=ApiResponse[DocumentUploadResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    kb_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
):
    kb = await _get_user_kb(db, kb_id, current_user.id)
    file_path, file_type, file_size = await save_upload_file(file, current_user.id)

    document = Document(
        kb_id=kb.id,
        title=title or file.filename or "untitled",
        file_type=file_type,
        file_path=str(file_path),
        file_size=file_size,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    background_tasks.add_task(run_ingest, document.id)

    return ApiResponse(
        data=DocumentUploadResponse(
            document_id=str(document.id),
            status="pending",
            message="文档已上传，正在解析索引",
        )
    )


@router.get("/documents/{doc_id}", response_model=ApiResponse[DocumentOut])
async def get_document(
    doc_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(
        select(Document)
        .join(KnowledgeBase)
        .where(Document.id == doc_id, KnowledgeBase.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return ApiResponse(
        data=DocumentOut(
            id=str(doc.id),
            title=doc.title,
            file_type=doc.file_type,
            file_size=doc.file_size,
            status=doc.status.value if hasattr(doc.status, "value") else doc.status,
            chunk_count=doc.chunk_count,
            error_message=doc.error_message,
            created_at=doc.created_at,
        )
    )


@router.delete("/documents/{doc_id}", response_model=ApiResponse[None])
async def delete_document(
    doc_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(
        select(Document)
        .join(KnowledgeBase)
        .where(Document.id == doc_id, KnowledgeBase.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(doc)
    await db.commit()
    return ApiResponse(data=None, message="deleted")


# ── Conversations & Chat ──────────────────────────────────────────

@router.get("/knowledge-bases/{kb_id}/conversations", response_model=ApiResponse[list[ConversationOut]])
async def list_conversations(
    kb_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await _get_user_kb(db, kb_id, current_user.id)
    result = await db.execute(
        select(Conversation)
        .where(Conversation.kb_id == kb_id, Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    convs = result.scalars().all()
    return ApiResponse(
        data=[
            ConversationOut(
                id=str(c.id),
                title=c.title,
                kb_id=str(c.kb_id),
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in convs
        ]
    )


@router.post(
    "/knowledge-bases/{kb_id}/conversations",
    response_model=ApiResponse[ConversationOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    kb_id: uuid.UUID,
    body: ConversationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await _get_user_kb(db, kb_id, current_user.id)
    conv = Conversation(user_id=current_user.id, kb_id=kb_id, title=body.title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ApiResponse(
        data=ConversationOut(
            id=str(conv.id),
            title=conv.title,
            kb_id=str(conv.kb_id),
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        )
    )


@router.get("/conversations/{conv_id}/messages", response_model=ApiResponse[MessageList])
async def get_messages(
    conv_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    messages = await chat_service.list_messages(db, conv_id, current_user.id)

    doc_ids = set()
    for msg in messages:
        for cite in msg.citations:
            if cite.chunk:
                doc_ids.add(cite.chunk.document_id)

    doc_titles: dict[uuid.UUID, str] = {}
    if doc_ids:
        result = await db.execute(select(Document.id, Document.title).where(Document.id.in_(doc_ids)))
        doc_titles = {row[0]: row[1] for row in result.all()}

    items: list[MessageOut] = []
    for msg in messages:
        citations: list[CitationOut] = []
        for cite in sorted(msg.citations, key=lambda c: c.citation_index):
            chunk = cite.chunk
            citations.append(
                CitationOut(
                    index=cite.citation_index,
                    chunk_id=str(cite.chunk_id),
                    document_title=doc_titles.get(chunk.document_id, "未知文档") if chunk else "未知文档",
                    page_number=chunk.page_number if chunk else None,
                    excerpt=chunk.content[:200] if chunk else "",
                    score=cite.score,
                )
            )
        items.append(
            MessageOut(id=str(msg.id), role=msg.role, content=msg.content, citations=citations, created_at=msg.created_at)
        )
    return ApiResponse(data=MessageList(items=items))


@router.post("/conversations/{conv_id}/chat", response_model=ApiResponse[ChatResponse])
async def chat(
    conv_id: uuid.UUID,
    body: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        msg, citations, latency_ms = await chat_service.chat(
            db, conv_id, current_user.id, body.question, body.top_k
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ApiResponse(
        data=ChatResponse(
            message_id=str(msg.id),
            answer=msg.content,
            citations=citations,
            latency_ms=latency_ms,
        )
    )


@router.post("/conversations/{conv_id}/chat/stream")
async def chat_stream(
    conv_id: uuid.UUID,
    body: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        stream, msg_id, citations = await chat_service.chat_stream(
            db, conv_id, current_user.id, body.question, body.top_k
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    async def event_generator():
        parts: list[str] = []
        async for token in stream:
            parts.append(token)
            yield f"event: token\ndata: {json.dumps({'content': token}, ensure_ascii=False)}\n\n"

        full_answer = "".join(parts)
        async with AsyncSessionLocal() as session:
            msg = await session.get(Message, msg_id)
            if msg:
                msg.content = full_answer
                await session.commit()

        done_data = {"message_id": str(msg_id), "citations": [c.model_dump() for c in citations]}
        yield f"event: done\ndata: {json.dumps(done_data, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

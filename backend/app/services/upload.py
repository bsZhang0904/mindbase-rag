import uuid
from pathlib import Path

from fastapi import UploadFile, HTTPException

from app.core.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt", ".markdown"}
EXT_TO_TYPE = {".pdf": "pdf", ".md": "md", ".markdown": "md", ".txt": "txt"}


async def save_upload_file(file: UploadFile, user_id: uuid.UUID) -> tuple[Path, str, int]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only pdf, md, txt files are supported")

    content = await file.read()
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail=f"File too large, max {settings.MAX_UPLOAD_SIZE_MB}MB")

    upload_root = Path(settings.UPLOAD_DIR) / str(user_id)
    upload_root.mkdir(parents=True, exist_ok=True)

    doc_id = uuid.uuid4()
    file_path = upload_root / f"{doc_id}{ext}"
    file_path.write_bytes(content)

    return file_path, EXT_TO_TYPE[ext], len(content)

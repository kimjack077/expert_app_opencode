import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException

from app.config import settings


ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".heic", ".heif", ".gif", ".webp", ".bmp",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".md", ".csv",
    ".json", ".zip",
}
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",        # Some clients report this non-standard type
    "image/png",
    "image/heic",
    "image/heif",       # iOS HEIC variant
    "image/gif",
    "image/webp",
    "image/bmp",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream",
}


def ensure_upload_dir():
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def validate_file(file: UploadFile) -> None:
    if file.size and file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size is {settings.MAX_FILE_SIZE // 1024 // 1024}MB",
        )

    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Invalid MIME type")


async def save_upload_file(
    file: UploadFile, subdir: Optional[str] = None
) -> tuple[str, str, int]:
    validate_file(file)

    upload_dir = ensure_upload_dir()
    if subdir:
        upload_dir = upload_dir / subdir
        upload_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    stored_name = f"{uuid.uuid4()}{ext}"
    file_path = upload_dir / stored_name

    content = await file.read()
    file_size = len(content)

    with open(file_path, "wb") as f:
        f.write(content)

    relative_path = file_path.relative_to(Path(settings.UPLOAD_DIR).parent).as_posix()
    # Ensure the path starts with / so it works as an absolute URL
    if not relative_path.startswith("/"):
        relative_path = "/" + relative_path
    return stored_name, relative_path, file_size


def delete_file(file_path: str) -> bool:
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            return True
    except Exception:
        pass
    return False

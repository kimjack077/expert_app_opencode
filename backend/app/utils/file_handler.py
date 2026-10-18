import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException

from app.config import settings


logger = logging.getLogger(__name__)


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


# 常见格式的文件头签名。客户端声明的 content_type 可伪造，
# 落盘前用真实字节校验，避免把可执行内容伪装成图片存进 uploads/。
_MAGIC_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".webp": (b"RIFF",),
    ".bmp": (b"BM",),
    ".pdf": (b"%PDF",),
    # OOXML(docx/xlsx/pptx) 本质是 zip
    ".docx": (b"PK\x03\x04",),
    ".xlsx": (b"PK\x03\x04",),
    ".zip": (b"PK\x03\x04", b"PK\x05\x06"),
}


def enforce_max_size(size: int) -> None:
    if size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size is {settings.MAX_FILE_SIZE // 1024 // 1024}MB",
        )


def enforce_magic_bytes(content: bytes, ext: str) -> None:
    signatures = _MAGIC_SIGNATURES.get(ext.lower())
    if not signatures:
        return  # 纯文本等无稳定签名的格式跳过
    if not any(content.startswith(sig) for sig in signatures):
        raise HTTPException(
            status_code=400,
            detail="文件内容与扩展名不符，已拒绝",
        )


def validate_file(file: UploadFile) -> None:
    if file.size:
        enforce_max_size(file.size)

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

    # 读取后按真实字节数复核：validate_file 依赖客户端声明的 file.size，
    # 该值可能为 None 或被伪造，只有这里才是权威大小。
    enforce_max_size(file_size)
    enforce_magic_bytes(content, ext)

    # 写盘是同步阻塞 IO；上传发生在移动端弱网、照片较大的场景，
    # 直接写在事件循环里会卡住其他请求。卸载到线程池。
    from starlette.concurrency import run_in_threadpool

    await run_in_threadpool(file_path.write_bytes, content)

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
    except OSError as exc:
        # 删除失败会留下孤儿文件占用磁盘；静默吞掉会让问题永远不可见。
        logger.warning("删除文件失败: %s (%s)", file_path, exc)
    return False

"""Portable, upload-root-scoped paths for persisted files."""

from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from app.config import settings


def upload_root() -> Path:
    return Path(settings.UPLOAD_DIR).resolve()


def storage_key(path: str | Path) -> str:
    """Return a host-independent key relative to ``UPLOAD_DIR``."""
    root = upload_root()
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("Storage path must be inside UPLOAD_DIR") from exc


def resolve_storage_path(reference: Any, *, require_file: bool = True) -> Path | None:
    """Resolve new storage keys and legacy absolute paths within UPLOAD_DIR.

    Legacy records may contain an absolute path from another operating system.
    Their suffix after the upload-root directory is mapped onto this host's
    configured root. Paths which escape that root are always rejected.
    """
    if isinstance(reference, dict):
        reference = next(
            (
                reference.get(key)
                for key in ("stored_path", "path", "url", "file_path")
                if reference.get(key)
            ),
            None,
        )
    if not isinstance(reference, (str, Path)) or not str(reference).strip():
        return None

    raw = str(reference).strip()
    parsed = urlparse(raw)
    if parsed.scheme and parsed.scheme.lower() not in {"file"}:
        # A Windows drive (D:) is parsed as a URL scheme on non-Windows hosts.
        if not (len(parsed.scheme) == 1 and len(raw) > 2 and raw[1] == ":"):
            return None
    path_text = unquote(parsed.path if parsed.scheme == "file" else raw).replace("\\", "/")
    root = upload_root()
    candidates: list[Path] = []

    supplied = Path(path_text)
    if supplied.is_absolute():
        candidates.append(supplied)

    parts = [part for part in path_text.strip("/").split("/") if part not in {"", "."}]
    root_name = root.name.casefold()
    root_indexes = [index for index, part in enumerate(parts) if part.casefold() == root_name]
    if root_indexes:
        candidates.append(root.joinpath(*parts[root_indexes[-1] + 1 :]))
    else:
        # New records contain only this relative key.
        candidates.append(root.joinpath(*parts))

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            continue
        if resolved.is_file() if require_file else resolved.exists():
            return resolved
    return None

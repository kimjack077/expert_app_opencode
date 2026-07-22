import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from app.config import settings
from app.routers.project_agent import artifact_dict
from app.schemas.project_agent import ArtifactGenerateRequest
from app.services.project_artifact_service import ProjectArtifactService
from app.utils.storage_path import resolve_storage_path


def _artifact(path: str, *, status: str = "ready") -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        artifact_type="package",
        path=path,
        filename="package.zip",
        status=status,
        progress=100,
        error_message=None,
        artifact_metadata={},
        version=1,
        file_size=3,
        mime_type="application/zip",
        created_at=now,
        updated_at=now,
    )


def test_artifact_dict_reports_legacy_missing_file_as_unavailable(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    artifact = _artifact(
        r"D:\old-host\backend\uploads\audit_projects\project-1\artifacts\v1_package.zip"
    )

    assert artifact_dict(artifact)["available"] is False


def test_default_artifact_generation_includes_complete_package():
    assert ArtifactGenerateRequest().artifact_types == ["package"]


def test_artifact_dict_reports_resolved_storage_key_as_available(
    tmp_path, monkeypatch
):
    root = tmp_path / "uploads"
    package = root / "audit_projects" / "project-1" / "artifacts" / "v2_package.zip"
    package.parent.mkdir(parents=True)
    package.write_bytes(b"zip")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(root))

    assert artifact_dict(_artifact("audit_projects/project-1/artifacts/v2_package.zip"))[
        "available"
    ] is True


def test_storing_package_after_missing_v1_creates_portable_v2(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(root))
    query_result = Mock()
    query_result.scalar_one_or_none.return_value = 1
    db = AsyncMock()
    db.execute.return_value = query_result
    db.add = Mock()
    project = SimpleNamespace(id=uuid4())

    artifact = asyncio.run(
        ProjectArtifactService()._store(
            db,
            project,
            "package",
            "package.zip",
            b"new-package",
            "application/zip",
            {},
            uuid4(),
        )
    )

    assert artifact.version == 2
    assert artifact.path == (
        f"audit_projects/{project.id}/artifacts/v2_package.zip"
    )
    assert resolve_storage_path(artifact.path).read_bytes() == b"new-package"

from pathlib import Path

import pytest

from app.config import settings
from app.utils.storage_path import resolve_storage_path, storage_key


def test_storage_key_round_trip_is_relative(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    stored = root / "audit_projects" / "project-1" / "artifacts" / "v2_package.zip"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"zip")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(root))

    key = storage_key(stored)

    assert key == "audit_projects/project-1/artifacts/v2_package.zip"
    assert resolve_storage_path(key) == stored.resolve()


@pytest.mark.parametrize(
    "legacy_path",
    [
        r"D:\old-host\expert_app\backend\uploads\audit_projects\project-1\artifacts\v1_package.zip",
        "/home/old-host/expert_app/backend/uploads/audit_projects/project-1/artifacts/v1_package.zip",
    ],
)
def test_legacy_absolute_path_maps_to_current_upload_root(
    tmp_path, monkeypatch, legacy_path
):
    root = tmp_path / "uploads"
    stored = root / "audit_projects" / "project-1" / "artifacts" / "v1_package.zip"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"zip")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(root))

    assert resolve_storage_path(legacy_path) == stored.resolve()


@pytest.mark.parametrize(
    "unsafe_path",
    ["../secret.txt", "audit_projects/../../secret.txt", "/uploads/../secret.txt"],
)
def test_storage_path_rejects_directory_traversal(tmp_path, monkeypatch, unsafe_path):
    root = tmp_path / "uploads"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(root))

    assert resolve_storage_path(unsafe_path) is None


def test_storage_key_rejects_path_outside_upload_root(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(root))

    with pytest.raises(ValueError, match="inside UPLOAD_DIR"):
        storage_key(outside)

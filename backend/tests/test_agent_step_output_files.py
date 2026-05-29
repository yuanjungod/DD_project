"""Tests for agent step output folder listing and export."""

from __future__ import annotations

from pathlib import Path
import zipfile
from io import BytesIO

import pytest
from fastapi import HTTPException

from app.services.agent_step_output_files import (
    build_output_folder_zip,
    list_output_files,
    read_output_file,
    resolve_file_in_folder,
)


def test_list_output_files_includes_all_text_files(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# hello", encoding="utf-8")
    (tmp_path / "result.json").write_text('{"ok": true}', encoding="utf-8")

    files = list_output_files(tmp_path)

    assert [item["path"] for item in files] == ["README.md", "result.json"]
    assert files[0]["content_type"] == "text"
    assert files[1]["content"] == '{"ok": true}'


def test_resolve_file_in_folder_rejects_traversal(tmp_path: Path) -> None:
    (tmp_path / "safe.txt").write_text("ok", encoding="utf-8")

    with pytest.raises(HTTPException) as exc:
        resolve_file_in_folder(tmp_path, "../outside.txt")
    assert exc.value.status_code == 400


def test_build_output_folder_zip_contains_files(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# hello", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "data.json").write_text("{}", encoding="utf-8")

    payload, filename = build_output_folder_zip(tmp_path)

    assert filename.endswith(".zip")
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        names = sorted(archive.namelist())
    assert names == ["README.md", "nested/data.json"]


def test_read_output_file_returns_text_content(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("line one", encoding="utf-8")

    entry = read_output_file(tmp_path, "notes.txt")

    assert entry["content_type"] == "text"
    assert entry["content"] == "line one"

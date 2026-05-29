"""Tests for skill ZIP import limits and validation."""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi import HTTPException

from app.services.skill_zip_import import MAX_FILES, skill_package_create_from_zip


def _build_skill_zip(extra_file_count: int = 0) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "my-skill/SKILL.md",
            "---\nname: my-skill\ndescription: test\n---\n\n# Skill\n",
        )
        for i in range(extra_file_count):
            zf.writestr(f"my-skill/scripts/extra_{i}.py", f"# file {i}\n")
    return buf.getvalue()


def test_skill_zip_import_accepts_many_files() -> None:
    payload = skill_package_create_from_zip(_build_skill_zip(extra_file_count=600))
    assert payload.directory_name == "my-skill"
    assert len(payload.package_files) == 600


def test_skill_zip_import_rejects_too_many_files() -> None:
    with pytest.raises(HTTPException) as exc:
        skill_package_create_from_zip(_build_skill_zip(extra_file_count=MAX_FILES))
    assert exc.value.status_code == 400
    assert "文件数量超过上限" in str(exc.value.detail)


def test_skill_zip_import_ignores_macos_metadata_and_outside_readme() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "docx-main/docx/SKILL.md",
            "---\nname: docx\ndescription: word docs\n---\n\n# Docx\n",
        )
        zf.writestr("docx-main/docx/LICENSE.txt", "license\n")
        zf.writestr("docx-main/README.md", "repo readme\n")
        zf.writestr("__MACOSX/docx-main/._docx", "junk")
        zf.writestr("docx-main/docx/.DS_Store", "junk")
    payload = skill_package_create_from_zip(buf.getvalue())
    assert payload.directory_name == "docx"
    assert payload.package_files == {"LICENSE.txt": "license\n"}


def test_skill_zip_import_accepts_flat_skill_root() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "SKILL.md",
            "---\nname: flat-skill\ndescription: root\n---\n\n# Flat\n",
        )
        zf.writestr("scripts/run.py", "print('ok')\n")
    payload = skill_package_create_from_zip(buf.getvalue())
    assert payload.directory_name == "flat-skill"
    assert payload.package_files == {"scripts/run.py": "print('ok')\n"}


def test_skill_zip_import_ignores_pycache_and_binary_artifacts() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "cashflow/SKILL.md",
            "---\nname: cashflow\ndescription: test\n---\n\n# Skill\n",
        )
        zf.writestr("cashflow/tests/test_contract.py", "def test_ok():\n    assert True\n")
        zf.writestr(
            "cashflow/tests/__pycache__/test_cashflow_contract.cpython-314-pytest-9.0.3.pyc",
            b"\x00\x01binary",
        )
        zf.writestr("cashflow/.pytest_cache/v/cache/nodeids", "[\"x\"]\n")
    payload = skill_package_create_from_zip(buf.getvalue())
    assert payload.directory_name == "cashflow"
    assert payload.package_files == {"tests/test_contract.py": "def test_ok():\n    assert True\n"}

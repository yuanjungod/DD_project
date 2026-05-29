from __future__ import annotations

import re
import zipfile
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any

import frontmatter
from fastapi import HTTPException

from app.schemas.dto import SkillPackageCreate

MAX_ZIP_BYTES = 20 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 60 * 1024 * 1024
# Large skills (e.g. docx with bundled Office XSD schemas) can exceed a few hundred files.
MAX_FILES = 4096


_IGNORED_PATH_PARTS = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".git",
        ".hg",
        ".svn",
        "htmlcov",
        "node_modules",
    }
)
_IGNORED_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".class",
)


def _is_ignored_zip_entry(path: str) -> bool:
    """Skip archive metadata and local dev/build artifacts that are not skill content."""
    if path.startswith("__MACOSX/"):
        return True
    parts = PurePosixPath(path).parts
    if any(part in _IGNORED_PATH_PARTS for part in parts):
        return True
    name = PurePosixPath(path).name
    if name in {".DS_Store", "Thumbs.db", "desktop.ini", ".coverage"}:
        return True
    if name.startswith("._"):
        return True
    lower = name.casefold()
    if lower.endswith(_IGNORED_SUFFIXES):
        return True
    return False


def _entries_under_prefix(
    entries: list[tuple[str, zipfile.ZipInfo]],
    prefix: str,
    skill_path: str,
) -> list[tuple[str, zipfile.ZipInfo]]:
    if not prefix:
        return entries
    scoped_prefix = prefix + "/"
    return [
        (path, info)
        for path, info in entries
        if path == skill_path or path.startswith(scoped_prefix)
    ]


def _slug_dir(name: str) -> str:
    s = name.strip().lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9_-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "skill-import"


def _safe_arc_name(name: str) -> str:
    normalized = name.replace("\\", "/").strip("/")
    if not normalized or normalized.startswith("/"):
        raise HTTPException(status_code=400, detail=f"无效的压缩路径: {name!r}")
    parts = normalized.split("/")
    if any(p == ".." for p in parts):
        raise HTTPException(status_code=400, detail="压缩包内禁止路径中包含 ..")
    return "/".join(parts)


def skill_package_create_from_zip(
    zip_bytes: bytes,
    *,
    directory_name_override: str | None = None,
) -> SkillPackageCreate:
    if len(zip_bytes) > MAX_ZIP_BYTES:
        raise HTTPException(status_code=413, detail=f"ZIP 体积超过上限（{MAX_ZIP_BYTES // (1024 * 1024)}MB）")

    try:
        zf = zipfile.ZipFile(BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail=f"无效的 ZIP 文件: {exc}") from exc

    try:
        entries: list[tuple[str, zipfile.ZipInfo]] = []
        seen: set[str] = set()
        uncompressed = 0
        for info in zf.infolist():
            if info.is_dir():
                continue
            norm = _safe_arc_name(info.filename)
            if _is_ignored_zip_entry(norm):
                continue
            if norm in seen:
                raise HTTPException(status_code=400, detail=f"压缩包中存在重复路径: {norm}")
            seen.add(norm)
            uncompressed += info.file_size
            entries.append((norm, info))

        if len(entries) > MAX_FILES:
            raise HTTPException(status_code=400, detail=f"压缩包内文件数量超过上限（{MAX_FILES}）")
        if uncompressed > MAX_UNCOMPRESSED_BYTES:
            raise HTTPException(status_code=413, detail="ZIP 解压后总体积过大")

        skill_entries = [(n, i) for n, i in entries if PurePosixPath(n).name.casefold() == "skill.md"]
        if not skill_entries:
            raise HTTPException(
                status_code=400,
                detail="ZIP 中必须包含 SKILL.md（大小写随意，但文件名需为 SKILL.md）",
            )
        if len(skill_entries) > 1:
            raise HTTPException(status_code=400, detail="ZIP 中只能包含一个 SKILL.md")

        skill_path, skill_info = skill_entries[0]
        parent_raw = PurePosixPath(skill_path).parent.as_posix()
        prefix = "" if parent_raw in ("", ".") else parent_raw

        entries = _entries_under_prefix(entries, prefix, skill_path)
        if not entries:
            raise HTTPException(status_code=400, detail="ZIP 中未找到可用的 Skill 文件")

        package_files: dict[str, str] = {}
        raw_skill = zf.read(skill_info)
        try:
            skill_md = raw_skill.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="SKILL.md 须为 UTF-8 编码") from exc

        for norm, info in entries:
            if norm == skill_path:
                continue
            rel_to_skill = norm[len(prefix) + 1 :] if prefix else norm
            if rel_to_skill == "SKILL.md" or rel_to_skill.casefold() == "skill.md":
                continue
            raw = zf.read(info)
            try:
                package_files[rel_to_skill] = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"文件须为 UTF-8 文本: {rel_to_skill}",
                ) from exc

        meta: dict[str, Any] = {}
        try:
            post = frontmatter.loads(skill_md)
            meta = dict(post.metadata) if isinstance(post.metadata, dict) else {}
        except Exception:
            meta = {}

        fm_name = meta.get("name")
        fm_desc = meta.get("description", "")

        directory_name = _slug_dir(
            directory_name_override or (str(fm_name) if fm_name else prefix or "imported-skill"),
        )

        catalog_name = str(fm_name).strip() if fm_name else directory_name
        catalog_name = catalog_name or directory_name

        all_files = ["SKILL.md", *sorted(package_files.keys())]
        manifest: dict[str, Any] = {
            "files": all_files,
            "references": sorted(p for p in all_files if p.startswith("references/")),
            "scripts": sorted(p for p in all_files if p.startswith("scripts/")),
            "assets": sorted(p for p in all_files if p.startswith("assets/")),
        }

        return SkillPackageCreate(
            name=catalog_name,
            description=str(fm_desc or "").strip(),
            directory_name=directory_name,
            skill_md=skill_md,
            package_files=package_files,
            resources_manifest=manifest,
            enabled=True,
        )
    finally:
        zf.close()

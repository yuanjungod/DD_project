"""Read and export agent step output folders on the backend filesystem."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

from fastapi import HTTPException

MAX_OUTPUT_FILES = 500
MAX_INLINE_TEXT_BYTES = 512_000
MAX_INLINE_TEXT_CHARS = 200_000

_TEXT_EXTENSIONS = frozenset(
    {
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".csv",
        ".tsv",
        ".html",
        ".htm",
        ".xml",
        ".log",
        ".py",
        ".js",
        ".ts",
        ".css",
        ".sql",
        ".ini",
        ".toml",
    }
)


def output_dir_from_step_result(result: object) -> str:
    if not isinstance(result, dict):
        return ""
    return str(result.get("output_dir") or "").strip()


def resolve_output_folder(output_dir: str) -> Path | None:
    text = output_dir.strip()
    if not text:
        return None
    folder = Path(text).expanduser().resolve()
    if not folder.is_dir():
        return None
    return folder


def resolve_file_in_folder(folder: Path, relative_path: str) -> Path:
    rel = relative_path.strip().replace("\\", "/").lstrip("/")
    if not rel:
        raise HTTPException(status_code=400, detail="File path is required")
    rel_path = Path(rel)
    if rel_path.is_absolute() or ".." in rel_path.parts:
        raise HTTPException(status_code=400, detail="Invalid file path")
    target = (folder / rel_path).resolve()
    try:
        target.relative_to(folder)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid file path") from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found in output folder")
    return target


def _is_hidden_relative_path(rel: Path) -> bool:
    return any(part.startswith(".") for part in rel.parts)


def _looks_like_text(path: Path) -> bool:
    if path.suffix.lower() in _TEXT_EXTENSIONS:
        return True
    try:
        sample = path.read_bytes()[:4096]
    except OSError:
        return False
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _read_text_preview(path: Path) -> tuple[str, bool]:
    raw = path.read_bytes()
    truncated = len(raw) > MAX_INLINE_TEXT_BYTES
    if truncated:
        raw = raw[:MAX_INLINE_TEXT_BYTES]
    text = raw.decode("utf-8", errors="replace")
    if len(text) > MAX_INLINE_TEXT_CHARS:
        text = text[:MAX_INLINE_TEXT_CHARS]
        truncated = True
    if truncated:
        text = text.rstrip() + "\n...(truncated)"
    return text, truncated


def list_output_files(folder: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(folder)
        if _is_hidden_relative_path(rel):
            continue
        entry: dict[str, Any] = {
            "path": rel.as_posix(),
            "name": path.name,
            "size_bytes": path.stat().st_size,
        }
        if _looks_like_text(path):
            content, truncated = _read_text_preview(path)
            entry["content_type"] = "text"
            entry["content"] = content
            entry["truncated"] = truncated
        else:
            entry["content_type"] = "binary"
            entry["preview_unavailable"] = True
        files.append(entry)
        if len(files) > MAX_OUTPUT_FILES:
            raise HTTPException(status_code=400, detail=f"Output folder exceeds {MAX_OUTPUT_FILES} files")
    files.sort(key=lambda item: (item["path"] != "README.md", item["path"].lower()))
    return files


def read_output_file(folder: Path, relative_path: str) -> dict[str, Any]:
    target = resolve_file_in_folder(folder, relative_path)
    rel = target.relative_to(folder).as_posix()
    entry: dict[str, Any] = {
        "path": rel,
        "name": target.name,
        "size_bytes": target.stat().st_size,
    }
    if _looks_like_text(target):
        content, truncated = _read_text_preview(target)
        entry["content_type"] = "text"
        entry["content"] = content
        entry["truncated"] = truncated
    else:
        entry["content_type"] = "binary"
        entry["preview_unavailable"] = True
    return entry


def build_output_folder_zip(folder: Path) -> tuple[bytes, str]:
    buffer = io.BytesIO()
    file_count = 0
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(folder)
            if _is_hidden_relative_path(rel):
                continue
            archive.write(path, arcname=rel.as_posix())
            file_count += 1
            if file_count > MAX_OUTPUT_FILES:
                raise HTTPException(status_code=400, detail=f"Output folder exceeds {MAX_OUTPUT_FILES} files")
    if file_count == 0:
        raise HTTPException(status_code=400, detail="Output folder is empty")
    filename = f"{folder.name}.zip"
    return buffer.getvalue(), filename

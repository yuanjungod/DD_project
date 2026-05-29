"""Atomic file writes shared across filesystem-backed stores."""

from __future__ import annotations

import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str, *, tmp_prefix: str = ".atomic_") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=tmp_prefix, suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        Path(tmp).replace(path)
    except Exception:
        try:
            Path(tmp).unlink(missing_ok=True)
        except OSError:
            pass
        raise

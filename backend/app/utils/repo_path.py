"""Ensure repository root is on sys.path once for ``import shared``."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONFIGURED = False


def ensure_repo_on_path() -> Path:
    global _CONFIGURED
    root = str(_REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    _CONFIGURED = True
    return _REPO_ROOT


def repo_root() -> Path:
    ensure_repo_on_path()
    return _REPO_ROOT

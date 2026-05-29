from __future__ import annotations

import logging
import os
import shutil
import warnings
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

HARNESS_PROJECT_DIR = ".harness_project"
LEGACY_DD_PROJECT_DIR = ".dd_project"
DEFAULT_DATA_SUBDIR = "data"
HARNESS_PLATFORM_DB = "harness_platform.db"
LEGACY_PLATFORM_DB = "dd_platform.db"


@dataclass
class MigrationResult:
    action: str
    source: Path | None = None
    target: Path | None = None
    platform_db_renamed: bool = False
    messages: list[str] = field(default_factory=list)


def resolve_env_with_legacy(primary: str, legacy: str | None, default: str = "") -> tuple[str, bool]:
    """Return (value, used_legacy)."""

    primary_value = os.environ.get(primary, "").strip()
    if primary_value:
        return primary_value, False
    if legacy:
        legacy_value = os.environ.get(legacy, "").strip()
        if legacy_value:
            warnings.warn(
                f"{legacy} is deprecated; use {primary} instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            logger.warning("%s is deprecated; migrate to %s", legacy, primary)
            return legacy_value, True
    return default, False


def resolve_repo_path(repo_root: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def default_data_root_relative(repo_root: Path) -> str:
    harness_data = repo_root / HARNESS_PROJECT_DIR / DEFAULT_DATA_SUBDIR
    legacy_data = repo_root / LEGACY_DD_PROJECT_DIR / DEFAULT_DATA_SUBDIR
    if harness_data.parent.exists() or not legacy_data.parent.exists():
        return f"{HARNESS_PROJECT_DIR}/{DEFAULT_DATA_SUBDIR}"
    return f"{LEGACY_DD_PROJECT_DIR}/{DEFAULT_DATA_SUBDIR}"


def runtime_project_home(repo_root: Path) -> Path:
    """Unified runtime home (.harness_project with legacy .dd_project fallback)."""

    configured, _ = resolve_env_with_legacy("HARNESS_DATA_ROOT", "DD_DATA_ROOT", "")
    if configured:
        configured_path = resolve_repo_path(repo_root, configured)
        if configured_path.name == DEFAULT_DATA_SUBDIR:
            return configured_path.parent
        return configured_path

    harness_home = repo_root / HARNESS_PROJECT_DIR
    legacy_home = repo_root / LEGACY_DD_PROJECT_DIR
    if harness_home.exists() or not legacy_home.exists():
        harness_home.mkdir(parents=True, exist_ok=True)
        return harness_home

    logger.warning(
        "Using legacy %s runtime home; migrate to %s",
        LEGACY_DD_PROJECT_DIR,
        HARNESS_PROJECT_DIR,
    )
    return legacy_home


def platform_db_path(data_root: Path) -> Path:
    platform_dir = data_root / "platform"
    platform_dir.mkdir(parents=True, exist_ok=True)
    harness_db = platform_dir / HARNESS_PLATFORM_DB
    legacy_db = platform_dir / LEGACY_PLATFORM_DB
    if legacy_db.is_file() and not harness_db.is_file():
        return legacy_db
    return harness_db


def rename_legacy_platform_db(project_home: Path, *, dry_run: bool = False) -> bool:
    """Rename data/platform/dd_platform.db to harness_platform.db when safe."""

    platform_dir = project_home / DEFAULT_DATA_SUBDIR / "platform"
    legacy_db = platform_dir / LEGACY_PLATFORM_DB
    harness_db = platform_dir / HARNESS_PLATFORM_DB
    if not legacy_db.is_file() or harness_db.exists():
        return False
    if dry_run:
        return True
    legacy_db.rename(harness_db)
    return True


def migrate_legacy_project_home(
    repo_root: Path,
    *,
    dry_run: bool = False,
    merge: bool = False,
) -> MigrationResult:
    """Copy legacy `.dd_project/` into `.harness_project/` and rename platform SQLite when safe."""

    source = repo_root / LEGACY_DD_PROJECT_DIR
    target = repo_root / HARNESS_PROJECT_DIR
    messages: list[str] = []

    if not source.is_dir():
        messages.append(f"No {LEGACY_DD_PROJECT_DIR}/ directory found; nothing to migrate.")
        return MigrationResult(action="none", messages=messages)

    if target.exists() and not merge:
        messages.append(
            f"{HARNESS_PROJECT_DIR}/ already exists. Re-run with --merge to combine trees, "
            f"or remove {HARNESS_PROJECT_DIR}/ first."
        )
        return MigrationResult(action="blocked", source=source, target=target, messages=messages)

    action = "merge" if target.exists() else "copy"
    if dry_run:
        messages.append(f"Would {action} {source} -> {target}")
    else:
        if target.exists():
            shutil.copytree(source, target, dirs_exist_ok=True)
            messages.append(f"Merged {source} into existing {target}")
        else:
            shutil.copytree(source, target)
            messages.append(f"Copied {source} -> {target}")

    db_renamed = rename_legacy_platform_db(target, dry_run=dry_run)
    if db_renamed:
        label = "Would rename" if dry_run else "Renamed"
        messages.append(
            f"{label} {DEFAULT_DATA_SUBDIR}/platform/{LEGACY_PLATFORM_DB} -> {HARNESS_PLATFORM_DB}"
        )

    return MigrationResult(
        action=f"dry_run_{action}" if dry_run else action,
        source=source,
        target=target,
        platform_db_renamed=db_renamed,
        messages=messages,
    )

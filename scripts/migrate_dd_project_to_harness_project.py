#!/usr/bin/env python3
"""Migrate legacy .dd_project runtime data to .harness_project."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.harness_paths import migrate_legacy_project_home


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy .dd_project/ to .harness_project/ and rename dd_platform.db when safe.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_REPO_ROOT,
        help="Repository root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without writing files",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge into an existing .harness_project/ tree instead of failing",
    )
    args = parser.parse_args()

    result = migrate_legacy_project_home(args.repo_root.resolve(), dry_run=args.dry_run, merge=args.merge)
    for message in result.messages:
        print(message)

    if result.action == "blocked":
        return 1
    if result.action == "none":
        return 0
    print(f"Done ({result.action}). Restart backend/agent services to pick up {result.target}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

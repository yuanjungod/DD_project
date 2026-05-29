"""Tests for Harness runtime path resolution and legacy migration."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from shared.harness_paths import (
    HARNESS_PLATFORM_DB,
    HARNESS_PROJECT_DIR,
    LEGACY_DD_PROJECT_DIR,
    LEGACY_PLATFORM_DB,
    default_data_root_relative,
    migrate_legacy_project_home,
    platform_db_path,
    rename_legacy_platform_db,
    runtime_project_home,
)


class HarnessPathsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)

    def _scratch(self, name: str) -> Path:
        path = Path(self._tempdir.name) / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def test_new_clone_creates_harness_home(self) -> None:
        root = self._scratch("fresh")
        home = runtime_project_home(root)
        self.assertEqual(home, root / HARNESS_PROJECT_DIR)
        self.assertTrue(home.is_dir())

    def test_legacy_fallback_when_only_dd_project_exists(self) -> None:
        root = self._scratch("legacy_only")
        legacy = root / LEGACY_DD_PROJECT_DIR
        legacy.mkdir()
        with mock.patch("shared.harness_paths.logger") as logger:
            home = runtime_project_home(root)
        self.assertEqual(home, legacy)
        logger.warning.assert_called_once()

    def test_harness_home_takes_priority_over_legacy(self) -> None:
        root = self._scratch("both")
        (root / HARNESS_PROJECT_DIR).mkdir()
        (root / LEGACY_DD_PROJECT_DIR).mkdir()
        home = runtime_project_home(root)
        self.assertEqual(home, root / HARNESS_PROJECT_DIR)

    def test_harness_data_root_override(self) -> None:
        root = self._scratch("custom")
        custom = root / "runtime" / "data"
        custom.mkdir(parents=True)
        env = {"HARNESS_DATA_ROOT": str(custom)}
        with mock.patch.dict(os.environ, env, clear=False):
            home = runtime_project_home(root)
        self.assertEqual(home.resolve(), custom.parent.resolve())

    def test_default_data_root_relative_prefers_harness_on_fresh_clone(self) -> None:
        root = self._scratch("defaults")
        rel = default_data_root_relative(root)
        self.assertEqual(rel, f"{HARNESS_PROJECT_DIR}/data")

    def test_default_data_root_relative_uses_legacy_when_only_dd_exists(self) -> None:
        root = self._scratch("legacy_default")
        (root / LEGACY_DD_PROJECT_DIR / "data").mkdir(parents=True)
        rel = default_data_root_relative(root)
        self.assertEqual(rel, f"{LEGACY_DD_PROJECT_DIR}/data")

    def test_platform_db_reads_legacy_when_harness_missing(self) -> None:
        data_root = self._scratch("db_legacy") / "data"
        platform = data_root / "platform"
        platform.mkdir(parents=True)
        (platform / LEGACY_PLATFORM_DB).write_text("legacy", encoding="utf-8")
        path = platform_db_path(data_root)
        self.assertEqual(path.name, LEGACY_PLATFORM_DB)

    def test_platform_db_prefers_harness_when_both_exist(self) -> None:
        data_root = self._scratch("db_both") / "data"
        platform = data_root / "platform"
        platform.mkdir(parents=True)
        (platform / LEGACY_PLATFORM_DB).write_text("legacy", encoding="utf-8")
        (platform / HARNESS_PLATFORM_DB).write_text("harness", encoding="utf-8")
        path = platform_db_path(data_root)
        self.assertEqual(path.name, HARNESS_PLATFORM_DB)

    def test_migrate_copies_tree_and_renames_db(self) -> None:
        root = self._scratch("migrate")
        legacy = root / LEGACY_DD_PROJECT_DIR
        (legacy / "users" / "user_a").mkdir(parents=True)
        (legacy / "data" / "platform").mkdir(parents=True)
        (legacy / "data" / "platform" / LEGACY_PLATFORM_DB).write_text("sqlite", encoding="utf-8")
        (legacy / "engagement_index.json").write_text("{}", encoding="utf-8")

        result = migrate_legacy_project_home(root)
        target = root / HARNESS_PROJECT_DIR
        self.assertEqual(result.action, "copy")
        self.assertTrue((target / "users" / "user_a").is_dir())
        self.assertTrue((target / "data" / "platform" / HARNESS_PLATFORM_DB).is_file())
        self.assertFalse((target / "data" / "platform" / LEGACY_PLATFORM_DB).exists())
        self.assertTrue(result.platform_db_renamed)

    def test_migrate_blocked_when_target_exists_without_merge(self) -> None:
        root = self._scratch("blocked")
        (root / LEGACY_DD_PROJECT_DIR).mkdir()
        (root / HARNESS_PROJECT_DIR).mkdir()
        result = migrate_legacy_project_home(root)
        self.assertEqual(result.action, "blocked")

    def test_migrate_merge_into_existing_target(self) -> None:
        root = self._scratch("merge")
        legacy = root / LEGACY_DD_PROJECT_DIR
        target = root / HARNESS_PROJECT_DIR
        (legacy / "users" / "legacy_user").mkdir(parents=True)
        (target / "users" / "harness_user").mkdir(parents=True)

        result = migrate_legacy_project_home(root, merge=True)
        self.assertEqual(result.action, "merge")
        self.assertTrue((target / "users" / "legacy_user").is_dir())
        self.assertTrue((target / "users" / "harness_user").is_dir())

    def test_rename_legacy_platform_db_dry_run(self) -> None:
        home = self._scratch("rename_dry")
        platform = home / "data" / "platform"
        platform.mkdir(parents=True)
        (platform / LEGACY_PLATFORM_DB).write_text("db", encoding="utf-8")
        renamed = rename_legacy_platform_db(home, dry_run=True)
        self.assertTrue(renamed)
        self.assertTrue((platform / LEGACY_PLATFORM_DB).is_file())


if __name__ == "__main__":
    unittest.main()

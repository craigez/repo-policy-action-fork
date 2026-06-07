# Copyright (c) Qualcomm Technologies, Inc.
# SPDX-License-Identifier: BSD-3-Clause

"""Tests for rules/file_existence.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.reporter import Reporter
from src.rules.file_existence import run


class TestFileExistenceRule(unittest.TestCase):
    def setUp(self):
        self.reporter = Reporter()

    def _make_repo(self, files: list[str]) -> str:
        tmp = tempfile.mkdtemp()
        for rel_path in files:
            path = Path(tmp) / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        return tmp

    def test_passes_when_file_exists(self):
        """Rule passes when a matching file is found at the repo root."""
        repo = self._make_repo(["LICENSE"])
        result = run(
            repo_path=repo,
            rule_name="license-file-exists",
            level="error",
            options={"globsAny": ["LICENSE", "COPYING", "NOTICE"]},
            reporter=self.reporter,
        )
        self.assertTrue(result.passed)

    def test_fails_when_no_file_exists(self):
        """Rule fails when no matching file is found."""
        repo = self._make_repo([])
        result = run(
            repo_path=repo,
            rule_name="license-file-exists",
            level="error",
            options={"globsAny": ["LICENSE", "COPYING", "NOTICE"]},
            reporter=self.reporter,
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.level, "error")

    def test_matches_nested_file(self):
        """Rule passes when the file is in a subdirectory."""
        repo = self._make_repo([".github/CONTRIBUTING.md"])
        result = run(
            repo_path=repo,
            rule_name="contributing-file-exists",
            level="warning",
            options={
                "globsAny": ["CONTRIBUTING*"],
                "dirs": ["", "docs", ".github"],
            },
            reporter=self.reporter,
        )
        self.assertTrue(result.passed)

    def test_level_is_preserved_on_failure(self):
        """Failing result preserves the configured level."""
        repo = self._make_repo([])
        result = run(
            repo_path=repo,
            rule_name="changelog-file-exists",
            level="warning",
            options={"globsAny": ["CHANGELOG*"]},
            reporter=self.reporter,
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.level, "warning")

    def test_no_globs_returns_pass(self):
        """Rule with no patterns configured passes (skipped)."""
        repo = self._make_repo([])
        result = run(
            repo_path=repo,
            rule_name="empty-rule",
            level="error",
            options={},
            reporter=self.reporter,
        )
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()

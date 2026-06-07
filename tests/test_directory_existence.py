# Copyright (c) Qualcomm Technologies, Inc.
# SPDX-License-Identifier: BSD-3-Clause

"""Tests for rules/directory_existence.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.reporter import Reporter
from src.rules.directory_existence import run


class TestDirectoryExistenceRule(unittest.TestCase):
    def setUp(self):
        self.reporter = Reporter()

    def _make_repo(self, dirs: list[str]) -> str:
        tmp = tempfile.mkdtemp()
        for rel_dir in dirs:
            (Path(tmp) / rel_dir).mkdir(parents=True, exist_ok=True)
        return tmp

    def test_passes_when_directory_exists(self):
        """Rule passes when a matching directory is found."""
        repo = self._make_repo(["tests"])
        result = run(
            repo_path=repo,
            rule_name="test-directory-exists",
            level="warning",
            options={"globsAny": ["**/test*", "**/spec*"]},
            reporter=self.reporter,
        )
        self.assertTrue(result.passed)

    def test_passes_with_nested_test_dir(self):
        """Rule passes when test directory is nested."""
        repo = self._make_repo(["src/tests"])
        result = run(
            repo_path=repo,
            rule_name="test-directory-exists",
            level="warning",
            options={"globsAny": ["**/test*"]},
            reporter=self.reporter,
        )
        self.assertTrue(result.passed)

    def test_fails_when_no_directory_matches(self):
        """Rule fails when no matching directory is found."""
        repo = self._make_repo(["src", "docs"])
        result = run(
            repo_path=repo,
            rule_name="test-directory-exists",
            level="warning",
            options={"globsAny": ["**/test*", "**/spec*"]},
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
            level="warning",
            options={},
            reporter=self.reporter,
        )
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()

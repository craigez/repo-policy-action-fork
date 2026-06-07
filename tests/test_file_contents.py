# Copyright (c) Qualcomm Technologies, Inc.
# SPDX-License-Identifier: BSD-3-Clause

"""Tests for rules/file_contents.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.reporter import Reporter
from src.rules.file_contents import run


class TestFileContentsRule(unittest.TestCase):
    def setUp(self):
        self.reporter = Reporter()

    def _make_repo(self, files: dict[str, str]) -> str:
        """Create a temporary repo with files mapping path→content."""
        tmp = tempfile.mkdtemp()
        for rel_path, content in files.items():
            path = Path(tmp) / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return tmp

    def test_passes_when_pattern_found(self):
        """Rule passes when the pattern is found in a matched file."""
        repo = self._make_repo(
            {"README.md": "This project is released under the MIT license."}
        )
        result = run(
            repo_path=repo,
            rule_name="readme-references-license",
            level="error",
            options={
                "globsAll": ["README*"],
                "content": "license|notice",
                "flags": ["IGNORECASE"],
            },
            reporter=self.reporter,
        )
        self.assertTrue(result.passed)

    def test_fails_when_pattern_missing(self):
        """Rule fails when the pattern is absent from a matched file."""
        repo = self._make_repo({"README.md": "Hello world."})
        result = run(
            repo_path=repo,
            rule_name="readme-references-license",
            level="error",
            options={
                "globsAll": ["README*"],
                "content": "license|notice",
                "flags": ["IGNORECASE"],
            },
            reporter=self.reporter,
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.level, "error")

    def test_file_starts_with_line_count(self):
        """lineCount restricts the search to the first N lines."""
        content = "\n".join(
            ["# Copyright Qualcomm Technologies, Inc."] + ["code"] * 20
        )
        repo = self._make_repo({"src/main.py": content})
        result = run(
            repo_path=repo,
            rule_name="source-qualcomm-license-headers-exist",
            level="warning",
            options={
                "globsAll": ["src/*.py"],
                "content": "Qualcomm",
                "lineCount": 5,
            },
            reporter=self.reporter,
        )
        self.assertTrue(result.passed)

    def test_line_count_does_not_match_later_content(self):
        """lineCount prevents matching content beyond the first N lines."""
        content = "\n".join(["code"] * 10 + ["# Copyright Qualcomm"])
        repo = self._make_repo({"src/main.py": content})
        result = run(
            repo_path=repo,
            rule_name="source-qualcomm-license-headers-exist",
            level="warning",
            options={
                "globsAll": ["src/*.py"],
                "content": "Qualcomm",
                "lineCount": 5,
            },
            reporter=self.reporter,
        )
        self.assertFalse(result.passed)

    def test_no_matching_files_with_fail_on_non_existent(self):
        """fail-on-non-existent causes failure when no files match."""
        repo = self._make_repo({})
        result = run(
            repo_path=repo,
            rule_name="readme-references-license",
            level="error",
            options={
                "globsAll": ["README*"],
                "content": "license",
                "fail-on-non-existent": True,
            },
            reporter=self.reporter,
        )
        self.assertFalse(result.passed)

    def test_no_matching_files_without_flag_passes(self):
        """Without fail-on-non-existent, no matching files is a pass."""
        repo = self._make_repo({})
        result = run(
            repo_path=repo,
            rule_name="readme-references-license",
            level="error",
            options={
                "globsAll": ["README*"],
                "content": "license",
                "fail-on-non-existent": False,
            },
            reporter=self.reporter,
        )
        self.assertTrue(result.passed)

    def test_skips_node_modules(self):
        """Files inside node_modules/ are not checked."""
        repo = self._make_repo(
            {"node_modules/pkg/index.js": "// no copyright here"}
        )
        result = run(
            repo_path=repo,
            rule_name="source-qualcomm-license-headers-exist",
            level="warning",
            options={
                "globsAll": ["**/*.js"],
                "content": "Qualcomm",
            },
            reporter=self.reporter,
        )
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()

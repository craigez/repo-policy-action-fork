# Copyright (c) Qualcomm Technologies, Inc.
# SPDX-License-Identifier: BSD-3-Clause

"""Integration-style tests for the rule dispatcher (rules/__init__.py)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.language_detector import detect_languages
from src.reporter import Reporter
from src.rules import run_all_rules

_MINIMAL_CONFIG = {
    "version": 2,
    "rules": {
        "license-file-exists": {
            "level": "error",
            "rule": {
                "type": "file-existence",
                "options": {"globsAny": ["LICENSE", "COPYING"]},
            },
        },
        "readme-file-exists": {
            "level": "error",
            "rule": {
                "type": "file-existence",
                "options": {"globsAny": ["README*"]},
            },
        },
        "disabled-rule": {
            "level": "off",
            "rule": {
                "type": "file-existence",
                "options": {"globsAny": ["NONEXISTENT"]},
            },
        },
    },
}

_LANGUAGE_CONDITIONAL_CONFIG = {
    "version": 2,
    "rules": {
        "rust-cargo-exists": {
            "level": "error",
            "where": ["linguist=Rust"],
            "rule": {
                "type": "file-existence",
                "options": {"globsAny": ["Cargo.toml"]},
            },
        },
    },
}


class TestRunAllRules(unittest.TestCase):
    def setUp(self):
        self.reporter = Reporter()

    def _make_repo(self, files: list[str]) -> str:
        tmp = tempfile.mkdtemp()
        for rel_path in files:
            path = Path(tmp) / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        return tmp

    def test_passing_repo(self):
        """All rules pass for a repo with all required files."""
        repo = self._make_repo(["LICENSE", "README.md"])
        languages = detect_languages(repo)
        results = run_all_rules(
            repo_path=repo,
            config=_MINIMAL_CONFIG,
            languages=languages,
            reporter=self.reporter,
        )
        self.assertTrue(all(r.passed for r in results))

    def test_failing_repo(self):
        """Error-level rules fail for a repo missing required files."""
        repo = self._make_repo([])
        languages = detect_languages(repo)
        results = run_all_rules(
            repo_path=repo,
            config=_MINIMAL_CONFIG,
            languages=languages,
            reporter=self.reporter,
        )
        failed = [r for r in results if not r.passed]
        self.assertEqual(len(failed), 2)

    def test_off_rules_are_skipped(self):
        """Rules with level='off' are not evaluated."""
        repo = self._make_repo(["LICENSE", "README.md"])
        languages = detect_languages(repo)
        results = run_all_rules(
            repo_path=repo,
            config=_MINIMAL_CONFIG,
            languages=languages,
            reporter=self.reporter,
        )
        rule_names = [r.rule_name for r in results]
        self.assertNotIn("disabled-rule", rule_names)

    def test_language_conditional_skipped_when_not_detected(self):
        """Language-conditional rules are skipped for non-matching repos."""
        repo = self._make_repo(["src/main.py", "src/utils.py"])
        languages = detect_languages(repo)
        results = run_all_rules(
            repo_path=repo,
            config=_LANGUAGE_CONDITIONAL_CONFIG,
            languages=languages,
            reporter=self.reporter,
        )
        # No Rust detected → rule should not have been evaluated
        self.assertEqual(len(results), 0)

    def test_language_conditional_applied_when_detected(self):
        """Language-conditional rules run when the language is detected."""
        repo = self._make_repo(["src/main.rs", "src/lib.rs"])
        languages = detect_languages(repo)
        results = run_all_rules(
            repo_path=repo,
            config=_LANGUAGE_CONDITIONAL_CONFIG,
            languages=languages,
            reporter=self.reporter,
        )
        # Rust detected, Cargo.toml missing → rule should fail
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].passed)


_WILDCARD_AXIOM_CONFIG = {
    "version": 2,
    "rules": {
        "any-language-check": {
            "level": "warning",
            "where": ["linguist=*"],
            "rule": {
                "type": "file-existence",
                "options": {"globsAny": ["README*"]},
            },
        },
    },
}

_UNKNOWN_AXIOM_CONFIG = {
    "version": 2,
    "rules": {
        "unknown-axiom-rule": {
            "level": "warning",
            "where": ["unknown_axiom=somevalue"],
            "rule": {
                "type": "file-existence",
                "options": {"globsAny": ["README*"]},
            },
        },
    },
}


class TestAxiomEdgeCases(unittest.TestCase):
    def setUp(self):
        self.reporter = Reporter()

    def _make_repo(self, files: list[str]) -> str:
        tmp = tempfile.mkdtemp()
        for rel_path in files:
            path = Path(tmp) / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        return tmp

    def test_wildcard_axiom_runs_when_any_language_detected(self):
        """linguist=* runs the rule when any language is detected."""
        repo = self._make_repo(["src/main.py", "src/utils.py", "README.md"])
        languages = detect_languages(repo)
        results = run_all_rules(
            repo_path=repo,
            config=_WILDCARD_AXIOM_CONFIG,
            languages=languages,
            reporter=self.reporter,
        )
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].passed)

    def test_wildcard_axiom_skipped_when_no_language_detected(self):
        """linguist=* skips the rule when no language is detected."""
        repo = self._make_repo(["README.md", "config.yaml"])
        languages = detect_languages(repo)
        results = run_all_rules(
            repo_path=repo,
            config=_WILDCARD_AXIOM_CONFIG,
            languages=languages,
            reporter=self.reporter,
        )
        self.assertEqual(len(results), 0)

    def test_unknown_axiom_key_does_not_prevent_rule_running(self):
        """An unrecognised axiom key in where is logged and skipped,
        not treated as a failing condition."""
        repo = self._make_repo(["README.md"])
        languages = detect_languages(repo)
        results = run_all_rules(
            repo_path=repo,
            config=_UNKNOWN_AXIOM_CONFIG,
            languages=languages,
            reporter=self.reporter,
        )
        # Unknown axiom is skipped (non-blocking); rule still runs.
        self.assertEqual(len(results), 1)


_FILE_TYPE_EXCLUSION_CONFIG = {
    "version": 2,
    "rules": {
        "binaries-not-present": {
            "level": "warning",
            "rule": {
                "type": "file-type-exclusion",
                "options": {
                    "type": ["**/*.exe", "**/*.dll", "!node_modules/**"]
                },
            },
        },
    },
}


class TestFileTypeExclusionAlias(unittest.TestCase):
    def setUp(self):
        self.reporter = Reporter()

    def _make_repo(self, files: list[str]) -> str:
        tmp = tempfile.mkdtemp()
        for rel_path in files:
            path = Path(tmp) / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        return tmp

    def test_file_type_exclusion_type_is_dispatched(self):
        """file-type-exclusion rule type is routed to the binary checker."""
        repo = self._make_repo(["src/main.py", "README.md"])
        languages = detect_languages(repo)
        results = run_all_rules(
            repo_path=repo,
            config=_FILE_TYPE_EXCLUSION_CONFIG,
            languages=languages,
            reporter=self.reporter,
        )
        # No actual binaries → rule passes.
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].passed)


if __name__ == "__main__":
    unittest.main()

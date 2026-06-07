# Copyright (c) Qualcomm Technologies, Inc.
# SPDX-License-Identifier: BSD-3-Clause

"""Tests for config.py — config loading and validation."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.config import load_config
from src.reporter import Reporter


class TestLoadConfig(unittest.TestCase):
    def setUp(self):
        self.reporter = Reporter()

    def test_loads_local_repolint_json(self, tmp_path=None):
        """load_config picks up a repolint.json at the repo root."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config_data = {"version": 2, "rules": {}}
            config_path = Path(tmp) / "repolint.json"
            config_path.write_text(json.dumps(config_data), encoding="utf-8")

            result = load_config(
                repo_path=tmp,
                config_file=None,
                config_url="https://example.com/config.json",
                reporter=self.reporter,
            )
            self.assertIsNotNone(result)
            self.assertEqual(result["version"], 2)

    def test_loads_repo_policy_json_over_repolint(self):
        """repo-policy.json takes priority over repolint.json."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "repolint.json").write_text(
                json.dumps({"version": 2, "rules": {}, "source": "repolint"}),
                encoding="utf-8",
            )
            Path(tmp, "repo-policy.json").write_text(
                json.dumps({"version": 2, "rules": {}, "source": "policy"}),
                encoding="utf-8",
            )

            result = load_config(
                repo_path=tmp,
                config_file=None,
                config_url="https://example.com/config.json",
                reporter=self.reporter,
            )
            self.assertEqual(result["source"], "policy")

    def test_explicit_config_file_wins(self):
        """An explicit --config-file path takes top priority."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            explicit = Path(tmp) / "custom.json"
            explicit.write_text(
                json.dumps({"version": 2, "rules": {}, "source": "explicit"}),
                encoding="utf-8",
            )

            result = load_config(
                repo_path=tmp,
                config_file=str(explicit),
                config_url="https://example.com/config.json",
                reporter=self.reporter,
            )
            self.assertEqual(result["source"], "explicit")

    @patch("src.config.requests.get")
    def test_falls_back_to_url(self, mock_get):
        """Falls back to fetching config_url when no local config found."""
        import tempfile

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "version": 2,
            "rules": {},
            "source": "url",
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with tempfile.TemporaryDirectory() as tmp:
            result = load_config(
                repo_path=tmp,
                config_file=None,
                config_url="https://example.com/config.json",
                reporter=self.reporter,
            )
            self.assertEqual(result["source"], "url")
            mock_get.assert_called_once()

    def test_invalid_json_returns_none(self):
        """Returns None when the config file contains invalid JSON."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "repolint.json").write_text(
                "not json!!", encoding="utf-8"
            )
            result = load_config(
                repo_path=tmp,
                config_file=None,
                config_url="https://example.com/config.json",
                reporter=self.reporter,
            )
            self.assertIsNone(result)

    def test_missing_rules_key_returns_none(self):
        """Returns None when the config has no 'rules' key."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "repolint.json").write_text(
                json.dumps({"version": 2}), encoding="utf-8"
            )
            result = load_config(
                repo_path=tmp,
                config_file=None,
                config_url="https://example.com/config.json",
                reporter=self.reporter,
            )
            self.assertIsNone(result)

    def test_unsupported_rule_type_does_not_fail(self):
        """Unsupported rule types are skipped, not fatal."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config_data = {
                "version": 2,
                "rules": {
                    "some-rule": {
                        "level": "warning",
                        "rule": {"type": "license-detectable-by-licensee"},
                    }
                },
            }
            Path(tmp, "repolint.json").write_text(
                json.dumps(config_data), encoding="utf-8"
            )
            result = load_config(
                repo_path=tmp,
                config_file=None,
                config_url="https://example.com/config.json",
                reporter=self.reporter,
            )
            self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()

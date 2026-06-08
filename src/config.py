# Copyright (c) Qualcomm Technologies, Inc.
# SPDX-License-Identifier: BSD-3-Clause

"""Config loading for repo-policy-action.

Resolves the policy config in priority order:
  1. Explicit --config-file argument
  2. repo-policy.json at the repo root (future v2 format)
  3. repolint.json at the repo root (backwards-compatible override)
  4. URL from --config-url (the Qualcomm org default config)

Parses a strict subset of the repolint.json v2 schema — only the rule
types present in the Qualcomm default config. Unsupported rule types
are skipped with a warning rather than causing a failure.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import requests

from reporter import Reporter

logger = logging.getLogger(__name__)

# Rule types this action knows how to execute. Any other type found in
# the config is skipped with a warning.
SUPPORTED_RULE_TYPES = frozenset(
    {
        "file-existence",
        "file-starts-with",
        "file-contents",
        "no-file-type-exists",
        "directory-existence",
    }
)


def load_config(
    repo_path: str,
    config_file: str | None,
    config_url: str,
    reporter: Reporter,
) -> dict[str, Any] | None:
    """Load and validate the policy config.

    Args:
        repo_path: Absolute path to the repository root.
        config_file: Explicit path to a config file, or None.
        config_url: Fallback URL to fetch config from.
        reporter: Reporter instance for emitting warnings.

    Returns:
        Parsed config dict, or None if loading failed.
    """
    raw = _resolve_config(repo_path, config_file, config_url, reporter)
    if raw is None:
        return None
    return _validate_config(raw, reporter)


def _resolve_config(
    repo_path: str,
    config_file: str | None,
    config_url: str,
    reporter: Reporter,
) -> dict[str, Any] | None:
    """Return the raw parsed JSON config from the highest-priority source."""
    if config_file:
        path = Path(config_file)
        logger.info("Using explicit config file: %s", path)
        return _load_json_file(path, reporter)

    root = Path(repo_path)

    for candidate in ("repo-policy.json", "repolint.json"):
        candidate_path = root / candidate
        if candidate_path.exists():
            logger.info("Using local config: %s", candidate_path)
            return _load_json_file(candidate_path, reporter)

    logger.info("No local config found; fetching from %s", config_url)
    return _fetch_json_url(config_url, reporter)


def _load_json_file(path: Path, reporter: Reporter) -> dict[str, Any] | None:
    """Parse a JSON file and return its contents.

    Args:
        path: Path to the JSON file.
        reporter: Reporter instance for emitting errors.

    Returns:
        Parsed dict, or None on failure.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        reporter.error(f"Config file not found: {path}")
        return None
    except json.JSONDecodeError as exc:
        reporter.error(f"Config file is not valid JSON ({path}): {exc}")
        return None


def _fetch_json_url(url: str, reporter: Reporter) -> dict[str, Any] | None:
    """Fetch and parse a JSON config from a URL.

    Args:
        url: URL to fetch.
        reporter: Reporter instance for emitting errors.

    Returns:
        Parsed dict, or None on failure.
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        reporter.error(f"Failed to fetch config from {url}: {exc}")
        return None
    except json.JSONDecodeError as exc:
        reporter.error(f"Config fetched from {url} is not valid JSON: {exc}")
        return None


def _validate_config(
    raw: dict[str, Any], reporter: Reporter
) -> dict[str, Any] | None:
    """Validate top-level config structure and warn on unsupported rules.

    Args:
        raw: Parsed config dict.
        reporter: Reporter instance for emitting warnings.

    Returns:
        The config dict (possibly with unsupported rules noted), or None
        if the config is structurally invalid.
    """
    if "rules" not in raw:
        reporter.error("Config is missing the required 'rules' key.")
        return None

    for rule_name, rule_def in raw["rules"].items():
        rule_type = rule_def.get("rule", {}).get("type", "")
        if rule_type and rule_type not in SUPPORTED_RULE_TYPES:
            logger.warning(
                "Rule '%s' uses unsupported type '%s' — skipping.",
                rule_name,
                rule_type,
            )

    return raw

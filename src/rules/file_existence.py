# Copyright (c) Qualcomm Technologies, Inc.
# SPDX-License-Identifier: BSD-3-Clause

"""file-existence rule type for repo-policy-action.

Checks that at least one file matching any of the provided glob
patterns exists somewhere under the repository root (optionally
restricted to specific subdirectories).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from reporter import Reporter, RuleResult

logger = logging.getLogger(__name__)


def run(
    repo_path: str,
    rule_name: str,
    level: str,
    options: dict[str, Any],
    reporter: Reporter,
) -> RuleResult:
    """Evaluate a file-existence rule.

    Args:
        repo_path: Absolute path to the repository root.
        rule_name: Rule identifier for annotations.
        level: ``"error"`` or ``"warning"``.
        options: Rule options from the config. Expected keys:
            - ``"globsAny"`` (list[str]): glob patterns, at least one
              must match.
            - ``"dirs"`` (list[str], optional): restrict search to
              these subdirectories relative to the repo root.
        reporter: Reporter instance.

    Returns:
        A RuleResult indicating pass or failure.
    """
    globs: list[str] = options.get("globsAny", [])
    dirs: list[str] = options.get("dirs", [""])

    if not globs:
        logger.warning(
            "Rule '%s' has no globsAny patterns — skipping.", rule_name
        )
        return reporter.rule_passed(
            rule_name, "No patterns configured — skipped."
        )

    root = Path(repo_path)
    for search_dir in dirs:
        base = root / search_dir if search_dir else root
        if not base.is_dir():
            continue
        for pattern in globs:
            matches = list(base.glob(pattern))
            if matches:
                logger.debug(
                    "Rule '%s' passed — found '%s'.",
                    rule_name,
                    matches[0],
                )
                return reporter.rule_passed(
                    rule_name,
                    f"Found: {matches[0].relative_to(root)}",
                )

    searched = ", ".join(
        (str(root / d) if d else str(root)) for d in dirs
    )
    return reporter.rule_failed(
        rule_name=rule_name,
        level=level,
        message=(
            f"No file matching {globs} found in: {searched}"
        ),
    )

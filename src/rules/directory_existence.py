# Copyright (c) Qualcomm Technologies, Inc.
# SPDX-License-Identifier: BSD-3-Clause

"""directory-existence rule type for repo-policy-action.

Checks that at least one directory matching any of the provided glob
patterns exists under the repository root.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from reporter import Reporter, RuleResult
from rules._common import globs_any_or_skip

logger = logging.getLogger(__name__)


def run(
    repo_path: str,
    rule_name: str,
    level: str,
    options: dict[str, Any],
    reporter: Reporter,
) -> RuleResult:
    """Evaluate a directory-existence rule.

    Args:
        repo_path: Absolute path to the repository root.
        rule_name: Rule identifier for annotations.
        level: ``"error"`` or ``"warning"``.
        options: Rule options from the config. Expected keys:
            - ``"globsAny"`` (list[str]): glob patterns, at least one
              must match a directory.
        reporter: Reporter instance.

    Returns:
        A RuleResult indicating pass or failure.
    """
    globs: list[str] = options.get("globsAny", [])

    skip_result = globs_any_or_skip(globs, rule_name, reporter)
    if skip_result is not None:
        return skip_result

    root = Path(repo_path)
    for pattern in globs:
        matches = [p for p in root.glob(pattern) if p.is_dir()]
        if matches:
            logger.debug(
                "Rule '%s' passed — found directory '%s'.",
                rule_name,
                matches[0],
            )
            return reporter.rule_passed(
                rule_name,
                f"Found directory: {matches[0].relative_to(root)}",
            )

    return reporter.rule_failed(
        rule_name=rule_name,
        level=level,
        message=f"No directory matching {globs} found under {root}",
    )

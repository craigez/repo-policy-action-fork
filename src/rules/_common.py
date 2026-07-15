# Copyright (c) Qualcomm Technologies, Inc.
# SPDX-License-Identifier: BSD-3-Clause

"""Helpers shared across rule modules."""

from __future__ import annotations

import logging

from reporter import Reporter, RuleResult

logger = logging.getLogger(__name__)


def globs_any_or_skip(
    globs: list[str], rule_name: str, reporter: Reporter
) -> RuleResult | None:
    """Return a passing RuleResult if ``globsAny`` is empty, else None.

    Args:
        globs: The rule's ``globsAny`` option value.
        rule_name: Rule identifier for annotations.
        reporter: Reporter instance.

    Returns:
        A passing RuleResult if there are no patterns to check, or
        None to signal the caller should proceed with evaluation.
    """
    if globs:
        return None
    logger.warning("Rule '%s' has no globsAny patterns — skipping.", rule_name)
    return reporter.rule_passed(rule_name, "No patterns configured — skipped.")

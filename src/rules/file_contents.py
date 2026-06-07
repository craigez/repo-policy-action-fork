# Copyright (c) Qualcomm Technologies, Inc.
# SPDX-License-Identifier: BSD-3-Clause

"""file-contents / file-starts-with rule types for repo-policy-action.

Checks that files matching a glob pattern contain (or start with) a
given string or regex. Used for copyright header enforcement and README
license reference checks.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from reporter import Reporter, RuleResult

logger = logging.getLogger(__name__)

# Directories to skip when scanning all source files.
_SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "vendor",
        ".tox",
        ".venv",
        "ENV",
        "venv",
        "__pycache__",
        "dist",
        "build",
    }
)


def run(
    repo_path: str,
    rule_name: str,
    level: str,
    options: dict[str, Any],
    reporter: Reporter,
) -> RuleResult:
    """Evaluate a file-contents or file-starts-with rule.

    Scans every file matched by ``globsAll`` (or all source files if
    not specified) and checks whether each contains the required
    content. Reports the first offending file, if any.

    Args:
        repo_path: Absolute path to the repository root.
        rule_name: Rule identifier for annotations.
        level: ``"error"`` or ``"warning"``.
        options: Rule options from the config. Expected keys:
            - ``"globsAll"`` (list[str]): every matched file must
              contain the required content.
            - ``"content"`` (str): regex pattern to match.
            - ``"flags"`` (list[str], optional): regex flags
              e.g. ``["IGNORECASE"]``.
            - ``"lineCount"`` (int, optional): only check the first N
              lines (used for file-starts-with semantics).
            - ``"fail-on-non-existent"`` (bool, optional): fail if no
              files match the glob (default: False).
        reporter: Reporter instance.

    Returns:
        A RuleResult indicating pass or failure.
    """
    globs: list[str] = options.get("globsAll", [])
    content_pattern: str = options.get("content", "")
    flag_names: list[str] = options.get("flags", [])
    line_count: int | None = options.get("lineCount")
    fail_on_missing: bool = options.get("fail-on-non-existent", False)

    if not content_pattern:
        logger.warning(
            "Rule '%s' has no content pattern — skipping.", rule_name
        )
        return reporter.rule_passed(
            rule_name, "No content pattern configured — skipped."
        )

    compiled = _compile_pattern(content_pattern, flag_names, rule_name)
    if compiled is None:
        return reporter.rule_failed(
            rule_name=rule_name,
            level=level,
            message=f"Invalid regex pattern: {content_pattern!r}",
        )

    root = Path(repo_path)
    matched_files = _find_files(root, globs)

    if not matched_files:
        if fail_on_missing:
            return reporter.rule_failed(
                rule_name=rule_name,
                level=level,
                message=f"No files matched patterns {globs}",
            )
        return reporter.rule_passed(
            rule_name, f"No files matched {globs} — skipped."
        )

    for file_path in matched_files:
        if not _file_contains(file_path, compiled, line_count):
            return reporter.rule_failed(
                rule_name=rule_name,
                level=level,
                message=(
                    f"Pattern {content_pattern!r} not found"
                    f" in {file_path.relative_to(root)}"
                ),
                file_path=str(file_path.relative_to(root)),
            )

    return reporter.rule_passed(
        rule_name,
        f"Pattern found in all {len(matched_files)} matched file(s).",
    )


def _compile_pattern(
    pattern: str, flag_names: list[str], rule_name: str
) -> re.Pattern | None:
    """Compile a regex pattern with optional flags.

    Args:
        pattern: The regex pattern string.
        flag_names: List of ``re`` flag names e.g. ``["IGNORECASE"]``.
        rule_name: Used only for log messages.

    Returns:
        Compiled pattern, or None if the pattern is invalid.
    """
    flags = re.MULTILINE
    for name in flag_names:
        flag = getattr(re, name.upper(), None)
        if flag is None:
            logger.warning(
                "Rule '%s': unknown regex flag '%s'.", rule_name, name
            )
        else:
            flags |= flag
    try:
        return re.compile(pattern, flags)
    except re.error as exc:
        logger.error(
            "Rule '%s': failed to compile pattern %r: %s",
            rule_name,
            pattern,
            exc,
        )
        return None


def _find_files(root: Path, globs: list[str]) -> list[Path]:
    """Return all files under root that match any of the glob patterns.

    Args:
        root: Repository root path.
        globs: List of glob patterns to match.

    Returns:
        Sorted, deduplicated list of matching file paths.
    """
    found: set[Path] = set()
    for pattern in globs:
        for match in root.glob(pattern):
            if match.is_file() and not _in_skip_dir(match, root):
                found.add(match)
    return sorted(found)


def _in_skip_dir(path: Path, root: Path) -> bool:
    """Return True if path is inside a directory that should be skipped.

    Args:
        path: File path to check.
        root: Repository root.

    Returns:
        True if any ancestor directory name is in ``_SKIP_DIRS``.
    """
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return any(part in _SKIP_DIRS for part in relative.parts[:-1])


def _file_contains(
    path: Path, pattern: re.Pattern, line_count: int | None
) -> bool:
    """Return True if the file content matches the pattern.

    Args:
        path: Path to the file.
        pattern: Compiled regex to search for.
        line_count: If set, only read the first N lines.

    Returns:
        True if the pattern matches; False otherwise or on read error.
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            if line_count is not None:
                text = "".join(
                    line for _, line in zip(range(line_count), fh)
                )
            else:
                text = fh.read()
        return bool(pattern.search(text))
    except OSError as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return False

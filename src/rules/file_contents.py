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

import magic

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

    Scans every file matched by ``globsAll`` and checks whether each
    contains the required content. Reports the first offending file.

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
              lines (file-starts-with semantics).
            - ``"fail-on-non-existent"`` (bool, optional): fail if no
              files match the glob (default: False).
            - ``"skip-paths-matching"`` (list[str], optional): skip
              files whose path matches any of these regex patterns or
              whose extension is in this list.
            - ``"skip-binary-files"`` (bool, optional): skip files
              detected as binary by libmagic (default: False).
            - ``"fail-message"`` (str, optional): custom failure
              message to emit instead of the default.
        reporter: Reporter instance.

    Returns:
        A RuleResult indicating pass or failure.
    """
    globs: list[str] = options.get("globsAll", [])
    content_pattern: str = options.get("content", "")
    flag_names: list[str] = options.get("flags", [])
    line_count: int | None = options.get("lineCount")
    fail_on_missing: bool = options.get("fail-on-non-existent", False)
    skip_paths: list[str] = options.get("skip-paths-matching", [])
    skip_binary: bool = options.get("skip-binary-files", False)
    fail_message: str | None = options.get("fail-message")

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

    skip_patterns = _compile_skip_patterns(skip_paths, rule_name)
    root = Path(repo_path)
    matched_files = _find_files(root, globs)

    if not matched_files:
        if fail_on_missing:
            return reporter.rule_failed(
                rule_name=rule_name,
                level=level,
                message=fail_message or f"No files matched patterns {globs}",
            )
        return reporter.rule_passed(
            rule_name, f"No files matched {globs} — skipped."
        )

    mime_detector = magic.Magic(mime=True) if skip_binary else None

    for file_path in matched_files:
        # Broken symlinks: skip rather than raise.
        if file_path.is_symlink() and not file_path.exists():
            logger.debug(
                "Rule '%s': skipping broken symlink %s.",
                rule_name,
                file_path,
            )
            continue

        rel = str(file_path.relative_to(root))
        if _should_skip_path(rel, skip_patterns):
            logger.debug(
                "Rule '%s': skipping %s (skip-paths-matching).",
                rule_name,
                rel,
            )
            continue

        if (
            skip_binary
            and mime_detector
            and _is_binary(file_path, mime_detector)
        ):
            logger.debug(
                "Rule '%s': skipping binary file %s.",
                rule_name,
                rel,
            )
            continue

        if not _file_contains(file_path, compiled, line_count):
            return reporter.rule_failed(
                rule_name=rule_name,
                level=level,
                message=fail_message
                or (f"Pattern {content_pattern!r} not found in {rel}"),
                file_path=rel,
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


def _compile_skip_patterns(
    skip_paths: list[str], rule_name: str
) -> list[re.Pattern]:
    """Compile skip-paths-matching entries into regex patterns.

    Entries that look like file extensions (start with ``.``) are
    converted to a suffix-match pattern. Other entries are compiled
    as-is.

    Args:
        skip_paths: List of extension strings or regex patterns.
        rule_name: Used only for log messages.

    Returns:
        List of compiled regex patterns.
    """
    compiled: list[re.Pattern] = []
    for entry in skip_paths:
        if entry.startswith("."):
            pattern = re.escape(entry) + "$"
        else:
            pattern = entry
        try:
            compiled.append(re.compile(pattern))
        except re.error as exc:
            logger.warning(
                "Rule '%s': invalid skip pattern %r: %s",
                rule_name,
                entry,
                exc,
            )
    return compiled


def _should_skip_path(rel_path: str, skip_patterns: list[re.Pattern]) -> bool:
    """Return True if the relative path matches any skip pattern.

    Args:
        rel_path: Relative path string to check.
        skip_patterns: Compiled patterns from skip-paths-matching.

    Returns:
        True if the file should be skipped.
    """
    return any(p.search(rel_path) for p in skip_patterns)


def _is_binary(path: Path, mime_detector: magic.Magic) -> bool:
    """Return True if libmagic identifies the file as binary.

    Args:
        path: Path to the file.
        mime_detector: Initialised magic.Magic(mime=True) instance.

    Returns:
        True if the file is not a text/* MIME type.
    """
    try:
        mime = mime_detector.from_file(str(path))
        return not mime.startswith("text/")
    except OSError:
        return False


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
            # Include broken symlinks so we can handle them explicitly.
            elif match.is_symlink() and not _in_skip_dir(match, root):
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
                text = "".join(line for _, line in zip(range(line_count), fh))
            else:
                text = fh.read()
        return bool(pattern.search(text))
    except OSError as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return False

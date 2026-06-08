# Copyright (c) Qualcomm Technologies, Inc.
# SPDX-License-Identifier: BSD-3-Clause

"""Lightweight language detection for repo-policy-action.

Determines which programming languages are present in a repository by
counting source files per extension. Extension-based detection is used
here rather than MIME types because libmagic's programming language
coverage is inconsistent — many source files return ``text/plain``.
Extensions remain the most reliable signal for this purpose.

Note: python-magic IS used in the binary-detection rule
(``rules/file_type.py``) where detecting by magic bytes rather than
extension is genuinely more robust.

No external tools (Linguist, enry, etc.) are required.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Directories to skip during the walk.
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

# Extension → canonical language name matching repolint.json axiom values.
_EXT_TO_LANGUAGE: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rs": "Rust",
    ".go": "Go",
    ".rb": "Ruby",
    ".m": "Objective-C",
    ".mm": "Objective-C",
    ".swift": "Swift",
    ".erl": "Erlang",
    ".hrl": "Erlang",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".c": "C",
    ".h": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".hxx": "C++",
}

# Packager detection: presence of these filenames implies the packager.
_PACKAGER_FILES: dict[str, str] = {
    "package.json": "npm",
    "Gemfile": "bundler",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle",
    "build.xml": "ant",
    "setup.py": "pip",
    "pyproject.toml": "pip",
    "requirements.txt": "pip",
    "Cargo.toml": "cargo",
    "Cargo.lock": "cargo",
    "Cartfile": "carthage",
    "Podfile": "cocoapods",
    "Package.swift": "swift-pm",
    "rebar.config": "rebar",
    "mix.exs": "mix",
}

# Minimum number of files with an extension before the language is
# considered "present". Avoids false positives from a single vendored
# or test-fixture file.
_MIN_FILE_THRESHOLD = 2


def detect_languages(repo_path: str) -> dict[str, set[str]]:
    """Return the languages and packagers detected in the repository.

    Args:
        repo_path: Absolute path to the repository root.

    Returns:
        A dict with two keys:
          - ``"languages"``: set of detected language names
          - ``"packagers"``: set of detected packager names
    """
    root = Path(repo_path)
    extension_counts: dict[str, int] = {}
    detected_packagers: set[str] = set()

    for item in _walk(root):
        if item.is_file():
            ext = item.suffix.lower()
            if ext in _EXT_TO_LANGUAGE:
                extension_counts[ext] = extension_counts.get(ext, 0) + 1
            if item.name in _PACKAGER_FILES:
                detected_packagers.add(_PACKAGER_FILES[item.name])
            if ext == ".podspec":
                detected_packagers.add("cocoapods")

    detected_languages: set[str] = {
        _EXT_TO_LANGUAGE[ext]
        for ext, count in extension_counts.items()
        if count >= _MIN_FILE_THRESHOLD
    }

    logger.info(
        "Detected languages: %s | packagers: %s",
        detected_languages or "(none)",
        detected_packagers or "(none)",
    )
    return {
        "languages": detected_languages,
        "packagers": detected_packagers,
    }


def _walk(root: Path):
    """Yield all files under root, skipping ignored directories.

    Args:
        root: Repository root path.

    Yields:
        Path objects for each non-skipped file.
    """
    for item in root.iterdir():
        if item.is_dir():
            if item.name not in _SKIP_DIRS:
                yield from _walk(item)
        else:
            yield item

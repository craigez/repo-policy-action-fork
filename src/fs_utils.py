# Copyright (c) Qualcomm Technologies, Inc.
# SPDX-License-Identifier: BSD-3-Clause

"""Shared filesystem walking helpers for repo-policy-action.

Centralises the directory skip-list and recursive walk used by
multiple rule modules and the language detector, so they stay in
sync rather than drifting as separate copies.
"""

from __future__ import annotations

from pathlib import Path

# Directories to skip when walking the repository tree.
SKIP_DIRS = frozenset(
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


def walk_files(root: Path):
    """Yield all files under root, skipping directories in SKIP_DIRS.

    Args:
        root: Repository root path.

    Yields:
        Path objects for each non-skipped file.
    """
    for item in root.iterdir():
        if item.is_dir():
            if item.name not in SKIP_DIRS:
                yield from walk_files(item)
        else:
            yield item

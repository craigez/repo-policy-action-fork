# Copyright (c) Qualcomm Technologies, Inc.
# SPDX-License-Identifier: BSD-3-Clause

"""Tests for rules/file_type.py (binary prohibition)."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.reporter import Reporter
from src.rules.file_type import run


def _write_elf_header(path: Path) -> None:
    """Write a minimal ELF magic header to simulate a Linux binary."""
    # ELF magic bytes: 0x7f 'E' 'L' 'F' followed by padding
    elf_header = b"\x7fELF" + b"\x00" * 12
    path.write_bytes(elf_header)


def _write_pe_header(path: Path) -> None:
    """Write a minimal MZ/PE header to simulate a Windows binary."""
    path.write_bytes(b"MZ" + b"\x00" * 14)


class TestFileTypeRule(unittest.TestCase):
    def setUp(self):
        self.reporter = Reporter()

    def _make_repo(self, files: dict[str, bytes | str]) -> str:
        tmp = tempfile.mkdtemp()
        for rel_path, content in files.items():
            path = Path(tmp) / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8")
        return tmp

    def test_passes_when_no_binaries(self):
        """Rule passes for a repo containing only text files."""
        repo = self._make_repo(
            {"src/main.py": "print('hello')", "README.md": "# Hi"}
        )
        result = run(
            repo_path=repo,
            rule_name="binaries-not-present",
            level="warning",
            options={},
            reporter=self.reporter,
        )
        self.assertTrue(result.passed)

    def test_fails_on_pe_binary(self):
        """Rule fails when a PE (Windows) executable is present."""
        repo = self._make_repo({})
        _write_pe_header(Path(repo) / "tool.exe")
        result = run(
            repo_path=repo,
            rule_name="binaries-not-present",
            level="warning",
            options={},
            reporter=self.reporter,
        )
        self.assertFalse(result.passed)

    def test_fails_on_elf_binary(self):
        """Rule fails when an ELF binary is present."""
        repo = self._make_repo({})
        _write_elf_header(Path(repo) / "tool")
        result = run(
            repo_path=repo,
            rule_name="binaries-not-present",
            level="warning",
            options={},
            reporter=self.reporter,
        )
        self.assertFalse(result.passed)

    def test_skips_node_modules(self):
        """Binaries inside node_modules/ are not flagged."""
        repo = self._make_repo({})
        binary_path = Path(repo) / "node_modules" / "native" / "binding.node"
        binary_path.parent.mkdir(parents=True)
        _write_elf_header(binary_path)
        result = run(
            repo_path=repo,
            rule_name="binaries-not-present",
            level="warning",
            options={},
            reporter=self.reporter,
        )
        self.assertTrue(result.passed)

    def test_allowed_extension_skipped(self):
        """Font files (.woff2) are in the allow-list and not flagged."""
        # woff2 files often have a binary signature; they should be skipped
        repo = self._make_repo(
            {"assets/font.woff2": b"\x77\x4f\x46\x32" + b"\x00" * 12}
        )
        result = run(
            repo_path=repo,
            rule_name="binaries-not-present",
            level="warning",
            options={},
            reporter=self.reporter,
        )
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()

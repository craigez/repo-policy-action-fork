# Copyright (c) Qualcomm Technologies, Inc.
# SPDX-License-Identifier: BSD-3-Clause

"""Pytest configuration: add src/ to sys.path so bare intra-package
imports (e.g. ``from reporter import ...``) resolve correctly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

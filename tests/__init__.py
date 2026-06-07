# Copyright (c) Qualcomm Technologies, Inc.
# SPDX-License-Identifier: BSD-3-Clause

# intentionally empty — pytest discovers tests without __init__.py,
# but this file marks the directory as a Python package so imports
# like `from src.config import ...` resolve correctly during test runs.

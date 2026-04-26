"""DEPRECATED — package config has moved to the repo-root ``pyproject.toml``.

The distribution is now published as ``canton-ginie`` on PyPI.
Install with:

    pip install canton-ginie

This file is kept only to avoid breaking any legacy ``pip install -e ./sdk``
invocations; it now defers to the root-level pyproject.toml.
"""

import warnings

warnings.warn(
    "sdk/setup.py is deprecated. Install canton-ginie via the project root: "
    "`pip install -e .` or `pip install canton-ginie` from PyPI.",
    DeprecationWarning,
    stacklevel=2,
)

from setuptools import setup

# Minimal setup() so `pip install -e ./sdk` still works but delegates
# configuration to the modern pyproject.toml at the repo root.
setup()

"""Smoke tests that verify the T04 scaffold loads before Contract Freeze (T05)."""

from __future__ import annotations

import importlib

import erre_sandbox


def test_version_defined() -> None:
    assert isinstance(erre_sandbox.__version__, str)
    assert erre_sandbox.__version__


def test_all_layers_importable() -> None:
    layers = [
        "erre_sandbox.schemas",
        "erre_sandbox.inference",
        "erre_sandbox.memory",
        "erre_sandbox.cognition",
        "erre_sandbox.world",
        "erre_sandbox.ui",
        "erre_sandbox.erre",
    ]
    for name in layers:
        module = importlib.import_module(name)
        assert module is not None, f"failed to import {name}"

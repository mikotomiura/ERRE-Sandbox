"""Shared fixtures for T18 dashboard tests."""

from __future__ import annotations

import pytest

from erre_sandbox.ui.dashboard.state import DashboardState
from erre_sandbox.ui.dashboard.stub import StubEnvelopeGenerator


@pytest.fixture
def state() -> DashboardState:
    """Return a fresh :class:`DashboardState`."""
    return DashboardState()


@pytest.fixture
def stub() -> StubEnvelopeGenerator:
    """Return a deterministic stub generator with ``seed=42``."""
    return StubEnvelopeGenerator(seed=42)

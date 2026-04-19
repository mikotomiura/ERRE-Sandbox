"""Shared fixtures for T19 integration skeleton tests.

Most scenario tests are ``@pytest.mark.skip`` until T14 (``gateway-fastapi-ws``)
lands and provides a live WS server to drive them against. The fixtures here
are minimal placeholders that the skipped tests reference by name so the
skeleton compiles cleanly today.

Once T14 lands, extend this file with:

* a real ``gateway`` fixture that starts the FastAPI app on a random port
* an ``observation_source`` fixture that yields seeded Observations
* a ``memory_store`` fixture that hands out fresh sqlite-vec DBs

See ``.steering/20260419-m2-integration-e2e/design.md`` §Test strategy.
"""

from __future__ import annotations

import pytest

from erre_sandbox.integration import (
    M2_THRESHOLDS,
    SCENARIO_MEMORY_WRITE,
    SCENARIO_TICK_ROBUSTNESS,
    SCENARIO_WALKING,
    Scenario,
    Thresholds,
)


@pytest.fixture
def walking_scenario() -> Scenario:
    """Return the S_WALKING scenario (Kant × Peripatos baseline)."""
    return SCENARIO_WALKING


@pytest.fixture
def memory_write_scenario() -> Scenario:
    """Return the S_MEMORY_WRITE scenario."""
    return SCENARIO_MEMORY_WRITE


@pytest.fixture
def tick_robustness_scenario() -> Scenario:
    """Return the S_TICK_ROBUSTNESS scenario."""
    return SCENARIO_TICK_ROBUSTNESS


@pytest.fixture
def thresholds() -> Thresholds:
    """Return the frozen :class:`Thresholds` used in M2 acceptance."""
    return M2_THRESHOLDS

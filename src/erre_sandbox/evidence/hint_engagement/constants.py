"""Frozen decision-table parameters for the hint-engagement instrument (ADR §6).

Single source of truth for every value the engagement instrument ADR §6
pre-registered (result-before freeze, Codex HIGH-2). The loader and the tests import
these constants instead of re-spelling a literal, so a value can only change by a
deliberate edit here — which itself requires an ADR revision (forking-paths guard,
ADR §8). No value is read off a result and then tuned.
"""

from __future__ import annotations

from typing import Final

WARMUP_TICKS: Final[int] = 5
"""Warmup ticks excluded from the eligible population (a tick with
``tick < WARMUP_TICKS`` is dropped — the SWM is still populating). ADR §5 / §6."""

N_MIN: Final[int] = 20
"""Minimum emitted-hint count over eligible ticks for a binding verdict; below this
the instrument is INSTRUMENT_INCONCLUSIVE (global stability gate). ADR §6."""

CHANNEL_FLOOR: Final[int] = 8
"""Minimum number of eligible channels with ``adopted_count >= 2``; below this the
instrument is INSTRUMENT_INCONCLUSIVE (global stability gate, evaluated first in the
precedence order alongside ``N_MIN``). ADR §6 / 補強 §6."""

THETA_E: Final[float] = 0.10
"""``emission_rate < THETA_E`` routes to state (a) emission rarity. ADR §6."""

THETA_A: Final[float] = 0.50
"""``adoption_rate < THETA_A`` (with emission healthy) routes to state (b) adoption
rejection. ADR §6."""

THETA_DIR: Final[float] = 0.60
"""``adopted_direction_consistency_rate < THETA_DIR`` (with emission + adoption
healthy) routes to state (c) direction inconsistency. The same ratio threshold marks
a single channel as same-direction-dominant (``|sum step| / sum|step| >= THETA_DIR``).
ADR §5 / §6."""

ADOPTED_CHANNEL_MIN: Final[int] = 2
"""A channel enters the direction-consistency population only with at least this many
adopted nudges (a single nudge has no cross-tick direction). ADR §5."""

__all__ = [
    "ADOPTED_CHANNEL_MIN",
    "CHANNEL_FLOOR",
    "N_MIN",
    "THETA_A",
    "THETA_DIR",
    "THETA_E",
    "WARMUP_TICKS",
]

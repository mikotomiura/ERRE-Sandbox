"""M10-A S4 PR-S4a: population launcher (3 measured same-base + N-3 background).

Verifies the S4 population launcher seam **offline** (no Ollama / SGLang health
check, no real inference — MED-3): the population roster contract
(measured/background split), the builder + validation, the separated 31-seat
table (legacy ``_NATURAL_AGORA_SEATS`` left at 3 / byte-identical), the
registration loop against a stub runtime, the CLI + function-level mutual
exclusion with the legacy same-base launcher, and a regression that the
``eval_natural_mode`` admission is untouched (G0-6 admission-invariance, the
(a) selective-scheduling-rejected binding). GPU/S4/S5 stay BLOCKed — this PR is
launcher implementation only, no smoke run.
"""

from __future__ import annotations

import asyncio
import math
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from erre_sandbox.cli.eval_run_golden import (
    _MEASURED_INDIVIDUAL_COUNT,
    _NATURAL_AGORA_POSITIONS,
    _NATURAL_AGORA_SEATS,
    _NATURAL_POPULATION_SEATS,
    _POPULATION_N_MAX,
    _build_arg_parser,
    _load_persona,
    _register_population_roster,
    build_population_roster,
    capture_natural,
)
from erre_sandbox.evidence.golden_baseline import DEFAULT_PERSONAS
from erre_sandbox.integration.dialog import (
    AgentView,
    InMemoryDialogScheduler,
    _iter_all_distinct_pairs,
)
from erre_sandbox.schemas import Zone

if TYPE_CHECKING:
    from random import Random

    from erre_sandbox.schemas import AgentState, ControlEnvelope, PersonaSpec

_PERSONAS_DIR = Path("personas")


# ---------------------------------------------------------------------------
# Seat table separation (legacy left untouched, population table = 31)
# ---------------------------------------------------------------------------


def test_legacy_seats_unchanged_three() -> None:
    """``_NATURAL_AGORA_SEATS`` stays at the three legacy AGORA coordinates."""
    assert tuple(_NATURAL_AGORA_POSITIONS.values()) == _NATURAL_AGORA_SEATS
    assert len(_NATURAL_AGORA_SEATS) == 3


def test_population_seats_length_is_n_max() -> None:
    assert _POPULATION_N_MAX == 31
    assert len(_NATURAL_POPULATION_SEATS) == _POPULATION_N_MAX


def test_population_seats_first_three_match_legacy() -> None:
    """First 3 population seats are byte-identical to the legacy table."""
    assert _NATURAL_POPULATION_SEATS[:3] == _NATURAL_AGORA_SEATS


def test_population_seats_all_distinct() -> None:
    assert len(set(_NATURAL_POPULATION_SEATS)) == _POPULATION_N_MAX


def test_population_background_seats_avoid_separation_nudge() -> None:
    """The 28 generated seats are >=1.6 m apart (above Kant's 1.5 m radius)."""
    generated = _NATURAL_POPULATION_SEATS[3:]
    assert len(generated) == 28
    for i, (xa, _ya, za) in enumerate(generated):
        for xb, _yb, zb in generated[i + 1 :]:
            assert math.hypot(xa - xb, za - zb) >= 1.6 - 1e-9
    # Generated seats sit at z >= 1.6 so none collides with the z==0 legacy row.
    assert all(z >= 1.6 - 1e-9 for _x, _y, z in generated)


# ---------------------------------------------------------------------------
# build_population_roster — contract
# ---------------------------------------------------------------------------


def test_population_roster_measured_is_three_same_base_focal() -> None:
    roster = build_population_roster("kant", world_size=21)
    assert roster.focal_persona == "kant"
    assert roster.measured == (("kant", 1), ("kant", 2), ("kant", 3))
    assert roster.measured_individual_ids == (
        "a_kant_001",
        "a_kant_002",
        "a_kant_003",
    )


def test_population_roster_background_is_cross_base_non_focal() -> None:
    roster = build_population_roster("kant", world_size=21)
    # 21 - 3 = 18 background, drawn round-robin from the non-focal personas.
    assert len(roster.background) == 18
    bg_bases = {pid for pid, _ord in roster.background}
    assert bg_bases == {"nietzsche", "rikyu"}  # focal 'kant' excluded
    assert "kant" not in bg_bases


def test_population_roster_world_size_and_all_entries_order() -> None:
    roster = build_population_roster("rikyu", world_size=31)
    assert roster.world_size == 31
    entries = roster.all_entries()
    assert len(entries) == 31
    # measured first (seat order), then background.
    assert entries[:3] == (("rikyu", 1), ("rikyu", 2), ("rikyu", 3))
    assert entries[3:] == roster.background


def test_population_roster_all_individual_ids_distinct() -> None:
    roster = build_population_roster("nietzsche", world_size=31)
    from erre_sandbox.bootstrap import make_agent_id

    ids = [make_agent_id(pid, ordinal) for pid, ordinal in roster.all_entries()]
    assert len(set(ids)) == 31


def test_population_roster_background_round_robin_ordinals() -> None:
    """Background cycles non-focal bases, incrementing ordinal each full cycle."""
    roster = build_population_roster("kant", world_size=9)  # 6 background
    # non-focal sorted = (nietzsche, rikyu); i//2 + 1 ordinal scheme.
    assert roster.background == (
        ("nietzsche", 1),
        ("rikyu", 1),
        ("nietzsche", 2),
        ("rikyu", 2),
        ("nietzsche", 3),
        ("rikyu", 3),
    )


def test_population_roster_minimal_world_size_no_background() -> None:
    roster = build_population_roster("kant", world_size=3)
    assert roster.background == ()
    assert roster.world_size == 3


# ---------------------------------------------------------------------------
# build_population_roster — validation
# ---------------------------------------------------------------------------


def test_population_roster_rejects_unknown_focal() -> None:
    with pytest.raises(ValueError, match="not part of the natural-condition"):
        build_population_roster("descartes", world_size=21)


def test_population_roster_rejects_world_size_over_n_max() -> None:
    with pytest.raises(ValueError, match="exceeds the frozen population ceiling"):
        build_population_roster("kant", world_size=_POPULATION_N_MAX + 1)


def test_population_roster_rejects_world_size_below_measured() -> None:
    with pytest.raises(ValueError, match="must be >= measured_count"):
        build_population_roster("kant", world_size=2)  # measured_count default 3


@pytest.mark.parametrize("bad", [0, -1, 2, 4])
def test_population_roster_rejects_measured_count_not_three(bad: int) -> None:
    """measured_count is pinned to the frozen 3 (⑤ N=3); any other value raises."""
    with pytest.raises(ValueError, match="must equal the frozen"):
        build_population_roster("kant", world_size=21, measured_count=bad)


def test_population_roster_measured_count_default_is_three() -> None:
    """The default measured_count equals the frozen _MEASURED_INDIVIDUAL_COUNT."""
    assert _MEASURED_INDIVIDUAL_COUNT == 3
    roster = build_population_roster("kant", world_size=21)
    assert len(roster.measured) == _MEASURED_INDIVIDUAL_COUNT


# ---------------------------------------------------------------------------
# _register_population_roster (offline, stub runtime — no inference)
# ---------------------------------------------------------------------------


class _StubRuntime:
    """Records register_agent calls; no cognition stack, no inference."""

    def __init__(self) -> None:
        self.registered: list[tuple[str, str]] = []
        self.seats: dict[str, tuple[float, float, float]] = {}

    def register_agent(self, state: AgentState, persona: PersonaSpec) -> None:
        assert persona.persona_id == state.persona_id
        self.registered.append((state.agent_id, state.persona_id))
        self.seats[state.agent_id] = (
            state.position.x,
            state.position.y,
            state.position.z,
        )


def _persona_specs() -> dict[str, PersonaSpec]:
    return {pid: _load_persona(_PERSONAS_DIR, pid) for pid in DEFAULT_PERSONAS}


def test_register_population_roster_offline() -> None:
    runtime = _StubRuntime()
    roster = build_population_roster("kant", world_size=21)
    _register_population_roster(runtime, roster, _persona_specs())  # type: ignore[arg-type]

    # roster length = N, distinct agent_id = N, distinct seats = N.
    assert len(runtime.registered) == 21
    ids = [aid for aid, _ in runtime.registered]
    assert len(set(ids)) == 21
    assert len(set(runtime.seats.values())) == 21

    # measured 3 = focal kant, registered first, on the legacy seats.
    measured = runtime.registered[:3]
    assert measured == [
        ("a_kant_001", "kant"),
        ("a_kant_002", "kant"),
        ("a_kant_003", "kant"),
    ]
    for k in range(3):
        assert runtime.seats[f"a_kant_{k + 1:03d}"] == _NATURAL_AGORA_SEATS[k]

    # density-audit aggregation target = measured 3 (focal base group); the
    # background never carries the focal base, so a loader grouping by
    # base_persona_id isolates the measured trio cleanly (disposition §2.4).
    measured_ids = set(roster.measured_individual_ids)
    bg_ids = {aid for aid, _ in runtime.registered if aid not in measured_ids}
    assert measured_ids == {"a_kant_001", "a_kant_002", "a_kant_003"}
    assert all(not aid.startswith("a_kant_") for aid in bg_ids)


# ---------------------------------------------------------------------------
# Mutual exclusion: same_base_count vs population_world_size
# ---------------------------------------------------------------------------


def test_capture_natural_rejects_both_launchers() -> None:
    """Function-level guard (internal API): both roster flags set -> ValueError."""
    with pytest.raises(ValueError, match="mutually exclusive"):
        asyncio.run(
            capture_natural(
                persona="kant",
                run_idx=0,
                turn_count=1,
                temp_path=Path("unused.duckdb"),
                ollama_host="http://127.0.0.1:11434",
                chat_model="qwen3:8b",
                embed_model="nomic-embed-text",
                memory_db_path=None,
                wall_timeout_min=1.0,
                same_base_count=2,
                population_world_size=21,
            )
        )


def _base_cli_args() -> list[str]:
    return [
        "--persona",
        "kant",
        "--run-idx",
        "0",
        "--condition",
        "natural",
        "--output",
        "out.duckdb",
    ]


def test_cli_rejects_both_roster_flags() -> None:
    """argparse mutual-exclusion: both flags -> SystemExit (parser error)."""
    parser = _build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                *_base_cli_args(),
                "--same-base-count",
                "3",
                "--population-world-size",
                "21",
            ]
        )


def test_cli_population_world_size_alone_parses() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args([*_base_cli_args(), "--population-world-size", "21"])
    assert args.population_world_size == 21
    assert args.same_base_count is None


def test_cli_same_base_count_alone_parses() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args([*_base_cli_args(), "--same-base-count", "3"])
    assert args.same_base_count == 3
    assert args.population_world_size is None


# ---------------------------------------------------------------------------
# admission-invariance regression (G0-6: dialog.py admission untouched)
# ---------------------------------------------------------------------------


def _always_fire() -> Random:
    from random import Random

    r = Random(0)
    r.random = lambda: 0.0  # type: ignore[method-assign]
    return r


def _population_agent_views() -> list[AgentView]:
    """N=21 mixed-base AgentViews mirroring a registered population roster."""
    roster = build_population_roster("kant", world_size=21)
    from erre_sandbox.bootstrap import make_agent_id

    return [
        AgentView(agent_id=make_agent_id(pid, ordinal), zone=Zone.AGORA, tick=0)
        for pid, ordinal in roster.all_entries()
    ]


def test_iter_all_distinct_pairs_is_full_clique_no_base_bias() -> None:
    """eval_natural_mode enumerates every C(N,2) pair, no same-base preference."""
    agents = _population_agent_views()
    n = len(agents)
    assert n == 21
    pairs = list(_iter_all_distinct_pairs(agents))
    assert len(pairs) == n * (n - 1) // 2  # C(21,2) = 210
    # Every unordered distinct pair appears exactly once; ordering is by
    # agent_id only (no persona/base inspection).
    seen = {frozenset((a.agent_id, b.agent_id)) for a, b in pairs}
    assert len(seen) == 210
    for a, b in pairs:
        assert a.agent_id < b.agent_id  # stable id-sorted order, base-agnostic


def test_scheduler_admission_constants_unchanged() -> None:
    """The frozen eval-natural admission cadence constants are untouched."""
    assert InMemoryDialogScheduler.AUTO_FIRE_PROB_PER_TICK == 0.25
    assert InMemoryDialogScheduler.COOLDOWN_TICKS_EVAL == 5
    assert InMemoryDialogScheduler.TIMEOUT_TICKS == 6


def test_eval_natural_mode_admits_full_clique_at_n21() -> None:
    """With always-fire RNG, one tick admits all C(21,2) pairs (uniform)."""
    captured: list[ControlEnvelope] = []

    def sink(env: ControlEnvelope) -> None:
        captured.append(env)

    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
    )
    scheduler.tick(world_tick=0, agents=_population_agent_views())
    assert scheduler.open_count == 210  # C(21,2): every distinct pair admitted

"""M10-A S4 GPU smoke wiring: path(a) S4 decision orchestration (synthetic, CPU).

Drives the full S4 forward-decision plumbing (论点 d focal-base assembly → H2 gate →
density audit → §6.1 decision) over **population** multi-base synthetic DuckDB captures,
with no GPU / model. Covers: the 论点 d focal filter (population assemble no longer
raises ``PathAAssemblyError``), legacy same-base byte-invariance, the GO path end to
end, the blocker1 per-seed escalation aggregation (the cross-seed min is never fed into
the 3-owner statistic, DA-S4GS-5), and the measured-3 cross-check.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import duckdb
import numpy as np
import pytest

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.eval_store import bootstrap_schema, connect_analysis_view
from erre_sandbox.evidence.individuation.layer1 import stub_embedding_provider
from erre_sandbox.evidence.individuation.path_a_density_audit import (
    DecisionAction,
    DensityAudit,
    DensityAuditError,
    escalation_feasible,
)
from erre_sandbox.evidence.individuation.path_a_gate import (
    IndividualSubstrate,
    PathARunInput,
    PathAVerdict,
)
from erre_sandbox.evidence.individuation.path_a_h2_gate import H2Verdict
from erre_sandbox.evidence.individuation.path_a_pipeline import (
    PathAAssemblyError,
    assemble_path_a_run_from_view,
)
from erre_sandbox.evidence.individuation.path_a_s4_runner import (
    S4RunnerError,
    _cross_check_measured,
    _map_gate_to_h2,
    run_s4_decision,
)
from erre_sandbox.evidence.individuation.runner import IndividuationContext
from erre_sandbox.evidence.individuation.trace_ddl import (
    TABLE_NAME,
    bootstrap_individual_state_trace_schema,
    column_names,
)

if TYPE_CHECKING:
    from pathlib import Path

_NOW = datetime(2026, 6, 1, tzinfo=UTC)
_KANT = ("a_kant_001", "a_kant_002", "a_kant_003")
_DIALOG_COLS = (
    "id",
    "run_id",
    "dialog_id",
    "tick",
    "turn_index",
    "speaker_agent_id",
    "speaker_persona_id",
    "addressee_agent_id",
    "addressee_persona_id",
    "utterance",
    "mode",
    "zone",
    "reasoning",
    "epoch_phase",
    "individual_layer_enabled",
    "created_at",
)

# Differentiated SWM (low jaccard → ③) + >= 2 belief classes, distinct dists (②).
_KANT_SWM = {
    _KANT[0]: [["self", "kt"], ["env", "agora"], ["env", "study"]],
    _KANT[1]: [["self", "kt"], ["env", "peripatos"], ["env", "agora"]],
    _KANT[2]: [["self", "kt"], ["env", "chashitsu"], ["env", "garden"]],
}
_KANT_BELIEFS = {
    _KANT[0]: ["trust", "wary"],
    _KANT[1]: ["trust", "trust", "wary"],
    _KANT[2]: ["trust", "wary", "wary"],
}
_EV_BIAS = (0.6, -0.5, 0.1)  # systematic-divergence per measured owner → H2 separates
_EV_ZONES = ("study", "peripatos", "chashitsu", "agora", "garden")


def _evidence_json(owner_idx: int, density: int) -> str:
    rng = np.random.default_rng(1000 + owner_idx)
    units: list[dict[str, Any]] = []
    for j in range(density):
        zone = _EV_ZONES[int(rng.integers(0, len(_EV_ZONES)))]
        aff = float(np.clip(_EV_BIAS[owner_idx] + rng.normal(0.0, 0.15), -0.95, 0.95))
        kind = (
            "trust"
            if aff >= 0.70
            else "curious"
            if aff > 0.0
            else "clash"
            if aff <= -0.70
            else "wary"
        )
        units.append(
            {
                "other_agent_id": f"o_{owner_idx}_{j}",
                "belief_kind": kind,
                "confidence": 0.8,
                "affinity": aff,
                "familiarity": 0.5,
                "last_interaction_zone": zone,
                "last_interaction_tick": 100,
            }
        )
    return json.dumps(units)


def _dialog_row(agent: str, persona: str, run_id: str) -> dict[str, Any]:
    return {
        "id": f"{run_id}-{agent}-1",
        "run_id": run_id,
        "dialog_id": "d0",
        "tick": 1,
        "turn_index": 0,
        "speaker_agent_id": agent,
        "speaker_persona_id": persona,
        "addressee_agent_id": "a_other",
        "addressee_persona_id": "other",
        "utterance": "the of and study here please",
        "mode": "",
        "zone": "agora",
        "reasoning": "",
        "epoch_phase": "evaluation",
        "individual_layer_enabled": True,
        "created_at": _NOW,
    }


def _insert(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    agent: str,
    persona: str,
    beliefs: list[str],
    swm: list[list[str]] | None,
    evidence: str,
) -> None:
    cols = ", ".join(_DIALOG_COLS)
    ph = ", ".join("?" for _ in _DIALOG_COLS)
    tcols = ", ".join(column_names())
    tph = ", ".join("?" for _ in column_names())
    row = _dialog_row(agent, persona, run_id)
    con.execute(
        f"INSERT INTO raw_dialog.dialog ({cols}) VALUES ({ph})",  # noqa: S608
        [row[c] for c in _DIALOG_COLS],
    )
    con.execute(
        f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} ({tcols}) VALUES ({tph})",  # noqa: S608
        (
            run_id,
            agent,
            1,
            None,
            None,
            json.dumps(beliefs),
            0,
            json.dumps(swm) if swm is not None else None,
            evidence,
        ),
    )


def _build_population_db(path: Path, run_id: str, *, kant_density: int = 20) -> None:
    """3 measured kant (differentiated, systematic-divergence) + 4 cross-base bg."""
    con = duckdb.connect(str(path), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    for idx, agent in enumerate(_KANT):
        _insert(
            con,
            run_id=run_id,
            agent=agent,
            persona="kant",
            beliefs=_KANT_BELIEFS[agent],
            swm=_KANT_SWM[agent],
            evidence=_evidence_json(idx, kant_density),
        )
    background = [
        ("a_nietzsche_001", "nietzsche"),
        ("a_nietzsche_002", "nietzsche"),
        ("a_rikyu_001", "rikyu"),
        ("a_rikyu_002", "rikyu"),
    ]
    for agent, persona in background:
        _insert(
            con,
            run_id=run_id,
            agent=agent,
            persona=persona,
            beliefs=["trust", "wary"],
            swm=[["self", "bg"], ["env", "agora"]],
            evidence=_evidence_json(0, 5),
        )
    con.execute("CHECKPOINT")
    con.close()


def _build_same_base_db(path: Path, run_id: str) -> None:
    """A legacy single-base rikyu run (no background) for byte-invariance coverage."""
    ids = ("a_rikyu_001", "a_rikyu_002", "a_rikyu_003")
    swm = {
        ids[0]: [["self", "rd"], ["env", "agora"], ["env", "study"]],
        ids[1]: [["self", "rd"], ["env", "peripatos"], ["env", "agora"]],
        ids[2]: [["self", "rd"], ["env", "chashitsu"], ["env", "garden"]],
    }
    beliefs = {
        ids[0]: ["trust", "wary"],
        ids[1]: ["trust", "trust", "wary"],
        ids[2]: ["trust", "wary", "wary"],
    }
    con = duckdb.connect(str(path), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    for idx, agent in enumerate(ids):
        _insert(
            con,
            run_id=run_id,
            agent=agent,
            persona="rikyu",
            beliefs=beliefs[agent],
            swm=swm[agent],
            evidence=_evidence_json(idx, 20),
        )
    con.execute("CHECKPOINT")
    con.close()


def _ctx(path: Path) -> IndividuationContext:
    return IndividuationContext(
        personas_dir=path.parent, provider=stub_embedding_provider(), computed_at=_NOW
    )


def _captures(tmp_path: Path, *, densities: tuple[int, int, int]) -> list[tuple]:
    captures: list[tuple] = []
    for idx, density in enumerate(densities):
        db = tmp_path / f"run{idx}.duckdb"
        _build_population_db(db, f"run{idx}", kant_density=density)
        captures.append((db, f"run{idx}", idx))
    return captures


# --- 论点 d: population assemble no longer raises -----------------------------


def test_population_assemble_focal_filter(tmp_path: Path) -> None:
    db = tmp_path / "pop.duckdb"
    _build_population_db(db, "run0")
    view = connect_analysis_view(db)
    try:
        # Without the focal filter the multi-base rows raise PathAAssemblyError.
        with pytest.raises(PathAAssemblyError):
            assemble_path_a_run_from_view(view, run_id="run0", run_idx=0, ctx=_ctx(db))
        run_input = assemble_path_a_run_from_view(
            view, run_id="run0", run_idx=0, ctx=_ctx(db), focal_persona="kant"
        )
    finally:
        view.close()
    assert run_input.base_persona_id == "kant"
    assert {i.individual_id for i in run_input.individuals} == set(_KANT)
    assert len(run_input.belief_variance_rows) == 3
    assert len(run_input.jaccard_rows) == 3  # C(3,2) focal dyads only


def test_legacy_same_base_focal_is_noop(tmp_path: Path) -> None:
    """``focal_persona`` on a single-base run is a no-op (same individuals)."""
    db = tmp_path / "rikyu.duckdb"
    _build_same_base_db(db, "run0")
    view = connect_analysis_view(db)
    try:
        legacy = assemble_path_a_run_from_view(
            view, run_id="run0", run_idx=0, ctx=_ctx(db)
        )
        with_focal = assemble_path_a_run_from_view(
            view, run_id="run0", run_idx=0, ctx=_ctx(db), focal_persona="rikyu"
        )
    finally:
        view.close()
    # Full invariance (Codex LOW-2): not just ids/counts — the projected individuals
    # and both MetricResult row tuples are identical with vs without the focal arg.
    assert legacy.base_persona_id == with_focal.base_persona_id == "rikyu"
    assert legacy.individuals == with_focal.individuals
    assert legacy.belief_variance_rows == with_focal.belief_variance_rows
    assert legacy.jaccard_rows == with_focal.jaccard_rows
    assert len(legacy.individuals) == 3


# --- 5→3 verdict map (all states, Codex LOW-1) --------------------------------


@pytest.mark.parametrize(
    ("gate", "expected"),
    [
        (PathAVerdict.GO, H2Verdict.PASS),
        (PathAVerdict.NO_GO, H2Verdict.INCONCLUSIVE),
        (PathAVerdict.REJECT, H2Verdict.INCONCLUSIVE),
        (PathAVerdict.INCONCLUSIVE, H2Verdict.INCONCLUSIVE),
        (PathAVerdict.INVALID, H2Verdict.INVALID),
    ],
)
def test_map_gate_to_h2_all_states(gate: PathAVerdict, expected: H2Verdict) -> None:
    assert _map_gate_to_h2(gate) is expected


# --- orchestration: GO path ---------------------------------------------------


def test_run_s4_decision_go(tmp_path: Path) -> None:
    captures = _captures(tmp_path, densities=(20, 20, 20))
    s4 = run_s4_decision(
        captures, focal_persona="kant", experiment_run_id="corner", ctx=_ctx(tmp_path)
    )
    assert s4.score_report.verdict is PathAVerdict.GO
    assert s4.h2_verdict is H2Verdict.PASS
    assert s4.experiment_d_pass is True
    assert s4.experiment_min_d == 20
    assert s4.density_decision.action is DecisionAction.GO
    # sidecar supersede markers (G0-4 substance)
    assert s4.score_report.null_control_kind == "h2_owner_shuffle_resynth"
    assert s4.score_report.null_control_conformance == "conformant"


# --- blocker1: per-seed escalation, cross-seed min never fed to 3-owner stat ---


def test_escalation_is_per_seed_not_cross_seed_min(tmp_path: Path) -> None:
    """A (20, 5, 20) corner: ``experiment_min_d=5`` (≤8 cutoff = infeasible if fed to
    the 3-owner statistic), but the optimistic seed (D=20) makes the per-seed ``any``
    feasible. Proves the runner never feeds the min-of-9 into ``escalation_feasible``.
    """
    captures = _captures(tmp_path, densities=(20, 5, 20))
    s4 = run_s4_decision(
        captures, focal_persona="kant", experiment_run_id="corner", ctx=_ctx(tmp_path)
    )
    assert s4.experiment_d_pass is False
    assert s4.experiment_min_d == 5
    # The buggy cross-seed path would feed min-of-9 = 5 → infeasible (D_min ≤ 8).
    assert escalation_feasible(s4.experiment_min_d).feasible is False
    # The correct per-seed aggregation: any(esc(20), esc(5), esc(20)) = optimistic seed.
    assert s4.experiment_escalation_feasible is True
    assert {e.d_min for e in s4.per_seed_escalation} == {5, 20}
    assert any(e.feasible for e in s4.per_seed_escalation)


def test_per_seed_escalation_matches_each_seed_min_d(tmp_path: Path) -> None:
    captures = _captures(tmp_path, densities=(20, 5, 20))
    s4 = run_s4_decision(
        captures, focal_persona="kant", experiment_run_id="corner", ctx=_ctx(tmp_path)
    )
    seed_min_ds = [a.min_d for a in s4.per_seed_audits]
    esc_d_mins = [e.d_min for e in s4.per_seed_escalation]
    assert esc_d_mins == seed_min_ds  # one feasibility per seed, on that seed's min_d


# --- measured-3 cross-check ---------------------------------------------------


def test_focal_absent_raises_density_error(tmp_path: Path) -> None:
    """A focal persona absent from the run's base_groups is rejected by the audit."""
    captures = _captures(tmp_path, densities=(20, 20, 20))
    with pytest.raises(DensityAuditError):
        run_s4_decision(
            captures,
            focal_persona="aristotle",  # not a base in the population run
            experiment_run_id="corner",
            ctx=_ctx(tmp_path),
        )


def test_cross_check_detects_trio_disagreement() -> None:
    """``_cross_check_measured`` raises when the gate trio != the audited trio."""
    run_input = PathARunInput(
        run_idx=0,
        run_id="run0",
        base_persona_id="kant",
        individuals=(
            IndividualSubstrate("a_kant_001", None, None),
            IndividualSubstrate("a_kant_002", None, None),
            IndividualSubstrate("a_kant_003", None, None),
        ),
        belief_variance_rows=(),
        jaccard_rows=(),
    )
    audit = DensityAudit(
        per_owner=(("a_kant_001", 20), ("a_kant_002", 20), ("a_kant_999", 20)),
        min_d=20,
        d_pass=True,
        d_pass_bonf=False,
    )
    with pytest.raises(S4RunnerError):
        _cross_check_measured("run0", run_input, audit)

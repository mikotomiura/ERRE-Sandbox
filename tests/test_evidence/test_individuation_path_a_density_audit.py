"""M10-A PR-S4c density audit coverage (pure, CPU, scipy-free, slim-CI runnable).

Exercises the three layers of :mod:`path_a_density_audit` — measured-3 resolution,
per-owner density with ``min(D_i)`` domination, and the §6.1 decision table + §6.2
Clopper-Pearson escalation feasibility — on synthetic inputs. The numerical core is
pinned against closed-form incomplete-beta identities (no scipy), and the frozen
escalation cutoff (``D_min <= 8`` fast-fail) + its family-wise false-fast-fail rate
are reproduced with ``math.comb`` so the ADR §6.2 freeze is executable everywhere.
The view-level wiring is driven on a synthetic population-shaped DuckDB.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import duckdb
import pytest

from erre_sandbox.contracts.cognition_layers import PromotedEvidenceUnit
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.eval_store import bootstrap_schema, connect_analysis_view
from erre_sandbox.evidence.individuation.path_a_density_audit import (
    ALPHA,
    ALPHA_OWNER,
    D_TARGET_WEAK,
    DecisionAction,
    DensityAuditError,
    audit_density_from_view,
    clopper_pearson_upper,
    decision,
    escalation_feasible,
    per_owner_density,
    resolve_focal_measured,
)
from erre_sandbox.evidence.individuation.path_a_density_audit import (
    _reg_incomplete_beta as reg_incomplete_beta,
)
from erre_sandbox.evidence.individuation.path_a_h2_gate import H2Verdict
from erre_sandbox.evidence.individuation.trace_ddl import (
    TABLE_NAME,
    bootstrap_individual_state_trace_schema,
    column_names,
)

if TYPE_CHECKING:
    from pathlib import Path

_NOW = datetime(2026, 6, 3, tzinfo=UTC)


def _unit(other: str) -> PromotedEvidenceUnit:
    """A minimal valid promoted unit (only ``other_agent_id`` varies for density)."""
    return PromotedEvidenceUnit(
        other_agent_id=other,
        belief_kind="trust",
        confidence=0.8,
        affinity=0.5,
        familiarity=0.5,
        last_interaction_zone="agora",
        last_interaction_tick=100,
    )


def _units_distinct(n: int) -> tuple[PromotedEvidenceUnit, ...]:
    """``n`` units each with a distinct ``other_agent_id`` (D_i = n)."""
    return tuple(_unit(f"o_{i}") for i in range(n))


# --- numerical core: incomplete beta closed-form pins (no scipy) --------------


def test_incomplete_beta_closed_forms() -> None:
    # I_x(1,1) = x
    assert reg_incomplete_beta(0.37, 1.0, 1.0) == pytest.approx(0.37, abs=1e-12)
    # I_x(a,1) = x^a
    assert reg_incomplete_beta(0.5, 3.0, 1.0) == pytest.approx(0.125, abs=1e-12)
    # I_0.5(2,2) = 0.5 (symmetric)
    assert reg_incomplete_beta(0.5, 2.0, 2.0) == pytest.approx(0.5, abs=1e-12)
    # boundary clamps
    assert reg_incomplete_beta(0.0, 2.0, 3.0) == 0.0
    assert reg_incomplete_beta(1.0, 2.0, 3.0) == 1.0


def test_incomplete_beta_symmetry() -> None:
    # I_x(a,b) = 1 - I_{1-x}(b,a) across the (a+1)/(a+b+2) branch boundary.
    for x, a, b in ((0.3, 2.0, 5.0), (0.8, 4.0, 2.0), (0.65, 3.0, 3.0)):
        assert reg_incomplete_beta(x, a, b) == pytest.approx(
            1.0 - reg_incomplete_beta(1.0 - x, b, a), abs=1e-12
        )


# --- Clopper-Pearson boundaries (DA-S4C-4) -----------------------------------


def test_clopper_pearson_boundaries() -> None:
    # k == n -> 1.0 (degenerate Beta(k+1, 0), never passed to the bisection).
    assert clopper_pearson_upper(20, 20, 0.983) == 1.0
    # k == 0 -> ordinary path; I_x(1,n)=1-(1-x)^n so x = 1-(1-conf)^(1/n).
    expected = 1.0 - (1.0 - 0.983) ** (1.0 / 20)
    assert clopper_pearson_upper(0, 20, 0.983) == pytest.approx(expected, abs=1e-9)
    # monotone increasing in k.
    ups = [clopper_pearson_upper(k, 20, 0.983) for k in range(21)]
    assert ups == sorted(ups)


def test_clopper_pearson_invalid_inputs() -> None:
    for k, n, conf in ((-1, 20, 0.9), (21, 20, 0.9), (5, 0, 0.9), (5, 20, 0.0)):
        with pytest.raises(DensityAuditError):
            clopper_pearson_upper(k, n, conf)


# --- escalation feasibility: frozen cutoff D_min <= 8 (ADR §6.2) -------------


def test_escalation_cutoff_is_eight() -> None:
    # The frozen fast-fail boundary: D_min=8 hopeless, D_min=9 feasible.
    assert escalation_feasible(8).feasible is False
    assert escalation_feasible(9).feasible is True
    # rho_upper straddles the 20/30 ceiling exactly across that boundary.
    assert escalation_feasible(8).rho_upper < 20 / 30
    assert escalation_feasible(9).rho_upper >= 20 / 30
    # Independent literal pins (Codex MED-2): values cross-checked by Codex's own
    # stdlib re-derivation, so a drift in the incomplete-beta core is caught.
    assert escalation_feasible(8).rho_upper == pytest.approx(0.6559816215, abs=1e-9)
    assert escalation_feasible(9).rho_upper == pytest.approx(0.7004389740, abs=1e-9)


def _binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p), via math.comb (no scipy)."""
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))


def test_clopper_pearson_inverts_binomial_cdf() -> None:
    # Independent inverse check (Codex MED-2): the Clopper-Pearson upper limit U for
    # k of n satisfies P(Bin(n, U) <= k) = 1 - conf = alpha_owner — verified with a
    # math.comb binomial CDF, independent of the incomplete-beta implementation.
    n = 20
    for k in (5, 8, 9, 15):
        rho_upper = escalation_feasible(k).rho_upper
        assert _binom_cdf(k, n, rho_upper) == pytest.approx(ALPHA_OWNER, abs=1e-7)


def test_escalation_edges_and_monotonicity() -> None:
    assert escalation_feasible(20).rho_upper == 1.0
    assert escalation_feasible(20).feasible is True
    assert escalation_feasible(0).feasible is False
    rhos = [escalation_feasible(d).rho_upper for d in range(21)]
    assert rhos == sorted(rhos)
    # Šidák per-owner level is the frozen value.
    expected_alpha_owner = 1 - (1 - ALPHA) ** (1 / 3)
    assert pytest.approx(expected_alpha_owner, abs=1e-15) == ALPHA_OWNER


def test_escalation_family_wise_false_fast_fail_rate() -> None:
    """ADR §6.2 / Codex round-3: at true rho=20/30 the min-of-3 fast-fail at the
    cutoff is ~0.0384 (<= 0.05), and jumps to ~0.1087 one step looser — the reason
    the cutoff is D_min<=8, reproduced with math.comb (no scipy)."""
    rho = 20 / 30
    n = 20

    def binom_cdf(cut: int) -> float:
        return sum(
            math.comb(n, i) * rho**i * (1 - rho) ** (n - i) for i in range(cut + 1)
        )

    fwer_8 = 1 - (1 - binom_cdf(8)) ** 3
    fwer_9 = 1 - (1 - binom_cdf(9)) ** 3
    assert fwer_8 == pytest.approx(0.0384, abs=5e-4)
    assert fwer_8 <= ALPHA
    assert fwer_9 == pytest.approx(0.1087, abs=5e-4)
    assert fwer_9 > ALPHA


# --- per-owner density: min(D_i) domination (DA-S4C-5 / DA-S4C-6) ------------


def _density(*counts: int | None) -> Any:
    ev: dict[str, tuple[PromotedEvidenceUnit, ...] | None] = {}
    ids = []
    for idx, c in enumerate(counts):
        oid = f"a_kant_{idx + 1:03d}"
        ids.append(oid)
        ev[oid] = None if c is None else _units_distinct(c)
    return per_owner_density(tuple(ids), ev)


def test_skew_vector_fails_on_smallest_owner() -> None:
    # (20,20,1): median is 20 but min=1 → d_fail (median sneak-through prevented).
    audit = _density(20, 20, 1)
    assert audit.min_d == 1
    assert audit.d_pass is False
    # per-owner vector is preserved (never median-compressed, S3.5a HIGH-1).
    assert audit.per_owner == (
        ("a_kant_001", 20),
        ("a_kant_002", 20),
        ("a_kant_003", 1),
    )


def test_uniform_pass_and_bonferroni() -> None:
    audit = _density(20, 20, 20)
    assert audit.min_d == 20
    assert audit.d_pass is True
    assert audit.d_pass_bonf is False  # 20 < 30
    assert audit.target == D_TARGET_WEAK
    strong = _density(30, 31, 30)
    assert strong.d_pass is True
    assert strong.d_pass_bonf is True  # min 30 >= D_TARGET_BONF


def test_below_target_fails() -> None:
    assert _density(20, 20, 8).d_pass is False  # min 8 < 20


def test_degenerate_owner_fails() -> None:
    audit = _density(20, None, 20)
    assert audit.min_d == 0  # None counted as effective 0
    assert audit.d_pass is False
    assert audit.degenerate_owners == ("a_kant_002",)
    assert audit.per_owner[1] == ("a_kant_002", None)


def test_duplicate_units_do_not_inflate_density() -> None:
    # 25 raw units all naming the same other → distinct-other D_i = 1 (frozen ⑦).
    # Exactly 3 owners (⑤ N=3); the duplicated owner dominates min(D_i).
    ev = {
        "a_kant_001": tuple(_unit("o_same") for _ in range(25)),
        "a_kant_002": _units_distinct(20),
        "a_kant_003": _units_distinct(20),
    }
    audit = per_owner_density(("a_kant_001", "a_kant_002", "a_kant_003"), ev)
    assert audit.per_owner[0] == ("a_kant_001", 1)
    assert audit.min_d == 1
    assert audit.d_pass is False


def test_per_owner_density_requires_exactly_three_owners() -> None:
    # ⑤ N=3: a widened / shrunk measured set must fail loud (Codex MED-1).
    ev = {"a_kant_001": _units_distinct(20)}
    with pytest.raises(DensityAuditError, match="exactly 3"):
        per_owner_density(("a_kant_001",), ev)


# --- measured-3 resolution (DA-S4C-2) ----------------------------------------


def test_resolve_population_focal_group() -> None:
    base_groups = (
        ("kant", ("a_kant_001", "a_kant_002", "a_kant_003")),
        ("nietzsche", tuple(f"a_nietzsche_{i:03d}" for i in range(1, 10))),
        ("rikyu", tuple(f"a_rikyu_{i:03d}" for i in range(1, 10))),
    )
    assert resolve_focal_measured(base_groups, "kant") == (
        "a_kant_001",
        "a_kant_002",
        "a_kant_003",
    )


def test_resolve_legacy_single_group() -> None:
    base_groups = (("rikyu", ("a_rikyu_001", "a_rikyu_002", "a_rikyu_003")),)
    assert resolve_focal_measured(base_groups, "rikyu") == (
        "a_rikyu_001",
        "a_rikyu_002",
        "a_rikyu_003",
    )


def test_resolve_count_collision_uses_identity_not_count() -> None:
    # world_size=9: every base group has exactly 3 → count==3 would be ambiguous,
    # but identity resolution returns precisely the focal trio (DA-S4C-2).
    base_groups = (
        ("kant", ("a_kant_001", "a_kant_002", "a_kant_003")),
        ("nietzsche", ("a_nietzsche_001", "a_nietzsche_002", "a_nietzsche_003")),
        ("rikyu", ("a_rikyu_001", "a_rikyu_002", "a_rikyu_003")),
    )
    assert resolve_focal_measured(base_groups, "kant") == (
        "a_kant_001",
        "a_kant_002",
        "a_kant_003",
    )


def test_resolve_focal_absent_raises() -> None:
    base_groups = (("nietzsche", ("a_nietzsche_001",)),)
    with pytest.raises(DensityAuditError, match="not a base group"):
        resolve_focal_measured(base_groups, "kant")


def test_resolve_wrong_size_raises() -> None:
    base_groups = (("kant", ("a_kant_001", "a_kant_002")),)
    with pytest.raises(DensityAuditError, match="expected exactly 3"):
        resolve_focal_measured(base_groups, "kant")


# --- decision table (ADR §6.1, all branches) ---------------------------------


def test_decision_table_all_branches() -> None:
    assert (
        decision(H2Verdict.PASS, d_pass=True, escalation_feasible=False).action
        is DecisionAction.GO
    )
    assert (
        decision(H2Verdict.INCONCLUSIVE, d_pass=True, escalation_feasible=False).action
        is DecisionAction.Y_PIVOT
    )
    assert (
        decision(H2Verdict.INVALID, d_pass=True, escalation_feasible=True).action
        is DecisionAction.Y_DIRECT
    )
    # d_fail ∧ (PASS|INCONCLUSIVE): feasible → ESCALATE, else Y_DIRECT.
    assert (
        decision(H2Verdict.PASS, d_pass=False, escalation_feasible=True).action
        is DecisionAction.ESCALATE
    )
    assert (
        decision(H2Verdict.INCONCLUSIVE, d_pass=False, escalation_feasible=True).action
        is DecisionAction.ESCALATE
    )
    assert (
        decision(H2Verdict.PASS, d_pass=False, escalation_feasible=False).action
        is DecisionAction.Y_DIRECT
    )
    # d_fail ∧ INVALID: INVALID precedence regardless of feasibility.
    assert (
        decision(H2Verdict.INVALID, d_pass=False, escalation_feasible=True).action
        is DecisionAction.Y_DIRECT
    )


# --- view-level wiring: synthetic population DuckDB ---------------------------

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


def _evidence_json(n_distinct: int) -> str:
    units = [
        {
            "other_agent_id": f"o_{j}",
            "belief_kind": "trust",
            "confidence": 0.8,
            "affinity": 0.5,
            "familiarity": 0.5,
            "last_interaction_zone": "agora",
            "last_interaction_tick": 100,
        }
        for j in range(n_distinct)
    ]
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


def _build_population_db(path: Path, run_id: str) -> None:
    """A population-shaped run: 3 measured kant + 4 cross-base background."""
    # (agent_id, persona, distinct-other count)
    roster = [
        ("a_kant_001", "kant", 20),
        ("a_kant_002", "kant", 20),
        ("a_kant_003", "kant", 20),
        ("a_nietzsche_001", "nietzsche", 5),
        ("a_nietzsche_002", "nietzsche", 5),
        ("a_rikyu_001", "rikyu", 5),
        ("a_rikyu_002", "rikyu", 5),
    ]
    con = duckdb.connect(str(path), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    cols = ", ".join(_DIALOG_COLS)
    ph = ", ".join("?" for _ in _DIALOG_COLS)
    tcols = ", ".join(column_names())
    tph = ", ".join("?" for _ in column_names())
    for agent, persona, density in roster:
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
                json.dumps(["trust", "wary"]),
                0,
                None,
                _evidence_json(density),
            ),
        )
    con.execute("CHECKPOINT")
    con.close()


def test_audit_density_from_view_population(tmp_path: Path) -> None:
    db = tmp_path / "pop.duckdb"
    _build_population_db(db, "run0")
    view = connect_analysis_view(db)
    try:
        audit = audit_density_from_view(view, run_id="run0", focal_persona="kant")
    finally:
        view.close()
    # Only the 3 measured kant owners are audited (background excluded), each D=20.
    assert {oid for oid, _ in audit.per_owner} == {
        "a_kant_001",
        "a_kant_002",
        "a_kant_003",
    }
    assert audit.min_d == 20
    assert audit.d_pass is True
    assert audit.degenerate_owners == ()


def test_audit_density_from_view_missing_run_raises(tmp_path: Path) -> None:
    db = tmp_path / "pop.duckdb"
    _build_population_db(db, "run0")
    view = connect_analysis_view(db)
    try:
        with pytest.raises(DensityAuditError):
            audit_density_from_view(view, run_id="absent", focal_persona="kant")
    finally:
        view.close()

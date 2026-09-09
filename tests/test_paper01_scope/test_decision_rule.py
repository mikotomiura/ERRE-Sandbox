"""Tests for the I-005 decision rule -- ``decide_scope()`` (design-final.md §3-§5).

Encoder-independent (Test Plan): every :class:`~scripts.paper01_scope_condition.
DeltaDecomposition` / :class:`Stage1Result` / :class:`CellResult` /
:class:`TauCalibration` fixture below is a hand-built dataclass instance,
never routed through the (out-of-scope-for-I-005) encoder / statistics
layers I-002..I-004/I-006 own -- exactly the Test Plan's "``ExternalVerdict``
相当の dataclass を直接構築して通す" discipline, applied to
:func:`decide_scope`'s own (not-yet-implemented-upstream) inputs.

Fixture-naming discipline throughout: each isolated-fail-branch fixture
below is built to trip **exactly one** of F1-F7 (design-final.md §4) --
every other branch's predicate is deliberately kept false in the same
fixture, so a fixture's ``fail_reason`` assertion is a witness for that one
branch, not an accident of overlapping conditions.
"""

from __future__ import annotations

import itertools

import pytest
from scripts import paper01_scope_condition as mod

_DEFAULT_OBJECTS: tuple[str, ...] = ("brick", "paperclip", "bottle", "shoe")
_DEFAULT_RHO_BY_TAU: tuple[float, ...] = (
    0.90,
    0.85,
    0.80,
    0.75,
    0.70,
    0.65,
    0.60,
    0.55,
    0.50,
    0.45,
    0.40,
)
_ALL_VERDICTS: tuple[str, ...] = (
    "PASS",
    "NO_VALID_SCORER",
    "INVALID_TASK_BATTERY",
    "INCONCLUSIVE_UNDERPOWERED",
)
_STAGE0_KINDS: tuple[str, ...] = (
    "material_s_driven",
    "material_t_driven",
    "no_material",
)

_STAGE1_BASE: dict[str, object] = {
    "candidate": "X0",
    "n_replicates": 500,
    "drop_p5": 0.10,
    "drop_p95": 0.30,
    "median_drop": 0.20,
    "eligible_fraction": 0.9,
    "drop_p5_eligible": 0.11,
    "drop_p95_eligible": 0.29,
    "median_drop_eligible": 0.19,
    "drop_p5_strat": 0.09,
    "drop_p95_strat": 0.31,
    "median_drop_strat": 0.21,
    "n_objects_pool_short": 0,
    "pool_short_objects": (),
    "median_draw_drop": 0.20,
    "median_draw_outcome": "DEFLATION_SUPPORTED",
}


# --- fixture builders --------------------------------------------------------


def _cell(
    *,
    verdict: str,
    active_objects: tuple[str, ...] = _DEFAULT_OBJECTS,
    tau: float = 0.90,
    k_target: int = 30,
    split_scheme: str = "SPLIT-BLOCK",
    corpus: str = "ocsai",
) -> mod.CellResult:
    weights = (
        {obj: 1.0 / len(active_objects) for obj in active_objects}
        if active_objects
        else {}
    )
    return mod.CellResult(
        tau=tau,
        k_target=k_target,
        k_effective=k_target,
        n_leaders=k_target,
        corpus=corpus,
        split_scheme=split_scheme,
        verdict=verdict,
        active_objects=active_objects,
        object_weights=weights,
    )


def _tau_cal(
    *,
    rho_int_primary: float = 0.5,
    single_point_dependent: bool = False,
    rho_by_tau: tuple[float, ...] = _DEFAULT_RHO_BY_TAU,
    tau_star: float = 0.5,
    k_star: int = 10,
) -> mod.TauCalibration:
    return mod.TauCalibration(
        rho_int_primary=rho_int_primary,
        rho_by_tau=rho_by_tau,
        tau_star=tau_star,
        k_star=k_star,
        single_point_dependent=single_point_dependent,
    )


def _split_cells(
    *,
    arm_a_verdict: str,
    arm_s_verdict: str,
    split_scheme: str = "SPLIT-BLOCK",
    arm_a_objects: tuple[str, ...] = _DEFAULT_OBJECTS,
    arm_s_objects: tuple[str, ...] = _DEFAULT_OBJECTS,
    rho_int_primary: float = 0.5,
    single_point_dependent: bool = False,
) -> mod.SplitCells:
    return mod.SplitCells(
        arm_a=_cell(
            verdict=arm_a_verdict,
            active_objects=arm_a_objects,
            tau=0.90,
            k_target=30,
            split_scheme=split_scheme,
        ),
        arm_s=_cell(
            verdict=arm_s_verdict,
            active_objects=arm_s_objects,
            tau=0.5,
            k_target=10,
            split_scheme=split_scheme,
        ),
        tau_calibration=_tau_cal(
            rho_int_primary=rho_int_primary,
            single_point_dependent=single_point_dependent,
        ),
    )


def _supportive_cells(
    *, rho_int_primary: float = 0.5, single_point_dependent: bool = False
) -> dict[str, mod.SplitCells]:
    """Both Ocsai splits: ARM-A PASS / ARM-S NO_VALID_SCORER, robust, ρ reachable.

    The condition-C-supported baseline every "only this one thing is wrong"
    fixture below starts from.
    """
    kwargs = {
        "rho_int_primary": rho_int_primary,
        "single_point_dependent": single_point_dependent,
    }
    return {
        "SPLIT-BLOCK": _split_cells(
            arm_a_verdict="PASS",
            arm_s_verdict="NO_VALID_SCORER",
            split_scheme="SPLIT-BLOCK",
            **kwargs,
        ),
        "SPLIT-PARITY": _split_cells(
            arm_a_verdict="PASS",
            arm_s_verdict="NO_VALID_SCORER",
            split_scheme="SPLIT-PARITY",
            **kwargs,
        ),
    }


def _totality_cells(
    verdict: str, *, agree: bool, robust: bool
) -> dict[str, mod.SplitCells]:
    """Sweep ``verdict`` through both arms of both splits for the totality test.

    Not meant to hit a specific F-branch -- only to prove
    :func:`~scripts.paper01_scope_condition.decide_scope` never raises for
    any :data:`_ALL_VERDICTS` member appearing anywhere in its input
    (AC 005-1). The F1-F7-specific fixtures live in
    ``test_each_fail_branch_is_reachable`` below.
    """
    other = _ALL_VERDICTS[(_ALL_VERDICTS.index(verdict) + 1) % len(_ALL_VERDICTS)]
    parity_verdict = verdict if agree else other
    return {
        "SPLIT-BLOCK": mod.SplitCells(
            arm_a=_cell(verdict=verdict, split_scheme="SPLIT-BLOCK"),
            arm_s=_cell(verdict=verdict, split_scheme="SPLIT-BLOCK"),
            tau_calibration=_tau_cal(single_point_dependent=not robust),
        ),
        "SPLIT-PARITY": mod.SplitCells(
            arm_a=_cell(verdict=parity_verdict, split_scheme="SPLIT-PARITY"),
            arm_s=_cell(verdict=parity_verdict, split_scheme="SPLIT-PARITY"),
            tau_calibration=_tau_cal(single_point_dependent=not robust),
        ),
    }


def _delta_row(
    source: str, candidate: str, *, t: float, s: float
) -> mod.DeltaDecomposition:
    """A Stage 0 row with ``Delta = T - S`` (design-final.md §1 algebra) and
    good/common set identically -- only the good/common *average* the F4 /
    T-confound checks read is exercised by this issue, not the MEDIUM-1
    label-stratified gap.
    """
    delta = t - s
    return mod.DeltaDecomposition(
        source=source,
        candidate=candidate,
        n_good=5,
        n_common=5,
        mean_t_good=t,
        mean_t_common=t,
        mean_s_good=s,
        mean_s_common=s,
        mean_delta_good=delta,
        mean_delta_common=delta,
        s_common_minus_s_good=0.0,
        rho=0.5,
    )


def _build_stage0(kind: str) -> tuple[mod.DeltaDecomposition, ...]:
    """3 hand-picked Stage 0 shapes (AC 005-1's "Stage0 3 値" axis).

    ``"material_s_driven"``: a material Delta difference exists (F4 false)
    and the T/S asymmetry is S-driven (no T-confound note).
    ``"material_t_driven"``: same material difference, but T-driven (forces
    ``t_confound_note_required``, AC 005-10).
    ``"no_material"``: ``|Delta_int - Delta_ext| < DELTA_MATERIAL_EPS``
    (F4, AC 005-11).
    """
    internal = _delta_row(
        mod._STAGE0_INTERNAL_SOURCE, mod._STAGE0_INTERNAL_CANDIDATE, t=0.90, s=0.70
    )
    if kind == "no_material":
        external = _delta_row(
            mod._STAGE0_EXTERNAL_SOURCE,
            mod._STAGE0_EXTERNAL_CANDIDATE,
            t=0.90,
            s=0.695,
        )
    elif kind == "material_t_driven":
        external = _delta_row(
            mod._STAGE0_EXTERNAL_SOURCE,
            mod._STAGE0_EXTERNAL_CANDIDATE,
            t=0.50,
            s=0.69,
        )
    else:  # "material_s_driven"
        external = _delta_row(
            mod._STAGE0_EXTERNAL_SOURCE,
            mod._STAGE0_EXTERNAL_CANDIDATE,
            t=0.89,
            s=0.30,
        )
    return (internal, external)


def _stage1(outcome: str) -> mod.Stage1Result:
    return mod.Stage1Result(
        stage1_outcome=outcome,
        deflation_supported=outcome == "DEFLATION_SUPPORTED",
        **_STAGE1_BASE,
    )


# --- AC 005-1 (totality) ------------------------------------------------------


def test_decide_scope_is_total() -> None:
    """``decide_scope`` returns a :class:`ScopeVerdict` for every combination
    of the declared input space, never raising (AC 005-1): 4 verdict x 2
    分割 (agree/disagree) x 隣接段 (robust/not) x Stage0 3 値 x Stage1 3 値
    x Cambridge (4 verdict values).
    """
    axes = itertools.product(
        _ALL_VERDICTS,
        (True, False),
        (True, False),
        _STAGE0_KINDS,
        mod.STAGE1_OUTCOME_ENUM,
        _ALL_VERDICTS,
    )
    count = 0
    for verdict, agree, robust, stage0_kind, stage1_outcome, cambridge_verdict in axes:
        count += 1
        cells = _totality_cells(verdict, agree=agree, robust=robust)
        stage0 = _build_stage0(stage0_kind)
        stage1 = _stage1(stage1_outcome)
        cambridge = _cell(verdict=cambridge_verdict)

        result = mod.decide_scope(stage0, stage1, cells, cambridge=cambridge)

        assert isinstance(result, mod.ScopeVerdict)
        assert result.verdict in mod.SCOPE_VERDICT_ENUM

    assert count == 4 * 2 * 2 * 3 * 3 * 4


# --- AC 005-2 (non-tautological) ----------------------------------------------


def test_both_outcomes_are_reachable() -> None:
    """``condition_c_supported`` reaches both ``True`` and ``False`` (AC 005-2)."""
    stage0 = _build_stage0("material_s_driven")
    cambridge = _cell(verdict="INCONCLUSIVE_UNDERPOWERED")
    stage1 = _stage1("DEFLATION_REJECTED")

    supported = mod.decide_scope(
        stage0, stage1, _supportive_cells(), cambridge=cambridge
    )
    assert supported.condition_c_supported is True
    assert supported.verdict == "WRITE"

    not_supported_cells = {
        "SPLIT-BLOCK": _split_cells(
            arm_a_verdict="PASS", arm_s_verdict="PASS", split_scheme="SPLIT-BLOCK"
        ),
        "SPLIT-PARITY": _split_cells(
            arm_a_verdict="PASS", arm_s_verdict="PASS", split_scheme="SPLIT-PARITY"
        ),
    }
    not_supported = mod.decide_scope(
        stage0, stage1, not_supported_cells, cambridge=cambridge
    )
    assert not_supported.condition_c_supported is False
    assert not_supported.verdict == "DO_NOT_WRITE"


# --- AC 005-3 (each F1-F7 branch reachable) -----------------------------------


def test_each_fail_branch_is_reachable() -> None:
    """One dedicated fixture per F1-F7, each isolated to that branch alone."""
    material_s_driven = _build_stage0("material_s_driven")
    no_material = _build_stage0("no_material")
    cambridge_ok = _cell(verdict="INCONCLUSIVE_UNDERPOWERED")
    cambridge_pass = _cell(verdict="PASS")
    stage1_rejected = _stage1("DEFLATION_REJECTED")

    f1_cells = {
        "SPLIT-BLOCK": _split_cells(
            arm_a_verdict="PASS",
            arm_s_verdict="NO_VALID_SCORER",
            split_scheme="SPLIT-BLOCK",
            rho_int_primary=0.1,
        ),
        "SPLIT-PARITY": _split_cells(
            arm_a_verdict="PASS",
            arm_s_verdict="NO_VALID_SCORER",
            split_scheme="SPLIT-PARITY",
            rho_int_primary=0.1,
        ),
    }
    f2_cells = {
        "SPLIT-BLOCK": _split_cells(
            arm_a_verdict="PASS",
            arm_s_verdict="NO_VALID_SCORER",
            split_scheme="SPLIT-BLOCK",
            arm_a_objects=("a", "b", "c", "d", "e", "f", "g", "h", "i", "j"),
            arm_s_objects=("a", "b"),
        ),
        "SPLIT-PARITY": _split_cells(
            arm_a_verdict="PASS",
            arm_s_verdict="NO_VALID_SCORER",
            split_scheme="SPLIT-PARITY",
            arm_a_objects=("a", "b", "c", "d", "e", "f", "g", "h", "i", "j"),
            arm_s_objects=("a", "b"),
        ),
    }
    f3_cells = {
        "SPLIT-BLOCK": _split_cells(
            arm_a_verdict="PASS",
            arm_s_verdict="INVALID_TASK_BATTERY",
            split_scheme="SPLIT-BLOCK",
        ),
        "SPLIT-PARITY": _split_cells(
            arm_a_verdict="PASS",
            arm_s_verdict="INVALID_TASK_BATTERY",
            split_scheme="SPLIT-PARITY",
        ),
    }
    f6_cells = {
        "SPLIT-BLOCK": _split_cells(
            arm_a_verdict="PASS",
            arm_s_verdict="NO_VALID_SCORER",
            split_scheme="SPLIT-BLOCK",
        ),
        "SPLIT-PARITY": _split_cells(
            arm_a_verdict="NO_VALID_SCORER",
            arm_s_verdict="NO_VALID_SCORER",
            split_scheme="SPLIT-PARITY",
        ),
    }
    f7_cells = {
        "SPLIT-BLOCK": _split_cells(
            arm_a_verdict="PASS",
            arm_s_verdict="NO_VALID_SCORER",
            split_scheme="SPLIT-BLOCK",
            single_point_dependent=True,
        ),
        "SPLIT-PARITY": _split_cells(
            arm_a_verdict="PASS",
            arm_s_verdict="NO_VALID_SCORER",
            split_scheme="SPLIT-PARITY",
            single_point_dependent=False,
        ),
    }

    cases: dict[str, tuple[dict[str, mod.SplitCells], tuple, mod.CellResult]] = {
        "F1": (f1_cells, material_s_driven, cambridge_ok),
        "F2": (f2_cells, material_s_driven, cambridge_ok),
        "F3": (f3_cells, material_s_driven, cambridge_ok),
        "F4": (_supportive_cells(), no_material, cambridge_ok),
        "F5": (_supportive_cells(), material_s_driven, cambridge_pass),
        "F6": (f6_cells, material_s_driven, cambridge_ok),
        "F7": (f7_cells, material_s_driven, cambridge_ok),
    }
    for expected, (cells, stage0, cambridge) in cases.items():
        result = mod.decide_scope(stage0, stage1_rejected, cells, cambridge=cambridge)
        assert result.fail_reason == expected, f"{expected}: got {result.fail_reason}"
        assert result.condition_c_supported is False
        assert result.verdict == "DO_NOT_WRITE"


# --- AC 005-4 (precedence, non-tautological) ----------------------------------


def test_fail_precedence_resolves_simultaneous_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F4 and F5 simultaneously true -> primary reason is F4 (AC 005-4).

    Non-tautology (Test Plan): re-ordering ``FAIL_PRECEDENCE`` via
    ``monkeypatch.setattr`` must move the winner -- proves the precedence
    tuple is actually read live, not hardcoded.
    """
    cells = _supportive_cells()
    stage0 = _build_stage0("no_material")  # F4 true
    cambridge = _cell(verdict="PASS")  # F5 true
    stage1 = _stage1("DEFLATION_REJECTED")

    result = mod.decide_scope(stage0, stage1, cells, cambridge=cambridge)
    assert result.fail_reason == "F4"

    monkeypatch.setattr(
        mod, "FAIL_PRECEDENCE", ("F5", "F4", "F1", "F2", "F3", "F6", "F7")
    )
    reordered = mod.decide_scope(stage0, stage1, cells, cambridge=cambridge)
    assert reordered.fail_reason == "F5"
    assert reordered.fail_reason != result.fail_reason


# --- AC 005-5 (Stage 1 override) ----------------------------------------------


def test_deflation_overrides_stage2() -> None:
    """Stage 2 supports C but Stage 1 supports deflation -> DO_NOT_WRITE
    without retroactively flipping ``condition_c_supported`` (AC 005-5).
    """
    cells = _supportive_cells()
    stage0 = _build_stage0("material_s_driven")
    cambridge = _cell(verdict="INCONCLUSIVE_UNDERPOWERED")
    stage1_supported = _stage1("DEFLATION_SUPPORTED")

    result = mod.decide_scope(stage0, stage1_supported, cells, cambridge=cambridge)

    assert result.condition_c_supported is True
    assert result.verdict == "DO_NOT_WRITE"
    assert result.deflation_supported is True


def test_inconclusive_never_derives_write_right() -> None:
    """This issue's core rule: ``INCONCLUSIVE`` must never produce ``"WRITE"``,
    even though it shares ``deflation_supported == False`` with
    ``DEFLATION_REJECTED`` (Codex TASK-PRE HIGH-3 / DA-SC-19).
    """
    cells = _supportive_cells()
    stage0 = _build_stage0("material_s_driven")
    cambridge = _cell(verdict="INCONCLUSIVE_UNDERPOWERED")

    inconclusive = mod.decide_scope(
        stage0, _stage1("INCONCLUSIVE"), cells, cambridge=cambridge
    )
    rejected = mod.decide_scope(
        stage0, _stage1("DEFLATION_REJECTED"), cells, cambridge=cambridge
    )

    assert inconclusive.deflation_supported is False
    assert rejected.deflation_supported is False
    assert inconclusive.deflation_supported == rejected.deflation_supported

    assert inconclusive.verdict == "DO_NOT_WRITE"
    assert rejected.verdict == "WRITE"
    assert inconclusive.verdict != rejected.verdict


# --- AC 005-6 (one-sided evidence) --------------------------------------------


def test_one_sided_evidence_is_not_support() -> None:
    """ARM-S NO_VALID_SCORER but ARM-A not PASS -> not supported (AC 005-6,
    B-G1-10's two-sided requirement).
    """
    cells = {
        "SPLIT-BLOCK": _split_cells(
            arm_a_verdict="INCONCLUSIVE_UNDERPOWERED",
            arm_s_verdict="NO_VALID_SCORER",
            split_scheme="SPLIT-BLOCK",
        ),
        "SPLIT-PARITY": _split_cells(
            arm_a_verdict="INCONCLUSIVE_UNDERPOWERED",
            arm_s_verdict="NO_VALID_SCORER",
            split_scheme="SPLIT-PARITY",
        ),
    }
    stage0 = _build_stage0("material_s_driven")
    cambridge = _cell(verdict="INCONCLUSIVE_UNDERPOWERED")

    result = mod.decide_scope(
        stage0, _stage1("DEFLATION_REJECTED"), cells, cambridge=cambridge
    )

    assert result.condition_c_supported is False
    assert result.verdict == "DO_NOT_WRITE"


# --- AC 005-7 (split disagreement, F6) ----------------------------------------


def test_split_disagreement_is_not_support() -> None:
    """One split supports condition 1, the other does not -> F6 (AC 005-7)."""
    cells = {
        "SPLIT-BLOCK": _split_cells(
            arm_a_verdict="PASS",
            arm_s_verdict="NO_VALID_SCORER",
            split_scheme="SPLIT-BLOCK",
        ),
        "SPLIT-PARITY": _split_cells(
            arm_a_verdict="NO_VALID_SCORER",
            arm_s_verdict="NO_VALID_SCORER",
            split_scheme="SPLIT-PARITY",
        ),
    }
    stage0 = _build_stage0("material_s_driven")
    cambridge = _cell(verdict="INCONCLUSIVE_UNDERPOWERED")

    result = mod.decide_scope(
        stage0, _stage1("DEFLATION_REJECTED"), cells, cambridge=cambridge
    )

    assert result.fail_reason == "F6"
    assert result.condition_c_supported is False


# --- AC 005-8 (single-point dependence, F7) -----------------------------------


def test_single_point_dependence_is_not_support() -> None:
    """τ* neighbour robustness fails on one split -> F7 (AC 005-8)."""
    cells = {
        "SPLIT-BLOCK": _split_cells(
            arm_a_verdict="PASS",
            arm_s_verdict="NO_VALID_SCORER",
            split_scheme="SPLIT-BLOCK",
            single_point_dependent=True,
        ),
        "SPLIT-PARITY": _split_cells(
            arm_a_verdict="PASS",
            arm_s_verdict="NO_VALID_SCORER",
            split_scheme="SPLIT-PARITY",
            single_point_dependent=False,
        ),
    }
    stage0 = _build_stage0("material_s_driven")
    cambridge = _cell(verdict="INCONCLUSIVE_UNDERPOWERED")

    result = mod.decide_scope(
        stage0, _stage1("DEFLATION_REJECTED"), cells, cambridge=cambridge
    )

    assert result.single_point_dependent is True
    assert result.fail_reason == "F7"
    assert result.condition_c_supported is False


# --- AC 005-9 (Cambridge non-contradiction, F5) -------------------------------


def test_cambridge_contradiction_only_on_pass() -> None:
    """Cambridge ARM-S PASS contradicts C (F5); INCONCLUSIVE_UNDERPOWERED
    does not (AC 005-9).
    """
    cells = _supportive_cells()
    stage0 = _build_stage0("material_s_driven")
    stage1 = _stage1("DEFLATION_REJECTED")

    contradicted = mod.decide_scope(
        stage0, stage1, cells, cambridge=_cell(verdict="PASS")
    )
    assert contradicted.fail_reason == "F5"
    assert contradicted.condition_c_supported is False

    underpowered = mod.decide_scope(
        stage0, stage1, cells, cambridge=_cell(verdict="INCONCLUSIVE_UNDERPOWERED")
    )
    assert underpowered.fail_reason is None
    assert underpowered.condition_c_supported is True


# --- AC 005-10 (T-confound note, does not fail) -------------------------------


def test_t_attribution_requires_note_but_does_not_fail() -> None:
    """A T-driven Stage 0 does not collapse the verdict -- it only requires
    the T-confound note (AC 005-10, design-final.md HIGH-3).
    """
    cells = _supportive_cells()
    stage0 = _build_stage0("material_t_driven")
    cambridge = _cell(verdict="INCONCLUSIVE_UNDERPOWERED")

    result = mod.decide_scope(
        stage0, _stage1("DEFLATION_REJECTED"), cells, cambridge=cambridge
    )

    assert result.condition_c_supported is True
    assert result.verdict == "WRITE"
    assert result.t_confound_note_required is True


# --- AC 005-11 (no material Delta -> F4) --------------------------------------


def test_no_material_delta_is_f4() -> None:
    """Stage 0 shows no material Delta difference -> F4 (AC 005-11)."""
    cells = _supportive_cells()
    stage0 = _build_stage0("no_material")
    cambridge = _cell(verdict="INCONCLUSIVE_UNDERPOWERED")

    result = mod.decide_scope(
        stage0, _stage1("DEFLATION_REJECTED"), cells, cambridge=cambridge
    )

    assert result.fail_reason == "F4"
    assert result.condition_c_supported is False
    assert result.verdict == "DO_NOT_WRITE"


# --- TASK-POST 反映 (二者レビュー) --------------------------------------------


def test_missing_ocsai_split_can_never_produce_write() -> None:
    """片方の Ocsai split しか無い ``cells`` から ``WRITE`` は出ない (Codex MEDIUM-1)。

    ``design-final.md`` §3 Stage 2 の条件 2 は **両分割**での成立を要求する。
    ``cli_scope()`` は片側欠如で exit 1 するが、**判定関数が呼び出し側の親切さに
    依存してはいけない** — 以前の実装は ``all(cond1_by_split.values())`` だったため、
    片側だけの ``cells`` でも「存在する split では全部成立」で真になり、
    **両分割合意として読まれ得た**。

    恒真ではない: 同じ入力から片方の split を**取り除くだけ**で
    verdict が ``WRITE`` から ``DO_NOT_WRITE`` へ変わることを示す。
    """
    stage0 = _build_stage0("material_s_driven")
    stage1 = _stage1("DEFLATION_REJECTED")
    cambridge = _cell(verdict="INCONCLUSIVE_UNDERPOWERED")

    both = _supportive_cells()
    baseline = mod.decide_scope(stage0, stage1, both, cambridge=cambridge)
    assert baseline.verdict == "WRITE", (
        "fixture must reach WRITE with both splits, otherwise the removal below "
        "proves nothing"
    )

    for dropped in tuple(both):
        one_split = {k: v for k, v in both.items() if k != dropped}
        got = mod.decide_scope(stage0, stage1, one_split, cambridge=cambridge)
        assert got.verdict == "DO_NOT_WRITE", (
            f"dropping {dropped!r} must fail closed, got {got.verdict!r}"
        )
        assert got.condition_c_supported is False

    empty = mod.decide_scope(stage0, stage1, {}, cambridge=cambridge)
    assert empty.verdict == "DO_NOT_WRITE"


def test_stage1_result_rejects_mirror_inconsistency() -> None:
    """``deflation_supported`` が ``stage1_outcome`` と食い違う artifact を拒否する
    (Codex MEDIUM-2)。

    ``deflation_supported`` は派生ミラーだが、dataclass は以前どの組合せも受け入れて
    いた。事前登録した装置では無害な不整合ではない — 2 つのフィールドは**別の読み手**
    (``decide_scope()`` は enum、単純な呼び出し側は bool) に渡るため、食い違った
    artifact は**同じ replicate から両方の主張を作れて**しまう。
    """
    base = dict(_STAGE1_BASE)

    for outcome in mod.STAGE1_OUTCOME_ENUM:
        consistent = outcome == "DEFLATION_SUPPORTED"
        mod.Stage1Result(stage1_outcome=outcome, deflation_supported=consistent, **base)
        with pytest.raises(ValueError, match="deflation_supported must mirror"):
            mod.Stage1Result(
                stage1_outcome=outcome, deflation_supported=not consistent, **base
            )

    with pytest.raises(ValueError, match="is not one of"):
        mod.Stage1Result(
            stage1_outcome="DEFLATION_REJECTED_TYPO",
            deflation_supported=False,
            **base,
        )

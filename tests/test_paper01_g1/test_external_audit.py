"""Tests for the Cambridge adapter + orchestration in
scripts/paper01_external_audit.py (Loop I-005).

design-final.md §3 / §4 / §7 is the single source of truth for the
procedures under test. Per the Test Plan (loop/.../issues/005.md):

* The decision-rule / arm-construction / negative-control / split tests
  are **encoder-independent**: candidates are built either directly as
  :class:`~scripts.paper01_external_audit.DrawItems` (numpy-only, mirrors
  ``tests/test_paper01_g1/test_statistics.py``) or scored through a tiny
  deterministic *stub* embedding closure (pure numpy/hash, no ML model) --
  never ``sentence_transformers``. CI runs with no ``[eval]`` extras.
* The real-xlsx end-to-end path is ``@pytest.mark.eval`` +
  ``pytest.importorskip("sentence_transformers")``.
* Every negative case is pushed through the *same* production function
  (``decide_external`` / ``score_rows_for_draw`` / ...) rather than
  asserting a hand-built dataclass's own fields.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import numpy as np
import pytest
from scripts import paper01_external_audit as mod

from erre_sandbox.evidence.es4_actuator import constants as _c

if TYPE_CHECKING:
    from collections.abc import Sequence

# =============================================================================
# shared helpers (encoder-independent)
# =============================================================================


def _draw(
    *,
    object_key: str = "bowl",
    good_scores: Sequence[float],
    common_scores: Sequence[float],
    good_scores_lao: Sequence[float] | None = None,
    common_scores_lao: Sequence[float] | None = None,
    potency: float,
) -> mod.DrawItems:
    """One hand-scored :class:`DrawItems` for a single object (numpy-only,
    no encoder) -- mirrors ``test_statistics.py``'s own construction style.
    """
    good_lao = good_scores if good_scores_lao is None else good_scores_lao
    common_lao = common_scores if common_scores_lao is None else common_scores_lao
    scores_full = tuple(good_scores) + tuple(common_scores)
    scores_lao = tuple(good_lao) + tuple(common_lao)
    labels = tuple([1] * len(good_scores) + [0] * len(common_scores))
    objects = tuple([object_key] * len(scores_full))
    return mod.DrawItems(scores_full, scores_lao, labels, objects, potency)


def _fixed_bootstrap(ci_lower: float, ci_upper: float):
    """A ``bootstrap_stratified_drop``-shaped fake returning a fixed CI,
    so a test can pin the survivor/collapsed/straddle regime exactly
    without spending real ``N_RESAMPLES`` resamples."""

    def _fake(
        *,
        scores_full: Sequence[float],
        scores_lao: Sequence[float],
        labels: Sequence[int],
        objects: Sequence[str],
        seed: int,
    ) -> mod.BootstrapDropResult:
        del scores_full, scores_lao, labels, objects, seed
        return mod.BootstrapDropResult(
            auc_full_ci=(0.0, 1.0),
            auc_lao_ci=(ci_lower, ci_upper),
            drop_ci=(0.0, 0.0),
            p_drop_le_zero=0.5,
        )

    return _fake


def _fake_permutation(
    scores: Sequence[float], labels: Sequence[int], objects: Sequence[str], *, seed: int
) -> float:
    del scores, labels, objects, seed
    return 0.5


_SURVIVOR_CI = (0.85, 0.95)
_COLLAPSED_CI = (0.50, 0.79)
_STRADDLE_CI = (0.70, 0.85)


def _report_via_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    *,
    good_scores: Sequence[float],
    common_scores: Sequence[float],
    good_scores_lao: Sequence[float] | None = None,
    common_scores_lao: Sequence[float] | None = None,
    potency: float,
    ci: tuple[float, float],
) -> mod.CandidateExternalReport:
    """Build one :class:`CandidateExternalReport` by driving it through the
    *real* §5.1 draw-flag pipeline (:func:`build_candidate_report`) from
    hand-scored items, with bootstrap/permutation replaced by fast fakes.

    This is deliberately not a direct ``CandidateExternalReport(...)``
    construction (that is ``test_decision_rule.py``'s own I-003 coverage) --
    it exercises this issue's combination of the §5 statistics layer with
    §6's judgment rule end to end, per the Goal in
    ``loop/20260907-paper01-g1-external-audit/issues/005.md``.
    """
    monkeypatch.setattr(mod, "bootstrap_stratified_drop", _fixed_bootstrap(*ci))
    monkeypatch.setattr(mod, "permutation_p_stratified", _fake_permutation)
    draws = [
        _draw(
            good_scores=good_scores,
            common_scores=common_scores,
            good_scores_lao=good_scores_lao,
            common_scores_lao=common_scores_lao,
            potency=potency,
        )
    ]
    summary = mod.build_candidate_report(
        key, "embedding", draws, bootstrap_seed=1, permutation_seed=2
    )
    return summary.report


_HIGH_SEP_GOOD = (0.9, 0.85, 0.8, 0.75)
_HIGH_SEP_COMMON = (0.3, 0.25, 0.2, 0.15)
_LOW_SEP_GOOD = (0.5, 0.4, 0.6, 0.3)
_LOW_SEP_COMMON = (0.55, 0.45, 0.65, 0.35)


# =============================================================================
# 005-1..005-7: decide_external combined with the §5 statistics layer
# =============================================================================


def test_ineligible_candidate_is_not_counted_as_collapse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A not-eligible candidate (auc_full below floor) must never enter
    eligible/engaged/collapsed even when its bootstrap CI looks collapsed --
    only a genuinely eligible survivor should decide the verdict.
    """
    ineligible = _report_via_pipeline(
        monkeypatch,
        "X0",
        good_scores=_LOW_SEP_GOOD,
        common_scores=_LOW_SEP_COMMON,
        potency=0.3,
        ci=_COLLAPSED_CI,
    )
    survivor = _report_via_pipeline(
        monkeypatch,
        "X1",
        good_scores=_HIGH_SEP_GOOD,
        common_scores=_HIGH_SEP_COMMON,
        potency=0.3,
        ci=_SURVIVOR_CI,
    )
    assert ineligible.auc_full_at_median_draw < _c.AUC_FLOOR

    result = mod.decide_external(
        [ineligible, survivor], class_sizes={"good": 40, "common": 2087}
    )
    assert result.verdict == "PASS"
    assert "X0" not in result.eligible
    assert "X0" not in result.engaged
    assert "X0" not in result.collapsed
    assert result.survivors == ("X1",)


def test_zero_potency_candidate_does_not_grant_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A potency=0 candidate has auc_lao == auc_full by construction (no
    anchor ever crossed REF_DEDUP to drop), so a naive rule could read it
    as a survivor -- it must not grant PASS: not engaged, excluded from E2.
    """
    zero_potency = _report_via_pipeline(
        monkeypatch,
        "X0",
        good_scores=_HIGH_SEP_GOOD,
        common_scores=_HIGH_SEP_COMMON,
        potency=0.0,
        ci=_SURVIVOR_CI,
    )
    assert zero_potency.audit_not_engaged is True

    result = mod.decide_external(
        [zero_potency], class_sizes={"good": 40, "common": 2087}
    )
    assert result.verdict != "PASS"
    assert result.engaged == ()
    assert result.survivors == ()


def test_all_potency_zero_is_invalid_task_battery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every eligible candidate is potency=0 (audit never fired anywhere)
    -> INVALID_TASK_BATTERY (DA-G1-11): |E2| == 0."""
    reports = [
        _report_via_pipeline(
            monkeypatch,
            key,
            good_scores=_HIGH_SEP_GOOD,
            common_scores=_HIGH_SEP_COMMON,
            potency=0.0,
            ci=_SURVIVOR_CI,
        )
        for key in ("X0", "X1")
    ]
    result = mod.decide_external(reports, class_sizes={"good": 40, "common": 2087})
    assert result.verdict == "INVALID_TASK_BATTERY"
    assert result.engaged == ()


def test_mixed_collapse_with_survivor_is_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """3 engaged-and-collapsed candidates coexist with 1 engaged survivor
    -> PASS (DA-G1-10): a single survivor is sufficient regardless of how
    many other engaged candidates collapsed.
    """
    collapsed = [
        _report_via_pipeline(
            monkeypatch,
            key,
            good_scores=_HIGH_SEP_GOOD,
            common_scores=_HIGH_SEP_COMMON,
            potency=0.4,
            ci=_COLLAPSED_CI,
        )
        for key in ("X0", "X1", "X2")
    ]
    survivor = _report_via_pipeline(
        monkeypatch,
        "X3a",
        good_scores=_HIGH_SEP_GOOD,
        common_scores=_HIGH_SEP_COMMON,
        potency=0.4,
        ci=_SURVIVOR_CI,
    )
    result = mod.decide_external(
        [*collapsed, survivor], class_sizes={"good": 40, "common": 2087}
    )
    assert result.verdict == "PASS"
    assert set(result.collapsed) == {"X0", "X1", "X2"}
    assert result.survivors == ("X3a",)


def test_decide_external_is_not_tautological(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same candidate construction pipeline reaches at least two
    different verdicts depending on the bootstrap CI regime alone -- the
    rule is not a constant function of its input.
    """
    survivor = _report_via_pipeline(
        monkeypatch,
        "X0",
        good_scores=_HIGH_SEP_GOOD,
        common_scores=_HIGH_SEP_COMMON,
        potency=0.3,
        ci=_SURVIVOR_CI,
    )
    collapsed = _report_via_pipeline(
        monkeypatch,
        "X0",
        good_scores=_HIGH_SEP_GOOD,
        common_scores=_HIGH_SEP_COMMON,
        potency=0.3,
        ci=_COLLAPSED_CI,
    )
    pass_result = mod.decide_external(
        [survivor], class_sizes={"good": 40, "common": 2087}
    )
    no_valid_result = mod.decide_external(
        [collapsed], class_sizes={"good": 40, "common": 2087}
    )
    assert pass_result.verdict == "PASS"
    assert no_valid_result.verdict == "NO_VALID_SCORER"
    assert pass_result.verdict != no_valid_result.verdict


def test_lexical_candidate_does_not_drive_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """X5/X6 (lexical) never enter EMBEDDING_FAMILY_EXT: changing a
    lexical candidate's CI/potency in any way must leave the verdict
    unchanged."""
    embedding_report = _report_via_pipeline(
        monkeypatch,
        "X0",
        good_scores=_HIGH_SEP_GOOD,
        common_scores=_HIGH_SEP_COMMON,
        potency=0.3,
        ci=_SURVIVOR_CI,
    )
    lexical_variant_a = _report_via_pipeline(
        monkeypatch,
        "X5",
        good_scores=_HIGH_SEP_GOOD,
        common_scores=_HIGH_SEP_COMMON,
        potency=0.9,
        ci=_COLLAPSED_CI,
    )
    lexical_variant_b = _report_via_pipeline(
        monkeypatch,
        "X6",
        good_scores=_LOW_SEP_GOOD,
        common_scores=_LOW_SEP_COMMON,
        potency=0.0,
        ci=_STRADDLE_CI,
    )
    result_a = mod.decide_external(
        [embedding_report, lexical_variant_a], class_sizes={"good": 40, "common": 2087}
    )
    result_b = mod.decide_external(
        [embedding_report, lexical_variant_b], class_sizes={"good": 40, "common": 2087}
    )
    assert result_a == result_b
    assert result_a.verdict == "PASS"
    assert "X5" not in result_a.eligible
    assert "X6" not in result_b.eligible


def test_small_class_is_invalid_task_battery(monkeypatch: pytest.MonkeyPatch) -> None:
    """A gold class below MIN_CLASS_N forces INVALID_TASK_BATTERY even when
    the candidate itself would otherwise PASS."""
    survivor = _report_via_pipeline(
        monkeypatch,
        "X0",
        good_scores=_HIGH_SEP_GOOD,
        common_scores=_HIGH_SEP_COMMON,
        potency=0.3,
        ci=_SURVIVOR_CI,
    )
    ok_result = mod.decide_external(
        [survivor], class_sizes={"good": 40, "common": 2087}
    )
    deficient_result = mod.decide_external(
        [survivor], class_sizes={"good": mod.MIN_CLASS_N - 1, "common": 2087}
    )
    assert ok_result.verdict == "PASS"
    assert deficient_result.verdict == "INVALID_TASK_BATTERY"


# =============================================================================
# 005-8: two-path import helper
# =============================================================================


def test_dual_path_import_resolves(monkeypatch: pytest.MonkeyPatch) -> None:
    """``resolve_sibling_script`` resolves under both the ERRE-Sandbox
    ``scripts`` namespace-package layout (today's environment) and, with
    the package path forced to fail, the flat paper-repo
    ``analysis/scripts/`` fallback -- both must return a working module.
    """
    pkg_module = mod.resolve_sibling_script(
        "scripts.paper01_fetch_sources", "paper01_fetch_sources"
    )
    assert hasattr(pkg_module, "load_cambridge_table")
    assert hasattr(pkg_module, "cambridge_gold_label")

    real_import_module = importlib.import_module

    def _fail_only_for_package_path(name: str, package: str | None = None) -> object:
        if name == "scripts.paper01_fetch_sources":
            raise ModuleNotFoundError(name)
        return real_import_module(name, package)

    monkeypatch.setattr(
        mod.importlib,  # type: ignore[attr-defined]
        "import_module",
        _fail_only_for_package_path,
    )
    flat_module = mod.resolve_sibling_script(
        "scripts.paper01_fetch_sources", "paper01_fetch_sources"
    )
    assert hasattr(flat_module, "load_cambridge_table")
    assert hasattr(flat_module, "cambridge_gold_label")
    # both resolve to equivalent, independently-callable behaviour
    assert flat_module.CAMBRIDGE_LICENSE == pkg_module.CAMBRIDGE_LICENSE


# =============================================================================
# 005-9: ARM-A draw determinism
# =============================================================================


def test_anchor_draws_are_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same SEED -> identical draw twice. Different SEED -> a different
    30-item draw (design-final.md §7)."""
    pool_size, k = 60, 30

    seed_a = mod.derive_seed("cambridge", "bowl", "SPLIT-BLOCK", "ARM-A")
    draw_1 = mod.anchor_draw_indices(pool_size, k, seed=seed_a, draw_index=5)
    draw_2 = mod.anchor_draw_indices(pool_size, k, seed=seed_a, draw_index=5)
    assert list(draw_1) == list(draw_2)

    monkeypatch.setattr(mod, "SEED", mod.SEED + 1)
    seed_b = mod.derive_seed("cambridge", "bowl", "SPLIT-BLOCK", "ARM-A")
    assert seed_b != seed_a
    draw_3 = mod.anchor_draw_indices(pool_size, k, seed=seed_b, draw_index=5)
    assert list(draw_3) != list(draw_1)


def test_arm_a_draw_texts_reproduces_and_diverges_with_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same property at the ``arm_a_draw_texts`` level (object-scoped
    pool of CambridgeRow, not raw indices)."""
    rows = tuple(
        mod.CambridgeRow(
            row_id=i, object="bowl", text=f"idea {i}", category="common_use_only"
        )
        for i in range(1, 61)
    )
    ctx = mod.ObjectSplitContext(
        object_key="bowl",
        split0=rows,
        split1=(),
        common_pool=rows,
        good_pool=(),
        dedup_common_pool=rows,
        dedup_good_pool=(),
        dropped=False,
        idf={},
        default_idf=1.0,
    )
    texts_1 = mod.arm_a_draw_texts(ctx, 3, corpus="cambridge", scheme="SPLIT-BLOCK")
    texts_2 = mod.arm_a_draw_texts(ctx, 3, corpus="cambridge", scheme="SPLIT-BLOCK")
    assert texts_1 == texts_2
    assert len(texts_1) == 30

    monkeypatch.setattr(mod, "SEED", mod.SEED + 1)
    texts_3 = mod.arm_a_draw_texts(ctx, 3, corpus="cambridge", scheme="SPLIT-BLOCK")
    assert texts_3 != texts_1


# =============================================================================
# stub-encoder fixture for the adapter/orchestration-level tests (005-10..15)
# =============================================================================


_FAKE_ENCODER_DIM = 16
_FAKE_ENCODER_HALF = _FAKE_ENCODER_DIM // 2


def _fake_encoder(texts: Sequence[str]) -> np.ndarray:
    """Deterministic 16-dim stub embedding (pure numpy/hash, no ML model).

    A "good N" text's vector lives entirely in the first half of the
    dimensions, a "common N" text's entirely in the second half -- so
    cross-class cosine similarity is *exactly* 0 (clean discrimination for
    ``auc_stratified``). Within a class, each text gets an independent
    hash-seeded random direction in that half-space; in
    ``_FAKE_ENCODER_HALF``-dim space, independent random unit vectors have
    low pairwise cosine (nowhere near ``REF_DEDUP=0.90``) with very high
    probability, so a class's items stay distinct after greedy dedupe
    rather than collapsing to one representative.
    """
    out = np.zeros((len(texts), _FAKE_ENCODER_DIM), dtype=float)
    for i, t in enumerate(texts):
        rng = np.random.default_rng(abs(hash(t)) % (2**32))
        vec = rng.normal(size=_FAKE_ENCODER_HALF)
        vec = vec / np.linalg.norm(vec)
        if "good" in t:
            out[i, :_FAKE_ENCODER_HALF] = vec
        else:
            out[i, _FAKE_ENCODER_HALF:] = vec
    return out


def _synthetic_rows(
    object_key: str, *, n_good: int, n_common: int, id_offset: int
) -> tuple[mod.CambridgeRow, ...]:
    """Interleaved ids so both classes land in both SPLIT-BLOCK halves."""
    rows: list[mod.CambridgeRow] = []
    row_id = id_offset
    gi = ci = 0
    total = n_good + n_common
    for k in range(total):
        take_good = gi < n_good and (k % 2 == 0 or ci >= n_common)
        if take_good:
            rows.append(
                mod.CambridgeRow(
                    row_id=row_id,
                    object=object_key,
                    text=f"{object_key} good idea {gi}",
                    category="good",
                )
            )
            gi += 1
        else:
            rows.append(
                mod.CambridgeRow(
                    row_id=row_id,
                    object=object_key,
                    text=f"{object_key} common idea {ci}",
                    category="common_use_only",
                )
            )
            ci += 1
        row_id += 1
    return tuple(rows)


@pytest.fixture
def synthetic_cambridge(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, tuple[mod.CambridgeRow, ...]], dict[str, dict[str, np.ndarray]]]:
    """A small synthetic 2-object Cambridge-shaped corpus + stub vmaps,
    with ANCHOR_DRAWS shrunk for test speed and bootstrap/permutation
    replaced by fast fakes so the full ``run_cambridge_split`` orchestration
    runs in well under a second.
    """
    monkeypatch.setattr(mod, "ANCHOR_DRAWS", 6)
    monkeypatch.setattr(
        mod, "bootstrap_stratified_drop", _fixed_bootstrap(*_SURVIVOR_CI)
    )
    monkeypatch.setattr(mod, "permutation_p_stratified", _fake_permutation)

    rows_by_object = {
        "bowl": _synthetic_rows("bowl", n_good=20, n_common=60, id_offset=1),
        "paperclip": _synthetic_rows(
            "paperclip", n_good=20, n_common=60, id_offset=1000
        ),
    }
    encoders = {
        "mpnet": _fake_encoder,
        "MiniLM-L6-v2": _fake_encoder,
        "e5-small-v2": _fake_encoder,
        "bge-small-en-v1.5": _fake_encoder,
    }
    vmaps = mod.embed_all_texts(rows_by_object, encoders)
    return rows_by_object, vmaps


# =============================================================================
# 005-10 / 005-14: verdict is ARM-A only; NC does not drive it
# =============================================================================


def test_verdict_uses_arm_a_median_only(
    synthetic_cambridge: tuple[
        dict[str, tuple[mod.CambridgeRow, ...]], dict[str, dict[str, np.ndarray]]
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Degrading ARM-B/ARM-D to an empty anchor set leaves the verdict
    byte-identical; only ``build_candidate_report`` calls (the
    bootstrapped, verdict-eligible path) are counted, and there are
    exactly ``len(EMBEDDING_FAMILY_EXT)`` of them -- ARM-B/D/NC never take
    that path at all.
    """
    rows_by_object, vmaps = synthetic_cambridge

    build_calls: list[str] = []
    real_build = mod.build_candidate_report

    def _spy_build(
        key: str,
        family: str,
        draws: Sequence[mod.DrawItems],
        *,
        bootstrap_seed: int,
        permutation_seed: int,
    ) -> mod.CandidateStatisticalSummary:
        build_calls.append(key)
        return real_build(
            key,
            family,
            draws,
            bootstrap_seed=bootstrap_seed,
            permutation_seed=permutation_seed,
        )

    monkeypatch.setattr(mod, "build_candidate_report", _spy_build)

    baseline = mod.run_cambridge_split(rows_by_object, "SPLIT-BLOCK", vmaps)
    calls_after_baseline = list(build_calls)

    monkeypatch.setattr(mod, "arm_b_texts", lambda ctx: ())  # noqa: ARG005
    monkeypatch.setattr(mod, "arm_d_texts", lambda ctx, mpnet_vmap: ())  # noqa: ARG005
    build_calls.clear()
    degraded = mod.run_cambridge_split(rows_by_object, "SPLIT-BLOCK", vmaps)

    assert degraded["verdict"] == baseline["verdict"]
    assert degraded["candidates"] == baseline["candidates"]
    assert degraded["sensitivity"] != baseline["sensitivity"]
    assert set(calls_after_baseline) == set(mod.EMBEDDING_FAMILY_EXT)
    assert len(calls_after_baseline) == len(mod.EMBEDDING_FAMILY_EXT)


def test_negative_controls_do_not_drive_verdict(
    synthetic_cambridge: tuple[
        dict[str, tuple[mod.CambridgeRow, ...]], dict[str, dict[str, np.ndarray]]
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Degrading NC-1/NC-2 to an empty anchor set leaves the verdict
    byte-identical; ``negative_controls`` itself does change."""
    rows_by_object, vmaps = synthetic_cambridge

    baseline = mod.run_cambridge_split(rows_by_object, "SPLIT-BLOCK", vmaps)

    monkeypatch.setattr(mod, "nc1_texts", lambda partner_ctx, *, corpus, scheme: ())  # noqa: ARG005
    monkeypatch.setattr(mod, "nc2_texts", lambda ctx, *, corpus, scheme: ())  # noqa: ARG005
    degraded = mod.run_cambridge_split(rows_by_object, "SPLIT-BLOCK", vmaps)

    assert degraded["verdict"] == baseline["verdict"]
    assert degraded["candidates"] == baseline["candidates"]
    assert degraded["negative_controls"] != baseline["negative_controls"]


# =============================================================================
# 005-11: object dropped when pool too small
# =============================================================================


def test_object_dropped_when_pool_too_small() -> None:
    """|R_o| < N_R_MIN after dedupe -> the object is dropped (recorded,
    excluded from active_objects/class_sizes), pushed through the same
    build_object_split_context used in production -- not a hand-set
    boolean.
    """
    tiny_rows = (
        mod.CambridgeRow(
            row_id=1, object="bowl", text="only common a", category="common_use_only"
        ),
        mod.CambridgeRow(
            row_id=2, object="bowl", text="only common b", category="common_use_only"
        ),
        mod.CambridgeRow(row_id=3, object="bowl", text="only good a", category="good"),
        mod.CambridgeRow(row_id=4, object="bowl", text="only good b", category="good"),
    )
    # split0 gets both rows (id ascending, first half of 4 = ids 1,2); pool
    # has 1 common item after the SPLIT-BLOCK partition -- well under
    # N_R_MIN=8.
    vmap = {r.text: np.array([1.0, 0.0]) for r in tiny_rows}
    ctx = mod.build_object_split_context("bowl", tiny_rows, "SPLIT-BLOCK", vmap)
    assert len(ctx.dedup_common_pool) < _c.N_R_MIN
    assert ctx.dropped is True


def test_active_object_is_not_dropped() -> None:
    """The mirror case: a pool with >= N_R_MIN distinct (non-near-dup)
    common texts is *not* dropped -- proves the gate is exercised both
    ways, not vacuously true.
    """
    rows: list[mod.CambridgeRow] = []
    vmap: dict[str, np.ndarray] = {}
    for i in range(20):
        text = f"common idea {i}"
        rows.append(
            mod.CambridgeRow(
                row_id=i + 1, object="bowl", text=text, category="common_use_only"
            )
        )
        # high-dim random unit vectors: pairwise cosine stays well under
        # REF_DEDUP=0.90 with high probability, so the pool does not
        # collapse to a handful of near-duplicates the way a 2D spread
        # would (adjacent points on a circle are too close together).
        rng = np.random.default_rng(1000 + i)
        v = rng.normal(size=16)
        vmap[text] = v / np.linalg.norm(v)
    ctx = mod.build_object_split_context("bowl", tuple(rows), "SPLIT-BLOCK", vmap)
    assert len(ctx.dedup_common_pool) >= _c.N_R_MIN
    assert ctx.dropped is False


def _build_all_common_context(n_rows: int) -> mod.ObjectSplitContext:
    """SPLIT-BLOCK, all-``common_use_only`` rows, well-separated (high-dim
    random) embeddings so dedupe keeps every row: ``split0`` (and hence
    ``dedup_common_pool``) lands at exactly ``n_rows // 2`` items."""
    rows: list[mod.CambridgeRow] = []
    vmap: dict[str, np.ndarray] = {}
    for i in range(n_rows):
        text = f"common idea {i}"
        rows.append(
            mod.CambridgeRow(
                row_id=i + 1, object="bowl", text=text, category="common_use_only"
            )
        )
        rng = np.random.default_rng(2000 + i)
        v = rng.normal(size=16)
        vmap[text] = v / np.linalg.norm(v)
    return mod.build_object_split_context("bowl", tuple(rows), "SPLIT-BLOCK", vmap)


def test_object_at_min_pool_boundary_is_not_dropped() -> None:
    """Pins the strict ``<`` in ``|R_o| < N_R_MIN`` at the exact boundary:
    a pool of exactly ``N_R_MIN`` (8) survivors is *not* dropped, a pool of
    ``N_R_MIN - 1`` (7) *is* -- kills the ``<=`` off-by-one mutant that
    ``test_active_object_is_not_dropped``/``test_object_dropped_when_pool_
    too_small`` (built with pools far from the boundary) do not reach.
    """
    at_boundary = _build_all_common_context(2 * _c.N_R_MIN)
    assert len(at_boundary.dedup_common_pool) == _c.N_R_MIN
    assert at_boundary.dropped is False

    below_boundary = _build_all_common_context(2 * _c.N_R_MIN - 2)
    assert len(below_boundary.dedup_common_pool) == _c.N_R_MIN - 1
    assert below_boundary.dropped is True


# =============================================================================
# 005-12: NC-1 cyclic-shift pairing determinism
# =============================================================================


def test_nc1_object_pairing_is_deterministic() -> None:
    """NC-1's object -> object' pairing is a deterministic cyclic shift of
    the frozen object order (Cambridge's 2-object case: a clean swap)."""
    assert mod.nc1_partner_object(mod.CAMBRIDGE_OBJECTS, "bowl") == "paperclip"
    assert mod.nc1_partner_object(mod.CAMBRIDGE_OBJECTS, "paperclip") == "bowl"
    # deterministic: calling again gives the identical answer
    assert mod.nc1_partner_object(mod.CAMBRIDGE_OBJECTS, "bowl") == "paperclip"

    # generalises beyond 2 objects (I-006's Ocsai reuse): the shift wraps.
    three = ("a", "b", "c")
    assert mod.nc1_partner_object(three, "a") == "b"
    assert mod.nc1_partner_object(three, "b") == "c"
    assert mod.nc1_partner_object(three, "c") == "a"


# =============================================================================
# 005-13: NC-2 reverses the discrimination direction
# =============================================================================


def test_nc2_reverses_discrimination_direction() -> None:
    """When the anchor is the object's own *good* pool (NC-2) instead of
    its common pool (ARM-A-style), the good/common discrimination
    direction flips: good items (near the good anchor) score *lower*
    rarity than common items (far from it), so AUC drops below what the
    common-anchored version gives.
    """
    good_texts = [f"good {i}" for i in range(10)]
    common_texts = [f"common {i}" for i in range(10)]
    rows = tuple(
        mod.CambridgeRow(row_id=i + 1, object="bowl", text=t, category="good")
        for i, t in enumerate(good_texts)
    ) + tuple(
        mod.CambridgeRow(
            row_id=100 + i, object="bowl", text=t, category="common_use_only"
        )
        for i, t in enumerate(common_texts)
    )
    vmap = dict(
        zip(
            good_texts + common_texts,
            _fake_encoder(good_texts + common_texts),
            strict=True,
        )
    )

    # common-anchored (ARM-A-style): rarity should discriminate good > common
    common_anchor = {"bowl": tuple(common_texts)}
    common_scored = mod.score_rows_for_draw(
        rows,
        anchor_texts_by_object=common_anchor,
        vmaps={"mpnet": vmap},
        idf_by_object={},
    )
    auc_common_anchor = mod.auc_stratified(
        common_scored["X0"].scores_full,
        common_scored["X0"].labels,
        common_scored["X0"].objects,
    )

    # good-anchored (NC-2): direction should reverse
    good_anchor = {"bowl": tuple(good_texts)}
    good_scored = mod.score_rows_for_draw(
        rows,
        anchor_texts_by_object=good_anchor,
        vmaps={"mpnet": vmap},
        idf_by_object={},
    )
    auc_good_anchor = mod.auc_stratified(
        good_scored["X0"].scores_full,
        good_scored["X0"].labels,
        good_scored["X0"].objects,
    )

    assert auc_common_anchor > 0.5
    assert auc_good_anchor < 0.5
    assert auc_good_anchor < auc_common_anchor


# =============================================================================
# 005-15: both split schemes are reported
# =============================================================================


def test_both_split_schemes_reported(
    synthetic_cambridge: tuple[
        dict[str, tuple[mod.CambridgeRow, ...]], dict[str, dict[str, np.ndarray]]
    ],
) -> None:
    """SPLIT-BLOCK and SPLIT-PARITY both produce an independent report with
    a verdict, driven through the same ``run_cambridge_split`` used for
    the real audit -- and their underlying row partitions actually differ.
    """
    rows_by_object, vmaps = synthetic_cambridge

    block = mod.run_cambridge_split(rows_by_object, "SPLIT-BLOCK", vmaps)
    parity = mod.run_cambridge_split(rows_by_object, "SPLIT-PARITY", vmaps)

    assert block["scheme"] == "SPLIT-BLOCK"
    assert parity["scheme"] == "SPLIT-PARITY"
    assert block["verdict"]["verdict"] in mod.VERDICT_ENUM
    assert parity["verdict"]["verdict"] in mod.VERDICT_ENUM

    # the two schemes assign rows to split0/split1 differently
    block_split0, _ = mod.split_cambridge_rows(rows_by_object["bowl"], "SPLIT-BLOCK")
    parity_split0, _ = mod.split_cambridge_rows(rows_by_object["bowl"], "SPLIT-PARITY")
    assert {r.row_id for r in block_split0} != {r.row_id for r in parity_split0}

    # SPLIT_SCHEMES itself declares exactly these two, BLOCK primary
    scheme_keys = {s.key for s in mod.SPLIT_SCHEMES}
    assert scheme_keys == {"SPLIT-BLOCK", "SPLIT-PARITY"}


# =============================================================================
# 005-16: AdversarialItem.object / anchor-dict key alignment
# =============================================================================


def test_object_key_alignment() -> None:
    """AdversarialItem.object (stamped by to_adversarial_items) is exactly
    the string used as the anchor dict's key -- a mismatch silently zeros
    every rarity (AUC collapses to 0.5) rather than raising, so this pins
    both the positive (aligned) and negative (mismatched) behaviour.
    """
    rows = (
        mod.CambridgeRow(row_id=1, object="bowl", text="a bowl idea", category="good"),
    )
    items = mod.to_adversarial_items(rows)
    assert items[0].object == "bowl"
    assert {item.object for item in items} == {r.object for r in rows}

    vmap = {
        "anchor common": np.array([0.0, 1.0]),
        "a bowl idea": np.array([0.99, 0.14106736]),
    }
    for key, value in vmap.items():
        vmap[key] = value / np.linalg.norm(value)

    anchor_texts_by_object = {"bowl": ("anchor common",)}
    candidate = mod.make_embed_candidate(
        "X0", "x0", vmap, anchor_texts_by_object, agg="max"
    )

    aligned = candidate.rarity(items[0].object, items[0].text, leave_anchor_out=False)
    mismatched = candidate.rarity("paperclip", items[0].text, leave_anchor_out=False)

    assert aligned > 0.0
    assert mismatched == 0.0


# =============================================================================
# real xlsx end-to-end (eval marker, extras-only)
# =============================================================================


@pytest.mark.eval
def test_cambridge_end_to_end_real_xlsx(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tiny (small-ANCHOR_DRAWS) real xlsx -> verdict smoke test.

    Skips when ``[eval]`` extras (``sentence_transformers``) or the raw
    Cambridge ``.xlsx`` files (fetched by I-001) are unavailable -- CI
    never exercises this path.
    """
    pytest.importorskip("sentence_transformers")
    if not (mod.CAMBRIDGE_RAW_DIR / "bowl AUT dataset.xlsx").exists():
        pytest.skip("Cambridge raw .xlsx not present locally (run I-001 fetch first)")

    monkeypatch.setattr(mod, "ANCHOR_DRAWS", 2)
    result = mod.run_cambridge_audit()

    assert result["corpus"] == "cambridge"
    for scheme_key in ("SPLIT-BLOCK", "SPLIT-PARITY"):
        assert scheme_key in result["splits"]
        assert result["splits"][scheme_key]["verdict"]["verdict"] in mod.VERDICT_ENUM

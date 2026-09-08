"""Tests for the §2 fidelity pin in scripts/paper01_external_audit.py (I-007).

design-final.md §2 / §7 (DA-G1-16) and loop/20260907-paper01-g1-external-audit/
issues/007.md are the single sources of truth for the procedures under test.

The fidelity pin proves the *external* harness's own rarity-scoring wiring
(``make_embed_candidate``, the same object-keyed function every Cambridge/
Ocsai candidate is built through) reproduces the **sealed**
``experiments/20260701-es4-scorer-diag/diagnostic.json`` rows exactly when
fed the *internal* anchor/gold data. Without this, "the external corpora
did not collapse" cannot be distinguished from "a different instrument was
applied".

Per the issue's Test Plan:

* 007-1 (fast pin, C4) and 007-5 (near-dup asymmetry, C0) are
  ``@pytest.mark.eval`` + ``pytest.importorskip("sentence_transformers")``
  -- deselected by default, run only in the real evaluation pass.
* 007-2 (C0's exact AUC reproduction) is deliberately **not** a pytest
  test at all -- ``run_diagnostic``'s reconstruction of the incumbent
  ``R_object`` needs Phase A's ~800 REF generations and takes 1-2 minutes
  on CPU, so it is checked only via ``python scripts/paper01_external_audit.py
  --fidelity`` (a real invocation, exit code asserted operationally).
* 007-3 pushes a deliberately-off observation through the *real*
  ``fidelity_candidate_matches`` / ``main`` --fidelity pipeline, not a
  hand-built fixture asserting its own fields -- only the (slow,
  sentence-transformers-dependent) candidate-construction step is stubbed.
* 007-4 is a `git status --porcelain` check that the sealed
  ``experiments/20260701-es4-scorer-diag`` tree is untouched.
"""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

import numpy as np
import pytest
from scripts import paper01_external_audit as mod

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

# =============================================================================
# 007-1 — fast pin (C4 curated-only), encoder-dependent
# =============================================================================


@pytest.mark.eval
def test_fidelity_internal_c4_curated_reference() -> None:
    """AC 007-1: C4 (curated-only reference) reproduces diagnostic.json exactly.

    Fast: no Phase A artifact needed, only the curated ``common_uses.yaml``
    (~160 strings) + the 41-item gold pair are embedded.
    """
    pytest.importorskip("sentence_transformers")
    mpnet = mod._diag.make_encoder("sentence-transformers/all-mpnet-base-v2")
    if mpnet is None:
        pytest.skip("mpnet encoder unavailable offline")

    result = mod.measure_c4_fidelity(mpnet)

    assert result.auc_full == mod.C4_EXPECTED_AUC_FULL
    assert result.auc_lao == mod.C4_EXPECTED_AUC_LAO
    assert result.matches is True


# =============================================================================
# 007-3 — mismatch exits non-zero, encoder-independent
# =============================================================================


def test_fidelity_mismatch_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """AC 007-3: a deliberately-off observation exits non-zero via `main`.

    Encoder-independent: only ``measure_c4_fidelity``/``measure_c0_fidelity``
    (the slow, sentence-transformers-dependent candidate construction) are
    stubbed. The *judgment* function (``fidelity_candidate_matches``) and
    the CLI exit-code wiring (``main`` -> ``write_fidelity`` ->
    ``run_fidelity``) run completely unmodified -- issue 007: "実際の照合
    関数に期待値ずれの入力を通して非ゼロ exit になることを示す".
    """

    def _stub_encoder(model_id: str) -> object:  # noqa: ARG001
        return lambda texts: np.zeros((len(texts), 2), dtype=float)

    def _fake_c4(mpnet: object) -> mod.FidelityCandidateResult:  # noqa: ARG001
        wrong_full = mod.C4_EXPECTED_AUC_FULL - 0.5  # deliberately off-target
        matches = mod.fidelity_candidate_matches(
            wrong_full,
            mod.C4_EXPECTED_AUC_LAO,
            expected_full=mod.C4_EXPECTED_AUC_FULL,
            expected_lao=mod.C4_EXPECTED_AUC_LAO,
        )
        assert matches is False  # the real judgment function must catch this
        return mod.FidelityCandidateResult(
            key="C4-mpnet-max-curated",
            auc_full=wrong_full,
            auc_lao=mod.C4_EXPECTED_AUC_LAO,
            expected_auc_full=mod.C4_EXPECTED_AUC_FULL,
            expected_auc_lao=mod.C4_EXPECTED_AUC_LAO,
            matches=matches,
            auc_membership=0.5,
            near_dup_good=0.0,
            near_dup_common=0.5,
            potency=0.1,
        )

    def _fake_c0(
        mpnet: object,  # noqa: ARG001
        run_dir: Path = mod.PHASE_A_RUN_DIR,  # noqa: ARG001
    ) -> mod.FidelityCandidateResult:
        matches = mod.fidelity_candidate_matches(
            mod.C0_EXPECTED_AUC_FULL,
            mod.C0_EXPECTED_AUC_LAO,
            expected_full=mod.C0_EXPECTED_AUC_FULL,
            expected_lao=mod.C0_EXPECTED_AUC_LAO,
        )
        assert matches is True  # C0 side is a correct control; only C4 is wrong
        return mod.FidelityCandidateResult(
            key="C0-mpnet-max-full",
            auc_full=mod.C0_EXPECTED_AUC_FULL,
            auc_lao=mod.C0_EXPECTED_AUC_LAO,
            expected_auc_full=mod.C0_EXPECTED_AUC_FULL,
            expected_auc_lao=mod.C0_EXPECTED_AUC_LAO,
            matches=matches,
            auc_membership=0.75,
            near_dup_good=0.0,
            near_dup_common=0.5,
            potency=0.195,
        )

    monkeypatch.setattr(mod._diag, "make_encoder", _stub_encoder)
    monkeypatch.setattr(mod, "measure_c4_fidelity", _fake_c4)
    monkeypatch.setattr(mod, "measure_c0_fidelity", _fake_c0)
    fidelity_path = tmp_path / "fidelity.json"
    monkeypatch.setattr(mod, "FIDELITY_PATH", fidelity_path)

    exit_code = mod.main(["--fidelity"])

    assert exit_code != 0
    written = json.loads(fidelity_path.read_text(encoding="utf-8"))
    assert written["all_match"] is False
    assert written["c4"]["matches"] is False
    assert written["c0"]["matches"] is True


def test_fidelity_match_exits_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Control for 007-3: the same pipeline, both candidates matching, exits 0.

    Without this, a mutant that always returns non-zero from ``main``
    regardless of ``all_match`` would still pass 007-3's assertion alone.
    """

    def _stub_encoder(model_id: str) -> object:  # noqa: ARG001
        return lambda texts: np.zeros((len(texts), 2), dtype=float)

    def _fake_c4(mpnet: object) -> mod.FidelityCandidateResult:  # noqa: ARG001
        return mod.FidelityCandidateResult(
            key="C4-mpnet-max-curated",
            auc_full=mod.C4_EXPECTED_AUC_FULL,
            auc_lao=mod.C4_EXPECTED_AUC_LAO,
            expected_auc_full=mod.C4_EXPECTED_AUC_FULL,
            expected_auc_lao=mod.C4_EXPECTED_AUC_LAO,
            matches=True,
            auc_membership=0.5,
            near_dup_good=0.0,
            near_dup_common=0.4375,
            potency=0.171,
        )

    def _fake_c0(
        mpnet: object,  # noqa: ARG001
        run_dir: Path = mod.PHASE_A_RUN_DIR,  # noqa: ARG001
    ) -> mod.FidelityCandidateResult:
        return mod.FidelityCandidateResult(
            key="C0-mpnet-max-full",
            auc_full=mod.C0_EXPECTED_AUC_FULL,
            auc_lao=mod.C0_EXPECTED_AUC_LAO,
            expected_auc_full=mod.C0_EXPECTED_AUC_FULL,
            expected_auc_lao=mod.C0_EXPECTED_AUC_LAO,
            matches=True,
            auc_membership=0.75,
            near_dup_good=0.0,
            near_dup_common=0.5,
            potency=0.195,
        )

    monkeypatch.setattr(mod._diag, "make_encoder", _stub_encoder)
    monkeypatch.setattr(mod, "measure_c4_fidelity", _fake_c4)
    monkeypatch.setattr(mod, "measure_c0_fidelity", _fake_c0)
    fidelity_path = tmp_path / "fidelity.json"
    monkeypatch.setattr(mod, "FIDELITY_PATH", fidelity_path)

    exit_code = mod.main(["--fidelity"])

    assert exit_code == 0
    written = json.loads(fidelity_path.read_text(encoding="utf-8"))
    assert written["all_match"] is True


# =============================================================================
# 007-4 — sealed diagnostic.json is untouched, encoder-independent
# =============================================================================


def test_sealed_diagnostic_json_is_unmodified() -> None:
    """AC 007-4: the sealed `experiments/20260701-es4-scorer-diag` tree has
    no working-tree changes -- this issue must never regenerate it."""
    result = subprocess.run(
        [  # noqa: S607
            "git",
            "status",
            "--porcelain",
            "experiments/20260701-es4-scorer-diag",
        ],
        cwd=mod.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == ""


# =============================================================================
# 007-5 — near-dup asymmetry (C0), encoder-dependent
# =============================================================================


@pytest.mark.eval
def test_internal_near_dup_asymmetry() -> None:
    """AC 007-5: C0's near-dup rate reproduces the good/common asymmetry.

    design-final.md §2: near-dup rate for C0 is good 0.000 / common 0.500.
    """
    pytest.importorskip("sentence_transformers")
    if not (mod.PHASE_A_RUN_DIR / "generations.jsonl").exists():
        pytest.skip("Phase A artifact not present locally")
    mpnet = mod._diag.make_encoder("sentence-transformers/all-mpnet-base-v2")
    if mpnet is None:
        pytest.skip("mpnet encoder unavailable offline")

    result = mod.measure_c0_fidelity(mpnet)

    assert result.near_dup_good == 0.0
    assert result.near_dup_common == 0.5


@pytest.mark.eval
def test_internal_dropped_anchor_fraction_c0_and_c4() -> None:
    """Orchestrator follow-up (2026-09-08): the internal counterpart of the
    external report's ``dropped_anchor_fraction_at_median_draw``, so the
    internal-vs-external asymmetry/drop comparison is not one-sided.

    Pins both C4 (fast) and C0 (heavy) against the values this same session
    measured via a real ``--fidelity`` run (``results/fidelity.json``:
    ``c4.dropped_anchor_fraction=0.017073``,
    ``c0.dropped_anchor_fraction=0.012828``) -- a regression pin, not a
    tune-to-pass: :func:`fidelity_candidate_matches` (the actual go/no-go)
    never reads this field, only ``auc_full``/``auc_lao``.
    """
    pytest.importorskip("sentence_transformers")
    if not (mod.PHASE_A_RUN_DIR / "generations.jsonl").exists():
        pytest.skip("Phase A artifact not present locally")
    mpnet = mod._diag.make_encoder("sentence-transformers/all-mpnet-base-v2")
    if mpnet is None:
        pytest.skip("mpnet encoder unavailable offline")

    c4 = mod.measure_c4_fidelity(mpnet)
    c0 = mod.measure_c0_fidelity(mpnet)

    assert c4.dropped_anchor_fraction == pytest.approx(0.017073, abs=1e-6)
    assert c0.dropped_anchor_fraction == pytest.approx(0.012828, abs=1e-6)
    # sanity: distinct from 0.0 (the "no vmap passed" default) and from each
    # other, so a mutant that always returns the default or swaps C0/C4
    # would be caught.
    assert c4.dropped_anchor_fraction != 0.0
    assert c0.dropped_anchor_fraction != 0.0
    assert c4.dropped_anchor_fraction != pytest.approx(c0.dropped_anchor_fraction)


# =============================================================================
# encoder-independent unit tests for the smaller building blocks
# =============================================================================


def test_fidelity_membership_and_potency_dropped_fraction_needs_both_args() -> None:
    """``dropped_anchor_fraction`` only computes when *both* ``vmap`` and
    ``anchor_texts_by_object`` are supplied; either omitted (the default for
    every pre-2026-09-08 caller) reports the neutral ``0.0`` rather than
    raising -- and supplying both over a hand-built fixture with a known
    near-dup produces a real, non-zero value.
    """
    import numpy as np

    class _FakeGold:
        def __init__(self, text: str, obj: str, category: str) -> None:
            self.text = text
            self.object = obj
            self.category = category

    class _FakeCandidate:
        def rarity(self, object_id: str, text: str, *, leave_anchor_out: bool) -> float:
            del object_id, text, leave_anchor_out
            return 0.5  # constant: irrelevant to this test's assertions

    gold_pair = (
        _FakeGold("good item", "bowl", "good"),
        _FakeGold("common item", "bowl", "common_use_only"),
    )
    candidate = _FakeCandidate()

    # neither vmap nor anchor_texts_by_object -> neutral default
    result_neither = mod.fidelity_membership_and_potency(candidate, gold_pair)
    assert result_neither[4] == 0.0

    # both provided, with a real near-dup anchor for "common item" only --
    # 3D so "good item"/"common item's own anchor"/"unrelated anchor" can
    # all be made pairwise orthogonal except the one deliberate near-dup.
    vmap = {
        "good item": np.array([1.0, 0.0, 0.0]),
        "common item": np.array([0.0, 1.0, 0.0]),
        "common item's own anchor": np.array([0.0, 1.0, 0.0]),  # cos=1.0 w/ common
        "unrelated anchor": np.array([0.0, 0.0, 1.0]),  # cos=0.0 w/ both
    }
    anchor_texts_by_object = {"bowl": ("common item's own anchor", "unrelated anchor")}
    result_both = mod.fidelity_membership_and_potency(
        candidate,
        gold_pair,
        vmap=vmap,
        anchor_texts_by_object=anchor_texts_by_object,
    )
    # "good item" drops 0/2 anchors (0.0), "common item" drops 1/2 (0.5) ->
    # mean = 0.25.
    assert result_both[4] == pytest.approx(0.25)


def test_build_c4_fidelity_candidate_delegates_to_shared_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``build_c4_fidelity_candidate`` (the public/tested entry point) is a
    thin wrapper over :func:`_c4_fidelity_context` -- pinned via a spy so a
    future edit cannot silently reintroduce a *second*, independent
    embedding pass duplicating the one ``measure_c4_fidelity`` already
    shares with it."""
    sentinel_candidate = object()
    calls: list[object] = []

    def _fake_context(mpnet: object) -> tuple[object, dict, dict]:
        calls.append(mpnet)
        return sentinel_candidate, {}, {}

    monkeypatch.setattr(mod, "_c4_fidelity_context", _fake_context)
    mpnet_arg = object()

    result = mod.build_c4_fidelity_candidate(mpnet_arg)

    assert result is sentinel_candidate
    assert calls == [mpnet_arg]


def test_build_c0_fidelity_candidate_delegates_to_shared_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same guard as the C4 case, for :func:`_c0_fidelity_context`."""
    sentinel_candidate = object()
    calls: list[tuple[object, object]] = []

    def _fake_context(mpnet: object, run_dir: object) -> tuple[object, dict, dict]:
        calls.append((mpnet, run_dir))
        return sentinel_candidate, {}, {}

    monkeypatch.setattr(mod, "_c0_fidelity_context", _fake_context)
    mpnet_arg = object()
    run_dir_arg = object()

    result = mod.build_c0_fidelity_candidate(mpnet_arg, run_dir_arg)

    assert result is sentinel_candidate
    assert calls == [(mpnet_arg, run_dir_arg)]


def test_fidelity_candidate_matches_requires_both_statistics() -> None:
    """Both auc_full and auc_lao must match; either alone is not enough."""
    assert mod.fidelity_candidate_matches(
        0.99, 0.755, expected_full=0.99, expected_lao=0.755
    )
    assert not mod.fidelity_candidate_matches(
        0.98, 0.755, expected_full=0.99, expected_lao=0.755
    )
    assert not mod.fidelity_candidate_matches(
        0.99, 0.754, expected_full=0.99, expected_lao=0.755
    )
    assert not mod.fidelity_candidate_matches(
        0.98, 0.754, expected_full=0.99, expected_lao=0.755
    )


def test_fidelity_candidate_matches_no_tolerance_band() -> None:
    """DA-G1-16 "完全一致で再現": a value one float ULP off does not match."""
    just_off = np.nextafter(0.99, 1.0)
    assert just_off != 0.99
    assert not mod.fidelity_candidate_matches(
        just_off, 0.755, expected_full=0.99, expected_lao=0.755
    )


def test_expected_constants_are_frozen_to_the_sealed_diagnostic_json() -> None:
    """Mutation target ③: the four committed values must not drift.

    Pins the literal ``experiments/20260701-es4-scorer-diag/diagnostic.json``
    rows (design-final.md §2) directly, independent of any encoder call --
    the eval-marked reproduction tests catch a mutation here too (their
    computed AUC would then disagree with the mutated constant), but this
    is the fast, always-run guard.
    """
    assert mod.C0_EXPECTED_AUC_FULL == 0.99
    assert mod.C0_EXPECTED_AUC_LAO == 0.755
    assert mod.C4_EXPECTED_AUC_FULL == 0.995
    assert mod.C4_EXPECTED_AUC_LAO == 0.705


def test_measure_c4_fidelity_does_not_swap_full_and_lao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation target ④: "auc_full と auc_lao の照合を取り違える".

    Encoder-independent: candidate construction and
    ``_diag.gold_good_vs_common`` are stubbed to return two *distinct*
    values, and a spy on ``fidelity_candidate_matches`` captures exactly
    what ``measure_c4_fidelity`` passed it -- a swap at that call site is
    detectable without an embedding model.
    """
    captured: dict[str, float] = {}

    def _spy_matches(
        auc_full: float, auc_lao: float, *, expected_full: float, expected_lao: float
    ) -> bool:
        captured["auc_full"] = auc_full
        captured["auc_lao"] = auc_lao
        captured["expected_full"] = expected_full
        captured["expected_lao"] = expected_lao
        return True

    class _FakeGoldResult:
        auc_full = 0.111
        auc_leave_anchor_out = 0.222

    monkeypatch.setattr(
        mod,
        "_c4_fidelity_context",
        lambda mpnet: (object(), {}, {}),  # noqa: ARG005
    )
    monkeypatch.setattr(mod, "fidelity_gold_pair", lambda: ())
    monkeypatch.setattr(
        mod._diag,
        "gold_good_vs_common",
        lambda *a, **k: _FakeGoldResult(),  # noqa: ARG005
    )
    monkeypatch.setattr(
        mod,
        "fidelity_membership_and_potency",
        lambda *a, **k: (0.0, 0.0, 0.0, 0.0, 0.0),  # noqa: ARG005
    )
    monkeypatch.setattr(mod, "fidelity_candidate_matches", _spy_matches)

    mod.measure_c4_fidelity(object())

    assert captured["auc_full"] == 0.111
    assert captured["auc_lao"] == 0.222
    assert captured["expected_full"] == mod.C4_EXPECTED_AUC_FULL
    assert captured["expected_lao"] == mod.C4_EXPECTED_AUC_LAO


def test_measure_c0_fidelity_does_not_swap_full_and_lao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation target ④, the C0 (heavy pin) call site -- same guard as
    ``test_measure_c4_fidelity_does_not_swap_full_and_lao``, independent
    code location."""
    captured: dict[str, float] = {}

    def _spy_matches(
        auc_full: float, auc_lao: float, *, expected_full: float, expected_lao: float
    ) -> bool:
        captured["auc_full"] = auc_full
        captured["auc_lao"] = auc_lao
        captured["expected_full"] = expected_full
        captured["expected_lao"] = expected_lao
        return True

    class _FakeGoldResult:
        auc_full = 0.333
        auc_leave_anchor_out = 0.444

    monkeypatch.setattr(
        mod,
        "_c0_fidelity_context",
        lambda mpnet, run_dir: (object(), {}, {}),  # noqa: ARG005
    )
    monkeypatch.setattr(mod, "fidelity_gold_pair", lambda: ())
    monkeypatch.setattr(
        mod._diag,
        "gold_good_vs_common",
        lambda *a, **k: _FakeGoldResult(),  # noqa: ARG005
    )
    monkeypatch.setattr(
        mod,
        "fidelity_membership_and_potency",
        lambda *a, **k: (0.0, 0.0, 0.0, 0.0, 0.0),  # noqa: ARG005
    )
    monkeypatch.setattr(mod, "fidelity_candidate_matches", _spy_matches)

    mod.measure_c0_fidelity(object())

    assert captured["auc_full"] == 0.333
    assert captured["auc_lao"] == 0.444
    assert captured["expected_full"] == mod.C0_EXPECTED_AUC_FULL
    assert captured["expected_lao"] == mod.C0_EXPECTED_AUC_LAO


def test_fidelity_gold_pair_is_41_good_and_common_use_only() -> None:
    """Sanity: the internal gold pair used by the pin is the 41 good/
    common_use_only items design-final.md §2 cites, no other category."""
    gold_pair: Sequence[object] = mod.fidelity_gold_pair()
    assert len(gold_pair) == 41  # design-final.md §2's frozen count
    categories = {g.category for g in gold_pair}  # type: ignore[attr-defined]
    assert categories == {"good", "common_use_only"}


def test_build_c0_fidelity_candidate_raises_when_phase_a_missing(
    tmp_path: Path,
) -> None:
    """Issue 007 Stop Condition: a missing Phase A artifact must raise, not
    silently fall back to something else."""
    missing_dir = tmp_path / "does-not-exist"

    with pytest.raises(FileNotFoundError):
        mod.build_c0_fidelity_candidate(
            lambda texts: np.zeros((len(texts), 2), dtype=float), missing_dir
        )


def test_main_no_args_keeps_pre_i007_default_behaviour(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Issue 007: "引数なしのときの既定動作は既存互換を保つこと".

    No flag at all still writes SEED/config.json/env.md (only), same as
    before this issue's CLI existed, and exits 0.
    """
    calls: list[str] = []
    monkeypatch.setattr(mod, "write_seed_file", lambda: calls.append("seed"))
    monkeypatch.setattr(mod, "write_config", lambda: calls.append("config"))
    monkeypatch.setattr(mod, "write_env_md", lambda: calls.append("env"))
    monkeypatch.setattr(
        mod,
        "write_fidelity",
        lambda **kw: calls.append("fidelity"),  # noqa: ARG005
    )
    monkeypatch.setattr(
        mod,
        "write_external_audit",
        lambda **kw: calls.append("audit"),  # noqa: ARG005
    )
    monkeypatch.setattr(mod, "FIDELITY_PATH", tmp_path / "fidelity.json")

    exit_code = mod.main([])

    assert exit_code == 0
    assert calls == ["seed", "config", "env"]


def test_main_fidelity_flag_does_not_write_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``--fidelity`` alone must not also run the write-config default path."""
    calls: list[str] = []
    monkeypatch.setattr(mod, "write_seed_file", lambda: calls.append("seed"))
    monkeypatch.setattr(mod, "write_config", lambda: calls.append("config"))
    monkeypatch.setattr(mod, "write_env_md", lambda: calls.append("env"))

    def _fake_write_fidelity(*, path: Path, run_dir: Path) -> dict[str, object]:  # noqa: ARG001
        calls.append("fidelity")
        return {"all_match": True, "c0": {"matches": True}, "c4": {"matches": True}}

    monkeypatch.setattr(mod, "write_fidelity", _fake_write_fidelity)
    monkeypatch.setattr(mod, "FIDELITY_PATH", tmp_path / "fidelity.json")

    exit_code = mod.main(["--fidelity"])

    assert exit_code == 0
    assert calls == ["fidelity"]

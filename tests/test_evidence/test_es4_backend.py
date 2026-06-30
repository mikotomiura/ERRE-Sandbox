"""Deterministic tests for the M13-ES4 real-backend orchestration (no GPU).

The live SGLang seams + the MPNet encoder are exercised by the real smoke (GPU,
not unit-testable here). What *is* deterministically testable — and what these
tests cover — is the persist + replay round-trip: running Phase A under the **mock**
seams, persisting, and replaying through ``run_phase_b`` must reproduce the direct
mock ``run_phase`` verdict exactly, with zero replay misses. That proves the
phase-flip orchestration touches nothing the frozen apparatus computes.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from erre_sandbox.evidence.es4_actuator.backend import (
    build_replay_seams,
    load_phase_a,
    p_yes_from_logprobs,
    parse_yes,
    run_phase_a,
    run_phase_b,
    strip_think,
)
from erre_sandbox.evidence.es4_actuator.mock_seams import (
    mock_encode,
    mock_inference,
    mock_judge,
    mock_score,
)
from erre_sandbox.evidence.es4_actuator.pipeline import run_phase

if TYPE_CHECKING:
    from pathlib import Path


# --- parsers ------------------------------------------------------------------


def test_strip_think_removes_block() -> None:
    assert strip_think("<think>reasoning</think>yes") == "yes"
    assert strip_think("  plain  ") == "plain"


def test_parse_yes() -> None:
    assert parse_yes("yes") is True
    assert parse_yes("Yes, it is") is True
    assert parse_yes("<think>x</think>YES") is True
    assert parse_yes("no") is False
    assert parse_yes("") is False
    assert parse_yes("maybe") is False
    assert parse_yes("yesterday") is False  # word-boundary (Codex LOW-1)


def test_p_yes_from_logprobs() -> None:
    import math

    payload = {
        "choices": [
            {
                "logprobs": {
                    "content": [
                        {
                            "top_logprobs": [
                                {"token": "yes", "logprob": math.log(0.8)},
                                {"token": "no", "logprob": math.log(0.2)},
                            ]
                        }
                    ]
                }
            }
        ]
    }
    p = p_yes_from_logprobs(payload)
    assert p is not None
    assert math.isclose(p, 0.8, abs_tol=1e-9)
    # no usable logprobs → None (caller falls back to the binary decision)
    assert p_yes_from_logprobs({"choices": [{}]}) is None


# --- replay round-trip --------------------------------------------------------


def _assert_verdicts_match(actual: object, expected: object) -> None:
    a, e = vars(actual), vars(expected)
    assert a["verdict"] == e["verdict"]
    assert a["reasons"] == e["reasons"]
    assert a["n_clusters"] == e["n_clusters"]
    assert a["monotone_supported"] == e["monotone_supported"]
    for key in (
        "delta_dq",
        "delta_dq_ci_lower",
        "delta_dq_ci_upper",
        "delta_dq_std",
        "delta_dq_std_ci_lower",
        "garbage_rate_a2",
        "a1_min_auc",
        "adversarial_auc",
        "a2_residual_ci_lower",
    ):
        assert math.isclose(a[key], e[key], rel_tol=0.0, abs_tol=1e-12), key


def test_phase_a_replay_matches_direct_mock_run(tmp_path: Path) -> None:
    """Phase A(mock) → persist → Phase B replay == direct mock run_phase."""
    run_phase_a(mock_inference, mock_judge, mock_score, tmp_path, "phase0")
    replayed, misses, extras = run_phase_b(
        tmp_path, mock_encode, projected_gpu_hours=0.0
    )

    assert misses.all_zero, vars(misses)
    direct = run_phase(
        "phase0",
        mock_inference,
        mock_encode,
        mock_judge,
        mock_score,
        projected_gpu_hours=0.0,
    )
    _assert_verdicts_match(replayed, direct)
    # forensic extras present (Codex HIGH-3/5/6)
    assert "r_object_hashes" in extras
    assert "persona_sep_min" in extras
    assert "phase0_total_gpu_hours" in extras


def test_phase_a_manifest_and_persistence(tmp_path: Path) -> None:
    manifest = run_phase_a(mock_inference, mock_judge, mock_score, tmp_path, "phase0")
    assert manifest["phase"] == "phase0"
    assert manifest["n_generations"] > 0
    assert manifest["n_judgements"] > 0
    assert manifest["n_scores"] > 0
    assert manifest["smoke"] is False

    data = load_phase_a(tmp_path)
    assert data.phase == "phase0"
    assert len(data.responses) == manifest["n_generations"]
    assert len(data.judgements) == manifest["n_judgements"]
    assert len(data.scores) == manifest["n_scores"]


def test_replay_misses_flag_uncovered_query(tmp_path: Path) -> None:
    run_phase_a(mock_inference, mock_judge, mock_score, tmp_path, "phase0")
    data = load_phase_a(tmp_path)
    _inference_fn, judge_fn, score_fn, misses = build_replay_seams(data)

    # A query Phase A never persisted is counted as a miss (worst-value fallback).
    assert judge_fn("not_an_object", "not an idea") is False
    assert score_fn("not_an_object", "not a string") == 0.0
    assert misses.judge == 1
    assert misses.score == 1
    assert not misses.all_zero
    # A covered query does not increment misses.
    obj, idea = next(iter(data.judgements))
    assert judge_fn(obj, idea) == data.judgements[(obj, idea)]
    assert misses.judge == 1


def test_smoke_filter_subsets_requests(tmp_path: Path) -> None:
    def only_kant_a0(req: object) -> bool:
        r = vars(req)
        return r["persona_id"] == "kant" and r["condition"] in {"A0", "REF"}

    full = run_phase_a(
        mock_inference, mock_judge, mock_score, tmp_path / "full", "phase0"
    )
    sub = run_phase_a(
        mock_inference,
        mock_judge,
        mock_score,
        tmp_path / "sub",
        "phase0",
        smoke_filter=only_kant_a0,
    )
    assert sub["smoke"] is True
    assert sub["n_generations"] < full["n_generations"]

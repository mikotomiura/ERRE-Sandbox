"""M13-ES4 rarity scoring + appropriateness gate (§2.1 / §2.2), fixed-stub embeddings.

DQ = on-task rarity over first-K-valid ideas, with the V<2→DQ=0 selection-bias
freeze. Embeddings are deterministic stubs so the rarity math is pinned without an
encoder. LLM is touched only through the (stubbed) seams.
"""

from __future__ import annotations

import numpy as np

from erre_sandbox.evidence.es4_actuator import constants as _c
from erre_sandbox.evidence.es4_actuator.scoring import (
    RarityReference,
    h_proxy,
    intra_list_dispersion,
    parse_ideas,
    passes_degeneracy,
    rarity,
    score_generation,
)

_E1 = np.array([1.0, 0.0, 0.0])
_E2 = np.array([0.0, 1.0, 0.0])
_E3 = np.array([0.0, 0.0, 1.0])

# Keys are >= 3-token phrases so they clear the degeneracy filter (IDEA_MIN_TOK).
_VEC = {"idea alpha here": _E1, "idea beta here": _E2, "idea gamma here": _E3}


def _stub_encoder(texts: list[str]) -> np.ndarray:
    return np.array(
        [_VEC.get(t.strip().lower(), np.zeros(3)) for t in texts], dtype=float
    )


def _always_true(_obj: str, _idea: str) -> bool:
    return True


def _ref(*texts: str) -> RarityReference:
    emb = _stub_encoder(list(texts))
    return RarityReference(
        object_id="x",
        texts=tuple(texts),
        embeddings=emb,
        content_hash="h",
        fallback_curated_only=False,
    )


def test_parse_ideas_splits_and_dedupes() -> None:
    response = "1. use as a stand\n2. use as a stand\n- a hook\n\n  * a wedge "
    assert parse_ideas(response) == ["use as a stand", "a hook", "a wedge"]


def test_degeneracy_filter() -> None:
    assert passes_degeneracy("use the brick as a wedge")
    assert not passes_degeneracy("brick")  # < IDEA_MIN_TOK tokens
    assert not passes_degeneracy("na " * 50)  # too long + low distinct ratio
    assert not passes_degeneracy("go go go go go go go")  # repeated trigram loop


def test_rarity_zero_for_match_one_for_orthogonal() -> None:
    out = rarity(np.array([_E1, _E2]), np.array([_E1]))
    assert out[0] == 0.0  # identical to reference
    assert out[1] == 1.0  # orthogonal to reference


def test_dispersion_zero_for_identical_one_for_orthogonal() -> None:
    assert intra_list_dispersion(np.array([_E1, _E1])) == 0.0
    assert intra_list_dispersion(np.array([_E1, _E2])) == 1.0


def test_h_proxy_nonneg_and_varies() -> None:
    assert h_proxy("") == 0.0
    rich = h_proxy("a wildly varied sentence with many distinct tokens here")
    poor = h_proxy("aaaaa aaaaa aaaaa aaaaa aaaaa")
    assert rich > poor >= 0.0


def test_dq_is_mean_rarity_over_valid() -> None:
    score = score_generation(
        "1. idea alpha here\n2. idea beta here",
        "x",
        _ref("idea alpha here"),
        _stub_encoder,
        _always_true,
    )
    assert score.n_valid == 2
    assert score.dq == 0.5  # mean(rarity(alpha)=0, rarity(beta)=1)


def test_v_below_two_floors_dq_to_zero() -> None:
    score = score_generation(
        "1. idea alpha here", "x", _ref("idea gamma here"), _stub_encoder, _always_true
    )
    assert score.n_valid == 1
    assert score.dq == 0.0  # V < MIN_VALID_IDEAS_FOR_DQ → worst value, not dropped


def test_first_k_valid_cap() -> None:
    ideas = "\n".join(f"{i}. idea alpha{i} here" for i in range(_c.K_IDEAS + 4))
    captured: list[int] = []

    def counting_encoder(texts: list[str]) -> np.ndarray:
        captured.append(len(texts))
        return np.ones((len(texts), 3))

    score_generation(
        ideas, "x", _ref("a curated reference use"), counting_encoder, _always_true
    )
    assert captured[0] == _c.K_IDEAS  # only first-K-valid ideas are scored


def test_empty_and_garbage_flags() -> None:
    empty = score_generation("", "x", _ref("a"), _stub_encoder, _always_true)
    assert empty.empty
    assert empty.dq == 0.0

    garbage = score_generation(
        "zzz zzz zzz zzz", "x", _ref("a"), _stub_encoder, _always_true
    )
    assert garbage.is_garbage
    assert garbage.n_valid == 0
    assert garbage.dq == 0.0


def test_judge_gate_filters_inappropriate() -> None:
    def reject_beta(_obj: str, idea: str) -> bool:
        return "beta" not in idea

    score = score_generation(
        "1. idea alpha here\n2. idea beta here",
        "x",
        _ref("ref use"),
        _stub_encoder,
        reject_beta,
    )
    assert score.n_valid == 1  # beta rejected by the judge

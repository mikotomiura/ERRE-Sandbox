"""M13-ES4 rarity reference R_object construction recipe (§2.2b), mock generation.

Pins the held-out high-frequency augmentation, the near-dup merge, the
sufficiency/fallback/drop branches, content-hash stability and the disjoint
reference-seed request set. LLM-free (deterministic stub encoder + judge).
"""

from __future__ import annotations

import hashlib

import numpy as np

from erre_sandbox.evidence.es4_actuator import constants as _c
from erre_sandbox.evidence.es4_actuator.reference import (
    REF_BASE,
    build_reference_requests,
    construct_reference,
)


def _signed_vec(text: str) -> np.ndarray:
    digest = hashlib.blake2b(
        text.strip().lower().encode("utf-8"), digest_size=16
    ).digest()
    return np.frombuffer(digest, dtype=np.uint8).astype(np.float64) - 128.0


def _encoder(mapping: dict[str, np.ndarray] | None = None):
    table = mapping or {}

    def fn(texts):
        return np.array([table.get(t, _signed_vec(t)) for t in texts], dtype=float)

    return fn


def _true(_obj: str, _idea: str) -> bool:
    return True


_CURATED10 = tuple(f"curated use number {i}" for i in range(10))


def test_curated_only_when_no_responses() -> None:
    ref = construct_reference("brick", _CURATED10, (), _encoder(), _true)
    assert ref is not None
    assert set(ref.texts) == set(_CURATED10)
    assert not ref.fallback_curated_only  # merged path (curated >= N_R_MIN)


def test_high_frequency_idea_is_added() -> None:
    responses = ["1. a shared common use\n2. one off idea here"] * 8 + [
        "1. a shared common use"
    ] * 2
    ref = construct_reference("brick", _CURATED10, responses, _encoder(), _true)
    assert ref is not None
    assert "a shared common use" in ref.texts  # freq 10/10 >= REF_FREQ_MIN


def test_low_frequency_idea_is_not_added() -> None:
    responses = ["1. rare singleton idea"] + ["1. nothing relevant token here"] * 9
    ref = construct_reference("brick", _CURATED10, responses, _encoder(), _true)
    assert ref is not None
    assert "rare singleton idea" not in ref.texts  # freq 1/10 < REF_FREQ_MIN


def test_near_duplicate_high_freq_is_deduped() -> None:
    dup_vec = _signed_vec(_CURATED10[0])  # identical embedding to a curated anchor
    responses = ["1. duplicate of anchor"] * 10
    enc = _encoder({"duplicate of anchor": dup_vec})
    ref = construct_reference("brick", _CURATED10, responses, enc, _true)
    assert ref is not None
    assert (
        "duplicate of anchor" not in ref.texts
    )  # cosine 1.0 >= REF_DEDUP → merged out


def test_dropped_when_curated_below_floor() -> None:
    ref = construct_reference("brick", ("only one use",), (), _encoder(), _true)
    assert ref is None  # < N_R_MIN even curated-only → object dropped


def test_content_hash_stable() -> None:
    a = construct_reference("brick", _CURATED10, (), _encoder(), _true)
    b = construct_reference("brick", _CURATED10, (), _encoder(), _true)
    assert a is not None
    assert b is not None
    assert a.content_hash == b.content_hash


def test_reference_size_capped() -> None:
    many = tuple(f"curated use number {i}" for i in range(_c.N_R_MAX + 15))
    ref = construct_reference("brick", many, (), _encoder(), _true)
    assert ref is not None
    assert len(ref.texts) <= _c.N_R_MAX


def test_build_reference_requests_disjoint_and_sized() -> None:
    reqs = build_reference_requests()
    assert len(reqs) == _c.N_AUT * _c.REF_SEEDS
    assert {r.condition for r in reqs} == {"REF"}
    assert all(r.resolved.temperature == REF_BASE.temperature for r in reqs)
    assert len({r.seed for r in reqs}) == len(reqs)  # all reference seeds distinct

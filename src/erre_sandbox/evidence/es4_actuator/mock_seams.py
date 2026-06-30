"""Deterministic LLM-free mock seams for the M13-ES4 Session 1 smoke + tests.

**Not** a backend. These are deterministic stand-ins for the three injectable
seams (:data:`scenario.InferenceFn`, :data:`scoring.EncoderFn`,
:data:`scoring.JudgeFn`, and the :data:`controls.ScoreFn`) so the whole apparatus
runs end-to-end **without any GPU / LLM** in Session 1. Session 2 replaces every
one of these with the real SGLang fp8 qwen3:8b backend + MPNet encoder; the
verdict a mock run produces is a **plumbing smoke**, not a scientific result.

Everything is a pure function of its inputs (hash-derived), so a mock run is
byte-reproducible.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Final

import numpy as np

from erre_sandbox.evidence.es4_actuator.battery import load_rat_battery

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.evidence.es4_actuator.scenario import GenerationRequest

_EMBED_DIM: Final[int] = 32

_ADJ: Final[tuple[str, ...]] = (
    "improvised",
    "decorative",
    "sturdy",
    "miniature",
    "portable",
    "clever",
    "rustic",
    "elegant",
    "makeshift",
    "hidden",
)
_NOUN: Final[tuple[str, ...]] = (
    "holder",
    "tool",
    "stand",
    "weight",
    "marker",
    "container",
    "anchor",
    "wedge",
    "scoop",
    "hook",
)
_COMMON: Final[tuple[str, ...]] = (
    "hold something",
    "cover a surface",
    "store small items",
    "prop a door",
    "weigh paper down",
)


def _hash_int(*parts: object) -> int:
    key = "|".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


def mock_encode(texts: Sequence[str]) -> np.ndarray:
    """Deterministic hash embedding (identical text → identical vector)."""
    rows = []
    for t in texts:
        digest = hashlib.blake2b(
            t.strip().lower().encode("utf-8"), digest_size=_EMBED_DIM
        ).digest()
        rows.append(np.frombuffer(digest, dtype=np.uint8).astype(np.float64))
    return np.asarray(rows, dtype=np.float64) if rows else np.zeros((0, _EMBED_DIM))


def mock_inference(request: GenerationRequest) -> str:
    """A deterministic pseudo-response that exercises the parse / score paths.

    AUT / reference responses are numbered idea lists whose count grows with the
    resolved temperature (so higher-λ conditions parse more ideas); reference
    generations lean on a small common-use bank so the frequency augmentation
    fires. RAT responses return the wrong/right token at a moderate base rate.
    """
    if request.task == "rat":
        rat = {it.item_id: it.answer for it in load_rat_battery().items}
        answer = rat.get(request.item_id, "answer")
        correct = _hash_int(request.item_id, request.seed_idx) % 10 < 5  # noqa: PLR2004
        return answer if correct else "thing"

    temp = request.resolved.temperature
    n_ideas = 3 + round(temp * 3)
    obj = request.item_id.replace("_", " ")
    lines: list[str] = []
    for k in range(n_ideas):
        salt = _hash_int(
            request.persona_id, request.item_id, request.condition, request.seed_idx, k
        )
        if request.condition == "REF" and k < 2:  # noqa: PLR2004
            lines.append(f"{k + 1}. {_COMMON[salt % len(_COMMON)]}")
        else:
            adj = _ADJ[salt % len(_ADJ)]
            noun = _NOUN[(salt // 7) % len(_NOUN)]
            lines.append(f"{k + 1}. use the {obj} as a {adj} {noun}")
    return "\n".join(lines)


def mock_judge(obj: str, idea: str) -> bool:  # noqa: ARG001 — seam signature
    """Heuristic appropriateness: a clean multi-word phrase passes."""
    toks = idea.split()
    distinct = len({t.lower() for t in toks})
    return len(toks) >= 3 and distinct / max(len(toks), 1) >= 0.5  # noqa: PLR2004


def mock_score(obj: str, text: str) -> float:  # noqa: ARG001 — seam signature
    """Continuous appropriateness score (higher = cleaner phrase).

    A coarse stand-in for the SGLang judge logit: rewards lexical variety and
    penalises degenerate repetition, enough to give a non-trivial AUC on the
    frozen labeled set under the mock (the real judge is Session 2).
    """
    toks = text.lower().split()
    if not toks:
        return 0.0
    distinct_ratio = len(set(toks)) / len(toks)
    has_alpha = sum(1 for t in toks if any(c.isalpha() for c in t)) / len(toks)
    return 0.5 * distinct_ratio + 0.5 * has_alpha


__all__ = [
    "mock_encode",
    "mock_inference",
    "mock_judge",
    "mock_score",
]

"""Frozen construction of the rarity reference ``R_object`` (§2.2b, Codex 2nd HIGH-A).

``DQ = 1 − max cos(idea, R_object)``, so the breadth of ``R_object`` directly
moves the primary ΔDQ and Phase 0 futility/power. The reference is therefore built
by a **deterministic recipe with a content-hash freeze**, *before* any A0/A1/A2/M2/F
verdict generation, and never regenerated (forking-paths seal). The recipe:

1. **curated anchor** — the hand-frozen ``data/common_uses.yaml`` (object × 10),
   the human rarity anchor.
2. **held-out high-frequency augmentation** — verdict-**disjoint** ``REF_SEEDS``
   generations per object at the neutral ``REF_TEMP``, parsed through the *same*
   (c) gate (:func:`scoring.valid_ideas`); ideas appearing in ≥ ``REF_FREQ_MIN`` of
   them are added (model-register common uses).
3. **merge + dedupe** — curated ∪ high-frequency, near-duplicates (cosine ≥
   ``REF_DEDUP``) collapsed, capped at ``N_R_MAX``.
4. **sufficiency / fallback** — ``|R_object| < N_R_MIN`` ⇒ fallback to curated-only;
   curated still < ``N_R_MIN`` ⇒ the object is **dropped** (→ valid-AUT count falls
   → INVALID_TASK_BATTERY). No manual exclusion (fully automatic).
5. **hash freeze** — content-hash of (sorted texts + rounded embeddings) recorded
   in the run manifest; Phase 1 reuses the frozen reference (no rebuild).

Generation is the injectable :data:`scenario.InferenceFn` seam and embedding the
:data:`scoring.EncoderFn` seam, so Session 1 builds + tests the whole recipe under
mocks. numpy / stdlib only otherwise.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import TYPE_CHECKING, Final

import numpy as np

from erre_sandbox.evidence.es4_actuator import constants as _c
from erre_sandbox.evidence.es4_actuator.battery import AutBattery, load_aut_battery
from erre_sandbox.evidence.es4_actuator.scenario import (
    GenerationRequest,
    derive_ref_seed,
)
from erre_sandbox.evidence.es4_actuator.scoring import RarityReference, valid_ideas
from erre_sandbox.inference.sampling import compose_sampling
from erre_sandbox.schemas import SamplingBase, SamplingDelta

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from erre_sandbox.evidence.es4_actuator.scoring import EncoderFn, JudgeFn

REF_BASE: Final[SamplingBase] = SamplingBase(
    temperature=_c.REF_TEMP, top_p=0.95, repeat_penalty=1.1
)
"""Neutral, persona-independent reference base (§2.2b step 2): ``REF_TEMP`` = 0.7,
a neutral top_p / repeat_penalty. Pinned in ``test_es4_reference.py``."""

_WS_RE: Final[re.Pattern[str]] = re.compile(r"\s+")
_HASH_DECIMALS: Final[int] = 6


def _normalise(text: str) -> str:
    return _WS_RE.sub(" ", text.strip().lower())


def build_reference_requests(aut: AutBattery | None = None) -> list[GenerationRequest]:
    """The held-out reference generations (object × ``REF_SEEDS``, disjoint seeds)."""
    aut = aut if aut is not None else load_aut_battery()
    resolved = compose_sampling(REF_BASE, SamplingDelta())
    requests: list[GenerationRequest] = []
    for item in aut.items:
        prompt = aut.prompt_for(item)
        requests.extend(
            GenerationRequest(
                persona_id="reference",
                task="aut",
                item_id=item.object_id,
                condition="REF",
                seed=derive_ref_seed(item.object_id, ref_idx),
                seed_idx=ref_idx,
                resolved=resolved,
                prompt=prompt,
                num_predict=_c.NUM_PREDICT_AUT,
                lam=None,
            )
            for ref_idx in range(_c.REF_SEEDS)
        )
    return requests


def _high_frequency_uses(
    responses: Sequence[str], obj: str, judge_fn: JudgeFn
) -> list[str]:
    """Ideas appearing in ≥ ``REF_FREQ_MIN`` of the held-out reference generations.

    Frequency is counted on the normalised idea (case / whitespace folded), at
    most once per generation; the representative text is the first occurrence.
    """
    threshold = _c.REF_FREQ_MIN * len(responses) if responses else 0.0
    counts: Counter[str] = Counter()
    representative: dict[str, str] = {}
    for response in responses:
        seen_here: set[str] = set()
        for idea in valid_ideas(response, obj, judge_fn):
            key = _normalise(idea)
            if key in seen_here:
                continue
            seen_here.add(key)
            counts[key] += 1
            representative.setdefault(key, idea)
    return [representative[k] for k, c in counts.most_common() if c >= threshold]


def _greedy_dedupe(texts: Sequence[str], embeddings: np.ndarray) -> list[int]:
    """Indices kept after greedy near-dup merge (cosine ≥ ``REF_DEDUP``), in order.

    Priority is the input order (curated first), so curated anchors are never
    dropped in favour of a held-out near-duplicate.
    """
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    unit = embeddings / np.where(norms == 0.0, 1.0, norms)
    kept: list[int] = []
    for i in range(len(texts)):
        if len(kept) >= _c.N_R_MAX:
            break
        if not kept:
            kept.append(i)
            continue
        cos = unit[i] @ unit[np.asarray(kept)].T
        if float(cos.max()) < _c.REF_DEDUP:
            kept.append(i)
    return kept


def _content_hash(texts: Sequence[str], embeddings: np.ndarray) -> str:
    h = hashlib.blake2b(digest_size=16)
    for text, row in zip(texts, embeddings, strict=True):
        h.update(text.encode("utf-8"))
        h.update(b"\x00")
        h.update(np.round(row, _HASH_DECIMALS).astype(np.float64).tobytes())
    return h.hexdigest()


def _assemble(
    object_id: str, texts: Sequence[str], encoder_fn: EncoderFn, *, fallback: bool
) -> RarityReference:
    emb = np.asarray(encoder_fn(list(texts)), dtype=float)
    kept = _greedy_dedupe(texts, emb)
    final_texts = tuple(texts[i] for i in kept)
    final_emb = emb[np.asarray(kept)] if kept else emb[:0]
    return RarityReference(
        object_id=object_id,
        texts=final_texts,
        embeddings=final_emb,
        content_hash=_content_hash(final_texts, final_emb),
        fallback_curated_only=fallback,
    )


def construct_reference(
    object_id: str,
    curated: Sequence[str],
    responses: Sequence[str],
    encoder_fn: EncoderFn,
    judge_fn: JudgeFn,
    obj: str | None = None,
) -> RarityReference | None:
    """Build the frozen ``R_object`` for one object (§2.2b), or ``None`` if dropped.

    ``responses`` are the held-out reference generations' raw texts; ``obj`` is the
    human object string for the judge (defaults to ``object_id``). Returns ``None``
    only when even curated-only has < ``N_R_MIN`` entries after dedupe (the object
    is dropped → it counts against the valid-AUT floor).
    """
    obj = obj if obj is not None else object_id
    high_freq = _high_frequency_uses(responses, obj, judge_fn)
    merged_texts = [*curated, *high_freq]
    merged = _assemble(object_id, merged_texts, encoder_fn, fallback=False)
    if len(merged.texts) >= _c.N_R_MIN:
        return merged

    curated_only = _assemble(object_id, list(curated), encoder_fn, fallback=True)
    if len(curated_only.texts) >= _c.N_R_MIN:
        return curated_only
    return None


def construct_all_references(
    curated_by_object: Mapping[str, Sequence[str]],
    responses_by_object: Mapping[str, Sequence[str]],
    objects_by_id: Mapping[str, str],
    encoder_fn: EncoderFn,
    judge_fn: JudgeFn,
) -> dict[str, RarityReference]:
    """Build every object's frozen ``R_object``; dropped objects are absent.

    The caller compares ``len(result)`` against ``MIN_VALID_AUT`` for the
    battery-validity gate (§3 / §8).
    """
    out: dict[str, RarityReference] = {}
    for object_id, curated in curated_by_object.items():
        ref = construct_reference(
            object_id,
            curated,
            responses_by_object.get(object_id, ()),
            encoder_fn,
            judge_fn,
            obj=objects_by_id.get(object_id, object_id),
        )
        if ref is not None:
            out[object_id] = ref
    return out


__all__ = [
    "REF_BASE",
    "build_reference_requests",
    "construct_all_references",
    "construct_reference",
]

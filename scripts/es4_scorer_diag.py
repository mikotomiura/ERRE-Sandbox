"""M13-ES4 **offline scorer diagnostic** (direction C) — zero new GPU.

Phase 0 returned ``INVALID_SCORER``. The rejected thing is the *measurement
instrument* (on-task rarity ``DQ = 1 - max_r cos(idea, R_object)``), **not** the
hypothesis H4 (which is unjudged). This script decides, using only the persisted
Phase A artifacts + frozen holdouts, whether a candidate divergent-quality scorer
*exists* that clears the non-tautology gates, and diagnoses *why* MPNet rarity
failed. It emits a per-candidate table + a go/no-go (``D`` re-enter / ``B`` pivot).

It is **read-only** w.r.t. the frozen apparatus ``evidence/es4_actuator`` (imported,
never mutated) and performs **no** new generation / GPU work — only CPU
re-embedding of already-persisted text. Design + Codex review: see
``.steering/20260701-m13-es4-scorer-diagnostic/`` and the approved plan.

Decision rule (Codex-hardened, no tune-to-pass backdoor):

* ``RARITY_OK(c)`` — the candidate separates gold ``good`` (high rarity) from gold
  ``common_use_only`` (low rarity), **among appropriate items only**, with AUC >=
  ``AUC_FLOOR`` on **both** the full reference **and** a leave-anchor-out audit
  (Codex HIGH-1/2). Candidates are taken in a pre-declared order (Codex MED-2).
* ``ENTROPY_OK(c)`` — the candidate's λ→DQ survives partialling out the entropy
  proxy on a holdout (residual CI_lower > 0; Codex HIGH-3), exploratory on A0/A2.
* ``SCORER_OK`` = ∃ candidate with ``RARITY_OK ∧ ENTROPY_OK``.
* ``SIGNAL_PLAUSIBLE`` = that candidate shows a non-trivial exploratory A0→A2
  effect, weighed against the flat-structure forensic.
* ``PASS → D`` iff ``SCORER_OK ∧ SIGNAL_PLAUSIBLE``; ``SCORER_OK ∧ ¬SIGNAL → B``;
  ``¬SCORER_OK → B``. GPU-only candidates are future-pre-register-only, never a PASS.

Usage::

    PYTHONPATH=src python scripts/es4_scorer_diag.py \
        --run-dir experiments/20260630-es4-phase0/phaseA \
        --out experiments/20260701-es4-scorer-diag/diagnostic.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from erre_sandbox.evidence.es4_actuator import constants as _c
from erre_sandbox.evidence.es4_actuator.battery import (
    AdversarialItem,
    load_adversarial_labeled,
    load_aut_battery,
    load_common_uses,
)
from erre_sandbox.evidence.es4_actuator.controls import auc, held_out_residual
from erre_sandbox.evidence.es4_actuator.reference import construct_all_references
from erre_sandbox.evidence.es4_actuator.scoring import (
    h_proxy,
    parse_ideas,
    passes_degeneracy,
)

EncoderFn = Callable[[Sequence[str]], np.ndarray]

# Alt encoders (Codex C3) — best-effort; gracefully skipped when not cached offline.
_ALT_ENCODER_IDS: tuple[str, ...] = (
    "sentence-transformers/all-MiniLM-L6-v2",
    "intfloat/e5-small-v2",
    "BAAI/bge-small-en-v1.5",
)
_TOKEN_RE = re.compile(r"[a-z0-9']+")


# --------------------------------------------------------------------------- #
# data loading
# --------------------------------------------------------------------------- #
def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def build_judge_map(
    judgements: Sequence[dict[str, Any]],
) -> dict[tuple[str, str], bool]:
    """``(object_human_string, idea) -> valid`` from the persisted judge labels."""
    return {(j["object"], j["idea"]): bool(j["valid"]) for j in judgements}


def make_replay_judge(
    judge_map: Mapping[tuple[str, str], bool],
) -> Callable[[str, str], bool]:
    """The appropriateness judge replayed from persisted labels (no new GPU)."""

    def judge(obj: str, idea: str) -> bool:
        return bool(judge_map.get((obj, idea), False))

    return judge


# --------------------------------------------------------------------------- #
# encoders (CPU, lazy import; 3-point set discipline)
# --------------------------------------------------------------------------- #
def make_encoder(model_id: str) -> EncoderFn | None:
    """Build a CPU sentence-transformers encoder, or ``None`` if unavailable offline.

    Mirrors ``backend.make_mpnet_encoder`` (e5-prefix logic from ``tier_b/vendi``)
    but is parametrised by ``model_id`` so the alt-encoder candidates reuse it.
    """
    try:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        from erre_sandbox.evidence.tier_b.vendi import (  # noqa: PLC0415
            e5_passage_prefix,
            model_needs_e5_prefix,
        )

        model = SentenceTransformer(model_id, device="cpu")
        needs_prefix = model_needs_e5_prefix(model_id)
        prefix = e5_passage_prefix()
        dim = int(model.get_sentence_embedding_dimension() or 768)
    except Exception:  # noqa: BLE001 — offline / missing model => graceful skip
        return None

    def encode(texts: Sequence[str]) -> np.ndarray:
        items = list(texts)
        if not items:
            return np.zeros((0, dim), dtype=float)
        inputs = [prefix + str(t) for t in items] if needs_prefix else items
        return np.asarray(model.encode(inputs, show_progress_bar=False), dtype=float)

    return encode


def embed_map(encoder: EncoderFn, texts: Sequence[str]) -> dict[str, np.ndarray]:
    """Unit-normalised embedding per unique text (cosine == dot product)."""
    uniq = sorted({str(t) for t in texts})
    if not uniq:
        return {}
    mat = np.asarray(encoder(uniq), dtype=float)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    unit = mat / np.where(norms == 0.0, 1.0, norms)
    return {t: unit[i] for i, t in enumerate(uniq)}


# --------------------------------------------------------------------------- #
# rarity definitions (per single idea string)
# --------------------------------------------------------------------------- #
def _cos_to_refs(vec: np.ndarray, ref: np.ndarray) -> np.ndarray:
    if ref.size == 0:
        return np.zeros(0, dtype=float)
    return ref @ vec


def embed_rarity(
    vec: np.ndarray, ref: np.ndarray, *, leave_anchor_out: bool, agg: str = "max"
) -> float:
    """Rarity ``1 - agg_r cos(idea, r)`` over the reference rows.

    Leave-anchor-out drops near-duplicate anchors (cos >= ``REF_DEDUP``) so a scorer
    cannot pass by recognising its own literal negative anchor (Codex HIGH-1).
    """
    cos = _cos_to_refs(vec, ref)
    if leave_anchor_out and cos.size:
        cos = cos[cos < _c.REF_DEDUP]
    if cos.size == 0:
        return 0.0  # everything is a near-dup => maximally common => rarity 0
    sim = float(cos.max()) if agg == "max" else float(cos.mean())
    return 1.0 - sim


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def jaccard_rarity(text: str, ref_texts: Sequence[str], *, drop_dup: bool) -> float:
    """``1 - max_r jaccard(tokens(idea), tokens(r))`` (encoder-free novelty)."""
    a = _tokens(text)
    if not a:
        return 0.0
    sims = []
    for r in ref_texts:
        b = _tokens(r)
        union = a | b
        j = len(a & b) / len(union) if union else 0.0
        sims.append(j)
    sims_arr = np.asarray(sims, dtype=float)
    if drop_dup and sims_arr.size:
        sims_arr = sims_arr[sims_arr < _c.REF_DEDUP]
    if sims_arr.size == 0:
        return 0.0
    return 1.0 - float(sims_arr.max())


def build_idf(corpus: Sequence[str]) -> dict[str, float]:
    n = len(corpus)
    df: Counter[str] = Counter()
    for doc in corpus:
        for tok in _tokens(doc):
            df[tok] += 1
    return {tok: math.log((n + 1) / (c + 1)) + 1.0 for tok, c in df.items()}


def tfidf_rarity(text: str, idf: Mapping[str, float], default_idf: float) -> float:
    toks = _TOKEN_RE.findall(text.lower())
    if not toks:
        return 0.0
    return float(np.mean([idf.get(t, default_idf) for t in toks]))


# --------------------------------------------------------------------------- #
# candidate abstraction
# --------------------------------------------------------------------------- #
class RarityFn(Protocol):
    """``(object_id, text, *, leave_anchor_out) -> rarity`` (higher = rarer)."""

    def __call__(
        self, object_id: str, text: str, *, leave_anchor_out: bool
    ) -> float: ...


@dataclass
class Candidate:
    """A pre-declared scorer candidate exposing a per-string rarity."""

    key: str
    description: str
    rarity: RarityFn
    available: bool = True


def _zero_rarity(object_id: str, text: str, *, leave_anchor_out: bool) -> float:  # noqa: ARG001
    """Placeholder rarity for an unavailable (offline-skipped) candidate."""
    return 0.0


# --------------------------------------------------------------------------- #
# RARITY_OK: gold good-vs-common (non-circular instrument test)
# --------------------------------------------------------------------------- #
@dataclass
class GoldResult:
    auc_full: float
    auc_leave_anchor_out: float
    perm_p_full: float
    n_good: int
    n_common: int


def gold_good_vs_common(
    cand: Candidate, gold: Sequence[AdversarialItem], *, perm_seed: int = 0
) -> GoldResult:
    """AUC of the candidate separating gold ``good`` (1) from ``common_use_only`` (0).

    Among the two *appropriate* categories only (Codex HIGH-2: isolate rarity from
    the appropriateness axis the judge already owns). Reported on the full
    reference and the leave-anchor-out audit (Codex HIGH-1).
    """
    pos = [g for g in gold if g.category == "good"]
    neg = [g for g in gold if g.category == "common_use_only"]
    items = pos + neg
    labels = [1] * len(pos) + [0] * len(neg)

    def aucs(*, leave_anchor_out: bool) -> float:
        scores = [
            cand.rarity(g.object, g.text, leave_anchor_out=leave_anchor_out)
            for g in items
        ]
        return auc(scores, labels)

    auc_full = aucs(leave_anchor_out=False)
    auc_lao = aucs(leave_anchor_out=True)

    # permutation p (full): label shuffle null. n is small => report honestly.
    rng = np.random.default_rng(perm_seed)
    base_scores = [cand.rarity(g.object, g.text, leave_anchor_out=False) for g in items]
    null = np.empty(_c.N_RESAMPLES, dtype=float)
    lab = np.asarray(labels)
    for i in range(_c.N_RESAMPLES):
        null[i] = auc(base_scores, rng.permutation(lab).tolist())
    perm_p = float((1.0 + np.sum(null >= auc_full)) / (_c.N_RESAMPLES + 1.0))
    return GoldResult(auc_full, auc_lao, perm_p, len(pos), len(neg))


# --------------------------------------------------------------------------- #
# per-generation DQ + ENTROPY_OK (a2') + SIGNAL on A0/A2
# --------------------------------------------------------------------------- #
@dataclass
class GenDQ:
    persona_id: str
    item_id: str
    condition: str
    seed_idx: int
    dq: float
    h_proxy: float


def valid_first_k(
    response: str, obj_human: str, judge: Callable[[str, str], bool]
) -> list[str]:
    ideas = [
        idea
        for idea in parse_ideas(response)
        if passes_degeneracy(idea) and judge(obj_human, idea)
    ]
    return ideas[: _c.K_IDEAS]


def per_gen_dq(
    cand: Candidate,
    gens: Sequence[dict[str, Any]],
    obj_human: Mapping[str, str],
    judge: Callable[[str, str], bool],
) -> list[GenDQ]:
    """Per-generation DQ = mean candidate-rarity over first-K-valid ideas (V<2 → 0).

    Mirrors ``scoring.score_generation`` but with the candidate's rarity.
    """
    out: list[GenDQ] = []
    for g in gens:
        item_id = g["item_id"]
        human = obj_human[item_id]
        ideas = valid_first_k(g["response"], human, judge)
        if len(ideas) >= _c.MIN_VALID_IDEAS_FOR_DQ:
            dq = float(
                np.mean(
                    [
                        cand.rarity(item_id, idea, leave_anchor_out=False)
                        for idea in ideas
                    ]
                )
            )
        else:
            dq = 0.0
        out.append(
            GenDQ(
                g["persona_id"],
                item_id,
                g["condition"],
                g["seed_idx"],
                dq,
                h_proxy(g["response"]),
            )
        )
    return out


@dataclass
class SignalResult:
    raw_delta_dq: float
    delta_ci_lower: float
    delta_ci_upper: float
    n_clusters: int
    a2_residual_ci_lower: float
    a2_survives: bool


def cluster_paired_delta(units: Sequence[GenDQ]) -> tuple[float, float, float, int]:
    """Cluster-paired ΔDQ (A2−A0) + bootstrap CI (exploratory only).

    The cluster is ``(persona, item)`` and effective N = clusters, mirroring
    ``decomposition``.
    """
    cells: dict[tuple[str, str, str], dict[int, float]] = {}
    for u in units:
        cells.setdefault((u.persona_id, u.item_id, u.condition), {})[u.seed_idx] = u.dq
    deltas: list[float] = []
    keys = {(p, i) for (p, i, _c2) in cells}
    for persona, item in keys:
        a0 = cells.get((persona, item, "A0"), {})
        a2 = cells.get((persona, item, "A2"), {})
        common = sorted(set(a0) & set(a2))
        if common:
            deltas.append(float(np.mean([a2[s] - a0[s] for s in common])))
    arr = np.asarray(deltas, dtype=float)
    if arr.size == 0:
        return 0.0, 0.0, 0.0, 0
    rng = np.random.default_rng(0)
    idx = rng.integers(0, arr.size, size=(_c.N_RESAMPLES, arr.size))
    means = arr[idx].mean(axis=1)
    lo = float(np.quantile(means, _c.CI_ALPHA / 2.0))
    hi = float(np.quantile(means, 1.0 - _c.CI_ALPHA / 2.0))
    return float(arr.mean()), lo, hi, arr.size


def signal_and_entropy(units: Sequence[GenDQ]) -> SignalResult:
    raw, lo, hi, n = cluster_paired_delta(units)
    paired = [u for u in units if u.condition in {"A0", "A2"}]
    dq = [u.dq for u in paired]
    hp = [u.h_proxy for u in paired]
    hi_lambda = [1 if u.condition == "A2" else 0 for u in paired]
    holdout = [1 if u.seed_idx % 2 == 0 else 0 for u in paired]
    res = held_out_residual(dq, hp, hi_lambda, holdout)
    return SignalResult(raw, lo, hi, n, res.residual_ci_lower, res.survives)


# --------------------------------------------------------------------------- #
# forensic battery
# --------------------------------------------------------------------------- #
def _spearman(x: Sequence[float], y: Sequence[float]) -> float:
    xa, ya = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if xa.size < 2 or np.all(xa == xa[0]) or np.all(ya == ya[0]):  # noqa: PLR2004 — needs ≥2
        return 0.0
    rx = np.argsort(np.argsort(xa))
    ry = np.argsort(np.argsort(ya))
    return float(np.corrcoef(rx, ry)[0, 1])


def forensic_battery(
    incumbent: Candidate,
    aut_gens: Sequence[dict[str, Any]],
    obj_human: Mapping[str, str],
    judge: Callable[[str, str], bool],
) -> dict[str, Any]:
    """Failure-mechanism forensic on the incumbent scorer.

    is_garbage vacuity, off-task / valid / fluency by condition, and
    rarity↔entropy/temperature/length correlations.
    """
    by_cond_garbage: Counter[str] = Counter()
    by_cond_n: Counter[str] = Counter()
    valid_idea_counts: dict[str, list[int]] = {}
    idea_rarity: list[float] = []
    idea_len: list[float] = []
    idea_temp: list[float] = []
    idea_hproxy: list[float] = []
    for g in aut_gens:
        cond = g["condition"]
        by_cond_n[cond] += 1
        parsed = parse_ideas(g["response"])
        degen = [i for i in parsed if passes_degeneracy(i)]
        is_garbage = g["response"].strip() == "" or (len(parsed) > 0 and not degen)
        if is_garbage:
            by_cond_garbage[cond] += 1
        human = obj_human[g["item_id"]]
        valid = [i for i in degen if judge(human, i)]
        valid_idea_counts.setdefault(cond, []).append(len(valid))
        for idea in valid[: _c.K_IDEAS]:
            idea_rarity.append(
                incumbent.rarity(g["item_id"], idea, leave_anchor_out=False)
            )
            idea_len.append(float(len(idea)))
            idea_temp.append(float(g["temperature"]))
            idea_hproxy.append(h_proxy(idea))
    return {
        "is_garbage_total": int(sum(by_cond_garbage.values())),
        "n_aut_generations": int(sum(by_cond_n.values())),
        "is_garbage_by_condition": dict(by_cond_garbage),
        "mean_valid_ideas_by_condition": {
            c: float(np.mean(v)) for c, v in valid_idea_counts.items()
        },
        "incumbent_rarity_corr": {
            "vs_h_proxy": _spearman(idea_rarity, idea_hproxy),
            "vs_temperature": _spearman(idea_rarity, idea_temp),
            "vs_idea_length": _spearman(idea_rarity, idea_len),
        },
        "incumbent_rarity_range": {
            "min": float(np.min(idea_rarity)) if idea_rarity else 0.0,
            "p50": float(np.median(idea_rarity)) if idea_rarity else 0.0,
            "max": float(np.max(idea_rarity)) if idea_rarity else 0.0,
            "n_ideas": len(idea_rarity),
        },
    }


def adversarial_full_auc(cand: Candidate, gold: Sequence[AdversarialItem]) -> float:
    """Full 6-category appropriate-vs-inappropriate AUC for the candidate's rarity.

    Embedding-rarity is *expected* to do poorly here — separating appropriate from
    off-task is the judge's job, reported for context, not a RARITY_OK gate.
    """
    scores = [cand.rarity(g.object, g.text, leave_anchor_out=False) for g in gold]
    labels = [1 if g.label == "appropriate" else 0 for g in gold]
    return auc(scores, labels)


# --------------------------------------------------------------------------- #
# candidate construction
# --------------------------------------------------------------------------- #
def _make_embed_candidate(
    key: str,
    desc: str,
    vecs: Mapping[str, np.ndarray],
    ref_emb: Mapping[str, np.ndarray],
    agg: str,
) -> Candidate:
    def rarity(object_id: str, text: str, *, leave_anchor_out: bool) -> float:
        vec = vecs.get(text)
        ref = ref_emb.get(object_id)
        if vec is None or ref is None or ref.size == 0:
            return 0.0
        return embed_rarity(vec, ref, leave_anchor_out=leave_anchor_out, agg=agg)

    return Candidate(key, desc, rarity)


def _length_controlled(base: Candidate, gold: Sequence[AdversarialItem]) -> Candidate:
    """Residualise the base rarity on idea char-length over the gold strings (C2).

    So a length artefact cannot masquerade as rarity.
    """
    items = [g for g in gold if g.category in {"good", "common_use_only"}]
    lengths = np.asarray([len(g.text) for g in items], dtype=float)
    rar = np.asarray(
        [base.rarity(g.object, g.text, leave_anchor_out=False) for g in items],
        dtype=float,
    )
    if lengths.size >= 2 and float(np.var(lengths)) > 0.0:  # noqa: PLR2004 — a line needs ≥2 points
        b, a = np.polyfit(lengths, rar, 1)
    else:
        b = a = 0.0

    def rarity(object_id: str, text: str, *, leave_anchor_out: bool) -> float:
        base_r = base.rarity(object_id, text, leave_anchor_out=leave_anchor_out)
        return base_r - (a + b * len(text))

    return Candidate(
        f"{base.key}-lenctrl", f"{base.description} (length-controlled)", rarity
    )


# --------------------------------------------------------------------------- #
# decision rule
# --------------------------------------------------------------------------- #
@dataclass
class CandidateReport:
    key: str
    description: str
    available: bool
    gold_auc_full: float
    gold_auc_leave_anchor_out: float
    gold_perm_p: float
    adversarial_full_auc: float
    rarity_ok: bool
    raw_delta_dq: float = 0.0
    delta_ci_lower: float = 0.0
    delta_ci_upper: float = 0.0
    a2_residual_ci_lower: float = 0.0
    entropy_ok: bool = False
    evaluated_signal: bool = False


def rarity_ok(rep: CandidateReport) -> bool:
    return (
        rep.available
        and rep.gold_auc_full >= _c.AUC_FLOOR
        and rep.gold_auc_leave_anchor_out >= _c.AUC_FLOOR
    )


def decide(reports: Sequence[CandidateReport]) -> dict[str, Any]:
    scorer_ok_cands = [
        r.key for r in reports if rarity_ok(r) and r.entropy_ok and r.evaluated_signal
    ]
    rarity_only = [r.key for r in reports if rarity_ok(r)]
    scorer_ok = bool(scorer_ok_cands)
    # SIGNAL_PLAUSIBLE: a SCORER_OK candidate with a non-trivial exploratory effect
    # (upper CI reaches the raw DQ floor — symmetric with the §4.1 strong-absence rule).
    signal_cands = [
        r.key
        for r in reports
        if r.key in scorer_ok_cands and r.delta_ci_upper >= _c.DQ_FLOOR_RAW
    ]
    signal_plausible = bool(signal_cands)

    if scorer_ok and signal_plausible:
        verdict, direction = "PASS", "D"
    elif scorer_ok:
        verdict, direction = "SCORER_OK_SIGNAL_ABSENT", "B"
    else:
        verdict, direction = "NO_VALID_SCORER", "B"
    return {
        "verdict": verdict,
        "recommended_direction": direction,
        "scorer_ok": scorer_ok,
        "signal_plausible": signal_plausible,
        "scorer_ok_candidates": scorer_ok_cands,
        "rarity_ok_candidates": rarity_only,
        "signal_candidates": signal_cands,
        "auc_floor": _c.AUC_FLOOR,
        "dq_floor_raw": _c.DQ_FLOOR_RAW,
    }


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #
def _build_encoder_caches(
    encoder_specs: Sequence[tuple[str, str, EncoderFn | None]],
    to_embed: Sequence[str],
    full_ref_texts: Mapping[str, Sequence[str]],
    curated_texts: Mapping[str, Sequence[str]],
) -> tuple[
    dict[str, dict[str, np.ndarray]],
    dict[str, dict[str, np.ndarray]],
    dict[str, dict[str, np.ndarray]],
]:
    """Embed every needed string once per available encoder; cache reference rows."""
    embed_caches: dict[str, dict[str, np.ndarray]] = {}
    ref_caches_full: dict[str, dict[str, np.ndarray]] = {}
    ref_caches_curated: dict[str, dict[str, np.ndarray]] = {}
    for enc_key, _desc, enc in encoder_specs:
        if enc is None:
            continue
        vmap = embed_map(enc, to_embed)
        embed_caches[enc_key] = vmap
        ref_caches_full[enc_key] = {
            oid: np.asarray([vmap[t] for t in txts if t in vmap], dtype=float)
            for oid, txts in full_ref_texts.items()
        }
        ref_caches_curated[enc_key] = {
            oid: np.asarray([vmap[t] for t in txts if t in vmap], dtype=float)
            for oid, txts in curated_texts.items()
        }
    return embed_caches, ref_caches_full, ref_caches_curated


def _build_candidates(
    encoder_specs: Sequence[tuple[str, str, EncoderFn | None]],
    embed_caches: Mapping[str, dict[str, np.ndarray]],
    ref_caches_full: Mapping[str, dict[str, np.ndarray]],
    ref_caches_curated: Mapping[str, dict[str, np.ndarray]],
    full_ref_texts: Mapping[str, Sequence[str]],
    all_ref_texts: set[str],
    gold: Sequence[AdversarialItem],
) -> list[Candidate]:
    """The frozen, pre-declared candidate menu C0..C6 (Codex MED-2 ordering)."""
    candidates: list[Candidate] = []
    # C0 MPNet rarity max-agg, full reference (incumbent)
    c0 = _make_embed_candidate(
        "C0-mpnet-max-full",
        "MPNet 1-max cos, full R_object (incumbent)",
        embed_caches["mpnet"],
        ref_caches_full["mpnet"],
        "max",
    )
    candidates.append(c0)
    # C1 MPNet rarity mean-agg, full reference
    candidates.append(
        _make_embed_candidate(
            "C1-mpnet-mean-full",
            "MPNet 1-mean cos, full R_object",
            embed_caches["mpnet"],
            ref_caches_full["mpnet"],
            "mean",
        )
    )
    # C2 length-controlled C0
    candidates.append(_length_controlled(c0, gold))
    # C3 alt encoders (best-effort; skipped offline)
    for enc_key, desc, enc in encoder_specs[1:]:
        if enc is None:
            candidates.append(
                Candidate(
                    f"C3-{enc_key}-max-full",
                    f"{desc} 1-max cos, full R_object",
                    _zero_rarity,
                    available=False,
                )
            )
            continue
        candidates.append(
            _make_embed_candidate(
                f"C3-{enc_key}-max-full",
                f"{desc} 1-max cos, full R_object",
                embed_caches[enc_key],
                ref_caches_full[enc_key],
                "max",
            )
        )
    # C4 MPNet rarity max-agg, curated-only reference
    candidates.append(
        _make_embed_candidate(
            "C4-mpnet-max-curated",
            "MPNet 1-max cos, curated-only reference",
            embed_caches["mpnet"],
            ref_caches_curated["mpnet"],
            "max",
        )
    )
    # C5 lexical Jaccard novelty (encoder-free)
    candidates.append(
        Candidate(
            "C5-jaccard-full",
            "lexical 1-max token-Jaccard, full R_object",
            lambda obj, text, *, leave_anchor_out: jaccard_rarity(
                text, full_ref_texts.get(obj, ()), drop_dup=leave_anchor_out
            ),
        )
    )
    # C6 TF-IDF self-rarity vs reference corpus (encoder-free)
    corpus = sorted(all_ref_texts)
    idf = build_idf(corpus)
    default_idf = math.log((len(corpus) + 1) / 1.0) + 1.0 if corpus else 1.0
    candidates.append(
        Candidate(
            "C6-tfidf-selfrarity",
            "TF-IDF mean token rarity vs reference corpus",
            lambda obj, text, *, leave_anchor_out: tfidf_rarity(  # noqa: ARG005
                text, idf, default_idf
            ),
        )
    )
    return candidates


def _evaluate_candidate(
    cand: Candidate,
    gold: Sequence[AdversarialItem],
    gold_pair: Sequence[AdversarialItem],
    a0a2_gens: Sequence[dict[str, Any]],
    obj_human: Mapping[str, str],
    judge: Callable[[str, str], bool],
) -> CandidateReport:
    """Evaluate one candidate's RARITY_OK, then its Stage-2 signal if it clears it.

    RARITY_OK = gold good-vs-common on the full reference + leave-anchor-out audit.
    ENTROPY_OK + the exploratory A0/A2 signal are computed only for a RARITY_OK
    candidate, so candidate selection never touches the verdict data.
    """
    if not cand.available:
        return CandidateReport(
            cand.key,
            cand.description,
            available=False,
            gold_auc_full=0.0,
            gold_auc_leave_anchor_out=0.0,
            gold_perm_p=1.0,
            adversarial_full_auc=0.5,
            rarity_ok=False,
        )
    gr = gold_good_vs_common(cand, gold_pair)
    adv = adversarial_full_auc(cand, gold)
    rep = CandidateReport(
        cand.key,
        cand.description,
        available=True,
        gold_auc_full=gr.auc_full,
        gold_auc_leave_anchor_out=gr.auc_leave_anchor_out,
        gold_perm_p=gr.perm_p_full,
        adversarial_full_auc=adv,
        rarity_ok=False,
    )
    rep.rarity_ok = rarity_ok(rep)
    # Stage 2 (post-selection): evaluate ENTROPY_OK + signal only for a RARITY_OK
    # candidate, so candidate selection never touches the A0/A2 verdict data.
    if rep.rarity_ok:
        units = per_gen_dq(cand, a0a2_gens, obj_human, judge)
        sig = signal_and_entropy(units)
        rep.raw_delta_dq = sig.raw_delta_dq
        rep.delta_ci_lower = sig.delta_ci_lower
        rep.delta_ci_upper = sig.delta_ci_upper
        rep.a2_residual_ci_lower = sig.a2_residual_ci_lower
        rep.entropy_ok = sig.a2_survives
        rep.evaluated_signal = True
    return rep


def run_diagnostic(run_dir: Path) -> dict[str, Any]:
    aut = load_aut_battery()
    obj_human = {it.object_id: it.object for it in aut.items}
    curated = load_common_uses()
    gold = load_adversarial_labeled()

    gens = load_jsonl(run_dir / "generations.jsonl")
    judgements = load_jsonl(run_dir / "judgements.jsonl")
    judge = make_replay_judge(build_judge_map(judgements))

    aut_gens = [g for g in gens if g["task"] == "aut"]
    ref_gens = [g for g in aut_gens if g["condition"] == "REF"]
    a0a2_gens = [g for g in aut_gens if g["condition"] in {"A0", "A2"}]

    # --- reconstruct the incumbent R_object (MPNet, judge replayed) -----------
    mpnet = make_encoder("sentence-transformers/all-mpnet-base-v2")
    if mpnet is None:
        raise RuntimeError("MPNet encoder unavailable; the incumbent cannot be rebuilt")
    responses_by_object: dict[str, list[str]] = {oid: [] for oid in obj_human}
    for g in ref_gens:
        responses_by_object[g["item_id"]].append(g["response"])
    references = construct_all_references(
        curated, responses_by_object, obj_human, mpnet, judge
    )
    full_ref_texts = {oid: list(ref.texts) for oid, ref in references.items()}
    curated_texts = {oid: list(txts) for oid, txts in curated.items()}

    # --- collect every string each encoder must embed -------------------------
    gold_pair = [g for g in gold if g.category in {"good", "common_use_only"}]
    idea_strings: set[str] = set()
    for g in a0a2_gens:
        human = obj_human[g["item_id"]]
        idea_strings.update(valid_first_k(g["response"], human, judge))
    all_ref_texts = {t for txts in full_ref_texts.values() for t in txts}
    all_ref_texts |= {t for txts in curated_texts.values() for t in txts}
    to_embed = sorted(idea_strings | all_ref_texts | {g.text for g in gold})

    # --- build candidates (pre-declared order, Codex MED-2) -------------------
    encoder_specs: list[tuple[str, str, EncoderFn | None]] = [
        ("mpnet", "MPNet all-mpnet-base-v2 (incumbent)", mpnet),
        *(
            (mid.split("/")[-1], f"alt encoder {mid}", make_encoder(mid))
            for mid in _ALT_ENCODER_IDS
        ),
    ]
    embed_caches, ref_caches_full, ref_caches_curated = _build_encoder_caches(
        encoder_specs, to_embed, full_ref_texts, curated_texts
    )
    candidates = _build_candidates(
        encoder_specs,
        embed_caches,
        ref_caches_full,
        ref_caches_curated,
        full_ref_texts,
        all_ref_texts,
        gold,
    )
    incumbent = next(c for c in candidates if c.key == "C0-mpnet-max-full")

    reports = [
        _evaluate_candidate(cand, gold, gold_pair, a0a2_gens, obj_human, judge)
        for cand in candidates
    ]
    forensic = forensic_battery(incumbent, aut_gens, obj_human, judge)
    forensic["appropriateness_ok_judge_auc"] = (
        0.9125  # frozen verdict fact (judge fine)
    )
    decision = decide(reports)

    return {
        "task": "m13-es4-scorer-offline-diagnostic",
        "verdict": decision["verdict"],
        "recommended_direction": decision["recommended_direction"],
        "decision": decision,
        "forensic": forensic,
        "candidates": [asdict(r) for r in reports],
        "n_references": len(references),
        "alt_encoders_available": [
            k for k, _d, e in encoder_specs[1:] if e is not None
        ],
        "alt_encoders_skipped_offline": [
            k for k, _d, e in encoder_specs[1:] if e is None
        ],
    }


def _format_table(result: dict[str, Any]) -> str:
    header = (
        f"{'candidate':<32} {'avail':<5}  AUC_full  AUC_LAO  perm_p  "
        f"adv_auc  rarity_ok  a2_ci_lo  entropy_ok  raw_dDQ"
    )
    rows = ["", header]
    rows.extend(
        f"{r['key']:<32} {r['available']!s:<5}  "
        f"{r['gold_auc_full']:.3f}    {r['gold_auc_leave_anchor_out']:.3f}    "
        f"{r['gold_perm_p']:.3f}   {r['adversarial_full_auc']:.3f}    "
        f"{r['rarity_ok']!s:<5}      {r['a2_residual_ci_lower']:+.4f}   "
        f"{r['entropy_ok']!s:<5}       {r['raw_delta_dq']:+.4f}"
        for r in result["candidates"]
    )
    d = result["decision"]
    rows.append("")
    rows.append(
        f"VERDICT = {result['verdict']}  ->  direction "
        f"{result['recommended_direction']}  (scorer_ok={d['scorer_ok']}, "
        f"signal_plausible={d['signal_plausible']})"
    )
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="M13-ES4 offline scorer diagnostic")
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=Path("experiments/20260630-es4-phase0/phaseA"),
        help="persisted Phase A directory (generations/judgements/scores jsonl)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("experiments/20260701-es4-scorer-diag/diagnostic.json"),
    )
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):  # dDQ / ± on a cp932 console
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    result = run_diagnostic(args.run_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    sys.stdout.write(_format_table(result) + "\n")
    sys.stdout.write(f"\nwrote {args.out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Real backend seams + phase-flip replay orchestration for M13-ES4 (§7).

Session 1 built the LLM-free apparatus with four injectable seams
(:data:`scenario.InferenceFn`, :data:`scoring.EncoderFn`, :data:`scoring.JudgeFn`,
:data:`controls.ScoreFn`) and exercised them under deterministic mocks. This module
provides the **real** seams and the two-phase run that the ADR mandates, *without
touching the frozen apparatus*:

* **Phase A** (``run_phase_a``) — the SGLang fp8 ``qwen3:8b`` backend is up. Every
  LLM-dependent quantity is computed and persisted: the raw generation for every
  request (reference + AUT + RAT), the appropriateness ``judge`` decision for every
  degeneracy-passing idea of every reference/AUT generation, and the continuous
  ``score`` for every frozen adversarial labeled string. SGLang is then stopped.
* **phase-flip** — stopping the SGLang server frees the GPU. The MPNet encoder runs
  on CPU; empirically (Session 2) ``sentence-transformers`` + ``transformers``
  5.3.0 coexist for MPNet, and the replay seams never call SGLang at all, so the
  ADR §7 transformers conflict does not materialise (``decisions.md`` DA-PH0-1).
* **Phase B** (``run_phase_b``) — the persisted Phase-A outputs are replayed as
  *deterministic* seams (raw-text / judge-bool / adversarial-score lookups) and fed
  together with the live MPNet :func:`make_mpnet_encoder` into the **unchanged**
  :func:`pipeline.run_phase`. ``run_phase`` cannot tell a replay seam from a live
  one, so the frozen verdict logic runs verbatim.

Running Phase A under the **mock** seams and replaying through Phase B reproduces
the direct mock ``run_phase`` verdict byte-for-byte — the deterministic test of the
persist+replay round-trip (no GPU). The live SGLang seams are exercised by the real
smoke (no unit test, GPU-bound).

extras-only dependency discipline (3-point set, see ``pyproject.toml``):
``sentence-transformers`` is imported **lazily** inside :func:`make_mpnet_encoder`,
the mypy override already lists ``sentence_transformers.*``, and the encoder test
guards with ``pytest.importorskip``. SGLang is reached over plain HTTP (httpx) via
:class:`~erre_sandbox.inference.sglang_adapter.SGLangChatClient`, so no heavy import
is introduced here.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import httpx
import numpy as np

from erre_sandbox.evidence.es4_actuator import constants as _c
from erre_sandbox.evidence.es4_actuator.battery import (
    load_adversarial_labeled,
    load_aut_battery,
)
from erre_sandbox.evidence.es4_actuator.pipeline import assemble_references, run_phase
from erre_sandbox.evidence.es4_actuator.reference import build_reference_requests
from erre_sandbox.evidence.es4_actuator.scenario import (
    build_aut_requests,
    build_rat_requests,
)
from erre_sandbox.evidence.es4_actuator.scoring import parse_ideas, passes_degeneracy
from erre_sandbox.inference.ollama_adapter import ChatMessage
from erre_sandbox.inference.sampling import ResolvedSampling
from erre_sandbox.inference.sglang_adapter import (
    DEFAULT_SGLANG_MODEL,
    DEFAULT_SGLANG_VERSION,
    NO_LORA_SENTINEL,
    SGLangChatClient,
    SGLangUnavailableError,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from erre_sandbox.evidence.es4_actuator.scenario import (
        GenerationRequest,
        Phase,
    )
    from erre_sandbox.evidence.es4_actuator.scoring import EncoderFn
    from erre_sandbox.evidence.es4_actuator.verdict_report import Es4Verdict

_PERSONAS_DIR: Final[Path] = Path(__file__).resolve().parents[4] / "personas"
_THINK_RE: Final[re.Pattern[str]] = re.compile(
    r"<think>.*?</think>", re.DOTALL | re.IGNORECASE
)
_YES_RE: Final[re.Pattern[str]] = re.compile(r"^yes\b", re.IGNORECASE)

# temp=0 sampling for the binary judge + continuous score (deterministic).
JUDGE_SAMPLING: Final[ResolvedSampling] = ResolvedSampling(
    temperature=_c.TEMP_MIN, top_p=1.0, repeat_penalty=1.0
)
_THINK_OFF: Final[dict[str, Any]] = {"chat_template_kwargs": {"enable_thinking": False}}
_JUDGE_MAX_TOKENS: Final[int] = 8
_JUDGE_TOP_LOGPROBS: Final[int] = 20

_LIST_INSTRUCTION: Final[str] = (
    "When asked to list ideas, reply with a numbered list, one short concrete "
    "phrase per line. When asked for a single word, reply with only that word. "
    "Always answer in English. Output only what is asked — no preamble, no "
    "explanation, no chain-of-thought."
)
_NEUTRAL_REF_SYSTEM: Final[str] = "You are a helpful assistant. " + _LIST_INSTRUCTION
_JUDGE_SYSTEM: Final[str] = (
    "You evaluate candidate answers to an Alternate Uses Task. Reply with exactly "
    "one word: yes or no. No explanation, no chain-of-thought."
)


def _judge_user(obj: str, idea: str) -> str:
    return (
        f"Object: {obj}\n"
        f'Candidate use: "{idea}"\n'
        "Is this a coherent, on-task, appropriate use of the object (not nonsense, "
        "not off-topic, not a mere restatement of the object)? Answer yes or no."
    )


def strip_think(text: str) -> str:
    """Remove any ``<think>…</think>`` block (defence in depth; think is off)."""
    return _THINK_RE.sub("", text).strip()


def parse_yes(text: str) -> bool:
    """Binary judge parse: a leading 'yes' token → appropriate (not 'yesterday')."""
    return bool(_YES_RE.match(strip_think(text)))


def p_yes_from_logprobs(payload: dict[str, Any]) -> float | None:
    """P(yes) from the first content token's top_logprobs (yes-mass / (yes+no)).

    Returns ``None`` when the response carries no usable logprobs so the caller
    can fall back to the binary decision. This is the continuous "judge
    probability" the §2.3 adversarial AUC validates — the *same* binary judge the
    V-gate uses (Codex HIGH-2), not a separate scorer.
    """
    try:
        content = payload["choices"][0]["logprobs"]["content"]
        top = content[0]["top_logprobs"]
    except (KeyError, IndexError, TypeError):
        return None
    yes_mass = 0.0
    no_mass = 0.0
    for entry in top:
        tok = str(entry.get("token", "")).strip().lower()
        prob = math.exp(float(entry["logprob"]))
        if tok.startswith("yes"):
            yes_mass += prob
        elif tok.startswith("no"):
            no_mass += prob
    total = yes_mass + no_mass
    if total <= 0.0:
        return None
    return yes_mass / total


# --- live SGLang backend ------------------------------------------------------


class SglangBackend:
    """Sync seam provider over the SGLang OpenAI-compatible endpoint.

    Each call opens a short-lived :class:`SGLangChatClient` inside ``asyncio.run``;
    the per-call setup is negligible against GPU generation time and avoids
    cross-event-loop client reuse bugs. ``think`` is suppressed via
    ``chat_template_kwargs``; the SGLang sampling ``seed`` and ``max_tokens`` ride
    the ``options`` dict the adapter merges into the request body (no adapter
    change). Persona system prompts are loaded once from ``personas/*.yaml``.
    """

    def __init__(
        self,
        *,
        endpoint: str = SGLangChatClient.DEFAULT_ENDPOINT,
        model: str = DEFAULT_SGLANG_MODEL,
        timeout: float = 300.0,
    ) -> None:
        self.endpoint = endpoint
        self.model = model
        self.timeout = timeout
        self._sys_cache: dict[str, str] = {}

    # -- system prompts --
    def _system_prompt(self, persona_id: str) -> str:
        if persona_id in self._sys_cache:
            return self._sys_cache[persona_id]
        prompt = self._build_system_prompt(persona_id)
        self._sys_cache[persona_id] = prompt
        return prompt

    def _build_system_prompt(self, persona_id: str) -> str:
        if persona_id == "reference":
            return _NEUTRAL_REF_SYSTEM
        from erre_sandbox.evidence.source_navigator.compiler import (  # noqa: PLC0415
            load_persona_spec,
        )

        spec = load_persona_spec(_PERSONAS_DIR, persona_id)
        habits = "\n".join(
            f"- {h.description} [{h.flag.value}]"
            for h in list(spec.cognitive_habits)[:3]
        )
        return (
            f"You are {spec.display_name} ({spec.era}). Think and express ideas in "
            f"your own characteristic style.\nCognitive habits:\n{habits}\n\n"
            + _LIST_INSTRUCTION
        )

    # -- chat --
    def _chat(
        self,
        system: str,
        user: str,
        sampling: ResolvedSampling,
        *,
        seed: int,
        max_tokens: int,
    ) -> str:
        async def _run() -> str:
            async with SGLangChatClient(
                endpoint=self.endpoint, model=self.model, timeout=self.timeout
            ) as client:
                resp = await client.chat(
                    [
                        ChatMessage(role="system", content=system),
                        ChatMessage(role="user", content=user),
                    ],
                    sampling=sampling,
                    adapter=NO_LORA_SENTINEL,
                    options={**_THINK_OFF, "seed": seed, "max_tokens": max_tokens},
                )
                return str(resp.content)

        return asyncio.run(_run())

    # -- seams --
    def inference(self, request: GenerationRequest) -> str:
        return strip_think(
            self._chat(
                self._system_prompt(request.persona_id),
                request.prompt,
                request.resolved,
                seed=request.seed,
                max_tokens=request.num_predict,
            )
        )

    def _binary_judge(self, obj: str, text: str) -> tuple[bool, float]:
        """One binary appropriateness judge at **temperature 0** with logprobs.

        Returns ``(is_yes, p_yes)``. ``judge`` uses the bool, ``score`` uses the
        continuous P(yes) — the *same* judge the V-gate uses, so the adversarial
        AUC validates the actual gate (Codex HIGH-1 temp=0 via the direct body,
        HIGH-2 single scorer). Direct httpx so ``temperature=0`` and ``logprobs``
        bypass the ResolvedSampling clamp / the adapter (which has no logprobs).
        """
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _JUDGE_SYSTEM},
                {"role": "user", "content": _judge_user(obj, text)},
            ],
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": _JUDGE_MAX_TOKENS,
            "seed": 0,
            "logprobs": True,
            "top_logprobs": _JUDGE_TOP_LOGPROBS,
            "stream": False,
            **_THINK_OFF,
        }
        try:
            resp = httpx.post(
                f"{self.endpoint.rstrip('/')}/v1/chat/completions",
                json=body,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            payload = resp.json()
            content = str(payload["choices"][0]["message"]["content"])
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise SGLangUnavailableError(f"SGLang judge call failed: {exc!r}") from exc
        is_yes = parse_yes(content)
        p_yes = p_yes_from_logprobs(payload)
        if p_yes is None:  # logprobs absent → fall back to the binary decision
            p_yes = 1.0 if is_yes else 0.0
        return is_yes, p_yes

    def judge(self, obj: str, idea: str) -> bool:
        return self._binary_judge(obj, idea)[0]

    def score(self, obj: str, text: str) -> float:
        return self._binary_judge(obj, text)[1]

    def health_check(self) -> str:
        """Fail fast if SGLang cannot *generate* (a real one-token probe).

        SGLang's ``GET /health`` returns 503 on this Blackwell GPU even when
        generation works (the endpoint gates on an internal warmup), so the real
        readiness signal is a tiny generation. Returns the probe text; raises
        :class:`SGLangUnavailableError` if the call fails.
        """
        return self._chat(
            "Reply with exactly: ok",
            "ping",
            JUDGE_SAMPLING,
            seed=0,
            max_tokens=4,
        )


# --- MPNet encoder seam -------------------------------------------------------


def make_mpnet_encoder() -> EncoderFn:
    """Build the live MPNet ``EncoderFn`` → raw ``(N, D)`` embeddings (CPU).

    Reuses the canonical encoder id + e5-prefix logic from ``tier_b/vendi`` but
    returns the raw embedding matrix the es4 ``rarity`` consumes (the vendi kernel
    returns a Gram matrix, not embeddings). ``sentence-transformers`` is imported
    lazily (3-point set).
    """
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    from erre_sandbox.evidence.tier_b.vendi import (  # noqa: PLC0415
        DEFAULT_ENCODER_MODEL_ID,
        e5_passage_prefix,
        model_needs_e5_prefix,
    )

    model = SentenceTransformer(DEFAULT_ENCODER_MODEL_ID, device="cpu")
    needs_prefix = model_needs_e5_prefix(DEFAULT_ENCODER_MODEL_ID)
    prefix = e5_passage_prefix()
    dim = int(model.get_sentence_embedding_dimension() or 768)

    def encode(texts: Sequence[str]) -> np.ndarray:
        items = list(texts)
        if not items:
            return np.zeros((0, dim), dtype=float)
        inputs = [prefix + str(t) for t in items] if needs_prefix else items
        encoded = model.encode(inputs, show_progress_bar=False)
        return np.asarray(encoded, dtype=float)

    return encode


# --- persistence --------------------------------------------------------------

_GEN_FILE: Final[str] = "generations.jsonl"
_JUDGE_FILE: Final[str] = "judgements.jsonl"
_SCORE_FILE: Final[str] = "scores.jsonl"
_MANIFEST_FILE: Final[str] = "phase_a_manifest.json"


def _gen_key(req: GenerationRequest) -> str:
    return f"{req.task}|{req.persona_id}|{req.item_id}|{req.condition}|{req.seed_idx}"


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _write_jsonl(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    _atomic_write_text(
        path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@dataclass(frozen=True)
class PhaseAData:
    """The persisted Phase-A outputs the replay seams read back."""

    phase: Phase
    responses: dict[str, str]
    """``_gen_key(request) → raw response``."""
    judgements: dict[tuple[str, str], bool]
    """``(object, idea) → appropriate``."""
    scores: dict[tuple[str, str], float]
    """``(object, adversarial-text) → 0-10 score``."""
    manifest: dict[str, Any]


@dataclass
class ReplayMisses:
    """Replay coverage counters; all must be 0 (Phase A covered every query)."""

    inference: int = 0
    judge: int = 0
    score: int = 0

    @property
    def all_zero(self) -> bool:
        return self.inference == 0 and self.judge == 0 and self.score == 0


def _generate(
    requests: Sequence[GenerationRequest],
    inference_fn: Callable[[GenerationRequest], str],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    gen_rows: list[dict[str, Any]] = []
    responses: dict[str, str] = {}
    for req in requests:
        resp = inference_fn(req)
        responses[_gen_key(req)] = resp
        gen_rows.append(
            {
                "key": _gen_key(req),
                "persona_id": req.persona_id,
                "task": req.task,
                "item_id": req.item_id,
                "condition": req.condition,
                "seed": req.seed,
                "seed_idx": req.seed_idx,
                "num_predict": req.num_predict,
                # forensic (Codex HIGH-6): the exact resolved sampling actually
                # used + prompt + λ, so the irreversible run is reproducible.
                "temperature": req.resolved.temperature,
                "top_p": req.resolved.top_p,
                "repeat_penalty": req.resolved.repeat_penalty,
                "lam": req.lam,
                "prompt": req.prompt,
                "response": resp,
            }
        )
    return gen_rows, responses


def _judge_coverage(
    requests: Sequence[GenerationRequest],
    responses: dict[str, str],
    judge_fn: Callable[[str, str], bool],
) -> list[dict[str, Any]]:
    """Judge every degeneracy-passing idea of every reference/AUT generation.

    This is exactly the set ``score_generation`` + ``valid_ideas`` query in Phase
    B (same ``parse_ideas`` → ``passes_degeneracy`` pipeline), so the replay judge
    has full coverage.
    """
    obj_of = {it.object_id: it.object for it in load_aut_battery().items}
    judge_rows: list[dict[str, Any]] = []
    judged: dict[tuple[str, str], bool] = {}
    for req in requests:
        if req.task != "aut":
            continue
        obj = obj_of.get(req.item_id, req.item_id)
        for idea in parse_ideas(responses[_gen_key(req)]):
            if not passes_degeneracy(idea):
                continue
            key = (obj, idea)
            if key in judged:
                continue
            judged[key] = judge_fn(obj, idea)
            judge_rows.append({"object": obj, "idea": idea, "valid": judged[key]})
    return judge_rows


def _score_adversarial(
    score_fn: Callable[[str, str], float], max_adversarial: int | None
) -> list[dict[str, Any]]:
    """Score the frozen adversarial labeled set (``max_adversarial`` caps the smoke)."""
    score_rows: list[dict[str, Any]] = []
    scored: dict[tuple[str, str], float] = {}
    adversarial = load_adversarial_labeled()
    if max_adversarial is not None:
        adversarial = adversarial[:max_adversarial]
    for item in adversarial:
        key = (item.object, item.text)
        if key in scored:
            continue
        scored[key] = score_fn(item.object, item.text)
        score_rows.append(
            {"object": item.object, "text": item.text, "score": scored[key]}
        )
    return score_rows


def run_phase_a(
    inference_fn: Callable[[GenerationRequest], str],
    judge_fn: Callable[[str, str], bool],
    score_fn: Callable[[str, str], float],
    run_dir: Path,
    phase: Phase,
    *,
    smoke_filter: Callable[[GenerationRequest], bool] | None = None,
    max_adversarial: int | None = None,
    overwrite: bool = False,
    extra_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate + judge + score everything Phase B will query, and persist it.

    Works with any seams (mock or live ``SglangBackend`` methods). Returns the
    manifest dict (also written to ``run_dir``). Refuses a run dir that already
    holds a manifest unless ``overwrite`` (Codex MEDIUM-1: never silently mix a
    half-finished run's data).
    """
    existing = run_dir / _MANIFEST_FILE
    if existing.exists() and not overwrite:
        raise FileExistsError(
            f"{existing} exists; pass overwrite=True to replace this run dir"
        )
    run_dir.mkdir(parents=True, exist_ok=True)
    requests = [
        *build_reference_requests(),
        *build_aut_requests(phase),
        *build_rat_requests(phase),
    ]
    if smoke_filter is not None:
        requests = [r for r in requests if smoke_filter(r)]

    start = time.monotonic()
    gen_rows, responses = _generate(requests, inference_fn)
    judge_rows = _judge_coverage(requests, responses, judge_fn)
    score_rows = _score_adversarial(score_fn, max_adversarial)
    wall_clock_s = time.monotonic() - start

    _write_jsonl(run_dir / _GEN_FILE, gen_rows)
    _write_jsonl(run_dir / _JUDGE_FILE, judge_rows)
    _write_jsonl(run_dir / _SCORE_FILE, score_rows)
    manifest: dict[str, Any] = {
        "phase": phase,
        "n_generations": len(gen_rows),
        "n_judgements": len(judge_rows),
        "n_scores": len(score_rows),
        "wall_clock_s": wall_clock_s,
        "smoke": smoke_filter is not None,
        "sglang_version": DEFAULT_SGLANG_VERSION,
        "model": DEFAULT_SGLANG_MODEL,
        **(extra_manifest or {}),
    }
    _atomic_write_text(
        run_dir / _MANIFEST_FILE, json.dumps(manifest, indent=2, ensure_ascii=False)
    )
    return manifest


def load_phase_a(run_dir: Path) -> PhaseAData:
    """Read the persisted Phase-A outputs back into a :class:`PhaseAData`."""
    manifest = json.loads((run_dir / _MANIFEST_FILE).read_text(encoding="utf-8"))
    responses = {r["key"]: r["response"] for r in _read_jsonl(run_dir / _GEN_FILE)}
    judgements = {
        (r["object"], r["idea"]): bool(r["valid"])
        for r in _read_jsonl(run_dir / _JUDGE_FILE)
    }
    scores = {
        (r["object"], r["text"]): float(r["score"])
        for r in _read_jsonl(run_dir / _SCORE_FILE)
    }
    return PhaseAData(
        phase=manifest["phase"],
        responses=responses,
        judgements=judgements,
        scores=scores,
        manifest=manifest,
    )


def build_replay_seams(
    data: PhaseAData,
) -> tuple[
    Callable[[GenerationRequest], str],
    Callable[[str, str], bool],
    Callable[[str, str], float],
    ReplayMisses,
]:
    """Deterministic seams backed by the persisted Phase-A outputs.

    A miss (a query Phase A did not cover) is counted and falls back to a worst
    value; the caller asserts :attr:`ReplayMisses.all_zero` after the pipeline.
    """
    misses = ReplayMisses()

    def inference_fn(req: GenerationRequest) -> str:
        key = _gen_key(req)
        if key not in data.responses:
            misses.inference += 1
            return ""
        return data.responses[key]

    def judge_fn(obj: str, idea: str) -> bool:
        key = (obj, idea)
        if key not in data.judgements:
            misses.judge += 1
            return False
        return data.judgements[key]

    def score_fn(obj: str, text: str) -> float:
        key = (obj, text)
        if key not in data.scores:
            misses.score += 1
            return 0.0
        return data.scores[key]

    return inference_fn, judge_fn, score_fn, misses


def _persona_separation(data: PhaseAData, encoder_fn: EncoderFn) -> dict[str, float]:
    """Cross-persona register separation forensic (Codex HIGH-3, measurement only).

    Mean / min pairwise cosine distance between per-persona centroids of the valid
    AUT ideas. This is a *forensic* proxy for persona separation; the gating
    ``persona_collapse`` (a Burrows Δ threshold) is **deferred** until a superseding
    ADR pre-registers the threshold (blockers.md B-6), so this never drives the
    verdict — it only records whether the personas are stylistically distinct.
    """
    by_persona: dict[str, list[str]] = {}
    for key, resp in data.responses.items():
        task, persona_id, item_id, condition, _seed = key.split("|")
        if task != "aut" or condition == "REF":
            continue
        for idea in parse_ideas(resp):
            if passes_degeneracy(idea) and data.judgements.get((item_id, idea), False):
                by_persona.setdefault(persona_id, []).append(idea)
    centroids: list[np.ndarray] = []
    for ideas in by_persona.values():
        emb = np.asarray(encoder_fn(ideas), dtype=float)
        if emb.size == 0:
            continue
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        unit = emb / np.where(norms == 0.0, 1.0, norms)
        centroids.append(unit.mean(axis=0))
    if len(centroids) < 2:  # noqa: PLR2004 — need a pair to separate
        return {"persona_sep_min": float("nan"), "persona_sep_mean": float("nan")}
    dists: list[float] = []
    for i in range(len(centroids)):
        for j in range(i + 1, len(centroids)):
            a, b = centroids[i], centroids[j]
            denom = float(np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
            dists.append(1.0 - float(a @ b) / denom)
    return {
        "persona_sep_min": float(np.min(dists)),
        "persona_sep_mean": float(np.mean(dists)),
    }


def run_phase_b(
    run_dir: Path,
    encoder_fn: EncoderFn,
    *,
    projected_gpu_hours: float | None = None,
    bootstrap_seed: int = 0,
) -> tuple[Es4Verdict, ReplayMisses, dict[str, Any]]:
    """Replay the persisted Phase-A outputs through the unchanged ``run_phase``.

    The replay seams + the live ``encoder_fn`` are handed to the frozen pipeline;
    the returned :class:`ReplayMisses` must be ``all_zero`` for a valid run. The
    third return value is a forensic ``extras`` dict (R_object content hashes,
    persona-separation, and the **total-inclusive** GPU-hour budget, Codex
    HIGH-3/5/6). ``projected_gpu_hours=None`` computes the total-inclusive Phase-0
    budget (Phase A wall-clock + this Phase B); pass a value to override.
    """
    data = load_phase_a(run_dir)
    inference_fn, judge_fn, score_fn, misses = build_replay_seams(data)

    t0 = time.monotonic()
    # forensic: rebuild R_object via the replay seams to record content hashes.
    references = assemble_references(inference_fn, encoder_fn, judge_fn)
    ref_hashes = {obj: ref.content_hash for obj, ref in references.items()}
    separation = _persona_separation(data, encoder_fn)

    phase_a_s = float(data.manifest.get("wall_clock_s", 0.0))
    if projected_gpu_hours is None:
        # rough total-inclusive Phase-0 GPU-hours (Phase A gen+judge+score already
        # measured; Phase B encode+score+verdict measured below after run_phase).
        budget = (phase_a_s + (time.monotonic() - t0)) / 3600.0
    else:
        budget = projected_gpu_hours

    verdict = run_phase(
        data.phase,
        inference_fn,
        encoder_fn,
        judge_fn,
        score_fn,
        projected_gpu_hours=budget,
        bootstrap_seed=bootstrap_seed,
    )
    phase_b_s = time.monotonic() - t0
    extras: dict[str, Any] = {
        "r_object_hashes": ref_hashes,
        "n_references": len(ref_hashes),
        **separation,
        "phase_a_wall_clock_s": phase_a_s,
        "phase_b_wall_clock_s": phase_b_s,
        "phase0_total_gpu_hours": (phase_a_s + phase_b_s) / 3600.0,
        "replay_misses": vars(misses),
    }
    return verdict, misses, extras


__all__ = [
    "JUDGE_SAMPLING",
    "PhaseAData",
    "ReplayMisses",
    "SglangBackend",
    "build_replay_seams",
    "load_phase_a",
    "make_mpnet_encoder",
    "p_yes_from_logprobs",
    "parse_yes",
    "run_phase_a",
    "run_phase_b",
    "strip_think",
]

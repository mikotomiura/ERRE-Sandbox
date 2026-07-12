#!/usr/bin/env python
"""M4 society live-capture CLI — Issue 002 (I2) apparatus (real run is Issue 004).

Design-copy (not import — ``scripts/ecl_v0_live_capture.py`` stays untouched,
design-final.md §B mirror table) of the ECL v0 live-capture CLI's ``--capture``/
``--verify`` pair, retargeted at the society-scope harness landed in Issue 001
(``integration/embodied/society_live.py``): where the ECL CLI wraps one
``inner_chat`` and drives ``run_ecl_loop``, this script wraps one ``inner_chat``
**per agent**
(:data:`~erre_sandbox.integration.embodied.society_live.SOCIETY_LIVE_AGENT_IDS`)
and drives :func:`~erre_sandbox.integration.embodied.society.run_society_loop`
via
:func:`~erre_sandbox.integration.embodied.society_live.run_society_live_capture`
(both imported and called, never modified).

``--capture`` (Issue 004, G-GEAR real Ollama, **here-untested**): builds one real
:class:`~erre_sandbox.inference.ollama_adapter.OllamaChatClient` per agent (the
only live piece) plus a shared constant-vector mock embedding, drives one
record-mode society run, renders the four handoff artifacts (``manifest.json``
with the society live env-pin + annotations overlay, ``ecl_trace.jsonl``,
``decisions.jsonl``, ``envelope_stream.jsonl``) via
:func:`~erre_sandbox.integration.embodied.handoff.render_society_golden` +
:func:`~erre_sandbox.integration.embodied.society_live.attach_society_live_observables`,
and derives ``expected_placement.jsonl`` (design-copy of
``tests/test_integration/test_m4_society_replay.py``'s
``build_expected_placement``, operating on the freshly-rendered artifact text
directly rather than re-reading from disk). ``--capture`` is import-lazy (no
live connection at import time) and is exercised for real only in Issue 004 —
this issue (I2) never invokes it.

``--verify`` (Ollama-free, CI/WSL-safe) is this issue's (I2) core apparatus:

* **R3 decoder** (:func:`society_recorded_calls_from_jsonl`) — the from-jsonl
  per-agent decoder ``handoff.py`` never needed for a single-agent run
  (``handoff.recorded_calls_from_jsonl`` is flat, no agent identity). It
  groups committed ``decisions.jsonl`` rows by ``agent_id`` in **physical line
  order** (the one true per-agent replay order), validates every row
  fail-closed (Codex HIGH-1: duplicate ``(agent_id, agent_tick)``, unknown
  ``agent_id``, ``order_slot`` inconsistent with the ``sorted(agent_ids)``
  roster, missing rows / incomplete tick-slots), then re-serialises each
  agent's ``decision`` sub-dict (itself an unmodified flat
  ``handoff.decision_to_dict`` payload) back into the exact per-line shape
  ``handoff.recorded_calls_from_jsonl`` already parses and **delegates to it**
  (Codex HIGH-2 — no independent re-implementation, so a future
  ``RecordedLlmCall``/outcome-union schema change only has one parser to keep
  in sync).
* :func:`verify` replays committed ``decisions.jsonl`` through
  :func:`~erre_sandbox.integration.embodied.society.run_society_loop` with
  **exactly** the three
  :data:`~erre_sandbox.integration.embodied.society_live.SOCIETY_LIVE_AGENT_IDS`
  keys (Codex HIGH-3 — the decoder's ``expected_agent_ids`` fail-closed check
  guarantees this, so no client can silently fall back to a live LLM on a
  key mismatch), asserts every replay client's ``inner_invocations == 0``, the
  replay/event-log checksums match, every per-artifact SHA-256 matches, **and**
  (Codex HIGH-5, the ECL verify peer) re-renders ``manifest.json`` itself
  through the exact same pipeline :func:`capture` used — reusing the
  **committed manifest's** ``env_pins``/``run`` block, never a fresh capture —
  so a drifted/stale committed manifest cannot vacuously pass. It also asserts
  (Codex HIGH-4) the committed ``fixed_constructor_fingerprint`` matches a
  fresh recomputation, and (Codex M1) structural completeness: exactly the
  three pinned agents, the pinned 12-tick horizon, and every agent's decision/
  call count equal to that horizon.

Scope guard (design-final.md §F, binding, mirrors ``ecl_v0_live_capture.py`` /
``society_live.py``). This is a *construction* apparatus, **NOT a measurement
line**. It imports no ``evidence`` / ``spdm`` / ``runningness`` machinery and
computes/emits no floor / landscape / verdict / divergence statistic.
"""

# ruff: noqa: T201, C901, PLR0912, PLR0915
# T201 (print): a CLI's entire job is human-readable stdout status lines
# (mirrors scripts/ecl_v0_live_capture.py, not itself ruff-checked by CI —
# `pre-push-check` only lints `src tests` — but this file is checked directly
# per Issue 002's own Done gate, so the exemption is explicit here rather than
# silently unenforced).
# C901/PLR0912/PLR0915 (verify complexity): verify() is an intentionally
# linear checklist mirroring ecl_v0_live_capture.py's verify() step order
# (O3a/O3b/HIGH-4/HIGH-5/M1) — splitting it into sub-functions would obscure
# the single ordered contract a reader needs to audit, trading one legible
# function for several out-of-order fragments.

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import httpx

from erre_sandbox.cognition.embodiment import K_ECL
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.live import LIVE_MODEL
from erre_sandbox.integration.embodied.loop import (
    DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    RecordedLlmCall,
    RecordReplayChatClient,
)
from erre_sandbox.integration.embodied.society import run_society_loop
from erre_sandbox.integration.embodied.society_live import (
    SOCIETY_LIVE_AGENT_IDS,
    SOCIETY_LIVE_N_COGNITION_TICKS,
    SOCIETY_LIVE_RUN_ID,
    attach_society_live_observables,
    build_society_live_env_pins,
    fixed_constructor_fingerprint,
    run_society_live_capture,
    society_live_agent_states,
    society_live_observation_factories,
    society_live_observation_factory,
    society_live_personas,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.integration.embodied.society import SocietyRunResult

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT_DIR = _REPO_ROOT / "tests" / "fixtures" / "m4_society_live_golden"

# --------------------------------------------------------------------------- #
# R3 — per-agent from-jsonl decoder (Codex HIGH-1/HIGH-2, handoff.py untouched)
# --------------------------------------------------------------------------- #


def society_recorded_calls_from_jsonl(
    text: str,
    *,
    expected_agent_ids: Sequence[str] | None = None,
) -> dict[str, list[RecordedLlmCall]]:
    """Reconstruct one replay stream per agent from a committed society JSONL.

    Each line of ``decisions.jsonl`` (:func:`handoff.build_society_decisions_stream`)
    is ``{"order_slot": int, "agent_id": str, "decision": {...}}`` where
    ``decision`` is an unmodified flat ``handoff.decision_to_dict`` payload
    (itself carrying ``agent_tick`` and ``call``). This function:

    1. Groups rows by ``agent_id`` in **physical line order** — the one true
       per-agent replay order (Codex HIGH-1: ``order_slot`` is used *only* to
       validate agent ordering below, never as the grouping/ordering key
       itself).
    2. Fail-closed validates (raises ``ValueError``, construction-time, not
       mid-replay): unknown ``agent_id`` / missing expected agent (when
       ``expected_agent_ids`` is given), duplicate ``(agent_id, agent_tick)``
       pairs, ``order_slot`` inconsistent with the ``sorted(agent_ids)``
       roster, and incomplete tick-slots (an ``agent_tick`` that some but not
       all roster agents reported — an insufficient-rows failure).
    3. Re-serialises each agent's ``decision`` sub-dict back into the exact
       per-line shape ``handoff.recorded_calls_from_jsonl`` already parses
       (``json.loads(line)["call"]``) and **delegates to it** (Codex HIGH-2 —
       no independent ``RecordedLlmCall`` reconstruction in this module).

    ``expected_agent_ids`` is optional so this helper is independently testable
    against arbitrary agent rosters (fail-closed test bundles); :func:`verify`
    always passes :data:`SOCIETY_LIVE_AGENT_IDS` (Codex HIGH-3 — the exact
    three-agent key set a replay-only ``RecordReplayChatClient`` mapping needs
    so a key mismatch cannot silently fall back to a live LLM).
    """
    parsed: list[tuple[str, int, int, dict[str, Any]]] = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        entry = json.loads(raw_line)
        agent_id = entry["agent_id"]
        order_slot = entry["order_slot"]
        decision = entry["decision"]
        agent_tick = decision["agent_tick"]
        parsed.append((agent_id, order_slot, agent_tick, decision))

    known_agent_ids = (
        set(expected_agent_ids) if expected_agent_ids is not None else None
    )
    discovered_agent_ids = {row[0] for row in parsed}

    if known_agent_ids is not None:
        unknown = sorted(discovered_agent_ids - known_agent_ids)
        if unknown:
            msg = f"unknown agent_id(s) in society decisions stream: {unknown}"
            raise ValueError(msg)
        missing = sorted(known_agent_ids - discovered_agent_ids)
        if missing:
            msg = (
                "missing agent_id(s) in society decisions stream (insufficient "
                f"rows): {missing}"
            )
            raise ValueError(msg)
        roster = sorted(known_agent_ids)
    else:
        roster = sorted(discovered_agent_ids)

    expected_slot = {agent_id: slot for slot, agent_id in enumerate(roster)}

    seen_pairs: set[tuple[str, int]] = set()
    ticks_by_agent: dict[str, set[int]] = {agent_id: set() for agent_id in roster}
    decision_lines_by_agent: dict[str, list[str]] = {
        agent_id: [] for agent_id in roster
    }

    for agent_id, order_slot, agent_tick, decision in parsed:
        if order_slot != expected_slot[agent_id]:
            msg = (
                f"order_slot {order_slot} for agent_id {agent_id!r} does not "
                f"match sorted-roster expected slot {expected_slot[agent_id]}"
            )
            raise ValueError(msg)
        pair = (agent_id, agent_tick)
        if pair in seen_pairs:
            msg = f"duplicate (agent_id, agent_tick) pair in decisions stream: {pair}"
            raise ValueError(msg)
        seen_pairs.add(pair)
        ticks_by_agent[agent_id].add(agent_tick)
        decision_lines_by_agent[agent_id].append(handoff.canonical_dumps(decision))

    all_ticks: set[int] = set()
    for ticks in ticks_by_agent.values():
        all_ticks |= ticks
    for agent_id in roster:
        gap = sorted(all_ticks - ticks_by_agent[agent_id])
        if gap:
            msg = (
                f"agent_id {agent_id!r} missing decision(s) for agent_tick(s) "
                f"{gap} (insufficient rows, tick-slot incomplete)"
            )
            raise ValueError(msg)

    return {
        agent_id: handoff.recorded_calls_from_jsonl(
            "\n".join(decision_lines_by_agent[agent_id]) + "\n"
        )
        for agent_id in roster
    }


# --------------------------------------------------------------------------- #
# expected_placement.jsonl derivation (design-copy of test_m4_society_replay's
# build_expected_placement, operating on in-memory rendered text)
# --------------------------------------------------------------------------- #

_FIRING_KINDS: Final[frozenset[str]] = frozenset({"speech", "animation"})


def _read_jsonl_text(text: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def build_expected_placement(trace_jsonl: str, stream_jsonl: str) -> str:
    """Derive the ``expected_placement.jsonl`` text from rendered artifacts.

    Design-copy of ``tests/test_integration/test_m4_society_replay.py``'s
    ``build_expected_placement`` (that helper takes ``Path`` args and is test
    module private; this variant takes the already-rendered JSONL text
    :func:`capture` holds in memory, avoiding a redundant file round-trip).
    Placement rows come from ``ecl_trace.jsonl`` sorted by
    ``(physics_tick_index, order_slot)``; envelope rows come from
    ``envelope_stream.jsonl`` (speech/animation only) sorted by
    ``(order_slot, agent_tick, seq)``. This function is exercised for real
    only in Issue 004 (``--capture``, here-untested in I2).
    """
    placements: list[dict[str, Any]] = [
        {
            "kind": "placement",
            "physics_tick_index": int(row["physics_tick_index"]),
            "order_slot": int(row["order_slot"]),
            "x": row["x"],
            "y": row["y"],
            "z": row["z"],
            "yaw": row["yaw"],
            "zone": row["zone"],
        }
        for row in _read_jsonl_text(trace_jsonl)
    ]
    placements.sort(key=lambda d: (d["physics_tick_index"], d["order_slot"]))

    envelopes: list[dict[str, Any]] = []
    for row in _read_jsonl_text(stream_jsonl):
        envelope = row["envelope"]
        kind = envelope["kind"]
        if kind not in _FIRING_KINDS:
            continue
        envelopes.append(
            {
                "kind": "envelope",
                "order_slot": int(row["order_slot"]),
                "agent_tick": int(row["agent_tick"]),
                "seq": int(row["seq"]),
                "envelope_kind": kind,
            }
        )
    envelopes.sort(key=lambda d: (d["order_slot"], d["agent_tick"], d["seq"]))

    return "".join(
        f"{handoff.canonical_dumps(row)}\n" for row in (*placements, *envelopes)
    )


# --------------------------------------------------------------------------- #
# Deterministic correction of society_live.py's constructor fingerprint
# (society_live.py untouched — this is a CLI-owned override of one sub-field)
# --------------------------------------------------------------------------- #


def _observation_factory_fingerprint_deterministic(
    agent_ids: Sequence[str] = SOCIETY_LIVE_AGENT_IDS,
) -> str:
    """A deterministic peer of ``society_live``'s ``observation_factories_sha256``.

    ``society_live.society_live_observation_factory``'s tick-0
    ``PerceptionEvent`` carries a ``wall_clock`` field defaulted via
    ``schemas._ObservationBase``'s ``default_factory=_utc_now`` — a
    non-deterministic value that leaks into
    ``society_live.fixed_constructor_fingerprint``'s
    ``observation_factories_sha256`` component (discovered empirically while
    building this issue's ``--verify`` apparatus: two back-to-back calls of
    ``fixed_constructor_fingerprint`` in the *same process* already disagree
    on that one sub-field — see
    ``tests/test_integration/test_m4_society_live.py::test_fixed_constructors_fingerprint``,
    an Issue 001 test unmodified here). ``society_live.py`` is untouched (I2
    Allowed Files scope, ``無改変厳守``); this CLI-owned helper reproduces the
    exact same factory-name/version/tick-0-observation shape but excludes
    ``wall_clock`` before hashing, so :func:`_corrected_fixed_constructor_fingerprint`
    below — used by both :func:`capture` (what gets pinned into ``env_pins``)
    and :func:`verify` (what gets recomputed and asserted against it) — is
    actually stable across processes, restoring the drift-detection Codex
    HIGH-4 intended.
    """
    factories = society_live_observation_factories(agent_ids)
    payload = {
        agent_id: {
            "factory": (
                f"{society_live_observation_factory.__module__}."
                f"{society_live_observation_factory.__qualname__}"
            ),
            "factory_version": 1,
            "tick0_observation": [
                obs.model_dump(mode="json", exclude={"wall_clock"})
                for obs in factories[agent_id](0)
            ],
        }
        for agent_id in agent_ids
    }
    blob = handoff.canonical_dumps(payload).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _agent_states_fingerprint_deterministic(agent_states: Sequence[Any]) -> str:
    """A deterministic peer of ``society_live``'s ``agent_states_sha256``.

    ``schemas.AgentState`` also carries a ``wall_clock: datetime =
    Field(default_factory=_utc_now)`` field (same root cause as
    :func:`_observation_factory_fingerprint_deterministic`'s docstring),
    which likewise leaks non-determinism into
    ``society_live.fixed_constructor_fingerprint``'s ``agent_states_sha256``
    (confirmed empirically). Excludes ``wall_clock`` before hashing.
    """
    payload = [
        state.model_dump(mode="json", exclude={"wall_clock"}) for state in agent_states
    ]
    blob = handoff.canonical_dumps(payload).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _corrected_fixed_constructor_fingerprint(
    *,
    agent_states: Sequence[Any],
    personas: Any,
    agent_ids: Sequence[str] = SOCIETY_LIVE_AGENT_IDS,
) -> dict[str, str]:
    """:func:`fixed_constructor_fingerprint` with deterministic sub-fields.

    ``personas_sha256`` is already deterministic (``PersonaSpec`` carries no
    wall-clock field) and is reused verbatim from
    ``society_live.fixed_constructor_fingerprint``; ``agent_states_sha256``
    and ``observation_factories_sha256`` are overridden with this module's
    wall-clock-excluding recomputations (both discovered non-deterministic
    while building this issue's ``--verify`` apparatus).
    """
    fingerprint = dict(
        fixed_constructor_fingerprint(
            agent_states=agent_states, personas=personas, agent_ids=agent_ids
        )
    )
    fingerprint["agent_states_sha256"] = _agent_states_fingerprint_deterministic(
        agent_states
    )
    fingerprint["observation_factories_sha256"] = (
        _observation_factory_fingerprint_deterministic(agent_ids)
    )
    return fingerprint


# --------------------------------------------------------------------------- #
# Shared Ollama-free mock embedding (design-copy of ecl_v0_live_capture's)
# --------------------------------------------------------------------------- #


def _mock_embedding() -> EmbeddingClient:
    """A constant-vector embedding — deterministic and Ollama-free (D-4)."""
    vec = [0.01] * EmbeddingClient.DEFAULT_DIM

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        inputs = body.get("input") or []
        count = len(inputs) if isinstance(inputs, list) else 1
        return httpx.Response(httpx.codes.OK, json={"embeddings": [vec] * count})

    return EmbeddingClient(
        client=httpx.AsyncClient(
            base_url=EmbeddingClient.DEFAULT_ENDPOINT,
            transport=httpx.MockTransport(handler),
        )
    )


# --------------------------------------------------------------------------- #
# --capture (Issue 004, real Ollama, here-untested in I2)
# --------------------------------------------------------------------------- #


async def capture(
    *,
    run_id: str,
    seed: int,
    n_cognition_ticks: int,
    physics_ticks_per_cognition: int,
    qwen3_model_digest: str,
    ollama_version: str,
    vram_gb: float,
    uv_lock_sha256: str,
) -> tuple[SocietyRunResult, dict[str, str]]:
    """Drive one society live-capture run and render the four handoff artifacts.

    Builds one real ``OllamaChatClient`` per agent (the sole live piece, lazily
    imported so a bare ``import`` of this module never requires Ollama
    reachability) plus a shared mock embedding, runs
    :func:`run_society_live_capture`, then renders the artifacts via
    ``handoff.render_society_golden`` plus the society live env-pin +
    annotations overlay ``society_live.py`` (Issue 001) owns. Does not write
    anything to disk — the caller (``main``) does that.
    """
    # Deliberately lazy (Codex-style D-4 precedent, ecl_v0_live_capture.py):
    # a bare `import` of this module must never require Ollama reachability.
    from erre_sandbox.inference.ollama_adapter import (  # noqa: PLC0415
        OllamaChatClient,
    )

    now = datetime.now(UTC)
    agent_states = society_live_agent_states()
    personas = society_live_personas()
    inner_chats = {
        agent_id: OllamaChatClient(model=LIVE_MODEL)
        for agent_id in SOCIETY_LIVE_AGENT_IDS
    }
    embedding = _mock_embedding()
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    try:
        result = await run_society_live_capture(
            inner_chats=inner_chats,
            store=store,
            embedding=embedding,
            run_id=run_id,
            agent_states=agent_states,
            personas=personas,
            retrieval_now=now,
            base_ts=now,
            seed=seed,
            n_cognition_ticks=n_cognition_ticks,
            physics_ticks_per_cognition=physics_ticks_per_cognition,
            observation_factories=society_live_observation_factories(),
        )
    finally:
        for client in inner_chats.values():
            await client.close()
        await embedding.close()
        await store.close()

    first_agent = SOCIETY_LIVE_AGENT_IDS[0]
    resolved_sampling = result.decisions[first_agent][0].call.sampling
    env_pins = build_society_live_env_pins(
        qwen3_model_digest=qwen3_model_digest,
        ollama_version=ollama_version,
        vram_gb=vram_gb,
        uv_lock_sha256=uv_lock_sha256,
        resolved_sampling=resolved_sampling,
        agent_states=agent_states,
        personas=personas,
        run_id=run_id,
        n_cognition_ticks=n_cognition_ticks,
        seed=seed,
    )
    # I2-owned additive witness field (script-local, not a society_live.py /
    # handoff.py schema change): lets --verify assert the replayed
    # event_log_checksum against the one the capture actually produced,
    # rather than only ever recomputing it fresh with nothing committed to
    # compare against.
    env_pins["captured_event_log_checksum"] = result.event_log_checksum
    # Override the non-deterministic observation_factories_sha256 sub-field
    # (see _corrected_fixed_constructor_fingerprint docstring) so a later
    # --verify recomputation can actually match.
    env_pins["fixed_constructor_fingerprint"] = (
        _corrected_fixed_constructor_fingerprint(
            agent_states=agent_states, personas=personas
        )
    )
    run_config = {
        "seed": seed,
        "physics_ticks_per_cognition": physics_ticks_per_cognition,
        "k_ecl": K_ECL,
        "base_ts": now.isoformat(),
        "retrieval_now": now.isoformat(),
    }
    rendered = handoff.render_society_golden(
        result, run_config=run_config, env_pins=env_pins
    )
    manifest = json.loads(rendered["manifest.json"])
    rendered["manifest.json"] = (
        handoff.canonical_dumps(attach_society_live_observables(manifest)) + "\n"
    )
    rendered["expected_placement.jsonl"] = build_expected_placement(
        rendered["ecl_trace.jsonl"], rendered["envelope_stream.jsonl"]
    )
    return result, rendered


def _write(out_dir: Path, rendered: dict[str, str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, text in rendered.items():
        # M4 (decisions.md): explicit newline="\n" so Windows write does not
        # introduce CRLF into a committed fixture (existing ECL contract).
        (out_dir / filename).write_text(text, encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------- #
# --verify (Ollama-free, CI/WSL-safe — this issue's (I2) core apparatus)
# --------------------------------------------------------------------------- #


async def verify(artifact_dir: Path) -> bool:
    """Ollama-free replay-verify of a committed society live-capture bundle.

    See module docstring for the full HIGH-1..HIGH-5/M1 checklist this
    reproduces; computes no floor / landscape / verdict / divergence
    statistic (measurement-line non-re-entry).
    """
    manifest_text = (artifact_dir / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    decisions_text = (artifact_dir / "decisions.jsonl").read_text(encoding="utf-8")
    trace_text = (artifact_dir / "ecl_trace.jsonl").read_text(encoding="utf-8")
    envelope_text = (artifact_dir / "envelope_stream.jsonl").read_text(encoding="utf-8")
    run_config = manifest["run"]
    env_pins = manifest["env_pins"]

    ok = True

    # Codex HIGH-4 — fixed-constructor fingerprint assert.
    agent_states = society_live_agent_states()
    personas = society_live_personas()
    observation_factories = society_live_observation_factories()
    fresh_fp = _corrected_fixed_constructor_fingerprint(
        agent_states=agent_states, personas=personas
    )
    committed_fp = env_pins.get("fixed_constructor_fingerprint")
    if fresh_fp != committed_fp:
        ok = False
        print(
            f"[verify] FAIL fixed_constructor_fingerprint mismatch: "
            f"{fresh_fp} != {committed_fp}"
        )
    else:
        print("[verify] OK fixed_constructor_fingerprint matches")

    # R3 decoder (Codex HIGH-1/HIGH-2) + Codex HIGH-3 (exact 3-agent key set,
    # no live fallback possible).
    recorded = society_recorded_calls_from_jsonl(
        decisions_text, expected_agent_ids=SOCIETY_LIVE_AGENT_IDS
    )
    llms = {
        agent_id: RecordReplayChatClient(recorded=recorded[agent_id])
        for agent_id in SOCIETY_LIVE_AGENT_IDS
    }

    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        result = await run_society_loop(
            run_id=run_config["run_id"],
            store=store,
            embedding=embedding,
            llms=llms,
            agent_states=agent_states,
            personas=personas,
            retrieval_now=datetime.fromisoformat(run_config["retrieval_now"]),
            base_ts=datetime.fromisoformat(run_config["base_ts"]),
            seed=run_config["seed"],
            n_cognition_ticks=run_config["cognition_ticks"],
            physics_ticks_per_cognition=run_config["physics_ticks_per_cognition"],
            k_ecl=run_config["k_ecl"],
            observation_factories=observation_factories,
        )
    finally:
        await embedding.close()
        await store.close()

    # O3a-equivalent — inner_invocations == 0 for every agent's replay client.
    for agent_id, client in llms.items():
        if client.inner_invocations != 0:
            ok = False
            print(
                f"[verify] FAIL {agent_id} replay touched a live LLM "
                f"({client.inner_invocations} calls)"
            )
    if result.checksum != manifest["replay_checksum"]:
        ok = False
        print(
            f"[verify] FAIL replay checksum {result.checksum} != "
            f"manifest {manifest['replay_checksum']}"
        )
    else:
        print(f"[verify] OK replay checksum {result.checksum}")

    committed_event_log_checksum = env_pins.get("captured_event_log_checksum")
    if committed_event_log_checksum is not None:
        if result.event_log_checksum != committed_event_log_checksum:
            ok = False
            print(
                f"[verify] FAIL event_log_checksum {result.event_log_checksum} "
                f"!= committed {committed_event_log_checksum}"
            )
        else:
            print(f"[verify] OK event_log_checksum {result.event_log_checksum}")

    # Codex M1 — structural completeness (fail-closed, gate-independent of the
    # annotation observables).
    expected_agent_ids = set(SOCIETY_LIVE_AGENT_IDS)
    committed_agent_ids = set(run_config.get("agent_ids", []))
    if committed_agent_ids != expected_agent_ids:
        ok = False
        print(
            f"[verify] FAIL structural completeness: agent_ids "
            f"{sorted(committed_agent_ids)} != {sorted(expected_agent_ids)}"
        )
    if run_config.get("cognition_ticks") != SOCIETY_LIVE_N_COGNITION_TICKS:
        ok = False
        print(
            f"[verify] FAIL structural completeness: cognition_ticks "
            f"{run_config.get('cognition_ticks')} != {SOCIETY_LIVE_N_COGNITION_TICKS}"
        )
    for agent_id in SOCIETY_LIVE_AGENT_IDS:
        n_decisions = len(result.decisions.get(agent_id, ()))
        n_calls = len(recorded.get(agent_id, []))
        if n_decisions != SOCIETY_LIVE_N_COGNITION_TICKS:
            ok = False
            print(
                f"[verify] FAIL structural completeness: {agent_id} decision "
                f"count {n_decisions} != {SOCIETY_LIVE_N_COGNITION_TICKS}"
            )
        if n_calls != SOCIETY_LIVE_N_COGNITION_TICKS:
            ok = False
            print(
                f"[verify] FAIL structural completeness: {agent_id} recorded "
                f"call count {n_calls} != {SOCIETY_LIVE_N_COGNITION_TICKS}"
            )

    # O3b — re-render (committed env_pins/run reused) -> per-artifact SHA-256.
    rendered = handoff.render_society_golden(
        result, run_config=run_config, env_pins=env_pins
    )
    artifacts = {
        "ecl_trace.jsonl": trace_text,
        "decisions.jsonl": decisions_text,
        "envelope_stream.jsonl": envelope_text,
    }
    for name, committed_text in artifacts.items():
        expected = manifest["artifacts"][name]["sha256"]
        actual = hashlib.sha256(rendered[name].encode("utf-8")).hexdigest()
        if actual != expected:
            ok = False
            print(f"[verify] FAIL {name} sha256 {actual} != {expected}")
        elif rendered[name] != committed_text:  # pragma: no cover - defensive
            ok = False
            print(f"[verify] FAIL {name} byte mismatch despite matching sha256")

    # O3b (manifest.json itself, Codex HIGH-5 anti-vacuous-pass): the
    # per-artifact SHA-256 checks above never touch manifest.json — a
    # drifted/stale committed manifest (env_pins / annotations overlay /
    # replay_checksum / artifact SHA fields) would otherwise vacuously pass.
    # Re-render through the exact same pipeline capture() used
    # (render_society_golden + attach_society_live_observables +
    # canonical_dumps), reusing the committed env_pins/run block (never a
    # fresh capture), and assert byte-identity.
    rerendered_manifest = (
        handoff.canonical_dumps(
            attach_society_live_observables(json.loads(rendered["manifest.json"]))
        )
        + "\n"
    )
    if rerendered_manifest != manifest_text:
        ok = False
        print("[verify] FAIL manifest.json byte mismatch on re-render")
    else:
        print("[verify] OK manifest.json byte-identical re-render")

    envelopes = handoff.validate_envelope_stream(envelope_text)
    print(f"[verify] OK {len(envelopes)} envelopes schema-conformant")

    print(
        "[verify] SOCIETY LIVE ARTIFACT OK"
        if ok
        else "[verify] SOCIETY LIVE ARTIFACT MISMATCH"
    )
    return ok


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="M4 society live-capture (Issue 001/002 apparatus)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--capture",
        action="store_true",
        help=(
            "drive one record-mode society run against a live Ollama and "
            "write artifacts"
        ),
    )
    group.add_argument(
        "--verify",
        action="store_true",
        help="Ollama-free replay-verify a committed artifact bundle (Issue 002)",
    )
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT_DIR)
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=_DEFAULT_OUT_DIR,
        help="artifact bundle to replay-verify (--verify only)",
    )
    parser.add_argument("--run-id", default=SOCIETY_LIVE_RUN_ID)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--n-cognition-ticks", type=int, default=SOCIETY_LIVE_N_COGNITION_TICKS
    )
    parser.add_argument(
        "--physics-ticks-per-cognition",
        type=int,
        default=DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    )
    parser.add_argument("--qwen3-model-digest", default="unknown")
    parser.add_argument("--ollama-version", default="unknown")
    parser.add_argument("--vram-gb", type=float, default=0.0)
    parser.add_argument("--uv-lock-sha256", default="unknown")
    args = parser.parse_args(argv)

    if args.verify:
        ok = asyncio.run(verify(args.artifact_dir))
        return 0 if ok else 1

    result, rendered = asyncio.run(
        capture(
            run_id=args.run_id,
            seed=args.seed,
            n_cognition_ticks=args.n_cognition_ticks,
            physics_ticks_per_cognition=args.physics_ticks_per_cognition,
            qwen3_model_digest=args.qwen3_model_digest,
            ollama_version=args.ollama_version,
            vram_gb=args.vram_gb,
            uv_lock_sha256=args.uv_lock_sha256,
        )
    )
    _write(args.out_dir, rendered)
    print(f"[capture] wrote {len(rendered)} artifacts to {args.out_dir}")
    print(f"[capture] replay_checksum = {result.checksum}")
    print(f"[capture] event_log_checksum = {result.event_log_checksum}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

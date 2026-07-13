"""M2 Layer2 — mirror-sim (self-other functional analog) acceptance tests.

FROZEN ADR ``.steering/20260713-m13-m2-layer2-impl-design/design-final.md`` §L10
(13 acceptance tests, all boolean/count/AST-only). This is a **construction**
apparatus, NOT a measurement line: every assertion here is boolean / count /
AST / byte-identity — never a floor / verdict / scorer / divergence / magnitude
aggregate over the records it observes. The self-other continuity gate proves a
*causal wiring* (``depends_on_other_observation ∈ {true, false}``), never how
*much* another agent's observation changed behaviour (magnitude-read = covert
scorer, §L4.1, forbidden).

NOT a structural-floor verdict; verdict は holding (design-final.md §L4/§L13,
binding anti-over-read guard). GATING is Layer1 (PR #72); these Layer2 tests are
**bounded** — a stubborn continuity gate is a *construction finding*, it does not
invalidate M2 and is not a measurement verdict (scoping §2.3.1).

Test ↔ issue (J-slice) map:
* J1 (Issue 001): ``test_self_other_world_model_coexist_deterministic`` (#10).
* J2 (Issue 002): ``test_self_other_context_builder_purity`` (#3),
  ``test_self_other_no_future_or_self_leak`` (#6).
* J3 (Issue 003): ``test_self_other_slot_provenance`` (#4),
  ``test_self_other_n1_degenerate`` (#9),
  ``test_self_other_event_log_checksum_stable`` (#8).
* J4 (Issue 004): ``test_self_other_wiring_continuity_positive`` (#1),
  ``test_self_other_wiring_continuity_negative`` (#2),
  ``test_self_other_replay_causal_separation`` (#5),
  ``test_self_other_disjointness`` (#7).
* J5 (Issue 005): ``test_self_other_functional_analog_vocabulary`` (#11),
  ``test_self_other_no_measurement_computation`` (#12),
  ``test_self_other_llm_call_cap`` (#13).

LLM is mocked (recorded ``LLMPlan`` replay / exact-oracle route); sqlite-vec runs
in ``:memory:`` — gating is replay/mock only (§L9). The采用 design adds **no new
LLM call** (self-other rides the existing cognition call's prompt), so Layer2
on/off draw the same per-agent-per-window call count.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from erre_sandbox.cognition.prompting import build_user_prompt
from erre_sandbox.contracts.cognition_layers import WorldModelEntry
from erre_sandbox.integration.embodied.society import (
    SelfOtherPriorRecord,
    build_self_other_context,
)
from erre_sandbox.schemas import MemoryEntry, MemoryKind

# --------------------------------------------------------------------------- #
# Shared Ollama-free fixtures (mirrors test_prompting_world_model.py)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _FakeRanked:
    entry: MemoryEntry
    strength: float
    cosine_sim: float = 0.9


def _mem(content: str) -> MemoryEntry:
    return MemoryEntry(
        id=f"m_{abs(hash(content)) & 0xFFFF}",
        agent_id="a_kant_001",
        kind=MemoryKind.EPISODIC,
        content=content,
        importance=0.5,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _entry(axis: str, key: str, value: float, confidence: float) -> WorldModelEntry:
    return WorldModelEntry(
        axis=axis,  # type: ignore[arg-type]
        key=key,
        value=value,
        confidence=confidence,
        cited_memory_ids=("belief_kant__x",),
        last_updated_tick=100,
    )


# A fixed, pre-rendered self-other segment (the shape build_self_other_context
# emits: a self-contained header + body). J1 only pins *placement*, so the exact
# wording is irrelevant here — J2/J4 pin the builder's real render.
_SELF_OTHER_SEGMENT = (
    "Observed others (prior window):\n"
    "- a_bravo: zone=peripatos, was_proximate=true"
)


# --------------------------------------------------------------------------- #
# J1 / #10 — world_model + self_other coexistence byte ordering golden
# (Codex MEDIUM-2, §L4.3/§L8)
# --------------------------------------------------------------------------- #


def test_self_other_world_model_coexist_deterministic() -> None:
    """self_other_context and world_model_entries compose without interference.

    NOT a structural-floor verdict; verdict は holding. Pins the §L8 coexistence
    ordering contract as a byte golden over the four quadrants of
    (world_model present?) × (self_other present?):

    * self_other empty → the prompt is **byte-identical** to the pre-Layer2
      contract, in **both** the world-model-empty and world-model-present cases
      (the held block's byte position is unchanged whether or not the Layer2
      segment exists — M10-B additive idiom preserved).
    * self_other non-empty → only a **stable added position** (after the held
      block, before the decision tail) changes; the world-model block bytes are
      untouched, and the segment appears verbatim.
    """
    obs: list = []
    mems = [_FakeRanked(_mem("walked the peripatos"), 0.6)]
    entries = (_entry("self", "diligence", 0.8, 0.9),)

    # Pre-Layer2 references (the exact byte output before self_other existed:
    # the default self_other_context="" path).
    base_no_wm = build_user_prompt(obs, mems)
    base_with_wm = build_user_prompt(obs, mems, world_model_entries=entries)

    # (1) self_other empty, world_model empty → byte-identical to pre-Layer2.
    so_empty_no_wm = build_user_prompt(obs, mems, self_other_context="")
    assert so_empty_no_wm == base_no_wm
    assert "Observed others" not in so_empty_no_wm

    # (2) self_other empty, world_model present → byte-identical to pre-Layer2
    #     (held block position unchanged — the Layer2 seam is inert when empty).
    so_empty_with_wm = build_user_prompt(
        obs, mems, world_model_entries=entries, self_other_context=""
    )
    assert so_empty_with_wm == base_with_wm

    # (3) self_other present, world_model empty → segment injected verbatim at a
    #     stable position; the pre-segment body is an unchanged prefix.
    so_only = build_user_prompt(obs, mems, self_other_context=_SELF_OTHER_SEGMENT)
    assert _SELF_OTHER_SEGMENT in so_only
    assert so_only != base_no_wm
    # The observations/memories header block is an unchanged prefix (the segment
    # is appended after it, before the decision tail — never interleaved).
    assert so_only.startswith("Recent observations:\n")
    assert "Relevant memories:\n" in so_only

    # (4) self_other present, world_model present → the held block bytes are
    #     unchanged; the segment sits *after* the held block, before the decision
    #     tail (stable added position, no interference — §L8).
    both = build_user_prompt(
        obs,
        mems,
        world_model_entries=entries,
        self_other_context=_SELF_OTHER_SEGMENT,
    )
    assert "Held world-model entries:\n" in both
    assert _SELF_OTHER_SEGMENT in both
    held_idx = both.index("Held world-model entries:\n")
    seg_idx = both.index(_SELF_OTHER_SEGMENT)
    decide_idx = both.index("Decide what to do in the next ten seconds.")
    # Ordering: held block → self_other segment → decision tail (stable).
    assert held_idx < seg_idx < decide_idx
    # The held block's own rendered bytes are identical to the no-self_other
    # case (the segment did not perturb the held block, only appended after it).
    held_block_bytes = base_with_wm[
        base_with_wm.index("Held world-model entries:\n") : base_with_wm.index(
            "Decide what to do in the next ten seconds."
        )
    ]
    assert held_block_bytes in both


# --------------------------------------------------------------------------- #
# J2 helpers + tests — pure builder (§L3/§L7, DA-L2-2 strict prefix filter)
# --------------------------------------------------------------------------- #

_ALLOWED_SCALARS = (str, int, bool, type(None))


def _assert_float_free(obj: Any) -> None:
    """Every scalar under ``obj`` is in {str, int, bool, None} — no float (§L7).

    ``bool`` is a subclass of ``int`` but explicitly allowed; a bare ``float``
    anywhere would drift cross-platform (the slot payload never passes through
    the 6-decimal quantiser, §L2/§L7 — float-free is the structural mitigation).
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert isinstance(k, str), f"non-str key {k!r}"
            _assert_float_free(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _assert_float_free(v)
    else:
        assert isinstance(obj, _ALLOWED_SCALARS) and not isinstance(obj, float), (
            f"payload scalar {obj!r} is not in {{str, int, bool, None}} (§L7 float-free)"
        )


def _prior(
    agent_id: str,
    window: int,
    *,
    zone: str = "peripatos",
    destination_zone: str | None = None,
    utterance: str | None = None,
    was_proximate: bool = False,
) -> SelfOtherPriorRecord:
    return SelfOtherPriorRecord(
        agent_id=agent_id,
        window=window,
        zone=zone,
        destination_zone=destination_zone,
        utterance=utterance,
        was_proximate=was_proximate,
    )


def test_self_other_context_builder_purity() -> None:
    """Same prior records → same canonical context (deterministic, sorted, float-free).

    NOT a structural-floor verdict; verdict は holding. The builder is an
    exact-oracle pure function: identical input yields an identical
    :class:`SelfOtherContext` (payload + rendered), the ``observed`` list is
    canonically sorted by ``other_agent_id`` regardless of input order, and the
    payload carries no float (the §L7 cross-platform-drift structural guard).
    """
    # Deliberately non-sorted input order (charlie, alpha, bravo) at the
    # immediately-prior window (t-1 = 2) for observer at window 3.
    records = [
        _prior("a_charlie", 2, zone="agora", utterance="こんにちは"),
        _prior("a_alpha", 2, zone="study", destination_zone="peripatos"),
        _prior("a_bravo", 2, zone="chashitsu", was_proximate=True),
    ]

    ctx_a = build_self_other_context(
        observer_id="a_observer", window_index=3, prior_records=records
    )
    # Purity: rebuild with the SAME records → byte-identical context.
    ctx_b = build_self_other_context(
        observer_id="a_observer", window_index=3, prior_records=list(records)
    )
    assert ctx_a == ctx_b
    assert ctx_a.injection_payload() == ctx_b.injection_payload()
    assert ctx_a.rendered == ctx_b.rendered

    # Order-insensitivity: a shuffled input yields the same canonical output.
    shuffled = [records[1], records[2], records[0]]
    ctx_shuffled = build_self_other_context(
        observer_id="a_observer", window_index=3, prior_records=shuffled
    )
    assert ctx_shuffled == ctx_a

    # observed is canonically sorted by other_agent_id (a total string order).
    observed_ids = [r.other_agent_id for r in ctx_a.observed]
    assert observed_ids == sorted(observed_ids)
    assert observed_ids == ["a_alpha", "a_bravo", "a_charlie"]

    # source_window is the immediately-prior window (t-1), strictly < window_index.
    assert ctx_a.source_window == 2
    assert ctx_a.source_window < ctx_a.window

    # Payload is float-free (§L7) and every declared scalar is str/int/bool/None.
    payload = ctx_a.injection_payload()
    _assert_float_free(payload)
    # A non-None destination / utterance / proximity round-trips into the payload.
    alpha = next(o for o in payload["observed"] if o["other_agent_id"] == "a_alpha")
    assert alpha["observed_destination_zone"] == "peripatos"
    assert alpha["observed_utterance"] is None
    assert alpha["was_proximate"] is False
    bravo = next(o for o in payload["observed"] if o["other_agent_id"] == "a_bravo")
    assert bravo["was_proximate"] is True
    charlie = next(o for o in payload["observed"] if o["other_agent_id"] == "a_charlie")
    assert charlie["observed_utterance"] == "こんにちは"

    # The rendered SimToM segment is deterministic, non-empty, and mentions each
    # observed other exactly once (bounded functional-analog framing).
    assert ctx_a.rendered
    for oid in ("a_alpha", "a_bravo", "a_charlie"):
        assert ctx_a.rendered.count(f"- {oid}:") == 1


def test_self_other_no_future_or_self_leak() -> None:
    """Builder reads only ``other != observer`` ∧ ``source_window < window_index``.

    NOT a structural-floor verdict; verdict は holding. Codex HIGH-2 / DA-L2-2:
    a 2-window fixture proves the strict prefix filter structurally rejects (a)
    the observer's own action, (b) any this-window record, and (c) any
    future-window record — if any leaked into the context the assertions below
    would go red. The context for window ``t`` is built **only** from the
    immediately-prior window ``t-1`` of *other* agents.
    """
    observer = "a_observer"
    window_index = 2  # source_window = 1
    records = [
        # (a) observer's OWN record at t-1 — must be excluded (self leak guard).
        _prior(observer, 1, zone="study"),
        # (b) another agent this-window (t) — must be excluded (future/this leak).
        _prior("a_other", 2, zone="agora"),
        # (c) another agent future window (t+1) — must be excluded.
        _prior("a_other", 3, zone="garden"),
        # (d) another agent two windows back (t-2) — excluded (source_window is t-1).
        _prior("a_other", 0, zone="chashitsu"),
        # (e) the ONLY admissible record: another agent at t-1.
        _prior("a_peer", 1, zone="peripatos", utterance="どうも"),
    ]

    ctx = build_self_other_context(
        observer_id=observer, window_index=window_index, prior_records=records
    )

    observed_ids = {r.other_agent_id for r in ctx.observed}
    # Only the other agent's t-1 record survives.
    assert observed_ids == {"a_peer"}
    # The observer never observes itself.
    assert observer not in observed_ids
    # No this-window / future / t-2 record leaked in.
    assert all(r.observed_zone == "peripatos" for r in ctx.observed)
    assert ctx.source_window == 1

    # window 0 → empty context (no prior window; honest, not a builder failure).
    ctx0 = build_self_other_context(
        observer_id=observer, window_index=0, prior_records=records
    )
    assert ctx0.is_empty
    assert ctx0.rendered == ""
    assert ctx0.injection_payload()["observed"] == []

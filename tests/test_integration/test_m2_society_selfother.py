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

from erre_sandbox.cognition.prompting import build_user_prompt
from erre_sandbox.contracts.cognition_layers import WorldModelEntry
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

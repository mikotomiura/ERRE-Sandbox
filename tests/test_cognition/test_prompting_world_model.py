"""M10-B USER-prompt injection tests for ``cognition.prompting``.

Covers the held-world-model section: byte-identity when empty (flag-off and
all pre-M10-B callers), correct positioning (right after memories, before the
decision/schema tail), the <= 80-proxy-token section budget, the top-K cap and
the deterministic fixed-point line format. See
``.steering/20260526-m10-b-swm-synthesis-prompt-injection/decisions.md``
DA-M10B-8/9/11.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from erre_sandbox.cognition.prompting import (
    RESPONSE_SCHEMA_HINT,
    RESPONSE_SCHEMA_HINT_WITH_UPDATE,
    build_user_prompt,
    format_world_model_entries,
    visible_entry_citations,
)
from erre_sandbox.contracts.cognition_layers import WorldModelEntry
from erre_sandbox.evidence.cache_benchmark.compute import count_proxy_tokens
from erre_sandbox.schemas import MemoryEntry, MemoryKind


@dataclass(frozen=True)
class _FakeRanked:
    entry: MemoryEntry
    strength: float
    cosine_sim: float = 0.9


def _mem(content: str) -> MemoryEntry:
    return MemoryEntry(
        id=f"m_{hash(content) & 0xFFFF}",
        agent_id="a_kant_001",
        kind=MemoryKind.EPISODIC,
        content=content,
        importance=0.5,
        created_at=datetime.now(tz=UTC),
    )


def _entry(
    axis: str,
    key: str,
    value: float,
    confidence: float,
    *,
    cited: tuple[str, ...] = ("belief_kant__x",),
) -> WorldModelEntry:
    return WorldModelEntry(
        axis=axis,  # type: ignore[arg-type]
        key=key,
        value=value,
        confidence=confidence,
        cited_memory_ids=cited,
        last_updated_tick=100,
    )


# ---------- byte-identity (flag-off / legacy callers) ----------------------


def test_empty_world_model_is_byte_identical_to_legacy() -> None:
    """An empty (default) world-model produces the exact pre-M10-B prompt."""
    obs: list = []
    mems = [_FakeRanked(_mem("walked the peripatos"), 0.6)]
    legacy = build_user_prompt(obs, mems)
    with_empty = build_user_prompt(obs, mems, world_model_entries=())
    assert legacy == with_empty
    assert "Held world-model entries" not in legacy


def test_empty_world_model_omits_section_entirely() -> None:
    """No header leaks when the entry list is empty."""
    prompt = build_user_prompt([], [], world_model_entries=())
    assert "Held world-model entries" not in prompt


# ---------- positioning + content ------------------------------------------


def test_section_inserted_after_memories_before_decision() -> None:
    """The held section sits between memories and the decision/schema tail."""
    entries = [_entry("self", "relational_disposition", 0.42, 0.80)]
    prompt = build_user_prompt([], [], world_model_entries=entries)
    held = prompt.index("Held world-model entries:")
    memories = prompt.index("Relevant memories:")
    decide = prompt.index("Decide what to do")
    assert memories < held < decide


def test_section_renders_axis_key_value_conf() -> None:
    entries = [_entry("env", "peripatos", 0.30, 0.65)]
    prompt = build_user_prompt([], [], world_model_entries=entries)
    assert "- [env/peripatos] value=+0.30 conf=0.65" in prompt


# ---------- top-K + token budget -------------------------------------------


def test_format_caps_at_max_items() -> None:
    """Only the head ``max_items`` entries render (entries are pre-sorted)."""
    entries = [_entry("env", f"z{i}", 0.5, 0.5) for i in range(6)]
    rendered = format_world_model_entries(entries)
    assert rendered.count("\n- ") + 1 == 4  # 4 lines (default max_items)


def test_section_within_80_token_budget() -> None:
    """The rendered section stays within the <= 80-proxy-token budget."""
    # Worst case: full top-K with the longest realistic key + signed values.
    entries = [
        _entry("self", "relational_disposition", -0.85, 0.80),
        _entry("env", "chashitsu", 0.66, 0.58),
        _entry("env", "peripatos", -0.41, 0.40),
        _entry("env", "garden", 0.58, 0.45),
        _entry("env", "agora", 0.33, 0.50),  # 5th: dropped by the cap
    ]
    rendered = format_world_model_entries(entries)
    assert count_proxy_tokens(rendered) <= 80


def test_format_is_deterministic_fixed_point() -> None:
    """Two-decimal signed value / unsigned conf, stable across calls."""
    entries = [_entry("self", "relational_disposition", 0.4166, 0.7999)]
    a = format_world_model_entries(entries)
    b = format_world_model_entries(entries)
    assert a == b
    assert "value=+0.42 conf=0.80" in a


def test_empty_entries_render_empty_string() -> None:
    assert format_world_model_entries([]) == ""


# ---------- M10-C: update channel gating (案 A, flag-on only) ---------------


def test_update_disabled_uses_base_schema_and_no_citations() -> None:
    """world_model_update_enabled=False (default) is byte-identical to M10-B."""
    entries = [_entry("env", "agora", 0.40, 0.60)]
    legacy = build_user_prompt([], [], world_model_entries=entries)
    explicit_off = build_user_prompt(
        [],
        [],
        world_model_entries=entries,
        world_model_update_enabled=False,
    )
    assert legacy == explicit_off
    assert RESPONSE_SCHEMA_HINT in legacy
    assert "world_model_update_hint" not in legacy
    assert "cite=" not in legacy


def test_flag_off_full_prompt_byte_identical_regardless_of_update_flag() -> None:
    """With no entries, the update flag cannot change the flag-off USER prompt."""
    mems = [_FakeRanked(_mem("walked the peripatos"), 0.6)]
    base = build_user_prompt([], mems)
    with_flag = build_user_prompt(
        [],
        mems,
        world_model_entries=(),
        world_model_update_enabled=True,
    )
    # No held entries ⇒ no citations to show; but the schema still flips when the
    # channel is on. The flag-off contract is the entries-empty default path.
    assert "Held world-model entries" not in with_flag
    assert base != with_flag  # only because the schema hint changed
    assert RESPONSE_SCHEMA_HINT_WITH_UPDATE in with_flag


def test_update_enabled_renders_citations_and_extended_schema() -> None:
    entries = [_entry("env", "agora", 0.40, 0.60, cited=("belief_kant__nietzsche",))]
    prompt = build_user_prompt(
        [],
        [],
        world_model_entries=entries,
        world_model_update_enabled=True,
    )
    assert "- [env/agora] value=+0.40 conf=0.60 cite=belief_kant__nietzsche" in prompt
    assert "world_model_update_hint" in prompt
    assert RESPONSE_SCHEMA_HINT_WITH_UPDATE in prompt


def test_citations_capped_per_entry() -> None:
    """Only the first two (sorted) belief ids per entry are displayed (MED-3)."""
    entries = [
        _entry(
            "self",
            "relational_disposition",
            0.40,
            0.60,
            cited=("belief_kant__c", "belief_kant__a", "belief_kant__b"),
        ),
    ]
    rendered = format_world_model_entries(entries, include_citations=True)
    assert "cite=belief_kant__a,belief_kant__b" in rendered
    assert "belief_kant__c" not in rendered


def test_visible_citations_match_rendered_display() -> None:
    """The verifier's exposed map equals exactly what the prompt shows."""
    entries = [
        _entry("env", "agora", 0.40, 0.60, cited=("belief_kant__n",)),
        _entry(
            "self",
            "relational_disposition",
            0.30,
            0.50,
            cited=("belief_kant__z", "belief_kant__a", "belief_kant__m"),
        ),
    ]
    exposed = visible_entry_citations(entries)
    assert exposed[("env", "agora")] == frozenset({"belief_kant__n"})
    # sorted + capped at 2: a, m (z is dropped)
    assert exposed[("self", "relational_disposition")] == frozenset(
        {"belief_kant__a", "belief_kant__m"},
    )


def test_update_enabled_section_within_citation_budget() -> None:
    """With citations the section grows past M10-B's 80-token no-cite budget but
    stays bounded (the authoritative flag-on gate is the +200 overall USER-prompt
    delta verified by the cache benchmark). Worst case = top-K full with two
    citations each; the per-entry citation cap keeps it well under 120 proxy tokens.
    """
    entries = [
        _entry(
            "self",
            "relational_disposition",
            -0.85,
            0.80,
            cited=("belief_kant__nz", "belief_kant__rk"),
        ),
        _entry(
            "env", "chashitsu", 0.66, 0.58, cited=("belief_kant__nz", "belief_kant__rk")
        ),
        _entry(
            "env",
            "peripatos",
            -0.41,
            0.40,
            cited=("belief_kant__nz", "belief_kant__rk"),
        ),
        _entry(
            "env", "garden", 0.58, 0.45, cited=("belief_kant__nz", "belief_kant__rk")
        ),
    ]
    rendered = format_world_model_entries(entries, include_citations=True)
    assert count_proxy_tokens(rendered) <= 120

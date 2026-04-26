# M7 Slice δ — Design Final (post /reimagine, hybrid adopted)

> Mirrors `~/.claude/plans/m7-slice-compressed-teapot.md`. Repo-resident reference for
> the next session's `/clear` handoff. Plan generated 2026-04-26 in Plan mode + Opus +
> `/reimagine` hybrid.

## Context

Slice γ (PR #92, merged 2026-04-25) shipped the **signature** for relationships:
`compute_affinity_delta(turn, recent_transcript, persona)` exists as a pure function but
returns constant **+0.02** (γ MVP, decisions.md D2). MacBook post-merge review (R3,
`.steering/20260425-m7-slice-gamma/decisions.md` lines 277-351) identified HIGH 3 +
MEDIUM 5 + LOW 4 deltas vs CSDG (前身プロジェクト). Slice δ fills the HIGH/MEDIUM
items and γ's C3 anatomy residual in **one PR (~12-15h)**.

This design is the **adopted hybrid** of v1 (independent design from prior session,
preserved at `~/.claude/plans/precious-moseying-dahl.md`) and v2 (independent
re-generation by `/reimagine` Plan agent this session). Empirical verification of v2
claims surfaced one critical flaw and two strengths; the adopted bundle takes the
better of each.

## Phase 3 — v1 / v2 comparison (per axis)

| Axis | v1 pick | v2 pick | Empirical check | **Adopted** | Why |
|---|---|---|---|---|---|
| **1a decay** | `0.02 + 0.06*neuroticism` (range 0.032-0.071) | `0.02 + 0.06*agreeableness` (range 0.035-0.05) | v1 half-life: kant 31 / nietzsche 14 / rikyu 28 turns. v2 half-life: kant 20 / nietzsche 28 / rikyu 20 turns | **v1 (neuroticism)** | Observability priority: nietzsche's 4× decay vs kant is dramatically observable in 90s live; v2's agreeableness gives narrower contrast. v2's psych argument (agreeableness = forgiveness/repair) is asymmetric (negative→neutral), not symmetric decay. v1's "neuroticism = volatility" framing matches Nietzsche's stormy historical relationships (Wagner, Salomé). Documented as future calibration alt. |
| **1b event_impact** | JP keyword lex sentiment (new `_relational_lex.py`, ~20 pos / ~15 neg tokens) | **Structural features only**: addressee_match + length_norm + erre_mode_engagement | v2 correct: MeCab-less keyword lex on 2-3 LLM-JP sentences is brittle. Structural features are deterministic, language-agnostic, testable without fixtures | **v2 structural** | v2 wins on defensibility. Drop the new lexicon module entirely (saves a brittle artifact + JP-fixture maintenance). Antagonism term moved out — see Axis 2. |
| **1c event_weight** | `0.5 + extraversion` (range 0.5-1.5) | `0.5 + 0.5*extraversion` (range 0.5-1.0) | Both clamp safely | **v1 (wider range)** | More contrast between extroverted Kant (0.85) and introverted Nietzsche/Rikyu (0.20 each). v2's narrower range over-conservative. |
| **2 negative path** | Hard-coded `_TRAIT_ANTAGONISM = {("kant","nietzsche"): -0.30, ("nietzsche","kant"): -0.30}` table + lex hybrid + `Physical.emotional_conflict` write/decay | Trait-distance derivation (7-D Big Five+ERRE Euclidean, antagonism gate >0.55) + emotional_conflict | **Computed distances:** K↔N=0.40, K↔R=0.30, **N↔R=0.443**. v2's gate >0.55 fires for **none**; gate ≥0.40 fires for **all three**, losing K↔N specificity. v2's claim "K↔N largest" is empirically false at N=3 | **v1 antagonism table + both `emotional_conflict` write/decay** | Hard-coded table is the right tool at N=3 (live-fire K↔N guarantee, deterministic). Trait-distance generalization deferred to m9-lora when persona count grows. v2's `Physical.emotional_conflict` mechanism is convergent — adopt. JP lex term removed (Axis 1b moved to structural). |
| **3 belief promotion** | template `f"belief: I {trust\|clash with} {name}"`, threshold 0.5/N=5 (asserted), permanent, **`belief_type`** field via migration | enum `belief_kind: Literal["trust","clash","wary","curious","ambivalent"]` + `confidence: float`, threshold 0.45/N=6 (simulation-derived), permanent, schema extension via `_migrate_*_schema` | v2 methodology (simulation-driven threshold via `test_relational_simulation.py`) is tighter than v1's assertion. Both converge on typed schema field via established migration pattern | **v2 (typed enum + confidence + simulation-derived threshold)** | v2 wins across the board. m8-affinity-dynamics Critics will query `WHERE belief_kind='clash' AND confidence > 0.6` cleanly. Threshold/N picked from a 30-line in-test simulation iterating recurrence over 20 turns × 3 pairs. |
| **4 SQL push** | extend `iter_dialog_turns(exclude_persona, limit)` **AND** new `recent_peer_turns()` wrapper (4-C, 2.0h) | extend `iter_dialog_turns` only (1.0h) | Single consumer site (`cycle.py:741-790`), wrapper adds indirection without callers | **v2 (extend only)** | YAGNI argument correct. Wrapper is justifiable when ≥2 callers exist; today there is one. Saves 1.0h. m8 cold-path metric query can call the same extension later. |
| **5 last_in_zone** | `last_interaction_zone: Zone \| None = None` + migration `_migrate_relationship_bond_schema` + SCHEMA_VERSION bump + Godot UI (2.0h) | Same field + bump + UI but **no DB migration** (RelationshipBond is AgentState-resident, not in SQLite) (1.5h) | Verified: `memory/store.py:178-191` archives RELATIONAL `MemoryEntry` content, not bond fields. Bond mutation via `model_copy` at `world/tick.py:455-510` stays in-memory | **v2 (no DB migration)** | v1 over-engineered; v2 spotted the AgentState-resident reality. Saves 0.5h of unneeded migration code. Still bump SCHEMA_VERSION → `0.7.0-m7d` for the schemas.py field addition. |
| **C3 #3 silhouette** | Defer to ε (D), bundle at 13.0h, cited Godot scene merge conflict | **Adopt Case A** (PersonaSpec.accent_color + Head sub-mesh material), 2.5h | AgentAvatar.tscn:48 shows all 6 meshes share `material_override = SubResource("6_bodymat")`. BodyTinter.gd:34-38 picks first child's material as `_shared_material`. Adoption requires (a) new sub-resource in tscn, (b) skip-Head logic in `_ready()`, (c) AgentManager accent wiring. **Actual cost ≈ 3.5-4h, not 2.5h** | **v1 (defer to ε)** but for v2's reason (v1's merge-conflict reason was wrong; defer because cost is undersized) | C3 ✅ already met at 2/3 (Relationships UI + visual primitive in production). #3 adoption pushes bundle to ~17h, exceeding 15h envelope by ~13%. Defer to ε with clean handoff: "C3 trinity 2/3 closed in γ+δ; #3 cosmetic differentiation pending m9-lora persona-spec voice anyway". |

**Convergent picks (both v1 and v2 agreed):**
- Bump `SCHEMA_VERSION = "0.6.0-m7g" → "0.7.0-m7d"`
- Add `# SAFETY: single-writer (M9 may need asyncio.Lock)` comment at `world/tick.py:455-510` (R3 H2). No Lock now — premature.
- `Physical.emotional_conflict` write trigger on negative delta + decay in `state.py::advance_physical`
- Permanent belief promotion (no re-eval; m8 Critics will revise, not decay)
- `_migrate_*_schema` pattern at `memory/store.py:261-276` for SemanticMemoryRecord extension

**Common items absorbed from R3 (both versions agree to bundle):**
- M2: `_decision_with_affinity` sort key → `(|affinity|, last_interaction_tick)` desc (`cycle.py:1104`)
- M3: persona registry resolver into `build_reflection_messages` (`reflection.py:169-175`)
- M5: `asyncio.timeout(2.0)` + empty-layout fallback at `gateway.py:573`

## Phase 4 — Adopted bundle (final design)

### Summary

| Axis | Pick | Cost (h) |
|---|---|---|
| 1a decay | neuroticism-coupled `0.02 + 0.06*neuroticism` | 1.0 |
| 1b impact | **structural features** (addressee_match 0.5 + length_norm 0.3 + erre_engagement 0.2), no JP lex | 2.0 |
| 1c weight | extraversion-coupled `0.5 + extraversion` | 0.5 |
| 1 plumbing | thread `prev=bond.affinity` + `recent_transcript` (Axis 4 result) + `addressee_persona` | 1.0 |
| 2 negative | `_TRAIT_ANTAGONISM` table (K↔N: -0.30) + `Physical.emotional_conflict` write/decay | 1.5 |
| 3 promotion | typed `belief_kind` enum + `confidence` + simulation-derived threshold (~0.45/N=6) + permanent + schema extension | 3.0 |
| 4 SQL | extend `iter_dialog_turns(exclude_persona, limit)` only — no wrapper | 1.0 |
| 5 zone | `last_interaction_zone: Zone \| None = None` + tick write + Godot UI (no DB migration) | 1.5 |
| C3 #3 | defer to ε (cost undersized; bundle stays in envelope) | 0 |
| Common | M2 sort key + M3 persona resolver + M5 layout timeout + H2 SAFETY comment | 1.4 |
| Tests + observation.md + decisions.md | acceptance gates | 1.5 |
| **Total** | | **14.4h** |

**Headroom:** 0.6h on a 15h soft cap. Calibration jitter buffer.

### Acceptance rationale (≤6 lines)

Stays inside 12-15h envelope with 0.6h headroom. Negative path is **guaranteed** to fire
for kant↔nietzsche via `_TRAIT_ANTAGONISM` table (3-persona world), satisfying live "negative
delta observed" gate. Trait-distance generalization deferred until persona count actually
warrants it (m9-lora). Belief promotion uses typed enum (`belief_kind` × `confidence`) with
simulation-derived threshold so calibration is reproducible and m8 Critics can query cleanly.
Axis 4 ships single primitive (extension only), Axis 5 ships in-memory field only (no DB
migration needed). C3 #3 deferral keeps bundle inside envelope with C3 trinity at 2/3
already closed; #3 is cosmetic differentiation pending m9-lora persona voice work anyway.

### Critical files (path:line ranges to be modified)

| File | Change | Axis |
|---|---|---|
| `src/erre_sandbox/cognition/relational.py:30-90` | Replace constant body with `prev*(1-decay) + impact*weight`; add helpers `_compute_decay`, `_compute_impact_structural`, `_compute_weight`, `_apply_antagonism`; new `compute_affinity_delta(turn, recent_transcript, persona, *, prev: float, addressee_persona: PersonaSpec \| None)` signature | 1, 2 |
| `src/erre_sandbox/cognition/_trait_antagonism.py` (NEW, ~30 LOC) | Hard-coded `_TRAIT_ANTAGONISM: dict[tuple[str,str], float] = {("kant","nietzsche"): -0.30, ("nietzsche","kant"): -0.30}` + lookup helper | 2 |
| `src/erre_sandbox/bootstrap.py:207-262` | Pass `prev=bond.affinity`, `recent_transcript=await store.iter_dialog_turns(exclude_persona=..., limit=3)`, `addressee_persona=registry[turn.target_id]` into compute; pass `zone=current_zone` into `apply_affinity_delta` | 1, 5 |
| `src/erre_sandbox/cognition/cycle.py:741-790` | Rewrite `_fetch_recent_peer_turns` to call extended `iter_dialog_turns(exclude_persona=..., limit=_PEER_TURNS_LIMIT)` with reverse-in-Python for 3 rows | 4 |
| `src/erre_sandbox/cognition/cycle.py:~1104` | Sort key `(|affinity|, last_interaction_tick)` desc | M2 |
| `src/erre_sandbox/memory/store.py:836-873` | Add `exclude_persona: str \| None = None` and `limit: int \| None = None` parameters to `iter_dialog_turns` | 4 |
| `src/erre_sandbox/memory/store.py:261-276, 621-655` | Extend `_migrate_semantic_schema` with `belief_kind TEXT NULL` + `confidence REAL NULL`; update `upsert_semantic` to write them | 3 |
| `src/erre_sandbox/world/tick.py:455-510` | Extend `apply_affinity_delta(self, ..., zone: Zone)`; write `last_interaction_zone=zone`; on `delta < -0.05` write `Physical.emotional_conflict += abs(delta)*0.5` clamped [0,1]; add `# SAFETY: single-writer (M9 may need asyncio.Lock)` comment; post-mutation belief promotion check | 2, 3, 5, H2 |
| `src/erre_sandbox/cognition/belief.py` (NEW, ~80 LOC) | `maybe_promote_belief(bond, persona, addressee, store, *, threshold=0.45, min_interactions=6) -> SemanticMemoryRecord \| None`; classifies into `belief_kind` enum; computes `confidence = min(1.0, |affinity|/AFFINITY_UPPER * (interactions/min_interactions))`; called from `world/tick.py` | 3 |
| `src/erre_sandbox/cognition/reflection.py:169-175, 336-344` | Inject persona display_name resolver; reuse `upsert_semantic` for belief promotion (single write site) | 3, M3 |
| `src/erre_sandbox/cognition/state.py` (around `advance_physical`) | Decay `emotional_conflict = max(0.0, prev.emotional_conflict - 0.02)` per tick | 2 |
| `src/erre_sandbox/schemas.py:44, 430-440, 752-781` | Bump `SCHEMA_VERSION = "0.7.0-m7d"`; add `last_interaction_zone: Zone \| None = None` to RelationshipBond; add `belief_kind: Literal[...] \| None = None` and `confidence: float = 1.0` to SemanticMemoryRecord | 3, 5 |
| `src/erre_sandbox/ui/gateway.py:573` | Wrap `layout_snapshot()` in `async with asyncio.timeout(2.0)`; empty-layout fallback on timeout | M5 |
| `godot_project/scripts/ReasoningPanel.gd:218-263` | Extend `_format_relationships` to emit `"<persona> affinity ±0.NN (N turns, last in <zone> @ tick T)"` | 5 |

**Existing utilities to reuse (no recompute):**
- `clamp_affinity_delta` at `cognition/relational.py:42-53` (centralized clamp; do not bypass)
- `apply_affinity` at `cognition/relational.py:84-90` (additive + clamp)
- `_migrate_*_schema` pattern at `memory/store.py:261-276` (idempotent ALTER TABLE ADD COLUMN IF NOT EXISTS)
- `upsert_semantic(record)` at `memory/store.py:621-640` (single semantic write API)
- `iter_dialog_turns(*, persona=None, since=None)` at `memory/store.py:836-873` (extend, do not replicate)
- `BodyTinter.apply_mode` at `godot_project/scripts/agents/BodyTinter.gd:45-67` (untouched in δ)

### Verification

**Unit (pytest, no LLM, no DB beyond `tmp_path`):**
- `tests/cognition/test_relational.py`:
  - `test_compute_affinity_delta_decays_prev` — `prev=0.8`, `event_impact=0` → next < 0.8
  - `test_compute_affinity_delta_negative_for_kant_nietzsche` — `_TRAIT_ANTAGONISM` fires → delta < -0.05
  - `test_compute_affinity_delta_positive_for_kant_rikyu` — no antagonism → delta > 0
  - `test_compute_affinity_delta_extraversion_weight_contrast` — kant utterance ≠ nietzsche utterance impact magnitude
  - `test_compute_affinity_delta_neuroticism_decay_contrast` — nietzsche decay ~2× kant decay
- `tests/cognition/test_relational_simulation.py` (NEW, ~30 LOC) — iterate recurrence 20 turns × 3 pairs; assert `|affinity|` saturates between turn 8-14 in saturating cases. **This test calibrates threshold/N**.
- `tests/cognition/test_belief_promotion.py` (NEW) — `|affinity| > 0.45` after 6+ interactions → SemanticMemoryRecord with correct `belief_kind` and `confidence`
- `tests/test_memory/test_store.py::test_iter_dialog_turns_exclude_persona_and_limit` — insert 10 rows, mock cursor, assert SQL `WHERE speaker_persona_id != ?` and `LIMIT ?` emitted with `("kant", 3)`
- `tests/test_schemas.py::test_relationship_bond_round_trip_with_zone` — round-trip `last_interaction_zone=Zone.chashitsu`
- `tests/test_schemas.py::test_semantic_memory_record_with_belief_kind` — round-trip `belief_kind="trust"`, `confidence=0.7`
- `tests/world/test_tick.py::test_apply_affinity_delta_writes_emotional_conflict_on_negative` — negative delta → `physical.emotional_conflict > 0`
- Godot GUT — `ReasoningPanel` "last in <zone>" rendering fixture

**Integration:**
- `tests/test_slice_delta_e2e.py` (NEW, ~80 LOC): drive 12 fake `DialogTurnMsg` between Kant/Nietzsche, assert (a) at least one negative bond.affinity, (b) one SemanticMemoryRecord with `belief_kind='clash'`, (c) `Physical.emotional_conflict > 0` for both, (d) `last_interaction_zone` set on bond

**Live G-GEAR (acceptance — requirement.md):**
- `feat/m7-slice-delta` branch
- `ERRE_ZONE_BIAS_P=0.1 uv run erre-sandbox --personas kant,nietzsche,rikyu --db var/run-delta.db`, 90-120s
- `evidence/<run>.summary.json` records:
  - dialog_turn ≥ 3
  - both signs of delta observed (positive and negative bond.affinity changes)
  - decay-induced saturation visible in time-series of bond.affinity
  - ≥1 belief promotion in `semantic_memory` with `belief_kind` populated
  - `recent_peer_turns` p95 latency < γ Run-1 baseline (verify via `EXPLAIN QUERY PLAN`)
  - `ReasoningPanel` screenshot shows `"last in <zone>"`

**Records (mirror γ structure):**
- `.steering/20260426-m7-slice-delta/observation.md` — formula calibration (decay rate / impact range / threshold actually fired)
- `.steering/20260426-m7-slice-delta/decisions.md` — C3 #3 deferral rationale + δ scope drift (if any)
- `.steering/20260426-m7-slice-delta/run-01-delta/` directory mirroring γ run-01-gamma layout

### Commit construction (sequential commits on `feat/m7-slice-delta`)

1. **C1 schemas** (~1.5h) — `schemas.py` SCHEMA_VERSION bump + RelationshipBond.last_interaction_zone + SemanticMemoryRecord.belief_kind/confidence; `memory/store.py` migration extension; round-trip + binary fixture compat tests; `last_interaction_zone` defaults to None for backward compat
2. **C2 SQL extension** (~1.0h) — `iter_dialog_turns(exclude_persona, limit)` + cycle.py rewrite + mock-SQL test
3. **C3 formula** (~3.5h) — `relational.py` body replacement + `_trait_antagonism.py` + plumbing in `bootstrap.py`; unit tests for decay/impact/weight/antagonism; SAFETY comment at `world/tick.py:455-510`
4. **C4 negative loop** (~1.5h) — `world/tick.py` write `emotional_conflict` + `last_interaction_zone`; `state.py` decay; integration test
5. **C5 belief promotion** (~3.0h) — `cognition/belief.py` + `reflection.py` integration + `test_relational_simulation.py` calibration test + promotion test
6. **C6 common items** (~1.4h) — M2 sort key + M3 persona resolver + M5 layout timeout
7. **C7 Godot UI** (~1.0h) — `ReasoningPanel.gd` extend `_format_relationships`; GUT fixture
8. **C8 acceptance** (~1.5h) — `test_slice_delta_e2e.py` + ruff/pytest pass + live G-GEAR run + observation.md / decisions.md / run-01-delta/ records

Final: PR `feat: M7 Slice δ — CSDG semi-formula + negative affinity + belief bridge`, base `main`, with R3 references and γ design-final cross-link.

## Plan → Clear → Execute (CLAUDE.md L65-71)

1. This `design-final.md` is the repo-resident commit-0 artifact (mirror of `~/.claude/plans/m7-slice-compressed-teapot.md`).
2. Next session `/clear` and start fresh by Reading: this file + `requirement.md` + `~/.claude/plans/m7-slice-compressed-teapot.md` (if still present) before C1.
3. Implement C1 → C8 sequentially on `feat/m7-slice-delta` branch (NOT `main`).
4. Each commit: ruff + pytest before move-on; do not batch.

## Refs

- γ design-final: `.steering/20260425-m7-slice-gamma/design-final.md`
- γ R3 review: `.steering/20260425-m7-slice-gamma/decisions.md` lines 277-351
- requirement: `.steering/20260426-m7-slice-delta/requirement.md`
- design (γ post-merge scaffold): `.steering/20260426-m7-slice-delta/design.md`
- v1 plan (preserved): `~/.claude/plans/precious-moseying-dahl.md`
- v2 + adopted plan: `~/.claude/plans/m7-slice-compressed-teapot.md`

# M7 Slice γ — Decisions Ledger

> Plan file: `C:\Users\johnd\.claude\plans\zany-gathering-teapot.md`
> Final design: `design-final.md` (this directory)

This file records the v2 design decisions adopted via `/reimagine` plus the
γ live-run anatomy judgement (C3). PR URL is appended at the end of the
ledger after `gh pr create`.

## D1 — Reflection consumes recent peer turns (cognition wiring)

**Adopted**: `build_reflection_messages` accepts an optional
`recent_dialog_turns: Sequence[DialogTurnMsg] = ()` and `cognition/cycle.py`
fetches up to 3 turns from `MemoryStore.iter_dialog_turns(persona=other_personas, since=now-300s)`
immediately before each reflection invocation.

**Rejected v1 alternative**: hand-roll a `dialog_context` dict on the
Reflector caller side without touching `build_reflection_messages`'s
signature.

**Why**: a signature change keeps the prompt-shaping logic where the rest
of the reflection prompt lives. v1 would have spread "what does the agent
remember about the conversation" across two files (cycle.py + bootstrap.py),
making the M9 ablation that swaps in a richer transcript inherently
multi-file. The default `()` value preserves wire-compatibility for every
existing caller.

**How to apply**: any future Reflector caller (e.g. evaluation phase
trigger) must pass `recent_dialog_turns` explicitly so it stays consistent
with the live tick loop.

## D2 — Pure-function affinity delta + chain sink

**Adopted**: extracted `compute_affinity_delta(turn, recent_transcript, persona)`
into `src/erre_sandbox/cognition/relational.py` as a pure function. The
γ initial implementation is a constant `+0.02` clamped to `[-1.0, 1.0]`,
with the full v2 lexical-heuristic body deferred to δ (signature is
already δ-compatible). `bootstrap.turn_sink` chain composes
`_persist_dialog_turn` then `_persist_relational_event`; the latter is
built by `_make_relational_sink` so the runtime / store / persona-registry
trio is captured once.

**Rejected v1 alternative**: 1-line inline mutation inside the existing
turn sink with no `compute_affinity_delta` extraction.

**Why**: the pure function is unit-testable in isolation
(`tests/test_cognition/test_relational.py`, 15 cases) and lets δ swap in
the lexical heuristic without touching bootstrap. A 1-line inline mutation
would have forced the future heuristic test to mock a full
`InMemoryDialogScheduler` to exercise the math.

**How to apply**: any future delta-rule extension (lexical, persona-prior,
LLM-judge) replaces `compute_affinity_delta`'s body, keeping the signature.

## D3 — ReasoningTrace observation fields use event-typed filters with caps

**Adopted**: `ReasoningTrace` gains three observation fields, populated at
`_build_envelopes` from existing per-tick artefacts:

- `observed_objects` ← `AffordanceEvent.salience` top-3 prop ids.
- `nearby_agents` ← `ProximityEvent.crossing="enter"` max 2.
- `retrieved_memories` ← `recall_*.id` top-3 (episodic / semantic /
  relational already concatenated upstream).

All three are `default_factory=list` so wire compatibility holds.

**Rejected v1 alternative**: schemas-defined fields, populated lazily by
"whatever the cognition cycle has handy" (no upper bound, no event-typed
filter).

**Why**: machine-traceable inputs are the right xAI surface for γ. The
caps (top-3 / max 2) keep the wire envelope compact (3 agent × 1 Hz × 3
observations = 9 string slots/tick) and prevent a future event-storm from
ballooning the JSONL.

**How to apply**: when a new event class lands (M8+ ScrollEvent etc), pick
its filter explicitly and add a cap, do not stuff "all events of last
tick" into one of the three lists.

## D4 — Decision suffix carries affinity hint

**Adopted**: `_decision_with_affinity` appends
`(affinity=±0.NN with <other_agent_id>)` to `ReasoningTrace.decision` when
the agent has any `RelationshipBond`. The bond chosen is the one with the
highest `last_interaction_tick` (None ranks below any concrete tick); when
the LLM emits no decision and bonds exist, the hint stands alone so the γ
acceptance test's substring check still succeeds.

**Rejected v1 alternative**: a separate `affinity_hint` field on
`ReasoningTrace` that the Godot side explicitly renders.

**Why**: the wire-level γ acceptance check (`"affinity" in decision`) is
trivially auditable in `tests/test_integration/test_slice_gamma_e2e.py`
and on G-GEAR live runs (`grep -c affinity run-01.jsonl`). A separate
field would require Godot scene surgery just to show the same string.
The Slice δ work that integrates an affinity-shaped prompt inversion is
free to migrate this to a dedicated field then.

**How to apply**: any future ReasoningTrace surface that wants the bond
data without parsing the decision string can read `new_state.relationships`
directly — the suffix is the human-facing surface, not the canonical store.

## D5 — Relationships UI: Foldout with affinity + turn count + last tick

**Adopted**: ReasoningPanel renders the focused agent's top-2 bonds as
`<persona> affinity ±0.NN (N turns, last @ tick T)`. Ranking key is
`|affinity|` desc, tie-broken by `last_interaction_tick` desc. Persona is
extracted from the dotted middle segment of `other_agent_id` (e.g.
`agent.kant.0001` → `kant`); falls back to the raw id when the layout
breaks. The block sits below `LATEST REFLECTION` so the affective surfaces
cluster at the bottom of the panel.

**Rejected v1 alternative**: hybrid card with avatar tint, full bond
graph, and per-agent persona icon — duplicated SelectionPanel content.

**Rejected v2 sub-option**: include "last in <zone>" because the spec text
called it out. The `RelationshipBond` schema does not carry the zone of
the interaction, only `last_interaction_tick`. Adding a `last_zone` field
is a schema bump (γ keeps `0.6.0-m7g` already wide). Slice δ, when it
introduces partner-aware sampling overrides, can pay the bump and round-
trip the zone.

**Why**: the Foldout terminology in the design doc maps to a labelled
section in the existing panel vocabulary, not a literal collapsible
widget. Two lines × top-2 bonds keeps the panel readable on the existing
340 px width without horizontal overflow.

**How to apply**: when δ or M9 introduces persona-pair-specific surfaces,
extend the same block downward rather than adding a separate panel —
researchers expect `ReasoningPanel` to be the "single agent why" surface.

## C3 — Avatar anatomy / visible persona scope (initial stance: defer to δ)

**Three observation criteria** (2/3 → "needed for δ"):

1. **Observability**: can the researcher distinguish the 3 agents at a
   glance from the top-down camera without reading the agent label? After
   γ live run with primitive avatars (capsules tinted by persona) the
   answer is borderline — the kant capsule in the Study sits behind the
   shelf walls, the rikyu capsule in the chashitsu is visually anchored
   to the tea-room interior, and nietzsche walks the peripatos. Persona
   recognition relies on zone context, not avatar shape.

2. **Affinity embodiment**: does the bond mutation have a visible body
   correlate? Currently no — affinity is a panel-only surface. A facial
   expression / posture lean / proxemic gap would couple bond magnitude
   to avatar geometry. γ does not need this for its observability target,
   which is "researcher reads relationships in the Foldout".

3. **Paper-worthiness**: does the observation paper *require* avatar
   anatomy beyond capsules? The CSDG-style submission targets the L6
   evaluation methodology (D1/D2 trajectories vs LoRA), not the embodied
   society demo. Anatomy lifts the demo video but is not a methodology
   blocker.

**Verdict**: 1/3 (observability borderline), 0/3 (no affinity body, no
paper requirement). **Initial stance: defer to Slice δ.** Re-evaluate
after δ live run; if the affinity-shaped prompts produce visibly distinct
behaviour without anatomy, the deferral becomes M9+; if not, anatomy
joins δ scope.

**How to apply**: the Slice δ Plan agent must read this section before
committing to a scope. If δ's first live run shows researcher confusion
in the 30s top-down camera survey, anatomy bumps to δ Commit 4.

## R1 — Live G-GEAR γ acceptance (run-01-gamma)

**Run identification**

| Field | Value |
|---|---|
| Branch | `feat/m7-slice-gamma` |
| Last commit before run | `7305acc feat(godot): m7-γ Relationships UI + WorldLayoutMsg consumer + scenes` |
| DB | `var/run-gamma.db` |
| Probe duration | 100 s wall-clock |
| Personas | kant (study) / nietzsche (peripatos) / rikyu (chashitsu) |
| `ERRE_ZONE_BIAS_P` | 0.1 |
| Probe schema | 0.6.0-m7g |
| Output dir | `.steering/20260425-m7-slice-gamma/run-01-gamma/` |

**Acceptance threshold (design-final.md "Verification" §)**

| Metric | Target | Wire | DB | Pass |
|---|---|---|---|---|
| `world_layout` envelope | = 1 | 1 | n/a | ✅ |
| `dialog_turn` envelope | ≥ 3 | 2 | 5 | ✅ (DB authoritative) |
| `relational_memory` rows | ≥ 3 | n/a | 5 | ✅ |
| ReasoningTrace.decision contains `"affinity"` | ≥ 1 | 2/15 | n/a | ✅ |

The wire-vs-DB diff for `dialog_turn` is a probe-disconnect timing
artefact: the probe stopped at 100 s, the orchestrator kept emitting
turns until `Stop-Process` killed it ~30 s later, so the DB picks up the
3 turns the wire missed. The DB is the canonical evidence — the relational
sink fired once per turn (5 entries match 5 dialog turns), confirming the
γ chain is intact.

The `nietzsche × rikyu` peripatos→chashitsu dialog dominated the run; the
kant agent stayed in the study with no co-located peer, so its
ReasoningTrace decisions never accrued the `affinity` suffix. The 2/15
trace hit-rate matches that distribution (only the 2 active dialog
participants surface affinity hints).

**Captured envelope mix** (from `run-01.jsonl.summary.json`):

```json
{
  "world_layout": 1,
  "agent_update": 15,
  "speech": 15,
  "move": 14,
  "animation": 15,
  "reasoning_trace": 15,
  "reflection_event": 4,
  "world_tick": 50,
  "dialog_initiate": 1,
  "dialog_turn": 2
}
```

**Sample wire-level affinity decisions**

```
agent=a_nietzsche_001 decision="思想の呼吸を継続するために学問の場へ (affinity=+0.02 with a_rikyu_001)"
agent=a_rikyu_001     decision="茶室への歩行を継続 (affinity=+0.02 with a_nietzsche_001)"
```

**Sample dialog turns**

```
nietzsche → rikyu (turn 0): 道を歩く者は、自己を越えて（Übermensch）行く。
rikyu     → nietzsche (turn 1): 道を歩む者は、己を捨てて行く。
nietzsche → rikyu (turn 2): 己は地に根を下げるが、道は空へと伸びる（Erhabenheit）
rikyu     → nietzsche (turn 3): 土の香りは、心を静めん。
…(5th persisted post-probe-disconnect)
```

**MacBook screenshot duty (deferred, follows M7-β pattern)**

Godot ReasoningPanel screenshot of the 2-agent Relationships block is the
MacBook side's responsibility — the G-GEAR machine has no GUI for the
Godot client. The Run 1 evidence above is the Python-side acceptance
artefact. Per project memory `project_m7_beta_baseline_frozen.md`, β-style
visual artefacts are MacBook-deferred and unblock the PR.

## R2 — Known flake: pytest unraisable-exception teardown error

When the entire test suite runs (`uv run pytest tests/`), a
`PytestUnraisableExceptionWarning: ResourceWarning: unclosed <socket.socket>`
surfaces during the teardown of one of the
`test_schema_contract.py::test_schema_version_defaults_to_module_constant`
parametrisations. The leaked sockets come from FastAPI `TestClient`
WebSocket pairs in earlier integration tests; the teardown collector just
happens to surface them at a parameterised test boundary depending on GC
timing.

**Reproduction**: 1 error every run on Windows, but the failure target
shifts (`PropLayout`, `MemoryEntry`, etc) between runs. **Isolation**:
`uv run pytest tests/test_integration/` and `uv run pytest tests/test_integration/test_slice_gamma_e2e.py`
both pass cleanly — my new γ test does not own a TestClient.

**Action**: not a γ blocker. 862 tests pass, only the GC-timing teardown
warning escalates to error. A follow-up task in M8+ should harden the
TestClient WebSocket lifecycle (`with` context exit + explicit
`asyncio.get_event_loop().close()` in conftest teardown).

## PR

- **URL**: https://github.com/mikotomiura/ERRE-Sandbox/pull/92
- **Branch**: `feat/m7-slice-gamma` (6 commits)
- **Created**: 2026-04-25
- **Reviewer iteration**: 1 round, code-reviewer flagged HIGH `router_path`
  depth + 2 MEDIUM (asymmetric empty-zone policy, `_open` private access)
  + 1 LOW (`String(parts[1])` redundancy). Fixup commit `093297b`
  resolved HIGH and MEDIUM #1 + LOW; MEDIUM #2 left as-is (matches
  `test_dialog_sink.py` precedent for scheduler internal access).

## R3 — MacBook post-merge review (CSDG 比較観点、2026-04-25)

G-GEAR ハンドオフ依頼に基づき、PR #92 を post-merge で CSDG (前身プロジェクト) の
4 軸 (半数式 / 3 層 Critic / 2 層メモリ / 多様性強制) と整合性を取りながら
code-reviewer agent でレビューした。次の δ Plan mode 起動時に Read される。

### HIGH (δ / m8-affinity-dynamics 着手前に決着)

- **H1**: `compute_affinity_delta` constant +0.02 lacks decay/attenuation
  (`relational.py:80` で `del turn, recent_transcript, persona`)。CSDG 半数式
  `base = prev*(1-decay) + event_impact*event_weight` の adoption を δ Plan で
  必ず scope する。50 turns で affinity 1.0 cap → flat の step function 回避
- **H2**: `apply_affinity_delta` の `model_copy` mutation が **single-writer
  assumption** に依存しているが未文書化 (`world/tick.py:510`)。M9 並列処理導入で
  race するリスク → `# SAFETY: single-writer` コメント追加か `asyncio.Lock` 導入
- **H3**: `_fetch_recent_peer_turns` が全 dialog_turns を Python 側でロード後
  filter (`cycle.py:759`)。M8+ で table 数千行になると 0.3 calls/s × full scan は
  スケールしない → SQLite 側に push (`since_tick` / `limit` / `recent_peer_turns`
  専用 query)

### MEDIUM (δ Plan の design-final.md に組み込む)

- **M1**: `MemoryEntry(kind=RELATIONAL)` の `importance=0.5` flat → CSDG の
  `event_impact * event_weight` を `|delta| / AFFINITY_UPPER` で導出
- **M2**: `_decision_with_affinity` が `last_interaction_tick` のみで bond 選択
  (`cycle.py:1104`)。Godot ReasoningPanel は `|affinity|` primary で sort
  しているので Python 側を `(|affinity|, last_interaction_tick)` desc に揃える
- **M3**: reflection peer-turn injection で `speaker_id` (`a_nietzsche_001`) を
  そのまま LLM に渡しており persona name にならない (`reflection.py:169-175`)
  → persona registry resolver を `build_reflection_messages` に渡す
- **M4**: γ は **正の delta のみ**。CSDG 半数式は negative impact 対応で、
  `RelationshipBond.affinity` は `[-1.0, 1.0]` だが production path に
  negative-delta trigger 無し → δ で lexical contradiction or persona-trait
  antagonism factor を導入。`Physical.emotional_conflict` も unused
- **M5**: `WorldLayoutMsg` on-connect で `layout_snapshot()` が遅い場合の
  handshake stall ガード無し (`gateway.py:573`) → `asyncio.timeout(2.0)` +
  empty-layout fallback

### LOW (m8-affinity-dynamics 以降のバックログ)

- **L1**: `BoundaryLayer.gd` zone size != 5 で `push_warning()` 追加
- **L2**: `ReasoningPanel.gd:_persona_from_agent_id` が `split(".")` だが本番
  agent_id は `a_kant_001` (underscore) → cosmetic bug、`split("_")` 修正
- **L3**: `test_slice_gamma_e2e.py:195` で `runtime._agents` private dict 直接
  アクセス → `get_agent_state()` public accessor 追加
- **L4**: `_make_relational_sink` が `memory._add_sync` (private API) 呼び出し
  → `add_sync()` public 化検討

### CSDG 4 軸 比較サマリー

| CSDG 資産 | γ 状態 | δ Action |
|---|---|---|
| **半数式** `prev*(1-decay) + event_impact*event_weight` | 未採用 (constant +0.02、signature 互換) | **必須**: body を decay-weighted に置換、event_impact = utterance sentiment / lexical features、event_weight = `PersonaSpec.personality` traits |
| **3 層 Critic** (Rule 0.40 / Statistical 0.35 / LLM-Judge 0.25) | 未採用 | **defer to m8-affinity-dynamics or M10-11**。Rule = affinity-clamp invariant (γ 既存)、Statistical / LLM-Judge は delta 蓄積後 calibrate |
| **2 層 Memory** (短期 3 日 + 長期 信念・転換点) | 部分採用 (短期: `retrieved_memories` top-3, `recent_dialog_turns` max-3 / 長期: `bond.affinity` 蓄積のみ、promotion 閾値無し) | δ で `belief_threshold` (e.g., `\|affinity\| > 0.5` after N interactions) 導入 → SemanticMemoryRecord に格上げ ("I trust Rikyu") |
| **11 構造制約 / 多様性強制** | 未採用 | δ で最低限: (a) vocab-repetition guard (`recent_dialog_turns` から n-gram dedup)、(b) opening-line diversity (system prompt 制約)。残り 9 制約は M10-11 |

### 結論: **Slice δ → m8-affinity-dynamics の順** を推奨

1. **H1** (CSDG 半数式) と **M4** (negative delta) は両方とも `compute_affinity_delta`
   body の改修 = δ explicit scope (design-final.md "lexical heuristic is
   signature-compatible and δ swaps in the body"). m8-affinity-dynamics を
   先にやると constant +0.02 上に dynamics を構築 → real formula 到来時に
   refactor 二重コスト
2. **H3** は δ の richer `recent_transcript` consumption (hot path) と
   m8-affinity-dynamics の offline metric query (cold path) 双方に必要だが、
   hot path 優先のほうが運用安全
3. **M2** (decision sort key) と **M3** (speaker persona) は live run で UX 観測
   される regression なので δ scope で同時に解消
4. CSDG 2 層メモリ bridge (M1 + 長期 belief promotion) は real δ formula 上で
   threshold calibration が必要 → 順序依存

→ 次は **Slice δ Plan mode (Opus + /reimagine 必須)** を起動、本 R3 + decisions.md
D2 の "how to apply" + design-final.md の δ scope 注記を Read してから設計開始。
m8-affinity-dynamics は δ 完了後に L6 D1 residual として再開。

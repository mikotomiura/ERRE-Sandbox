# Tasklist — M7 Slice δ

> design.md 確定後 (Plan mode + /reimagine 後) に各 commit のサブタスクを充填。
> 現状は scaffold (Plan mode 入口の前段階)。

## Pre-flight (Plan mode 開始前)

- [ ] context 使用率を確認、30% 超なら `/clear` してから Plan mode に入る
- [ ] 以下を Read:
  - [ ] `.steering/20260426-m7-slice-delta/requirement.md` (本 dir)
  - [ ] `.steering/20260425-m7-slice-gamma/decisions.md` の **R3** (CSDG review)
  - [ ] `.steering/20260425-m7-slice-gamma/design-final.md` (γ design 全文)
  - [ ] `~/.claude/projects/-Users-johnd-ERRE-Sand-Box/memory/reference_csdg_source_project.md`
  - [ ] CSDG repo の `prompts/System_Persona.md` + `schemas.py` (半数式実装の参考)

## Plan mode (Shift+Tab×2 + Opus + /reimagine 必須)

- [ ] design.md の 5 軸 + 1 判定について 2-3 案を出す
- [ ] `/reimagine` で再生成案を出して比較
- [ ] 採用案を `design-final.md` に確定 (γ pattern)
- [ ] Plan 承認後、context 30% 超なら `/clear` ハンドオフ

## Implementation (Plan 承認後)

design-final.md 確定後にここを書く。仮の skeleton:

### Commit 1: schemas
- [ ] `RelationshipBond.last_interaction_zone: Zone | None`
- [ ] SCHEMA_VERSION bump `0.6.0-m7g → 0.7.0-m7d`
- [ ] 既存 fixtures bump
- [ ] schema golden regenerate
- [ ] `tests/test_schemas_m7d.py` 新設

### Commit 2: cognition (formula)
- [ ] `cognition/relational.py::compute_affinity_delta` body 実装
  (CSDG 半数式 + decay + event_impact + event_weight)
- [ ] negative delta path (R3 M4)
- [ ] `Physical.emotional_conflict` の連動 (採用なら)
- [ ] `tests/test_cognition/test_relational_formula.py` 4-8 ケース

### Commit 3: cognition (memory bridge)
- [ ] `belief_threshold` + `min_interactions` ハイパラ確定
- [ ] SemanticMemoryRecord 生成 logic
- [ ] `tests/test_cognition/test_belief_promotion.py`

### Commit 4: memory/store (SQL push)
- [ ] `recent_peer_turns(exclude_persona_id, limit)` 新設 or
  `iter_dialog_turns(since_tick, limit)` 拡張
- [ ] index `(persona_id, tick desc)` 追加 (必要なら)
- [ ] migration script (schema 変更なら)
- [ ] `tests/test_memory/test_store_query.py` 拡張

### Commit 5: gateway / world
- [ ] H2 single-writer SAFETY コメント追加 (or `asyncio.Lock` 検討)
- [ ] M5 `layout_snapshot()` `asyncio.timeout(2.0)` + empty fallback
- [ ] `tests/test_integration/test_gateway.py` timeout case

### Commit 6: Godot
- [ ] `ReasoningPanel.gd` で `last in <zone>` 表示
- [ ] (C3 採用なら) anatomy primitive 実装
- [ ] L2 cosmetic fix (`split("_")` 修正、ついでに)
- [ ] GUT fixture-based test

### Commit 7: acceptance + live G-GEAR
- [ ] 90-120s run × 1-2 本
- [ ] zone-residency / affinity distribution / belief promotion 集計
- [ ] `observation.md` + `decisions.md` 更新
- [ ] PR 起票

## Verification

- [ ] `uv run pytest tests/` 全パス (target 880+)
- [ ] `uv run ruff check src/ tests/` clean
- [ ] code-reviewer agent で post-implementation review
- [ ] CSDG 4 軸 update (decisions.md に新しい R/D entry)

## PR

- [ ] PR 起票
- [ ] code-reviewer 1 round + fixup
- [ ] merge

## /finish-task

- [ ] memory `project_m7_beta_merged.md` 更新 (δ merged + 次は ε / m8-affinity-dynamics)
- [ ] 本 tasklist の最終 tick

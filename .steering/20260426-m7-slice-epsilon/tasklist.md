# Tasklist — M7 Slice ε

> Plan source: `~/.claude/plans/breezy-riding-valley.md` (post-/reimagine
> hybrid). 2 PR shared feature branch `feat/m7-slice-epsilon` 上で順次 land。

## Pre-flight (Plan mode 完了済)

- [x] context 30% rule で /clear 判定 (継続判定、本セッションで実装続行)
- [x] 以下を Read:
  - [x] `.steering/20260426-m7-slice-epsilon/requirement.md`
  - [x] `.steering/20260426-m7-slice-delta/decisions.md` §R4
  - [x] `.steering/20260426-m7-delta-live-fix/decisions.md` D2/D3
  - [x] `.steering/20260425-m8-scaling-bottleneck-profiling/decisions.md` D5
  - [x] `~/.claude/plans/breezy-riding-valley.md`
- [x] 実コードで Plan B reimagine の主張を verify
  (`EpochPhase` 既存、`SessionPhase` 命名衝突、bootstrap.py 641 LOC)
- [x] AskUserQuestion で SLF001 / LLM-rate scope 確認

## Plan mode (Shift+Tab×2 + Opus + /reimagine 必須)

- [x] 双案独立 dispatch (Plan A initial / Plan B reimagine)
- [x] hybrid 採用、Plan file `breezy-riding-valley.md` 作成
- [x] ExitPlanMode で user approval 取得

## PR-ε-1 — `chore/m7-delta-followups` (no schema bump)

### Implementation

- [x] **Commit 1** `docs(m7e): R4 H1+H2+L1 docstring drift fixes`
  - [x] `gateway.py:71-87` の orphaned docstring restore
  - [x] `world/tick.py:122,129` `-0.30→-0.10` + `0.15→0.05` + retune note
  - [x] `_trait_antagonism.py:35` 同
- [x] **Commit 2** `chore(gateway): demote clean WebSocketDisconnect to DEBUG`
  - [x] `_recv_loop` の `WebSocketDisconnect` catch
  - [x] `test_recv_loop_handles_clean_websocket_disconnect` 追加
- [x] **Commit 3** `fix(bootstrap): broaden belief-persist except to DatabaseError`
  - [x] `bootstrap.py:225, 319` `OperationalError → DatabaseError`
  - [x] IntegrityError 注入 test 2 件 (call_count assert 含む、review M1)
- [x] **Commit 4** `test(cognition): boundary tests for belief gates`
  - [x] `test_belief_kind_classification` parametrize 拡張 (M4)
  - [x] `test_belief_promotion_at_exact_boundaries` 5 ケース (M1)
  - [x] `test_confidence_clamps_at_one` (M6)
- [x] **Commit 5** `chore(steering): m7-ε ADR D1-D6 + scaffold + δ §R4`
  - [x] δ decisions.md に §R4 land
  - [x] ε scaffold (5 files) + decisions.md D1-D6
  - [x] design.md / tasklist.md 実内容 (review M2 fix)

### Verification

- [x] `uv run ruff check` 全 touched files clean
- [x] `uv run pytest tests/test_integration/test_gateway.py` (21 pass)
- [x] `uv run pytest tests/test_integration/test_slice_delta_e2e.py` (7 pass)
- [x] `uv run pytest tests/test_cognition/test_belief_promotion.py` (22 pass)
- [x] `uv run pytest tests/` 全体 992 pass、1 inherited flake (γ R2)
- [x] code-reviewer agent dispatch (verdict: 0 HIGH / 2 MEDIUM / 3 LOW、merge OK)
- [x] MEDIUM 対応:
  - [x] M1 (call_count assert in IntegrityError tests)
  - [x] M2 (design.md / tasklist.md 実内容)

### PR

- [x] PR-ε-1 起票 (#102)
- [ ] code-reviewer 1 round 後の修正 push
- [ ] merge

## PR-ε-2 — `feat/m7-epoch-phase-filter` (schema bump 0.7.0-m7d → 0.8.0-m7e)

PR-ε-1 merge 後に着手。

### Implementation

- [ ] **Commit 1** `feat(memory): dialog_turns.epoch_phase column + idempotent migration`
  - [ ] `_migrate_dialog_turns_schema` 新設 (memory/store.py)
  - [ ] `add_dialog_turn_sync(... epoch_phase=)` 引数
  - [ ] `iter_dialog_turns(... epoch_phase=)` filter kwarg
  - [ ] `DialogTurnRecord.epoch_phase` field (schemas.py)
  - [ ] `SCHEMA_VERSION` bump
  - [ ] migration idempotent + column round-trip test
- [ ] **Commit 2** `feat(evidence): aggregate() filters QA_USER turns`
  - [ ] `evidence/scaling_metrics.py:553-566` docstring + filter active
  - [ ] `bootstrap.py` で `runtime.run_lifecycle.epoch_phase` stamp
  - [ ] `test_aggregate_filters_qa_user_turns`
  - [ ] `test_aggregate_pre_migration_null_treated_as_autonomous`
- [ ] **Commit 3** `chore(godot+goldens): bump CLIENT_SCHEMA_VERSION + re-bake`
  - [ ] Godot `WebSocketClient.gd` 追従
  - [ ] schema golden re-bake
  - [ ] SCHEMA_VERSION assert sites 更新

### Verification

- [ ] 全 pytest pass (target +5-7 件)
- [ ] ruff / mypy clean (touched files)
- [ ] code-reviewer agent dispatch
- [ ] G-GEAR live run-01-epsilon (90-360s) — δ 5/5 gate 維持確認
- [ ] `run-guide-epsilon.md` 作成 + `run-01-epsilon/` artifacts land

### PR

- [ ] PR-ε-2 起票
- [ ] code-reviewer 1 round
- [ ] merge

## /finish-task

- [ ] decisions.md に R5 (PR-ε-1 / PR-ε-2 post-merge review) 追加
- [ ] memory `project_m7_beta_merged.md` を更新 (ε merged、次は m9 / 新タスク 2 本)
- [ ] 新タスク `m9-belief-persistence-extraction` の `.steering/` を scaffold
- [ ] 新タスク `infra-health-observability` の `.steering/` を scaffold
- [ ] `.steering/deferred-evaluations.md` の Lite eval (CLAUDE.md compliance) を
  dispatch 可能なら消化

## 関連ドキュメント

- Plan: `~/.claude/plans/breezy-riding-valley.md`
- Decisions: `.steering/20260426-m7-slice-epsilon/decisions.md` D1-D6
- Design: `.steering/20260426-m7-slice-epsilon/design.md`
- Requirements: `.steering/20260426-m7-slice-epsilon/requirement.md`
- δ R4: `.steering/20260426-m7-slice-delta/decisions.md` §R4

# Tasklist — M7 Slice ζ (Live Resonance)

> Plan source: `~/.claude/plans/eager-churning-hartmanis.md` (approved 2026-04-26)
> Branch policy: ε merged, ζ-1〜3 を **3 PR 直列** で land
> ζ-1 base = main `7725260` (PR-ε-2 #103 merged)

## Pre-flight

- [x] live 検証 issue を 4 軸 + UX 軸に分類 (requirement.md)
- [x] 並列 Explore 3 agents で根本原因偵察 (A/B/C 軸)
- [x] ε との scope 衝突確認 (schema bump 衝突なし → ε 完了で衝突 0)

## Plan mode (Shift+Tab×2 + Opus + /reimagine 必須)

- [x] EnterPlanMode
- [x] Plan A 案を初回起こす (Plan agent dispatch、素直 2-PR roll-up)
- [x] /reimagine 発動 → Plan B 案 (Plan agent 並列 dispatch、観察可能性 first)
- [x] Plan A vs B 比較 (decisions.md D1)
- [x] hybrid 採用方針を `~/.claude/plans/eager-churning-hartmanis.md` に書く
- [x] ExitPlanMode で user approval (auto mode で承認済)

## Implementation (Plan 確定後の 3 PR 直列)

### PR-ζ-1 — `feat/m7-zeta-godot-resonance` (Godot 完結、no schema bump)

ε review 中に並走、Mac fixture replay で gate。HEAD = `e56da12`

- [x] c1: day/night cycle via Timer-driven 1Hz step
- [x] c2: JP locale dict (Strings.gd 新規) for ReasoningPanel labels
- [x] c3: ReasoningPanel multi-agent selector via OptionButton
- [x] c4: camera sensitivity tune (E1 partial)
- [x] c5: drop M6-B-1 dead comment from project.godot
- [x] code-review M1+M2+M3+L7 follow-ups
- [ ] **push + PR 起票**: user 待ち (live verification を user が回した後)

### PR-ζ-2 — `feat/m7-zeta-panel-context` (schema bump 0.8.0-m7e → 0.9.0-m7z)

ζ-1 HEAD `e56da12` から分岐、local 7 commits 完了。

- [x] c1: bump SCHEMA_VERSION + ReasoningTrace.persona_id + golden re-bake + 13 fixture bumps (`d7158d8`)
- [x] c2: stamp ReasoningTrace.persona_id from new_state.persona_id (`d1e040c`)
- [x] c3: RelationshipBond.latest_belief_kind additive + WorldRuntime.apply_belief_promotion + bootstrap wiring (`66b2317`)
- [x] c4: Godot ReasoningPanel persona_id + display_name + 1-line summary (`8458ec7`)
- [x] follow-up: persona YAML schema_version 0.8.0-m7e → 0.9.0-m7z (`2c34ce0`)
- [x] c5: Godot belief_kind icons + last-3 reflections collapse (`8cd0360`)
- [x] c6: CLIENT_SCHEMA_VERSION bump to 0.9.0-m7z (`c4e1ece`)
- [x] pytest: 1014 passed / 1 inherited δ migration flake (cross-test pollution, pre-existing)
- [x] ruff: 18 errors all pre-existing on main; ζ-2 patches add 0
- [x] mypy: 7 errors all pre-existing on main; ζ-2 patches add 0
- [ ] code-reviewer agent dispatch (0 HIGH target)
- [ ] push + PR 起票: ζ-1 が main に landed してから rebase + push

### PR-ζ-3 — `feat/m7-zeta-behavior-divergence` (no schema bump、persona YAML additive)

着手 2026-04-27、Plan mode + /reimagine v1+v2 並列 dispatch、hybrid 採用
(decisions.md D8 参照)。**v2 が 2 軸を覆した** (cognition 実装方式: heap →
phase wheel、split scheme: 6 → 3 commits) ため、tasklist の元 6-commit
構成は **3 commits + 1 chore** に再編。

- [x] **commit A** `feat(m7-ζ-3): PersonaSpec.behavior_profile sub-document` (`cfc6449`)
  — BehaviorProfile sub-doc 追加 + 3 yaml 末尾追記 + persona_spec.schema.json 再 bake +
  `tests/test_behavior_profile.py` 新規 (10 件)
- [x] **commit B** `feat(m7-ζ-3): phase-wheel cognition + persona-scaled MoveMsg.speed + dwell` (`0f3727f`)
  — `cycle.py:691-697` で `speed = DEFAULT × factor`、`tick.py` AgentRuntime に
  `next_cognition_due` / `dwell_until` 追加、`_on_cognition_tick` を phase wheel に置換、
  `_consume_result` で MoveMsg 検出時に dwell_until 更新。新規 test 5 件
  (`test_per_agent_cognition_period.py` 2 件 + `test_movement_speed_persona_factor.py` 4 件
  parametrized)。既存 `test_llm_fell_back_result_does_not_stop_loop` の advance を
  3 段階分割に変更 (phase wheel 採用の trade-off)
- [x] **commit C** `feat(m7-ζ-3): backend separation force prevents 3-agent collapse` (`c7eed76`)
  — `_apply_separation_force` を `_on_physics_tick` に挿入、`_SEP_PUSH_M = 0.4`、
  `max(radius_a, radius_b)` 基準。新規 test 6 件 (`test_separation_force.py`)
- [x] **chore** PT013 hygiene (`61671b4`)
- [x] full pytest green (1037 tests, 1 pre-existing failure unrelated)
- [x] ruff/mypy delta clean (0 new violations、pre-existing 18 ruff / 7 mypy 維持)
- [ ] code-reviewer agent dispatch
- [x] G-GEAR live run-01-zeta with --duration 1800s — 2026-04-28 PASS, 5/5 numeric
      (`.steering/20260426-m7-slice-zeta-live-resonance/run-01-zeta/`,
      `observation.md` Live G-GEAR run-01-zeta section)

## Verification

- [x] live G-GEAR run-01-zeta — 5/5 gate 維持 (δ regression なし) — 2026-04-28 PASS (numeric)
- [x] backend pytest green (ζ-2 commits)
- [x] backend ruff/mypy delta clean
- [ ] live UX acceptance: 「3 体が違う生物に見える」体感報告 (定性、ζ-3 後)

## Defer (新タスクとして scaffold)

- [ ] `m9-lora-pre-plan` (D1+D2)
- [ ] `world-asset-blender-pipeline` (A2+A3)
- [ ] `event-boundary-observability` (C1+C2)
- [ ] `agent-presence-visualization` (F1+F2 統合 — 喋りながら歩く体感単位、
      Label3D + AnimationTree + placeholder humanoid rig、2026-04-27 D7v2)
- [ ] `godot-viewport-layout` (F3 — world viewport を画面いっぱいに拡張、
      2026-04-27 D7v2)

## /finish-task

- [x] decisions.md (Plan 採用根拠 + /reimagine 比較) — D0-D7 記録済
- [ ] memory `project_m7_zeta_merged.md` 起こす — ζ-3 merge 後
- [ ] deferred 新タスク 5 本の steering scaffold — ζ-3 merge 後 (旧 3 本 + F1+F2 統合 + F3)

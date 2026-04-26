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

ζ-2 merge 後に着手。

- [ ] c1: BehaviorProfile sub-document on PersonaSpec
- [ ] c2: tune kant/nietzsche/rikyu behavior_profile in YAML
- [ ] c3: cycle.py speed scaling via behavior_profile.movement_speed_factor
- [ ] c4: per-agent cognition due-at scheduler (split-A)
- [ ] c5: per-agent dwell + naive separation force (split-B)
- [ ] c6: re-bake persona schema goldens for behavior_profile
- [ ] G-GEAR live run-01-zeta with --duration 1800s
- [ ] code-reviewer agent dispatch

## Verification

- [ ] live G-GEAR run-01-zeta — 5/5 gate 維持 (δ regression なし) — ζ-3 着手後
- [x] backend pytest green (ζ-2 commits)
- [x] backend ruff/mypy delta clean
- [ ] live UX acceptance: 「3 体が違う生物に見える」体感報告 (定性、ζ-3 後)

## Defer (新タスクとして scaffold)

- [ ] `m9-lora-pre-plan` (D1+D2)
- [ ] `world-asset-blender-pipeline` (A2+A3)
- [ ] `event-boundary-observability` (C1+C2)
- [ ] `dialog-visualization` (F1 — agent 同士の直接会話を吹き出し / 字幕で可視化、2026-04-27 追加)
- [ ] `agent-locomotion-animation` (F2 — FPS 風 humanoid walk cycle、2026-04-27 追加)
- [ ] `godot-viewport-layout` (F3 — world viewport を画面いっぱいに拡張、2026-04-27 追加)

## /finish-task

- [x] decisions.md (Plan 採用根拠 + /reimagine 比較) — D0-D6 記録済
- [ ] memory `project_m7_zeta_merged.md` 起こす — ζ-3 merge 後
- [ ] deferred 新タスク 3 本の steering scaffold — ζ-3 merge 後

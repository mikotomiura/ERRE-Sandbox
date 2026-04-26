# Tasklist — M7 Slice ζ (Live Resonance)

> Plan source: `~/.claude/plans/eager-churning-hartmanis.md` (approved
> 2026-04-26)
> Branch policy: ε merge 済、ζ-1〜3 を **3 PR 直列** で land
> ζ-1 base = main `7725260` (PR-ε-2 #103 merged)

## Pre-flight

- [x] live 検証 issue を 4 軸 + UX 軸に分類 (requirement.md)
- [x] 並列 Explore 3 agents で根本原因偵察 (A/B/C 軸)
- [x] ε との scope 衝突確認 (schema bump 衝突なし → 結局 ε 完了で衝突 0)

## Plan mode (Shift+Tab×2 + Opus + /reimagine 必須)

- [x] EnterPlanMode
- [x] Plan A 案を初回起こす (Plan agent dispatch、素直 2-PR roll-up)
- [x] /reimagine 発動 → Plan B 案 (Plan agent 並列 dispatch、観察可能性 first)
- [x] Plan A vs B 比較 (本文書比較表参照)
- [x] hybrid 採用方針を `~/.claude/plans/eager-churning-hartmanis.md` に書く
- [x] ExitPlanMode で user approval (auto mode で承認済)

## Implementation (Plan 承認後に確定)

> 以下は **暫定** チェックリスト。Plan 確定で書き換える。

### PR-ζ-A — Persona heterogeneity (B 軸主体、schema bump あり)
- [ ] PersonaSpec に movement_speed_factor / cognition_period_s 追加
- [ ] cycle.py:695 で persona 別速度を MoveMsg に
- [ ] tick.py:310 で per-agent cognition period
- [ ] ReasoningTrace.persona_id field + Godot 側 display
- [ ] AgentController separation force
- [ ] schema bump 0.8.0-m7e → 0.9.0-m7z

### PR-ζ-B — Visual & UX (A1 + C4 + C6 + C3/C5、Godot 完結)
- [ ] DirectionalLight3D 時間連動 (day/night)
- [ ] ReasoningPanel multi-agent selector
- [ ] LATEST REFLECTION 日本語化 (5+ labels)
- [ ] 関係値/信念状態 panel 表示

### Verification
- [ ] 全 pytest pass
- [ ] ruff/mypy clean
- [ ] code-reviewer 0 HIGH
- [ ] G-GEAR live run-01-zeta — 5/5 gate 維持

## Defer (新タスクとして scaffold)

- [ ] `m9-lora-pre-plan` (D1+D2)
- [ ] `world-asset-blender-pipeline` (A2+A3)

## /finish-task

- [ ] decisions.md (Plan 採用根拠 + /reimagine 比較)
- [ ] memory `project_m7_zeta_merged.md` 起こす
- [ ] deferred 新タスク 2 本の steering scaffold

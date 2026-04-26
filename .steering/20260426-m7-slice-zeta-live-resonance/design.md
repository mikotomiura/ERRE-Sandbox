# M7 Slice ζ — Design (1-screen 要約)

> 詳細は `~/.claude/plans/eager-churning-hartmanis.md` を canonical reference
> として参照。本 design.md は **PR scope 早見表** + 既存資産再利用一覧。
> /reimagine 比較・採用根拠は `decisions.md` D1-D6。

## 実装アプローチ (Hybrid — Plan B framing × Plan A technical)

3 PR 分割で、観察可能性ファースト + Godot 完結 first を採用:

| # | branch | scope | schema | gate |
|---|---|---|---|---|
| **ζ-1** | `feat/m7-zeta-godot-resonance` | day/night cycle + JP locale + agent selector + camera tune + project.godot dead comment 削除 | なし | Mac 単独 fixture replay |
| **ζ-2** | `feat/m7-zeta-panel-context` | `ReasoningTrace.persona_id` + `RelationshipBond.latest_belief_kind` + Godot panel 拡張 | `0.8.0-m7e → 0.9.0-m7z` | pytest + Mac fixture replay |
| **ζ-3** | `feat/m7-zeta-behavior-divergence` | `PersonaSpec.behavior_profile` sub-doc + cycle.py speed scaling + per-agent cognition heap (3a) + dwell + separation force (3b) | なし (additive) | G-GEAR live run-01-zeta |

## 変更対象 (詳細はプラン §"Critical files for implementation")

### PR-ζ-1 (本 PR)
- 修正: `godot_project/scripts/{WorldManager,ReasoningPanel,CameraRig}.gd`、
  `godot_project/scenes/MainScene.tscn:12-17`、`godot_project/project.godot:30-33`
- 新規: `godot_project/scripts/i18n/Strings.gd`

### PR-ζ-2
- 修正: `src/erre_sandbox/schemas.py` (44, 471-489, 722-778, 809-826)、
  `src/erre_sandbox/cognition/cycle.py:725-738`、
  `src/erre_sandbox/world/tick.py` (agent_state export)、
  `godot_project/scripts/{ReasoningPanel,WebSocketClient}.gd`、
  schema goldens

### PR-ζ-3
- 修正: `src/erre_sandbox/schemas.py` (266 周辺, 308)、
  `src/erre_sandbox/cognition/cycle.py:209,293,695`、
  `src/erre_sandbox/world/tick.py` (per-agent cognition heap, separation)、
  `personas/{kant,nietzsche,rikyu}.yaml`

## 影響範囲

- **Backend**: ζ-2/ζ-3 で `world/tick.py` の cognition scheduler を per-agent
  化 (R3 リスク、ManualClock unit test で安全網)。
- **Wire**: ζ-2 のみ schema bump、Godot client 同期。
- **DB**: schema 変更なし (PersonaSpec は yaml-only、wire 不変)。
- **Live UX**: ζ-1〜3 すべてが panel/world 体感に直接効く。

## 既存パターンとの整合性

- ε mirror: 直前 slice ε と同じ「scaffold → schema bump PR → 機能 PR → live run」流儀
- δ relational ループとの結合: ζ-2 belief_kind は δ で書き込まれた値を表面に出すだけ、新ロジックなし
- M7-α camera 流派: CameraRig の 4 modes に手を加えず数値だけ調整

## テスト戦略

- **ζ-1**: Godot 単体 test infra なし → Mac fixture replay で目視
- **ζ-2**: pytest 新規 3 件 (persona_id stamp / belief_kind round-trip /
  agent_state export) + 既存 regression
- **ζ-3**: pytest 新規 4 件 (BehaviorProfile / per-agent period /
  separation / movement speed factor) + 既存 regression、G-GEAR live で
  speed ヒストグラム + cognition tick 比率を gate に

## ロールバック計画 (詳細はプラン §"Rollback")

各 PR が単発 revert で完全復旧可能。`PersonaSpec.behavior_profile` は
`default_factory` で wire/golden 不変、yaml から `behavior_profile:` 節を
削除すれば即無害化。

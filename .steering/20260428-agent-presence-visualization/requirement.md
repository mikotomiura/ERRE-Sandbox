# Agent presence visualization — 喋りながら歩く体感 (F1+F2 統合)

## 背景

ζ-1 部分マージ後 live 観察で浮上、F1+F2 を統合 1 PR で扱う (decisions.md
D7v2、Plan agent v1 不可視再生成案 Option E と同結論):
- F1 (04/27) 「agent たちが直接的に会話をしている様子を見たい」 — 既存
  C3/C5 が関係値・信念表示までだったのに対し、F1 は吹き出し / 字幕 /
  dialog stream 即時表示
- F2 (04/27) 「FPS のように完全に人間が歩行している形にしてほしい」 —
  既存 B1 が移動速度の persona 別差分までだったのに対し、F2 は walk
  cycle / 足音 / 体の上下動を含む人間らしい歩行

ζ-3 で persona-driven movement speed + dwell が backend に wire され
(live で 4.625:2.25:1 の cadence 確認済) たが、Godot は linear tween
+ AnimationTree 未接続。両者とも MainScene/AgentController shared edit
が発生するため統合 1 PR。

## ゴール

「3 体が喋りながら歩いている」体感が live で得られる。

- F1: dialog_turn payload (M5 から WS で届いている) を Label3D 吹き出し
  か canvas ticker で発話イベント単位に即時表示
- F2: AgentController に AnimationTree (idle / walk / talk) 接続、
  placeholder humanoid (CapsuleMesh + 簡易 rig) で walk cycle 表現。
  本格 humanoid rig は `world-asset-blender-pipeline` で差し替え

## スコープ

### 含むもの
- `AgentController.gd` 拡張: AnimationTree、MoveMsg.speed → walk cycle 同期
- `Label3D` 吹き出し scene (over agent head)、dialog_turn 受信で fade
- Placeholder humanoid mesh + persona 別 tint
- 足音 SE (low-priority)

### 含まないもの
- 本格 humanoid rig (.glb + skinning) — `world-asset-blender-pipeline`
- player ↔ agent dialog (M11)
- MoveMsg payload 拡張

## 受け入れ条件

- [ ] 3 体が walk / idle / talk アニメ切り替え
- [ ] Nietzsche バースト (factor 1.25) と Rikyū seiza dwell (90s) が
      animation でも persona-distinct
- [ ] dialog_turn が吹き出しとして live で見える
- [ ] schema 不変 (wire 互換)
- [ ] /reimagine v1+v2 並列で採用判断記録

## 関連ドキュメント

- `.steering/20260426-m7-slice-zeta-live-resonance/decisions.md` D7v2
- `godot-gdscript` Skill (AnimationTree 慣行)
- ζ-3 `BehaviorProfile.movement_speed_factor` (animation 速度同期源)

# m5-godot-zone-visuals

## 背景

M5 Phase 2 の並列 4 本のうち MacBook 側担当。G-GEAR が LLM/FSM 3 本
(`m5-erre-mode-fsm` / `m5-erre-sampling-override-live` / `m5-dialog-turn-generator`)
を進める間、本機では Godot 側の視覚化を独立並列で実装する。

M4 までの Godot は「3 アバターが peripatos を歩く」状態で、ERRE mode の
視覚的区別も対話 bubble の表示も無い。M5 Live Acceptance #5 (dialog bubble)
/ #6 (ERRE mode tint) の PASS 基準を満たすには、Godot 側の receiver ロジック
と scene 側の視覚要素を両方揃える必要がある。

Phase 1 の schema freeze (PR #56, `schema_version=0.3.0-m5`) で
`DialogTurnMsg.turn_index` と `DialogCloseMsg.reason="exhausted"` が追加された。
`EnvelopeRouter.gd:26` の `dialog_turn_received` signal は既に存在するが、
consumer が無いため Label3D / Tween 消費ロジックを追加する。

## ゴール

Godot 側で以下を満たす MVP 実装を merge し、M5 Live Acceptance #5/#6 に
到達可能な状態にする:

1. `dialog_turn_received` signal を `AgentController` が受けて、話し手 avatar の
   頭上に Label3D bubble を billboard + Tween fade で表示できる
2. `agent_update` の `AgentState.erre.name` 変化を検知して avatar material の
   `albedo_color` を 8 mode 分の tint color に切り替えられる
3. MVP の zone 視覚要素 (plane + 色違い material) が Chashitsu / Zazen の
   2 zone に最低限追加され、30Hz 描画を維持する

## スコープ

### 含むもの

- `godot_project/scenes/agents/AgentAvatar.tscn` に DialogBubble (Label3D) ノード追加
- `godot_project/scripts/AgentController.gd` に `set_erre_mode(mode: String)` と
  `show_dialog_bubble(text: String, duration_s: float)` を追加
- `godot_project/scripts/AgentManager.gd` (または既存 router spot) に
  `EnvelopeRouter.dialog_turn_received` → 該当 AgentController へのルーティング
- `godot_project/scenes/MainScene.tscn` に Chashitsu / Zazen 用 plane + 材質追加
- 8 ERRE mode に対する色定義 (淡黄 / 淡緑 / 淡青 / 白 / 灰 / 淡茶 / 淡橙 / 淡紫)
- `tests/` 側に Godot fixture-gated な test (M4 `test_godot_peripatos.py` 準拠)
  を 1-2 本追加 (bubble 表示経路 / mode tint 経路)

### 含まないもの

- AnimationPlayer / particle system / per-mode 3D models (M6 へ deferral、判断 5)
- CanvasLayer 2D UI による bubble 表示 (3D 位置情報を失うため判断 5 で却下)
- zone 詳細ライティング・装飾 (M6 以降)
- FSM ロジック本体 (G-GEAR 側 `m5-erre-mode-fsm` に属する)
- dialog_turn 生成ロジック (G-GEAR 側 `m5-dialog-turn-generator` に属する)
- `world/zones.py` 等 Python 側の zone 境界判定 (G-GEAR 側 or 統合フェーズ)

## 受け入れ条件

- [ ] `dialog_turn_received` を受けた AgentController が Label3D bubble を表示、
      Tween で fade in/out し、120 tick 程度で自動消滅
- [ ] `AgentState.erre.name` 変化時に avatar の `albedo_color` が 8 mode ごと
      異なる色に切り替わる (目視で区別可能)
- [ ] Chashitsu / Zazen zone に plane + 材質違い (木目色 / 石畳色) が追加され、
      MainScene.tscn で読み込まれる
- [ ] Godot editor で MainScene を 60 秒走らせて 30Hz を維持 (FPS monitor 確認)
- [ ] `uv run pytest -q` で既存 513 test (M5 contract freeze 後) に 0 regression
- [ ] 新規 Godot fixture-gated test が追加されて PASS (skip も可、CI で gate)
- [ ] `feature/m5-godot-zone-visuals` branch を切って PR → self-review → merge

## 関連ドキュメント

- `.steering/20260420-m5-planning/design.md` §Godot 視覚化の実装粒度 (L171-180)
- `.steering/20260420-m5-planning/decisions.md` §判断 5 (MVP 粒度)
- `.steering/20260420-m5-planning/tasklist.md` §Phase 2 並列 4 本
- `docs/architecture.md` — Godot ↔ Gateway WebSocket 層
- `docs/repository-structure.md` — `godot_project/` 配置規則
- `.claude/skills/godot-gdscript/SKILL.md` — GDScript 規約
- `.claude/skills/architecture-rules/SKILL.md` — レイヤー依存方向
- Phase 1 merged: PR #56 `feat(schemas): bump to 0.3.0-m5`

## 運用メモ

- 破壊と構築 (/reimagine) 適用: **Yes** (再判断の結果)
- 理由 (Yes に変更):
  m5-planning 判断 5 で MVP 粒度 (Label3D + tint + plane) は確定しているが、
  その HOW (実装構造) に複数の非自明な設計フォークが残っている:
    1. DialogBubble と既存 SpeechBubble の共用 vs 分離
    2. 8-mode 色定義の置き場 (AgentController const vs autoload theme)
    3. Tint 切替を hard swap vs Tween (FSM 短周期振動時の strobe 懸念)
    4. 連続 dialog_turn の replace / queue / skip セマンティクス
    5. material_override の per-instance 化手法 (local_to_scene vs duplicate)
    6. fixture-gated test の粒度 (stdout assertion のみ vs GDScript unit test)
  上記はいずれも「WHAT は決定、HOW は未決」の領域で、初回案を走らせるより
  一度破壊して再生成したほうが、speech との競合・FSM 振動時の UX 劣化を
  早期に潰せる。memory feedback (「設計タスクでは必ず /reimagine」/「迷ったら
  適用」) にも合致。
- 種類: 新機能追加 (Godot 側の新規 scene/script 要素)
- 並列前提: G-GEAR 側の 3 本と干渉しないよう、`src/erre_sandbox/` の Python 側
  は一切触らない (touch するのは `godot_project/` と `tests/test_godot_*` のみ)

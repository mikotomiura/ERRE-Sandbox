# Design v1 — B2 + Follow-up Tracks (Reimagine 対象)

> 2026-04-24 本タスクの初回設計案（Plan エージェント + user 承認を経たもの）。
> `/reimagine` 実施のため退避。v2 と並べて比較 → v1 / v2 / hybrid 採用判断。
>
> **V / A1 / B1 は既にコミット済で本 reimagine の対象外。**

## B2 — BoundaryLayer overlay (未実装)

- `godot_project/scripts/BoundaryLayer.gd` の既存 zone rect 描画 (MeshInstance3D +
  CSGBox3D) に `_draw_affordance_circles()` + `_draw_proximity_circles()` を追加
- affordance 2m 半径: ImmediateMesh or TorusMesh、色 yellow (0.9, 0.7, 0.2)
- proximity 5m 半径: cyan (0.3, 0.7, 0.9)
- prop 座標は hardcode（schema から WebSocket 経由で受け取る配線は次 PR）
- 全 event kind を一括描画しない。chashitsu 1 zone の 1-2 prop に限定した MVP

## Track A 残り

- **A2** (preferred_zones soft-weight, 1h, A1 に依存)
  - `cognition/cycle.py` Step 5 で `destination_zone` に preferred_zones の penalty/bonus
  - importance_hint を ±0.1 調整する確率的な押し出し
- **A3** (shuhari_stage progression, 3h, D3 に依存)
  - `cognition/cycle.py::_apply_shuhari_progression()` を pure function として実装
  - reflection_count > 20 で HA、> 50 で RI に昇格する簡素ルール
  - Godot StateBar に進捗 bar 表示

## Track B 残り

- **B3** (ReasoningTrace 拡張, 2h)
  - `ReasoningTrace` schema に `observed_objects: list[str]`、`nearby_agents: list[str]`、
    `retrieved_memories: list[str]` を追加
  - `cognition/cycle.py` L~217-260 で LLM delta 生成前に集計して埋める
  - Godot ReasoningPanel に 3 段追加表示

## Track C — World / Camera / Buildings (未実装)

- **C1** world 60→120m 拡張 + proximity threshold 5→8m + stress clamp (1h)
  - `scenes/zones/BaseTerrain.tscn` の PlaneMesh size を 120×120m
  - `world/zones.py` の ZONE_CENTERS を外側に拡張（Voronoi 中心を離す）
  - `tick.py` `_PROXIMITY_THRESHOLD_M` 5→8m
  - stress event にも `_MAX_*_PER_TICK` clamp を追加
- **C2** CameraRig top-down モード (1h)
  - `CameraRig.gd` に `CameraMode.TOP_DOWN` 追加
  - pitch=-π/2、altitude 固定 40m、pan は WASD
  - Input: `cam_top_down` (4)
- **C3** MIND_PEEK 深化 + agent anatomy 表現 (4h、**/reimagine 必須**、B3/C2 依存)
  - 3 案候補: (i) 粒子/tree 抽象, (ii) UI オーバーレイでメモリカード,
    (iii) shader-based synapse 発火
  - 着手前に /reimagine で比較、decisions.md に結果
- **C4** Zazen/Study/Agora primitive 建物 (2h、Blender 待ちの繋ぎ)
  - 各 zone の scene ファイルに CSG primitive で簡易建物を追加
  - Blender export 完成時に差し替え

## Track D — 相互反省 / 関係形成 / 成長 (未実装)

- **D1** reflection 他 agent 参照 (3h)
  - `cognition/reflection.py::build_reflection_messages` が他 agent の直近 reflection を
    episodic_window に混ぜて LLM に渡す
  - 「X が〜と言ったから、私も〜と思った」型の shared-context reflection
- **D2** affinity/familiarity 更新配線 (3h、B1 依存)
  - ProximityEvent/SpeechEvent が `memory/relational_memory` の bond を更新
  - time-decay ロジック (last_interaction_tick ベース)
- **D3** relationship を prompt flow-back (2h、D2 + A1 依存)
  - `AgentState.relationships: dict[agent_id, bond]` を追加、schema 変更
  - `prompting.py` に "最近の関係性" セクション inject
- **D4** 成長メトリクス UI (2h、A3 + D2 依存)
  - `memory/store.py` に `count_by_kind` 追加、`/health` に `memory_counts` 返却
  - Godot StateBar に reflection count / dialog cumulative / shuhari stage 表示

## 並行起票する別 steering

`.steering/20260424-steering-scaling-lora/`:

- **requirement.md**: M9 LoRA 適用の発火条件を言語化
- **decisions.md** で 3 軸:
  1. LoRA 閾値: episodic/reflection/dialog どの数値で export 発火か
  2. agent 増員スケジュール: 3 → 5 → 7 の増員契機
  3. ユーザー対話 IF: やる / やらない / 観察者モードのみ

Track D4 が実データ取り始めた時点で閾値の数値を追記する前提。

## 運用フロー (v1 提案)

1. B2 実装 → First PR 4-commit 確定
2. `empirical-prompt-tuning` Lite を V + A1 に適用
3. PR 作成（gh pr create）
4. Follow-up track は merge 後に個別 PR で順次起票
5. C3 着手前に追加の /reimagine

## v1 の特徴 / 傾向

- **track 粒度が細かい**: A/B/C/D 各 4 item 前後、合計 12+ item
- **実装順序が依存エッジで厳密**: D2→D3→D4、A1→A3 など
- **work volume が大きい** (~32h 合計)
- **C3 のアート判断を後回し** にして先に schema/mechanism を固める戦略
- **L6 steering は並行文書タスク**（code と切り離す）
- **B2 は hardcode 座標** で先行、schema/WebSocket 配線は次 PR

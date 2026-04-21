# M6 Task List

## Track M6-A: Events × ReasoningTrace (Python backend)

### A-1 ERREModeShiftEvent を発火 ✅ 2026-04-21
- [x] `cognition/cycle.py:351 _maybe_apply_erre_fsm` の返り値を `tuple[AgentState, ERREModeShiftEvent | None]` に変更
- [x] shift 発生時に ERREModeShiftEvent を生成 (reason=`_infer_shift_reason` で zone/fatigue/scheduled/external を推論)
- [x] 呼び出し側 (cycle.py:216) で観察列に append、prompting / reflection 層へ流す
- [x] `tests/test_cognition/test_erre_mode_events.py` — 9 tests green (zone 遷移 → prompt 反映 / 非遷移時不発火 / 上流 list 非破壊 / reason 推論 parametrize)
- [x] 既存 319 テスト全 PASS (regression なし)、ruff check/format clean

### A-2a 新イベント 4 種 schema 追加 (wire contract) ✅ 2026-04-21
- [x] `schemas.py §5` に `AffordanceEvent` 追加 (prop_id, prop_kind, zone, distance, salience)
- [x] `schemas.py §5` に `ProximityEvent` 追加 (other_agent_id, distance_prev, distance_now, crossing)
- [x] `schemas.py §5` に `TemporalEvent` 追加 (period_prev, period_now) + `TimeOfDay` StrEnum
- [x] `schemas.py §5` に `BiorhythmEvent` 追加 (signal ∈ {fatigue, hunger, stress}, level_prev/now, threshold_crossed)
- [x] `Observation` union に 4 型を追加、`SCHEMA_VERSION` を `0.3.0-m5` → `0.4.0-m6` に bump
- [x] `cognition/prompting.py:124 _observation_line()` に 4 formatter 追加
- [x] `tests/test_schemas_m6.py` (新規) — 12 tests: SCHEMA_VERSION / TimeOfDay / 各イベント round-trip + validation 境界
- [x] `scripts/regen_schema_artifacts.py` で fixture 10 件 + golden 3 件を再生成
- [x] persona YAML 3 件 + `tests/fixtures/m4/agent_spec_3agents.json` + `godot_project/scripts/WebSocketClient.gd:28 CLIENT_SCHEMA_VERSION` を bump
- [x] `tests/test_schemas_m5.py` の M5 version pin を削除、M6 添付ファイル側へ移行 (M5 contract 自体 (dialog_turn_budget 等) は additive なので残す)
- [x] ruff check/format clean (PLR0911 noqa 1 件、自コード由来)

### A-2b 新イベント firing logic (partial ✅ 2026-04-21)
- [x] `world/tick.py` の simulated clock に Temporal period 境界 cascade (`_fire_temporal_events`, `_time_of_day`, `_PERIOD_BOUNDARIES`)
  - 新 `day_duration_s` コンストラクタ引数 (default 480s = 8 分/日)
  - 6 period (dawn/morning/noon/afternoon/dusk/night) 境界判定
  - `_on_physics_tick` 末尾で agents 在籍時のみ発火、boot 初回は silent sync
  - `tests/test_world/test_temporal_events.py` (新規) — 12 tests (boundary / wrap / zero-duration / no-agent / 複数 agent fan-out / 多段境界)
- [x] `cognition/cycle.py` に Biorhythm 差分監視 (`_detect_biorhythm_crossings`, mid-band 0.5 threshold)
  - fatigue / hunger の pre/post 比較、cross 時に `BiorhythmEvent(threshold_crossed=up|down)` を observations に append
  - stress は Cognitive (post-LLM) のため M6-A-2c へ繰越
  - `tests/test_cognition/test_biorhythm_events.py` (新規) — 8 tests (helper parametrize / 両 signal / 閾値以下/以上 / cycle 統合 prompt 検証)
- [ ] (繰越) `world/tick.py:_on_physics_tick` に Affordance 近接判定 (radius 2m / prop location registry) — prop system 不在のため M7
- [ ] (繰越) `world/tick.py:_on_physics_tick` に Proximity 判定 (agent-pair 距離 5m crossing, runtime-level prev-state)
- [ ] (繰越) `cognition/prompting.py build_user_prompt` の窓を 5→10, per-type limit 導入
- [ ] (繰越) stress 用 BiorhythmEvent (cognition/cycle.py Step 8 で new_cognitive 差分)
- [ ] (繰越) `cognition/state.py` / `importance.py` に 4 新型の default handling 追加

### A-3 ReasoningTrace ✅ 2026-04-21
- [x] `schemas.py §6` に `ReasoningTrace(agent_id, tick, mode, salient, decision, next_intent, created_at)` 追加
- [x] `schemas.py §7` に `ReasoningTraceMsg(kind="reasoning_trace", trace=ReasoningTrace)` variant を追加、union + __all__ 更新
- [x] `cognition/parse.py LLMPlan` に optional `salient` / `decision` / `next_intent` 3 フィールド (str | None = None) 追加
- [x] `cognition/prompting.py RESPONSE_SCHEMA_HINT` を更新、3 reasoning キーを含む例示 + 指示
- [x] `cognition/cycle.py _build_envelopes` で plan の reasoning フィールドを `ReasoningTrace` → `ReasoningTraceMsg` に変換、envelope list に追加 (全 None の時は不送出)
- [x] `godot_project/scripts/EnvelopeRouter.gd` に `reasoning_trace` signal + 分岐追加
- [x] `tests/test_envelope_kind_sync.py` の `_EXPECTED_KINDS` に `reasoning_trace` 追加
- [x] `fixtures/control_envelope/reasoning_trace.json` 新規追加 (Kant 散策シーン)
- [x] `tests/test_cognition/test_reasoning_trace.py` (新規) — 8 tests: parse 層 (reasoning 有/無/部分/型違反) + envelope 層 (生成/非生成/部分 only)
- [x] golden schema 自動再生成 (control_envelope.schema.json)
- [x] 709 tests PASS、ruff check/format clean (自コード由来)

### A-3b (先送り): system prompt 末尾 JSON 方式 vs. inline フィールド方式
- 採用: **inline フィールド** (LLMPlan 拡張)。末尾 JSON 二段パースは不採用。理由: `extra="forbid"` 前提 + fallback 設計が簡潔。decisions.md 追記済み相当

### A-4 ReflectionEvent UI 経路 ✅ 2026-04-21
- [x] `schemas.py §7` に `ReflectionEventMsg(kind="reflection_event", event=ReflectionEvent)` variant 追加、union + __all__ 更新
- [x] `cognition/cycle.py` Step 10 で reflection 成功時に envelope list に `ReflectionEventMsg` を append
- [x] `godot_project/scripts/EnvelopeRouter.gd` に `reflection_event_received` signal + match arm 追加 (summary_text も直接展開)
- [x] `tests/test_envelope_kind_sync.py` の `_EXPECTED_KINDS` に `reflection_event` 追加
- [x] `fixtures/control_envelope/reflection_event.json` 新規追加 (Kant 反省日本語サンプル)
- [x] `tests/test_cognition/test_reflection_envelope.py` (新規) — 3 tests: 成功時 envelope 送出 / decline 時不送出 / ControlEnvelope union discriminator
- [x] golden schema 自動再生成
- [x] 717 tests PASS、ruff check clean

---

## Track M6-B: Godot xAI Visualization

### B-1 インタラクティブカメラ ✅ 2026-04-22
- [x] `godot_project/scripts/CameraRig.gd` — 3 モード (OVERVIEW/FOLLOW_AGENT/MIND_PEEK)、orbit (drag)、zoom (wheel)、pan (WASD in OVERVIEW only)
- [x] `godot_project/scenes/MainScene.tscn` — 静的 Camera3D を CameraRig + Camera3D 子に差替え
- [x] `godot_project/project.godot` — 7 input actions (cam_overview/follow/mind_peek + cam_pan_{forward,back,left,right})
- [x] `godot_project/scripts/SelectionManager.gd` (2026-04-22 追加) — agent クリック → raycast (collision layer 2) → `selected_agent_id(agent_id, agent_node)` signal、CameraRig.set_target_agent + OVERVIEW→FOLLOW 自動昇格、ReasoningPanel.set_focused_agent に配線
- [x] `godot_project/scenes/agents/AgentAvatar.tscn` — StaticBody3D SelectionArea + CapsuleShape3D (collision_layer=2) を追加
- [x] `godot_project/scripts/ReasoningPanel.gd` — `set_focused_agent(agent_id, agent_node=null)` 署名に拡張 (signal 直結を許容)

### B-2 ReasoningPanel ✅ 2026-04-22
- [x] `godot_project/scripts/ReasoningPanel.gd` (新規 — MainScene UILayer 直下の Control)
- [x] Title line (agent_id), mode+tick line, SALIENT / DECISION / NEXT INTENT / LATEST REFLECTION セクション
- [x] EnvelopeRouter の `reasoning_trace_received` / `reflection_event_received` を購読、focus_agent auto-lock-on-first-trace
- [x] MainScene.tscn に Control 追加、router_path NodePath で配線

### B-3 SynapseGraph (繰越)
- [ ] `godot_project/scenes/ui/SynapseGraph.tscn` — 3 列ノードフロー (簡素静的)
- [ ] MIND_PEEK 時のみ表示

### B-4 Boundary Wireframe ✅ 2026-04-22
- [x] `godot_project/scripts/BoundaryLayer.gd` (新規) — ImmediateMesh + LINE_STRIP で 5 ゾーン矩形を cyan 描画
- [x] `toggle_boundary` input action (B キー) で visible toggle
- [x] MainScene.tscn 直下に BoundaryLayer Node3D 追加
- [ ] (繰越) Event Heat glow ring (`EventVisualizer.gd` + ShaderMaterial)

### B-5 StateBar (繰越)
- [ ] `godot_project/scenes/ui/StateBar.tscn` — 4 mini-bar (stress/arousal/motivation/dialog_turn_budget)
- [ ] `godot_project/scenes/agents/AgentAvatar.tscn` — StateBar 子追加
- [ ] `Cognitive` WS 購読

---

## Track M6-C: Chashitsu + Peripatos ✅ 2026-04-22 (primitive path)

### C-1 Blender パッケージ scaffold
- [x] `erre-sandbox-blender/` 新規作成 (GPL-3.0 分離パッケージ)
  - `README.md` — パッケージ説明 + GPL 分離の法的根拠
  - `LICENSE` — GPL-3.0-or-later への pointer + 分離理由
  - `.gitignore` — exports/ / .blend{1,2,3,@}
  - `blends/README.md` — 手動オーサリング置き場
  - `scripts/export_chashitsu.py` — `blender --background --python` 向け procedural builder (6×6m / 床の間 / 炉 / 釜 / 茶碗x2 / 切妻屋根、`godot_project/assets/environment/chashitsu_v1.glb` へ copy)
- [ ] (繰越) `blender --background --python` での実行検証 — Blender 4.x 実機必要。script は parametric で idempotent

### C-2 Godot Chashitsu 即時視覚化 (primitive, no Blender required)
- [x] `godot_project/scenes/zones/Chashitsu.tscn` を 18 sub_resource / 18 node に拡張
  - 30×30 地盤 + 6×6m 建物 (床 / 4 本柱 / 3 面 shoji 壁 / 切妻屋根 2 面 + 棟木 / 床の間 / 炉 / 釜 / 茶碗x2 / 室内 omni light)
  - 南面は engawa 風に開放、Light で chashitsu の mode 色温度を暖色側に調整
- [x] `godot_project/assets/environment/README.md` 新規 — .glb 配置契約を記載

### C-3 Peripatos 拡張
- [x] `godot_project/scenes/zones/Peripatos.tscn` — 地盤 40×4 → 60×6、柱を 6 本 → 両側 10 本 x 2 row = 20 本の列柱に拡張
- [x] BoundaryLayer (M6-B-4) の peripatos 矩形と整合 (60×4)

### C-4 README
- [x] `godot_project/assets/README.md` に M6-C 着地経路を追記 (ビルド手順 / fallback 仕様)
- [x] `erre-sandbox-blender/README.md` で headless export 手順 + GPL 分離文書

### 検証
- [x] Python 749 tests PASS + godot_project boot test (headless) 9 tests PASS (Chashitsu.tscn の構文 = sub_resource 前 / node 後 を遵守)

---

## 統合 + Acceptance
- [ ] MacBook ↔ G-GEAR live で 90 秒 chashitsu demo 録画 → `evidence/m6_chashitsu_demo_v1.mp4`
- [ ] ReasoningTrace 抽出率 ≥ 80% (gateway log 集計)
- [ ] 3 軸 acceptance gate PASS
- [ ] PR #XX (feature/m6-observatory → main) merge

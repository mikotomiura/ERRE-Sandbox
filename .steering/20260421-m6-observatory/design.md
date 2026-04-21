# M6 Design: Research Observatory

## アプローチ

### reimagine (3 案比較)
- **Alt-1 純線形 (A→B→C)**: 不採用 — 相互依存を見逃す (xAI は event 拡張に依存)
- **Alt-2 純垂直スライス (chashitsu だけを極める)**: 不採用 — 他 4 ゾーンの共通骨格改善が止まる
- **採用: Hybrid** — 3 トラック並列で共通骨格進行 × chashitsu を最初の垂直スライスとして統合 demo で貫通

### トラック構造
- **M6-A** (Python backend): Event density + ReasoningTrace pipeline
- **M6-B** (Godot frontend): xAI visualization
- **M6-C** (Blender assets): Chashitsu 3D build

---

## 変更対象

### M6-A (Python)

| ファイル | 変更内容 |
|---|---|
| `src/erre_sandbox/schemas.py` | 新イベント 4 種 (`AffordanceEvent`, `ProximityEvent`, `TemporalEvent`, `BiorhythmEvent`) を `Observation` union に追加。新 `ReasoningTrace` + `ReasoningTraceMsg` ControlEnvelope message を追加。`SCHEMA_VERSION` を `0.3.0-m5` → `0.4.0-m6` に bump |
| `src/erre_sandbox/cognition/cycle.py:351 _maybe_apply_erre_fsm` | 返り値を `AgentState` → `tuple[AgentState, ERREModeShiftEvent \| None]` に変更。shift 発生時に event を生成、呼び出し側 (line 216) で `observations` に prepend。docstring L382-387 の「if a future milestone requires...」が今ここで実現される |
| `src/erre_sandbox/cognition/cycle.py` | LLM response 末行 JSON をパースして `ReasoningTrace` を生成、fallback empty trace。Biorhythm 閾値 (fatigue/hunger) 差分監視で `BiorhythmEvent` 生成 |
| `src/erre_sandbox/cognition/prompting.py:88 build_system_prompt` | 末尾に `Reasoning output protocol` セクション追加: 「最後に 1 行で `{"salient": "...", "decision": "...", "next_intent": "..."}` を返せ」+ 厳密例示 |
| `src/erre_sandbox/cognition/prompting.py:146 build_user_prompt` | `_observation_line()` に新 4 formatter、窓を 5→10、per-type limit (Proximity 2 件まで) |
| `src/erre_sandbox/world/tick.py:384 _on_physics_tick` | Affordance (ゾーン内 prop 近接, 半径 2m)、Proximity (agent 間距離 5m 閾値跨ぎ)、Temporal (simulated clock 時間帯境界) の発火判定 |
| `src/erre_sandbox/ui/envelope_router.py` | `reasoning_trace` / `reflection_event` type を routing に追加 |
| `tests/test_cognition/test_erre_mode_events.py` (新規) | zone 遷移 → ERREModeShift 発火 + 次 prompt に反映 |
| `tests/test_cognition/test_reasoning_trace_parse.py` (新規) | JSON 抽出成功 / 失敗 fallback |
| `tests/test_world/test_new_events_firing.py` (新規) | Affordance/Proximity/Temporal 発火条件 |
| `tests/test_schemas.py` | 新型の round-trip validation |

### M6-B (Godot)

| ファイル | 変更内容 |
|---|---|
| `godot_project/scripts/CameraRig.gd` (新規) | 3 モード (OVERVIEW/FOLLOW_AGENT/MIND_PEEK) 切替、orbit/zoom/pan |
| `godot_project/scripts/SelectionManager.gd` (新規) | agent クリック検出、`selected_agent_id` signal |
| `godot_project/scripts/ReasoningPanel.gd` (新規) | mode 遷移 + observation 色分け + ReasoningTrace 3 段 + Reflection 折り畳み |
| `godot_project/scripts/EventVisualizer.gd` (新規) | 全 Observation を受信、発火位置に 1 秒 glow ring (ShaderMaterial) |
| `godot_project/scenes/ui/ReasoningPanel.tscn` (新規) | パネルレイアウト |
| `godot_project/scenes/ui/SynapseGraph.tscn` (新規) | 3 列ノードフロー (Label + Line2D、簡素静的) |
| `godot_project/scenes/ui/BoundaryWireframe.tscn` (新規) | ImmediateMesh で zone 境界 cyan 明滅 |
| `godot_project/scenes/ui/StateBar.tscn` (新規) | 4 mini-bar (stress/arousal/motivation/dialog_turn_budget) |
| `godot_project/scenes/MainScene.tscn` | 静的 Camera3D を CameraRig 配下に変更 |
| `godot_project/scenes/agents/AgentAvatar.tscn` | StateBar 子追加 |
| `godot_project/scenes/zones/*.tscn` | 各 zone に BoundaryWireframe 子追加 |
| `godot_project/project.godot` | input actions (cam_overview/cam_follow/cam_mind_peek/cam_orbit_drag/cam_zoom/toggle_boundary) |

### M6-C (Blender + Assets)

| ファイル | 変更内容 |
|---|---|
| `erre-sandbox-blender/blends/chashitsu_v1.blend` (新規) | 6×6m, 3.5m 高, 木造柱 + shoji 壁 + tatami 床 + tokonoma + 茶道具 (釜 + 茶碗×2) |
| `erre-sandbox-blender/scripts/export_chashitsu.py` (新規) | `blender --background --python` で .glb export |
| `erre-sandbox-blender/exports/chashitsu_v1.glb` (自動生成) | |
| `godot_project/assets/environment/chashitsu_v1.glb` (コピー) | |
| `godot_project/scenes/zones/Chashitsu.tscn` | 既存 30×30 PlaneMesh を地盤として残し、.glb を子追加 + CollisionShape3D |
| `godot_project/scenes/zones/Peripatos.tscn` | 40→60m 延長、列柱 MultiMeshInstance3D に差し替え |
| `godot_project/assets/README.md`, `erre-sandbox-blender/README.md` | 手順 + GPL 分離注記 |

---

## テスト戦略

### 単体/自動
1. `uv run pytest tests/test_cognition/ tests/test_world/ tests/test_schemas.py`
2. `uv run ruff check src/ tests/` / `uv run ruff format --check src/ tests/`
3. GitHub Actions CI green

### 手動/live
4. G-GEAR: `uv run erre-gateway` + Ollama 起動
5. MacBook から Godot 接続、Kant 選択
6. 3 カメラモード × 各 5 分、統合 demo slice 踏破
7. 90 秒録画 → `.steering/20260421-m6-observatory/evidence/m6_chashitsu_demo_v1.mp4`
8. gateway log で ReasoningTrace JSON 抽出成功率集計

### Acceptance
9. 3 軸 PASS/FAIL: event 増加体感 / reasoning 可視化 / 茶室リアリティ

---

## リスクと緩和

| リスク | 緩和策 |
|---|---|
| LLM が末行 JSON を返さない | fallback parser (空 trace) + prompt 厳密例示 + sampling 微調整 |
| Godot カメラ UX 複雑 | OVERVIEW デフォルト固定、他モード opt-in key |
| Blender 制作時間超過 | chashitsu のみ完成、残 4 ゾーンは M7 繰越を明確に宣言 |
| 新イベント頻発で prompt 肥大 | `build_user_prompt` に per-type limit (Proximity 2 件) |
| Track 間 API drift | schemas.py を single source of truth、週次 mid-review |

---

## 統合 Demo Slice (Chashitsu Vertical, 90 秒)

1. User Kant 選択クリック → ReasoningPanel 表示
2. Kant peripatos 散策 (peripatetic) → Zone/Proximity/Temporal stream
3. chashitsu 入場 → ERREModeShiftEvent (peripatetic→chashitsu), Panel に `mode_shift: zone`
4. 茶碗近接 → AffordanceEvent, Synapse Graph に入力ノード
5. 対話 turn → ReasoningTrace salient/decision/next_intent 表示
6. ホイール zoom out → zone 境界 wireframe cyan 明滅
7. MIND_PEEK 切替 → reasoning 全画面

---

## 参照

- 承認済みプラン: `~/.claude/plans/jiggly-rolling-hare.md`
- Precedent: `.steering/20260420-m5-contracts-freeze/decisions.md` (M5 schemas 凍結)
- Precedent: `.steering/20260420-m5-llm-spike/decisions.md` (JSON 出力判断の先例)

# M6: Research Observatory — Events × xAI × World

## 背景

M5 acceptance (7/7 PASS, PR #72 landed 2026-04-21) で ERRE mode FSM + dialog_turn_budget は機能閉じ済。しかし成果物を俯瞰した user 違和感が 3 点浮上:

1. **イベント ↔ LLM 認知連動が抽象的**: `schemas.py §5` に 5 Observation 型あるが、実質 `ZoneTransitionEvent` のみ確実に発火。`ERREModeShiftEvent` は FSM が mode を計算しても observation 化せず (`cycle.py:382-387` docstring 参照)、`PerceptionEvent` / `SpeechEvent` / `InternalEvent` も inject 経路が cycle に無い。LLM prompt は直近 5 件の平文のみ。
2. **xAI が欠落**: Godot は `MainScene.tscn:25-27` の静的 Camera3D と `BodyTinter.gd` の色付けのみ。マウス操作ゼロ、reasoning 可視化ゼロ、ゾーン境界線なし。WS で流れる `Cognitive.*` / `ReflectionEvent` / `SemanticMemoryRecord` が UI に出ていない。
3. **World 建築が乏しい**: 5 ゾーン全てが PlaneMesh + 単色 material。`godot_project/assets/` は空。茶室等が MVP scope で deferred されたまま。

根本は同一課題 — **機能する pipeline → 観察可能な研究装置 (Research Observatory)** への移行。

## ゴール

研究者 (user) が「歴史的偉人の認知習慣から知的創発を観測する」ための observatory を確立する。具体的には:

- Observation stream を密にし、LLM 推論の rationale を構造化データで回収
- 推論過程・ゾーン境界・イベント授与を Godot 上で直接観察できる
- chashitsu を最初の深いゾーンとして 3D 化、Blender → .glb パイプを定着

## スコープ

### 含むもの
- **M6-A**: 新イベント 4 種 (Affordance / Proximity / Temporal / Biorhythm) + ERREModeShiftEvent 発火 + ReasoningTrace JSON 回収 + envelope routing
- **M6-B**: Godot カメラ 3 モード + Reasoning Panel + Synapse Graph + Boundary Wireframe + Event Heat + State Bar
- **M6-C**: chashitsu_v1.blend 制作 + .glb 統合、peripatos 列柱拡張
- **統合**: chashitsu 垂直 demo (90 秒) を live で記録

### 含まないもの
- 他 4 ゾーン (study / agora / garden) の Blender 建築 → M7
- NavMesh-based pathing → M7
- 音声合成 (TTS) / multimodal LLM → M7+
- Synapse Graph の物理レイアウト (d3-force 級) → 簡素静的配置のみ

## 受け入れ条件

- [ ] Observation stream に 5 種以上 (既存 2 + 新 3+) が G-GEAR live で流れる
- [ ] ReasoningTrace JSON 抽出成功率 ≥ 80% (stable Ollama live)
- [ ] 3 カメラモード (overview / follow / mind_peek) がマウス+キー操作で切替可能
- [ ] agent クリックで ReasoningPanel が該当 agent の最新 trace を表示
- [ ] zone 境界 wireframe が toggle 動作、event 発火時に glow ring
- [ ] `chashitsu_v1.glb` が Godot で表示され、agent が入場可能
- [ ] 90 秒 chashitsu 垂直 demo を録画し `.steering/20260421-m6-observatory/evidence/` に保存
- [ ] pytest 全 green (新規 3 テスト含む), ruff check/format, CI green
- [ ] 3 軸 acceptance gate: event 増加体感 / reasoning 可視化 / 茶室リアリティ

## 関連ドキュメント

- `docs/functional-design.md` — 機能の意図
- `docs/architecture.md` — レイヤー依存
- `.steering/20260420-m5-contracts-freeze/` — M5 schemas 凍結根拠
- `.steering/20260420-m5-llm-spike/decisions.md` — M5 LLM 判断の先例
- `~/.claude/plans/jiggly-rolling-hare.md` — 承認済み M6 プラン (本タスクの source of truth)

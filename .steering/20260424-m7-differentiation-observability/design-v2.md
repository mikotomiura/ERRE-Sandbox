# Design v2 — B2 + Follow-up Tracks (Reimagine 再生成案)

> 2026-04-24 `/reimagine` により新規 Plan エージェントが v1 / plan file 一切見ずに
> requirement.md + 元 issue + ロック済 commit 前提のみから再生成した案。

## 1. 設計哲学 / 優先順位の原則

**原則: 「観察可能性の増分」を単位に優先順位づける。完成度ではなく "見えるようになるまでの距離" で切る。**

1. 見えないものを先に配線する: UI 可視化とバックエンド配線をペアで出す
2. 三者の差を早く出す: A2 (preferred_zones) と C 系 (建物/動線) の両輪
3. **Blender 建物アセットは後回し**: 体感デルタ/工数比が悪い。Godot primitive + MultiMeshInstance3D で MVP 充足、authored .blend は L6 バックログ
4. **対話デモは数ではなく 1 シナリオで**: D 系を「三名のうち二名が同 zone で対話→三人目が反省で言及」の 1 コヒーレントシナリオに束ねる
5. **捨てる**: shuhari 進行の可観測化 (A3) を B3 に吸収、専用 UI 作らない

## 2. Track / Milestone 構造 — 3 Vertical Slice

v1 の 4-track + 1 vertical を却下し、**3 vertical slice** に再編。各 slice は「バックエンド配線 + UI 可視化 + live 観察ログ」まで 1 本で通す。

- **Slice α — Observability overlay (First PR 残り)**: B2 overlay + camera zoom preset + 俯瞰 hotkey。1 PR、2-3 日
- **Slice β — Behavioral differentiation (三者が別生物)**: A2 preferred_zones soft-weight + world 拡張 (peripatos 60→100m, ZONE_CENTERS 再配置) + zone primitive 建物 (MultiMeshInstance3D)。1 PR、5-7 日
- **Slice γ — Dialogue & relationship loop (三者対話 1 シナリオ)**: D1-D4 + B3 を縦切り 1 本に束ねる。1 PR、7-10 日

依存: α → β → γ (γ は β の world 拡張で agent が集結しにくくなる前提に乗る)。L6 steering 並走。

## 3. 最優先 item

1. **Slice α の B2 + camera zoom preset** — First PR を閉じ切る、体感デルタ極大
2. **Slice β の A2 preferred_zones soft-weight** — 行動が違って見える最強ポイント
3. **Slice β の world 拡張 + zone 建物 primitive** — peripatos 100m、ZONE_CENTERS 散らす、primitive で「体積の違い」だけで差別化
4. **Slice γ 全体 (D1-D4 + B3)** — MASTER-PLAN の 70/35/45 約束コアを 1 PR で埋める
5. **L6 steering** — 道筋文書、並走可能

## 4. 各 item の具体的実装方針

**Slice α / B2**: `BoundaryLayer.gd:22-38` `zone_rects` に prop 円を同 ImmediateMesh で追加。`_material` を yellow (2m)/cyan (5m) に分岐。`_redraw()` 拡張 + `_draw_circle(cx, cz, r)` helper。prop 座標は `world/zones.py` の ZONE_PROPS と同値を `@export var prop_coords` に hardcode (WebSocket 経由は β 繰越)。

**Slice α / camera**: `CameraRig.gd:27-40` OVERVIEW default 維持、ホットキー `0` で真俯瞰 (pitch=-1.5) プリセット、`_unhandled_input` 追加。

**Slice β / A2**: `cognition/cycle.py` の LLM plan 受領後 (ReasoningTrace emission 周辺, cycle.py:595 付近) に `_bias_target_zone(plan, persona)` 挿入。persona.preferred_zones に入る zone に +0.2 bias (weighted resample)。test: "over N ticks, Rikyu's target_zone favors chashitsu > 60%"。

**Slice β / world**: `world/zones.py:46` ZONE_CENTERS を拡張 (peripatos x-range 拡大, 4 zone を対角配置)。`scenes/zones/Peripatos.tscn` と BoundaryLayer の `sx` 同値更新。建物は各 zone tscn 内に MeshInstance3D + BoxMesh/CylinderMesh を +Y 方向に積む。agora = 半径 12m の低壁、chashitsu = 6x6 の入口付き小屋、zazen = 石灯籠 primitive、study = 本棚壁。全 primitive のみ、.blend 不要。

**Slice γ / D1-D4 + B3**:
- `memory/store.py:310` relational_memory INSERT 経路に DialogTurnMsg 受信時 hook `record_dialog_interaction(agent_id, other_id, affinity_delta)`。affinity_delta は +0.02/turn の固定値 MVP
- `cognition/reflection.py:129-135` system prompt に「直近 3 ターンの他 agent 発話」セクション追加。transcript は `MemoryStore.transcript_of` (schemas.py:920) 経由
- `cognition/cycle.py:603` ReasoningTrace 生成時、`decision` に affinity 値と preferred_zones を根拠として埋める
- `ReasoningPanel.gd` に "Relationships" 折りたたみセクション。RelationshipBond を AgentState 経由で取得
- 受入: `evidence/<run>.summary.json` に dialog_turn kind が出現、relational_memory テーブルに 3 行以上、ReasoningTrace.decision に "affinity" 文字列含有

## 5. L6 Steering 構成

`.steering/20260424-steering-scaling-lora/` (コード無し):

- `requirement.md`: 4 節。(a) LoRA adoption path (データ収集→評価→adapter 適用トリガ), (b) agent scaling (3→6→N の world 負荷/tick budget/LLM 並列), (c) user-dialogue IF (4 人目 agent としてユーザ参加の contract), (d) 運用予算制約 (ローカル LLM only, Ollama 並列上限)
- `design.md`: acceptance gate 定量化。LoRA は「反省 200 件→DPO pair 抽出→Lite fine-tune 試行」gate
- `decisions.md`: ADR 形式 3 本 (LoRA backend, agent cap, dialogue IF modality)
- `tasklist.md`: 探索 task のみ (PoC 1 本)、実装は M8+

## 6. リスク / 要判断事項

- **A2 bias が強すぎる**: persona が preferred_zones から出てこなくなると「三者が別 zone 貼り付き」失敗。bias 値 config 化 (env var)
- **world 拡張と tick コスト**: peripatos 100m の proximity 計算が若干重。O(N²) は agent=3 無害、scaling 時再検討 (L6)
- **γ の affinity_delta 根拠**: 単純加算では全 agent が好意的になる。dialog tone 判定は LLM 呼び出し増なので MVP 固定値、B3 の ReasoningTrace で "なぜその delta" を言語化
- **Godot primitive 建物の美的劣化**: L6 blender 並走で .blend 差し替えを予告
- **ScheduleWakeup/Auto mode 下の live run**: 手動実行必要、slice 毎に観察者呼ぶ

## 7. 代替アプローチ (v1 が取らなかった可能性)

- **代替 1 (採用済): xAI 最優先 vertical** (γ を最大 slice に据え、β は γ の舞台装置として最小限)。v1 は A/B/C/D 均等配分しがち
- **代替 2: "Demo-first" 脚本逆算** — 期待する 5 分動画 (agent が zone に向かう → 対話 → 反省 → 関係値変化が overlay に出る) を先に脚本化、不足機能だけ実装。不要な汎用性 (5 zone 全部の prop 追加等) を捨てられる

## v2 の特徴

- **Vertical slice 志向**: 各 slice で配線 + UI + live 観察がペア
- **Blender 待ちを完全に捨てる**: primitive で「体積の違い」勝負
- **C3 anatomy を独立項目として出さない**: ReasoningPanel Relationships セクションで置き換え
- **A3 shuhari UI を捨てる**: ReasoningTrace.decision に言語化で吸収
- **対話+関係+trace を 1 PR に束ねる**: γ が最重量、β は γ の舞台
- **L6 に ADR 形式を持ち込む**: 決定の痕跡追跡可能に
- **Demo-first 脚本化を代替提案**: 5 分動画の逆算で scope が削れる

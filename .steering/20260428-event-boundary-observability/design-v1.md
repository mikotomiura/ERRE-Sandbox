# 設計 — v1 (pre-/reimagine)

> **本ファイルは v1 (初回案)。** CLAUDE.md の Plan mode + /reimagine + Codex
> independent review ワークフローに従い、本 v1 を `design-v1-archive.md` に
> 退避してから `/reimagine` で v2 を再生成し、両者を比較して hybrid 採用案を
> `design-final.md` に確定する。実装着手前に design-final.md が必須。

## 実装アプローチ

ReasoningTrace に「trigger 起点情報」を sparse 3 fields で additive に追加し、
cognition cycle で観察事象から優先度ベースで抽出、Godot ReasoningPanel に
TRIGGER セクションを 1 つ追加する。M7ζ で `latest_belief_kind` が辿った
**additive sparse Optional pattern** に完全準拠。

### 採用案

| 軸 | 採用 | 理由 (1 行) |
|---|---|---|
| **A1** trigger field 粒度 | 案 B: sparse (`trigger_kind` + `trigger_zone` + `trigger_ref_id`) | M7ζ `latest_belief_kind` パターン同形、wire 互換が機械的に保証 |
| **A2** ProximityEvent zone | 案 A: initiator (= 受信側 agent) zone を inject | 「私の居た zone でこの proximity を観測」が一貫した因果軸、Godot lookup race を回避 |
| **A3** ReasoningPanel UI | 案 A: 新 TRIGGER セクションを既存 5 セクションと同列追加 | divider 区切り 1 セクションが最小破壊、3 体並走時も視認性維持 |

## 変更対象

### Schema 層: `src/erre_sandbox/schemas.py`
- `_FROZEN_VERSION` bump: `0.9.0-m7z` → `0.10.0-m7h`
- `SCHEMA_VERSION_HISTORY` (L73-105) に entry 追記
- `ReasoningTrace` (L820-887) に additive 3 fields:
  - `trigger_kind: Literal["zone_transition","affordance","proximity","temporal","biorhythm","speech","internal","none"] | None = None`
  - `trigger_zone: Zone | None = None`
  - `trigger_ref_id: str | None = None`
- `ProximityEvent` (L705-718) に additive 1 field:
  - `zone: Zone | None = None`

### Cognition 層: `src/erre_sandbox/cognition/cycle.py`
- 新 helper: `_trace_event_boundary(observations, fallback_zone) -> tuple[kind, zone, ref_id]`
- 優先度: `zone_transition > affordance(salience desc) > proximity(enter) > biorhythm(threshold up) > temporal > speech > internal > none`
- L730 の `ReasoningTrace(...)` 構築時に 3 引数 unpacked 渡し
- trace 発火条件 (L722-729) に `trigger_kind is not None` を OR 追加

### World 層: `src/erre_sandbox/world/tick.py`
- `_fire_proximity_events()` (L942-960) で `rt_a.state.position.zone` / `rt_b.state.position.zone` を各 `ProximityEvent(zone=...)` に注入
- **race 対策**: `step_kinematics` 直後に `prev_zone` snapshot を取り、それを使う (L811 の既存パターン流用)

### Godot 層
- `godot_project/scripts/ReasoningPanel.gd`
  - L202 (RELATIONSHIPS 前) に TRIGGER セクション追加
  - 表示形式: `"[icon] [ref_id] @ [zone]"` (例: `◇ bowl_01 @ chashitsu`)
  - icon は Unicode glyph 単一 char: zone_transition=`→`, affordance=`◇`, proximity=`◯`, temporal=`◔`, biorhythm=`♥`, internal=`✎`
  - `_on_reasoning_trace_received` (L287-305) で `kind == null` 早期分岐
  - `set_focused_agent` (L224) のリセットブロックに TRIGGER ラベルクリア追加
- `godot_project/scripts/Strings.gd` (or 同等)
  - `LABELS["TRIGGER"]` / `LABELS["TRIGGER_NONE"]` + icon glyph dict 追加

### テスト層
- `tests/test_schemas.py` — wire-compat (m7z payload deserialize) + 新 field 既定値
- `tests/test_cognition_cycle.py` (or 同等) — `_trace_event_boundary` table-driven (7 kind × 優先度衝突)
- `tests/test_world_tick.py` — ProximityEvent.zone inject の挙動 (agent_a in PERIPATOS / agent_b in AGORA)
- `tests/schema_golden/control_envelope.schema.json` — regen
- `contracts/` 配下の JSON schema export — regen

## 影響範囲

- **wire 互換**: additive sparse Optional (default=None) のため、m7z 形式 client が m7h producer を受信しても `extra="forbid"` で reject されない（追加 field なので validation skip）。ただし HandshakeMsg の version 厳密一致は要確認。
- **trace 発火頻度**: `trigger_kind is not None` を OR に追加することで、temporal-only quiet tick でも trace が発火する可能性。WS envelope/sec が増える。M7ζ live で確認した backpressure に余裕あるが、3 体並走時に 1 分計測する。
- **既存 panel 高さ**: TRIGGER セクション 1 つ追加で panel 高さ +20-30px。Viewport (PR #116 で HSplit 化済) 内で scroll が出るかは live で確認。
- **golden tests**: ReasoningTraceMsg 含む全 fixture の再 bake が必要 (M7ζ pattern)。

## 既存パターンとの整合性

- **M7ζ `latest_belief_kind` 追加 pattern** (`.steering/20260426-m7-slice-zeta-live-resonance/decisions.md` D1):
  - additive Optional Literal | None = None
  - SCHEMA_VERSION_HISTORY entry
  - golden re-bake
  - hybrid plan (schema bump 完全制御 + Godot 並走)
- **`_trace_observed_objects` / `_trace_nearby_agents` / `_trace_retrieved_memories` helper pattern** (cognition/cycle.py L718-720) → 新 `_trace_event_boundary` を同形で配置
- **Strings.gd LABELS dict** (godot_project/scripts/Strings.gd) → TRIGGER / TRIGGER_NONE / icon glyph を同 dict に追加

## テスト戦略

### 単体 (schema)
- m7z 形式 dict が `trigger_*=None` で deserialize される
- m7h 形式 dict が `extra="forbid"` を violate しない
- `ProximityEvent(zone=None)` が legacy path で構築可能
- `SCHEMA_VERSION_HISTORY` の最後 entry が `0.10.0-m7h` であることを property test

### 単体 (cognition helper)
- `_trace_event_boundary` を 7 kind × 優先度衝突ケースで table-driven test
- 空 observations → `(None, None, None)`
- 同 priority に複数 candidate がある場合の tie-break (insertion order)

### 統合 (cognition cycle)
- fixture observations (AffordanceEvent 1 件 + ProximityEvent 1 件混在) → `ReasoningTrace.trigger_kind` が最高優先 (zone_transition 不在なら affordance) になるか assert
- temporal-only quiet tick で trace 発火するか (発火条件緩和の意図確認)

### 統合 (world tick)
- `_fire_proximity_events` を agent_a in PERIPATOS / agent_b in AGORA で発火 → 各 ProximityEvent.zone が initiator 側になっているか assert
- `step_kinematics` 後 zone 境界跨ぎでも `prev_zone` snapshot が effective

### live 受け入れ (G-GEAR)
- 3 ペルソナ走行 → ReasoningPanel TRIGGER 行が tick 進行で更新
- Linden-Allee zone enter で Kant trace の `trigger_kind=zone_transition`, `trigger_zone=peripatos` 表示確認
- screenshot を `observation.md` に添付

## 実装順序 (4 commit、各段で CI green を確認)

1. **schema bump**: `schemas.py` + `SCHEMA_VERSION_HISTORY` + golden regen + `test_schemas.py` の wire-compat
2. **cognition helper**: `_trace_event_boundary` + L730 配線 + helper 単体テスト
3. **world inject**: `_fire_proximity_events` zone 注入 + `prev_zone` snapshot race 対策 + tick テスト
4. **godot UI**: TRIGGER セクション + icon mapping + Strings.gd

## ロールバック計画

各 commit 単位で逆順 revert 可能。

- **schema bump 戻し**: `_FROZEN_VERSION` 戻し + `SCHEMA_VERSION_HISTORY` entry 削除 1 commit
- **Godot 戻し**: `_make_label` 行ごと revert (Strings.gd 追加 dict key も同 commit に含めて atomic 化)
- **検出**: 各 commit 後に CI green を確認、live G-GEAR で envelope 受信に異常 (handshake fail / trace 表示崩壊) があれば即 revert

## リスク (top 5)

1. **ProximityEvent.zone race** — `step_kinematics` 後 `_apply_separation_force` で位置が動く。`prev_zone` snapshot で対処 (L811 流用)
2. **wire 互換** — m7z client が新 fields を reject しないか。Godot は `dict.get` で additive 安全、Python は `extra="forbid"` の影響範囲を `HandshakeMsg` 含めて要確認
3. **Godot null crash** — `trace.get("trigger_zone")` の null 分岐を厳格に
4. **trace 発火条件緩和** — `trigger_kind is not None` を OR 追加で temporal-only quiet tick も trace 発火 → envelope/sec 計測 (live で 1 分 × 3 体)
5. **3 体並走の前回値残存** — `set_focused_agent` リセットで TRIGGER ラベル明示クリア

## /reimagine + Codex review 後の更新方針

- v1 (本ファイル) を `design-v1-archive.md` にコピー
- /reimagine で v2 を再生成 (本 design 不可視で independent generation)
- v1 vs v2 を A1/A2/A3 軸で並列比較 → hybrid 採用案を `design-final.md` に確定
- Codex CLI (`codex review`) で hybrid を independent review、HIGH 指摘を design-final.md に反映
- design-final.md 確定後に tasklist.md を埋めて実装着手

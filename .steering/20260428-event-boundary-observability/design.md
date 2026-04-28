# 設計 — ハイブリッド (v1 ⊗ v2、Codex review 直前)

> **本ファイルは /reimagine 後のハイブリッド採用案。**
> Codex CLI による independent review (gpt-5.5) に投入し、HIGH 指摘を取り込んだ
> 上で `design-final.md` として確定する。実装着手は design-final.md 確定後。

## 採用アプローチ — 「trigger_event tag (nested) + zone pulse (violet) + summary≤60chars」

`ReasoningTrace` に `trigger_event: TriggerEventTag | None` を 1 つだけ additive に
足す。`TriggerEventTag` は次の 3 フィールド構造体:

- `kind: Literal["zone_transition","affordance","proximity","temporal","biorhythm","speech","internal","unknown"]` (8 種、v1 構成踏襲)
- `zone: Zone | None`
- `summary: str` (**≤60 chars**、panel 幅 320px / 13pt の visual budget に整合)

`erre_mode_shift` / `perception` は cognition 側に正規源がないため M10+ で再検討、
本タスクからは除外。

cognition cycle で観察列から 1 個を投票で選ぶ純関数 `_pick_trigger_event()`。
優先順位 = `zone_transition > affordance > biorhythm > proximity > temporal > speech > internal`。

Godot 側は **2 modality 同時提示**:

1. **ReasoningPanel** に「気づきの起点」セクション 1 行追加 (icon + zone + summary)
2. **BoundaryLayer.`pulse_zone(zone)`** で該当 zone rect を 0.6s 間 **violet** に pulse (既存 yellow affordance / cyan proximity と色で区別)

`reasoning_trace_received` 受信時に `trace.trigger_event.zone` 非空なら `EnvelopeRouter` が新 signal `zone_pulse_requested(zone, tick)` を emit、BoundaryLayer が subscribe。

## 採用案の根拠 (v1 ⊗ v2 ハイブリッド)

### v2 から採用した要素

- **nested `TriggerEventTag`**: sparse 3 fields より構造化、Pydantic / GDScript 双方で `dict.get` でフェイル静か
- **`summary: str`**: ref_id 単独より因果が伝わる (live 観察体験を質的に底上げ)
- **2 modality (panel + zone pulse)**: 要件 C2「**境界線**」の空間 metaphor に整合、眼球 1 サッカードで読める
- **ProximityEvent 無変更**: cycle 側で `AgentState.position.zone` から取得、race 対策の `prev_zone` snapshot 不要
- **5 commit 分割**: bisect 性確保 (schema → cycle → fixtures → panel → pulse)
- **既存 BoundaryLayer 資産活用**: 既存 zone 境界線描画を pulse 拡張
- **新 signal `zone_pulse_requested(zone, tick)`**: 2 modality の同期点を envelope router に集約

### v1 から取り込んだ要素

- **schema bump 表記 `0.10.0-m7h`** (M7 系一貫性、v2 の `0.10.0-m9` ではなく)
- **trigger kind 8 種** (v2 の `erre_mode_shift / perception` を除外、cognition 正規源確認まで)
- **summary 上限 60 chars** (v2 の 80 chars から短縮、panel visual budget に整合)
- **pulse 色 violet** (v2 の amber を変更、既存 yellow affordance との色被り回避)

### 両案で共通だった要素 (収束)

- M7ζ `latest_belief_kind` の additive default-None pattern 踏襲
- 優先度ベースで 1 件選択 (順位の細部は若干異なるが大筋一致)
- live G-GEAR 3 体走行で受け入れ確認

## 変更対象 (path:line)

### Schema 層
- `src/erre_sandbox/schemas.py` (line approx 44 / 73-105)
  - `_FROZEN_VERSION` bump: `0.9.0-m7z` → `0.10.0-m7h`
  - `SCHEMA_VERSION_HISTORY` に entry 追記
- `src/erre_sandbox/schemas.py:820` 付近 — `class TriggerEventTag(BaseModel)` を `ReasoningTrace` の直前に新設
  - `kind: Literal[...]` (8 種)
  - `zone: Zone | None = None`
  - `summary: str = Field(default="", max_length=60)`
- `ReasoningTrace` (L820-887) に additive: `trigger_event: TriggerEventTag | None = Field(default=None)`

### Cognition 層
- `src/erre_sandbox/cognition/cycle.py:1062` 付近 — 純関数 `_pick_trigger_event(observations, current_zone) -> TriggerEventTag | None` 新設
  - 優先順位ロジック内包
  - summary 生成 (≤60 chars、トリミング処理)
- `src/erre_sandbox/cognition/cycle.py:711` `_build_envelopes` — `trigger = _pick_trigger_event(observations, new_state.position.zone)` を加え `ReasoningTrace(...)` に渡す
  - 発火条件 (L722-729) に `or trigger is not None` を OR 追加

### World 層
- **無変更** (v2 の選択を採用)。ProximityEvent.zone は追加せず、cognition cycle が AgentState から取得

### Godot 層
- `godot_project/scripts/EnvelopeRouter.gd:91` — 新 signal `zone_pulse_requested(zone: String, tick: int)` を追加し、`reasoning_trace` ハンドラ内で `trace.trigger_event.zone` 非空時に emit
- `godot_project/scripts/ReasoningPanel.gd:178` 付近
  - 「気づきの起点」セクション (`_make_label` + `_trigger_label`) を salient の上に追加
  - kind→icon dict (Strings.gd 経由)
  - `_on_reasoning_trace_received` で `trace.trigger_event` null guard
  - `set_focused_agent` のリセットブロックに TRIGGER ラベルクリア追加
- `godot_project/scripts/BoundaryLayer.gd` — `pulse_zone(zone, color, duration)` 新規
  - `zone_pulse_requested` signal subscribe
  - Tween で zone rect の line_color を violet (例: `Color(0.55, 0.4, 0.85)`) → 既定色へ
- `godot_project/scripts/i18n/Strings.gd` (or 同等)
  - `LABELS["TRIGGER_EVENT"]`, `LABELS["TRIGGER_NONE"]`, `TRIGGER_ICON_*` dict

### テスト層
- `tests/test_schemas.py` — `TriggerEventTag` round-trip + `ReasoningTrace.trigger_event=None` default + `extra="forbid"` + summary max_length=60 violation
- `tests/test_envelope_fixtures.py` — golden `reasoning_trace.json` re-bake 検証
- 新規 `tests/test_cognition_trigger_pick.py` — 8 obs 種類 × 優先順位行列で `_pick_trigger_event` 純関数テスト (zone_transition と affordance 同居 → zone_transition 勝ち、空 obs → None、summary trimming など 8+ ケース)
- `tests/test_envelope_kind_sync.py` — 既存 (kind 増えないので pass のはず確認)
- `tests/test_godot_project.py` 系 — Godot smoke (ReasoningPanel.gd / BoundaryLayer.gd の `class_name` / signal 名 parse)

## 既存資産の活用

- `_decision_with_affinity` (cognition/cycle.py:1102) パターン — 純関数で string 装飾、`_pick_trigger_event` で踏襲
- `AgentState.position.zone` (既に agent_update に carry、panel 未参照) — cognition 側で current_zone 取得に流用
- `BoundaryLayer._draw_circle` / `_make_unshaded_material` — zone rect の violet pulse に転用
- `Strings.gd` の `BELIEF_ICON_*` パターン — TRIGGER_ICON_* に同形コピー
- `ZoneLayout` / `PropLayout` (schemas.py:1103) — nested model 追加の前例

## 影響範囲

- **Wire**: 1 nested type 追加 + 1 optional field 追加。HandshakeMsg 厳密 version match のため SCHEMA_VERSION 必須 bump
- **Producers**: cognition/cycle.py のみ。world/tick.py / gateway.py 無変更
- **Consumers**: ReasoningPanel + BoundaryLayer + EnvelopeRouter + Strings。WorldManager / AgentController は無関係
- **LLM prompt**: スコープ外 (要件明示)
- **Panel 高さ**: TRIGGER 行 1 つ追加で +20-30px。Viewport (PR #116 HSplit) 内 scroll は live で確認
- **Trace 発火頻度**: `trigger_kind is not None` OR 追加で temporal-only quiet tick も発火、envelope/sec を live 1 分 × 3 体で計測

## 既存パターンとの整合性

- **Additive default=None**: M7ζ `persona_id` / `latest_belief_kind` と同形
- **Nested model 追加**: `ZoneLayout` / `PropLayout` の前例
- **Icon dict**: ReasoningPanel `belief_icon` と同形
- **Pulse 演出**: 既存 BoundaryLayer の static 描画から動的 Tween への 1 ステップ拡張、新ファイル 0
- **Strings.gd LABELS dict**: 既存 BELIEF_ICON_* / RELATIONSHIP_LABEL 群と同居

## テスト戦略

### 単体 (schema)
- `TriggerEventTag` の round-trip serialize/deserialize
- `ReasoningTrace.trigger_event` default=None
- `summary` max_length=60 violation で `ValidationError`
- m7z 形式 dict が `trigger_event=None` で deserialize される (wire-compat)
- m7h 形式 dict が `extra="forbid"` を violate しない
- `SCHEMA_VERSION_HISTORY` 末尾 entry が `0.10.0-m7h` であることを property test

### 単体 (cognition helper)
- `_pick_trigger_event` を 8 kind × 優先順位衝突ケースで table-driven (zone_transition 勝ち、affordance vs proximity、temporal のみ、空 → None など 8+ ケース)
- summary trimming 境界 (60 chars 超過、Unicode 多 byte 文字)
- 同 priority 複数 candidate の tie-break (insertion order)

### 統合 (cognition cycle)
- fixture observations (AffordanceEvent + ProximityEvent 混在) → `ReasoningTrace.trigger_event.kind` 期待値
- temporal-only quiet tick で trace 発火 (発火条件緩和の意図確認)

### 統合 (Godot smoke)
- ReasoningPanel.gd / BoundaryLayer.gd / EnvelopeRouter.gd の `class_name` / signal 名 parse
- `zone_pulse_requested` signal が EnvelopeRouter で定義され、BoundaryLayer で接続

### live 受け入れ (G-GEAR)
- 3 ペルソナ走行 (Kant / Rikyu / Dogen) → ReasoningPanel TRIGGER 行が tick 進行で更新
- Linden-Allee zone enter で Kant trace の `trigger_event.kind=zone_transition`, `trigger_event.zone=peripatos`, `summary` に zone 名表示確認
- BoundaryLayer の violet pulse が該当 zone で 0.6s 発火、yellow affordance / cyan proximity と区別可能
- screenshot を `observation.md` に添付

## 実装順序 (5 commit、各段で CI green を確認)

1. **schema bump**: `schemas.py` (`TriggerEventTag` + `ReasoningTrace.trigger_event`) + `SCHEMA_VERSION_HISTORY` + `test_schemas.py`
2. **cognition helper**: `_pick_trigger_event` + `_build_envelopes` 配線 + `test_cognition_trigger_pick.py`
3. **fixtures**: golden `reasoning_trace.json` re-bake + `test_envelope_fixtures.py` green
4. **godot panel**: `Strings.gd` + `EnvelopeRouter.gd` signal 追加 + `ReasoningPanel.gd` TRIGGER 行
5. **godot pulse**: `BoundaryLayer.pulse_zone` + signal connect

## ロールバック計画

- Wire は additive のため `trigger_event=None` で送出すれば panel は dash 表示でフェイル静か
- BoundaryLayer.pulse_zone がエラーした場合 panel 表示は無傷 (signal disconnect で arm)
- 完全戻し: schemas の `TriggerEventTag` + `trigger_event` 削除 + cycle.py helper 削除 + Godot 追加コード削除
- `SCHEMA_VERSION` を `0.9.0-m7z` に戻すだけで wire 互換は復帰
- 5 commit 分割で逆順 revert 可能

## リスク (top 5)

1. **trigger 優先順位の妥当性が live で「何で zone_transition が affordance より上?」と user 質問** — 根拠 (因果連鎖の上流性) を decisions.md に明記
2. **Violet pulse が既存 BoundaryLayer の other color (yellow affordance / cyan proximity / 既定 zone 境界) と区別可能か** — 色座標を pre-implement で目視確認、悪ければ高彩度 magenta に切替
3. **同 tick 内に 2 つ以上の strong event (zone_transition + biorhythm 同時) があると trigger が 1 つに丸まり情報損失** — `summary` を `"linden-allee 進入; 鼓動↑"` のように compound 表示する小細工で対処、要件は 1 行なので妥協可
4. **fixture re-bake で test_contract_snapshot 系が連動 fail** — golden 更新を commit 3 で集約しテストグリーンを担保
5. **新 signal `zone_pulse_requested` を `EnvelopeRouter` に足す際 `tests/test_envelope_kind_sync.py` の正規表現が signal を kind と誤検出しないか** — kind 抽出 regex は `match` ブロック内のみ走査するため安全 (確認済み: EnvelopeRouter.gd:33 の match 構文)

## 設計判断の履歴

- **2026-04-28**: 初回案 (`design-v1.md`) と再生成案 (`/reimagine` v2) を比較 → ハイブリッド採用
- **採用**: ハイブリッド (v2 ベース + v1 race 対策議論 + schema bump 表記 + summary 上限 + pulse 色)
- **根拠**:
  1. 2 modality (panel + zone pulse) は要件 C2「境界線」の空間 metaphor に整合、live 観察体験を質的に底上げ
  2. `summary` 文字列で因果が text 化され、ref_id 単独より読める (M9 LoRA pre-plan 「推奨第 1 候補」の研究 observatory 価値に直結)
  3. ProximityEvent 無変更で `prev_zone` snapshot race 対策が不要、実装健全性で勝る
  4. 侵襲度差 +40 LoC は godot-viewport-layout (PR #115/#116) で +200 LoC merge 実績ありで受容可
- **比較表全文**: `design-comparison.md` 参照
- **次工程**: Codex CLI (`codex review`) で本ハイブリッドを independent review、HIGH 指摘を `design-final.md` に反映、その後 tasklist.md を埋めて実装着手

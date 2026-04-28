# 設計 — FINAL (Codex review 反映後)

> **本ファイルは Codex independent review (gpt-5.5) の VERDICT: BLOCK + 5 HIGH + 4 MEDIUM + 1 LOW を全て反映した最終確定版。** 実装はこのファイルに従う。
> 履歴: `design-v1.md` (初回) → `/reimagine` → ハイブリッド (`design.md` の現状) → 本 final。

## Codex review 反映サマリ

| # | Severity | 指摘 | 反映 |
|---|---|---|---|
| 1 | HIGH | `_FROZEN_VERSION` / `SCHEMA_VERSION_HISTORY` は実コードに存在しない (Claude hallucination)。実体は `SCHEMA_VERSION` 一箇所 + 複数 test の hardcoded "0.9.0-m7z" + Godot `CLIENT_SCHEMA_VERSION` | schema commit を atomic 化: Python `SCHEMA_VERSION` + Godot `CLIENT_SCHEMA_VERSION` + 3 test files + golden JSON の同時更新 |
| 2 | HIGH | nested model は `extra="forbid"` 既定で適用されない、`__all__` 漏れも要注意 | `TriggerEventTag` に `model_config = ConfigDict(extra="forbid")` 明示、`__all__` に追加、unknown nested key の rejection test 追加 |
| 3 | HIGH | 5 commit "各段 CI green" が成立しない (golden / fixtures が schema bump で即 fail) | **4 commit に再編、commit 1 で wire 契約全体を atomic 更新** |
| 4 | HIGH | `zone_pulse_requested(zone, tick)` に agent_id 不在 → 3 体 live で focus 外 trace でも world pulse | signal を `zone_pulse_requested(agent_id, kind, zone, tick)` に拡張、BoundaryLayer は ReasoningPanel の `_focused_agent` と一致時のみ pulse |
| 5 | HIGH | BoundaryLayer の `_material` は全 zone 共有、tween で全 zone 再色塗り発生 | per-zone state map + per-zone material instance に再構成、active tween は zone ごと kill/replace |
| 6 | MEDIUM | `summary: str` 自由テキストは backend↔UI 結合過剰、i18n もブロック | `summary` を schema から削除、`ref_id: str | None` を保持。表示は Godot Strings.gd で `(kind, zone, ref_id)` から localized text 生成 |
| 7 | MEDIUM | 非空間 kind (temporal/biorhythm/internal/speech/perception/erre_mode_shift) も pulse 発火する可能性 | EnvelopeRouter で **kind ∈ {zone_transition, affordance, proximity} のみ** pulse emit |
| 8 | MEDIUM | 同 tick 複数 strong event の wire 上の defined behavior 不在 | strict single-winner + `secondary_kinds: list[Literal[...]] = []` を additive 追加して "+N more" UI hint |
| 9 | MEDIUM | `max_length=60` は Unicode visual width を保証しない | summary 削除で moot (kind+ref_id+zone から Godot が visual budget 内整形、overrun は ellipsis) |
| 10 | LOW | `unknown` には producer なし、`erre_mode_shift` は cycle.py:607 で実際 emit 中 | kind 列を **9 種** に確定 (実 Observation union と一致): zone_transition / affordance / proximity / temporal / biorhythm / erre_mode_shift / internal / speech / perception |

## 採用アプローチ (Final)

`ReasoningTrace` に `trigger_event: TriggerEventTag | None` を additive 追加。`TriggerEventTag` は次の構造体:

- `kind: Literal["zone_transition","affordance","proximity","temporal","biorhythm","erre_mode_shift","internal","speech","perception"]` (9 種、実 Observation union と一致)
- `zone: Zone | None`
- `ref_id: str | None` (zone_transition→`to_zone`、affordance→`prop_id`、proximity→`other_agent_id`、その他→`None`)
- `secondary_kinds: list[Literal[...]] = []` (同 tick で勝てなかった strong event の "+N more" hint)

**summary は schema に持たない。** Godot 側 Strings.gd で `(kind, zone, ref_id)` tuple から localized 1 行表示を組み立てる (例: `→ peripatos に入った` / `◇ chashitsu の bowl_01` / `◯ rikyu と接近`)。これにより backend ↔ UI 結合を切る。

cognition cycle で観察列から 1 件を投票: 優先順位 = `zone_transition > affordance > proximity > biorhythm > erre_mode_shift > temporal > internal > speech > perception` (空間性高 → 抽象度高)。空 obs → `None`。

Godot 側 2 modality (Codex HIGH 4/5 反映):

1. **ReasoningPanel** に「気づきの起点」セクション 1 行 (icon + zone + Strings.gd で組み立てた text)
2. **BoundaryLayer.`pulse_zone(zone, kind)`** で zone rect を 0.6s 間 violet pulse、**ただし spatial kind のみ** (zone_transition / affordance / proximity)、かつ **focused agent 起点のみ**

`reasoning_trace_received` 受信時に EnvelopeRouter が `trace.trigger_event` を unpack し、新 signal `zone_pulse_requested(agent_id, kind, zone, tick)` を emit。BoundaryLayer は焦点 agent (SelectionManager の `selected_agent_id` と一致) かつ kind が spatial の時のみ pulse。

## 変更対象 (path:line)

### Schema 層 (`src/erre_sandbox/schemas.py`)
- L44: `SCHEMA_VERSION` bump `"0.9.0-m7z"` → `"0.10.0-m7h"`
- L820 直前: 新 `class TriggerEventTag(BaseModel)`:
  - `kind: Literal[...9 種...]`
  - `zone: Zone | None = None`
  - `ref_id: str | None = Field(default=None, max_length=64)`
  - `secondary_kinds: list[Literal[...9 種...]] = Field(default_factory=list, max_length=8)`
  - `model_config = ConfigDict(extra="forbid")` 明示
- L820 `class ReasoningTrace`: `trigger_event: TriggerEventTag | None = Field(default=None, description="...")`
- L1368 `__all__`: `"TriggerEventTag"` 追記
- 既存 docstring (L73-129 付近の version notes) に M9-A entry 追記 (M7 系の最後の minor として 0.10.0-m7h 採番、M9 名前空間衝突を避ける)

### Godot version-pinned (`godot_project/scripts/WebSocketClient.gd:28`)
- `const CLIENT_SCHEMA_VERSION: String = "0.9.0-m7z"` → `"0.10.0-m7h"`
- HandshakeMsg 厳密 match のため schema commit と同期必須

### Test 層 (commit 1 atomic)
- `tests/test_schemas.py:381` `assert SCHEMA_VERSION == "0.9.0-m7z"` → `"0.10.0-m7h"`
- `tests/test_schemas_m6.py:47` 同上
- `tests/test_schemas_m7g.py:55,57` (docstring + assert) 同上
- `tests/schema_golden/control_envelope.schema.json` 内 `"0.9.0-m7z"` 全置換 (10+ 箇所、自動 regen)
- 新規 test cases:
  - `TriggerEventTag` round-trip serialize/deserialize
  - `ReasoningTrace.trigger_event=None` default
  - `TriggerEventTag` に unknown nested key を渡すと `ValidationError` (extra=forbid)
  - `ref_id` max_length=64 violation で `ValidationError`
  - `secondary_kinds` max_length=8 violation で `ValidationError`
  - m7z 形式 (古い) ReasoningTrace dict が `trigger_event=None` で deserialize される
  - `__all__` に `TriggerEventTag` が含まれる

### Cognition 層 (commit 2)
- `src/erre_sandbox/cognition/cycle.py` 新純関数:
  ```python
  def _pick_trigger_event(
      observations: Sequence[Observation],
      current_zone: Zone,
  ) -> TriggerEventTag | None:
      """Priority: zone_transition > affordance(salience desc) > proximity(enter) >
      biorhythm > erre_mode_shift > temporal > internal > speech > perception.
      ref_id mapping per kind. secondary_kinds = strong losers (top 8)."""
  ```
- `_build_envelopes` (L711) で呼び出し、`ReasoningTrace(...)` に `trigger_event=trigger` を渡す
- 発火条件 (L722-729 周辺) に `or trigger is not None` を OR 追加
- 新規 `tests/test_cognition_trigger_pick.py`: 9 kind × 優先衝突で 10+ ケース

### Godot Panel 層 (commit 3)
- `godot_project/scripts/i18n/Strings.gd`:
  - `LABELS["TRIGGER"] = "気づきの起点"`
  - `LABELS["TRIGGER_NONE"] = "—"`
  - `TRIGGER_ICON = {"zone_transition": "→", "affordance": "◇", "proximity": "◯", "temporal": "◔", "biorhythm": "♥", "erre_mode_shift": "✦", "internal": "✎", "speech": "💬", "perception": "👁"}`
  - 新関数 `format_trigger(kind: String, zone: String, ref_id: String) -> String`
- `godot_project/scripts/EnvelopeRouter.gd`:
  - 新 signal `zone_pulse_requested(agent_id: String, kind: String, zone: String, tick: int)`
  - L91 `reasoning_trace` ハンドラ内で `trace.trigger_event` を unpack、kind が spatial set に含まれかつ zone 非空なら emit
- `godot_project/scripts/ReasoningPanel.gd`:
  - L178 付近に「気づきの起点」セクション (`_make_label` + `_trigger_label`)
  - `_on_reasoning_trace_received` で `trace.get("trigger_event")` の null guard
  - `set_focused_agent` リセットブロックに TRIGGER ラベルクリア
  - `Strings.format_trigger()` で表示文字列を生成

### Godot Pulse 層 (commit 4)
- `godot_project/scripts/BoundaryLayer.gd` 大改修:
  - `_zone_materials: Dictionary` (zone_id → StandardMaterial3D) で per-zone material 管理 (現状 `_material` 単一を分離)
  - `_active_tweens: Dictionary` (zone_id → Tween) で per-zone tween 追跡、再 trigger で kill/replace
  - 新 method `pulse_zone(zone: String, kind: String, duration: float = 0.6) -> void`
    - 既存 tween があれば `kill()`
    - violet `Color(0.55, 0.4, 0.85)` ↔ default `line_color` を `Tween` で 0.6s
  - `_ready` で `EnvelopeRouter.zone_pulse_requested` を connect、focus filter:
    ```gdscript
    func _on_zone_pulse(agent_id: String, kind: String, zone: String, tick: int) -> void:
        if agent_id != SelectionManager.selected_agent_id:
            return
        if kind not in ["zone_transition", "affordance", "proximity"]:
            return
        pulse_zone(zone, kind)
    ```

## 既存資産の活用

- `_decision_with_affinity` (cognition/cycle.py:1102) パターン → `_pick_trigger_event` で踏襲 (純関数で構造体生成)
- `AgentState.position.zone` (agent_update に carry 済) → `current_zone` 引数として cycle.py で取得
- `BoundaryLayer._make_unshaded_material` (L116) → per-zone material 量産に転用
- M7ζ `latest_belief_kind` (L541) の "additive default-None on existing model" → trigger_event additive で踏襲
- `ZoneLayout` / `PropLayout` (L1103) nested model → `TriggerEventTag` の前例
- `Strings.gd` 既存 LABELS dict + key lookup → TRIGGER 関連 label の置き場所
- `SelectionManager.selected_agent_id` → focus filter の単一情報源

## 影響範囲

- **Wire**: 1 nested type 追加 + 1 optional field 追加 + Godot client version bump
  - HandshakeMsg 厳密 match のため schema commit が atomic でないと live reconnect 失敗
  - additive のため client が新型未対応でも `extra=forbid` violate なし (ReasoningTrace は既存)
- **Producers**: cognition/cycle.py のみ。world/tick.py / gateway.py 無変更
- **Consumers**: ReasoningPanel + BoundaryLayer + EnvelopeRouter + Strings + WebSocketClient (version 定数のみ)
- **LLM prompt**: スコープ外 (要件明示)
- **Trace 発火頻度**: `or trigger is not None` の OR 追加で temporal-only quiet tick も発火、live G-GEAR 1 分 × 3 体で envelope/sec 計測
- **Tween overhead**: 3 体並走、focus 1 体のみ pulse 対象なので最大 1 active tween/tick、軽量

## 既存パターンとの整合性

- **Additive default=None**: M7ζ `persona_id` / `latest_belief_kind` と同形
- **Nested model + extra=forbid**: 全 public model の既定方針 (Codex HIGH 2 で明示確認)
- **Focus-gated UI**: SelectionManager.selected_agent_id で panel と pulse を一元化
- **Strings.gd 経由 i18n**: backend ↔ UI 文字列結合を排除する established pattern (M7δ から踏襲)

## テスト戦略

### 単体 (schema, commit 1)
- `TriggerEventTag` round-trip
- `ReasoningTrace.trigger_event` default=None
- `TriggerEventTag(extra={...})` で `ValidationError`
- `ref_id` max_length=64 / `secondary_kinds` max_length=8 違反で `ValidationError`
- m7z (古い) ReasoningTrace payload が m7h schema で `trigger_event=None` で deserialize
- `__all__` に `TriggerEventTag` が export
- `SCHEMA_VERSION == "0.10.0-m7h"` の assert 全 3 test files (test_schemas.py / test_schemas_m6.py / test_schemas_m7g.py)

### 単体 (cognition helper, commit 2)
- 9 kind × 優先衝突 table-driven (10+ ケース、空 obs → None、tie-break = insertion order)
- `secondary_kinds` が strong losers のみ含むこと (kind が spatial set かつ winner と異なる)
- ref_id mapping (zone_transition→to_zone / affordance→prop_id / proximity→other_agent_id / その他→None)

### 統合 (cognition cycle, commit 2)
- fixture observations (Affordance + Proximity 混在) → `trigger_event.kind=affordance`、`secondary_kinds=["proximity"]`
- temporal-only quiet tick で trace 発火 (発火条件緩和)
- biorhythm 単独 → `trigger_event.kind=biorhythm`, `zone=None` (非空間)

### Godot smoke (commit 3 / 4)
- ReasoningPanel.gd / BoundaryLayer.gd / EnvelopeRouter.gd の `class_name` / signal 名 parse
- `zone_pulse_requested` signal が EnvelopeRouter で 4-arg 定義されていること
- Strings.format_trigger() の 9 kind × zone 有無の出力 fixture

### live 受け入れ (G-GEAR)
- 3 ペルソナ走行 (Kant / Rikyu / Dogen) → ReasoningPanel TRIGGER 行が tick 進行で更新
- Linden-Allee zone enter で Kant trace の `trigger_event.kind=zone_transition`, `zone=peripatos`, `ref_id="peripatos"` 表示確認
- BoundaryLayer の violet pulse が **focused agent (Kant 選択時のみ)** で peripatos zone に 0.6s 発火、yellow affordance / cyan proximity と区別可能
- Rikyu/Dogen 選択切替で pulse 対象も切り替わること (HIGH 4 検証)
- temporal/biorhythm のみの tick で pulse が**起こらない**こと (MEDIUM 7 検証)
- screenshot を `observation.md` に添付

## 実装順序 (4 commit)

### commit 1: schema + version + test + golden + Godot client (atomic wire 契約)
- `src/erre_sandbox/schemas.py`: `TriggerEventTag` + `ReasoningTrace.trigger_event` + `SCHEMA_VERSION` bump + `__all__`
- `godot_project/scripts/WebSocketClient.gd:28`: `CLIENT_SCHEMA_VERSION` bump
- `tests/test_schemas.py` / `tests/test_schemas_m6.py` / `tests/test_schemas_m7g.py`: version assert update + 新 test cases (round-trip / extra=forbid / max_length / wire-compat)
- `tests/schema_golden/control_envelope.schema.json`: regen
- **CI green を此処で確保**

### commit 2: cognition helper + 配線 + 単体/統合 test
- `src/erre_sandbox/cognition/cycle.py`: `_pick_trigger_event` + `_build_envelopes` 配線
- `tests/test_cognition_trigger_pick.py`: 新規、9 kind table-driven
- 既存 `tests/test_cognition_cycle.py` (or 同等) に統合 test 追加

### commit 3: Godot panel
- `godot_project/scripts/i18n/Strings.gd`: TRIGGER labels + icon dict + `format_trigger()`
- `godot_project/scripts/EnvelopeRouter.gd`: `zone_pulse_requested(agent_id, kind, zone, tick)` 追加 + reasoning_trace ハンドラ拡張
- `godot_project/scripts/ReasoningPanel.gd`: TRIGGER 行 + null guard + focus reset

### commit 4: Godot pulse (BoundaryLayer 大改修)
- `godot_project/scripts/BoundaryLayer.gd`: per-zone material map + per-zone tween 管理 + `pulse_zone()` + signal connect with focus filter

## ロールバック計画

- Wire は additive のため `trigger_event=None` 送出で panel は dash 表示でフェイル静か
- BoundaryLayer.pulse_zone がエラーした場合 panel 表示は無傷 (signal disconnect で arm)
- 完全戻し: 4 commit 逆順で revert
  - commit 1 戻しは schema + version + test + golden + Godot client が atomic に戻る (handshake 互換維持)
  - commit 2 戻しは cycle.py のみ
  - commit 3/4 戻しは Godot 側のみ

## リスク (Codex review 後 top 5)

1. **Per-zone material 量産で BoundaryLayer 描画コストが微増** — zone 数 5 (study/peripatos/chashitsu/agora/garden) 程度なので無視可、但し draw call 計測を live で確認
2. **Tween 同時発火 (zone 切替速度速い時)** — `_active_tweens[zone].kill()` で per-zone 排他化、test で connection burst を fuzz
3. **focused agent 切替時の pulse 抜け** — `SelectionManager.selected_agent_id` 変更時に走行中 tween をクリア、新 agent の最後 trigger を再 pulse する仕様にすべきか要件確認 (現方針: 切替後の新 trace から有効、過去 trace は再 pulse しない)
4. **wire-compat test の golden diff レビュー負荷** — 10+ "0.9.0-m7z" 置換 + TriggerEventTag schema 追加で diff が大きい、commit 1 review に時間配分
5. **`ref_id` の semantic (zone_transition→to_zone vs from_zone)** — `to_zone` を採用 (因果 = "どこに入った"), decisions.md に明記

## 設計判断の履歴

- **2026-04-28 (1)**: 初回案 `design-v1.md` 作成
- **2026-04-28 (2)**: `/reimagine` で v2 生成 → ハイブリッド採用 (`design-comparison.md` 参照)
- **2026-04-28 (3)**: Codex independent review (gpt-5.5, run 2026-04-28T16Z) で **VERDICT: BLOCK** + 5 HIGH + 4 MEDIUM + 1 LOW を受領
- **2026-04-28 (4)**: 全 10 finding を反映し本 `design-final.md` を確定
  - HIGH 1: 実コード `SCHEMA_VERSION` / Godot `CLIENT_SCHEMA_VERSION` / hardcoded test を atomic 化
  - HIGH 2: `model_config = ConfigDict(extra="forbid")` 明示 + `__all__` 追加
  - HIGH 3: 5 commit → 4 commit に再編、commit 1 で wire 契約全体 atomic
  - HIGH 4: signal を `(agent_id, kind, zone, tick)` 4-arg 化、focus filter
  - HIGH 5: BoundaryLayer per-zone material + per-zone tween 管理に再構成
  - MEDIUM 6: `summary` 削除、Godot Strings.gd で生成
  - MEDIUM 7: spatial kind のみ pulse
  - MEDIUM 8: `secondary_kinds: list[Literal[...]]` additive
  - MEDIUM 9: summary 削除で moot
  - LOW 10: kind 列を実 Observation union と一致 (9 種、`unknown` 削除、`erre_mode_shift` 含める)
- **次工程**: tasklist.md 確定 → 実装 4 commit → live G-GEAR 受け入れ → PR

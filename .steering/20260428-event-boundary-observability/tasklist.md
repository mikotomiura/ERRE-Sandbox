# タスクリスト

## 準備 (完了)
- [x] requirement.md 確認
- [x] file-finder / Explore で影響範囲調査 (schemas / cognition / world / godot)
- [x] design.md v1 を承認 plan から書き出し
- [x] /reimagine で v2 生成、design-comparison.md 比較、ハイブリッド採用
- [x] Codex independent review (gpt-5.5) で VERDICT: BLOCK + 5 HIGH + 4 MEDIUM + 1 LOW
- [x] design-final.md 確定 (全 10 finding 反映)
- [x] feat/event-boundary-observability ブランチ作成 (main 起点 clean)

## 実装

### commit 1: schema + version + test + golden + Godot client (atomic wire 契約)
- [ ] `src/erre_sandbox/schemas.py:44`: `SCHEMA_VERSION` bump `"0.9.0-m7z"` → `"0.10.0-m7h"`
- [ ] `src/erre_sandbox/schemas.py:820` 直前: `class TriggerEventTag(BaseModel)` 追加
  - kind: 9 種 Literal、zone: Zone | None、ref_id: str | None (max 64)、secondary_kinds: list[...] (max 8)
  - `model_config = ConfigDict(extra="forbid")` 明示
- [ ] `src/erre_sandbox/schemas.py:820` `class ReasoningTrace`: `trigger_event: TriggerEventTag | None = Field(default=None, ...)`
- [ ] `src/erre_sandbox/schemas.py:1368` `__all__` に `"TriggerEventTag"` 追記
- [ ] schemas.py docstring (L73-129 周辺) に M9-A entry 追記 (`0.10.0-m7h` の意味)
- [ ] `godot_project/scripts/WebSocketClient.gd:28`: `CLIENT_SCHEMA_VERSION` bump
- [ ] `tests/test_schemas.py:381`: version assert update + 新 test cases (round-trip / extra=forbid / max_length / wire-compat / __all__ check)
- [ ] `tests/test_schemas_m6.py:47`: version assert update
- [ ] `tests/test_schemas_m7g.py:55,57`: docstring + version assert update
- [ ] `tests/schema_golden/control_envelope.schema.json`: regen (10+ "0.9.0-m7z" 置換 + TriggerEventTag schema 追加)
- [ ] `uv run ruff check src tests && uv run ruff format --check src tests` green
- [ ] `uv run mypy src` green
- [ ] `uv run pytest tests/test_schemas.py tests/test_schemas_m6.py tests/test_schemas_m7g.py -q` green
- [ ] commit & push

### commit 2: cognition helper + 配線 + 単体/統合 test
- [ ] `src/erre_sandbox/cognition/cycle.py`: `_pick_trigger_event(observations, current_zone) -> TriggerEventTag | None` 純関数追加
  - 優先順位: zone_transition > affordance > proximity > biorhythm > erre_mode_shift > temporal > internal > speech > perception
  - ref_id mapping: zone_transition→to_zone / affordance→prop_id / proximity→other_agent_id / その他→None
  - secondary_kinds: 同 tick の strong losers (top 8)
- [ ] `_build_envelopes` (L711) で `_pick_trigger_event` 呼び出し、`ReasoningTrace(trigger_event=...)` に渡す
- [ ] 発火条件 (L722-729 周辺) に `or trigger is not None` を OR 追加
- [ ] `tests/test_cognition_trigger_pick.py` 新規: 9 kind × 優先衝突 + tie-break + ref_id mapping + secondary_kinds 10+ ケース
- [ ] 既存 `tests/test_cognition_cycle.py` (or 同等) に統合 test 追加 (Affordance + Proximity 混在 / temporal-only quiet tick / biorhythm 単独)
- [ ] CI 全 green
- [ ] commit & push

### commit 3: Godot panel + EnvelopeRouter signal
- [ ] `godot_project/scripts/i18n/Strings.gd`:
  - `LABELS["TRIGGER"]` = "気づきの起点"
  - `LABELS["TRIGGER_NONE"]` = "—"
  - `TRIGGER_ICON` dict (9 kind → glyph)
  - `format_trigger(kind, zone, ref_id) -> String` 関数
- [ ] `godot_project/scripts/EnvelopeRouter.gd`:
  - 新 signal `zone_pulse_requested(agent_id: String, kind: String, zone: String, tick: int)` 追加
  - L91 `reasoning_trace` ハンドラ内で `trace.trigger_event` を unpack、kind ∈ spatial set かつ zone 非空なら emit
  - `tests/test_envelope_kind_sync.py` の regex が match block 外を見ないこと確認
- [ ] `godot_project/scripts/ReasoningPanel.gd`:
  - L178 付近に「気づきの起点」セクション (`_make_label` + `_trigger_label`)
  - `_on_reasoning_trace_received` で `trace.get("trigger_event")` null guard
  - `set_focused_agent` リセットブロックに TRIGGER ラベルクリア
  - `Strings.format_trigger()` 経由で表示
- [ ] CI 全 green (Godot smoke 含む)
- [ ] commit & push

### commit 4: Godot pulse (BoundaryLayer per-zone refactor)
- [ ] `godot_project/scripts/BoundaryLayer.gd` 大改修:
  - `_zone_materials: Dictionary` (zone_id → StandardMaterial3D) で per-zone material 管理
  - `_active_tweens: Dictionary` (zone_id → Tween) で per-zone tween 追跡
  - `pulse_zone(zone, kind, duration=0.6)` 新 method (既存 tween kill→新 Tween)
  - `_ready` で `EnvelopeRouter.zone_pulse_requested` connect
  - focus filter: `SelectionManager.selected_agent_id` と一致時のみ pulse
  - kind filter: `["zone_transition", "affordance", "proximity"]` のみ pulse
  - violet `Color(0.55, 0.4, 0.85)` ↔ default `line_color` の Tween
- [ ] CI 全 green
- [ ] commit & push

## レビュー
- [ ] code-reviewer サブエージェントで commit 1-4 を review
- [ ] HIGH 指摘への対応

## live G-GEAR 受け入れ
- [ ] 3 ペルソナ走行 (Kant / Rikyu / Dogen)
- [ ] ReasoningPanel TRIGGER 行が tick 進行で更新されることを確認
- [ ] Linden-Allee zone enter で Kant trace の `trigger_event.kind=zone_transition`, `zone=peripatos`, `ref_id="peripatos"` 表示確認
- [ ] focused agent (Kant) で peripatos zone に violet pulse 0.6s 確認
- [ ] focus 切替 (Kant→Rikyu) で pulse 対象が切り替わること確認
- [ ] temporal/biorhythm のみの tick で pulse が**起こらない**こと確認 (MEDIUM 7 検証)
- [ ] envelope/sec を 1 分計測、ζ-3 baseline 比較
- [ ] screenshot を `observation.md` に添付

## ドキュメント
- [ ] `docs/architecture.md` の trace flow 図に trigger_event 言及 (必要なら)
- [ ] `docs/glossary.md` に "trigger event tag" 用語追加 (必要なら)
- [ ] `decisions.md` に最終判断ログ (Codex review 反映) を保存

## 完了処理
- [ ] design-final.md / decisions.md / observation.md を最終化
- [ ] PR 作成 (gh pr create、`feat/event-boundary-observability` → `main`)
- [ ] PR description に Codex review verdict + reflection を含める
- [ ] CI green merge

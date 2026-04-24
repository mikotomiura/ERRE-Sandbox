# Tasklist — M7 First PR

> 各項目は 30 分以内で完了できる粒度。
> チェックは完了ごとに更新。

## Setup

- [ ] 既存 M6 carryover (3/3) のステータス確認と、V 完了後に close 宣言
- [ ] feature branch `feat/m7-priority3-differentiation-xai` を main から切る

## V — reflection Japanese (0.5h)

- [ ] `src/erre_sandbox/integration/dialog_turn.py:100-118` の `_DIALOG_LANG_HINT` パターンを精読
- [ ] `src/erre_sandbox/cognition/reflection.py:129-135` system prompt 末尾に 1 行 inject
- [ ] `tests/test_cognition/test_reflection.py` に `test_reflection_system_prompt_includes_japanese_hint` 追加
- [ ] `uv run pytest tests/test_cognition/test_reflection.py` 緑
- [ ] commit: `feat(cognition): force Japanese for reflection system prompt (V)`

## A1 — personality inject (2h)

- [ ] `src/erre_sandbox/schemas.py` の PersonaSpec / personality 定義確認（Big Five フィールド名確定）
- [ ] `src/erre_sandbox/cognition/prompting.py:65-76` `_format_persona_block` に 2 行追加（Big Five / Wabi・Ma_sense）
- [ ] `tests/test_cognition/test_prompting.py` に `test_persona_block_includes_personality` 追加
- [ ] `uv run pytest tests/test_cognition/test_prompting.py` 緑
- [ ] commit: `feat(cognition): inject personality fields into persona prompt block (A1)`

## B1 — _fire_affordance_events (2h)

- [ ] `src/erre_sandbox/world/tick.py:520-559` `_fire_proximity_events` を精読（テンプレ確認）
- [ ] `src/erre_sandbox/schemas.py` の `AffordanceEvent` 定義確認（field 名を揃える）
- [ ] `src/erre_sandbox/world/zones.py` に `ZONE_PROP_COORDS` 定数を追加（chashitsu 2 点）
- [ ] `src/erre_sandbox/world/tick.py` に `_fire_affordance_events()` を実装
- [ ] `_fire_proximity_events` を呼んでいる tick main loop に `_fire_affordance_events` も追加
- [ ] `tests/test_world/test_tick.py` に 2 ケース追加（2m 以内発火 / 外は非発火）
- [ ] `uv run pytest tests/test_world/test_tick.py` 緑
- [ ] commit: `feat(world): fire AffordanceEvent for zone props (B1)`

## B2 — BoundaryLayer overlay (3h)

- [ ] `godot_project/scripts/BoundaryLayer.gd` の現状 zone rect 描画コードを精読
- [ ] `_draw_circle(cx, cz, r)` ヘルパー関数を実装（ImmediateMesh で円軌道）
- [ ] `_draw_affordance_circles()` 実装（ImmediateMesh、yellow 0.9,0.7,0.2）
- [ ] `_draw_proximity_circles()` 実装（ImmediateMesh、cyan 0.3,0.7,0.9）
- [ ] prop 座標は hardcode（schemas/WebSocket 経由は Slice β で配線）
- [ ] Godot で scene 起動し目視で円が描画されていることを確認（可能なら）
- [ ] commit: `feat(godot): add affordance/proximity overlay to BoundaryLayer (B2)`

## α-cam1 — Camera 真俯瞰 hotkey (0.5h)

- [ ] `godot_project/scripts/CameraRig.gd` の現状モード切替を精読
- [ ] ホットキー `0` (Key.KEY_0) で pitch=-1.57 (真俯瞰)、altitude 固定 40m のプリセット
- [ ] `_unhandled_input` に `cam_top_down` action を追加
- [ ] MainScene の help text に記載
- [ ] commit: `feat(godot): add top-down camera preset on hotkey 0 (α-cam1)`

## α-cam2 — Camera zoom step preset (0.5h)

- [ ] `CameraRig.gd` に zoom step (wheel-less) ホットキー `-` / `=` で min/max 間を n 段階
- [ ] ズーム段階は 5 ステップ固定（3m / 8m / 15m / 30m / 60m）
- [ ] commit: `feat(godot): add zoom step hotkeys -/= for preset distances (α-cam2)`

## Verification

- [ ] test-runner agent で `uv run pytest tests/` 全パス確認
- [ ] build-executor or 直接 `uv run ruff check src/ tests/` パス
- [ ] `uv run ruff format --check src/ tests/` パス
- [ ] code-reviewer agent で 4 commit レビュー、HIGH 全対応

## Empirical Lite

- [ ] `.claude/skills/empirical-prompt-tuning/SKILL.md` Read
- [ ] V (reflection prompt) に Lite tier 適用、subagent dispatch × 2 iter
- [ ] A1 (persona prompt) に Lite tier 適用、subagent dispatch × 2 iter
- [ ] 結果を `.claude/skills/empirical-prompt-tuning/examples.md` に追記
- [ ] 収束（不明瞭点 0、精度改善 +3pt 以下）or 反映必要な修正を identify

## PR

- [ ] `git push -u origin feat/m7-priority3-differentiation-xai`
- [ ] `gh pr create` with Test plan（unit + live G-GEAR 5 項目）
- [ ] PR URL を decisions.md に記録

## Follow-up (本タスク完了時に整理)

- [ ] M6 carryover を V 吸収として close、`_setup-progress` 相当を更新
- [ ] A2/A3/B3/C1-4/D1-4 の track チケットを個別に起票（本タスクに追記 or 別タスク）
- [ ] L6 steering (別 steering dir) の状態確認

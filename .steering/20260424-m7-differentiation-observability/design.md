# Design — M7 First PR (優先 3)

## アプローチ / 修正方針

既存のパターンを流用して **最小差分** で 4 変更を入れる。いずれも
「contract は schema に既存、発火側 or inject 側だけを追加」の構図。
プロンプト改修 2 件 (V, A1) は実装直後に empirical-prompt-tuning Lite で
検証する。

## 変更対象ファイル

### Python (src/erre_sandbox/)

- **`cognition/reflection.py`** (V)
  - L129-135: `build_reflection_messages()` の system prompt 末尾に
    "Respond in Japanese (日本語で応答してください)." に相当する 1 行を追加
  - `integration/dialog_turn.py:100-118` の `_DIALOG_LANG_HINT` dict パターンを
    そのまま流用。persona ごとに語彙を分けない最低実装（必要なら次 PR で拡張）

- **`cognition/prompting.py`** (A1)
  - L65-76: `_format_persona_block(persona)` を拡張
    - `personality` (O/C/E/A/N) を「openness=0.80 conscientiousness=0.40 …」の
      1 行として差し込む
    - `wabi`, `ma_sense` (存在すれば) を「wabi=0.9 ma_sense=0.7」1 行
  - 既存の `preferred_zones` 表示はそのまま残す
  - prompt 長は +2 行以内に抑える

- **`world/tick.py`** (B1)
  - 新規メソッド `_fire_affordance_events(tick, agents, envelope_queue)` を
    `_fire_proximity_events` (L520-559) の直後に挿入
  - zone prop 座標テーブルを `world/zones.py` (L26-34) の近傍に追加
    - MVP: chashitsu の `(x=0, y=0.4, z=15)` 付近に `chawan_01`, `chawan_02` の 2 点
  - agent position が prop 座標と `distance <= 2.0` で `AffordanceEvent` を push
  - 既存の `_fire_proximity_events` の呼び出し箇所と同 tick 内で呼ぶ

- **`world/zones.py`** (B1 の補助)
  - 新定数 `ZONE_PROP_COORDS: dict[Zone, list[PropSpec]]` を追加
  - 初期実装: chashitsu だけ。他 zone は空 list

### Godot (godot_project/)

- **`scripts/BoundaryLayer.gd`** (B2)
  - 既存の zone rect 描画処理 (MeshInstance3D + CSGBox3D) の末尾に
    `_draw_affordance_circles()` と `_draw_proximity_circles()` を追加
  - affordance 2m 半径: ImmediateMesh or TorusMesh、色 yellow (0.9, 0.7, 0.2)
  - proximity 5m 半径: 色 cyan (0.3, 0.7, 0.9)
  - prop 座標は hardcode（schema の PropSpec を Godot 側で受け取る配線は次 PR）

### Tests

- **`tests/test_cognition/test_reflection.py`** (新規 or 既存ファイル追記)
  - `test_reflection_system_prompt_includes_japanese_hint`: system prompt に
    「日本語」「Japanese」いずれかが含まれる
- **`tests/test_cognition/test_prompting.py`** (新規 or 既存ファイル追記)
  - `test_persona_block_includes_personality`: _format_persona_block の返り値に
    `openness=`, `wabi=` 等のキーが含まれる
- **`tests/test_world/test_tick.py`** (既存ファイルに追加)
  - `test_fire_affordance_events_emits_on_proximity`: agent を chawan 2m 以内に
    配置したとき `AffordanceEvent` がエンベロープキューに入る
  - `test_fire_affordance_events_no_emit_outside_radius`: 2m 外では発火しない

## 既存パターンとの整合性

| 新実装 | 流用元 | 共通点 |
|---|---|---|
| V: reflection 日本語化 | `integration/dialog_turn.py:100-118` (_DIALOG_LANG_HINT) | system prompt tail inject |
| A1: personality inject | 同 `prompting.py:65-76` の preferred_zones 行 | 同関数内で 1 行追加 |
| B1: _fire_affordance_events | `world/tick.py:520-559` (_fire_proximity_events) | agent 位置 + 距離判定 + envelope push |
| B2: BoundaryLayer overlay | `scripts/BoundaryLayer.gd` 既存 zone rect 描画 | `_draw_*()` 命名とマテリアル構成 |

## テスト戦略

- TDD 採用: V/A1/B1 は unit 先行（赤 → 実装 → 緑）
- B2 は Godot の UI 変更なので unit test はスキップ、live 検証に回す
- integration: `tests/test_integration/` 既存の end-to-end に触らない（First PR では）
- empirical Lite: V と A1 は指示テキスト改修で、subagent dispatch で検証

## 関連 Skill

- `implementation-workflow` — 共通骨格
- `python-standards` — src/ 配下の Python 編集時
- `test-standards` — tests/ 追加時
- `error-handling` — _fire_affordance_events の例外処理（既存 _fire_proximity_events 踏襲）
- `godot-gdscript` — BoundaryLayer.gd 変更時
- `empirical-prompt-tuning` — V / A1 の検証
- `architecture-rules` — import 方向確認（cognition/ ↔ world/ 不変）

## アンチパターン回避 (plan file より)

- B2 で全 event kind を一括描画しない。chashitsu 1 zone の 1-2 prop 限定 MVP。
- A1 で prompt 長が膨らまない。1 行 Big Five + 1 行 Wabi/Ma のみ。
- V で reflection.py を大改造しない。system prompt tail +1 行。

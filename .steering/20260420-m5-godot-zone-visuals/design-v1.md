# 設計 — m5-godot-zone-visuals (v1 初回案)

> Note: これは /reimagine 前の初回案。/reimagine 起動後に design-v1.md へ退避され、
> design-v2.md (再生成案) / design-comparison.md との比較を経て最終版 design.md が
> hybrid で確定する想定。

## 実装アプローチ

M4 で既に配線済みの WebSocket 信号フロー
(`WebSocketClient → EnvelopeRouter → AgentManager → AgentController`) を
そのまま延伸する。GDScript 側の変更を最小化し、Python 側は一切触らない。

1. **DialogBubble**: `AgentAvatar.tscn` に既存する `SpeechBubble` Label3D を
   **そのまま流用** し、`AgentController.show_dialog_bubble(text, duration_s)` を
   追加。Tween で modulate.a を 0→1 fade-in (0.3s) → sustain → 1→0 fade-out (0.3s)。
   同じ agent に連続 dialog_turn が来たら前の Tween を kill して replace。
2. **ERRE mode tint**: 8 mode × `Color` の dict を `AgentController` の const に
   埋め込む。`AgentState.erre.name` が変化したら `_body.material_override.albedo_color`
   を更新。material_override は SubResource として packed scene に埋めてあるので
   avatar 間で共有されないよう scene 側で `resource_local_to_scene = true` を設定。
3. **Zone MVP**: 既存 `scenes/zones/Peripatos.tscn` を手本に
   `Chashitsu.tscn` / `Zazen.tscn` を追加。Plane + 色違い material + 最低限の
   装飾 (座布団 BoxMesh 等は後回し) で「形だけ」追加。`WorldManager.ZONE_MAP` に
   2 entry 追加するだけで MainScene.tscn は触らない (T17 judgement 9 準拠)。
4. **Signal wiring**: `AgentManager._ready` に `dialog_turn_received` /
   `dialog_close_received` の connect を追加。`agent_updated` handler で
   `agent_state.erre.name` を読んで `set_erre_mode` を呼ぶ。

## 変更対象

### 修正するファイル

- `godot_project/scripts/AgentController.gd`
  - const `ERRE_MODE_COLORS: Dictionary` を追加 (8 mode → Color)
  - const `BUBBLE_FADE_SEC = 0.3`, `BUBBLE_DEFAULT_DURATION = 4.0`
  - `func set_erre_mode(mode: String) -> void` 追加
  - `func show_dialog_bubble(text: String, duration_s: float = 4.0) -> void` 追加
  - `update_position_from_state` で `agent_state.erre.name` を取って
    `set_erre_mode` を呼ぶ (nil-safe)
  - 既存 `show_speech` は M4 互換のため残す
- `godot_project/scripts/AgentManager.gd`
  - `_REQUIRED_SIGNALS` に `dialog_turn_received`, `dialog_close_received` を追加
  - `_on_dialog_turn_received(dialog_id, speaker_id, addressee_id, utterance)` 追加
    → speaker_id の avatar を `_get_or_create_avatar` で取得 → `show_dialog_bubble`
  - `_on_dialog_close_received(dialog_id, reason)` は log のみ (bubble は自然消滅)
- `godot_project/scripts/WorldManager.gd`
  - `ZONE_MAP` に `"chashitsu": preload(...)`, `"zazen": preload(...)` を追加
- `godot_project/scenes/agents/AgentAvatar.tscn`
  - `SpeechBubble` Label3D の `modulate` 初期値を `Color(1,1,1,0)` に (Tween 制御用)
  - Body の material_override の sub_resource に `resource_local_to_scene = true` を
    付与してシーン instantiate 時に複製されるようにする

### 新規作成するファイル

- `godot_project/scenes/zones/Chashitsu.tscn` — 木目 plane + 低座布団風 box 数個
- `godot_project/scenes/zones/Zazen.tscn` — 石畳 plane + 中央に岩/坐蒲風 box
- `tests/test_godot_dialog_bubble.py` — fixture 再生 → stdout の
  `[AgentController] dialog_bubble agent_id=... len=...` 行を assert
- `tests/test_godot_mode_tint.py` — fixture 再生 → stdout の
  `[AgentController] mode_set agent_id=... mode=chashitsu` を assert

### 削除するファイル

- なし (additive only)

## 影響範囲

- **MainScene.tscn**: 触らない方針。ZoneManager の子は WorldManager が runtime で
  instantiate するため .tscn diff は 0。
- **既存 show_speech path**: そのまま維持。M4 の speech 経路は dialog_turn と
  独立しているので並走可能。
- **fixture replay (test_godot_peripatos)**: ZONE_MAP 追加で chashitsu/zazen も
  boot 時 spawn される。既存 assertion は「peripatos spawned」のみチェックする
  substring 一致なので理論上は無回帰だが、要確認。
- **material_override 共有**: AgentAvatar.tscn 内部の SubResource は packed scene
  instantiation 時に複製されないのが Godot 4 default。3 avatar 同時存在時に
  1 agent の tint 変更が全員に伝播する bug を `resource_local_to_scene = true` で
  回避。

## 既存パターンとの整合性

- `show_speech` (AgentController.gd:111) のシグネチャに揃えて
  `show_dialog_bubble(text, duration_s)` を兄弟メソッド化
- `AgentManager._REQUIRED_SIGNALS` と match signal connect のパターンを踏襲
- `WorldManager.ZONE_MAP` の preload パターンをそのまま使う
- `scenes/zones/Peripatos.tscn` の Plane + material_override 構造を手本
- `tests/test_godot_peripatos.py` の harness_result 共有 fixture pattern を
  bubble / tint test にも複製
- Godot print prefix `[AgentController] xxx agent_id=... ...` の log 書式を維持
  (fixture replay 用 assertion に依存している)

## テスト戦略

- **Python 側単体テスト**: 無し (GDScript 側のロジックは Python から直接呼べない)
- **Godot fixture-gated 統合**:
  - `test_godot_dialog_bubble.py`: fixture dir に `dialog_turn.json` を置いた
    harness replay → `[AgentController] dialog_bubble agent_id=a_kant_001 len=...`
    行と `[AgentManager] avatar spawned` 行の両方を assert
  - `test_godot_mode_tint.py`: `agent_update.json` に `erre.name=chashitsu` を
    持たせた fixture を投入 → `[AgentController] mode_set agent_id=... mode=chashitsu`
    を assert
- **既存 regression**:
  - `test_godot_peripatos.py` が新規 zone spawn で失敗しないか確認
  - `uv run pytest -q` で 513 test に 0 regression
- **Live (M5 acceptance #5/#6)**:
  - MacBook Godot editor で MainScene を 60s 走らせて bubble 表示 + tint 変化を
    目視 + mp4 録画
  - FPS overlay (F3) で 30Hz 維持を確認

## ロールバック計画

- AgentController の新規 method は additive なので未呼出しなら影響ゼロ
- AgentManager の新規 signal connect を削除すれば M4 挙動に戻る
- MainScene.tscn 無改変のため .tscn revert は不要
- WorldManager.ZONE_MAP から chashitsu/zazen を削除すれば zone 非表示
- feature flag は Python 側 (`src/erre_sandbox/__main__.py`) の
  `--disable-dialog-turn` が M5 plan 判断 6 で既に予定されているので、Godot 側
  bubble は dialog_turn envelope が来ない限り発火しない → 自動 opt-out 可能
- 最終手段: `git revert` で PR 単位 revert

## 未解決 / 気になる点 (reimagine で攻めるべき)

- DialogBubble と SpeechBubble を同じ Label3D で兼用するのは本当に正解か?
  (speech と dialog_turn が同 frame に来たら last-wins で情報欠落)
- 8-mode 色定義を AgentController の const にハードコードするか、autoload
  Singleton (`ERREModeTheme.gd`) に分離するか
- Tint 変化を hard swap vs Tween で滑らかにするか (FSM が短周期で振れたら
  strobe になる懸念)
- dialog_close 時の bubble 処理は Tween 任せで十分か、明示 fade-out すべきか
- Chashitsu/Zazen の装飾粒度 (plane だけ vs 座布団/岩など MVP 相当の小物)
- fixture-gated test だけで bubble fade timing / tint transition を十分
  covering できるか (Godot 側 GDScript unit test 導入の是非)

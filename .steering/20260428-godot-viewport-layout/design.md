# 設計 (v2.1 — codex review 反映後の最終版)

> **採用版**。Claude が生成した v2 を **codex review (gpt-5.5, xhigh)** が
> independent に評価し、HIGH 3 件 / MEDIUM 2 件の盲点を指摘 → **案 A
> (measured/persistent split)** が推奨された。本文書は v2 + codex 修正を
> 取り込んだ実装契約。
>
> 参照: `codex-review.md` / 過去案: `design-v1.md` / 比較: `design-comparison.md`

## 実装アプローチ

`HBoxContainer "Split"` を **`HSplitContainer "Split"`** に置換し、
`window/stretch` で window 比例伸縮を有効化、collapse は **「内容を畳む
(body container を `visible=false`)」+ 幅を 60px に縮める** の 2 段で
実装する。expanded/collapsed の最小幅は **2 つの異なる定数** で管理し、
`custom_minimum_size` を状態に応じて切り替える。drag された expanded 幅は
`dragged` signal で記憶し、collapse → expand で復元する。

`split_offset` は Godot 4.6 で deprecated path を辿る (codex HIGH 1) ため、
**`split_offsets`** (PackedInt32Array) を使い、scene 側では初期値を計算式に
頼らず、起動時に `_apply_split_offset()` で `clamp_split_offset()` 経由で
設定する。

`size_2d_override_stretch` は no-op の可能性が高い (codex MEDIUM 4) ため
**追加しない**。黒帯は `window/stretch/*` のみで解消できる仮説を採り、
ローカル手動 verify で実測 size をログ出力して原因切り分けする。

## codex 指摘の取り込み一覧

| codex 指摘 | 重要度 | 反映 |
|---|---|---|
| `split_offset` deprecated, default 位置は expand flags + min_size 依存 | HIGH | `split_offsets` API + 起動時計算で解消 |
| 320→340 と 320→60 の混在矛盾 | HIGH | `PANEL_EXPANDED_WIDTH=340` / `PANEL_COLLAPSED_WIDTH=60` を分離、状態に応じて `custom_minimum_size` を切替 |
| collapse 中も body が見える → 60px で UI 潰れる | HIGH | body VBoxContainer (header 除く) を `visible=false` にする |
| `size_2d_override_stretch` no-op | MEDIUM | 追加しない、`window/stretch/*` のみで解消、verify で実測 |
| resize 後 collapse → expand で drag 幅が失われる | MEDIUM | `dragged` signal で `_last_expanded_offset` 記録、expand 時は復元 |
| Button を panel root に add する誤り | LOW | `_build_header(vbox)` で vbox 直下に Header HBoxContainer を作り、Body は別 VBoxContainer に分離 |
| design-comparison.md「6 件」記載 (実は 4 件) | LOW | comparison 側で訂正 |
| 「v2 は v1 strictly superset」過大評価 | LOW | comparison 側で訂正 |

## 変更対象

### 修正するファイル

- **`godot_project/project.godot`** (`[display]` セクション)
  - 追加: `window/size/resizable = true`
  - 追加: `window/stretch/mode = "canvas_items"`
  - 追加: `window/stretch/aspect = "expand"`
  - **追加せず**: `window/stretch/scale` 系は default のまま

- **`godot_project/scenes/MainScene.tscn`**
  - `[node name="Split" type="HBoxContainer" parent="UILayer"]` を
    `[node name="Split" type="HSplitContainer" parent="UILayer"]` に置換
  - `anchors_preset = 15` (Full Rect) は維持
  - **`split_offset` / `split_offsets` を tscn に書かない** (起動時に GDScript
    から `clamp_split_offset()` 経由で設定)
  - `[node name="WorldView" type="SubViewportContainer" ...]`
    - `stretch = true`, `size_flags_horizontal = 3`, `size_flags_vertical = 3`
      は維持
    - **`size_2d_override_stretch` は追加しない** (codex MEDIUM-4)
  - `[node name="ReasoningPanel" type="Control" ...]`
    - `custom_minimum_size = Vector2(340, 0)` は **維持** (初期 expanded 状態)
    - `size_flags_horizontal = 0 → 3` に変更 (HSplit 子は両側 expand 必要)
    - `size_flags_vertical = 3` 維持

- **`godot_project/scripts/ReasoningPanel.gd`**
  - 定数追加 (file 上部):
    ```gdscript
    const PANEL_EXPANDED_WIDTH := 340
    const PANEL_COLLAPSED_WIDTH := 60
    ```
  - メンバ変数追加:
    ```gdscript
    var _split: HSplitContainer
    var _collapsed: bool = false
    var _last_expanded_offset: int = 0
    var _collapse_button: Button
    var _body_container: VBoxContainer
    ```
  - L93 `Vector2(320, 0)` → `Vector2(PANEL_EXPANDED_WIDTH, 0)` に変更
    (起動時は expanded、collapse すると `Vector2(PANEL_COLLAPSED_WIDTH, 0)` に
    切り替える)
  - `_build_tree()` 構造を改修:
    - 既存 ColorRect / MarginContainer は維持
    - vbox の構造を `Header HBox` + `Body VBoxContainer` の 2 段に分離
    - Header: 折りたたみボタン (▶ / ◀) のみ
    - Body: 既存の OptionButton / Label 群
    - collapse 時は `_body_container.visible = false`、expand で `true`
  - `_ready()` で:
    - `_split = get_parent() as HSplitContainer`
    - 直後に `_apply_split_offset(-PANEL_EXPANDED_WIDTH)` で初期化
    - `_split.dragged.connect(_on_split_dragged)` で drag 記録
  - 新規メソッド:
    - `_build_header(vbox)`: HBox + ▶ Button (vbox 直下に挿入)
    - `_build_body(vbox)`: 既存 VBox 中身を Body 配下にラップ
    - `_toggle_collapse()`: collapse / expand toggle、custom_minimum_size と
      `_body_container.visible` と `_collapse_button.text` を切替
    - `_apply_split_offset(offset)`: `_split.split_offsets = PackedInt32Array([offset])`
      + `_split.clamp_split_offset()` (4.6 API)
    - `_on_split_dragged(offset)`: `_last_expanded_offset = offset` 記録
      (collapse 状態では記録しない)

### 新規作成するファイル

- なし

### 削除するファイル

- なし

## 影響範囲

- **resize**: HSplitContainer の splitter ドラッグで panel 幅変更可能
- **collapse**: ▶ ボタンで body を畳み 60px 幅に。再度 ▶ で記憶された
  drag 幅または default 340 に展開
- **regression リスク**:
  - HBoxContainer → HSplitContainer の置換は子 size_flags 要件が異なるため
    panel size_flags_h を 0 → 3 に変更必須。`split_offsets` で実効幅を制御
  - SelectionManager → ReasoningPanel の signal 接続 (MainScene.tscn:97) は
    Split node 名変更がないため影響なし
- **camera / 3D viewport**: SubViewportContainer の現状設定維持で互換
- **ζ-1 surfaces (OptionButton / day-night ambient)**: Body 配下に移動するが
  parent 階層は VBoxContainer 同士なので layout は同等

## 既存パターンとの整合性

- `godot-gdscript` Skill: Container based layout 規約と整合
- `_build_tree()` の動的 UI 構築パターンを維持。`_build_header` / `_build_body` は
  同パターン
- M5 zone-visuals 以来の `CanvasLayer > Split > {WorldView, ReasoningPanel}`
  ネスト構造を保つ (Split type のみ変更)

## テスト戦略

- **回帰**: `tests/test_godot_project.py::test_godot_project_boots_headless`、
  `tests/test_godot_ws_client.py` (FixtureHarness) ともに pass
- **新規**: GDScript 側の split/collapse は Godot binary 必須なので pytest 不可。
  手動 verify で受け入れ
- **解像度**: 1280x720 / 1920x1080 / 2560x1440 でローカル boot し、
  各解像度で `print()` で `Split.size.x` / `WorldView.size.x` / `ReasoningPanel.size.x`
  / `WorldViewport.size` を 1 度ログ出力 (codex 必須確認 1)。実装完了後にログ出力は
  消すか debug build のみ残す
- **手動 acceptance**:
  - 3 解像度で 3D viewport が画面 ~75%+ を占有 (panel 340px 維持)
  - ▶ クリックで body 消失 + 60px collapse
  - ◀ クリックで body 復活 + 元の幅に expand (drag 記憶あれば復元)
  - splitter ドラッグで panel 幅変更、minimum 60px で stop
  - collapsed 中に OptionButton クリック / camera drag / left click selection /
    day-night ambient (M7-ζ surfaces) regression なし

## ロールバック計画

- 全変更は 4 ファイル (project.godot, MainScene.tscn, ReasoningPanel.gd,
  + .steering/) のみ。`git revert <commit>` 1 発で完全戻し
- 部分破綻時 (例: HSplitContainer の挙動が想定外):
  - MainScene.tscn の Split node type を HBoxContainer に戻す
  - ReasoningPanel.gd の `_split` 参照を guard で無効化
  - body container 構造変更だけ残す → collapse 機能 off で 1280x720 動作復帰

## 設計判断の履歴

- 初回案 (`design-v1.md`) と再生成案 (旧 v2、`design-v1.md` 隣の Claude 自己再生成) を比較
  (`design-comparison.md`)、Claude は v2 採用判断
- `codex-review-prompt.md` で codex (gpt-5.5, xhigh) に independent 評価依頼
- codex review (`codex-review.md`) で v2 の HIGH 3 / MEDIUM 2 / LOW 1 が指摘され、
  「案 A: measured/persistent split (v2.1)」を推奨
- 採用: **v2.1** (本文書)。codex 指摘 6 件全てを設計に反映
- 確定日: 2026-04-28

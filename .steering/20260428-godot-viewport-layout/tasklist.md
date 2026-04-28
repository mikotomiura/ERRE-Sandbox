# タスクリスト — godot-viewport-layout (v2.1 採用、codex review 反映後)

## 準備
- [x] requirement.md / design.md / .steering/ 関連を読む
- [x] file-finder で project.godot / MainScene.tscn / ReasoningPanel.gd 現状調査
- [x] /reimagine v1/v2 比較 (Claude 自己判断は v2)
- [x] **codex に v1/v2 評価を依頼** (gpt-5.5 xhigh、`codex-review.md`)、案 A
      (v2.1 measured/persistent split) 推奨を受領
- [x] design.md / design-comparison.md を v2.1 に更新

## 実装

### A. project.godot に display stretch を追加 (codex 影響なし)
- [ ] `[display]` セクション末尾に追加:
  - `window/size/resizable = true`
  - `window/stretch/mode = "canvas_items"`
  - `window/stretch/aspect = "expand"`

### B. MainScene.tscn のレイアウト改修 (codex MEDIUM-4 反映: size_2d_override_stretch 削除)
- [ ] `[node name="Split" type="HBoxContainer" ...]` を `HSplitContainer` に置換
- [ ] `split_offset` / `split_offsets` を tscn には書かない (起動時 GDScript 設定)
- [ ] WorldViewport は変更なし (`size_2d_override_stretch` は no-op のため追加せず)
- [ ] ReasoningPanel の `size_flags_horizontal = 0 → 3` に変更
- [ ] ReasoningPanel `custom_minimum_size = Vector2(340, 0)` は維持 (初期 expanded)

### C. ReasoningPanel.gd の改修 (codex HIGH 3件 + MEDIUM 1件 反映)

#### C-1. 定数とメンバ変数 (codex HIGH-2: 矛盾解消)
- [ ] file 上部に定数:
  - `const PANEL_EXPANDED_WIDTH := 340`
  - `const PANEL_COLLAPSED_WIDTH := 60`
- [ ] メンバ変数追加:
  - `var _split: HSplitContainer`
  - `var _collapsed: bool = false`
  - `var _last_expanded_offset: int = 0`
  - `var _collapse_button: Button`
  - `var _body_container: VBoxContainer`

#### C-2. _build_tree() を Header / Body 分離構造に (codex HIGH-3 + LOW-6)
- [ ] L93 `Vector2(320, 0)` → `Vector2(PANEL_EXPANDED_WIDTH, 0)` に変更
- [ ] vbox を `Header HBox` + `_body_container = VBoxContainer` の 2 段に分離
- [ ] Header に collapse ボタン (▶) のみ追加
- [ ] 既存の OptionButton / Label 群を Body 配下に移動

#### C-3. _ready() で split を取得 + drag signal 接続 (codex HIGH-1 + MEDIUM-5)
- [ ] `_split = get_parent() as HSplitContainer` 取得
- [ ] `_apply_split_offset(-PANEL_EXPANDED_WIDTH)` で初期 expanded
- [ ] `_split.dragged.connect(_on_split_dragged)` で drag 記録

#### C-4. 新規メソッド
- [ ] `_build_header(parent)`: HBox + ▶ Button を parent 直下に作成
- [ ] `_build_body(parent)`: 既存 VBox 中身を Body 配下にラップ
- [ ] `_toggle_collapse()`:
  - `_collapsed` flip
  - `custom_minimum_size = Vector2(PANEL_COLLAPSED_WIDTH if _collapsed else PANEL_EXPANDED_WIDTH, 0)`
  - `_body_container.visible = not _collapsed`
  - `_collapse_button.text = "◀" if _collapsed else "▶"`
  - `_apply_split_offset(-PANEL_COLLAPSED_WIDTH if _collapsed else _last_expanded_offset)`
- [ ] `_apply_split_offset(offset)`:
  - `_split.split_offsets = PackedInt32Array([offset])` (Godot 4.6 API、deprecated `split_offset` 不使用)
  - `_split.clamp_split_offset()`
- [ ] `_on_split_dragged(offset)`:
  - `if not _collapsed: _last_expanded_offset = offset` で expanded 中の drag のみ記録

## テスト・検証
- [ ] `tests/test_godot_project.py::test_godot_project_boots_headless` 単独実行で headless boot 成功
- [ ] `tests/test_godot_ws_client.py` regression なし (FixtureHarness 経路)
- [ ] **codex 必須確認 1**: 1280/1920/2560 で起動し `print()` で `Split.size.x`,
      `WorldView.size.x`, `ReasoningPanel.size.x`, `WorldViewport.size` をログ出力
      し黒帯原因を切り分け (実装中の debug 用、merge 前に削除 or `#if DEBUG` 保持)
- [ ] **codex 必須確認 2**: Godot 4.6 で `split_offsets` の scene serialization 確認
- [ ] **codex 必須確認 3**: collapse 中に OptionButton / camera drag / left click
      selection / day-night ambient regression なし
- [ ] ローカル手動: 1280x720 / 1920x1080 / 2560x1440 で 3D viewport ~75%+ 占有
- [ ] ローカル手動: ▶ クリックで body 消失 + 60px collapse、再クリックで復元
- [ ] ローカル手動: splitter ドラッグで panel 幅変更、minimum 60px で stop、
      collapse → expand で記憶幅復元

## レビュー
- [ ] code-reviewer サブエージェントによるレビュー
- [ ] HIGH 指摘への対応
- [ ] MEDIUM 指摘の判断

## ドキュメント・記録
- [x] decisions.md に v2.1 採用根拠 + codex 評価結果 (本 task 開始時に作成済の場合は更新)
- [x] design.md の最終化 (v2.1 として codex 指摘 6 件全反映)

## 完了処理
- [ ] git add: project.godot / MainScene.tscn / ReasoningPanel.gd / .steering/20260428-godot-viewport-layout/
- [ ] `feat(ui): expand 3D viewport via HSplitContainer + window stretch + collapsible ReasoningPanel (v2.1 codex)` で commit
- [ ] PR 作成、3 並列 CI 確認
- [ ] /finish-task で closure

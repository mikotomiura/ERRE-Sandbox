# 設計 (v1 — 初回案)

## 実装アプローチ

「最小修正で黒帯を消し、既存 Layout を温存する」方針。
project.godot に `window/stretch/mode = "canvas_items"` と
`window/stretch/aspect = "expand"` を追加することで Godot 4 の disabled
デフォルトを解消し、ウィンドウリサイズに viewport が追随するようにする。
ReasoningPanel は現行どおり固定幅 (340px) の右サイド固定パネルとして据え置き、
既存挙動の regression を最小化する。`_build_tree()` の 320/340 不整合は
340 に統一する付随修正。

採用根拠: 黒帯の根本原因 (`window/stretch/mode` 未設定) を最低限のキーで
解消し、UI 構造変更を伴わない。observation.md L488-490 の "3D canvas
occupies ~50% of window" を「ほぼ全面化 (panel 占有 ~25% を除く)」に到達
させる最短路。collapse / resize は次回 task に分離。

## 変更対象

### 修正するファイル

- `godot_project/project.godot`
  - `[display]` セクション末尾に追加:
    - `window/size/resizable = true`
    - `window/stretch/mode = "canvas_items"`
    - `window/stretch/aspect = "expand"`
- `godot_project/scenes/MainScene.tscn`
  - `WorldView (SubViewportContainer)` の `size_flags_horizontal = 3` 維持、
    `stretch_shrink = 1` を明示 (デフォルトと同値だがレイアウト contract 化)
  - `SubViewport "WorldViewport"` に `size_2d_override_stretch = true` を追加
- `godot_project/scripts/ReasoningPanel.gd` L93
  - `Vector2(320, 0)` を `Vector2(340, 0)` に揃え、tscn と整合

### 新規作成するファイル

- なし

### 削除するファイル

- なし

## 影響範囲

- 既存挙動の変更箇所は「ウィンドウサイズ != 1280x720 でも viewport が
  比例伸縮する」ことだけ
- ReasoningPanel 幅は 340px に統一、20px 広がる程度の差異
- 1280x720 では現状とほぼ同一見た目、1920x1080 / 2560x1440 で 3D area が
  ウィンドウ拡張に追随

## 既存パターンとの整合性

- `godot-gdscript` Skill の anchor / Control レイアウト規約に従う
- 既存の HBoxContainer Split 構造は変更しない (M5 zone-visuals 以来安定)

## テスト戦略

- `tests/test_godot_project.py::test_godot_project_boots_headless` が pass
- 1280x720 / 1920x1080 / 2560x1440 でローカル手動 boot し screenshot 確認
- Fixture harness (`test_godot_ws_client` 経路) regression なしを確認

## ロールバック計画

- project.godot の 3 行 + tscn 1 行 + GDScript 1 行のみ。`git revert` 1 発で
  完全戻し可能

## 弱点 (再生成時に考慮すべき)

- ReasoningPanel が collapse / resize 不可のまま → requirement 受け入れ条件
  L36 「collapse / resize 可能」を満たさない
- 高解像度 (4K+) で panel が相対的に小さく見える固定幅問題は未解決
- side overlay 化や splitter 導入の余地未検討

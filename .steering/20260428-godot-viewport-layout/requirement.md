# Godot viewport layout — world を画面いっぱいに拡張 (F3)

## 背景

ζ-1 部分マージ後 live 観察 (decisions.md D7v2):
- F3 (04/27) 「world 画面自体がとても小さいので拡張してほしい」

ζ-3 verify frame でも 3D viewport は canvas 中央に小さく表示、上下左右
に黒余白が大きく残る。E1 (camera 操作) や A4 (world 物理サイズ拡張)
とは別系統で、Godot ウィンドウ / viewport / UI レイアウト anchor 設計が
原因。schema/backend 非依存、1 PR 最速 land 可能。

## ゴール

Godot ウィンドウのほぼ全面に 3D world が描画され、ReasoningPanel は
side overlay または resizable split として共存。M9-LoRA 着手前に live
UX を最速で底上げ。

## スコープ

### 含むもの
- `godot_project/project.godot` `display/window/size/viewport_*` 見直し
- `MainScene.tscn` root の anchor / margin 設計刷新
- `ReasoningPanel` の Control anchor 調整 (full-height side overlay)
- 必要なら resizable splitter / collapse button

### 含まないもの
- camera 操作の polish (E1)
- world 物理サイズ拡張 (A4)
- backend / schema 変更

## 受け入れ条件

- [ ] 1280x720 / 1920x1080 / 2560x1440 で 3D viewport がほぼ全面
- [ ] ReasoningPanel が collapse / resize 可能、minimum width で生き残る
- [ ] OptionButton / camera 操作 / day-night ambient (ζ-1 surfaces) の
      regression なし
- [ ] /reimagine v1+v2 並列 (anchor 設計は複数案ありうる)

## 関連ドキュメント

- `.steering/20260426-m7-slice-zeta-live-resonance/decisions.md` D7v2
- `godot-gdscript` Skill (anchor / Control レイアウト)
- ζ-3 verify frames at observation.md

# 設計 — T15 godot-project-init (初回案 v1)

## 実装アプローチ

MASTER-PLAN §7.3 が指示する **最小ブートアブル** 構成を素直に作る。
`godot_project/` に project.godot + 1 つのスタブ MainScene + icon.svg のみを
置き、Compatibility renderer で declare。`.gitignore` に Godot キャッシュ
(`.godot/`, `*.import`, `export_presets.cfg`) を追加。patterns.md の
5-zone / AgentManager / UILayer 構造は T17 / M5 に譲る。

方針の要点:
1. MainScene = Node3D + Label3D "ERRE-Sandbox T15 init" のみ
2. `project.godot` は 4.4 compat + Compatibility renderer + main_scene 指定
3. `icon.svg` は ERRE-Sandbox の暫定アイコン (手書き)
4. 検証は手動: `Godot --path godot_project --headless --quit`
5. patterns.md の MainScene 階層 (5 zones/AgentManager/UILayer) は未着手

## 変更対象

### 修正するファイル
- `.gitignore` — Godot キャッシュ除外

### 新規作成するファイル
- `godot_project/project.godot`
- `godot_project/icon.svg`
- `godot_project/scenes/MainScene.tscn`

### 削除するファイル
- なし

## テスト戦略

- 手動検証: `Godot --path godot_project --headless --quit` がエラー無終了
- pytest 自動テストは v1 では導入しない (headless boot は OS 依存)

## ロールバック計画

- 新規 `godot_project/` + .gitignore 編集のみ。`git clean -fdx godot_project` で復元

## v1 の自覚している懸念点

| 懸念 | 内容 |
|---|---|
| T16/T17 の pick-up が遅い | MainScene 階層 (ZoneManager/AgentManager/WebSocketClient/UILayer) が patterns.md に書かれているのに v1 では空のため、T16 着手時に一式追加する手間が増える |
| 空 SVG icon のデザイン | 手書きは時間がかかる。pure white 四角でも良い |
| GDScript ファイルなし | `WorldManager.gd` や `MainScene.gd` が無いと Skill の参照例と齟齬 |
| repository-structure ミラー不完全 | `scenes/zones/`, `scripts/`, `assets/` ディレクトリが未作成 |
| 自動検証なし | Godot boot を手動確認のみ依存 |
| patterns.md との乖離残存 | T17 着手時に「v1 で空にした部分」を追加する判断が毎回必要 |

これらを引きずらず、`/reimagine` で v2 を生成する。

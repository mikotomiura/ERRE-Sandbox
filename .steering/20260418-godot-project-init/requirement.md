# T15 godot-project-init

## 背景

Phase C が完了し Phase P (Parallel Build) に突入。MacBook 側ラインの起点として、
`godot_project/` に Godot 4.4 の最小ブート可能プロジェクトを初期化する。
後続 T16 godot-ws-client (WebSocket 受信) / T17 godot-peripatos-scene
(Linden-Allee 3D シーン) / M5 のゾーン拡張 (chashitsu/agora/garden) が
このスケルトンの上に積み上がる。

制約:

- `godot_project/` 内に Python を置くことは厳禁 (architecture-rules 参照)。
  Godot ↔ Python 連携は WebSocket 経由のみ
- GPL 依存の bpy / Blender も `godot_project/` に入れない
- MacBook Air M4 (Apple Silicon) で動作すること
  - 実機 Godot 4.6.2 がインストール済 (`/Applications/Godot.app`)
  - project.godot は Godot 4.4 compat で declare (MASTER-PLAN 指定)
  - renderer は Apple Silicon で安定する `gl_compatibility` または `mobile` を選ぶ
- Godot 側のキャッシュ (`.godot/`, `*.import`) は .gitignore に追加

## ゴール

- `/Applications/Godot.app/Contents/MacOS/Godot --path godot_project --headless --quit`
  がエラーなく完了する最小構成
- Godot Editor で `godot_project/project.godot` を開くと MainScene が表示される
- `.gitignore` に Godot キャッシュ関連エントリを追加
- repository-structure.md の `godot_project/` ツリーと実体が整合
- T16 godot-ws-client が WebSocketClient.gd をすぐ書き足せる配置

## スコープ

### 含むもの
- `godot_project/project.godot` — Godot 4.4 project 定義
  - feature flags: `4.4`, 適切な renderer
  - `run/main_scene` に MainScene.tscn 指定
  - `application/config/name` = "ERRE-Sandbox"
- `godot_project/icon.svg` — プロジェクトアイコン (Godot デフォルト相当を手書き)
- `godot_project/scenes/MainScene.tscn` — スタブシーン (Node3D + Label3D で
  "ERRE-Sandbox T15 init" 表示)
- `godot_project/scripts/MainScene.gd` — boot 用最小スクリプト (optional)
- `.gitignore` に Godot 関連エントリ追加 (`godot_project/.godot/`, `*.import`,
  `export_presets.cfg` 等)
- Godot headless boot の検証方法を design.md に記録
- 必要なら Godot boot を検証する Python テスト (pytest で
  `Godot --headless --quit` を呼ぶ) — design で判断

### 含まないもの
- WebSocketClient.gd の実装 (T16 godot-ws-client)
- 5 ゾーンシーンの実装 (T17 + M5)
- AgentAvatar シーン・アニメーション設定 (T16/T17)
- Streamlit / HTMX ダッシュボード (T18)
- 3D アセット (.glb モデル) の追加 (M4 以降、Blender 連携時)

## 受け入れ条件

- [ ] `godot_project/project.godot` が Godot 4.4 compat で declare 済
- [ ] `godot_project/scenes/MainScene.tscn` が存在し `run/main_scene` で参照
- [ ] `godot_project/icon.svg` が存在
- [ ] `/Applications/Godot.app/Contents/MacOS/Godot --path godot_project --headless --quit`
  がエラーなく終了
- [ ] `.gitignore` に `godot_project/.godot/`, `*.import`, `export_presets.cfg`
- [ ] `godot_project/` に `.py` ファイルが 0 件
- [ ] `godot_project/` に GPL 由来のアセット・ライブラリが 0 件
- [ ] MainScene を実機 Godot エディタで開けること (手動確認)
- [ ] `uv run ruff check src/ tests/` 警告ゼロ (影響なし確認)
- [ ] `uv run pytest` 全パス (影響なし確認; 新テストを追加する場合も含む)
- [ ] Conventional Commits でコミット & PR 作成

## 関連ドキュメント

- `docs/repository-structure.md` §1 `godot_project/` ツリー
- `docs/architecture.md` (Godot 4.4 MIT ライセンス)
- `.claude/skills/godot-gdscript/SKILL.md` (GDScript 命名規約, ControlEnvelope 処理)
- `.claude/skills/architecture-rules/SKILL.md` (godot_project に Python 禁止)
- `.claude/skills/blender-pipeline/SKILL.md` (GPL 分離ルール)
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §4.2 T15 行

## 運用メモ

- 破壊と構築（/reimagine）適用: **Yes**
- 理由: 「最小ブート」と「スカフォールド」の 2 方向があり、後続 T16/T17 の
  受け入れ体験 + repository-structure.md との整合に影響する。reimagine で
  両方を並べて判断する価値が高い
- タスク種別: その他 (インフラ初期化)
- 使用するサブエージェント・コマンド:
  - /start-task (完了), /reimagine, /finish-task 相当
  - file-finder — 既存 godot 関連記述・テンプレート・参考資産の調査
  - code-reviewer — project.godot 設定・tscn 構造・.gitignore 網羅のレビュー
- 注意事項:
  - 実機 Godot は 4.6.2 (newer than 4.4)。4.4 compat で書けば 4.6.2 で開ける
  - Apple Silicon で Forward+ renderer が不安定なケースがあるため
    `gl_compatibility` または `mobile` を第一候補

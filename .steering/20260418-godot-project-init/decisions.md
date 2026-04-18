# 重要な設計判断 — T15 godot-project-init

## 判断 1: Scaffolded Handoff (v1 最小ブートを破棄)

- **判断日時**: 2026-04-18
- **背景**: T15 は Phase P MacBook 側ラインの起点。後続 T16/T17/M5 の
  pick-up 体験に直接影響する
- **選択肢**:
  - A: 最小ブートアブル (MainScene に Label3D のみ、他空)
  - B: Scaffolded Handoff (patterns.md §2 階層 + dir ミラー + GDScript 骨組み)
- **採用**: B (v2)
- **理由**: requirement.md §ゴール「T16 がすぐ書き足せる配置」要求への直接応答

## 判断 2: GL Compatibility renderer を採用

- **判断日時**: 2026-04-18
- **背景**: Apple Silicon M4 統合 GPU + Godot 4.6.2 の組み合わせで Forward+
  が不安定なケース報告あり
- **採用**: `renderer/rendering_method="gl_compatibility"`
- **理由**:
  - MASTER-PLAN §7.3 が明示指定 ("Compatibility" renderer)
  - Apple Silicon での描画安定性
  - MVP 段階では Forward+ の高度な lighting は不要
- **見直しタイミング**: M4 で Blender アセットを追加し Forward+ の PBR lighting が
  必要になった時

## 判断 3: MainScene 階層を patterns.md §2 に完全準拠

- **判断日時**: 2026-04-18
- **採用される階層**:
  ```
  MainScene (Node3D, WorldManager.gd)
  ├── Environment (WorldEnvironment + Environment sub-resource)
  │   └── DirectionalLight3D (shadow_enabled)
  ├── Camera3D (current=true)
  ├── ZoneManager (Node3D)           ← T17/M5 がゾーン instance 追加
  ├── AgentManager (Node3D)          ← T16 がエージェント add_child
  ├── WebSocketClient (Node)         ← T16 が .gd を attach
  └── UILayer (CanvasLayer)
      ├── SpeechBubbleContainer (Control)
      └── DebugOverlay (Label)
  ```
- **理由**: 後続タスクで「階層追加」ではなく「既存ノードへの attach / instance」で
  進められる
- **影響範囲**: T16, T17, M5 全てに波及。階層変更が必要になった場合は本 PR を
  起点として別 PR で変更

## 判断 4: 各 dir に README.md を配置 (`.gitkeep` ではない)

- **判断日時**: 2026-04-18
- **採用場所**:
  - `scenes/zones/README.md` — 予定ファイル表 + 命名規約 + ZONE_MAP での
    enum-node name 吸収
  - `scripts/README.md` — GDScript 命名規約 + 予定ファイル一覧 + 禁止事項
  - `assets/README.md` — GPL 分離ルール + Blender パイプライン
- **理由**:
  - 空 dir 問題 (git untracked) を解決
  - Godot 開発者 (T17 / M4 / 新参) に即座に文脈を提供
  - `.gitkeep` は無機質で意図不明

## 判断 5: pytest で Godot headless boot を自動検証

- **判断日時**: 2026-04-18
- **背景**: Phase C の「機械で守る」精神を Phase P でも継続
- **実装**: `tests/test_godot_project.py` に 3 件
  1. 必須ファイル存在 (project.godot / MainScene.tscn / icon.svg / WorldManager.gd)
  2. Python 混入ゼロ (architecture-rules 強制)
  3. Godot headless boot (Godot 未 install 環境は skip)
- **理由**:
  - 将来 Godot 更新で破壊された時に即検知
  - architecture-rules の禁止事項をコード自身が守る
- **トレードオフ**: `S603 noqa` 1 件を受け入れ (入力は全て trusted source)

## 判断 6: Godot 4.4 compat declare + 4.6.2 実機

- **判断日時**: 2026-04-18
- **背景**: setup-macbook decisions 判断 1 の延長
- **採用**: `config/features=PackedStringArray("4.4", "GL Compatibility")`
- **理由**:
  - MASTER-PLAN は Godot 4.4 を指定
  - Godot 4.x は minor 間で後方互換
  - 4.4 compat なら 4.6.2 editor でも開けるが、4.4 ユーザーも保護できる
- **波及**: `.claude/skills/godot-gdscript/patterns.md` の 4.4 表記を 4.4-4.6 に
  緩和 (setup-macbook decisions の予告同期を履行)

## 判断 7: NOTICE に Godot ランタイム言及を追記

- **判断日時**: 2026-04-18
- **追記**: "Godot runtime (not bundled, user-installed)" 節
- **理由**:
  - Godot MIT は NOTICE 強制不要だが、good hygiene として追記
  - user-installed であることを明示し bundled ではないことを示す
  - T08 の CSDG 帰属追記と同じ粒度で一貫性

## 判断 8: code-reviewer HIGH 1 件 + MEDIUM 3 件 + LOW 2 件に対応

- **判断日時**: 2026-04-18
- **対応内容**:
  1. **`WorldEnvironment` に Environment sub-resource** (HIGH):
     background_mode=1 (custom color) + ambient_light + sky なし。T17 で
     アセット追加時に精緻化
  2. **`DirectionalLight3D.shadow_enabled = true`** (MEDIUM #2):
     T17 の peripatos scene で影が必要になる
  3. **`GODOT_BIN` env var override** (MEDIUM #3): Linux / 非標準 Godot install 対応
  4. **boot test で stderr に `ERROR:` が無いこと** (MEDIUM #4): rc=0 だけでは
     見逃すケースを補強
  5. **`WorldManager.gd` の `##` doc comment を API/計画に分離** (MEDIUM #5):
     `##` は API ドキュメント、計画は通常コメントに降格
  6. **`Camera3D.current = true`** (LOW): 意図を明示
  7. **`scenes/zones/README.md` の命名記述を明確化** (LOW): tscn と
     Godot node は PascalCase、schemas.py Zone enum は snake_case、
     mapping は GDScript 側の `ZONE_MAP` で吸収

## 見送り (LOW 指摘、後続タスクで対応可)

- **icon.svg の 16px 表示**: 暫定アイコン、M4-M10 で正式ロゴ差し替え予定
- **`.gitignore` `*.import` パターン**: Godot 3.x 互換の念のため残す
- **その他の Godot API バージョン差分**: T16/T17 の実装時に露呈したら対応

## 関連する後続タスク

- **T16 godot-ws-client**: `$WebSocketClient` ノードに `WebSocketClient.gd` を
  attach し、`envelope_received(Dictionary)` signal を `WorldManager.gd` で
  受けて `$AgentManager` に dispatch
- **T17 godot-peripatos-scene**: `Peripatos.tscn` を `$ZoneManager` 配下に
  instance。Linden-Allee 3D メッシュと NavigationRegion3D を追加
- **T18 ui-dashboard-minimal**: Streamlit 側 (Godot 外) で別途構築
- **M4**: Blender から `.glb` export し `godot_project/assets/` に追加
- **M5**: 5 ゾーン (chashitsu/agora/garden) を scenes/zones/ に追加

## 検証履歴

- `uv run pytest tests/test_godot_project.py` — 全 3 件 pass (headless boot 含む)
- 実機確認: `/Applications/Godot.app/Contents/MacOS/Godot --path godot_project --headless --quit` が rc=0 で完了

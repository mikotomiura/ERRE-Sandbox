# T16 godot-ws-client — タスクリスト

採用設計 (v2) に基づく。各タスク **30 分以内** を目安に粒度分割。

## Step A/B/C ✓ (完了済)
- [x] implementation-workflow Skill Read
- [x] docs (architecture / development-guidelines / repository-structure) Read
- [x] requirement.md Read
- [x] file-finder で既存 Godot 資産と fixtures を調査
- [x] impact-analyzer で MainScene 変更影響を分析
- [x] design.md 初回案 (v1) 作成
- [x] /reimagine で v2 再生成
- [x] design-comparison.md で比較 → **v2 採用確定**

## Step D (本ステップ) ✓
- [x] tasklist.md を v2 設計に即して 30 分粒度で分解

## Step E: 実装

### E-1: Schema 同期ガード (TDD 先行)
- [ ] `tests/test_envelope_kind_sync.py` を新規作成
      (Python 側 7 kind 抽出 + EnvelopeRouter.gd regex parse + 集合一致 assert)
- [ ] 現時点で EnvelopeRouter.gd は未作成なので **`FileNotFoundError` で fail
      する状態を commit** (TDD 赤フェーズ)
- [ ] Python 側の 7 kind 抽出ロジックを先に単体検証
      (`get_args(ControlEnvelope)` ルートが Pydantic v2 + discriminated union で
      動くことを確認)

### E-2: Godot production scripts
- [ ] `godot_project/scripts/WebSocketClient.gd` を新規作成
      (patterns.md §1 テンプレ踏襲、**fixture コードなし**)
      - [ ] `WS_URL` / `RECONNECT_DELAY` 定数
      - [ ] `envelope_received(Dictionary)` / `connection_status_changed(bool)` signal
      - [ ] `_process()` で WebSocketPeer poll + 状態遷移
      - [ ] `_schedule_reconnect()` メソッド分離
- [ ] `godot_project/scripts/EnvelopeRouter.gd` を新規作成
      - [ ] 7 個の専用 signal 宣言
        (`handshake_received` / `agent_updated` / `speech_delivered` /
         `move_issued` / `animation_changed` / `world_ticked` / `error_reported`)
      - [ ] `_on_envelope_received(envelope: Dictionary)` で match 分岐
      - [ ] 未知 kind は `push_warning`、crash なし
- [ ] `godot_project/scripts/AgentManager.gd` を新規作成
      - [ ] `_ready()` で EnvelopeRouter の 4 signals
        (`agent_updated` / `speech_delivered` / `move_issued` / `animation_changed`)
        を connect
      - [ ] 各ハンドラは `print()` スタブ (T17 でアバター生成に置き換え)

### E-3: Godot dev scripts (fixture 隔離)
- [ ] `godot_project/scripts/dev/` ディレクトリ作成 + `README.md` 配置
      (GPL 分離ルールと同じく「dev 専用、production ビルド除外対象」を明記)
- [ ] `godot_project/scripts/dev/FixturePlayer.gd` を新規作成
      - [ ] `DEFAULT_PLAYLIST: PackedStringArray` に 7 ファイル名を定数宣言
      - [ ] `_ready()` で `OS.get_cmdline_user_args()` から `--fixture-dir=` 解析
      - [ ] `FileAccess.open()` で各 JSON を順次読み込み
      - [ ] `Timer` ノードで **0.5 秒間隔** に emit
      - [ ] 全 envelope 再生後 2 秒待機 → `get_tree().quit()`
- [ ] `godot_project/scenes/dev/` ディレクトリ作成 + `README.md` 配置
- [ ] `godot_project/scenes/dev/FixtureHarness.tscn` を新規作成
      - [ ] MainScene を instance
      - [ ] FixturePlayer ノードを子として add
      - [ ] MainScene 内の WebSocketClient を `set_process(false)` で無効化する
        セットアップスクリプトをどこに書くか検討 (FixtureHarness 専用の
        `FixtureHarness.gd` を作る or FixturePlayer の `_ready()` で find)

### E-4: MainScene.tscn 修正 (Godot エディタ経由)
- [ ] Godot エディタで `scenes/MainScene.tscn` を開く
- [ ] WebSocketClient ノードに `WebSocketClient.gd` を attach
- [ ] MainScene 直下に `EnvelopeRouter` ノード (Node) を追加し `EnvelopeRouter.gd`
      を attach (階層: WorldManager 配下 or 直下、patterns.md §2 と整合する位置)
- [ ] AgentManager ノードに `AgentManager.gd` を attach
- [ ] `$WebSocketClient.envelope_received` → `$EnvelopeRouter._on_envelope_received`
      の signal 配線をシーン内に記述
- [ ] Godot エディタで保存 → `.tscn` の `load_steps` / `ext_resource` が自動更新
      されたことを確認
- [ ] `git diff godot_project/scenes/MainScene.tscn` で手動編集ミスがないことを確認

### E-5: WorldManager.gd 修正
- [ ] `_ready()` に EnvelopeRouter の 2 signals (`world_ticked` / `error_reported`)
      を connect する行を追加
- [ ] `_on_world_ticked(wall_clock, tick)` / `_on_error_reported(code, detail)`
      ハンドラを追加 (T16 時点ではログ + DebugOverlay 更新)
- [ ] line 7-8 の T16 handoff コメントを「完了」に書き換え

### E-6: tests 拡張
- [ ] `tests/conftest.py` を作成 (or 既存に追記) し、`_resolve_godot()` を
      `tests/test_godot_project.py` から移動
- [ ] `tests/test_godot_project.py` を conftest 利用に書き換え
      + `test_required_project_files_exist` に新 5 ファイル
      (WebSocketClient / EnvelopeRouter / AgentManager / FixturePlayer /
       FixtureHarness.tscn) アサーション追加
- [ ] `tests/test_godot_ws_client.py` を新規作成
      - [ ] `_resolve_godot()` (conftest から import) で Godot 解決 or skip
      - [ ] `FixtureHarness.tscn` を `--fixture-dir=<abs>` 付きで headless 起動
      - [ ] stdout で 7 kind の signal 発火ログを順序確認
      - [ ] "Unknown kind" warning が 0 件
      - [ ] exit 0 + FixturePlayer 終了メッセージ

### E-7: tasklist 更新
- [ ] 実装完了タスクを順次チェック

## Step F: テストと検証
- [ ] `uv run pytest tests/test_envelope_kind_sync.py -v` が pass (赤→緑転換)
- [ ] `uv run pytest tests/test_godot_project.py -v` が pass (拡張後も通る)
- [ ] `uv run pytest tests/test_godot_ws_client.py -v` が pass (Godot 解決時)
      or skip (Godot 未解決時)
- [ ] `uv run pytest tests/` 全体が緑
- [ ] `uv run ruff check .` が通る
- [ ] `uv run ruff format --check .` が通る
- [ ] `uv run mypy src tests` が通る (test_envelope_kind_sync.py の型)

## Step G: code-reviewer
- [ ] `code-reviewer` サブエージェント起動
      (レビュー対象: GDScript 3 + dev 2 / tests 2 / tscn 1 / WorldManager diff)
- [ ] HIGH 指摘 → 必ず修正
- [ ] MEDIUM 指摘 → ユーザー確認
- [ ] LOW 指摘 → blockers.md に記録

## Step H: security-checker (外部入力 = WebSocket JSON)
- [ ] `security-checker` サブエージェント起動
      - JSON パースの安全性 (malformed / 深いネスト / 巨大メッセージ)
      - FileAccess の fixture パス注入 (path traversal)
      - WebSocket URL hardcode vs 環境変数
- [ ] CRITICAL/HIGH 指摘 → 必ず修正

## Step I: ドキュメント更新
- [ ] `docs/functional-design.md` 更新判断 (大幅変更なら追記、小さければ不要)
- [ ] `docs/glossary.md` 更新判断 (新用語 "EnvelopeRouter" / "FixtureHarness"
      を追加するか)
- [ ] `docs/architecture.md` 更新判断 (Godot 側スクリプト構造図の追加)
- [ ] `.steering/_setup-progress.md` を T16 完了で更新 (Phase 8 セクション)
- [ ] `.steering/20260418-implementation-plan/tasklist.md` の T16 を `[x]` に

## Step J: コミットと PR
- [ ] `git status` / `git diff` で変更確認
- [ ] 論理的まとまりでコミット分割を検討
      - C1: feat(godot): T16 — scripts (WebSocketClient/Router/AgentManager)
      - C2: feat(godot): T16 — fixture harness (FixturePlayer + FixtureHarness.tscn)
      - C3: test(godot): T16 — kind sync ガード + headless 回帰 + conftest 抽出
      - C4: chore(steering): T16 完了マーク + PR # 参照
        (または C1-C3 を 1 コミットに束ねる判断もあり、diff サイズで決める)
- [ ] `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` 付与
- [ ] `Refs: .steering/20260418-godot-ws-client/`
- [ ] `git push -u origin feature/godot-ws-client`
- [ ] `gh pr create` で PR 作成 (Conventional Commits 準拠のタイトル)

## 完了処理
- [ ] decisions.md の作成 (本タスクで採用した v2 設計 + 5 件以上の判断を記録)
- [ ] MASTER-PLAN.md tasklist の T16 を `[x]` に
- [ ] `/finish-task` で最終化

## ブロッカー候補 (発生時に blockers.md へ)
- Godot エディタが MainScene.tscn を Apple Silicon で開けない
- FixtureHarness.tscn のノード構造で WebSocketClient の無効化が安定しない
- `get_args(ControlEnvelope)` が discriminated union の Literal を取れない
- headless boot の `--quit-after` 秒数と FixturePlayer の再生時間 (0.5s × 7 + 2s
  = 5.5s) の整合

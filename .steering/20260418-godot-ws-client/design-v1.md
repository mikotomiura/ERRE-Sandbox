# T16 godot-ws-client — 設計 (v1 初回案)

> **⚠️ この v1 は `/reimagine` の破壊対象**。requirement.md 運用メモの承認通り、
> 初回案 (v1) を意図的に素直 / 凡庸に書いた上で、`/reimagine` でゼロから
> 再生成した v2 と比較し、採用案を確定する。

## 実装アプローチ

### 全体方針 (素直案)

- `godot_project/scripts/WebSocketClient.gd` **1 本**に以下を全部載せる:
  - WebSocketPeer による実接続
  - 自動再接続 (5 秒)
  - Developer fixture mode (環境変数で切替)
  - ControlEnvelope JSON パース
  - `kind` による dispatch (7 kind 分岐)
- `godot_project/scripts/AgentManager.gd` を新規作成。`envelope_received` を
  受けて `kind == "agent_update"` のみログ出力するスタブ (アバター生成は T17)。
- `WorldManager.gd` (既存) は `_ready()` で
  `$WebSocketClient.envelope_received.connect(_on_envelope_received)` を追加
  するのみ。既存 comment (line 7-8) を実行する形。
- MainScene.tscn は Godot エディタ経由で script を attach (`load_steps` 手動編集は避ける)。

### Fixture 再生モード

- 起動時に `OS.get_cmdline_user_args()` または環境変数 `ERRE_FIXTURE_DIR` を確認
- 設定されていれば fixture mode、未設定なら実 WebSocket mode
- Fixture mode:
  1. `FileAccess.open(fixture_dir + "/handshake.json")` から順次読み込み
  2. 固定順 `[handshake, agent_update, speech, move, animation, world_tick, error]`
  3. 各 envelope を **0.5 秒間隔** で `envelope_received` に emit
  4. 最後の envelope 後 2 秒経ったら自動終了 (`get_tree().quit()`)

### Kind dispatch

`WebSocketClient.gd` 内部で以下の match:

```gdscript
match envelope.get("kind", ""):
    "handshake": _handle_handshake(envelope)
    "agent_update": _handle_agent_update(envelope)
    "speech": _handle_speech(envelope)
    "move": _handle_move(envelope)
    "animation": _handle_animation(envelope)
    "world_tick": _handle_world_tick(envelope)
    "error": _handle_error(envelope)
    _: push_warning("Unknown kind: %s" % envelope.get("kind"))
```

各 `_handle_*` は `print("[WS] kind=... payload=...")` 相当のログ出力のみ
(T16 はルーティングまでで実処理は T17/M5 以降)。

## 変更対象

### 新規作成するファイル
- `godot_project/scripts/WebSocketClient.gd` (~150 行想定) — WebSocket + fixture + dispatch の全部入り
- `godot_project/scripts/AgentManager.gd` (~50 行) — envelope_received の受け口スタブ
- `tests/test_godot_ws_client.py` (~100 行) — Godot headless で fixture 再生を検証

### 修正するファイル
- `godot_project/scenes/MainScene.tscn` — WebSocketClient / AgentManager ノードに script attach (Godot エディタ経由、`load_steps` / `ext_resource` 正しく更新)
- `godot_project/scripts/WorldManager.gd` — `_ready()` にシグナル接続 1 行追加
- `tests/test_godot_project.py` — `test_required_project_files_exist` に新 2 ファイルのアサーション追加

### 削除するファイル
- なし

### 変更なし (参照のみ)
- `fixtures/control_envelope/*.json` (7 ファイル)
- `src/erre_sandbox/schemas.py` §7
- `.claude/skills/godot-gdscript/SKILL.md` / `patterns.md`

## 影響範囲

impact-analyzer 結果に基づく:

- **HIGH 局所**: MainScene.tscn の手動編集リスク → Godot エディタ経由必須
- **MEDIUM**: schemas.py ↔ GDScript kind の手動同期 (自動追従なし、今回は顕在化せず)
- **MEDIUM**: `fixtures/` が `res://` 外 → 絶対パスを `OS.get_cmdline_user_args()` で受け渡し
- **LOW**: tests/test_godot_project.py の既存テストは不破壊 (追加のみ)

## 既存パターンとの整合性

- **WorldManager.gd line 7-8 コメント** が T16 の道標。そのまま実装。
- **test_godot_project.py** の 3 層パターン (必須ファイル / Python 混入 /
  headless boot) を `test_godot_ws_client.py` で踏襲、`_resolve_godot()`
  ヘルパを再利用 (conftest.py への抽出検討)。
- **fixtures/control_envelope/README.md** line 52-71 の GDScript 例を
  `WebSocketClient.gd` の match 文テンプレートとして直接使用。
- **T08 test-schemas** の「3 層契約ガード」思想をクライアント側にも適用:
  - L1: WebSocketClient.gd の kind dispatch (boundary)
  - L2: fixture 再生の順序テスト (meta-invariant)
  - L3: schemas.py §7 の 7 kind と GDScript match の一致確認 (手動、将来自動化)

## テスト戦略

### Godot headless 回帰 (`tests/test_godot_ws_client.py`)

- T15 の `_resolve_godot()` を共通モジュール化 (conftest.py へ) して再利用
- 起動パターン: `godot --headless --quit-after N path/to/MainScene.tscn -- --fixture-dir=/abs/path`
- assertions:
  1. **exit 0** で終了する
  2. **stdout/stderr に 7 kind 全てのログ** が現れる (`[WS] kind=handshake` ... `[WS] kind=error`)
  3. **"Unknown kind" warning が 0 件**
  4. **fixture mode 終了メッセージ** が現れる

### 必須ファイル / Python 混入

- `test_godot_project.py` の既存 2 テストに WebSocketClient.gd と AgentManager.gd
  を追加 (網羅性維持)

### TDD 適用範囲

- GDScript 本体のロジック: **TDD 対象外** (描画・Godot ランタイム依存)
- fixture 再生のルーティング検証: **ヘッドレス統合テストで代替**
- テスト順序: まず `test_godot_ws_client.py` のスケルトンを書き (skip or xfail)、
  実装を進めながら assertion を有効化

## 関連する Skill

- `godot-gdscript` — SKILL.md 全体とくにルール 2/3、patterns.md §1/§4
- `error-handling` — WebSocket 再接続パターン (今回は GDScript だが思想は共通)
- `architecture-rules` — `godot_project/` に Python 不混入、`ui/` → `schemas.py` のみ依存 (今回 ui/ は触らない)
- `test-standards` — `tests/test_godot_ws_client.py` のフィクスチャ / skip 判断
- `git-workflow` — feat(godot): T16 ... + Refs: .steering/20260418-godot-ws-client/

## ロールバック計画

- T16 は T15 scaffold の上に新規ファイル追加が主体。問題時は以下で戻る:
  1. `git reset --hard origin/main` で T16 branch を破棄 (main は T15 完了状態)
  2. MainScene.tscn を誤編集した場合: `git checkout origin/main -- godot_project/scenes/MainScene.tscn`
  3. WorldManager.gd の signal 接続行を追加しなかったことにする場合: 該当 1 行削除で v1 scaffold 状態に戻る

## 初回案 (v1) の自覚的弱点

破壊と構築の材料として、v1 自身が持つ弱点を明示する。

| # | 弱点 | 深刻度 |
|---|---|---|
| V1-W1 | `WebSocketClient.gd` に WebSocket 接続・再接続・fixture 再生・dispatch を全部詰めており、**単一責任原則 (SRP) 違反**。ファイル 150 行が行き過ぎた肥大化の入り口になる | 中-高 |
| V1-W2 | Fixture 再生ロジックが本番 WebSocket クライアントに紛れ込み、テスト用コードが production path に残る。将来 `.pck` ビルドで fixture code が混入する | 中 |
| V1-W3 | `AgentManager.gd` がスタブに留まり、T17 以降で大幅書き直しが発生する可能性。境界を引かず始めると T17 で破壊的変更 | 中 |
| V1-W4 | 7 kind の handler を全部 WebSocketClient.gd の private メソッドにしているため、将来 schemas.py §7 に kind が増えた時の同期点が 1 箇所に集中。responsibility が混線 | 中 |
| V1-W5 | `EnvelopeRouter.gd` を作らない決定により requirement.md の記述と不整合。要件段階で提示したモジュール分割を設計段階で勝手に畳んでいる | 中 |
| V1-W6 | Fixture 再生の「0.5 秒間隔 / 固定順序」がハードコード。playlist 機構がなく、異なる scenario を試すには GDScript 自体を書き換え必要 | 低-中 |
| V1-W7 | `OS.get_cmdline_user_args()` と環境変数の二重サポートが実装を複雑化。どちらか一方でよい | 低 |

**この v1 を意図的に破壊して v2 を再生成し、並べて比較して採用案を決める。**

## 次のステップ

1. `/reimagine` を起動 → 本 design.md を `design-v1.md` に退避
2. ゼロから再生成した v2 を新 design.md に書く
3. `design-comparison.md` で v1/v2 を並置、採用案 (v2 or ハイブリッド) を決定
4. 採用版 design.md に基づき Step D (tasklist) に進む

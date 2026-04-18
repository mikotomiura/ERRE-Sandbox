# ブロッカー・懸案事項 — T16 godot-ws-client

本タスクの実装中に解決できず、後続で対応すべき LOW 懸案を記録する。
CRITICAL / HIGH / MEDIUM は全て解消済み (`decisions.md` 判断 4/6/8/10 参照)。

## LOW (後続タスクで対応)

### L1: `WebSocketClient.gd` 初回接続失敗時のサイレント reconnect サイクル

- **起点**: code-reviewer LOW #6
- **内容**: `ws://g-gear.local:8000/stream` が最初から到達不能な場合、初回
  `push_warning` 後は 5 秒ごとに `_connect_to_server()` が呼ばれるが、
  ログが出ない (`_connected` が true になってから false に遷移するパスのみ
  ログを出すため)
- **対処候補**: 5 サイクルごとに 1 度 `push_warning("[WS] still retrying after
  %d attempts" % _retry_count)` を出す
- **対応時期**: T14 gateway-fastapi-ws と統合する T19 E2E 時 (実 gateway 接続
  の観測性強化)

### L2: `res://../fixtures/control_envelope` のパス traversal にインラインコメント

- **起点**: code-reviewer LOW #8
- **内容**: `FixturePlayer.gd FALLBACK_CANDIDATES` 内の `res://..` は
  `godot_project/` から一階層上 = repo root を指す。Godot では稀な使い方で
  後続開発者が混乱する可能性
- **対処**: 定数直前に 1 行コメント `# repo_root/fixtures/ via ../ since
  res:// is rooted at godot_project/` を追加
- **対応時期**: 次回 T16 系 PR (今回は範囲外)

### L3: `EnvelopeRouter.gd` の agent_id 取り出しに関するコメント

- **起点**: code-reviewer LOW #10
- **内容**: `agent_update` のみ `agent_id` が `envelope.agent_state.agent_id`
  にネストされている (他 kind は envelope top-level)。このコードの非対称性に
  ついて in-line コメントが欲しい
- **対処**: `EnvelopeRouter.gd` の `"agent_update":` ブロックに
  `# agent_id lives inside agent_state (AgentUpdateMsg schema §7)` を追加
- **対応時期**: 次回 T16 系 PR

### L4: WS_URL の外部化 (環境変数 / `@export`)

- **起点**: security-checker MEDIUM #3
- **内容**: `const WS_URL: String = "ws://g-gear.local:8000/stream"` は
  マルチ環境対応 (staging / CI / 複数 G-GEAR) で不便
- **対応時期**: M5 以降のマルチ環境対応、または T19 E2E で gateway を外す時

### L5: MainScene.tscn を Godot エディタで再保存して canonical 化

- **起点**: decisions.md 判断 9
- **内容**: `load_steps=6` / ext_resource ID (`1_worldmgr` 等) を手動で決めた
  ので、Godot エディタで開いて保存した時に canonical 化される可能性
- **対応**: エディタで開く → 保存 → diff 整形コミット
- **対応時期**: Godot エディタ利用可能な次セッション

## 解決済み (参考)

- HIGH (code-reviewer #1): WorldManager `push_error` → `push_warning` + `print`
- HIGH (security-checker #1): WebSocketClient `_consume_packets` に
  `MAX_FRAME_BYTES` ガード追加
- HIGH (実装中): `class_name EnvelopeRouter` cross-ref 解決失敗
  → `Node` + `has_signal` duck typing
- MEDIUM (code-reviewer #2): FixturePlayer に `MAX_FIXTURE_BYTES` ガード
- MEDIUM (code-reviewer #3): kind_sync regex を on_envelope_received 関数
  本体にスコープ限定
- MEDIUM (security-checker #2): malformed frame ログに `.c_escape()` 適用

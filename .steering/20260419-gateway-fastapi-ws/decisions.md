# 設計判断の記録 — T14 gateway-fastapi-ws

## D1: 関数 = 状態機械 (Session クラス不在)

**判断**: WS ハンドラ関数 `ws_observe` 自体をセッション状態機械とする。
`SessionPhase` enum を runtime の値として保持せず、3 フェーズ (AWAITING/ACTIVE/CLOSING) は
try/except 境界と `return` による早期終了で表現する。

**根拠**:
- **二重表現リスク排除**: v1 案の `Session.phase` 属性と try/except が同じ情報を 2 箇所で
  持つことになる。情報が 1 箇所 (制御フロー) に集約される方が同期ズレを起こさない
- **MVP 責務に見合う**: Session 固有の拡張 state (per-client metric / auth / subscription
  filter) は M4-M7 以降で必要になる。MVP 段階でクラス化はオーバーキル
- **コード量 30% 削減**: v1 の ~1200 行 → v2 の ~850 行。Session クラス setup/teardown と
  session.py/test_session.py の分離が消える

**参照**: `.steering/20260419-gateway-fastapi-ws/design-comparison.md`

## D2: `asyncio.timeout` ネストで handshake + idle を統一

**判断**: Python 3.11+ native の `asyncio.timeout(sec)` コンテキストマネージャを
handshake 待ち受けと idle 判定の両方で使う。別 watchdog タスク + `time.monotonic` polling は
採用しない。

**根拠**:
- **タイマー管理を async 側に委譲**: receive ごとに `async with asyncio.timeout(IDLE)` を
  ネストすれば、タイマーのライフサイクル (作成・reset・破棄) がすべて Python async
  ランタイムに任せられる。手動 Event / monotonic 差分は不要
- **タスク数削減**: 1 接続あたり watchdog タスクを持たないため、N 接続時のメモリ/CPU が
  ほぼ線形で増えない
- **`asyncio.wait_for` より native**: `wait_for` は Task を内部生成するが、`timeout()`
  コンテキストはスコープ付き cancel scope。Python 3.11 で追加された推奨形

## D3: 単一 broadcaster タスク + Registry fan-out

**判断**: 1 個の `_broadcaster` タスクが lifespan スコープで動き、
`WorldRuntime.recv_envelope()` を await して、`Registry.fan_out()` で全 session queue に
`put_nowait` する。`WorldRuntime` 側に複数 subscriber API を追加しない。

**根拠**:
- **T13 の `recv_envelope()` 契約をそのまま消費**: T14 は唯一の consumer となり、
  `WorldRuntime` の envelope 生成源インタフェースを変更せずに済む
- **fan-out 責務を gateway に閉じる**: envelope をどう配る (broadcast / filter / replay) かは
  gateway の責務であり、`WorldRuntime` は知る必要がない
- **将来の拡張余地**: `agent_id` filter / `since_tick` replay を追加する時も `Registry` と
  `_broadcaster` の内部変更で済む

## D4: Per-client bounded queue + oldest-drop + ErrorMsg warning

**判断**: 各 session は `asyncio.Queue(maxsize=MAX_ENVELOPE_BACKLOG=256)` を持つ。
満杯時は **oldest を 2 件 drop → `ErrorMsg(backlog_overflow)` push → 新 env push** の
3 ステップ。

**根拠**:
- **メッセージ最新性優先**: Godot 側で stale な envelope を重ねて表示するより、最新状態に
  追いつかせる方が可視化として有益
- **警告の観測性**: client 側が overflow を静かに drop されると診断不可能。
  ErrorMsg を投入することで Godot 側の log で気づける
- **2 件 drop が必要な理由**: 1 件だけだと、warning + env の 2 件を push する余地が
  できない (maxsize=2 のテストケースで検出済み)

## D5: Registry の `maxsize=0` ガード (code review HIGH #2 対応)

**判断**: `Registry.fan_out` で `queue.maxsize > 0 and queue.full()` のガードを入れる。
unbounded queue では drop ロジックをスキップし素直に `put_nowait(env)` する。

**根拠**:
- **初期実装のバグ**: `maxsize=0` のとき `qsize() > maxsize - 2` が `qsize() > 0` となり、
  unbounded queue のあらゆる要素を drain しつつ warning + env のみ残す挙動になる
- **将来の debug 用途**: `_NullRuntime` や将来の試験実装で unbounded queue を渡す可能性を
  想定した defensive

## D6: `internal_error` detail を固定文字列に (code review + security HIGH #1 対応)

**判断**: `internal_error` ErrorMsg の `detail` に exception 型名/メッセージを含めず、
固定文字列 `"internal server error"` のみとする。詳細は `logger.exception` で server
ログに残す。

**根拠**:
- **情報漏洩防止**: 内部クラス名・ファイルパス・DB スキーマが client (Godot / 将来の
  外部 peer) に流れるのを防ぐ
- **M10 外部公開への備え**: 今 LAN 前提でも、M10 でインターネット公開する際の修正を
  先回りして閉じておく (後戻りコスト低)
- **observability は server 側**: `logger.exception` が traceback を完全記録するので
  開発者は失うものがない

## D7: 64KB frame upper bound with 2-stage size check

**判断**: `_parse_envelope` が `_MAX_RAW_FRAME_BYTES=64KB` の上限を課す。
**1 段階目は `len(raw)` (codepoint 数)、2 段階目は Pydantic validation** の順。
security-checker の指摘を受けて `raw.encode("utf-8")` を毎回走らせる v1 実装を
粗いチェック (codepoint >= UTF-8 bytes は安全側) に変更。

**根拠**:
- **DoS 緩和**: 悪意ある 64KB 弱フレームの高頻度攻撃で encode コピーによる GC 圧力を回避
- **UTF-8 エンコード不変性**: codepoint 数 N に対して UTF-8 bytes は N〜4N。
  `len(raw) > 64KB` なら必ず 64KB 超、逆は保証されないが実用上の攻撃面は十分小さい
- **コストシンプル**: O(1) の `len()` でほぼ全フレームを通過させ、Pydantic が sanity check

## D8: `_send_loop` で OSError / RuntimeError も `_GracefulCloseError` に包む
(code review MEDIUM 対応)

**判断**: `_send_loop` の except 節に `(OSError, RuntimeError)` を追加し、
Starlette が surfaces する下位例外を `_GracefulCloseError` で包んで TaskGroup の
`except*` にクリーンに合流させる。

**根拠**:
- **opaque ExceptionGroup 回避**: `WebSocketDisconnect` 以外の "WebSocket is not
  connected" などを握りこぼすと ExceptionGroup が上位で raise され、ログが読みづらい
- **観測性**: `logger.debug` に送信失敗理由を残す
- **セッション終了シグナル統一**: recv_loop / send_loop のどちらから exit しても
  `_GracefulCloseError` で TaskGroup が畳まれる一貫性

## D9: Debug snapshot + 0.0.0.0 default bind (docstring と `# noqa: S104` で対処)

**判断**: `Registry.debug_snapshot()` は v1 → v2 への補完として追加 (inspectability 確保、
v1 の session クラス化を不要にする)。`--host 0.0.0.0` デフォルトは `# noqa: S104` 付き、
docs で LAN 前提を明記 (認証欠如と同等の扱い)。

**根拠**:
- **debug_snapshot**: `/health` の `active_sessions` に加えて、queue 深さや session_id 派生
  ハッシュを覗ける軽量インタフェース。デバッグでクラス化の代替
- **0.0.0.0**: Godot (MacBook) が LAN 経由 `g-gear.local:8000` で繋ぐ前提。
  security-checker でも LAN-only MVP として許容判定

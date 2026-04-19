# タスクリスト — T14 gateway-fastapi-ws

v2 採用 (関数即セッション + `asyncio.timeout` ネスト + 単一 gateway.py)。
各タスクは 30 分以内粒度。

## 準備

- [x] docs 4 種読了 / requirement.md 記入 / file-finder + impact-analyzer 実行
- [x] /reimagine で v1 退避 → v2 生成 → 比較 → v2 採用確定
- [x] PR #23 (Mac の integration/ scaffold) を main にマージ済み

## 実装フェーズ 1: 骨格と Registry

- [x] `feature/gateway-fastapi-ws` ブランチ作成
- [x] `src/erre_sandbox/integration/gateway.py` 骨格
      (imports + `_ADAPTER = TypeAdapter(ControlEnvelope)` + `_GracefulClose`)
- [x] `Registry` クラス: `add(id, queue)` / `remove(id)` / `fan_out(env)` /
      `debug_snapshot()` / `__len__`
- [x] `tests/test_integration/test_gateway.py` 骨格 + Registry 単体テスト 5 件

## 実装フェーズ 2: 純粋ヘルパ

- [x] `_make_server_handshake(runtime) -> HandshakeMsg`
      (peer="g-gear", capabilities=7 種, schema_version)
- [x] `_make_error(tick, code, detail) -> ErrorMsg`
- [x] `_parse_envelope(raw: str) -> ControlEnvelope | None`
      (TypeAdapter + ValidationError → None、DoS ガードで長さ制限)
- [x] 対応テスト: handshake 形 / error 形 / parse 正常・失敗・超過長

## 実装フェーズ 3: WS ハンドラ (コア)

- [x] `_send(ws, env)` / `_send_error(ws, code, detail)` I/O 関数
- [x] `_recv_loop(ws, on_invalid)` — `asyncio.timeout(IDLE_DISCONNECT_S)` ネスト、
      invalid → warning + 継続、timeout → `_GracefulClose` via ErrorMsg
- [x] `_send_loop(ws, queue)` — queue から pop して `ws.send_text(model_dump_json)`
- [x] `ws_observe(ws)` エンドポイント:
  - Phase 1 AWAITING: accept (header 付) → server handshake 送信 →
    `asyncio.timeout(HANDSHAKE_TIMEOUT_S)` で client handshake 受信 →
    schema 判定 → (失敗時 ErrorMsg)
  - Phase 2 ACTIVE: per-client queue 作成 → registry.add → TaskGroup で
    recv_loop + send_loop 並列 → except\* `_GracefulClose` で正常終了 →
    finally registry.remove
  - トップレベル except で `WebSocketDisconnect` / `Exception` → ErrorMsg("internal_error")
  - finally で `ws.close()` を try/except で安全に

## 実装フェーズ 4: アプリと lifespan

- [x] `_broadcaster(app)` — `runtime.recv_envelope()` → `registry.fan_out`
- [x] `_lifespan(app)` — broadcaster task を作成・cancel/await
- [x] `_health(app) -> dict` — `{schema_version, status, active_sessions}`
- [x] `_NullRuntime` — `recv_envelope` が無限 await する stub (テストデフォルト用)
- [x] `make_app(runtime=None) -> FastAPI` factory
- [x] `__main__` ブロック: argparse + `uvicorn.run(..., factory=True)`

## 実装フェーズ 5: 公開 API と conftest

- [x] `src/erre_sandbox/integration/__init__.py` に `Registry` / `make_app` を
      追加 export (既存 __all__ は変更せず末尾に追記)
- [x] `tests/test_integration/conftest.py` に以下を追加 (既存は触らない):
  - `mock_runtime()` fixture — `asyncio.Queue` ベースの MockRuntime
  - `app(mock_runtime)` fixture — `make_app(runtime=mock_runtime)`
  - `client(app)` fixture — `fastapi.testclient.TestClient` with コンテキスト
  - `fast_timeouts(monkeypatch)` — `protocol.HANDSHAKE_TIMEOUT_S=0.2`,
    `IDLE_DISCONNECT_S=1.0`, `MAX_ENVELOPE_BACKLOG=4` を monkeypatch

## 実装フェーズ 6: 統合テスト (TestClient 経由)

- [x] `GET /health` → 200 + schema_version/status/active
- [x] WS 接続 → server HandshakeMsg 受信
- [x] handshake 成立後、`mock_runtime.put(env)` が client に forward される
- [x] 複数 client (2 本) 同時接続 → fan-out
- [x] client HandshakeMsg 未送信 → fast_timeouts で handshake_timeout
- [x] client HandshakeMsg.schema_version が違う → schema_mismatch + close
- [x] client が invalid JSON → invalid_envelope + 接続維持
- [x] fast_timeouts 下で idle > 1s → idle_disconnect + close
- [x] backlog overflow: mock_runtime に envelope を連続 put + client 受信遅延 →
      backlog_overflow warning

## 検証フェーズ

- [x] `uv run pytest tests/test_integration/test_gateway.py -v`
- [x] `uv run pytest` 全緑 (既存 274 passed + T14 追加、skeleton skip は据え置き)
- [x] `uv run ruff check src/erre_sandbox/integration tests/test_integration`
- [x] `uv run ruff format --check src/erre_sandbox/integration tests/test_integration`
- [x] `uv run mypy --strict src/erre_sandbox/integration`
- [x] `integration/gateway` は `ui/` を import していないこと grep 確認

## レビュー

- [x] code-reviewer サブエージェントで差分レビュー
- [x] HIGH 指摘対応
- [x] security-checker サブエージェント (外部入力を扱うので必須):
      DoS / injection / logging / 認証欠如の妥当性 / WS close の leak

## ドキュメント

- [x] docs/architecture.md §1 Gateway の記述が実装と一致することを確認
      (差分があれば修正)
- [x] docs/functional-design.md §2 機能 1d Express の WS 部分に T14 完了を反映
      (1-2 行追記で可)
- [x] docs/glossary.md の追加不要

## 完了処理

- [x] `.steering/_setup-progress.md` に T14 エントリ追加
- [x] `decisions.md` 作成 (v2 採用 + Registry.debug_snapshot 追加 +
      asyncio.timeout ネスト選択 + broadcaster pattern)
- [x] tasklist 全 ✅
- [x] Conventional Commit でコミット (`feat(integration): T14 ...`)
- [x] push + gh pr create

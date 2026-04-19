# 設計 v2 — 関数即セッション + `asyncio.timeout` ネスト + 単一 gateway.py

> **ステータス**: 再生成案 (v2)。v1 は `design-v1.md` に退避済み。
> `design-comparison.md` で比較後、採用案を確定する。

## 1. 実装アプローチ

**発想の転換**: "Session" は**クラスではなく、WS ハンドラ関数そのもの** にする。
セッション状態機械の 3 フェーズ (AWAITING_HANDSHAKE → ACTIVE → CLOSING) は、
関数の**線形な制御フロー**に埋め込み、try/except 境界で自然に表現する。
`Session` クラスを持たないので `session.py` も作らない。

### 1.1 WS ハンドラ = セッション

```python
@app.websocket("/ws/observe")
async def ws_observe(ws: WebSocket) -> None:
    runtime: WorldRuntime = ws.app.state.runtime
    registry: Registry = ws.app.state.registry
    session_id = secrets.token_hex(8)

    await ws.accept(headers=[
        (SCHEMA_VERSION_HEADER.lower().encode(), SCHEMA_VERSION.encode()),
    ])

    try:
        # ---- Phase 1: AWAITING_HANDSHAKE -----------------------------
        await _send(ws, _make_server_handshake(runtime))
        try:
            async with asyncio.timeout(HANDSHAKE_TIMEOUT_S):
                raw = await ws.receive_text()
        except TimeoutError:
            await _send_error(ws, "handshake_timeout", "5s exceeded")
            return
        client_hs = _parse_or_none(raw)
        if not isinstance(client_hs, HandshakeMsg):
            await _send_error(ws, "invalid_envelope", "expected HandshakeMsg")
            return
        if client_hs.schema_version != SCHEMA_VERSION:
            await _send_error(ws, "schema_mismatch", client_hs.schema_version)
            return

        # ---- Phase 2: ACTIVE -----------------------------------------
        out_queue: asyncio.Queue[ControlEnvelope] = asyncio.Queue(
            maxsize=MAX_ENVELOPE_BACKLOG,
        )
        registry.add(session_id, out_queue)
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(_send_loop(ws, out_queue), name="send")
                tg.create_task(_recv_loop(ws, runtime_current_tick=runtime),
                               name="recv")
        except* _GracefulClose:
            pass  # any loop voluntarily ended → normal close
        finally:
            registry.remove(session_id)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception("session %s crashed", session_id)
        try:
            await _send_error(ws, "internal_error", str(exc))
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
```

### 1.2 なぜ Session クラスを持たないか

- **状態 = ローカル変数**: `phase` の明示 enum は要らない。try/except の位置が
  フェーズ境界、`return` で CLOSING に遷移、関数終了で破棄される
- **テストしやすい**: 関数 1 つに対する pytest。クラスの setup/teardown が消える
- **読みやすい**: 上から下に読めば session のライフサイクル全てが分かる
- **依存注入は `app.state` 経由**: `runtime` / `registry` は FastAPI が提供する
  `ws.app.state` から取れる (テストでは `make_app(runtime=mock)` factory で差し替え)

### 1.3 Idle disconnect は watchdog タスクを作らない

v1 が採用しそうな「別タスクで監視」をやめて、**`asyncio.timeout(IDLE_DISCONNECT_S)`
を `ws.receive_text()` ごとにネスト**する。これで:

- タイマーのライフサイクルは receive ごとに自動再起動 (手動 reset 不要)
- タスク数が増えないのでメモリ軽量
- `TimeoutError` を catch する場所が明確 (recv_loop 一箇所)

```python
async def _recv_loop(ws, runtime):
    while True:
        try:
            async with asyncio.timeout(IDLE_DISCONNECT_S):
                raw = await ws.receive_text()
        except TimeoutError:
            await _send_error(ws, "idle_disconnect", f"{IDLE_DISCONNECT_S}s")
            raise _GracefulClose
        env = _parse_or_none(raw)
        if env is None:
            await _send_error(ws, "invalid_envelope", "parse failed")
            # do NOT close — spec says "one-shot warning" (contract §3)
            continue
        # M2 では client → server の pub は許容しないが、無視して継続
```

### 1.4 Fan-out は broadcaster タスク 1 つだけ

アプリの lifespan で、1 つの `asyncio.Task` が `runtime.recv_envelope()` を
await して、registry の全 session queue に `put_nowait` する:

```python
async def _broadcaster(app: FastAPI) -> None:
    runtime = app.state.runtime
    registry = app.state.registry
    while True:
        env = await runtime.recv_envelope()
        registry.fan_out(env)  # sync iteration with oldest-drop per queue
```

`Registry.fan_out(env)` は同期メソッドで、queue が満杯なら **oldest 1 件 drop +
ErrorMsg("backlog_overflow") 1 件 enqueue + env enqueue** の 3 手順。

### 1.5 Registry は `dict[str, asyncio.Queue]` の薄いラッパ

クラスを作るが、state 機械は持たせない。責務は:

1. session_id → queue のマッピング保持
2. `fan_out(env)` 同期呼び出し
3. `iter_active()` でデバッグ用 snapshot
4. `len()` で `/health` の `active_sessions` を返す

### 1.6 エントリーポイント

```python
def make_app(runtime: WorldRuntime | None = None) -> FastAPI:
    app = FastAPI(lifespan=_lifespan)
    app.state.runtime = runtime or _null_runtime()
    app.state.registry = Registry()
    app.add_api_route("/health", _health, methods=["GET"])
    app.add_api_websocket_route("/ws/observe", ws_observe)
    return app

if __name__ == "__main__":
    import argparse, uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(
        "erre_sandbox.integration.gateway:make_app",
        factory=True, host=args.host, port=args.port,
    )
```

## 2. モジュール構成

```
src/erre_sandbox/integration/
├── __init__.py     # make_app / Registry / SCHEMA_VERSION を追加 re-export
├── protocol.py     # 既存 (Mac PR #23)
├── scenarios.py    # 既存
├── metrics.py      # 既存
├── acceptance.py   # 既存
└── gateway.py      # 新規 (~430 行) — すべてここに集約
                    #   _make_server_handshake / _send / _send_error /
                    #   _parse_or_none / _recv_loop / _send_loop /
                    #   _broadcaster / _lifespan / ws_observe /
                    #   _health / Registry / make_app / _NullRuntime /
                    #   _GracefulClose / __main__
```

`session.py` は**作らない**。ハンドラ関数 `ws_observe` が session そのもの。

## 3. 変更対象

### 新規作成 (3 ファイル)

| ファイル | 想定行数 |
|---|---|
| `src/erre_sandbox/integration/gateway.py` | ~430 |
| `tests/test_integration/test_gateway.py` | ~420 |
| (合計) | ~850 |

v1 の `session.py` + `test_session.py` 分の ~420 行が消える。

### 修正 (3 ファイル)

| ファイル | 内容 |
|---|---|
| `src/erre_sandbox/integration/__init__.py` | `Registry` / `make_app` を export |
| `tests/test_integration/conftest.py` | `mock_runtime` / `app` / `client` / `fast_timeouts` fixture |
| `.steering/_setup-progress.md` | T14 エントリ追加 |

### 削除
なし。

## 4. 影響範囲

- `integration/gateway.py` のみ追加、`__init__.py` 末尾 2 シンボル追加
- `test_contract_snapshot.py` は既存 `__all__` を削除・改名しない限り無傷
- `WorldRuntime._envelopes` は unbounded のまま (TODO コメント維持)。
  本番稼働時の server-side 上限は別タスクで対応 (slow consumer 側の問題は
  per-client 256 件で吸収済みなので MVP 範囲で安全)
- 既存 T19 skeleton テストは一切触らない (skip のまま)

## 5. 既存パターンとの整合性

| パターン | 参照 | v2 での適用 |
|---|---|---|
| ClassVar DEFAULT_*  + kw-only DI | `world/tick.py:179` `WorldRuntime` | `Registry` / `make_app(runtime=...)` |
| TypeAdapter(ControlEnvelope) で parse | `tests/test_schemas.py:122` | module-level `_ADAPTER = TypeAdapter(ControlEnvelope)` |
| pure function + I/O 関数分離 | `cognition/state.py` vs `cycle.py` | `_parse_or_none` (pure) vs `_send` (I/O) |
| asyncio.TaskGroup | `world/tick.py` で未採用 (v2 で初) | ACTIVE フェーズの recv/send 並列 |
| asyncio.timeout (3.11+) | (プロジェクト内初出) | handshake / idle の両方で使用 |
| tests ミラー構造 | `tests/test_world/` | `tests/test_integration/test_gateway.py` (1 ファイルで統合) |

## 6. テスト戦略

### 6.1 `test_gateway.py` (~420 行)

**2 層テスト構造**:

**層 A: 関数単体** (TestClient 不使用、mock WebSocket、高速):

- `_parse_or_none` — valid/invalid JSON、discriminator 不一致
- `Registry.fan_out` — 満杯時に oldest drop + ErrorMsg append
- `_recv_loop` (mock ws) — invalid envelope → warning + 継続
- `_send_loop` (mock ws) — queue から順次送信、QueueShutdown で return
- `_make_server_handshake` — peer="g-gear", capabilities=7 種, schema_version

**層 B: FastAPI TestClient による統合** (6-8 件、遅めだが end-to-end):

- `GET /health` → 200 + JSON
- WS 接続 → server HandshakeMsg → client HandshakeMsg → envelope が配信される
- client が HandshakeMsg を送らない → (timeout 短縮 fixture で) ErrorMsg("handshake_timeout")
- schema_version 不一致 → ErrorMsg("schema_mismatch") + close
- client が invalid JSON → ErrorMsg("invalid_envelope") + 接続維持
- 60s 無通信 → (idle 短縮 fixture で) ErrorMsg("idle_disconnect") + close
- 2 client 同時接続 → 両 client が同じ envelope を受信
- backlog overflow → ErrorMsg("backlog_overflow") + 接続維持 (queue サイズ短縮 fixture)

### 6.2 conftest.py

```python
@pytest.fixture
def mock_runtime() -> MockRuntime:
    """recv_envelope を test 側から制御できる最小実装。"""

@pytest.fixture
def app(mock_runtime) -> FastAPI:
    return make_app(runtime=mock_runtime)

@pytest.fixture
def client(app) -> TestClient:
    with TestClient(app) as c:
        yield c

@pytest.fixture
def fast_timeouts(monkeypatch) -> None:
    """HANDSHAKE_TIMEOUT_S を 0.2s、IDLE_DISCONNECT_S を 1.0s、
    MAX_ENVELOPE_BACKLOG を 4 に短縮。gateway.py 内で定数を都度参照している
    前提 (module-level import で束縛しない実装を v2 の制約とする)。"""
```

`MockRuntime` は `asyncio.Queue` を持ち、`recv_envelope()` は `get()`、
テストは `await mock.put(env)` で envelope を注入する。

### 6.3 回帰確認

- baseline: 274 passed / 34 skipped
- 期待: +20-25 件、skip 据え置き

## 7. ロールバック計画

- 単一 `gateway.py` + conftest 拡張のみ。`git revert` 1 コミットで復元
- Fan-out 方式は `_broadcaster` 差し替え 1 箇所
- Timeout 値は protocol.py 定数変更のみ

## 8. 関連する Skill

- `error-handling` — asyncio.timeout / TaskGroup / WS close (primary)
- `python-standards` — FastAPI / asyncio 3.11+
- `architecture-rules` — integration/gateway.py → world 依存許容
- `test-standards` — pytest-asyncio, TestClient, mock_runtime

## 9. v2 の差別化ポイント (v1 比)

| 観点 | v1 | v2 |
|---|---|---|
| Session 実装 | `Session` クラス + 3 内部タスク | **関数 `ws_observe` そのもの**、state = ローカル変数 |
| ファイル分離 | gateway.py + session.py | **gateway.py のみ** |
| Idle 監視 | 別 watchdog タスク + `time.monotonic` 差分 | `asyncio.timeout(IDLE)` を receive_text ごとにネスト |
| Handshake timeout | `asyncio.wait_for` | `asyncio.timeout` コンテキスト |
| テスト構造 | test_session + test_gateway 分離 | 関数単体 + TestClient 統合の 2 層を 1 ファイルに |
| 想定 LOC | ~1200 | ~850 |
| state 機械の表現 | SessionPhase enum を Session インスタンスに保持 | **try/except の境界が暗黙の状態機械** (enum は protocol.py のまま、gateway.py では使用しない) |

## 設計判断の履歴

- 初回案 (`design-v1.md`) と再生成案 (本ファイル = v2) を `design-comparison.md` で比較
- 採用: **v2**
- 根拠:
  1. **関数 = 状態機械の表現力**: `ws_observe` を上から下に読めば 3 フェーズ全 path が
     追える。`SessionPhase` を値として持つ必要がなく、二重表現リスクがない
  2. **`asyncio.timeout` 統一**: handshake と idle の両方を native コンテキスト
     マネージャで書けるため、watchdog タスク + `time.monotonic` polling を排除
  3. **30% コード量削減**: ~1200 → ~850 行。Session クラスと session.py 分離の
     オーバヘッドが消える
  4. **MVP 範囲に見合った責務**: Session 単位で持ちたい拡張 state (auth / metric /
     subscription filter) は M4-M7 以降で現れる。v2 から v1 方向への将来リファクタは
     可能、早期最適化を回避
  5. **Python 3.11 ネイティブ機能活用**: T13 の asyncio.TaskGroup 採用に続き、
     `asyncio.timeout` を採用することでプロジェクト全体の async 方針に整合
- v1 の長所の補完:
  - **inspectability** は `Registry.debug_snapshot() -> list[dict]` で確保 (~20 行)
  - **拡張容易性** は将来必要になった時点で Session クラス化する余地を残す
  - **ハンドラ関数のネスト深さ** はフェーズごとのコメントマーカーと早期 `return` で管理
- `fast_timeouts` fixture は `monkeypatch.setattr(protocol, "HANDSHAKE_TIMEOUT_S", 0.2)` で
  実装する制約を課す (gateway.py 内では `from . import protocol` して
  `protocol.HANDSHAKE_TIMEOUT_S` 参照、定数を再束縛しない)

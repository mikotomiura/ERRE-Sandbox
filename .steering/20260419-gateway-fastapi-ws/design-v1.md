# 設計 v1 — FastAPI TestClient + 単一 broadcaster Task + per-Session Class

> **ステータス**: 初回案 (v1)。`/reimagine` で破棄・再生成して v2 と比較予定。
> 本ファイルは `/reimagine` 実行時に `design-v1.md` へ退避される。

## 1. 実装アプローチ

**方針**: FastAPI + `starlette.websockets.WebSocket` を採用し、Session を 1 つの
クラスに閉じ込める。fan-out は単一の「broadcaster タスク」が
`WorldRuntime.recv_envelope()` を await して、接続中の全 session に配信する。

### 1.1 全体構造

```
┌─ Gateway FastAPI app ────────────────────────────────────┐
│                                                            │
│  GET /health  → 200 {schema_version, status, active}      │
│  GET  /ws/observe (WS upgrade)                            │
│         │                                                  │
│         ▼                                                  │
│   Session(ws, runtime) ──── registry.add(self)             │
│         │                                                  │
│         └── asyncio.TaskGroup:                             │
│             ├─ _await_client_handshake   (timeout 5s)      │
│             ├─ _recv_loop                (client → server) │
│             └─ _send_loop                (queue → ws.send) │
│                                                            │
│  Lifespan background task:                                 │
│    broadcaster() — pull from WorldRuntime + fan-out        │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### 1.2 Session クラス

```python
class Session:
    DEFAULT_QUEUE_SIZE: ClassVar[int] = MAX_ENVELOPE_BACKLOG  # 256

    def __init__(self, ws: WebSocket, session_id: str) -> None:
        self.ws = ws
        self.id = session_id
        self.phase = SessionPhase.AWAITING_HANDSHAKE
        self.queue: asyncio.Queue[ControlEnvelope] = asyncio.Queue(
            maxsize=self.DEFAULT_QUEUE_SIZE,
        )
        self._last_recv_at: float = time.monotonic()
        self._closing = asyncio.Event()

    async def run(self) -> None:
        await self.ws.accept(headers=[
            (SCHEMA_VERSION_HEADER.encode(), SCHEMA_VERSION.encode()),
        ])
        await self._send_server_handshake()
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._await_client_handshake(), name="hs")
                # recv / send loops spawned once ACTIVE
        except* Exception as eg:
            logger.exception("session %s crashed: %s", self.id, eg)
        finally:
            self.phase = SessionPhase.CLOSING
            await self._safe_close()

    def enqueue(self, env: ControlEnvelope) -> None:
        """Invoked by broadcaster. If queue is full, drop oldest + send warning."""
        if self.queue.full():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self.queue.put_nowait(
                ErrorMsg(tick=..., code="backlog_overflow", detail="..."),
            )
            return
        self.queue.put_nowait(env)
```

### 1.3 broadcaster タスク

```python
async def broadcaster(app: FastAPI) -> None:
    runtime: WorldRuntime = app.state.runtime
    registry: SessionRegistry = app.state.registry
    while True:
        env = await runtime.recv_envelope()
        for sess in registry.iter_active():
            sess.enqueue(env)
```

`lifespan` context で `asyncio.create_task(broadcaster(app))` として起動、
`app.state.broadcaster_task` に保持。shutdown 時に cancel + await。

### 1.4 Timeouts

- **Handshake**: `asyncio.wait_for(session._recv_handshake(), HANDSHAKE_TIMEOUT_S)`
  5 秒。timeout で `ErrorMsg(code="handshake_timeout")` → close
- **Idle disconnect**: Session に `_last_recv_at` を保持、`_recv_loop` 内で
  毎回更新。別 watchdog タスクを asyncio.create_task で起動し、
  1 秒ごとに `time.monotonic() - last > IDLE_DISCONNECT_S` をチェック。該当で
  `ErrorMsg("idle_disconnect")` + close

### 1.5 Entry point

```python
# gateway.py 末尾
if __name__ == "__main__":
    import argparse
    import uvicorn
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
├── __init__.py     # 既存に 3-4 シンボル追加 (Session / make_app / SessionRegistry)
├── protocol.py     # 既存 (Mac PR #23)
├── scenarios.py    # 既存
├── metrics.py      # 既存
├── acceptance.py   # 既存
├── gateway.py      # 新規 (~400-500 行)
│                   # make_app() factory + /health + /ws/observe +
│                   # broadcaster task + SessionRegistry
└── session.py      # 新規 (~200-250 行)
                    # Session クラス、phase 遷移、handshake/recv/send/watchdog
```

## 3. 変更対象

### 新規作成 (5 ファイル)

| ファイル | 想定行数 |
|---|---|
| `src/erre_sandbox/integration/gateway.py` | ~400 |
| `src/erre_sandbox/integration/session.py` | ~220 |
| `tests/test_integration/test_gateway.py` | ~380 |
| `tests/test_integration/test_session.py` | ~200 |
| (新規合計) | ~1200 |

### 修正 (3 ファイル)

| ファイル | 内容 |
|---|---|
| `src/erre_sandbox/integration/__init__.py` | Session / SessionRegistry / make_app を export |
| `tests/test_integration/conftest.py` | gateway_app / live_gateway / mock_runtime fixture |
| `.steering/_setup-progress.md` | T14 エントリ追加 |

### 削除
なし。

## 4. 影響範囲

- `integration/` に gateway.py / session.py 追加、`__init__.py` 末尾に 3 シンボル追加
- 既存 `__all__` を削除・改名しないため `test_contract_snapshot.py` は無傷
- `WorldRuntime._envelopes` は現状 unbounded。T14 本文では変更しない
  (per-client 256 件の bounded queue により slow consumer 対策は完成)
- 既存 skeleton test (test_scenario_*) は触らない (T19 scope)

## 5. 既存パターンとの整合性

| パターン | 参照 | T14 での適用 |
|---|---|---|
| ClassVar + kw-only __init__ DI | `cognition/cycle.py:107`, `world/tick.py:179` | `Session.DEFAULT_QUEUE_SIZE`, `make_app(runtime=...)` |
| TypeAdapter(ControlEnvelope) で parse | `tests/test_schemas.py:122` | `_ADAPTER = TypeAdapter(ControlEnvelope)` module-level |
| DI で決定論 | `world/tick.py:91` ManualClock | `Session` の timeout に monotonic fn を注入可能 |
| asyncio.TaskGroup | (世界初登場は T13) | Session.run() で 3 タスクを管理、except\* でエラー吸収 |
| tests ミラー構造 | `tests/test_world/` | `test_integration/test_gateway.py` + `test_session.py` |

## 6. テスト戦略

### 6.1 `test_session.py` (~200 行)

Starlette を使わず、Session クラス単体:

- phase が `AWAITING_HANDSHAKE` から始まる
- enqueue が 256 件超で oldest drop + ErrorMsg append
- enqueue が close 後は無視される
- handshake timeout → ErrorMsg + phase=CLOSING

Mock WebSocket: `MagicMock(spec=WebSocket)` + asyncio.Queue で in/out 模擬。

### 6.2 `test_gateway.py` (~380 行)

`starlette.testclient.TestClient` で同期的に WS を叩く:

- `/health` 200 OK + JSON
- `/ws/observe` 接続 → server HandshakeMsg 受信 → client HandshakeMsg 送信 → ACTIVE
- client が HandshakeMsg を送らない → timeout fixture で短縮して検証
- schema_version 不一致で ErrorMsg("schema_mismatch")
- 2 client 同時接続 → runtime に envelope 投入 → 両 client 受信
- backlog overflow の挙動
- invalid JSON → ErrorMsg("invalid_envelope")
- idle disconnect (fixture で IDLE_DISCONNECT_S=1s に)

### 6.3 conftest.py 拡張

```python
@pytest.fixture
def mock_runtime() -> MockRuntime: ...

@pytest.fixture
def gateway_app(mock_runtime) -> FastAPI: ...

@pytest.fixture
def client(gateway_app) -> TestClient: ...

@pytest.fixture
def fast_timeouts(monkeypatch) -> None:
    monkeypatch.setattr(protocol, "HANDSHAKE_TIMEOUT_S", 0.2)
    monkeypatch.setattr(protocol, "IDLE_DISCONNECT_S", 1.0)
```

### 6.4 回帰

- baseline: 274 passed / 34 skipped (T13 + Mac T19 design 合流後)
- 期待: +25-30 件、skip は据え置き

## 7. ロールバック計画

- 新規ファイル + `__init__.py` 追加のみ。`git revert` 1 コミットで復元
- Fan-out 方式は broadcaster タスク差し替え 1 箇所
- Timeout 値は `protocol.py` 差し替えのみ

## 8. 関連する Skill

- `error-handling` — asyncio timeout, TaskGroup except\*, WS close 手順 (primary)
- `python-standards` — FastAPI / starlette / uvicorn
- `architecture-rules` — integration/gateway.py → world 依存の新規許容、ui 禁止
- `test-standards` — pytest-asyncio, TestClient, mock fixture

## 9. 破壊と構築 (/reimagine) 適用予定

比較軸:

1. **Fan-out 戦略**: (a) 単一 broadcaster タスクが全 session queue に put、
   (b) 各 session が独自 subscribe、(c) PubSub ハブ、(d) `WorldRuntime` に複数
   subscriber 対応 API を追加
2. **Session 実装形**: クラス + 3 内部タスク / 単一 run() / Task per phase
3. **Timeout**: `asyncio.wait_for` / `asyncio.timeout` / 手動 Event + watchdog
4. **テスト手法**: starlette TestClient (sync) / httpx_ws (async) / Mock class
5. **gateway.py と session.py の分離**: 1 ファイル畳む vs 責務別分割

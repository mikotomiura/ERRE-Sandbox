# T14 gateway-fastapi-ws

## 背景

T13 で `world.WorldRuntime` が `ControlEnvelope` を `asyncio.Queue` に出力できる
状態になり、Mac 側の PR #23 (T19 設計フェーズ) で
`src/erre_sandbox/integration/protocol.py` に session lifecycle の定数と
`SessionPhase` enum が凍結された。しかし以下が欠落している:

- **WebSocket サーバー不在**: `WorldRuntime._envelopes` に流れる envelope を
  外部 (Godot クライアント) に届ける HTTP/WS エンドポイントがない
- **Session 管理不在**: Mac が定義した
  `AWAITING_HANDSHAKE → ACTIVE → CLOSING` 遷移・`HANDSHAKE_TIMEOUT_S=5.0` /
  `IDLE_DISCONNECT_S=60.0` / `HEARTBEAT_INTERVAL_S=1.0` /
  `MAX_ENVELOPE_BACKLOG=256` を実装する箇所がない
- **Fan-out 機構不在**: `WorldRuntime._envelopes` は単一キューであり、
  複数の WS クライアントに fan-out する仕組みがない
- **T19 ブロック**: tests/test_integration/ の skeleton が T14 の live server
  fixture を待って全 skip、E2E 実行フェーズ (T19 実装版) / T20 検収が開始できない

MASTER-PLAN T14 行: `gateway-fastapi-ws` (G-GEAR, 1d, T13 依存, error-handling Skill)。
docs/architecture.md §1 Gateway と §3 Gateway 責務、
docs/functional-design.md §2 機能 1d Express に直接対応する。

契約文書: `.steering/20260419-m2-integration-e2e/integration-contract.md` が
T14 実装者向けの詳細 rational を既に記述済み (Mac が書いた)。本タスクはその契約を
実装に落とす作業。

## ゴール

`src/erre_sandbox/integration/gateway.py` が提供する FastAPI アプリで:

1. **WS エンドポイント `GET /ws/observe`** — 認証なし LAN 内前提、
   アップグレード応答に `X-Erre-Schema-Version: <SCHEMA_VERSION>` ヘッダ
2. **Handshake 交換** — accept 直後に server → client の `HandshakeMsg`
   (peer="g-gear", capabilities=7 種) を送信、`HANDSHAKE_TIMEOUT_S=5.0` 以内に
   client → server の `HandshakeMsg` を受信。schema_version 不一致なら
   `ErrorMsg(code="schema_mismatch")` 送信 → close
3. **Active フェーズ** — `WorldRuntime._envelopes` から pull した envelope を
   接続中の全 client に fan-out。per-client 有界キュー (256 件) を持ち、
   超過時に oldest を drop して `ErrorMsg(code="backlog_overflow")` 警告
4. **Idle disconnect** — `IDLE_DISCONNECT_S=60.0` 秒 client からの frame なしで
   `ErrorMsg(code="idle_disconnect")` → close
5. **ヘルスチェック `GET /health`** — 200 OK + JSON `{schema_version, status: "ok", active_sessions}`
6. **エントリーポイント** — `uv run python -m erre_sandbox.integration.gateway` で
   uvicorn 起動 (ws://0.0.0.0:8000/ws/observe)

## スコープ

### 含むもの
- `src/erre_sandbox/integration/gateway.py` — FastAPI app + WS endpoint +
  session state machine + fan-out + `__main__` ブロック
- `src/erre_sandbox/integration/session.py` (必要なら分離) — `Session` クラス
  (SessionPhase 遷移、per-client queue、timeouts)
- 既存 `integration/__init__.py` に新シンボル追加
- 単体テスト `tests/test_integration/test_gateway.py` —
  handshake success / handshake timeout / schema mismatch / streaming /
  idle disconnect / backlog overflow / invalid envelope
- `tests/test_integration/conftest.py` の更新:
  - `gateway_app` fixture (`FastAPI` instance、AsyncClient で接続可能)
  - `live_gateway` fixture (`uvicorn.Server` を random port で起動/停止)
  - mock `WorldRuntime` を受け取れる構造 (テスト用に envelope を注入)
- 既存 skeleton テスト (`test_scenario_walking.py` 等) の skip マーカーは維持
  (E2E 実行フェーズは T19 で実施)
- `docs/_pdf_derived/` 追加なし

### 含まないもの
- Godot 側 WS クライアント実装 → T16 で完了済み
- TLS / 認証 (OAuth2 など) — M10 以降
- E2E scenario テストの skip 解除 → T19 実行フェーズ
- Dashboard UI (Streamlit / HTMX) → T18 (optional)
- Envelope の msgpack 圧縮 → 将来課題 (現時点は JSON のみ)
- Multiple gateway subscribers の fan-out 設計最適化 (simple broadcast で可)
- `since_tick` による replay / `agent_id` filter → Mac 契約 §5 Q3 "Postpone to T14 or later"、
  **本 T14 では実装しない**
- SGLang / vLLM の後段切替 → M7 / M9

## 受け入れ条件

- [ ] `uv run python -m erre_sandbox.integration.gateway --port 8000` で
      FastAPI + uvicorn が起動し `/health` が 200 OK
- [ ] `ws://localhost:8000/ws/observe` に接続 → server が HandshakeMsg 送信 →
      client が HandshakeMsg 送信 → 5 秒以内に ACTIVE 遷移
- [ ] ACTIVE フェーズで `WorldRuntime._envelopes.put_nowait(WorldTickMsg(...))` が
      接続中の全 client に forward される
- [ ] client が `HANDSHAKE_TIMEOUT_S=5.0` を超えて無応答 → `ErrorMsg("handshake_timeout")`
      + close、session が CLOSING に遷移
- [ ] client の schema_version が不一致 → `ErrorMsg("schema_mismatch")` + close
- [ ] per-client queue が 256 超 → oldest 1 件 drop + `ErrorMsg("backlog_overflow")` 警告
      (close しない)
- [ ] 60 秒無通信 → `ErrorMsg("idle_disconnect")` + close
- [ ] 複数 client 同時接続 (>=2) で fan-out が動作し、1 client 切断が他に波及しない
- [ ] `uv run pytest tests/test_integration/test_gateway.py -v` がグリーン
- [ ] 既存 248 テスト + T19 skeleton の 23 skipped 構成が崩れない (gateway テストのみ追加)
- [ ] `ruff check` / `ruff format --check` / `mypy --strict src/erre_sandbox/integration/` 緑
- [ ] `from erre_sandbox.integration.gateway import *` が `ui/` を import していない
- [ ] `integration-contract.md` §3 の `ErrorMsg.code` 6 種すべてに対応する path が存在
      (`handshake_timeout` / `schema_mismatch` / `idle_disconnect` /
      `backlog_overflow` / `invalid_envelope` / `internal_error`)

## 関連ドキュメント

- `docs/architecture.md` §1 全体図 Gateway / §3 Gateway 責務 / §6 外部システム連携
- `docs/functional-design.md` §2 機能 1d Express / §5 非機能要件 (ティックレート・認証方式)
- `docs/repository-structure.md` §2 `integration/` / §4 依存方向
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` T14 行 / §11 Critical Files
- `.steering/20260419-m2-integration-e2e/integration-contract.md` — **T14 実装者向け契約文書**
- `.steering/20260419-m2-integration-e2e/decisions.md` D1-D4 (Mac 側の決定)
- `src/erre_sandbox/integration/protocol.py` — 定数と SessionPhase enum (消費)
- `src/erre_sandbox/integration/scenarios.py` — Scenario モデル (T19 で消費、T14 では間接参照)
- `src/erre_sandbox/schemas.py` §7 ControlEnvelope (7 種 + discriminated union)
- `src/erre_sandbox/world/tick.py` — `WorldRuntime` (envelope 生成源)
- `.claude/skills/error-handling/SKILL.md` (primary, WS 再接続と asyncio 例外処理)
- `.claude/skills/python-standards/SKILL.md`
- `.claude/skills/architecture-rules/SKILL.md` (integration レイヤーの依存方向)

## 運用メモ

- 破壊と構築（/reimagine）適用: **Yes (推奨)**
- 理由: (1) Fan-out 戦略に複数案がある
  (WorldRuntime 側で直接 broadcast / 各 Session が独自 subscribe / PubSub ハブを挟む /
  `asyncio.Queue` を複製)。
  (2) Session state machine の実装形 (単一クラス / 関数 + Enum / asyncio.TaskGroup で
  子タスク分離) に複数選択肢。
  (3) Timeout 実装 (`asyncio.wait_for` vs `asyncio.timeout` コンテキスト vs 手動 Event)。
  (4) FastAPI の `starlette.websockets.WebSocket` vs `websockets` 直接使用の選択。
  設計判断が後戻りコスト高い箇所が多いため `/reimagine` を推奨。

# 設計 (v2 再生成案)

## 実装アプローチ

**「Single-file HTML + Server-side Metrics State + Typed WS message envelope」
アプローチ** — HTML/JS/CSS を Python 文字列定数に埋め込む single-file 構成、
ブラウザ側は Web Components で 3 パネルを宣言的に記述、metrics 集計と threshold
判定は **server 側で state を保持** し、client には `snapshot` / `delta` / `alert`
の 3 種に discriminate した **型付き UI メッセージ** を push する。

### 着想の核

要件の 3 パネルは本質的に:
- **state の射影**: Agent Panel = 最新 `AgentState` の射影
- **time series の射影**: Envelope Stream = 直近 N 件の tail
- **集計の射影**: Metrics Panel = rolling window の集計値

いずれも「server side で完成した state を client に render させる」モデルが自然。
client 側で metric 集計をするより、server 側で完結させて dashboard は純粋な render 層にする。

この分離により:
1. **Metric 集計ロジックが単体テスト容易** — server 側の純関数として分離可能
2. **再接続時に状態が消えない** — 新 client は最初に snapshot を受ける
3. **Threshold 判定が一元化** — server が alert を発信、client は表示するだけ

### Server → Client メッセージ型 (3 種 discriminated union)

`schemas.py` の `ControlEnvelope` と同じ discriminated-union パターンを踏襲:

| kind | 送出タイミング | payload |
|---|---|---|
| `snapshot` | client 接続直後に 1 回 | 全 state (latest AgentState / envelope tail / metrics / alerts) |
| `delta` | envelope 1 件受信ごと | その envelope + 更新後 metrics |
| `alert` | threshold 逸脱検出時 | which threshold, current value, timestamp |

Pydantic BaseModel で型定義し、`model_dump_json()` で送出。

## 変更対象

### 新規作成するファイル

```
src/erre_sandbox/ui/dashboard/
├── __init__.py        — 公開 API
├── __main__.py        — `python -m erre_sandbox.ui.dashboard`
├── server.py          — FastAPI app factory + WS handler
├── state.py           — DashboardState + MetricsAggregator + ThresholdEvaluator
├── messages.py        — UiMessage discriminated union (SnapshotMsg/DeltaMsg/AlertMsg)
├── stub.py            — ControlEnvelope を循環供給する deterministic generator
└── html.py            — index.html テンプレ文字列 (Python 定数)
```

```
tests/test_ui/
├── __init__.py
├── conftest.py        — DashboardState / TestClient fixture
├── test_messages.py   — UiMessage の型検証
├── test_state.py      — MetricsAggregator 単体、ThresholdEvaluator 境界値
├── test_stub.py       — Stub generator の決定性と ControlEnvelope 経由性
└── test_server.py     — FastAPI TestClient で GET /dashboard, WS snapshot/delta/alert
```

### 修正するファイル
- `src/erre_sandbox/ui/__init__.py` — docstring を更新 (integration 依存を明示)
- `.steering/20260418-implementation-plan/tasklist.md` — T18 行を `[x]` + PR #

## 影響範囲

| 領域 | 影響 | 対処 |
|---|---|---|
| `src/erre_sandbox/ui/` | `dashboard/` サブパッケージ新規 | architecture-rules: ui/ は schemas.py のみ依存が既定 → integration/ への依存を追加、decisions.md に記録 |
| 依存ライブラリ | FastAPI / uvicorn / pydantic (全て既存) | 追加なし |
| テスト | `tests/test_ui/` 新規 | FastAPI TestClient 使用 |
| CI | pytest 自動収集 | skip/active は全て active (stub 前提) |
| Godot | 影響なし | — |
| T14 gateway | 影響なし (別プロセス) | — |

## 既存パターンとの整合性

- **Discriminated union (UiMessage)** — `schemas.py` ControlEnvelope と同思想
- **FastAPI app factory (`create_app`)** — pytest TestClient との既定 pattern
- **frozen Pydantic / dataclass** — `integration/` モジュールの流儀を継承
- **Stub が ControlEnvelope Pydantic を経由** — T05 schemas-freeze の契約に乗る
- **Rolling window は `collections.deque`** — 純 Python、追加依存なし

## テスト戦略

| テスト | 内容 |
|---|---|
| `test_messages.py::test_snapshot_delta_alert_discrimination` | UiMessage のタグ付き union が正しく解決する |
| `test_state.py::test_metrics_aggregator_empty` | 初期状態で p50/p95 計算が NaN を返さない (None or 0) |
| `test_state.py::test_metrics_aggregator_converges` | 既知 latency 系列で p50/p95 が期待値 |
| `test_state.py::test_threshold_evaluator_boundary` | 境界値でちょうど・超過の判定が正確 |
| `test_stub.py::test_stub_is_deterministic` | seed 固定で同一系列 |
| `test_stub.py::test_stub_emits_control_envelope_pydantic` | 各 envelope が ControlEnvelope として parse 可能 |
| `test_server.py::test_get_dashboard_returns_html_200` | GET /dashboard が 200 + text/html |
| `test_server.py::test_ws_initial_snapshot` | WS 接続直後に SnapshotMsg を 1 件受信 |
| `test_server.py::test_ws_delta_stream` | snapshot 後に DeltaMsg を複数受信 |
| `test_server.py::test_ws_alert_on_threshold_violation` | 閾値を超える envelope を注入すると AlertMsg 受信 |

目標: **10 件** の test 全 PASS。要件の最低 4 件を超過。

## ロールバック

```bash
git checkout main
git branch -D feature/ui-dashboard-minimal
rm -rf src/erre_sandbox/ui/dashboard/ tests/test_ui/
```

## リスク

| リスク | 影響 | 緩和策 |
|---|---|---|
| HTML を Python 文字列に埋め込む可読性 | HTML 編集時の DX 悪化 | html.py に単一の `HTML_TEMPLATE` 定数 + triple-quoted raw string、linting は ruff 対象外として OK |
| Web Components の IE 非互換 | 非互換ブラウザ対応負担 | IE 非対応を明記 (開発用 dashboard、最新 Chrome/Firefox/Safari 前提) |
| Server state が再起動で消える | 開発中に dashboard server restart すると履歴ロスト | 要件で「in-memory rolling buffer のみ」明記済み、DB 不要 |
| threshold 判定が false positive を多発 | UI がノイジーに | warming-up (最初 5 envelope) は alert しない、decisions.md に記録 |
| stub と T14 gateway の API ズレ | 視覚検証が無意味化 | stub が ControlEnvelope を経由、test_stub で保証 |
| port 8001 競合 | 起動失敗 | default 8001、`ERRE_DASHBOARD_PORT` env で上書き可 |

## 設計判断の履歴

- **初回案 (`design-v1.md`) と再生成案 (v2) を比較** → `design-comparison.md` 参照
- **採用: v2** (2026-04-19) — Web Components を 1 個に縮小、HTML_TEMPLATE は
  plain HTML 寄せで編集性を確保
- **根拠**:
  1. schemas.py / integration の discriminated union 思想との一貫性が決定的
  2. Server-side metrics state により、再接続耐性と純関数テスト容易性の両方を得る
  3. threshold alert は envelope とは性質の異なるメッセージで、型分離が素直
  4. 10 件のテスト粒度で state / stub / server を独立検証できる
- **v1 から取り込んだ要素**:
  HTML 編集性を重視し、Web Components の使用を 1 個に限定、残りは plain DOM 操作。
  `html.py` の `HTML_TEMPLATE` は raw triple-quoted string で、なるべく普通の
  HTML として可読に保つ。

# 設計 (v1 初回案)

## 実装アプローチ

**「FastAPI mini app + Vanilla JS SPA」アプローチ** — 独立プロセス (port 8001) で
FastAPI を起動し、HTML/JS/CSS を `StaticFiles` で配信、WS で envelope を push する。
T14 が未完成の間は fixtures/control_envelope の JSON を繰り返し生成する stub
generator が envelope を供給する。

## 変更対象

### 新規作成するファイル

**Python 側**:
```
src/erre_sandbox/ui/dashboard/
├── __init__.py          — 公開 API (create_app, StubEnvelopeGenerator)
├── __main__.py          — `python -m erre_sandbox.ui.dashboard` エントリ
├── server.py            — FastAPI app factory + WS /ws/dashboard handler
├── stub.py              — fixtures/control_envelope を循環再生する generator
└── metrics.py           — rolling window で latency/jitter/write-rate 集計
```

**静的アセット**:
```
src/erre_sandbox/ui/dashboard/static/
├── index.html           — 3 パネル layout
├── app.js               — WS 購読 + DOM 更新
└── style.css            — 最小スタイル
```

**テスト**:
```
tests/test_ui/
├── __init__.py
└── test_dashboard.py    — TestClient で GET / WS / stub / thresholds を検証
```

### 修正するファイル
- `.steering/20260418-implementation-plan/tasklist.md` — T18 行を `[x]` + PR #
- `src/erre_sandbox/ui/__init__.py` — dashboard export 追加

## 影響範囲

| 領域 | 影響 | 対処 |
|---|---|---|
| `src/erre_sandbox/ui/` | dashboard/ サブパッケージ新規 | architecture-rules: ui/ は schemas.py のみ依存が既定。integration/ への依存を追加する (decisions.md で記録) |
| 依存ライブラリ | fastapi / uvicorn は既存、追加なし | — |
| テスト | tests/test_ui/ 新規 | fastapi.testclient.TestClient を使用 (既存 pattern) |
| CI | 自動収集 | — |
| Godot | 影響なし | — |

## 既存パターンとの整合性

- ui/ モジュール内の既存 `__init__.py` docstring ("depends on schemas only") に
  integration を追加する旨を記録
- FastAPI app factory pattern (create_app) — pytest TestClient との相性◎
- StaticFiles で /static を mount、Jinja2 なしで文字列テンプレ的に index.html を配信
- rolling window は collections.deque(maxlen=50) で envelope を保持、純 Python で集計

## テスト戦略

- **unit**: StubEnvelopeGenerator の決定性 (seed 固定で同一列)
- **unit**: rolling window metrics 計算ロジック (latency p50/p95 のナイーブ実装)
- **integration**: FastAPI TestClient で GET /dashboard 200 + text/html
- **integration**: TestClient の websocket_connect で /ws/dashboard に接続、
  少なくとも 3 envelope 受信を確認
- **contract**: 閾値逸脱検出ロジックの境界値テスト

## ロールバック計画

```bash
git checkout main
git branch -D feature/ui-dashboard-minimal
rm -rf src/erre_sandbox/ui/dashboard/ tests/test_ui/
```

## リスク

| リスク | 影響 | 緩和策 |
|---|---|---|
| stub が T14 完成時に実 WS 型と乖離 | 視覚確認したはずの UI が本番で壊れる | stub も `ControlEnvelope` Pydantic を経由させる (JSON → model → dict) |
| 閾値計算がサンプル数不足で不安定 | 早期に警告が誤動作 | 最初の N 件 (例 5) は「warming up」扱い、警告表示しない |
| ui/ の依存方向違反 | architecture-rules 違反 | schemas.py + integration/ のみ import、cognition/memory/world/inference を触らない (lint 不可なので review で見る) |
| Godot client との port 競合 | T14 gateway (想定 8000) と本 dashboard (8001) の競合 | 別 port、default を env var 化 |

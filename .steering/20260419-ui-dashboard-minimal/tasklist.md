# タスクリスト (T18 ui-dashboard-minimal)

v2 採用に基づき以下の順で進める。

## Phase A: 設計記録
- [x] A1. requirement.md
- [x] A2. design-v1.md 作成
- [x] A3. design.md v2
- [x] A4. design-comparison.md
- [ ] A5. decisions.md (4-6 件)

## Phase B: 型とロジック (src/erre_sandbox/ui/dashboard/)
- [ ] B1. `messages.py` — UiMessage discriminated union
      (`SnapshotMsg` / `DeltaMsg` / `AlertMsg`、Pydantic v2)
- [ ] B2. `state.py` — `MetricsAggregator` (rolling window with
      `collections.deque`) + `ThresholdEvaluator` + `DashboardState`
- [ ] B3. `stub.py` — fixtures/control_envelope を巡回しつつ latency ノイズを
      加える deterministic generator、seed 可変
- [ ] B4. `html.py` — `HTML_TEMPLATE` 定数 (plain HTML + 最小 JS + Web Component 1 個)
- [ ] B5. `server.py` — `create_app()` factory + WS handler + `GET /dashboard`
- [ ] B6. `__main__.py` — uvicorn 起動 (default port 8001, env override)
- [ ] B7. `__init__.py` — 公開 API

## Phase C: テスト (tests/test_ui/)
- [ ] C1. `__init__.py`, `conftest.py`
- [ ] C2. `test_messages.py` — UiMessage の discriminator 解決
- [ ] C3. `test_state.py` — MetricsAggregator / ThresholdEvaluator の境界
- [ ] C4. `test_stub.py` — 決定性 + ControlEnvelope 経由性
- [ ] C5. `test_server.py` — GET /dashboard, WS snapshot/delta/alert

## Phase D: 連携・検証
- [ ] D1. `ruff check` 緑
- [ ] D2. `ruff format --check` 緑
- [ ] D3. `mypy src` 緑
- [ ] D4. `pytest` 緑 (全体)
- [ ] D5. `python -m erre_sandbox.ui.dashboard` で起動し、ブラウザで挙動を目視
      (localhost:8001/dashboard)
- [ ] D6. MASTER-PLAN 直下 tasklist.md の T18 を `[x]` + PR 番号併記

## Phase E: レビュー・クローズ
- [ ] E1. self-review
- [ ] E2. git commit (Conventional Commits、feat(ui): T18 …)
- [ ] E3. push + PR 作成 (base=main)

## ロールバック
```bash
git checkout main
git branch -D feature/ui-dashboard-minimal
rm -rf src/erre_sandbox/ui/dashboard/ tests/test_ui/
```

# タスクリスト (T19 設計フェーズ)

design.md の v2 採用に基づき、以下の順で進める。

## Phase A: 前提確認・設計記録

- [x] A1. `requirement.md` 記入
- [x] A2. `design-v1.md` 作成 (初回案退避)
- [x] A3. `design.md` v2 記入
- [x] A4. `design-comparison.md` 作成
- [x] A5. `schemas.py` の既存 `ControlEnvelope` / `HandshakeMsg` / `WorldTickMsg` / `ErrorMsg` を確認 → **重複定義しない** 方針確定
- [x] A6. `architecture-rules` Skill 確認 → `integration/` は新レイヤー、依存は `schemas.py` のみ、T14 gateway 実装時に `world/` import を追加する方針
- [ ] A7. `decisions.md` 作成 (判断 5-7 件)

## Phase B: 機械可読契約モジュール (src/erre_sandbox/integration/)

- [ ] B1. `src/erre_sandbox/integration/__init__.py` — 公開 API の `__all__`
- [ ] B2. `src/erre_sandbox/integration/protocol.py`
      — session lifecycle 定数 (HEARTBEAT_INTERVAL_S=1.0, HANDSHAKE_TIMEOUT_S=5.0, IDLE_DISCONNECT_S=60.0 等) + `SessionPhase` StrEnum (AWAITING_HANDSHAKE / ACTIVE / CLOSING)
      — **WS メッセージ型は schemas.py のものを再利用**
- [ ] B3. `src/erre_sandbox/integration/scenarios.py`
      — `Scenario` dataclass (frozen) + `SCENARIO_WALKING` / `SCENARIO_MEMORY_WRITE` / `SCENARIO_TICK_ROBUSTNESS` の定数タプル + 各シナリオの時系列 step 定義
- [ ] B4. `src/erre_sandbox/integration/metrics.py`
      — `Thresholds` Pydantic model (frozen=True): p50/p95 latency、tick jitter、memory 書込み率、arousal range など数値定義
- [ ] B5. `src/erre_sandbox/integration/acceptance.py`
      — `AcceptanceItem` dataclass + `ACCEPTANCE_CHECKLIST` 定数リスト (T20 用、Python から走査可能)

## Phase C: 試験 skeleton (tests/test_integration/)

- [ ] C1. `tests/test_integration/__init__.py` (空)
- [ ] C2. `tests/test_integration/conftest.py`
      — 共通 fixture (AgentState 生成、Observation stream stub、fake WS client)
- [ ] C3. `tests/test_integration/test_contract_snapshot.py` **(常時 ON、skip しない)**
      — `ControlEnvelope` の各 envelope kind について `model_json_schema()` のハッシュを固定、ドリフト検出
      — `Thresholds.model_json_schema()` も同様
- [ ] C4. `tests/test_integration/test_scenario_walking.py` (`pytestmark = pytest.mark.skip(...)`)
      — S1/S2 skeleton
- [ ] C5. `tests/test_integration/test_scenario_memory_write.py` (skip)
      — S3 skeleton
- [ ] C6. `tests/test_integration/test_scenario_tick_robustness.py` (skip)
      — S4/S5 skeleton

## Phase D: 人間向けナラティブ Markdown

- [ ] D1. `.steering/.../scenarios.md`
      — 3-5 シナリオの日本語時系列記述 (ユースケース説明、Python 側の `SCENARIO_*` と相互参照)
- [ ] D2. `.steering/.../integration-contract.md`
      — WS 契約の rational、エラー応答方針、セッション設計、T14 実装者への FAQ
- [ ] D3. `.steering/.../metrics.md`
      — 閾値の根拠、測定方法、調整記録のテンプレ
- [ ] D4. `.steering/.../t20-acceptance-checklist.md`
      — MVP タグ `v0.1.0-m2` 前チェック 10-15 項目、運用 runbook 形式

## Phase E: 連携・検証

- [ ] E1. `.steering/20260418-implementation-plan/tasklist.md` の T19 行を設計フェーズ完了マーク + PR 番号で更新 (commit は別にする)
- [ ] E2. `uv run ruff check` 緑
- [ ] E3. `uv run ruff format --check` 緑
- [ ] E4. `uv run mypy src` 緑
- [ ] E5. `uv run pytest` 緑 (新 skeleton は SKIPPED、contract_snapshot は PASS)
- [ ] E6. `uv run pytest tests/test_integration/ --collect-only` で 4 件収集 (3 skip + 1 active) を目視確認

## Phase F: レビュー・クローズ

- [ ] F1. self-review (design.md / decisions.md / integration-contract.md の整合確認)
- [ ] F2. (任意) code-reviewer subagent 起動
- [ ] F3. git commit (Conventional Commits: `feat(integration): T19 design — contract module + skeleton tests`)
- [ ] F4. push + PR 作成 (base=main, head=feature/m2-integration-e2e)
- [ ] F5. `/finish-task` による最終処理

## ロールバック

```bash
git checkout main
git branch -D feature/m2-integration-e2e
rm -rf src/erre_sandbox/integration/ tests/test_integration/
```

# T19 m2-integration-e2e — 実行フェーズ (Execution Phase)

## 背景

T19 設計フェーズ (PR #23, `.steering/20260419-m2-integration-e2e/`) で以下を凍結済み:

- 3 シナリオ定義: `SCENARIO_WALKING` / `SCENARIO_MEMORY_WRITE` / `SCENARIO_TICK_ROBUSTNESS`
  (`src/erre_sandbox/integration/scenarios.py` + `scenarios.md`)
- 受け入れメトリクス: `M2_THRESHOLDS` (p50 ≤ 100ms, p95 ≤ 250ms, tick jitter ≤ 0.20, memory write rate ≥ 0.98)
  (`src/erre_sandbox/integration/metrics.py` + `metrics.md`)
- T20 acceptance チェックリスト: `ACCEPTANCE_CHECKLIST` (schema / runtime / memory / observability / reproducibility / docs カテゴリ)
  (`src/erre_sandbox/integration/acceptance.py` + `t20-acceptance-checklist.md`)
- Skeleton tests: `tests/test_integration/test_scenario_{walking,memory_write,tick_robustness}.py`
  (現在 `@pytest.mark.skip("T19 実行フェーズ待ち")` で待機中)
- Contract snapshot test: `tests/test_integration/test_contract_snapshot.py` (常時 ON、23 件 PASSED)

T14 gateway (PR #24) と T17/T18 MacBook 側も完成し、T19 **実行フェーズ** の前提が整った。

本タスクは T19 実行フェーズを G-GEAR 側で遂行し、
- skeleton tests の skip を解除して CI 上で実行
- `AsyncClient` + `MockRuntime` ベース (Layer B) と 必要に応じて Ollama 実機起動 (Layer C) でシナリオを点灯
- 実 E2E 実行ログを取得して T20 acceptance checklist の runtime / memory / observability 系項目を可能な範囲で埋める
- MacBook/Godot 側での最終検証 (30Hz 描画 / Avatar Tween 移動) は **別セッションに引き渡す**

## ゴール

以下をすべて満たすこと:

1. **Skeleton tests の点灯**: `tests/test_integration/test_scenario_*.py` の 3 ファイル合計 11 件の `@pytest.mark.skip` を解除、
   - Layer B (in-process TestClient + MockRuntime or lightweight fake): CI 常時実行で PASS
   - Layer C (Ollama 実機連携): `@pytest.mark.integration` または env gating で opt-in (CI デフォルト OFF)
2. **実 E2E 実行ログ**: G-GEAR 機で Ollama serve + `python -m erre_sandbox.integration.gateway` を起動し、
   `logs/m2-acceptance-run.jsonl` に envelope / memory write ログを取得
3. **T20 checklist 部分実施**: G-GEAR 側で実施可能な項目 (ACC-SCHEMA-FROZEN / ACC-SCENARIO-* / ACC-LATENCY-* /
   ACC-MEMORY-WRITE-RATE / ACC-LOGS-PERSISTED / ACC-REPRO-SEED) を埋め、
   MacBook/Godot 依存項目は「MacBook セッション引き継ぎ事項」として `handoff-to-macbook.md` に記録
4. **MASTER-PLAN 同期**: `.steering/20260418-implementation-plan/tasklist.md` の T19 行を「実行フェーズ完了」に更新

## スコープ

### 含むもの
- `tests/test_integration/test_scenario_walking.py` の skip 解除と Layer B / Layer C 実装
- `tests/test_integration/test_scenario_memory_write.py` の skip 解除と Layer B 実装 (sqlite-vec in-memory)
- `tests/test_integration/test_scenario_tick_robustness.py` の skip 解除と Layer B 実装
  (disconnect/reconnect は `AsyncClient` の `ws_disconnect` で代替)
- Observability: scenario 実行時に envelope と memory write を構造化ログに出力
  (`jsonl` 形式、latency_ms フィールド含む)
- Seed 固定: シナリオ実行に `seed=42` を注入する経路 (pytest fixture 経由)
- G-GEAR 実機での smoke run 1 回以上 (Ollama + gateway + scenario で 1 tick サイクル確認)
- `.steering/20260419-m2-integration-e2e-execution/handoff-to-macbook.md` の作成
- MASTER-PLAN tasklist の T19 行更新 + PR 番号併記

### 含まないもの
- **T20 `v0.1.0-m2` タグ付与** — 次タスク (T20) に委譲
- **MacBook/Godot 側検証** (Avatar Tween 移動、30Hz 描画、ws_client 実接続) — MacBook セッション引き継ぎ
- **ACC-DOCS-UPDATED** (`docs/architecture.md` の T14 セクション更新) — T20 範囲
- **ACC-TAG-READY** (バージョン 0.1.0 整合) — T20 範囲
- **SGLang 移行 / LoRA** — M7 以降
- **M4 以降の拡張シナリオ** (S_DIALOG / S_REFLECTION / S_MODE_FSM / S_MULTI_ZONE / S_12H_STABILITY)
- **クラウド LLM API 利用** (予算ゼロ制約)
- **新規 WS API 追加** — T14 Contract は凍結済み、変更が必要なら別タスク化

## 受け入れ条件

- [ ] `tests/test_integration/test_scenario_{walking,memory_write,tick_robustness}.py` 3 ファイルで
      `@pytest.mark.skip("T19 実行フェーズ待ち")` が全て解除されている
- [ ] `uv run pytest tests/test_integration/` が G-GEAR で PASS (Layer B のみ、ollama 不要)
- [ ] `uv run pytest -m integration tests/test_integration/` が G-GEAR で PASS
      (Layer C、Ollama 実機 + `qwen3:8b` + `nomic-embed-text` ロード済み前提)
- [ ] `uv run ruff check` / `uv run ruff format --check` / `uv run mypy src` 全緑
- [ ] `logs/m2-acceptance-run.jsonl` に最低 1 シナリオ分の構造化ログ (envelope + memory write + latency_ms) が存在
- [ ] `handoff-to-macbook.md` に MacBook/Godot 側で実施すべき acceptance 項目が明記
- [ ] `.steering/20260418-implementation-plan/tasklist.md` の T19 行に「実行フェーズ完了」と本タスク PR 番号が併記
- [ ] 本タスクの PR がレビューを経て main に merge

## 関連ドキュメント

- `.steering/20260419-m2-integration-e2e/` — T19 設計フェーズ成果物一式 (PR #23)
  - `design.md` v2 採用 (契約先行 / Layer A-C 試験階層)
  - `scenarios.md` — 3 シナリオのナラティブ
  - `metrics.md` — 閾値の根拠
  - `integration-contract.md` — WS 契約 (T14 実装者向け)
  - `t20-acceptance-checklist.md` — runbook 形式チェックリスト
- `.steering/20260419-gateway-fastapi-ws/` — T14 実装 (PR #24)
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §4.4 MVP 検収条件
- `docs/development-guidelines.md` — テスト方針、CI

## 運用メモ

- **種類**: その他 (実装あり・アーキ判断なし、T19 設計で `/reimagine` 済み)
- **破壊と構築 (`/reimagine`) 適用**: **No**
  - 理由: T19 設計フェーズ (PR #23) で既に v1→v2 の `/reimagine` を適用済み。
    本タスクは確定した v2 設計に基づく skeleton の点灯と実行であり、設計判断は含まない。
    アーキ判断が必要な場面が出現したら個別に `/reimagine` 起動を検討。
- **次コマンド**: `/add-feature` (skeleton 点灯 + ログ取得の実装を伴うため)
- **担当機**: G-GEAR (現セッション)、MacBook 側検証は handoff-to-macbook.md で引き継ぎ

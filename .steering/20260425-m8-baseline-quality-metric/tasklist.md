# Tasklist — M8 Baseline Quality Metric (v2)

> L6 D1 precondition の残り半分。v1 → v2 で scope を圧縮、affinity は
> defer して別 spike (`m8-affinity-dynamics`) 起票予定。
> Plan mode + /reimagine 5 軸で既に確定、`decisions.md` D1-D5 参照。

## 準備

- [x] Plan mode + /reimagine 5 軸で v2 確定
- [x] `design.md` / `decisions.md` / `requirement.md` 整備
- [ ] feat branch `feat/m8-baseline-quality-metric` を main (0e2e50e) から切る
- [ ] L6 ADR decisions.md に `m8-affinity-dynamics` を D1 residual 追記

## 実装

### Phase 1: データ層 (bias_events)

- [ ] `src/erre_sandbox/memory/store.py`
  - CREATE TABLE `bias_events` を `create_schema()` に追加
  - INDEX ix_bias_events_persona on (persona_id, created_at)
  - `add_bias_event_sync(*, dialog_id, tick, agent_id, persona_id,
    from_zone, to_zone, bias_p) -> str` (UUID 生成、INSERT)
  - `async add_bias_event(...)` wrapper (to_thread)
  - `iter_bias_events(*, persona=None, since=None) -> Iterator[dict[str, object]]`

### Phase 2: sink 注入 (cognition + bootstrap)

- [ ] `src/erre_sandbox/cognition/cycle.py`
  - `BiasFiredEvent` dataclass 追加 (tick, agent_id, from_zone, to_zone,
    bias_p、dialog_id は None のまま渡す)
  - `_apply_zone_bias(..., bias_sink: Callable | None = None)` 追加、発火
    時に sink があれば event を call
- [ ] `src/erre_sandbox/bootstrap.py`
  - `_persist_bias_event` closure を追加 (runtime, memory を capture)
  - `runtime.agent_persona_id(event.agent_id)` で persona_id を解決
  - cognition cycle 生成パスに sink を注入

### Phase 3: 集計層 (evidence.metrics)

- [ ] `src/erre_sandbox/evidence/__init__.py` (package marker)
- [ ] `src/erre_sandbox/evidence/metrics.py`
  - `compute_self_repetition_rate(turns) -> float | None` (N=5 window、
    空データは None)
  - `compute_cross_persona_echo_rate(turns) -> float | None`
  - `compute_bias_fired_rate(events, run_duration_s, num_agents) -> float | None`
  - `aggregate(run_db_path: Path) -> dict` — 3 関数を呼び baseline JSON
    を組み立て、`affinity_trajectory: None` field を含む

### Phase 4: CLI

- [ ] `src/erre_sandbox/cli/baseline_metrics.py`
  - `register(subparsers)` + `run(args)` pattern
  - 引数: `--run-db <path>` (required)、`--out <path or "-">` (default "-")
  - JSON 出力 (`indent=2`、NaN/None は統一して null)
- [ ] `src/erre_sandbox/__main__.py`
  - `_SUBCOMMANDS` frozenset に `"baseline-metrics"` 追加
  - `_build_subcommand_parser` 内で import + register
  - cli() dispatch ルートを確認

## テスト (MacBook で完走)

- [ ] `tests/test_memory/test_store.py` — bias_events 3-4 本:
  - insert 単発
  - filter by persona
  - filter by since
  - iter 順序 (created_at ASC)
- [ ] `tests/test_cognition/test_cycle.py` — sink call テスト 1-2 本:
  - sink=None で既存動作維持
  - sink 指定時に発火で event 引数が正しい
- [ ] `tests/test_evidence/__init__.py` 新規
- [ ] `tests/test_evidence/test_metrics.py` — metric 純関数 5-8 本:
  - self_repetition 空データで None
  - self_repetition 既知 fixture で期待 trigram 率
  - cross_persona_echo fixture で期待値
  - bias_fired_rate 計算 (run_duration, num_agents, bias_p で正規化)
  - aggregate(db_path) で JSON shape 確認
- [ ] `tests/test_cli_baseline_metrics.py` (新規) — CLI round-trip:
  - `--help` で subcommand 表示
  - fixture DB → stdout JSON round-trip
  - 空 DB で全 metric が null

## 検証

- [ ] `uv run pytest tests/test_evidence/` PASS
- [ ] `uv run pytest tests/test_memory/test_store.py -k bias_event` PASS
- [ ] `uv run pytest tests/test_cognition/test_cycle.py -k bias_sink` PASS
- [ ] `uv run pytest tests/test_cli_baseline_metrics.py` PASS
- [ ] `uv run pytest` 全体 regression なし
- [ ] `git diff --stat main...HEAD` が src / tests / .steering のみ
- [ ] `grep 'SCHEMA_VERSION' src/erre_sandbox/schemas.py` → `0.5.0-m8` 維持
- [ ] `grep -rn "affinity" src/ | wc -l` → 1 (schemas.py:422 のみ)
- [ ] `grep 'pyarrow\|pandas' pyproject.toml` → ゼロ

## レビュー

- [ ] `code-reviewer` subagent で metric 関数と JSON schema をレビュー
- [ ] `security-checker` (PII が metric に混入しないか)

## ドキュメント (最小)

- [ ] `docs/architecture.md` の evidence layer 記述 (必要なら 1 行追加)

## 完了処理

- [ ] commit (`feat(evidence): M8 baseline quality metric (fidelity + bias_fired, affinity deferred)`)
- [ ] push + `gh pr create` (body で v2 scope と affinity defer 根拠を明示)
- [ ] L6 D1 を「baseline 固定済 (Mac impl 完、live は G-GEAR session 預り)」に更新
- [ ] memory ファイル `project_m7_beta_merged.md` を更新 (PR 番号、残 spike 1 本)

## G-GEAR acceptance (別セッション、本 PR merge 後)

- [ ] G-GEAR で 60-90s baseline run × 3-5 本 (bias_p=0.1 固定)
- [ ] 各 run で `erre-sandbox export-log` + `erre-sandbox baseline-metrics`
- [ ] `baseline.md` に平均 / 分散 / 代表値を table 化、M9 比較 reference 固定
- [ ] CSDG 単著閾値 (0.30 / 0.50) を参照値として並記

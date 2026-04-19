# T20 Acceptance Checklist (v0.1.0-m2)

MVP タグ `v0.1.0-m2` を打つ前に実施する最終チェック。
機械可読なリストは `src/erre_sandbox/integration/acceptance.py` の
`ACCEPTANCE_CHECKLIST` を参照。本ファイルは **operator が手動で実行する runbook**。

各項目の `id` は Python 側と 1 対 1 で対応する。

---

## カテゴリ: schema

### [ ] ACC-SCHEMA-FROZEN
**確認**: ControlEnvelope と Thresholds の `model_json_schema` が snapshot と一致
**実行**:
```bash
uv run pytest tests/test_integration/test_contract_snapshot.py -v
```
**合格**: 23 件 PASSED

---

## カテゴリ: runtime

### [ ] ACC-SCENARIO-WALKING
**確認**: S_WALKING が 3 連続実行で全て成功
**実行**:
```bash
uv run pytest tests/test_integration/test_scenario_walking.py --count 3 -v
```
**合格**: 全 test が PASSED を 3 回連続

### [ ] ACC-SCENARIO-TICK-ROBUSTNESS
**確認**: S_TICK_ROBUSTNESS で tick drop / reconnect に耐える
**実行**:
```bash
uv run pytest tests/test_integration/test_scenario_tick_robustness.py -v
```
**合格**: 全 test が PASSED、特に disconnect→reconnect 後の agent_id 継続

### [ ] ACC-LATENCY-P50
**確認**: p50 envelope latency ≤ `M2_THRESHOLDS.latency_p50_ms_max` (100ms)
**実行**: scenario 実行時のログから latency 系列を抽出
```bash
jq '.latency_ms' logs/m2-acceptance-run.jsonl | datamash perc 50
```
**合格**: 計算された p50 ≤ 100

### [ ] ACC-LATENCY-P95
**確認**: p95 envelope latency ≤ `M2_THRESHOLDS.latency_p95_ms_max` (250ms)
**実行**: 同上 p95
```bash
jq '.latency_ms' logs/m2-acceptance-run.jsonl | datamash perc 95
```
**合格**: p95 ≤ 250

### [ ] ACC-TICK-JITTER
**確認**: tick 周期の σ/μ ≤ `M2_THRESHOLDS.tick_jitter_sigma_max` (0.20)
**実行**: `WorldTickMsg` 受信間隔を計算
**合格**: σ/μ ≤ 0.20

### [ ] ACC-STATE-RANGE
**確認**: `AgentState.{arousal, valence, attention}` が閾値範囲内 (逸脱 0 件)
**実行**: scenario 実行中の AgentUpdateMsg を全件検査
**合格**: 逸脱 0 件

### [ ] ACC-CI-GREEN
**確認**: ruff check / ruff format --check / mypy src / pytest が main で緑
**実行**: GitHub Actions の main 最新ビルドを確認
**合格**: 全 job success

---

## カテゴリ: memory

### [ ] ACC-SCENARIO-MEMORY-WRITE
**確認**: S_MEMORY_WRITE で episodic 4 + semantic 1 件が sqlite-vec に書込
**実行**:
```bash
uv run pytest tests/test_integration/test_scenario_memory_write.py -v
```
**合格**: 全 test PASSED

### [ ] ACC-MEMORY-WRITE-RATE
**確認**: memory 書込み成功率 ≥ `M2_THRESHOLDS.memory_write_success_rate_min` (0.98)
**実行**: ログから attempt / success を集計
```bash
grep "memory.insert" logs/m2-acceptance-run.jsonl | \
  jq -s 'group_by(.outcome) | map({key:.[0].outcome, count:length})'
```
**合格**: `success / (success + failure)` ≥ 0.98

---

## カテゴリ: observability

### [ ] ACC-LOGS-PERSISTED
**確認**: 全 envelope と memory write のログが永続化されている
**実行**:
```bash
ls -la logs/ | grep m2-acceptance
```
**合格**: scenario 実行中のタイムスタンプ網羅、ファイルサイズが妥当

---

## カテゴリ: reproducibility

### [ ] ACC-REPRO-SEED
**確認**: ランダムシード固定で scenario が再現する
**実行**:
```bash
uv run pytest tests/test_integration/test_scenario_walking.py --seed 42
# 別シェルでもう一回
uv run pytest tests/test_integration/test_scenario_walking.py --seed 42
# diff を取る
diff logs/run1.jsonl logs/run2.jsonl
```
**合格**: AgentUpdateMsg 列が同値 (時刻以外)

---

## カテゴリ: docs

### [ ] ACC-DOCS-UPDATED
**確認**: `docs/architecture.md` の WS / Gateway セクションが T14 完成版に更新
**実行**: `git log --follow docs/architecture.md` を確認
**合格**: T14 関連の commit (scope: docs) が main に含まれる

### [ ] ACC-MASTER-PLAN-SYNC
**確認**: MASTER-PLAN tasklist の T14/T19/T20 が完了マーク + PR 番号併記
**実行**:
```bash
grep -E "^- \[x\] T1[4-9]|T20" .steering/20260418-implementation-plan/tasklist.md
```
**合格**: T14 / T19 / T20 すべてに `[x]` と PR 番号が併記されている

### [ ] ACC-TAG-READY
**確認**: CITATION.cff と pyproject.toml のバージョンが v0.1.0-m2 に一致
**実行**:
```bash
grep -E "0\.1\.0" CITATION.cff pyproject.toml
```
**合格**: 両ファイルに `0.1.0` が記載されている

---

## 最終タグ付け

全項目が合格したら:

```bash
git checkout main
git pull
git tag -a v0.1.0-m2 -m "ERRE-Sandbox M2 MVP: 1 agent × 1 zone integration"
git push origin v0.1.0-m2
gh release create v0.1.0-m2 --title "v0.1.0-m2" --notes-file docs/release-notes/v0.1.0-m2.md
```

## ロールバック

タグ付け後に重大な問題が発覚した場合:

```bash
git tag -d v0.1.0-m2
git push origin :refs/tags/v0.1.0-m2
gh release delete v0.1.0-m2 --yes
```

修正後に新タグ `v0.1.1-m2` として再公開する (同一バージョン番号の再利用は避ける)。

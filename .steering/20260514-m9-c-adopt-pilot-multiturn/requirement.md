# m9-c-adopt pilot multi-turn investigation

## 背景

- PR #165 (2026-05-14 merge) で M9-C-adopt Phase B が closure、DA-12 verdict =
  DEFER 確定。Phase B 第 4 セッション (Big5 ICC + Burrows Option A + semantic
  Vendi 揃い) の matrix で **DA-1 4 軸 intersection 2-of-4 PASS のみ** (ICC +
  throughput)、Vendi semantic + Burrows Δ は全 rank で **direction failure**
  (LoRA-on > baseline、DA-1 hypothesis "LoRA-on < no-LoRA" と逆方向)。
- DA-12 hot decision: 2 因子 (a) **pilot single-turn vs baseline multi-turn
  methodology confound**、(b) **LoRA が IPIP self-report neutral midpoint を実質
  shift しない** は pilot data 単独で identifiability 不能。pilot を multi-turn
  採取に拡張すれば direction failure の主因が切り分け可能。

## ゴール

DA-12 で identifiability 不能と認定された 2 因子のうちどちらが dominant かを
**multi-turn pilot data で empirical に判定** し、後続経路 (retrain v2 /
Phase E A-6 direct / Phase E A-6 amended / Phase E direct) を確定する。

## スコープ

### 含むもの

- `scripts/m9-c-adopt/tier_b_pilot.py` を multi-turn 採取可能に拡張
- 3 rank × 2 run × 300 focal turn の multi-turn pilot 採取 (6 shard、新 directory)
- 既存 consumer (Vendi semantic / Big5 ICC / Burrows Δ) を multi-turn shard
  に対して走らせて 3 metric × 3 rank の値を artefact 出力
- `da1_matrix.py` を multi-turn 行 inclusion 可能に拡張、4 軸 intersection 再評価
- DA-13 ADR (5 要素 + シナリオ判定 + 後続経路) 起票
- `blockers.md` U-6 status update + 後続 PR の next-session-prompt 起草

### 含まないもの

- nietzsche / rikyu の同 investigation (Phase C 着手前に再 fire 必要)
- `MultiBackendChatClient` 実装 (Phase D)
- production loader `_validate_adapter_manifest()` (Phase F)
- FSM smoke 24 cell (Phase E)
- Phase E A-6 7500-turn full Tier B 採取 (別 PR)
- retrain v2 (min_examples 3000) (別 PR、本 PR は「retrain v2 が必要か」を
  empirical に判定するのみ)

## 受け入れ条件

- [ ] `tier_b_pilot.py` multi-turn 拡張 + `--multi-turn-max N` flag (default 1 で
      過去互換)、stimulus YAML `expected_turn_count` を尊重、baseline と同
      protocol (`GoldenBaselineDriver` ベース) で alternating speaker 生成
- [ ] multi-turn pilot 採取 (3 rank × 2 run × 300 focal turn = 6 shard) 完遂
- [ ] Vendi semantic / Big5 ICC / Burrows Δ 全 3 metric × 3 rank 再算出
- [ ] DA-1 4 軸 intersection matrix 再集約 + Cohen's d diagnostic
- [ ] `decisions.md` DA-13 ADR 起票 + シナリオ判定 + 後続経路明示
- [ ] `blockers.md` U-6 status update
- [ ] 新 branch `feature/m9-c-adopt-pilot-multiturn-investigation`、commit
      + push + `gh pr create` (PR description に matrix + DA-13)
- [ ] シナリオ別の次セッション prompt 起草

## シナリオと後続経路

| シナリオ | multi-turn pilot vs baseline | 結論 | 後続経路 |
|---|---|---|---|
| **I (A 優位)** | direction が逆転 (LoRA-on Vendi < baseline) | methodology confound dominant | DA-12 close、Phase E A-6 direct、retrain v2 skip |
| **II (B 優位)** | direction 変わらず (LoRA-on > baseline) | LoRA failure dominant | DA-12 close、feature/m9-c-adopt-retrain-v2 経路 confirmed |
| **III (両者)** | direction 改善するが thresholds 未達 | 両因子寄与、両者修正必要 | DA-12 partial close、Phase E A-6 内で multi-turn protocol + retrain v2 を combine |
| **IV (新情報なし)** | multi-turn 採取 fail or CI 広すぎる | identifiability 不能のまま | DA-12 維持、Phase E A-6 7500-turn が唯一の closure path |

## 関連ドキュメント

- `.steering/20260513-m9-c-adopt/decisions.md` DA-1 / DA-9 / DA-11 / DA-12
- `.steering/20260513-m9-c-adopt/phase-b-report.md`
- `.steering/20260513-m9-c-adopt/da1-matrix-kant.json` (PR #165 baseline)
- `.steering/20260513-m9-c-adopt/blockers.md` U-6
- `scripts/m9-c-adopt/tier_b_pilot.py` (拡張対象)
- `src/erre_sandbox/evidence/golden_baseline.py` (baseline driver reference)
- `src/erre_sandbox/cli/eval_run_golden.py` (baseline inference_fn 設計 reference)
- `docs/runbooks/m9-c-adapter-swap-runbook.md` (SGLang launch SOP、`--max-lora-rank 16` amendment)

# experiments/20260701-es4-scorer-diag

M13-ES4 **scorer offline diagnostic** (方向 C)。Phase 0 = INVALID_SCORER を受け、既取得 Phase A データ +
凍結 holdout 上で「(a1)(a2) を非循環に通す候補 scorer が存在するか」を **GPU 追加ゼロ** で検証する。

## 構成
- `diagnostic.json` — per-candidate metrics + forensic + decision (go/no-go)。
- `run.sh` — 1 コマンド再現 (CPU のみ)。

## 実行
```bash
bash experiments/20260701-es4-scorer-diag/run.sh
# or:
PYTHONPATH=src python scripts/es4_scorer_diag.py \
  --run-dir experiments/20260630-es4-phase0/phaseA \
  --out experiments/20260701-es4-scorer-diag/diagnostic.json
```

## 入力 (read-only、凍結)
- `experiments/20260630-es4-phase0/phaseA/{generations,judgements,scores}.jsonl` (Phase A 永続データ)。
- `src/erre_sandbox/evidence/es4_actuator/data/{adversarial_labeled,common_uses,aut_battery}.yaml` (凍結 battery)。
- harness は凍結 apparatus を **read-only 再利用** (改変なし)。

## 結果 (2026-07-01)
**VERDICT = NO_VALID_SCORER → 方向 B (arc pivot)**。embedding rarity 族は全て leave-anchor-out audit で
floor 未満に崩落 (Codex HIGH-1 の anchor 循環性の実証)、唯一 RARITY_OK を通した lexical Jaccard も entropy 還元
可能 + 効果 floor 未満。詳細 = `.steering/20260701-m13-es4-scorer-diagnostic/diagnostic-report.md`。

## 注記
- GPU 不使用。alt encoder (C3: MiniLM / e5-small / bge-small) は初回 model download に network を要する。
  offline では graceful skip され、結論は不変。
- 凍結 apparatus 不変 (`git status` で `src/erre_sandbox/evidence/` 変更ゼロ)。

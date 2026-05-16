# m9-c-adopt Plan B eval generation + verdict 計算

## 背景

PR #181 (`feature/m9-c-adopt-plan-b-retrain`、merge SHA `f68ac63`) で
Plan B retrain artifact (`data/lora/m9-c-adopt-v2/kant_r8_v3/checkpoint-1500/`、
eval_loss=0.18259) が生成された。続く PR #183 (prep PR、merge 済) で
retrain artifact の forensic JSON tracking と、eval shard 不在 blocker
(`kant_r8v3_run*_stim.duckdb` が repo 内に **未生成**) の明文化が行われた
(`.steering/20260518-m9-c-adopt-plan-b-verdict/blockers.md` ブロッカー 1)。

本 PR (`feature/m9-c-adopt-plan-b-eval-gen`) は、その blocker を解消し
Plan B verdict (kant ADOPT or Phase E A-6 (rank=16) 移行) を確定させる。

retrain (model 学習) と eval generation (推論で stim 応答採取) は別工程
であり、retrain だけでは verdict 計算は走れない。本 PR で SGLang adapter
serve → stim 推論で shard 採取 → 4 encoder rescore → Burrows/ICC/throughput
→ verdict aggregator → ADOPT/REJECT 判定までを一気通貫で実行する。

## ゴール

- Plan B LoRA-on shards (`kant_r8v3_run{0,1}_stim.duckdb`) と Plan B no-LoRA
  control shards (`kant_planb_nolora_run{0,1}_stim.duckdb`) を生成
- 4 encoder rescore (MPNet / E5-large / lexical-5gram primary、BGE-M3
  exploratory) の JSON output 生成
- Burrows reduction% / ICC(A,1) / throughput pct of baseline を計算
- verdict aggregator (`da14-verdict-plan-b-kant.json` + `.md`) で encoder
  agreement axis (3-of-4 primary のうち 2 以上) を判定
- **kant ADOPT or Phase E A-6 (rank=16) 移行決定**を decisions.md に記録
- Codex independent review を起票し HIGH/MEDIUM/LOW を verbatim 保存
- pre-push CI parity check (4 段全 pass) → commit + push + `gh pr create`

## スコープ

### 含むもの

1. `feature/m9-c-adopt-plan-b-eval-gen` branch を main から分岐
2. `.steering/20260516-m9-c-adopt-plan-b-eval-gen/` 5 標準 file
3. `scripts/m9-c-adopt/rescore_vendi_alt_kernel.py` の CLI flag 拡張
   (blocker 2 解消):
   - `--v2-shards` / `--nolora-shards` kw-only flag 追加 (default は
     既存 hard-coded path、backward-compat)
   - `--kernel-type` flag 追加 (`semantic` default、`lexical_5gram` で
     `_load_default_kernel(kernel_type='lexical_5gram')` 経由)
   - test 追加 (`tests/test_scripts/test_rescore_vendi_alt_kernel_cli.py`)
4. SGLang server (K-α launch v5 invocation) を G-GEAR WSL2 で起動、
   `kant_r8v3` adapter を `--lora-paths` で load
5. Plan B eval shard 生成 (~5h GPU overnight):
   - LoRA-on × 2 (run0, run1): `tier_b_pilot.py --rank 8 --turn-count 300
     --cycle-count 6 --multi-turn-max 6`
   - no-LoRA × 2 (run0, run1): `--no-lora-control --rank 0` + 同 protocol
6. shard 検証 (`validate_multiturn_shards.py`)
7. 4-encoder rescore (~1-2h CPU):
   - MPNet (primary): `--encoder sentence-transformers/all-mpnet-base-v2
     --kernel-type semantic`
   - E5-large (primary): `--encoder intfloat/multilingual-e5-large
     --kernel-type semantic`
   - lexical-5gram (primary): `--kernel-type lexical_5gram` (encoder
     argument は dummy/conditional skip)
   - BGE-M3 (exploratory): `--encoder BAAI/bge-m3 --kernel-type semantic`
8. Burrows / ICC / throughput 計算
9. verdict aggregator (新規 `da14_verdict_plan_b.py` or `da15_verdict.py`
   拡張) で `da14-verdict-plan-b-kant.{json,md}` emit
10. **kant ADOPT or Phase E A-6 判定**:
    - 全 gate pass → ADOPT、`decisions.md` DR-? に記録
    - 1 axis fail → Phase E A-6 (rank=16 spike) 移行、DA-16 ADR 起票候補
11. Codex independent review (~30 min)
12. pre-push CI parity check + commit + push + `gh pr create`

### 含まないもの

- nietzsche / rikyu の Plan B 展開 (kant ADOPT 後の別 PR)
- WeightedTrainer Blocker 2 (sample weight collapse) の修正
  (Plan B verdict ADOPT なら保留、REJECT なら別 PR で優先)
- 新規 retrain (kant_r8_v3 checkpoint-1500 を verdict 判定用に使う、
  別 checkpoint や rank=16 spike は本 PR scope 外、ADR DA-16 として
  別 PR で起票)

## 受け入れ条件

- [ ] `feature/m9-c-adopt-plan-b-eval-gen` branch (main 派生)
- [ ] `.steering/20260516-m9-c-adopt-plan-b-eval-gen/` 5 標準 file
- [ ] `rescore_vendi_alt_kernel.py` CLI flag 拡張 + test
      (`tests/test_scripts/test_rescore_vendi_alt_kernel_cli.py`)
- [ ] Plan B eval shards 4 個 (LoRA-on × 2 + no-LoRA × 2、SGLang stim
      protocol が v2 baseline と apples-to-apples)
- [ ] `validate_multiturn_shards.py` で alternation + row count + multi-turn
      整合性 PASS
- [ ] 4-encoder rescore JSON: `da14-rescore-{mpnet,e5large,lex5,bgem3}-
      plan-b-kant.json`
- [ ] Burrows / ICC / throughput verdict 計算
- [ ] verdict aggregator JSON + MD: `da14-verdict-plan-b-kant.json` +
      `da14-verdict-plan-b-kant.md`
- [ ] kant ADOPT or Phase E A-6 判定 + `decisions.md` DR-? に記録
- [ ] Codex independent review 起票 + `codex-review.md` verbatim
- [ ] `pre-push-check.sh` または `.ps1` 4 段全 pass 確認
- [ ] commit + push + `gh pr create`
- [ ] **ADOPT 時**: nietzsche / rikyu の Plan B 展開 next-session prompt
      起票
- [ ] **Phase E A-6 移行時**: DA-16 ADR 起票 (rank=16 spike)

## 関連ドキュメント

- `.steering/20260518-m9-c-adopt-plan-b-verdict/decisions.md` DV-1〜DV-3
- `.steering/20260518-m9-c-adopt-plan-b-verdict/blockers.md` ブロッカー 1/2
- `.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md` DR-1〜DR-7
- `.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json`
- `src/erre_sandbox/evidence/tier_b/vendi_lexical_5gram.py`
- `src/erre_sandbox/evidence/tier_b/vendi.py` L312-378
  (`_load_default_kernel(kernel_type=...)` dispatch)
- `scripts/m9-c-adopt/rescore_vendi_alt_kernel.py` (改修対象)
- `scripts/m9-c-adopt/tier_b_pilot.py` (eval generation driver)
- memory `reference_qwen3_sglang_fp8_required.md` (SGLang DR-4)
- memory `feedback_pre_push_ci_parity.md` (push 前 4 段 check)
- memory `feedback_retrain_handoff_must_include_eval_gen.md` (本 PR
  の reflection 起点)
- `CLAUDE.md` 「禁止事項」(pre-push CI parity + extras-only 3 点セット)

## 運用メモ

- 破壊と構築（/reimagine）適用: No
- 理由: 本 PR は既存 design.md の §1.2 9 step が明確に確定しており、
  実装の選択肢に大きな分岐がない (CLI flag pattern は blocker 2 で
  既に Option (a) `--v2-shards`/`--nolora-shards` を推奨確定)。
  ただし lexical_5gram の rescore 内 dispatch (pool-fit vs per-window
  fit) は技術判断が必要 → decisions.md DE-? として明記する。

Verdict: ADOPT-AS-IS

**(a) Forensic 一貫性**
- HIGH: none
- MEDIUM: none
- LOW: none

`train_metadata.json` は v3/v4 とも top-level 26 keys、recursive schema も一致。v4 は `eval_loss=0.18046319484710693`、`weighted=true`、`lora_rank=8`、`max_steps=2500`、`quantization=nf4`、`batch_size=1`、`gradient_accumulation_steps=8`、`metadata.seed=42` が記録済み: [train_metadata.json](/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v4/train_metadata.json:20)。

best step は `checkpoint-2000/trainer_state.json` で `best_global_step=2000` / `best_metric=0.18046319484710693` と確認: [trainer_state.json](/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v4/checkpoint-2000/trainer_state.json:2)。`metadata.audit_*` と corpus gate / weight audit の `de_en_mass`、`n_eff`、`top_5_pct_weight_share` も一致: [plan-b-corpus-gate.json](/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v4/plan-b-corpus-gate.json:3)、[weight-audit.json](/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v4/weight-audit.json:37)。

**(b) v3/v4 eval_loss 直接比較**
- HIGH: none
- MEDIUM: none
- LOW: none

直接比較は妥当。eval examples は `sample_weight=1.0`: [train_kant_lora.py](/mnt/c/ERRE-Sand_Box/src/erre_sandbox/training/train_kant_lora.py:761)。eval batch は `per_device_eval_batch_size=1`: [train_kant_lora.py](/mnt/c/ERRE-Sand_Box/src/erre_sandbox/training/train_kant_lora.py:1728)。loss reducer は `(per_example_loss * weights).mean()`: [weighting.py](/mnt/c/ERRE-Sand_Box/src/erre_sandbox/training/weighting.py:514)。

v3 best `0.18258875608444214` @ step 1500、v4 best `0.18046319484710693` @ step 2000。差分は `-0.002125561237335205` で、PR description の `-0.00213` 主張と整合。

**(c) DP3-1 HF push 後送り**
- HIGH: none
- MEDIUM: none
- LOW: none

現方針は論理的に優位。案 A は「公開行為は verdict 後」「REJECT 時 cleanup ゼロ」を明記し、案 B の delete/rename コストと比較済み: [decisions.md](/mnt/c/ERRE-Sand_Box/.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/decisions.md:25)。local path 依存リスク、v3/v4 非対称、外部研究者再現性の caveat も記録済み: [decisions.md](/mnt/c/ERRE-Sand_Box/.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/decisions.md:60)、[decisions.md](/mnt/c/ERRE-Sand_Box/.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/decisions.md:69)、[decisions.md](/mnt/c/ERRE-Sand_Box/.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/decisions.md:97)。

Local binary は現時点で存在確認済み。`adapter_model.safetensors` と best checkpoint は各 30 MB。

**(d) .gitignore / staged artifact**
- HIGH: none
- MEDIUM: none
- LOW: staged total size note only

`.gitignore` patterns are correct for all requested binary/model-side paths: [`.gitignore`](/mnt/c/ERRE-Sand_Box/.gitignore:74)。`git check-ignore -v` confirmed adapter, checkpoints, tokenizer, chat template, and README are ignored.

v3 tracked set and v4 staged set are symmetric: `adapter_config.json`, `plan-b-corpus-gate.json`, `train_metadata.json`, `weight-audit.json`. No binary is staged; `git diff --cached --numstat` reports text-only additions.

LOW note: staged text payload is `27,887` bytes total because the five `.steering` files are ~21 KB. The four forensic JSON files alone are `6,892` bytes, so the “~10 KB” expectation is true for JSON artifacts but not for JSON + steering combined. No action required unless you want the wording tightened.

Checks run: staged diff/stat/name-only/numstat, Python JSON schema comparison, trainer_state inspection, `git check-ignore -v`, and `git diff --cached --check`. Sandbox is read-only, so I did not save this report into `codex-review.md`.

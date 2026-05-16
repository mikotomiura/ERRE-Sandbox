# Codex independent review prompt — DA-15 Phase 1 implementation

## 役割

Project ERRE-Sandbox (Apache-2.0 OR MIT) の **m9-c-adopt DA-15 Phase 1
implementation** PR の independent reviewer。Verdict は `ADOPT` /
`ADOPT-WITH-CHANGES` / `REJECT`、severity 階層は `HIGH` / `MEDIUM` / `LOW`。

## 文脈

DA-14 verdict (`.steering/20260515-m9-c-adopt-retrain-v2-verdict/da14-verdict-
v2-kant.json`) は kant retrain v2 を REJECT した。primary axis 1-of-3 (ICC
PASS、Vendi d=-0.18 / Burrows +0.43% は閾値未達、throughput PASS)。

`.steering/20260516-m9-c-adopt-da15-adr/` で DA-15 ADR (Plan A = Vendi
kernel swap、Plan B = Candidate C targeted hybrid sequential、Hybrid H-α
pre-staging) を起票し、ADOPT-WITH-CHANGES verdict + HIGH-1 (versioned
metric) / HIGH-2 (calibration panel) / MEDIUM 3 件 / LOW-1 を全反映済 (PR
#177 merged)。

本 PR は **Phase 1 = Plan A** の literal 実装。新規 training なし、新規 data
採取なし、measurement-side swap のみ。DA-14 thresholds は不変、新 metric
`vendi_semantic_v2_encoder_swap` を versioned 起こす。MPNet `vendi_semantic`
は historical record として併報告。

## Review 対象

`feature/m9-c-adopt-da15-implementation` branch (本 PR) の diff vs `main`。
特に以下を確認:

1. **`src/erre_sandbox/evidence/tier_b/vendi.py`** — `_load_default_kernel(
   encoder_name=None)` 引数化、MPNet default 維持、E5 prefix 自動 handling
2. **`scripts/m9-c-adopt/compute_baseline_vendi.py`** — `--encoder` CLI、
   kernel_name 切替 (DA-14 baseline は `semantic`、それ以外は
   `semantic_v2_encoder_swap`)
3. **`scripts/m9-c-adopt/da15_calibration_panel.py`** — Kant + Nietzsche
   control corpus を language-stratified に build (Codex HIGH-2)、各 encoder
   で AUC ≥ 0.75 + within-language AUC ≥ 0.75 を gate
4. **`scripts/m9-c-adopt/rescore_vendi_alt_kernel.py`** — v2 + no-LoRA を
   apples-to-apples で再 score、standard / language-balanced / length-
   balanced bootstrap + within-language d
5. **`.steering/20260516-m9-c-adopt-da15-impl/decisions.md` D-2** — encoder
   + HF revision SHA + library version pre-registration (Codex HIGH-1)
6. **`scripts/m9-c-adopt/da1_matrix_multiturn.py`** — comparator switch
   (MATCHED HISTORICAL Ollama → no-LoRA SGLang)
7. **DA-15 verdict 文書** — `da15-verdict-kant.json` + `da15-verdict-kant.md`、
   Burrows named limitation 記載 (Codex LOW-1)

## 報告フォーマット

ADR PR (`.steering/20260516-m9-c-adopt-da15-adr/codex-review.md`) と同等の
形式:

```
[HIGH-1] <title>
- Finding: <一言要約>
- Why it matters: <なぜ blocker か>
- Fix: <具体的修正>
- Severity rationale: <HIGH の理由>

[HIGH-2] ...
...
[MEDIUM-1] ...
...
[LOW-1] ...

Verdict: ADOPT / ADOPT-WITH-CHANGES / REJECT
```

## Review focus

特に以下の観点で:

### HIGH-3 遵守
- DA-14 thresholds (d ≤ -0.5、CI upper < 0、point Burrows ≥ 5%、ICC ≥ 0.55)
  が **不変** で、新 metric だけが追加されているか
- MPNet `vendi_semantic` が **historical record** として保持され、新 metric
  `vendi_semantic_v2_encoder_swap` と並列報告されているか
- "DA-14 fail のまま DA-15 pass" の文書化が十分か

### HIGH-1 pre-registration
- encoder + revision SHA が rescore 実行 **前** に decisions.md D-2 に固定
  されているか (git history で trace 可能か)
- exploratory encoders (philosophy-domain BERT 等) が ADOPT 寄与から除外
  されているか

### HIGH-2 calibration / balancing
- calibration corpus が language-stratified に build されているか (Codex の
  「encoder が language ID を拾ってないか」検証)
- AUC ≥ 0.75 gate が **overall + within-language 両方** で適用されているか
- balanced bootstrap (language / token length) が実装されているか
- within-language d (d_de, d_en, d_ja) が報告されているか

### LOW-1 Burrows named limitation
- kant ADOPT 時の verdict 文書に「Burrows reduction remains FAIL; German
  function-word stylometry is not improved」を含む limitation 記載が
  あるか

### コード品質
- backward compatibility (既存 callers が引数なしで MPNet を使い続けられるか)
- error handling (encoder load 失敗、pool too small 等)
- reproducibility (seed=42、bootstrap deterministic、HF revision pin)

### Statistical soundness
- cohens_d 計算の正確性 (pooled SD)
- bootstrap CI の coverage validity
- 6 windows × 2 conditions という小 sample で d ≤ -0.5 + CI upper < 0 を
  満たすために必要な effect size の現実性
- stratified bootstrap の stratum quota allocation

## 出力先

`.steering/20260516-m9-c-adopt-da15-impl/codex-review.md` に verbatim 保存。
要約しない。

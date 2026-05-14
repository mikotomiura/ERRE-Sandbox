# Codex review — m9-c-adopt retrain v2 spec design

You are reviewing the **design-only** PR for `feature/m9-c-adopt-retrain-v2-design`.
Training execution is NOT in this PR's scope; only the spec, corpus analysis,
DA-14 thresholds, and handoff prompt are. Your verdict drives whether the
spec ships as-is, ships with HIGH-marked changes, or is rejected.

## 1. Background (essential context — 内面化必須)

### 1.1 PR #166 DA-13 Backend Confound Discovery (前 PR で empirical 確定)

Multi-turn pilot investigation で以下を empirical 確定:

- **Direction failure 主因 = backend confound (Ollama → SGLang)**, NOT LoRA failure
- backend confound magnitude: Vendi **+2.144** / Burrows **+5.391** (matched
  Ollama baseline 31.167 → no-LoRA SGLang baseline 33.311)
- **LoRA effect proper** (rank=8 no-LoRA SGLang vs LoRA-on SGLang): Vendi
  **+0.446** / Burrows **-0.960** — **near-zero, direction-mixed**
- Cohen's d for rank=8 LoRA effect ≈ +2.17 against matched Ollama (wrong
  direction), but factor-decomposition shows backend confound dominates

Reference artefacts (verbatim values come from these JSONs):
- `.steering/20260514-m9-c-adopt-pilot-multiturn/da1-matrix-multiturn-kant.json`
- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json`
- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-burrows.json`
- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-icc.json`

### 1.2 既存 K-β rank=8 LoRA の現状

`data/lora/m9-c-adopt/archive/rank_8/kant/train_metadata.json`:
- base_model = Qwen/Qwen3-8B, lora_rank=8, quantization=nf4 + double quant
- `min_examples_threshold = 1000` (CS-3 SLO)
- **`realised_examples = 5022`** — **5x margin で既に実施済**
- shard_stats: 10 shards (natural 2,502 + stimulus 2,520)
- train_loss = 0.2155 (3.488 → 0.128 で 27x improvement、収束済)
- max_seq_length=2048, max_steps=2000, target_modules=[q,k,v,o_proj], lora_alpha=16

つまり **DA-9 の literal "min_examples 1000 → 3000"** 解釈は不正確で、
volume framing は empirical evidence で defeat される (5022 ≫ 1000)。

### 1.3 Step 1 corpus 特性分析 finding (本 PR で実施)

`scripts/analysis/analyze_kant_training_corpus.py` で 5,022 examples を
re-extract、5 metrics 算出 (`corpus-analysis-kant.json` verbatim 抜粋):

| Gap | 観測値 | 詳細 |
|---|---|---|
| **C1: 日本語 56.7%** | ja=2847, de=798, en=1296, mixed=81 | langdetect 不使用、独語 diacritics + 関数語 + kana/kanji heuristic |
| **C2: short 69.0%** | <30 tokens dominate、max=132 | whitespace×1.3 proxy (Qwen3-8B tokenizer 不利用) |
| **C3: monolog 0%** | dialog=100%、top addressees: interlocutor 2520, nietzsche 1258, rikyu 1244 | 全 5022 が addressee 付き |
| **C4: marker 0.76x** | combined 1.52 (anchor 2.0)、self-ref 0.30、Kantian 1.23、median 0.00 | regex-based markers |

**統合解釈**: effective discriminative signal ≈ 5% (~250 examples、de × ≥30
token × non-zero marker)。これが LoRA effect proper near-zero の mechanism。

Caveat: tokenizer は **whitespace × 1.3 proxy** (Qwen3-8B tokenizer は
training extras 配下で本環境では不在)、language は **simple character-set
heuristic** (langdetect 非 dep)。distribution shape は妥当だが absolute
counts は ±10-20% 誤差ありうる。

## 2. レビュー対象成果物 (本 PR design-only)

以下を必ず Read してから review:

- `.steering/20260514-m9-c-adopt-retrain-v2-design/design-final.md` — **本 review の主対象**
- `.steering/20260514-m9-c-adopt-retrain-v2-design/corpus-analysis-kant.md` — Step 1 finding (human-readable)
- `.steering/20260514-m9-c-adopt-retrain-v2-design/corpus-analysis-kant.json` — Step 1 finding (machine-readable)
- `.steering/20260514-m9-c-adopt-retrain-v2-design/requirement.md`
- `.steering/20260514-m9-c-adopt-retrain-v2-design/design.md` (4 falsifiable claims)
- `.steering/20260514-m9-c-adopt-retrain-v2-design/decisions.md` (DR-1: signal-driven preferred)
- `.steering/20260513-m9-c-adopt/decisions.md` DA-9 (元 spec), DA-12 (direction failure), DA-13 (backend confound)
- `.steering/20260514-m9-c-adopt-pilot-multiturn/decisions.md` (D-1 Codex HIGH 4 件、PR #166)
- `.steering/20260514-m9-c-adopt-pilot-multiturn/report.md` (4-axis matrix + factor decomposition)
- `scripts/analysis/analyze_kant_training_corpus.py` (Step 1 implementation)
- `tests/test_analysis/test_kant_corpus.py` (3-case smoke、green)
- `src/erre_sandbox/training/dataset.py` / `train_kant_lora.py` (production filter chain / 4-種 hard-fail gate)

## 3. 採用 spec 要旨 (verbatim は design-final.md)

**Candidate B (signal-driven) 採用** (3 candidates 比較は design-final.md §2):

- data: 5022 維持 (新規採取なし) + per-example weight column 追加
- weighting formula (clamped `[0.1, 3.0]`):
  ```
  weight = lang_factor * 0.35 + length_factor * 0.20
         + monolog_bonus * 0.15 + marker_factor * 0.30
  ```
  - lang: de=1.4, en=1.0, mixed=0.5, ja=0.2
  - length: <30=0.3, 30-59=0.8, 60-119=1.5, 120+=2.0
  - monolog_bonus: addressee=None → 1.5, else 1.0
  - marker_factor: max(density/2.0, 0.2)
- diversity injection: natural shards から 2-turn 連続 Kant utterance を
  monolog re-cast (~150-300 synthetic examples、`dialog_id="<orig>_mono"`
  で分離、`epoch_phase=training` 維持)
- rank=8 固定、PEFT setup PR #163 K-β baseline 同一
- max_steps=4000 (旧 2000 の 2x、weighted batch の effective LR scaling)
- compute envelope: 3-5h training + 1h pilot recapture + 30min consumer/matrix
  ≈ 5-7h G-GEAR overnight、abort >8h

**DA-14 thresholds 方向性** (Step 4 で正式起票):
- Vendi: Cohen's d ≤ **-0.5** vs no-LoRA SGLang baseline (旧 0.3 vs Ollama)
- Burrows reduction: ≥ **5%** + CI lower > 0 (旧 10% 緩和)
- ICC(A,1) primary: ≥ **0.55** + CI lower ≥ 0.50 (旧 ICC(C,k) → diagnostic)
- throughput ≥ 70% (不変)

## 4. レビュー軸 — 各々 ADOPT / MODIFY / REJECT を返答すること

### HIGH (即反映、design-final.md 編集トリガー)

**HIGH-A**: training data sourcing operational risk

Step 1 で realized=5022 と判明し、DA-9 literal volume framing は defeat
された。Candidate B (signal-driven、新規採取 0h) で十分か、Candidate C
(hybrid、+2500 turn 採取 3h) が overfit 回避に必要か?

特に懸念: weighted loss が同じ examples を異 weight で繰り返し露出させる
ことで、stylistic shortcut overfit (Kant-stripe-pattern memorisation) を
誘発する risk。Candidate B でこれを回避する手段が validation split (10%
holdout) のみで十分か、追加で hybrid 採取が必須か。

**HIGH-B**: G-GEAR overnight compute feasibility

16GB-class GPU + QLoRA NF4 + rank=8 + max_steps=4000 + sample_weight
collator (HF Trainer 標準 `sample_weight` 拡張) + 5022 examples で、3-5h
training が現実的か。**実 K-β baseline** (PR #163) は max_steps=2000 で
peak_vram=10.55GB を観測、本 spec の 2x step + weight column overhead が
12GB 安全 margin を超過する risk があるか。

**HIGH-C**: weight 式 statistical soundness

4-factor linear weighted sum + clamp `[0.1, 3.0]`:

```
weight = lang * 0.35 + length * 0.20 + monolog * 0.15 + marker * 0.30
```

- gradient variance blowup risk (clamp 30x range): focal loss γ=2 相当か?
- mode collapse risk: ja down-weight 0.2 で de+en に over-fit する確率
- HF Trainer の `sample_weight` 標準パス (`per_sample_weight` collator) で
  CE loss に渡す形式が gradient 計算上正しいか
- weight 構成の sum-of-coefficients = 1.0 (interpretable) で、各 factor の
  weight (0.35 / 0.20 / 0.15 / 0.30) が empirical evidence から導出か、
  arbitrary か

prior art として focal loss (Lin 2017)、curriculum learning (Bengio 2009)、
DAP (Direct Preference Personalization) のうちどれが closest match か。

**HIGH-D**: DA-14 thresholds empirical justification

LoRA effect proper near-zero (rank=8 で Vendi +0.446 / Burrows -0.960) を
踏まえた新 threshold (Cohen's d ≤ -0.5 / Burrows ≥ 5% / ICC(A,1) ≥ 0.55) が:

- (a) signal-driven (Candidate B) で達成可能か
- (b) かといって既存 ICC(C,k) >0.97 のように uninformative にならないか
- (c) Burrows 5% は literature shoulder 5-15% の下限、ambitious 過ぎないか
- 4 axis intersection (2-of-3 quorum) で kant ADOPT 確率 がどれくらいか

### MEDIUM (decisions.md 採否記録)

**MEDIUM-1**: Step 1 corpus analysis の metric coverage

5 metrics (token / self-ref / dialog / stim-coverage / language) で gap
finding 十分か、以下のうち追加すべきものはあるか:

- n-gram entropy (lexical diversity proxy)
- TTR (type-token ratio)
- subordinate clause depth (syntactic complexity)
- BPE-fragmentation rate (qwen tokenizer-side metric)
- semantic embedding clustering (上位概念分布)

特に tokenizer は whitespace × 1.3 proxy で、ja CJK chars は 1:1 で count
(qwen tokenizer は ja を sub-char で割る可能性あり、actual token 数は ±20%
誤差)。proxy 妥当性に重大な問題があるか?

**MEDIUM-2**: weighted overfit risk (HIGH-A の補強)

- validation split 10% (Trainer の `eval_dataset` 経由) + early stopping で
  sufficient か
- weight 計算 metadata (lang / length / marker_density) を training data に
  artificially leak させていないか
- ja down-weighting が `Trainer.compute_loss` の reduction='mean' default
  と互換か (weighted-sum vs weighted-mean 混在懸念)

**MEDIUM-3**: monolog re-cast の eval intent leak risk

natural shards から t=5, t=7 (Kant 2 turns) を `addressee=None` で結合し
synthetic monolog 化 (~150-300 examples、`dialog_id="<orig>_mono"` で分離):

- 元 dialog_id と分離するだけで eval contamination が防げるか
- 元 evaluation_phase 行が混入しないか (`build_examples` の epoch_phase
  filter で除外されるが、synthetic 行は再度 phase 付与する設計)
- monolog re-cast が **semantic duplicate** を生む懸念 (元 t=5,7 turn が
  既に corpus にあり、追加で結合 turn を入れる)

### LOW (blockers.md 持ち越し可)

**LOW-1**: ADR cross-link consistency between
`.steering/20260513-m9-c-adopt/decisions.md` (DA-14 append) と
`.steering/20260514-m9-c-adopt-retrain-v2-design/decisions.md` (DR-1, DR-2)

**LOW-2**: design-final.md の wording / section ordering (改善点があれば
具体的箇所引用、なければ "minor" 1 行で OK)

## 5. 報告フォーマット (verbatim 保存される、構造重要)

```
# Codex review — m9-c-adopt retrain v2 spec design

## Verdict
[Overall ADOPT / ADOPT-WITH-CHANGES / REJECT]

## HIGH-A: [ADOPT / MODIFY / REJECT]
[詳細、特に MODIFY なら具体的 change proposal を 1-3 件、quoted file path / 数値で]

## HIGH-B: ...
## HIGH-C: ...
## HIGH-D: ...

## MEDIUM-1: ...
## MEDIUM-2: ...
## MEDIUM-3: ...

## LOW
- LOW-1: ...
- LOW-2: ...

## Closing note
[design-only PR としての ship 可否、HIGH 反映 commit が必要かどうか、
training execution PR にどの不安を持ち越すか]
```

verbatim 保存 (`codex-review.md`) されて PR description にリンク参照される。
LowEffortRescue (LOW を上方修正してまで対応する) は不要、HIGH は decisions.md
DR-2 に即記録、MEDIUM は採否 1 行記録、LOW は blockers.md に流れる。

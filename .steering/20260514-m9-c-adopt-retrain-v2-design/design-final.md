# Retrain v2 spec — design-final (Plan-approved, /reimagine-applied, Codex HIGH-reflected)

**Status**: Codex review (`codex-review.md`) ADOPT-WITH-CHANGES verdict 後の確定版
**Branch**: `feature/m9-c-adopt-retrain-v2-design`
**Replaces**: `.steering/20260513-m9-c-adopt/decisions.md` DA-9 literal spec
**Inputs**: Step 1 `corpus-analysis-kant.{json,md}`, DA-13 verdict, D-1
**Codex HIGH reflections**: HIGH-A/B/C/D すべて反映済 (詳細 §3.2 / §3.3 / §5)

---

## 1. Step 1 empirical gap recap (justification anchor)

`corpus-analysis-kant.json` で 5,022 examples を offline 解析した結果、4 gap
を発見:

| # | Gap | 観測値 | 意味 |
|---|---|---|---|
| C1 | 日本語占有 | ja=56.7%, de=15.9%, en=25.8% | Kant style 学習の base rate ~16% に圧縮 |
| C2 | short utterance | <30 tokens=69.0%, max=132 tokens | Kantian long-form syntax 表現 capacity 不足 |
| C3 | monolog ゼロ | dialog=100%, monolog=0% | self-addressed expository signal 完全欠落 |
| C4 | marker 不足 | combined density 1.52 (anchor 2.0、76%) / self-ref 0.30 | persona-discriminative 語彙不足 |

C1 × C2 × C3 × C4 の **multiplicative interaction** で effective
discriminative signal は **~5% (≈ 250 examples)** と推定 (de × ≥30 tokens
× non-zero marker density)。これが DA-13 で empirical 確定した LoRA effect
proper near-zero (Vendi +0.446 / Burrows -0.960 vs no-LoRA SGLang) の
mechanism。

## 2. /reimagine — 3 candidates の equal-footing 比較

DA-9 literal "min_examples 1000 → 3000" は volume framing。Step 1 の
empirical findings はこの framing を **defeat** する: 5,022 example の
realized count は volume 不足ではなく、その 95% が persona-discriminative
signal を担えない (C1-C4 multiplicative)。3 candidates を比較:

### Candidate A: Volume-driven (DA-9 literal)

- **data**: 5022 → 12,000+ examples via M9-eval P3+ stim battery 70 → 200 拡張
- **filter**: 不変 (`build_examples` そのまま)
- **rank**: 8 (固定)
- **max_steps**: ~3,000
- **新規採取コスト**: ~2,500 turn × 4 cycle (P3+) = ~6h G-GEAR
- **C1-C4 impact**:
  - C1 (ja 56.7%): **未解決** — 新規 stim も ja-heavy 採取される (kant
    persona の言語選好は corpus-side default)
  - C2 (short 69%): **未解決** — stim battery 拡張は length 分布を
    変えない
  - C3 (monolog 0%): **未解決** — stim by definition dialog
  - C4 (marker 0.76x): **未解決** — new examples も同 base distribution
- **predicted Vendi effect**: ±0.5 (現状と同 magnitude)
- **verdict**: ❌ **REJECT** — empirical gap を一つも address しない

### Candidate B: Signal-driven (preferred、DR-1 採用)

- **data**: 5022 維持 (or 高 signal subset 3,000+)
- **filter**: 不変 + **per-example weight column 追加**
- **weighting formula** (clamped `[0.1, 3.0]`):
  ```
  weight = (
      lang_de_or_en_factor * 0.35
    + length_factor       * 0.20
    + monolog_bonus       * 0.15
    + marker_density      * 0.30
  )
  ```
  - `lang_de_or_en_factor`: ja → 0.2, mixed → 0.5, en → 1.0, de → 1.4
  - `length_factor`: <30 → 0.3, 30-59 → 0.8, 60-119 → 1.5, 120+ → 2.0
  - `monolog_bonus`: addressee=None → 1.5, addressee≠None → 1.0
  - `marker_density`: max(self_ref + kantian_density / 2.0, 0.2)
- **diversity injection** (sampling-side、weight 別):
  - synthetic monolog generation 不採用 (eval contamination risk MEDIUM-3 で
    Codex に投げる)
  - 代わりに **natural shards から 2-turn 連続 Kant utterance を 1 chunk
    として再 cast** で長文 monolog proxy を作る
- **rank**: 8 (固定、DA-12 provisional carry-over)
- **PEFT setup**: PR #163 K-β baseline 同一 (`target_modules=[q,k,v,o_proj]`,
  `lora_alpha=2*r`, `lora_dropout=0.05`, NF4 + double quant)
- **max_steps**: ~4,000 (PR #163 の 2x、effective weighted batch を勘案)
- **新規採取コスト**: ゼロ
- **C1-C4 impact**:
  - C1: ja examples が weight 0.2 で down-weighted → effective de+en signal
    が ~3.5x ブースト
  - C2: short examples が 0.3、long が 1.5-2.0 → length 分布の effective
    バイアスが Kantian-favourable
  - C3: monolog proxy で synthetic に 20-30% 比率を狙う
  - C4: marker non-zero examples が ~1.5x、zero が ~0.5x → median 0 →
    floor 0.5 に底上げ
- **predicted Vendi effect**: -0.5 to -1.0 (proper direction、DA-14 達成圏)
- **statistical risk**: gradient variance、weight clamp で mitigate。
  weighted CE loss は HF Trainer の `sample_weight` 標準サポート (Codex
  HIGH-C で statistical soundness 検証)
- **verdict**: ✅ **PREFERRED** (empirical evidence-grounded、新規採取
  コストゼロ、4 gap すべてを address)

### Candidate C: Targeted hybrid (Codex HIGH-A 反映で narrow 化)

- **data**: 5022 → 7,500 (**+2500 turn を targeted 採取**:
  **de/en のみ × ≥60 tokens × monolog/long-form** biased — 一般的 stim bump
  は無意味)
- **filter**: 不変 + stratified sampling (採取側で de/en/≥60/monolog 制御)
- **rank**: 8
- **新規採取コスト**: ~2,500 turn (P3+ 部分採取、driver の generation-side で
  prompt + persona response の length / language 制約を加える)
- **C1-C4 impact**:
  - C1: 新規 2,500 turn を de/en に絞ることで de 比率 25-35% に底上げ
  - C2: ≥60 token bias で long form 比率増
  - C3: monolog re-cast を training 側で行う (B と同経路)
  - C4: ≥60 token + lang フィルタで marker density 改善
- **predicted Vendi effect**: -0.4 to -0.8
- **verdict**: 🟡 **FALLBACK** — 以下の trigger 発火時に startup 切替:
  - Candidate B の **weight-concentration audit** (§3.3) で
    effective high-signal mass < 1000、OR top 5% examples が total weight
    の 50% 超
  - DA-14 4 軸 intersection で kant が REJECT (Vendi/Burrows/ICC(A,1))
  - overfit diagnostics (validation eval loss が train loss から
    早期に乖離) で stylistic shortcut 兆候

### 結論 (decision matrix)

| 軸 | A (volume) | B (signal) | C (hybrid) |
|---|---|---|---|
| 新規採取コスト | 6h | **0h** | 3h |
| C1 (ja 56.7%) 対応 | ❌ | ✅ | 🟡 |
| C2 (short 69%) 対応 | ❌ | ✅ | 🟡 |
| C3 (monolog 0%) 対応 | ❌ | 🟡 | 🟡 |
| C4 (marker 0.76x) 対応 | ❌ | ✅ | 🟡 |
| codebase 変更面積 | 小 | **中** | 中 |
| statistical risk | 低 | **中 (要 Codex)** | 低 |
| **採用** | REJECT | **ADOPT** | FALLBACK |

## 3. 採用 spec (Candidate B 詳細)

### 3.1 DA-9 amendment (immutable append として DA-14 へ)

- **baseline backend**: no-LoRA SGLang multi-turn (DA-13 backend confound 受け)
  - artefact 再利用:
    `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-{vendi-semantic,burrows,icc}.json`
  - Ollama baseline は historical reference only
- **`min_examples`**: quality proxy として **放棄** (MEDIUM-6 + Step 1
  evidence)。`realised_examples` を post-weighting で 3,000 floor 維持
  (operational SLO、quality proof ではない)
- **rank**: 8 固定 (DA-12 provisional carry-over)
- **PEFT setup**: PR #163 K-β baseline 同一

### 3.2 Signal weighting 式 + WeightedTrainer (Codex HIGH-C MODIFY 反映)

> **Codex HIGH-C MODIFY**: HF causal-LM Trainer は `sample_weight` を
> 自動 consume しない。`WeightedTrainer.compute_loss` を **自前実装** し、
> token CE を `reduction="none"` で計算 → 非 `-100` label 上の per-example
> mean → weighted sum / normaliser を取る。係数 0.35/0.20/0.15/0.30 は
> **heuristic** (sum-to-1 で interpretable ではあるが empirical 由来では
> ない)。

#### compute_example_weight 関数 (raw weight、normalize 前)

```python
def compute_example_weight(example_metadata: dict) -> float:
    """Heuristic raw weight; normalised to mean=1.0 across train split before
    being fed to WeightedTrainer (see §3.3). Coefficients (0.35/0.20/0.15/0.30)
    are interpretable but NOT empirically derived — flagged in DR-2."""
    lang = example_metadata["language"]  # "de" / "en" / "ja" / "mixed"
    tokens = example_metadata["token_count"]
    has_addressee = example_metadata["has_addressee"]
    marker_density = example_metadata["marker_density_per_100_tokens"]

    lang_factor = {"de": 1.4, "en": 1.0, "mixed": 0.5, "ja": 0.2}[lang]
    if tokens < 30:
        length_factor = 0.3
    elif tokens < 60:
        length_factor = 0.8
    elif tokens < 120:
        length_factor = 1.5
    else:
        length_factor = 2.0
    monolog_bonus = 1.0 if has_addressee else 1.5
    marker_factor = max(marker_density / 2.0, 0.2)

    raw = (
        lang_factor   * 0.35
      + length_factor * 0.20
      + monolog_bonus * 0.15
      + marker_factor * 0.30
    )
    return float(min(max(raw, 0.1), 3.0))
```

#### Normalisation (HIGH-C #2 反映)

Train split 上で raw weights を **mean=1.0** に normalise:
```
weights = [compute_example_weight(m) for m in train_metadata]
mean_w = sum(weights) / len(weights)
normalised_weights = [w / mean_w for w in weights]
```
これで effective LR の silent shift を防ぐ。最終的な weight 範囲は
`[0.1/mean_w, 3.0/mean_w]`、Step 1 finding 由来の corpus 分布で
`mean_w ≈ 0.85` を想定 → 実効レンジ `[0.12, 3.53]`。

#### WeightedTrainer 実装 (HIGH-C #1 反映)

```python
class WeightedTrainer(transformers.Trainer):
    def compute_loss(self, model, inputs, return_outputs=False, **kw):
        weights = inputs.pop("sample_weight")  # [batch_size]
        outputs = model(**inputs)
        logits = outputs.logits[:, :-1, :]
        labels = inputs["labels"][:, 1:]
        token_ce = torch.nn.functional.cross_entropy(
            logits.reshape(-1, logits.size(-1)),
            labels.reshape(-1),
            ignore_index=-100,
            reduction="none",
        ).reshape(labels.shape)
        valid_mask = labels != -100
        per_example_loss = (token_ce * valid_mask).sum(dim=1) / valid_mask.sum(
            dim=1
        ).clamp_min(1)
        weighted_loss = (per_example_loss * weights).sum() / weights.sum().clamp_min(
            1e-8
        )
        return (weighted_loss, outputs) if return_outputs else weighted_loss
```

#### Pre-training audit (HIGH-A #2 反映)

Training kickoff 直前に以下を必ず log + ファイル化
(`weight-audit.json`):
- per-language weighted mass (`sum(w_i) for lang_i == "de"` / "en" / "ja" /
  "mixed") with target: de+en weighted mass ≥ 60% of total
- top 5% examples の total weight 占有率 (≤ 35% を target、≥ 50% で
  Candidate C fallback trigger)
- weighted effective sample size: `N_eff = (Σw_i)² / Σw_i²`
  (target ≥ 1,500、< 1,000 で fallback trigger)
- weight distribution: min / p10 / p50 / p90 / max + per-bucket (lang ×
  length × marker_quartile) weighted count

**rationale (HIGH-C #3 反映)**:
- 4 factor 加重平均 (sum-of-coefficients = 1.0): **interpretable / heuristic**
  (NOT empirical)。Step 1 evidence からは **どの factor を上げるか** は
  empirical だが、coefficient の specific value (0.35 vs 0.40 vs 0.30) は
  hand-set
- clamp `[0.1, 3.0]` で gradient variance を抑える (実効レンジは
  normalisation 後で確定、~30x ratio は practical min 0.34 / max 3.53 で
  ~10x に縮小 — HIGH-C LOW-2 反映)
- normalisation は mean=1.0 にして effective LR の silent shift を防ぐ
- WeightedTrainer は HF Trainer の compute_loss override で実装、
  `Trainer` の reduction='mean' default とは別経路

**closest prior art (HIGH-C verdict 反映)**:
- **Static importance weighting / curriculum learning (Bengio 2009)**:
  正解。本式は data-side static weight、model-confidence 不依存
- Focal Loss (Lin 2017): **loose analogy のみ** — focal は model output 依存
  dynamic weight、本式 は data 固定 static
- DAP (Direct Preference Personalization): 目的関数が異なる、NOT matching

### 3.3 Diversity injection (Codex MEDIUM-3 反映、group-aware separation)

> **Codex MEDIUM-3 反映**: `dialog_id="<orig>_mono"` 分離だけでは
> semantic duplicate が train↔eval 間で leak しうる。**group-aware split**
> を training kickoff 前に確定し、monolog re-cast は **training group のみ**
> で行う。

#### Group-aware validation split (HIGH-A #1 + MEDIUM-2 反映)

1. **Pre-split** (training kickoff の最初): 5,022 examples を
   `(source_shard, dialog_id)` で group 化、group 単位で 90/10 random split
   (seed=42、stratified by `source_shard_type`) → train_groups / eval_groups
2. **eval_groups の dialog_id は monolog re-cast の source から除外**
3. **synthetic monolog re-cast は train_groups からのみ生成**:
   `"<orig_dialog_id>_mono"` で記録、`synthetic_source_dialog_id` +
   `synthetic_source_turn_indices` metadata 付与
4. eval split は monolog re-cast を含まない (純 dialog example のみ)
5. WeightedTrainer の `eval_dataset` は eval split の **non-weighted**
   (or all-weight=1.0) で early stopping トリガー

#### Monolog re-cast spec

- **source**: natural shards (5 runs) の train_groups から、Kant が連続
  2 turn (t=k, t=k+2 で speaker=Kant、t=k+1 が別 persona) を抽出
- **生成**: `t=k` + ` ` + `t=k+2` utterance を結合、`addressee=None`、
  `epoch_phase="training"` (eval phase は元から除外)
- **数**: train split sample ~4,520 × 推定 connection rate ~5-7% = **150-300**
  synthetic monolog examples
- **記録**: 各 synthetic example に
  `synthetic_source_dialog_id`, `synthetic_source_turn_indices=[k, k+2]`,
  `synthesised_at_commit=<git_sha>` を metadata 付与
- **重複報告**: training kickoff log に "synthetic_n=… / unique_source_dialog_n=…"
  を出力 (Codex MEDIUM-3 reporting requirement)

#### contamination 防止

- 元 dialog turn (`t=k`, `t=k+2`) は train split に残留 (このまま使う、
  semantic duplicate 露出は intentional)
- ただし eval split に同 dialog_id の turn は **絶対に含まれない**
  (group split が保証)
- assert: `len(set(train_dialog_ids) & set(eval_dialog_ids)) == 0` を
  training kickoff の `_collect_from_shards` 後に hard-fail で確認

### 3.4 Hyperparameters

| Parameter | DA-9 / K-β | retrain v2 |
|---|---|---|
| base_model | Qwen/Qwen3-8B | 同一 |
| lora_rank | 8 | **8 固定** |
| target_modules | q,k,v,o_proj | 同一 |
| lora_alpha | 16 | 16 |
| lora_dropout | 0.05 | 0.05 |
| quantization | nf4 + double quant | 同一 |
| batch_size | 1 | 1 |
| gradient_accumulation | 8 | 8 |
| max_seq_length | 2048 | 2048 (C2 finding 受け、長文を活用) |
| max_steps | 2000 | **4000** (weighted batch の effective LR scaling) |
| learning_rate | 2e-4 | 2e-4 |
| save_steps | 500 | 500 |
| seed | 42 | 42 |
| min_examples | 1000 | **削除** (CS-3 SLO は post-weighting realised_count で
  3,000 floor) |
| **NEW**: sample_weight collator | N/A | `WeightedDataCollator` 新実装 |
| **NEW**: weight metadata column | N/A | `compute_example_weight` 産物 |

### 3.5 Compute envelope (Codex HIGH-B ADOPT 反映)

> **Codex HIGH-B ADOPT**: K-β baseline (PR #163) で
> peak_vram_bytes=10,553,926,656 (~9.83 GiB)、batch=1, grad_accum=8, NF4 で
> 観測。`max_steps` 倍増は wall time のみで activation memory には影響なし。
> scalar `sample_weight` + per-example loss vector は QLoRA activation /
> model memory に対して negligible。

| Phase | 時間 | 出力 |
|---|---|---|
| Data prep + weight metadata 算出 | ~10 min | weighted examples list + `weight-audit.json` |
| Group split + monolog re-cast | ~5 min | train/eval split + synthetic monolog log |
| LoRA training (max_steps=4000、weighted) | **3-5h** | `data/lora/m9-c-adopt-v2/kant_r8_v2/` |
| multi-turn pilot recapture (rank=8) | 1h | new tier-b-pilot artefacts |
| consumer (Vendi/Burrows/ICC、SGLang baseline reuse) | 20 min | new metric JSON |
| da1_matrix_multiturn.py + DA-14 thresholds | 10 min | 4-axis matrix verdict |
| **合計** | **5-7h** (envelope **8h** abort) | ADOPT / REJECT verdict |

**Training-time guards (HIGH-B 補強)**:
- **eval batch=1** (logits 保持を抑制)
- **loss-only eval** (generation-time eval は使わない、early stopping は
  eval_loss で trigger)
- **gradient_checkpointing=True** (activation memory 抑制、PR #163 同設定)
- 12GB VRAM safety margin 維持、weight column overhead は KB 単位で
  margin 内

>8h 時 abort 経路: 詳細は `next-session-prompt.md` で記述。trigger 例:
- training が 7h 超えても收束しない → kill、checkpoint で部分評価
- multi-turn pilot validation gate (`validate_multiturn_shards.py`) fail
- → Scenario IV / Phase E direct fall-through に escalate

## 4. DA-1 thresholds re-calibration (Codex HIGH-D 反映、Step 4 で DA-14 確定)

> **Codex HIGH-D MODIFY**: Vendi `d ≤ -0.5` は defensible、Burrows ≥5% は
> ambitious だが acceptable (現状 rank=8 proper effect は 115.101 →
> 114.141 で **only ~0.83% reduction** なので、5% pass は真の shift を意味)。
> ICC(A,1) ≥ 0.55 は適正、ICC(C,k) >0.97 (saturated) からの primary 昇格は妥当。

新 thresholds (Step 4 で `da1-thresholds-recalibrated.json` に pin):

- **Vendi semantic**: Cohen's d ≤ **-0.5** vs no-LoRA SGLang baseline
  - 旧 `|d| ≥ 0.3 vs Ollama baseline` を置換
  - 根拠: empirical LoRA effect proper は +0.446 (wrong direction)、-0.5 d は
    proper baseline 比 ~1.0 Vendi reduction、Anthropic persona-vector
    evidence で達成可能、|d| ≥ 1.0 は 5k LoRA で literature 上 unreachable
- **Burrows reduction**: ≥ **5%** point + CI lower > 0
  - 旧 `≥ 10%` を緩和、literature shoulder 5-15% (Burrows 1987 / Eder 2016)
  - 根拠: 現状 LoRA effect proper は `-0.96 / 115.101 = -0.83%` (wrong
    direction)、5% pass は真の signal shift を意味
- **ICC(A,1)** primary 昇格: ≥ **0.55** point + CI lower ≥ **0.50**
  - 旧 `ICC(C,k) ≥ 0.6` は >0.97 で saturated → diagnostic に格下げ
  - MEDIUM-4 ICC(A,1) precedent 採用
  - 根拠: no-LoRA SGLang baseline で ICC(A,1)=0.9061、LoRA-on r=8 で 0.9002 →
    persona-fit signal が ICC(A,1) で測れる帯域に入っている
- **throughput**: ≥ 70% (不変)

**4 axis intersection ADOPT 確率推定** (Codex HIGH-D feedback):
- Candidate B (signal-driven) で 4 axis すべて pass 確率: 中程度
  (Vendi/Burrows が co-improvement する点が key、ICC(A,1) は near-saturated
  なので shift が観測可能か未知)
- kant quorum 2-of-3 (Vendi + ICC + Burrows) で kant ADOPT 確率: より高い

DA-14 として `.steering/20260513-m9-c-adopt/decisions.md` に immutable
append (DA-12/13 不変)。Step 4 で正式起票。

## 5. Risks and mitigations

| Risk | Mitigation |
|---|---|
| R-B1: weighting で gradient variance blowup | clamp `[0.1, 3.0]`、HF Trainer の `sample_weight` 標準パスを利用、Codex HIGH-C で statistical review |
| R-B2: weighted loss が stylistic shortcut overfit | Codex MEDIUM-2 で evaluation contamination risk と合わせて検証、validation split (10%) で early stopping |
| R-B3: monolog synthetic re-cast が eval intent leak | 元 dialog turn と synthetic monolog の `dialog_id` 共有を禁止 (新 `dialog_id="<orig>_mono"` で分離)、`epoch_phase=training` 維持 |
| R-B4: ja down-weighting が training-data distribution shift で OOD | Codex MEDIUM-1 で n-gram entropy / TTR 不足を投げる、必要なら weight clamp を `[0.3, 2.5]` に narrow |
| R-B5: rank=8 固定で capacity 不足 | Phase E A-6 で rank=16 を再評価可能、本 spec scope 外 |
| R-B6: G-GEAR overnight >8h | abort criteria 明示 (`next-session-prompt.md`)、Scenario IV / Phase E direct fall-through |
| R-B7: tokenizer proxy が production tokenize と乖離 | Codex MEDIUM-1 で flag、production training 時に **必ず Qwen3-8B 実 tokenizer で weight 再算出** (corpus-analysis では proxy で OK、training 時は real が必須) |

## 6. Codex review 質問軸 (Step 3 で起票)

- **HIGH-A** (data sourcing operational): signal-driven (B) で十分か、hybrid
  (C) が overfit 回避に必要か
- **HIGH-B** (compute feasibility): G-GEAR overnight ~6h で 5,022 weighted
  examples + max_steps 4,000 + sample_weight collator + QLoRA NF4 + rank=8 が
  完遂可能か (16GB-class GPU)
- **HIGH-C** (weight 式 statistical soundness): 4-factor linear + clamp
  `[0.1, 3.0]` の妥当性、gradient variance / mode collapse 懸念
- **HIGH-D** (DA-14 thresholds): LoRA effect proper ±0.5 を踏まえ達成可能か
- **MEDIUM-1** (Step 1 metric coverage): n-gram entropy / TTR / 文構造 metric
  追加検討
- **MEDIUM-2** (weighted overfit): stylistic shortcut への overfit リスク
- **MEDIUM-3** (monolog re-cast eval leak): dialog_id 分離で十分か、それとも
  contamination 懸念か
- **LOW**: wording / ADR ordering / cross-link

## 7. 次セッション handoff (Step 5 で詳細起票)

- branch: `feature/m9-c-adopt-retrain-v2-implementation` (main 派生)
- 目的: weight metadata 実装 + training + recapture + DA-14 4-axis 判定
- compute envelope: 5-7h、abort 8h
- ADOPT / REJECT criteria: DA-14 4-axis intersection (kant quorum 2-of-3)

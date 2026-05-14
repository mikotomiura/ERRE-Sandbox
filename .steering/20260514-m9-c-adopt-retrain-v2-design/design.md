# 設計 (working draft)

> **Note**: design-final.md が `/reimagine` 適用 + user 承認後に確定する。
> 本 design.md は working draft (Step 1-2 中の作業領域)。

## 前提と継承 (PR #166 / DA-13 内面化)

### DA-13 verdict (Scenario II + Backend Confound Discovery)

PR #166 で確定:

- **factor decomposition** (`.steering/20260514-m9-c-adopt-pilot-multiturn/report.md`):

  | 比較 | Vendi Δ | Burrows Δ | 解釈 |
  |---|---|---|---|
  | backend confound (matched Ollama → no-LoRA SGLang) | **+2.144** | **+5.391** | direction failure の primary cause |
  | LoRA effect proper (rank=8) | +0.446 | -0.960 | near-zero, direction-mixed |

- DA-12 direction failure 主因 = **backend confound** (NOT LoRA failure)
- LoRA effect は near-zero (±0.5)、persona-discriminative signal が
  intrinsic に弱い

### 最重要 finding (Phase 1 探索)

`data/lora/m9-c-adopt/archive/rank_8/kant/train_metadata.json` より:

- `min_examples_threshold = 1000` (CS-3 operational SLO)
- `realized_examples = **5,022**` (5x margin で既に実施済)
- shard_stats: 10 shards (natural run0-4 + stimulus run0-4)
  - natural: 500-501 persona examples / shard (total 2,502)
  - stimulus: 504 persona examples / shard (total 2,520)
- `train_loss = 0.2155` (3.488 → 0.128 で 27x 改善、収束済)
- `training_executed: true` (2026-05-13 完遂)

つまり **真の問題は num_examples ではなく per-example discriminative signal**。
DA-9 の literal "1000 → 3000" 解釈は不正確。retrain v2 spec は **signal-driven
engineering** に rebrand する。

### 継承する constraint

- baseline = **no-LoRA SGLang multi-turn** (DA-13 backend confound 受け、Ollama
  は historical reference only)
- rank=8 固定 (DA-12 provisional carry-over + smaller-rank-preferred spirit)
- PEFT 同 setup (PR #163 K-β baseline: `target_modules=[q,k,v,o_proj]`,
  `lora_alpha=2*r`, `lora_dropout=0.05`)
- 4-axis intersection 維持 (Vendi + ICC + Burrows + throughput)、quorum 規則
  (kant: 2-of-3) 不変
- multi-turn protocol obligation (DA-11 + DA-13)

### 継承する Codex HIGH operational legacy

- HIGH-1: no-LoRA SGLang control が retrain v2 baseline (本 PR で reuse)
- HIGH-2: matched baseline downsampling protocol = retrain v2 validation baseline
- HIGH-3: pre-register thresholds (post-hoc movement 禁止)
- HIGH-4: validation gate (`validate_multiturn_shards.py`) = ADOPT acceptance gate

## 実装アプローチ (Step 1-2)

### Step 1: training data 特性分析 (本セッションで実行)

`scripts/analysis/analyze_kant_training_corpus.py` を新規作成し、既存 5,022
examples を re-extract して **5 metrics** を算出:

1. **token length 分布**: `AutoTokenizer.from_pretrained("Qwen/Qwen3-8B")` で
   per-example token 数を histogram 化
2. **persona self-reference markers** (Kant style): 独語
   `{ich, meiner, meines, meiner Ansicht, mir scheint, m.E.}` + Kantian 用語
   `{categorical, imperative, a priori, synthetic, transcendental, in itself}`
   + 1人称 ratio。per-example density (per 100 tokens) を算出
3. **dialog vs monolog ratio**: ChatML に addressee role-tag 含む例 / 含まない例の比
4. **per-stimulus category coverage**: `kant_stimulus_run*` shards →
   `stimulus_id` join → `{wachsmuth(30), tom_chashitsu(20), roleeval(10), moral_dilemma(10)}`
   per `golden/stimulus/kant.yaml`、`kant_natural_run*` → `natural_dialog` bucket
5. **utterance language distribution**: `langdetect` で de/en/ja 分布

**reuse 方針** (architecture-rules 準拠):
- `from erre_sandbox.training.dataset import build_examples` で production filter
  chain 同一保証
- `from erre_sandbox.training.train_kant_lora import _collect_from_shards,
  assert_phase_beta_ready` で per-shard DuckDB load + contamination gate 継承

**outputs**:
- `.steering/20260514-m9-c-adopt-retrain-v2-design/corpus-analysis-kant.json`
- `corpus-analysis-kant.md` (gap finding、falsifiable claim 必須)

### Step 2: retrain v2 spec design + `/reimagine`

`/reimagine` で 3 candidate を equal-footing 比較、signal-driven (推奨) を defend:

1. **Volume-driven** (DA-9 literal): 5022 → 12000+ via M9-eval P3+ stim battery
   拡張 (70 → 200)、filter chain 不変、rank=8、`max_steps ≈ 3000`
   - Cons: realized=5022 既に literature shoulder 越え、新規採取コスト大
2. **Signal-driven** (Claude/user 承認): 5022 維持 + per-example loss/sampling
   weights = `(self_ref_density * 0.4 + dialog_bonus * 0.3 + stim_category_balance * 0.3)`
   clamp `[0.1, 3.0]`
   - 実装 (次セッション): `build_weighted_examples()` adapter を `dataset.py`、
     HF Trainer sample-weight collator
3. **Hybrid**: ~7500 examples + stratified sampling diversity injection、weight
   column なし、rank=8、`max_steps ≈ 2500`

`design-final.md` 必須節 (Step 2 末で確定):
- DA-9 amendment (baseline = no-LoRA SGLang multi-turn)
- `min_examples` を quality proxy として放棄、realised_examples floor 3000
- persona-signal weighting 式 + clamp + statistical soundness justification
- diversity injection (per-stim-category target counts from Step 1 gap table)
- rank=8 固定 + PEFT 同 setup
- compute envelope: 3-5h training + 1h pilot + 30 min consumer/matrix ≈ 5-7h

## 変更対象

### 新規作成 (本 PR)

- `scripts/analysis/analyze_kant_training_corpus.py` — corpus analysis script
- `tests/test_analysis/test_kant_corpus.py` — 3-case smoke
- `.steering/20260514-m9-c-adopt-retrain-v2-design/corpus-analysis-kant.{json,md}`
- `.steering/20260514-m9-c-adopt-retrain-v2-design/design-final.md`
- `.steering/20260514-m9-c-adopt-retrain-v2-design/codex-review-prompt.md`
- `.steering/20260514-m9-c-adopt-retrain-v2-design/codex-review.md` (verbatim)
- `.steering/20260514-m9-c-adopt-retrain-v2-design/da1-thresholds-recalibrated.json`
- `.steering/20260514-m9-c-adopt-retrain-v2-design/next-session-prompt.md`

### 追記 (immutable append)

- `.steering/20260513-m9-c-adopt/decisions.md` — **DA-14** append (DA-12/13 不変)

### 再利用 (modify せず import)

- `src/erre_sandbox/training/dataset.py` (`build_examples`)
- `src/erre_sandbox/training/train_kant_lora.py` (`_collect_from_shards`, `assert_phase_beta_ready`)

## 影響範囲

本 PR は design only。`src/erre_sandbox/` 配下のコード変更なし。
`scripts/analysis/` は新規 directory (test path 別)。

次 PR (`feature/m9-c-adopt-retrain-v2-implementation`) で影響:
- `src/erre_sandbox/training/dataset.py` (`build_weighted_examples` 追加)
- `src/erre_sandbox/training/train_kant_lora.py` (sample-weight collator)
- `data/lora/m9-c-adopt-v2/kant_r8_v2/` (新規 LoRA output)

## 既存パターンとの整合性

- `.steering/_template/` の 5-file structure 踏襲
- ADR は immutable convention で append のみ (DA-12/13 同様)
- Codex review verbatim 保存 (PR #166 と同様)
- Conventional Commits + git-workflow Skill 準拠 (commit prefix `design(adopt):`)

## テスト戦略

- **単体テスト**: `tests/test_analysis/test_kant_corpus.py` 3 case
  (fixture DuckDB shard で 5 metrics 算出 logic を検証)
- **統合テスト**: 不要 (本 PR は design + analysis、production code 不変)
- **E2E テスト**: 不要

## ロールバック計画

design-only PR のため、本 PR 自体は revert で完全戻し可能。次 PR
(`feature/m9-c-adopt-retrain-v2-implementation`) に impact なし。

DA-14 ADR は `.steering/20260513-m9-c-adopt/decisions.md` への追記なので、
revert 時は同 file から DA-14 セクションのみ削除。

## ゴール falsifiable claims (Step 1 corpus analysis 結果より)

Step 1 で 5,022 examples を re-analysed (`corpus-analysis-kant.json`)。複数の
empirical gap が判明:

### Claim 1 (PRIMARY): training corpus の **56.7% が日本語**

- ja: 2,847 examples (56.7%) — kana/kanji ratio ≥ 5% を含む utterance
- en: 1,296 examples (25.8%)
- **de: 798 examples (15.9%)** ← Burrows discriminator は de-only を前提
- mixed: 81 examples (1.6%)

これは LoRA effect proper near-zero (DA-13 Vendi +0.446 / Burrows -0.960) の
**最有力 mechanism**。Kant の persona-discriminative style (de Critique 風 long
sentences、Kantian philosophy lexicon) は日本語 utterance では学習できず、
de utterance 15.9% という critical mass 不足が style learning を骨抜きにする。
Burrows reference corpus (de-only) との apples-to-oranges 比較も avoidable
ではない。

**Falsifiability**: 日本語 utterance を de/en に絞り込む signal-driven
weighting + diversity injection で、retrain v2 後の Vendi semantic distance
が SGLang baseline 比で **少なくとも +0.5 reduction** (proper direction) を
生じるはず。

### Claim 2: **69.0% が <30 tokens** (short utterance dominance)

- 0-9 tokens: 538 (10.7%)
- 10-29 tokens: 2,926 (58.3%)
- 30-59 tokens: 1,509 (30.0%)
- 60-119 tokens: 48 (1.0%)
- 120+ tokens: 1 example only
- **max: 132 tokens** (max_seq_length=2048 がほぼ未使用)

Kant style は subordinate clause を多重に重ねる long-form expository prose
(典型 200-500 tokens / sentence) が discriminative。30 tokens 以下では
Kantian syntax 構造 (relative pronoun chains, parenthetical qualifiers) を
表現する余地なし。

**Falsifiability**: <30 token utterance を de-prioritise (weight 0.3) し、
60+ token utterance を up-weight (weight 2.0) する signal-driven 設計で、
retrain v2 後の Vendi semantic 多様性が増加するはず。

### Claim 3: **dialog 100% / monolog 0%**

- 全 5,022 examples が `addressee_persona_id` 付き dialog turn
- top addressees: `interlocutor` (2,520 = 全 stimulus turns), `nietzsche`
  (1,258), `rikyu` (1,244)
- Kant の **monolog philosophical exposition は corpus にゼロ**

Critique of Pure Reason 風の self-addressed reasoning chain は training
signal として欠落。これは ERRE simulation の cognitive habit (Kant が
書斎で長文 critique を書く 5:00-7:00) と乖離。

**Falsifiability**: monolog 比率を 20-30% まで synthetic に boost
(natural shards から 2-turn 連続自発発言を抽出 → addressee=None で
re-cast) し、retrain v2 後の Kantian lexicon density が増加するはず。

### Claim 4: marker density は anchor の **0.76x**

- Combined marker density: 1.52 per 100 tokens (literature anchor 2.0)
- **Self-reference markers: 0.30 per 100 tokens** ← anchor 期待 ≥1.0 の 3.3x 不足
- Kantian philosophy markers: 1.23 (modest)
- Median = 0.00 (50% 以上の examples で markers 完全に欠落)

**Falsifiability**: self-ref + Kantian marker 含有 examples (corpus 内に
非ゼロ density のもの) を up-weight (weight 1.5-2.0) し、ゼロ density 例を
down-weight (weight 0.5) する。retrain v2 後の persona-fit ICC(A,1) が
0.55 floor (DA-14 threshold) を超えるはず。

### 統合解釈

DA-13 で empirical に確定した LoRA effect proper near-zero (Vendi +0.446 /
Burrows -0.960) は、上記 4 gap の **multiplicative interaction** で説明
できる:

- Claim 1 (ja 56.7%) → Kantian style 学習の **base rate** が ~16% に圧縮
- Claim 2 (short 69%) → de 内訳でも style 表現 capacity 不足
- Claim 3 (monolog 0%) → long-form expository signal ゼロ
- Claim 4 (marker 0.76x) → 残った de utterance でも marker density 不足

つまり 5,022 examples 中、**Kant persona-discriminative signal を真に
学習可能な subset は ~5%** (de × ≥30 tokens × non-zero marker density ≈
250 examples) と推定。これは CS-3 SLO 1,000 を **大幅に下回る effective
signal count**。retrain v2 spec は **signal-driven weighting で effective
count を 1,000+ に底上げ** することが本質的解決策。

これらの knobs は DR-1 (signal-driven preferred) の weighting 式の入力で
あり、Step 2 design-final.md の signal-driven candidate を選択する empirical
justification となる。

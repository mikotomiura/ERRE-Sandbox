# P4a Tier B — design final (Codex Verdict: ADOPT-WITH-CHANGES、HIGH 4 全反映)

> v3 hybrid を出発点に、Codex independent review (`codex-review-p4a.md`、196K tok)
> の HIGH 4 / MEDIUM 5 / LOW 3 を全反映した最終 design。
>
> Closing note (Codex 引用):「Adopt v3 hybrid, not v1 or v2, but only after the
> HIGH fixes. The right final shape is v3 with: Vendi kernel sensitivity instead
> of hard-coded 0.7/0.3 faith, corrected ICC notation/consumer semantics,
> license-cleared Japanese IPIP corpus or explicit defer, and anti-social-
> desirability IPIP administration.」

## 0. Mission (不変)

`src/erre_sandbox/evidence/tier_b/` をゼロから起草、LoRA 採用判定 (DB9 quorum)
の 3 sub-metric (`vendi_score` / `big5_stability_icc` / `burrows_delta_to_reference`)
のうち Tier B 新規 2 (Vendi / Big5 ICC) と IPIP-NEO administering helper を提供。
Burrows Δ は `tier_a/burrows.py` 既存。

DB9 quorum: Tier B = LoRA 採用 offensive gate の唯一の arbiter。

## 1. HIGH-1 反映 — Vendi kernel は **sensitivity matrix** で起草

### 確定事項

- **default kernel**: `semantic` (sentence-transformers MPNet)。
  hybrid 0.7/0.3 は **commit しない** (Friedman & Dieng 2023 に prior art なし)。
- **one-hot sanity test の正しい形**: score = N が成立する条件は **K = I** (identity
  kernel、off-diagonal すべて 0)。lexical one-hot で hybrid kernel score=N は
  **数学的に成立しない** ので、sanity test は **identity-kernel stub** を直接渡して
  検証する。
- **kernel sensitivity test (preregistered)**: P4b で golden baseline data に対して
  下記 5 候補を batch 計算し、persona-discriminative power と stability を比較する。
  P4a 本体では **sensitivity 実行は scope 外**、sensitivity entry point の API のみ提供。
  - `semantic-only` (MPNet cosine)
  - `lexical-only` (5-gram Jaccard or count)
  - `hybrid-0.5-0.5`
  - `hybrid-0.7-0.3`
  - `hybrid-0.9-0.1`
- **window size**: 100-turn 維持 (design-final.md 整合)。P4b sensitivity と併せて
  100-turn での finite-sample stability を empirical 確認。

### API 反映

```python
@dataclass(frozen=True, slots=True)
class VendiResult:
    score: float
    n: int                    # window utterance 数
    kernel_name: str          # "semantic" | "lexical-5gram" | "hybrid-{w_s}-{w_l}" | "identity"
    semantic_weight: float    # hybrid 時のみ (0.0-1.0)、それ以外 1.0/0.0
    lexical_weight: float     # 同上


def compute_vendi(
    utterances: Sequence[str],
    *,
    kernel: VendiKernel | None = None,
    kernel_name: str = "semantic",
) -> VendiResult: ...


def vendi_kernel_sensitivity_panel(
    utterances: Sequence[str],
    *,
    semantic_kernel: VendiKernel,
    lexical_kernel: VendiKernel,
    weights: Sequence[tuple[float, float]] = ((1.0, 0.0), (0.0, 1.0), (0.5, 0.5),
                                                (0.7, 0.3), (0.9, 0.1)),
) -> list[VendiResult]:
    """Preregistered sensitivity panel (HIGH-1)."""
```

### sanity test 修正

- `test_compute_vendi_identity_kernel_score_equals_n` (新): identity-kernel stub で
  N×N の I を返させ、score = N を検証。**lexical one-hot では成立しないことを
  comment で明記**。
- `test_compute_vendi_identical_utterances_score_equals_one` (既存): degenerate.
- `test_vendi_kernel_sensitivity_panel_shape` (新): 5 候補で N=5 結果を返す.

## 2. HIGH-2 反映 — ICC は **Koo-Li notation 統一 + dual-consumer split**

### 確定事項

- **notation 統一**: McGraw & Wong (1996) 表記に統一。`ICC(A,1)` = absolute agreement
  single rater、`ICC(A,k)` = absolute agreement k-rater average、`ICC(C,1)` =
  consistency single rater、`ICC(C,k)` = consistency k-rater average。Shrout-Fleiss
  notation は **comment で対応関係のみ示す** (ICC(2,k) ≈ ICC(A,k))。
- **dual consumer split** (Codex HIGH-2):
  - **ME-1 reliability fallback trigger**: `ICC(C,k)` consistency primary (現行 ME-1
    threshold 0.6 / lower CI 0.5 を継続適用、Koo-Li 2016 cutoff の根拠は consistency)
  - **DB9 drift/adoption gate**: `ICC(A,1)` absolute agreement primary (level shift =
    drift signal)。**ME-1 threshold 流用禁止**、DB9 用 cutoff は P4b で persona-
    conditional に calibrate
- **degenerate handling** (MEDIUM-5): identical 全 constant 回答列で ANOVA は 0/0 →
  `Big5ICCResult.icc_point = 1.0, degenerate=True, fallback_fire=False` を **意図的
  special case** として返す (assumption ではない)。

### API 反映

```python
@dataclass(frozen=True, slots=True)
class Big5ICCResult:
    # ME-1 consumer (reliability fallback trigger)
    icc_consistency_average: float    # ICC(C,k) point — McGraw-Wong notation
    icc_consistency_single: float     # ICC(C,1)
    icc_consistency_lower_ci: float
    icc_consistency_upper_ci: float
    me1_fallback_fire: bool           # ICC(C,k) < 0.6 OR lower CI < 0.5

    # DB9 consumer (drift/adoption gate)
    icc_agreement_single: float       # ICC(A,1) point
    icc_agreement_average: float      # ICC(A,k)
    icc_agreement_lower_ci: float
    icc_agreement_upper_ci: float
    # NOTE: DB9 threshold は P4b calibrate、ME-1 の 0.6/0.5 を流用しない

    # diagnostic
    n_clusters: int                   # 25 typical (5 run × 5 window)
    n_dimensions: int                 # 5 (E/A/C/N/O)
    degenerate: bool                  # ANOVA 0/0 case (identical responses)
    formula_notation: str             # "McGraw-Wong 1996"


def compute_big5_icc(
    big5_per_window: Sequence[Big5Scores],
    *,
    seed: int = 0,
    n_resamples: int = 2000,
) -> Big5ICCResult: ...
```

### test 反映

- `test_compute_big5_icc_identical_windows_degenerate_returns_one` (修正): 1.0 を
  return しつつ `degenerate=True`。
- `test_compute_big5_icc_consistency_vs_agreement_offset_sensitivity` (新):
  systematic offset 加算で `icc_consistency_*` は不変、`icc_agreement_*` は変化。
- `test_compute_big5_icc_me1_fallback_uses_consistency_only` (新): fallback fire
  flag が consistency ICC のみ参照。

## 3. HIGH-3 反映 — IPIP-NEO 版は **IPIP-50 (English) only**、日本語 defer

### 確定事項

- **版**: IPIP-50 (Goldberg 1992、IPIP English official、public domain commercial use OK)
- **language**: P4a では `language="en"` only。`language="ja"` は **NotImplementedError**
  を raise + ADR で defer 理由明示。
- **defer 理由** (HIGH-3):
  - Murakami 2002/2003 は **Japanese lexical Big Five 研究** であって IPIP-50 翻訳
    ではない (Codex 引用)
  - 公式 IPIP translations page (https://ipip.ori.org/newTranslations.htm) は
    Nakayama/Karlin の Japanese IPIP リストを示すが、IPIP-50 specific translation
    の license/provenance は P4a 内で確定不能
  - Merge condition (Codex): vendor exact public-domain text with provenance OR ship
    en-only — 後者を採用
- **defer task**: 別タスク `m9-eval-p4b-ja-ipip-vendoring` を `tasklist.md` に追加、
  Nakayama/Karlin 公式 source の license 確認 + 50 item vendoring を要件化。

### Persona language 制約

- kant / nietzsche: 多くの dialog は ja だが、IPIP 投与時は **system prompt 固定で
  English self-report** を request。Salecha 2024 の cross-language stability
  literature を adopt task で確認。
- rikyu: Japanese persona だが IPIP 投与は en で実施 (defer 解消まで)。**ADR で
  pragmatic choice 明示**。

## 4. HIGH-4 反映 — IPIP anti-demand-characteristics 設計

### 確定事項 (Codex HIGH-4 quotation)

> The helper should avoid announcing "Big Five/IPIP/personality test" in the prompt,
> isolate items or use constrained scoring, randomize order deterministically,
> include decoys/control items, and record base-model no-persona controls.

### prompt design

- **avoid**: "personality test", "Big Five", "IPIP", "questionnaire", "survey"
- **alt framing**: "Read the statement and reply with one digit 1-5 indicating how
  well it describes you, where 1=not at all, 5=very much."
- item を **batch ではなく 1 item ずつ独立** に提示 (context contamination 防止)
- **deterministic shuffling**: `seed` から item order を blake2b-derived RNG で固定
- **decoy items**: 5 件追加 (Big5 dimension 外の neutral statements)、scoring 時に
  filter
- **control measurement** (ME-1 既決): persona prompt 無し base model qwen3:8b raw
  で同 IPIP 投与を 1 run 実施

### API 反映

```python
def administer_ipip_neo(
    responder: PersonaResponder,
    *,
    version: str = "ipip-50",   # only this in P4a (mini-ipip-20 deferred)
    language: str = "en",       # only this in P4a
    seed: int = 0,
    include_decoys: bool = True,
    decoy_count: int = 5,
) -> Big5Scores:
    """Administer IPIP-50 with anti-demand-characteristics design (HIGH-4).

    The prompt template explicitly avoids 'personality test' / 'Big Five' /
    'IPIP' / 'questionnaire' phrasing. Items are presented one at a time
    in deterministically shuffled order. Optional decoy items dilute
    test-taking context inference (Salecha 2024).
    """
```

### diagnostic 4 種 (ME-1 既決)

- acquiescence_index (logit balance over Likert 1-5)
- straight_line_runs (max consecutive identical answers)
- reverse_keyed_agreement (corr forward / reverse pairs)
- **decoy_consistency** (新): decoy items の Likert 分布が真の items と乖離するか

## 5. MEDIUM 反映

### MEDIUM-1: bootstrap output `ci_primary` + `ci_diagnostic_auto_block` 分離

- `BootstrapResult` 既存は `point/lo/hi/width/n/method` のみ。Tier B 用に新 dataclass
  を導入し、両 CI を併記:

```python
@dataclass(frozen=True, slots=True)
class TierBBootstrapPair:
    """Primary CI (cluster_only) + diagnostic CI (auto_block) のペア."""
    primary: BootstrapResult        # method="hierarchical-cluster-only", ESS=25
    diagnostic_auto_block: BootstrapResult | None  # method="hierarchical-block", auto_block path
    persona_id: str
    metric_name: str
    ess_disclosure: int             # 25 (5 run × 5 window)
```

- DB9 quorum 判定 code は **`primary` のみ参照** (consumer rule、ADR で禁止条項化)。
- `diagnostic_auto_block` は JSON 出力併記、運用者が variance underestimation を
  cross-check するためのみ。
- **pooled-persona CI 禁止** (Codex MEDIUM-1): persona-conditional のみ。pooled は
  exploratory 専用 path で `is_exploratory=True` flag 付与時のみ計算可。

### MEDIUM-2: column 流用は維持、helper で `window_index` 名称 + JSON metadata

- `metrics.tier_b` schema は不変 (`turn_idx` を `window_index` 意味で再利用)
- `eval_store.py` の retrieval helper は **`window_index` 名称** で返す:

```python
def fetch_tier_b_metric(
    view: AnalysisView,
    *,
    run_id: str,
    persona_id: str,
    metric_name: str,
) -> list[TierBMetricRow]:
    """Return rows with window_index (not turn_idx) and parsed notes JSON."""


@dataclass(frozen=True, slots=True)
class TierBMetricRow:
    window_index: int       # 0..24 (turn_idx 再利用)
    metric_value: float
    window_start_turn: int  # notes JSON
    window_end_turn: int    # notes JSON
    window_size: int        # notes JSON, 100 typical
    metric_schema_version: str  # notes JSON, e.g. "tier-b-v1"
```

- INSERT 時の `notes` JSON 構造を固定 schema 化:
  `{"window_start_turn": int, "window_end_turn": int, "window_size": int,
    "metric_schema_version": "tier-b-v1", "kernel_name": str | null,
    "ipip_version": str | null, "icc_formula": str | null}`

### MEDIUM-3: DB11 follow-up は明示 ADR、 "DB5 が保証" 主張禁止

- decisions.md ME-15 (新) で次を明記:
  - Tier B は eval-only path であり P4a 時点で training への漏洩は **構造的に防がれて
    いる** (DB5)
  - **ただし DB11 の `individual_layer_enabled=false` AND `evaluation_epoch=false`
    enforcement は raw_dialog allow-list に未追加** (現行 `ALLOWED_RAW_DIALOG_KEYS`
    確認済、`individual_layer_enabled` を含まない)
  - **必須 follow-up**: M9-C-adopt または別タスク `m9-individual-layer-schema-add`
    で raw_dialog DDL に `individual_layer_enabled BOOLEAN DEFAULT FALSE` 追加 +
    training-view 入口 assert + grep gate 拡張
  - P4a 本体は **その follow-up を blockers.md に記録**、Tier B docstring で
    "training enforcement の DB11 plumbing は別タスク" と明示

### MEDIUM-4: multilingual Vendi diagnostic + exact model id assert

- `tier_a/novelty.py` は `sentence-transformers/all-mpnet-base-v2` (English-only) を
  load。Tier B Vendi も **同 model を流用** (追加 dep 0)、ただし test で:
  - `test_vendi_default_encoder_model_id_is_all_mpnet_base_v2` (新): exact model id
    を assert
  - `test_vendi_language_stratified_diagnostic` (新): ja-only / en-only / mixed
    window stub に対し、stratified score を返す helper の動作検証
- 多言語 fairness はこの段階では **diagnostic only**。multilingual encoder 切替は
  別タスク `m9-eval-multilingual-vendi-encoder` (HIGH ではない、Codex も
  diagnostic で十分とする)。

### MEDIUM-5: ICC sample size と degenerate 明示

- `Big5ICCResult.n_clusters` を 25 と明示 (5 run × 5 window)、ただし内部で
  cross-checking用に `n_dimensions=5` も保持
- effective ICC design は **5 runs × 5 windows × 5 domains** (ratings is windows,
  measurements is dimensions)。サンプルサイズ言及は docstring で明示
- `degenerate=True` case (MEDIUM-5 / LOW-2 と整合): identical 全 constant 回答列の
  ANOVA 0/0 は意図的 special case で `icc_*=1.0, degenerate=True` を返す、ANOVA
  formula を bypass

## 6. LOW 反映

### LOW-1: 5-point Likert 維持

- 7-point は採用しない、5-point の方が LLM 解析 ambiguity が低い (Codex)
- balanced reverse-keyed ~50% は v3 通り、ただし forward / reverse adjacency は
  避ける (deterministic shuffle 内で)

### LOW-2: P5 残課題 close OK、ただし regression/sanity ラベル

- `test_compute_vendi_identity_kernel_score_equals_n`
- `test_compute_big5_icc_identical_windows_degenerate_returns_one`
- これらは **regression/sanity test** であって metric validity の証拠ではないと
  docstring に明記。tasklist.md の P5 sub-items 2 件 は close 可能。

### LOW-3: LIWC framing は `empath_proxy.py` 雛形を逐語コピー

- Tier B 全 module 冒頭 docstring に下記同形 (docstring 文言)を入れる:
  - "IPIP self-report only — no LIWC equivalence claim, no external-lexicon Big5
    inference. Tier A `empath_proxy` is a separate psycholinguistic axis (ME-1 /
    DB10 Option D)."

## 7. 最終 5 Question commitment matrix

| Q | v1 | v2 | v3 | **final** |
|---|---|---|---|---|
| Q1 Vendi kernel | semantic | hybrid 0.7/0.3 | hybrid 0.7/0.3 | **default semantic + sensitivity panel API** (HIGH-1) |
| Q1 window | 100 | 200 | 100 | 100 (sensitivity に preregister) |
| Q2 IPIP-NEO 版 | mini-20 | IPIP-50 ja+en | IPIP-50 ja+en | **IPIP-50 en-only** (HIGH-3、ja defer) |
| Q3 ICC primary | ICC(2,k) consistency | ICC(A,1) agreement | both surfaced | **ME-1=ICC(C,k) consistency / DB9=ICC(A,1) agreement、McGraw-Wong notation 統一** (HIGH-2) |
| Q4 bootstrap | cluster_only | block | both 併載 | cluster_only primary + auto_block diagnostic、`ci_primary` field 分離、quorum は primary のみ参照 (MEDIUM-1) |
| Q5 LIWC | 全廃 | 全廃 | 全廃 | 全廃 + empath_proxy.py 雛形を逐語コピー (LOW-3) |
| Q4+ persona-conditional | implicit | implicit | implicit | **pooled-persona CI 禁止、persona-conditional のみ** (MEDIUM-1) |
| Q5+ IPIP wording | naïve | naïve | naïve | **anti-demand-characteristics、"personality test" wording 禁止、decoys、deterministic shuffle、base-model control** (HIGH-4) |

## 8. 新規 ADR (decisions.md 追記対象)

`.steering/20260430-m9-eval-system/decisions.md` に下記 6 ADR 追加:

- **ME-10**: Vendi kernel default + sensitivity panel preregister (HIGH-1 反映)
- **ME-11**: ICC McGraw-Wong notation + dual-consumer split (ME-1 consistency / DB9 agreement) (HIGH-2 反映)
- **ME-12**: IPIP-50 en-only + Japanese vendoring defer + persona language pragmatic choice (HIGH-3 反映)
- **ME-13**: IPIP anti-demand-characteristics 設計 (HIGH-4 反映)
- **ME-14**: Tier B BootstrapPair (primary cluster_only + diagnostic auto_block)、persona-conditional 強制、pooled 禁止 (MEDIUM-1 反映)
- **ME-15**: Tier B 出力 schema (window_index helper + notes JSON 固定 schema) + DB11 follow-up 明示 (MEDIUM-2/3 反映)

各 ADR は 5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件) で記述。

## 9. tasklist.md 更新対象

P4a 本体で close する sub-items:

- P4a vendi.py 実装 + sensitivity panel API
- P4a ipip_neo.py 実装 + anti-demand-characteristics
- P4a big5_icc.py 実装 + McGraw-Wong notation + dual-consumer
- P4a tier_b/__init__.py + eval_store.py additive helper
- P5 残: Vendi identity-kernel one-hot=N test (修正後 sanity)
- P5 残: Big5 ICC identical-response degenerate=1.0 test

新規 follow-up task (blockers.md / 別 task):

- `m9-eval-p4b-ja-ipip-vendoring` (HIGH-3 defer)
- `m9-eval-p4b-vendi-kernel-sensitivity` (HIGH-1 preregistered sensitivity)
- `m9-individual-layer-schema-add` (MEDIUM-3 DB11 follow-up)
- `m9-eval-multilingual-vendi-encoder` (MEDIUM-4 cross-language fairness)

## 10. test plan (final、合計 ~22 件)

### `test_vendi.py` (7 件)

1. `test_compute_vendi_identity_kernel_score_equals_n` (HIGH-1 sanity)
2. `test_compute_vendi_identical_utterances_score_equals_one`
3. `test_compute_vendi_empty_input_returns_zero_n`
4. `test_compute_vendi_kernel_stub_round_trip`
5. `test_compute_vendi_per_persona_bootstrap_cluster_only_primary` (MEDIUM-1)
6. `test_vendi_default_encoder_model_id_is_all_mpnet_base_v2` (MEDIUM-4)
7. `test_vendi_kernel_sensitivity_panel_shape` (HIGH-1 preregister API)

### `test_ipip_neo.py` (7 件)

1. `test_administer_ipip_50_replay_determinism`
2. `test_administer_ipip_50_no_personality_keywords_in_prompt` (HIGH-4)
3. `test_administer_ipip_50_deterministic_shuffle_seed_stable` (HIGH-4)
4. `test_administer_ipip_50_decoy_items_filtered_in_scoring` (HIGH-4)
5. `test_administer_ipip_50_japanese_raises_not_implemented` (HIGH-3)
6. `test_compute_ipip_diagnostic_acquiescence_balanced`
7. `test_compute_ipip_diagnostic_straight_line_detection`

### `test_big5_icc.py` (6 件)

1. `test_compute_big5_icc_identical_windows_degenerate_returns_one` (HIGH-2 / MEDIUM-5 / LOW-2)
2. `test_compute_big5_icc_consistency_vs_agreement_offset_sensitivity` (HIGH-2)
3. `test_compute_big5_icc_me1_fallback_uses_consistency_only` (HIGH-2)
4. `test_compute_big5_icc_db9_uses_agreement_only` (HIGH-2)
5. `test_compute_big5_icc_bootstrap_cluster_only_seed_stable` (MEDIUM-1)
6. `test_compute_big5_icc_uncorrelated_windows_below_threshold`

### `test_eval_store.py` 追加 (2 件)

1. `test_fetch_tier_b_metric_returns_window_index_and_notes_metadata` (MEDIUM-2)
2. `test_tier_b_metric_isolation_from_training_view` (DB5 contract sentinel)

合計 22 件。

## 11. effort estimate (final)

| Phase | 推定 (final) |
|---|---|
| design-final.md (本書、済) | 30min ✓ |
| decisions.md ME-10〜ME-15 ADR 追記 | 30min |
| Implementation (3 file + 22 test + eval_store helper) | 4-5h (HIGH-4 anti-demand + sensitivity API で +0.5h) |
| PR description + commit + push | 30min |
| **本 phase 残合計** | **~5-6h** |

## 12. (Optional) /clear hand-off note

context が 30%↑なら `/clear`、次セッション resume 時は:

1. 本 `p4a-tier-b-design-final.md` を Read
2. `decisions.md` ME-10〜ME-15 を Read
3. `codex-review-p4a.md` の HIGH 4 + MEDIUM 5 を逐語確認
4. branch `feat/m9-eval-p4a-tier-b` 作成 → Phase E 実装着手

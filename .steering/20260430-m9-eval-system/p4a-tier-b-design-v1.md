# P4a Tier B — design v1 (Plan mode 初回案)

> 本 v1 は意図的に /reimagine で破棄される対象。次の v2 が別の出発点 (例: prior
> art / ICC stability 起点) から再生成され、design-comparison.md で hybrid v3 を
> 検討する。HIGH 検出は Codex review に委ねる。
>
> Refs: launch prompt (`mac-p4a-tier-b-launch-prompt.md`)、plan file
> (`m9-eval-system-p4a-tier-glistening-tulip.md`)、ADR DB9/DB10/DB11 (M9-B)、
> ME-1/ME-4/ME-5 (M9-eval)、Codex HIGH-2/HIGH-5 (P5)、PR #146 P5 hardening
> (`hierarchical_bootstrap_ci(cluster_only=True)`)。

## 1. Mission

`src/erre_sandbox/evidence/tier_b/` をゼロから起草し、LoRA 採用判定 (DB9 quorum)
の 3 sub-metric (Vendi Score / Big5 stability ICC / Burrows Δ) のうち、Tier B
新規 2 件 (Vendi / Big5 ICC) と IPIP-NEO 質問紙 administering helper を提供する。
Burrows Δ は `tier_a/burrows.py` 既存。

quorum role:

- adoption: 3 sub-metric の 2-of-3 が `BootstrapResult` の CI で baseline positive 方向
- rollback: 2-of-3 が baseline negative 方向
- single regression は warning のみ
- defensive canary (Tier C: self_rep / cross_echo) は本 PR scope 外

Tier B は **offensive gate の唯一の arbiter** — Tier A=floor diagnostic、
Tier C=defensive canary なので、Tier B 不在の限り LoRA 採用判定は機能不全。

## 2. The 5 question answers (v1 commitment)

### Q1. Vendi Score kernel

**v1**: semantic kernel (sentence-transformers MPNet
`paraphrase-multilingual-mpnet-base-v2`)。

- 算出: `vendi.score(utterances, k=mpnet_cosine_kernel)` 同様の
  custom path、または `vendi-score` package の cosine similarity matrix path
- multilingual 必要 (kant=ja/en mixed, rikyu=ja, nietzsche=ja/en mixed)
- `tier_a/novelty.py` で MPNet encoder lazy-load 既に存在 → 流用 (追加 dep なし)
- sanity: 直交 one-hot input → score = N (within float tolerance)。P5 残課題 close
- trade-off: per-window 100 utterances → cosine matrix 100×100。25 windows × 3 persona
  × 5 run = 375 windows。MPNet inference を 100 utt/window で batch、CPU でも
  許容範囲 (~1s/window 想定、合計 6-10 min)

**棄却候補**: unigram count kernel — multilingual 弱い、長い utterance で
N-gram-overlap 過小評価、Codex prior art に正当化させる必要が高い

### Q2. IPIP-NEO 版

**v1**: Mini-IPIP-20 (Donnellan et al., 2006)。

- 20 items × 25 windows × 3 persona × 5 run = **7,500 LLM calls**
  (vs short-50: 18,750 / full-300: 112,500)
- agentic loop overhead 最小化、qwen3:8b deterministic temp=0
- 5-point Likert (1=strongly disagree ... 5=strongly agree)
- balanced reverse-keyed: ~50% items
- Big5 dimension: 4 items × 5 dimension (E/A/C/N/O)
- 日本語 prompt 整備 (Goldberg 1992 の英語原文 + 既存日本語訳との対照)。kant/rikyu
  /nietzsche persona は system prompt で persona-conditional 環境にする
- replay determinism test: temp=0 で identical input → identical output

**Codex に問う**: short-50 (Goldberg 1992) との reliability/validity trade-off、
日本語訳の cross-language validation literature

### Q3. Big5 ICC formula

**v1**: ICC(2,k) random raters average + ICC(3,1) fixed raters single (diagnostic)。

- ICC(2,k): primary metric。run を rater (random sample) 扱い、5 run の平均
  reliability。across-mode (peripatos/chashitsu/zazen) variability も run に吸収
- ICC(3,1): diagnostic only。fixed run 単一 score の reliability。
- 算出は `pingouin.intraclass_corr` か自前 ANOVA-based formula
- ME-1 cutoff: ICC point < 0.6 OR lower CI < 0.5 が ≥2/3 personas → fallback fire
- 1.0 convergence sanity: 同一回答列 → ICC = 1.0 (within float tolerance)。
  P5 残課題 close
- bootstrap CI: per-100-turn windowed Big5 score を `cluster_only=True` で resample
  (window が cluster、5 run × 5 window = 25 cluster)

**Codex に問う**: ICC(2,k) vs ICC(3,1) vs ICC(2,1) の選択を LLM personality
stability 文脈で正当化する prior art (2024-2026)、convergence threshold 0.6 の
empirical 妥当性

### Q4. per-100-turn windowing × cluster_only bootstrap

**v1 (確定)**: 5 runs × 5 windows = 25 cluster/persona、`cluster_only=True`。

- PR #146 で `hierarchical_bootstrap_ci(values_per_cluster, *, cluster_only=True,
  n_resamples=2000, ci=0.95, seed=0) -> BootstrapResult` 完成、流用
- effective sample size 25 framing は Codex HIGH-2 で既に承諾、PR description
  + docstring で明示
- `BootstrapResult.method == "hierarchical-cluster-only"` を出力 JSON で表示

### Q5. LIWC alternative honest framing

**v1 (確定)**: DB10 Option D 通り LIWC 全廃。Tier B では新規 LIWC alternative を
**導入しない**。

- Empath は `tier_a/empath_proxy.py` に既存 (psycholinguistic axis only、Big5 claim
  しない、ME-1 既に明示)
- Big5 claim は Tier B IPIP-NEO self-report のみ
- docstring 文言 (Tier B 全 module 冒頭): 「Big5 self-report via IPIP-NEO; not LIWC,
  not a Big5 claim from external lexicon. Tier A Empath is psycholinguistic axis
  only (ME-1 / DB10).」

## 3. API skeleton (signatures)

### `src/erre_sandbox/evidence/tier_b/vendi.py`

```python
"""Vendi Score (Friedman & Dieng 2023) — diversity metric for Tier B DB9 quorum.

Computes the exponential of Shannon entropy of the eigenvalue spectrum of the
similarity kernel matrix K, normalized so K_ii = 1. With the MPNet semantic
kernel this measures **semantic diversity**: identical utterances → score=1,
fully orthogonal one-hot → score=N.

DB9 sub-metric: vendi_score. Persona-conditional: bootstrap CI per persona
across 25 windows / persona (5 runs × 5 per-100-turn windows). Use with
:func:`hierarchical_bootstrap_ci(cluster_only=True)`.

LIWC alternative honest framing (DB10 Option D): this module makes no Big5
claim; Big5 self-report goes through ``ipip_neo.py`` + ``big5_icc.py``.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

VendiKernel = Callable[[Sequence[str]], np.ndarray]
"""Stub-friendly callable: return N×N similarity matrix in [0, 1]."""


@dataclass(frozen=True, slots=True)
class VendiResult:
    """Vendi Score for one window."""
    score: float           # exp(H(eigenvalues))
    n: int                 # window size (utterances)
    kernel: str            # "mpnet-cosine" | "unigram-count" | <stub>


def compute_vendi(
    utterances: Sequence[str],
    *,
    kernel: VendiKernel | None = None,
    kernel_name: str = "mpnet-cosine",
) -> VendiResult:
    """Compute Vendi Score for a window of utterances.

    Args:
        utterances: 1 window (typically 100 turns).
        kernel: Optional stub callable (utterances -> N×N similarity).
            Default is MPNet cosine via the lazy loader.
        kernel_name: Identifier surfaced in the result.

    Returns:
        :class:`VendiResult`. Empty input → score=0, n=0.
    """
```

Plus a per-persona aggregator that takes 25 windows and returns
`BootstrapResult` via `hierarchical_bootstrap_ci(cluster_only=True)`.

### `src/erre_sandbox/evidence/tier_b/ipip_neo.py`

```python
"""IPIP-NEO Mini-20 (Donnellan et al. 2006) administering helper.

Builds the prompt, parses persona LLM responses, returns Big5 score vector.
Deterministic under temperature=0 + same seed (replay determinism test).

LIWC alternative honest framing (DB10): Big5 self-report only — no claim that
this maps to LIWC categories or any external lexicon.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

PersonaResponder = Callable[[str], int]
"""Stub-friendly: take prompt, return Likert 1..5 integer."""


@dataclass(frozen=True, slots=True)
class Big5Scores:
    """Per-administration Big5 vector."""
    extraversion: float
    agreeableness: float
    conscientiousness: float
    neuroticism: float
    openness: float
    n_items: int  # 20 for Mini-IPIP, 50 for short, 300 for full
    version: str  # "mini-ipip-20" | "short-50" | "full-300"


def administer_ipip_neo(
    responder: PersonaResponder,
    *,
    version: str = "mini-ipip-20",
    language: str = "en",
) -> Big5Scores:
    """Administer the questionnaire and return Big5 scores.

    Args:
        responder: Callable taking item prompt → 1..5 integer.
            Tests pass a deterministic stub.
        version: "mini-ipip-20" | "short-50" | "full-300".
        language: "en" | "ja" — selects the prompt corpus.

    Returns:
        :class:`Big5Scores` averaged over the items per dimension after
        reverse-keying.
    """
```

Diagnostic (常時計測、ME-1 要件):

```python
@dataclass(frozen=True, slots=True)
class IPIPDiagnostic:
    """Quality-control side-channel — never used as Big5 itself."""
    acquiescence_index: float       # logit balance over Likert 1..5
    straight_line_runs: int         # max consecutive identical answers
    reverse_keyed_agreement: float  # corr between forward / reverse pairs


def compute_ipip_diagnostic(responses: Sequence[int]) -> IPIPDiagnostic: ...
```

### `src/erre_sandbox/evidence/tier_b/big5_icc.py`

```python
"""Big5 stability ICC across runs / windows for Tier B DB9 quorum.

Sub-metric: big5_stability_icc. ICC(2,k) random-raters-average is the primary;
ICC(3,1) is reported as diagnostic. Identical responses → ICC=1.0 (sanity).

ME-1 fallback trigger: point ICC < 0.6 OR lower CI < 0.5 in ≥2/3 personas →
emit re-open candidate to ``decisions.md``.

Bootstrap CI uses :func:`hierarchical_bootstrap_ci(cluster_only=True)` over
25 windows / persona (5 run × 5 per-100-turn window).
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Big5ICCResult:
    icc_point: float              # ICC(2,k) point estimate
    icc_lower_ci: float           # 95% bootstrap lower bound
    icc_upper_ci: float           # 95% bootstrap upper bound
    icc_31_diagnostic: float      # ICC(3,1) for cross-check
    n_windows: int                # cluster count (25 typical)
    fallback_fire: bool           # ICC < 0.6 OR lower CI < 0.5
    formula: str                  # "ICC(2,k) random-raters-average"


def compute_big5_icc(
    big5_per_window: Sequence[Big5Scores],
    *,
    seed: int = 0,
    n_resamples: int = 2000,
) -> Big5ICCResult: ...
```

## 4. Persistence model (eval_store.py 統合)

`metrics.tier_b` table (already created by `bootstrap_schema()`) の column 流用:

```
run_id TEXT, persona_id TEXT, turn_idx INTEGER, metric_name TEXT,
metric_value DOUBLE, notes TEXT
```

Tier B では **`turn_idx` を `window_index` (0..24) として再利用** (column rename
は破壊的、避ける)。`metric_name` の値を以下に固定:

- `tier_b.vendi_score`
- `tier_b.big5_extraversion` ... `tier_b.big5_openness` (5 行)
- `tier_b.big5_stability_icc`
- `tier_b.big5_icc_31_diagnostic`
- `tier_b.acquiescence_index`
- `tier_b.straight_line_runs`
- `tier_b.reverse_keyed_agreement`

`notes` には JSON で kernel_name / version / formula を埋める。

### eval_store.py への additive patch

新規 helper のみ追加 (既存 API 破壊しない):

```python
def fetch_tier_b_metric(
    view: AnalysisView,
    *,
    run_id: str,
    persona_id: str,
    metric_name: str,
) -> list[tuple[int, float, str | None]]:
    """Return [(window_index, metric_value, notes), ...] for Tier B."""
    return view.execute(
        "SELECT turn_idx, metric_value, notes"
        f" FROM {METRICS_SCHEMA}.tier_b"
        " WHERE run_id = ? AND persona_id = ? AND metric_name = ?"
        " ORDER BY turn_idx",
        (run_id, persona_id, metric_name),
    )
```

DB5/DB6/DB11 contract: Tier B 計算は eval-side のみ、`metrics.tier_b` には
`connect_training_view()` から到達不可能 (training-view は `raw_dialog.dialog`
projection のみ)。**追加 assert 不要、構造的に保証済**。docstring で明示。

## 5. Test plan (9-15 件)

### `tests/test_evidence/test_tier_b/test_vendi.py` (5 件)

1. `test_compute_vendi_orthogonal_one_hot_score_equals_n` — sanity (P5 残課題)
2. `test_compute_vendi_identical_utterances_score_equals_one` — degenerate
3. `test_compute_vendi_empty_input_returns_zero_n` — boundary
4. `test_compute_vendi_kernel_stub_round_trip` — stub 経由
5. `test_compute_vendi_per_persona_bootstrap_cluster_only` — integration with
   `hierarchical_bootstrap_ci(cluster_only=True)`、25 cluster

### `tests/test_evidence/test_tier_b/test_ipip_neo.py` (5 件)

1. `test_administer_ipip_neo_mini_20_replay_determinism` — replay (temp=0 stub)
2. `test_administer_ipip_neo_reverse_keyed_consistency` — reverse-keyed score
3. `test_compute_ipip_diagnostic_acquiescence_index_balanced` — balanced
4. `test_compute_ipip_diagnostic_straight_line_detection` — 10 連続同回答
5. `test_administer_ipip_neo_japanese_prompt_round_trip` — language="ja" stub

### `tests/test_evidence/test_tier_b/test_big5_icc.py` (5 件)

1. `test_compute_big5_icc_identical_windows_returns_one` — 1.0 (P5 残課題)
2. `test_compute_big5_icc_uncorrelated_windows_below_threshold` — synthetic <0.5
3. `test_compute_big5_icc_fallback_fire_threshold` — <0.6 OR lower CI <0.5
4. `test_compute_big5_icc_31_diagnostic_present` — diagnostic surfaced
5. `test_compute_big5_icc_bootstrap_cluster_only_seed_stable` — seed determinism

### `tests/test_evidence/test_eval_store.py` 追加 (1-2 件)

1. `test_fetch_tier_b_metric_round_trip` — INSERT → SELECT
2. `test_tier_b_isolation_from_training_view` — `connect_training_view()` から
   `metrics.tier_b` 不可視を sentinel 経由で確認

合計: 16 件 (上限内)。

## 6. ADR alignment (絶対遵守)

| ADR | 制約 | Tier B 実装の対応 |
|---|---|---|
| DB5/DB6 | raw_dialog vs metrics 物理分離、`evaluation_epoch=false` only training | Tier B は `metrics.tier_b` のみ。raw_dialog 不変。docstring 明示 |
| DB9 | 3 sub-metric 2-of-3 quorum、bootstrap CI で baseline 方向判定 | vendi.py + big5_icc.py で 2/3 sub-metric 提供、Burrows は tier_a 流用 |
| DB10 Option D | LIWC 全廃、proxy framing 必須、Big5 は IPIP-NEO self-report only | Tier B 全 module 冒頭 docstring に honest framing 明示 |
| DB11 (PR #145) | Tier B 計算 path が training に漏れない構造 | DB5 で構造的担保済、docstring/comment で明示 (assert 追加不要) |
| ME-1 | IPIP-NEO fallback ICC<0.6 OR lower CI<0.5 が ≥2/3 persona | `Big5ICCResult.fallback_fire` field、acquiescence/straight-line/reverse-keyed 4 種 diagnostic |
| ME-4 | ratio 200/300 の re-eval は P4 完了 trigger | P4a 完了 = partial update #4 trigger、PR description 明示 |
| ME-5 | blake2b uint64 seed、Mac/G-GEAR 同値性 | Vendi/ICC bootstrap で `seed` 引数を頭から伝播 |

## 7. v1 で意図的に未解決にしている点 (/reimagine + Codex で challenge)

- Vendi kernel 詳細: 純 cosine vs Gram-matrix normalization vs spectrum smoothing
- IPIP-NEO 日本語 prompt の cross-language validation literature
- ICC formula: ICC(2,k) primary 選択の正当性 (LLM personality stability prior art)
- per-window n=100 turn が ICC 計算に sufficient か (rule-of-thumb / power)
- Vendi/IPIP-NEO/Big5 ICC 結果間の cross-validation (相関 / 直交性)

## 8. Out of scope (この PR で触らない)

- LoRA training (M9-C-adopt 範囲)
- Tier C judge LLM (P6 範囲)
- G-GEAR golden baseline 採取 (P3 範囲、calibration 待ち)
- Burrows reference corpus 整備 (Tier A 既存範囲、blockers.md defer)
- persona refactor / philosopher_seed (M10-A、認知深化 PR #144)
- DB11 contamination assert 実装 (M9-C-adopt、現状 docstring 明示のみ)
- Empath/spaCy/自作 LIWC alternative の新規導入 (DB10 Option D 確定済)
- Tier B 3 metric を分割 PR で incremental merge (DB9 quorum 機能不全)

## 9. Effort estimate

| Sub-step | 推定 |
|---|---|
| design-v1.md (本書) | 30min ✓ |
| /reimagine v2 + comparison.md | 1h |
| Codex review prompt + execution + 反映 | 1.5h |
| design-final.md + decisions.md ADR 追記 | 30min |
| Implementation (3 file + tests + eval_store) | 3.5h |
| PR | 30min |
| **合計** | **~7.5-8h** (1-2 セッション) |

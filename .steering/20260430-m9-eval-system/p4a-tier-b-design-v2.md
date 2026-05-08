# P4a Tier B — design v2 (/reimagine 後、psychometric-rigor-first 起点)

> **/reimagine premise**: v1 を意図的に破棄し、別の出発点から再起草。v1 は
> infrastructure-reuse + minimum-cost を起点にした (Mini-IPIP-20、cluster_only
> only、MPNet 流用)。v2 は **psychometric rigor + statistical power を最優先** に
> し、infrastructure cost を二次評価軸として再構成する。
>
> Refs: Codex HIGH-3 (Vendi 200-turn 最小)、Codex HIGH-2 (cluster + block hierarchical
> bootstrap)、Salecha 2024 (LLM Big5 social desirability bias)、Donnellan 2006
> (Mini-IPIP reliability)、Goldberg 1992 (IPIP-50)、Shrout & Fleiss 1979
> (ICC notation)。

## v2 の基本方針 (v1 との対比)

| 項目 | v1 (infrastructure-first) | v2 (rigor-first) |
|---|---|---|
| 出発点 | bootstrap_ci PR #146 流用 | 心理測定論 + 統計検出力 |
| 評価基準 | 計算コスト・dep 重複回避 | reliability / construct validity / power |
| trade-off | 工数 8h 内に収める | 必要なら工数増を許容 |
| 失敗モード | psychometric weakness (mini-20 reliability、cluster_only over-coverage) を見逃す | infrastructure complexity 増・工数膨張 |

## 1. Mission (v1 と同じ)

`tier_b/` 3 module を提供し、DB9 quorum (Vendi / Big5 ICC / Burrows Δ) を稼働
させる。Tier B が offensive gate の唯一の arbiter。

## 2. The 5 question — v2 (rigor-first)

### Q1. Vendi Score kernel

**v2**: hybrid kernel (semantic MPNet + lexical 5-gram) + 200-turn window。

- **window 100 → 200 に拡大**: Codex HIGH-3 が「Vendi は 200-turn 最小」を
  prior art (Friedman & Dieng 2023) ベースで指摘。100 turn は spectrum collapse
  リスクが Codex 側で raise されている領域
- **kernel 拡張**: semantic alone は paraphrase に過敏、lexical alone は
  surface-form noise に過敏 → hybrid (重み 0.7 semantic / 0.3 lexical 5-gram)
- 直交 one-hot sanity (P5 残課題) は lexical 成分で達成、score=N
- 効果: window 200 化で 5 runs × 2.5 windows = **12.5 cluster/persona**
  (window 数半減、cluster 内 turn 数倍増、有効サンプル空間は同等だが
  spectrum stability は向上)
- trade-off: window 数減 → bootstrap CI width 拡大。`block_length` 内側 block
  bootstrap も併用 (cluster_only ではなく `cluster + block`)

**v2 が v1 を破壊する点**: window=100 cluster_only mode を再考。HIGH-3 を
literally 受け止め直す。

### Q2. IPIP-NEO 版

**v2**: IPIP-50 short (Goldberg 1992) — Mini-IPIP-20 では reliability 不十分。

- Mini-IPIP-20 は per-dimension **4 items**、Cronbach α が dimension 依存で
  0.6-0.7 と marginal (Donnellan 2006 self-reported)
- IPIP-50 は per-dimension **10 items**、α が安定して 0.8 以上
- agentic loop overhead: 50 items × 25 windows × 3 persona × 5 run =
  **18,750 calls** (vs mini-20: 7,500)
- qwen3:8b で 1 item ≤ 1s 想定、合計 ~5h overnight 1 回限り (M9-eval P3 で
  G-GEAR 走行と並行可)
- balanced reverse-keyed: ~50% items
- 日本語訳: IPIP-50 公式日本語版 (Murakami 2002 / 2003) を流用、出典明記

**v2 が v1 を破壊する点**: Mini-IPIP-20 は cost-only 観点。psychometric
reliability prior art は IPIP-50 を強く支持。Codex prior art search に確認させる。

### Q3. Big5 ICC formula

**v2**: ICC(A,1) absolute agreement single rater (McGraw & Wong 1996 notation
= Shrout & Fleiss 1979 ICC(2,1) absolute agreement) + ICC(2,k) consistency
diagnostic。

- **rationale 切り替え**: v1 は ICC(2,k) consistency primary。だが LoRA
  drift detection の文脈では「baseline と比べて Big5 score が同じか」を
  問うため、**absolute agreement** が construct validity 上正しい。
  consistency は rater-level offset を除外してしまう
- ICC(A,1): 単一 run の reliability、5 run でも単一 score を扱う想定
- ICC(2,k) consistency: diagnostic for cross-check
- ME-1 cutoff (ICC<0.6 / lower CI<0.5) は absolute agreement 文脈でも適用可、
  ただし **threshold 値の妥当性は再評価必要** (Koo & Li 2016 の cutoff は
  consistency ICC が中心)

**v2 が v1 を破壊する点**: formula 選択は notation 違いではなく construct
意味が異なる。LoRA drift detection の意味論で再選択。

### Q4. windowing × bootstrap

**v2**: 200-turn window × 5 runs = 12.5 cluster/persona、`cluster + block`
hierarchical bootstrap (cluster_only ではない)。

- v1 の cluster_only は per-window autocorrelation を完全に放棄。これは
  「window 内 sample 順序に意味がない」場合に正当だが、Vendi は kernel
  matrix 全体を扱うため per-window 内構造を block bootstrap で保つほうが
  variance underestimation を防ぐ
- `hierarchical_bootstrap_ci(values_per_cluster, block_length=50,
  cluster_only=False, auto_block=True)` を採用 — PR #146 の `auto_block`
  path で per-cluster block を Politis-White 推定で動的選択
- effective sample size framing は cluster (12.5) ではなく blocks 経由の
  effective n に切替

**v2 が v1 を破壊する点**: cluster_only は P5 hardening で実装したが
**Tier B の使用文脈には not necessarily right fit**。auto_block が prior art
寄り。

### Q5. LIWC alternative honest framing

**v2 (確定、v1 と同)**: DB10 Option D。Tier B では LIWC alternative 新規導入
なし。Empath は Tier A 既存範囲。

ここは v1 と一致。/reimagine も DB10 を破棄する根拠を見出さない。

## 3. API skeleton — v2 で v1 から変わる点

### `vendi.py` 差分

```python
@dataclass(frozen=True, slots=True)
class VendiResult:
    score: float
    n: int                    # 200 (v2) vs 100 (v1)
    kernel: str               # "hybrid-mpnet-5gram" (v2) vs "mpnet-cosine" (v1)
    spectrum_entropy: float   # 内部診断、kernel matrix の H(λ)
    semantic_weight: float    # 0.7
    lexical_weight: float     # 0.3
```

### `ipip_neo.py` 差分

```python
@dataclass(frozen=True, slots=True)
class Big5Scores:
    extraversion: float
    agreeableness: float
    conscientiousness: float
    neuroticism: float
    openness: float
    n_items: int     # 50 (v2) vs 20 (v1)
    version: str     # "ipip-50" (v2) vs "mini-ipip-20" (v1)
    cronbach_alpha: dict[str, float]  # 新: 各 dimension の α 計算値
```

### `big5_icc.py` 差分

```python
@dataclass(frozen=True, slots=True)
class Big5ICCResult:
    icc_point: float              # ICC(A,1) absolute agreement (v2)
    icc_lower_ci: float
    icc_upper_ci: float
    icc_2k_consistency: float     # diagnostic (v2): consistency ICC(2,k)
    n_windows: int                # 12.5 cluster (v2) vs 25 (v1)
    fallback_fire: bool           # ICC < 0.6 OR lower CI < 0.5
    formula: str                  # "ICC(A,1) absolute agreement, McGraw-Wong 1996"
    threshold_basis: str          # "Koo-Li 2016 / re-evaluated for absolute agreement"
```

## 4. Persistence — v2 (v1 とほぼ同)

`metrics.tier_b` table column 流用は v1 と同じ。v2 では `metric_name` に追加:

- `tier_b.vendi_spectrum_entropy` (内部診断)
- `tier_b.cronbach_alpha_extraversion` ... 5 行 (per dimension)
- `tier_b.big5_icc_2k_consistency_diagnostic`

`notes` JSON で kernel weights / version / formula を埋める。

## 5. Test plan — v2 で追加 (合計 18-20 件)

v1 16 件 + 追加:

- `test_compute_vendi_window_200_spectrum_stability` — 200-turn での
  kernel matrix spectrum がランダム性に対して安定
- `test_compute_vendi_hybrid_kernel_weight_sum_one` — 0.7+0.3=1.0 sanity
- `test_compute_ipip_neo_50_cronbach_alpha_lower_bound` — α >= 0.7 (synthetic)
- `test_compute_big5_icc_absolute_agreement_offset_sensitivity` — offset 加算で
  ICC が変化することを確認 (consistency なら不変、agreement なら変化)

## 6. Effort estimate — v2

| Sub-step | 推定 |
|---|---|
| 全体 | **~10-12h** (v2 は 50 items + 200 window + auto_block で +25-50%) |

v1 の 8h との差は **2-4h 増**。trade-off:

- 工数増 +2-4h
- 得るもの: psychometric reliability up (α 0.6-0.7 → 0.8+)、Vendi spectrum
  stability up、ICC construct validity 改善、auto_block で bootstrap CI 妥当性 up

## 7. v2 の意図的な懸念点

- **window 200 化が design-final.md (M9-eval) で per-100-turn を確定済**:
  確定文書の上書きが必要。decisions.md 新 ADR で justify
- **IPIP-50 日本語訳 license**: Murakami 2002/2003 の利用条件確認が要 — defer
  すれば Mini-IPIP-20 fallback
- **ICC formula 切り替えで ME-1 threshold の妥当性が揺らぐ**: Codex に
  literature 確認させる
- **auto_block の per-cluster cap が cluster_only より bootstrap CI が
  狭すぎる可能性**: synthetic AR(1) test で empirical 確認
- **agentic loop budget +150% (mini-20 → ipip-50)**: G-GEAR 並行 OK か要確認

## 8. v2 が捨てている v1 の正しさ (hybrid v3 候補)

v1 が正しい点 (v2 が損なうべきでないもの):

- **infrastructure-reuse**: MPNet encoder lazy-load 流用は依然強い
- **cluster_only mode 実装済**: PR #146 の労力を活かしたい
- **per-100-turn windowing が design-final 確定済**: 上書きは新 ADR coast 高い
- **8h 工数内に収まる**: solo cadence で安全

→ **hybrid v3 候補**:

- Vendi: window=100 維持 (design-final 整合) + hybrid kernel (semantic+lexical) 採用
- IPIP-NEO: **IPIP-50 採択** (psychometric reliability 優先)
- ICC: ICC(2,k) consistency primary 維持 + ICC(A,1) absolute agreement diagnostic
  追加 (両 framing surfaced)
- bootstrap: cluster_only primary + auto_block diagnostic を JSON 出力併載
- Window 200 化は **defer** (design-final 上書きを ADR で正当化するコスト > 利得)

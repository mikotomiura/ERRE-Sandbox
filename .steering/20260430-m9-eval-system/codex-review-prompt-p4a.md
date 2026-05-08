# Codex independent review request — M9-eval-system P4a Tier B 起草

## 役割

あなたは ERRE-Sandbox プロジェクトの **independent reviewer**。Claude が起草
した P4a Tier B 設計案 (v1 + v2 + comparison v3) を **同一モデル 1 発生成の
構造的バイアス** から救出するために招かれている。Verdict + 優先度付き finding
+ web-search-based prior art 引用で reply してほしい。要約禁止、verbatim 保存
される。

## 報告フォーマット (厳守)

1. **Verdict**: 一行 — `APPROVE` / `ADOPT-WITH-CHANGES` / `REJECT`
2. **HIGH** finding (must reflect before merge): 各 finding に
   `[HIGH-N] title` + ≥3 行 rationale + 引用 (URL or paper)
3. **MEDIUM** finding (decisions.md ADR 反映): `[MEDIUM-N]`
4. **LOW** finding (blockers.md defer 可): `[LOW-N]`
5. **Prior art summary** (web search 必須): 下記 §「Prior art 必須調査」5 件全件
6. **Closing note**: v3 hybrid を採用すべきか / v1 / v2 / 別案

## Mission の再掲

`src/erre_sandbox/evidence/tier_b/` をゼロから起草、LoRA 採用判定 (DB9 quorum)
の 3 sub-metric (Vendi Score / Big5 stability ICC / Burrows Δ) のうち Tier B
新規 2 (Vendi / Big5 ICC) + IPIP-NEO administering helper を提供する。Burrows
Δ は `tier_a/burrows.py` 既存。

DB9 quorum (M9-B `decisions.md` DB9):
- adoption: 3 sub-metric の 2-of-3 が `BootstrapResult` の CI で baseline positive
- rollback: 2-of-3 が baseline negative
- Tier A=floor diagnostic、Tier C=defensive canary、**Tier B=offensive gate
  唯一の arbiter**

## 必読 reference files (本セッション scope 内、独立 read 可能)

### Claude 設計案 (3 件、本 prompt の review 対象)

- `.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md` (infrastructure-first)
- `.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md` (psychometric-rigor-first)
- `.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md` (hybrid v3 candidate)

### ADR 制約 (絶対遵守)

- `.steering/20260430-m9-b-lora-execution-plan/decisions.md` DB1-DB11 (M9-B)
- `.steering/20260430-m9-eval-system/decisions.md` ME-1〜ME-9 (M9-eval)
- `.steering/20260430-m9-eval-system/design-final.md` (Tier B が DB9 で果たす役割)

### 既存 infrastructure (流用先)

- `src/erre_sandbox/evidence/bootstrap_ci.py` — `BootstrapResult`,
  `hierarchical_bootstrap_ci(values_per_cluster, *, block_length=50,
  cluster_only=False, auto_block=False, n_resamples=2000, ci=0.95, seed=0)`,
  `estimate_block_length()` (PR #146 P5 hardening)
- `src/erre_sandbox/evidence/tier_a/empath_proxy.py` — proxy framing docstring
  雛形 (DB10 honest framing)
- `src/erre_sandbox/evidence/tier_a/novelty.py` — MPNet
  (`paraphrase-multilingual-mpnet-base-v2`) lazy-load パターン
- `src/erre_sandbox/evidence/eval_store.py` — DuckDB schema、`metrics.tier_b`
  table column (`run_id/persona_id/turn_idx/metric_name/metric_value/notes`)、
  `connect_training_view()` は `raw_dialog.dialog` projection only (DB5
  contract)

### Codex 過去 review 履歴 (本タスクと同質補正期待の文脈)

- `.steering/20260430-m9-eval-system/codex-review.md` (P5 HIGH-2 hierarchical
  bootstrap、HIGH-3 Vendi 200-turn 最小、HIGH-5 Burrows L1)
- 過去 5 連続 (P3a-finalize / Phase 2 run0 / CLI partial-fix / run1 calibration /
  ME-9 trigger) で Claude solo 検出不能の HIGH を切出した empirical 実績あり

## v3 hybrid の要点 (review 対象)

| Q | v3 commitment |
|---|---|
| Q1 Vendi kernel | hybrid (semantic MPNet 0.7 + lexical 5-gram 0.3) |
| Q1 window | 100 turn (design-final 整合) |
| Q2 IPIP-NEO 版 | IPIP-50 (Goldberg 1992、日本語 Murakami 2002/2003 流用) |
| Q3 ICC formula | ICC(2,k) consistency primary + ICC(A,1) absolute agreement diagnostic |
| Q4 bootstrap | `cluster_only=True` primary + `auto_block=True` diagnostic 併載 |
| Q5 LIWC alternative | DB10 Option D 通り全廃、Tier B 全 module 冒頭 docstring に honest framing |

## Prior art 必須調査 (web search 強制、verbatim 引用)

以下 5 件全件で literature 引用を伴う finding を出してほしい。1 件でも skip した
ら REJECT 扱い。

1. **Vendi Score 2023 paper** (https://arxiv.org/abs/2210.02410) の kernel 選択
   - hybrid kernel (semantic + lexical) の prior art 有無
   - 100-turn vs 200-turn window の minimum sample size 議論
   - orthogonal one-hot で score=N が成立する数学的条件
2. **IPIP-NEO Mini-20 vs IPIP-50** (Donnellan et al. 2006、Goldberg 1992)
   - Cronbach α の dimension-level reliability 比較
   - LLM personality assessment の 2024-2026 prior art (e.g.,
     Salecha et al. 2024 arXiv 2405.06058、Huang et al. arXiv 2310.01386 等)
   - Mini-20 が ICC<0.6 trigger を不当発火させるリスク
3. **ICC for LLM personality stability** prior art (2024-2026)
   - ICC(2,k) consistency vs ICC(A,1) absolute agreement の選択基準
   - Koo & Li 2016 cutoff (0.5/0.75/0.9) が absolute agreement に適用可か
   - drift detection 文脈での appropriate ICC formula
4. **LIWC vs Empath empirical equivalence** (Fast et al. 2016)
   - DB10 Option D (LIWC 全廃) の justifiability
   - Tier A Empath proxy framing が DB10 honest framing 要件を満たすか
5. **Mini-IPIP / IPIP-50 日本語版** (Murakami 2002/2003)
   - 利用条件 (open / 学術 / 商用)、license, retrieval URL
   - cross-language validation 問題

## review で必ず check してほしい質問群

下記は launch prompt §「Codex review で必須に問うこと」全件を細分化したもの。
省略禁止。

### Vendi 関連

- Q1A: hybrid kernel weight 0.7/0.3 の妥当性 (Friedman & Dieng 2023 Section 4)
- Q1B: window 100 turn が Vendi spectrum stability に sufficient か
  (Codex 過去 HIGH-3 で 200-turn 最小と指摘、v3 で 100 維持の trade-off)
- Q1C: orthogonal one-hot で score=N が成立する条件と sanity test 設計
- Q1D: multilingual (ja+en mixed) で MPNet kernel が semantic similarity を
  fairly 測れるか

### IPIP-NEO 関連

- Q2A: IPIP-50 vs Mini-IPIP-20 の Cronbach α gap が ME-1 fallback (ICC<0.6)
  trigger 判定に与える影響
- Q2B: 日本語 IPIP-50 (Murakami 2002/2003) の利用 license 確認、
  defer 必要なら fallback path
- Q2C: persona-conditional prompt (kant/rikyu/nietzsche system prompt + IPIP-NEO
  item) の framing が social desirability bias (Salecha 2024) に耐えるか
- Q2D: 5-point Likert vs 7-point Likert の trade-off (LLM agentic loop 文脈)
- Q2E: balanced reverse-keyed item 比率 (~50%) の妥当性

### Big5 ICC 関連

- Q3A: ICC(2,k) consistency と ICC(A,1) absolute agreement のどちらを ME-1
  trigger primary にするべきか
- Q3B: ME-1 threshold 0.6 (point) / 0.5 (lower CI) が absolute agreement にも
  literally 適用可か、再評価必要か
- Q3C: per-window n=100 turn が ICC 計算に sufficient か (rule-of-thumb / power
  analysis literature)
- Q3D: identical 回答列 → ICC = 1.0 の sanity test が両 formula で成立するか
- Q3E: 5 run × 5 window = 25 cluster で ICC 信頼区間が construct validity に
  耐えるか

### bootstrap 関連

- Q4A: `cluster_only=True` primary + `auto_block=True` diagnostic 併載が JSON
  consumer 側で混乱を招かないか
- Q4B: PR #146 で `cluster_only` を承諾した HIGH-2 framing と矛盾しないか
- Q4C: 25 cluster (cluster_only) と 12.5 cluster (200-turn window 案) の
  effective sample size 比較
- Q4D: bootstrap CI が persona-conditional でなく pooled で運用される場合の
  variance underestimation リスク

### LIWC 関連

- Q5A: DB10 Option D (LIWC 全廃) の literature justifiability
- Q5B: Tier B 全 module 冒頭 docstring の honest framing 文言が DB10 要件を
  satisfied するか (`empath_proxy.py` 雛形と同等の rigor か)

### 設計全体

- Q6A: v3 hybrid が v1 + v2 の structural bias を残していないか (independent
  reviewer 視点)
- Q6B: `metrics.tier_b` の column schema (`turn_idx` を `window_index` 意味で
  再利用) の semantic abuse リスク
- Q6C: DB11 contamination prevention (PR #145) の Tier B 観点 follow-up
- Q6D: P5 残課題 2 件 (Vendi orthogonal one-hot test / Big5 ICC 1.0 convergence
  test) を本 PR で close する妥当性

## 出力先

verdict + finding は **そのまま raw text** で reply。Claude が
`.steering/20260430-m9-eval-system/codex-review-p4a.md` に **verbatim 保存**
する (要約禁止)。

## 工数 expectation

- web search 5 件全件 + finding 起票で **30-40 分**、token 予算 ~150K-200K
  程度を想定 (`.codex/budget.json` の per-invocation max 内)

## 最後に

直近 5 連続の Codex review で Claude solo 検出不能の HIGH を毎回切り出してきた
empirical 実績がある。本 review でも同質の補正を期待する。Adopt-with-changes
が default expected verdict。

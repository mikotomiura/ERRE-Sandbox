# M10-0 Individuation Metrics — Threshold Preregistration (`thresholds.md`)

> **WP9** / M10-0 ① individuation-metrics PR-4 doc 成果物。
> **Status**: PREREGISTRATION (数値は freeze date まで未確定でよい。`protocol_id` は M10-0 で frozen)。
> **Baseline**: **no-LoRA / prompt persona**(ADR-PM-8 gate DISCHARGED = terminal REJECT、canonical §Y.1/§Y.2)。

⚠ 本 doc は **acceptance 閾値の事前登録 (preregistration)** であり、実装コードの
`src/erre_sandbox/contracts/thresholds.py`(M2 受け入れ閾値、pydantic)とは別物。
本 doc は M10-0 individuation の calibration protocol を固定するための **markdown 仕様**。

---

## §0. Claim boundary（canonical §0、本 doc での 1 回明示）

- Layer 2 (Cite-Belief Discipline) は **Social-ToM proper の sufficient statistic ではない**。
- M10-0 では Layer 2 3 metric すべてが **`status='unsupported'` 100% pin**(active 計測なし)。
- SWM Jaccard / recovery は M10-0 で **valid を返さない**(`METRIC_SPECS` が構造的に禁止)。

---

## §1. State model（v2 §2.5、HIGH-1 反映）

各 threshold は以下のいずれかの **state** を持つ:

| state | 意味 |
|---|---|
| `frozen(value, freeze_date, calibration_source)` | 数値固定済み |
| `calibrate_before_unblinding(protocol_id, data_split)` | 数値未固定、protocol で固定する宣言 |
| `defer(target_milestone, reason)` | 後続 milestone へ送る |

- すべての threshold は `protocol_id` を持ち、**`protocol_id` 自体は M10-0 で frozen**。
- calibration data と evaluation data は **必ず disjoint**(`data_split` で明示)。
- protocol には bootstrap CI rule / exclusion rule / degenerate handling / effect direction を含む。
- circular gate（評価直前に同じ data で閾値選定 + 成功判定）を防ぐため `data_split` 必須。

---

## §2. ⚠ 継続バイアス guard（canonical §Y.4、最重要 acceptance note）

- M10-0 の threshold は **metric validity / data-quality / descriptive reporting** 用であって、
  **LoRA / Plan B の objective ではない**。
- ⚠ **prompt variant / baseline 選択を Vendi-Burrows 同時改善で選ばない**。
  旧 draft の `burrows_base_retention ≥` / `vendi_diversity ≥` を「両方改善したら成功」へ
  逆戻りさせる余地を塞ぐ。terminate した Plan B の sunk momentum が threshold/baseline 選択経路から
  侵入するのを防ぐ。
- M10-0 は Vendi/Burrows を **descriptive individuation metric として計測するが simultaneity を
  最適化しない**(simultaneity 最適化 = terminate 済 Plan B の objective、Q1 で conclusive に foreclose 済)。
  M9-C finding は Layer 1 の **解釈ノート**としてのみ参照する。

---

## §3. Layer 1 threshold（8 entry、v2 §2.5）

> ⚠ **全 entry を active と読まないこと**。各 entry は preregistration **state** と、
> 現行 M10-0 individuation 実装での **status** を別々に持つ。後者の値域は
> `active`（valid-capable に実装済）/ `unsupported`（input channel 構造的不在）/
> `diagnostic`（診断専用、acceptance gate 不参入）/ `deferred`（M10-0 では未計測）。

| # | threshold | preregister state | M10-0 実装 status | protocol |
|---|---|---|---|---|
| 1 | `burrows_base_retention ≥`（→ §3.1 で再定義） | `calibrate_before_unblinding(P-BURROWS, split=[run0-2]→cal/[run3-4]→eval)` | **active**（en/de は valid-capable）。実 golden は ja のため **unsupported** | P-BURROWS: en/de のみ valid、ja unsupported、bootstrap 1000 resample、95% CI |
| 2 | `pairwise centroid distance ≥` | `calibrate_before_unblinding(P-CENTROID, split=同上)` | **active**（same-base N≥2 で valid-capable）。実 golden は N=1 のため **degenerate** | P-CENTROID: `embedding_model_id` pinned、effect direction = greater |
| 3 | `vendi_diversity ≥` | `calibrate_before_unblinding(P-VENDI, split=同上)` | **active**（実 golden で valid） | P-VENDI: kernel sensitivity follow-up 完了後 freeze |
| 4 | `worldmodel_update_adoption_rate band` | `frozen([0.05, 0.40], 2026-05-08, DA-12)` | **deferred** — `WorldModelUpdateHint` LLMPlan は M10-C territory、M10-0 individuation では非計測 | DA-12 由来 |
| 5 | `belief_variance > 0` | `frozen(0, 2026-05-08, design-final.md §5)` | **active**（input-present 時 valid-capable）。実 golden は belief substrate 不在のため **unsupported** | strict |
| 6 | `personality_drift_offset bound` | `defer(M11-C, multi-individual divergence 観測待ち)` | **deferred**（M11-C） | DA-12 |
| 7 | `big5_icc (within-base)` | `defer(M11-C, N≥3 必須)` | **diagnostic**（diagnostic-only、acceptance gate 不参入、MEDIUM-3） | ICC(A,1)/ICC(C,k) を診断用途 |
| 8 | `recovery_rate band` | `defer(M11-C, M11-B development_state 後 calibrate)` | **unsupported** — `intervention_recovery_rate` は `reason="requires perturbation protocol run, M11-C territory"`（→ `recovery-protocol.md` と整合） | HIGH-3 で protocol 設計変更（`recovery-protocol.md` 参照） |

### §3.1 ⚠ `burrows_base_retention` 名称再定義（canonical §Y.3、REJECT 分岐）

no-LoRA baseline では Burrows は空洞化しないが「**LoRA base retention**」ではなくなる:

- **再定義**: 「**prompt-persona stylometric anchoring / reference-corpus distance**」
  （prompt persona の文体的固着 / reference corpus との距離）。
- ⚠ **LoRA ADOPT 前提の旧閾値を流用しない**。旧 draft の LoRA-base-retention 閾値は REJECT 分岐で無効。
  P-BURROWS protocol は **prompt-baseline 前提で再 calibrate** する。

---

## §4. metric ↔ M10-0 実 golden status マッピング（全 12 METRIC_SPECS、honest 全景）

> §3 の閾値名は acceptance 用語で、`policy.METRIC_SPECS` の 12 metric とは 1:1 でない。
> **全てを active と誤読させない**ため、実装済 12 metric の現行 status を明示する
> （source: `evidence/individuation/layer1.py` / `cite_belief.py`、design.md §10.4 実 golden 表）。

| metric_name | channel | M10-0 実 golden status | 備考 |
|---|---|---|---|
| `burrows_base_retention` | utterance | **unsupported**（ja 短絡） | en/de は valid-capable（§3.1 再定義） |
| `semantic_centroid_distance` | utterance | **degenerate**（N=1 same-base） | N≥2 で valid-capable |
| `vendi_diversity` | utterance | **valid** | base 内 N≥2 |
| `cognitive_habit_recall_rate` | behavioral | **degenerate**（`mode` 列空） | valid-capable、channel 不在で degenerate |
| `action_adherence_rate` | behavioral | **degenerate**（LLMPlan 非 capture） | 同上 |
| `zone_behavior_consistency` | behavioral | **valid** | zone 充実 + preferred_zones 既知 |
| `belief_variance` | belief_substrate | **unsupported**（substrate 不在） | input-present 時 valid-capable |
| `world_model_overlap_jaccard` | world_model | **unsupported**（never valid） | `reason="SubjectiveWorldModel not captured in raw_dialog; SWM Jaccard active at M10-A"` |
| `intervention_recovery_rate` | recovery | **unsupported**（never valid） | `reason="requires perturbation protocol run, M11-C territory"` |
| `cite_belief_discipline.provisional_to_promoted_rate` | belief_substrate | **unsupported** | M-L2-1、§5 |
| `cite_belief_discipline.cited_memory_id_source_distribution` | citation_substrate | **unsupported** | M-L2-2、§5 |
| `cite_belief_discipline.counterfactual_challenge_rejection_rate` | citation_substrate | **unsupported** | M-L2-3、§5 |

---

## §5. Layer 2 threshold（3 entry、すべて unsupported state、canonical §C.6）

| Threshold | State | Protocol |
|---|---|---|
| `cite_belief_discipline.provisional_to_promoted_rate` | **unsupported** — 現行 `belief_kind` schema に provisional/promoted 不在、`status='unsupported'` 100% pin | schema 拡張 task で active 化後 calibrate（block/cluster bootstrap、autocorrelation 補正後 effective N report） |
| `cite_belief_discipline.cited_memory_id_source_distribution` JS divergence | **unsupported** — M10-C `cited_memory_ids` schema 確定後に descriptive estimation 切替、M10-0 では threshold 不参入 | M10-0 では計測しない（`status='unsupported'` 100% を behavior pin） |
| `cite_belief_discipline.counterfactual_challenge_rejection_rate` | **unsupported** — perturbation 実走 M11-C territory、`status='unsupported'` 100% pin | M11-C で perturbation 実走後 calibrate（within-individual non-perturbation baseline、effect direction = greater、p<0.05 after FDR、block/cluster bootstrap） |

---

## §6. Layer 4 (deferred) entry

| Threshold | State | Protocol |
|---|---|---|
| Layer 4 Social-ToM proper（全 metric） | `defer(M11-C, multi-agent rollout 後 calibrate)` | M11-C task `m11-c-social-tom-proper` で protocol design（→ `social-tom-scenarios.md`） |

---

## §7. Acceptance（canonical §C.7 A11）

- **A11**: 本 `thresholds.md` の全 threshold が §1 の state（frozen / calibrate_before_unblinding / defer）
  のいずれかであり、`protocol_id` が固定されている。数値は freeze date 到達まで未確定でよい。
- Layer 2 全 3 metric は **unsupported state** で記載（§5）。
- ⚠ **A5（cache benchmark frame）は本 PR-4 の scope 外**(WP6、別 PR へ defer)。よって本 doc 完了時点では
  **M10-0 close（A1〜A18 full pass）には至らない**。M10-0 close 条件は WP6 完了後（`tasklist.md` PR-5 参照）。

---

## 関連 doc

- `recovery-protocol.md`（WP10、recovery_rate / counterfactual_challenge protocol）
- `prompt-ordering-contract.md`（WP7）
- `social-tom-scenarios.md`（WP11、Layer 4 handoff）

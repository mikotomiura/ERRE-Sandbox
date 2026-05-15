# 設計 (HISTORICAL / SUPERSEDED) — pre-M10 design synthesis (M10 評価体制 concrete robust design)

> ⚠️ **HISTORICAL REFERENCE ONLY — DEPRECATED** (Codex MEDIUM-5 反映、2026-05-15)
>
> 本書は `/reimagine` 経由で **意図的に破棄** された初版案 (capability-oriented scenario-lib、Layer 2 = Social-ToM 専用、5 metric × 7 scenario × 5 NC)。
> ADR-PM-6 (Hybrid-A revised 採用、2026-05-15) で **SUPERSEDED**。
> **Implementation reference**: `design-final.md`
> **Alternative explored**: `design-reimagine.md` (process-trace + power-first)
>
> 本書の内容を実装に踏襲しないこと。M10-0 sub-task scaffold / Codex 14th 以降の review は `design-final.md` を起点とする。
> 本書は `/reimagine` 規約に従った design discipline 履歴として保持される。

---

> 本書の中核は §3 「M10-0 評価体制 concrete robust design」。
> §1-§2 は context、§4-§7 は §3 設計から派生する配置決定 / patch / scaffold / memo の整理。
> User 直接指示 (2026-05-15) 「m10 では具体的に ToM などを含めた評価体制を具体的に強固に設計してから決めてください」を受け、placement-first を design-first に逆転させている。

---

## §1. memo 要旨

### `idea_judgement.md` (Corpus2Skill 型 source_navigator) — 2026-05-12 起草

- 公式 `dukesun99/Corpus2Skill` 直接導入は不採用 (Anthropic API 必須、license 未確認)
- 論文の compile-then-navigate pattern を **ローカル再実装** する案を「8/10、強い採用候補」
- M10-0 preflight として設計するのが最適 (runtime 非接続、史料・evidence の階層 navigator)
- 4 idea: persona source navigator / M10 WorldModel citation navigator / Evaluation Corpus QA harness / Developer navigation skill
- MVP scope: Kant のみ / depth 2 / markdown+JSON / 6 cognitive_habits 全件が `source / flag / trigger_zone / document_ids / provenance` に辿れる

### `idea_judgement_2.md` (LLM 研究開発手法と評価調査) — 2026-05-13 起草

- 結論: FT 手法 (QDoRA) より先に **人格・社会性・個体化を測る評価基盤を厚く** する
- M10-0 で必須:
  - `metrics.individuation`、`AnalysisView` loader (v2 draft で吸収済)
  - 4 個体化 metrics (うち 3 件 v2 draft 吸収、`intervention_recovery_rate` は protocol 化済)
  - metric 相関行列 / `thresholds.md` `calibrate_before_unblinding` (v2 draft 吸収済)
  - **Social-ToM 最小 spec (ExploreToM/SocialEval 翻案)** ← **v2 draft 未吸収、本 synthesis で concrete 化**
- M12+: QDoRA ablation registry (yaml format 提示済)
- 採用順序: M10-0 evaluation expansion → Social-ToM/counterfactual protocol → QLoRA-LoRA baseline freeze → QDoRA ablation

---

## §2. v2 draft 既吸収項目 mapping 表

`.steering/20260508-cognition-deepen-7point-proposal/m10-0-concrete-design-draft.md` (PR #159、Codex 12th HIGH 5 反映済) で既に吸収されている項目:

| idea_judgement_2.md 項目 | v2 draft 反映先 |
|---|---|
| `metrics.individuation` schema 配下 | §2.3、HIGH-2 反映 |
| `AnalysisView` loader (raw_dialog window 抽出) | §2.2 / §2.9 / WP5、HIGH-5 反映 |
| `cognitive_habit_recall_rate` / `action_adherence_rate` / `zone_behavior_consistency` | §2.2 matrix、MEDIUM-2 |
| `thresholds.md` `calibrate_before_unblinding` state | §2.5、HIGH-1 |
| DB11 sentinel poison row test | §2.4 A9、HIGH-2 |
| metric correlation matrix | §2.4 A10、MEDIUM-4 |
| QDoRA M12+ ablation gate | §2.7 out-of-scope |
| persona/source checklist M10-A defer | §2.7 out-of-scope |
| MeCab ja-tokenizer 別 task | §2.7 + WP4 削除、HIGH-4 + MEDIUM-5 |
| Vendi kernel sensitivity 別 task | §2.7 |
| Big5 ICC は diagnostic only / N≥3 で M11-C active | §2.2 / §2.5、MEDIUM-3 |
| `counterfactual_challenge` 隔離 + 3 種 negative control | §2.6、HIGH-3 |
| recovery protocol (Burrows + behavioral dual channel) | §2.6 |

**v2 draft 未吸収** (本 synthesis で対処):

- idea_judgement.md 全 4 idea (source_navigator) → §4 で配置 (B-1)
- idea_judgement_2.md §2 Social-ToM minimum spec → **§3 で concrete 化**
- idea_judgement_2.md §4 PEFT ablation registry yaml → §4 で linkback (B-3)
- idea_judgement_2.md §2 MentalAlign / HEART (emotional/cognitive alignment) → §3.9 で defer 採否

---

## §3. M10-0 評価体制 concrete robust design (中核)

### §3.1 評価体制の上位構造 (4 layer)

M10-0 の評価体制を以下の 4 layer に分割し、それぞれ独立した metric channel + provenance + acceptance を持つ。layer 間の直交性は §3.8 で相関行列 detection。

```
Layer 1: Individuation (個体化)
  - 既存 v2 draft §2.2 matrix の 11 metric
  - Burrows / Vendi / centroid / belief_variance / SWM Jaccard / habit_recall / action_adherence / zone_behavior
  - Population-level + per-individual aggregation
  - Schema: metrics.individuation (v2 §2.3、provenance 7 fields)

Layer 2: Social-ToM (社会的心の理論)  ← 本 synthesis で concrete 化
  - 新規 scenario harness + 5 metric (§3.3)
  - Zone × scenario × counterfactual variant の格子
  - Schema: metrics.social_tom (新規、§3.4、metrics.* namespace で DB11 防御下)

Layer 3: Counterfactual perturbation (反事実摂動)
  - v2 draft §2.6 protocol を v3 (§3.5) に拡張
  - opposite-stance memory 隔離 + SWM write 禁止 + negative control 5 種 (§3.6、3→5 拡張)
  - Schema: metrics.individuation の channel 拡張 (perturbation tick window で計測)

Layer 4: (defer) Emotional / cognitive alignment  ← §3.9 で defer 採否
  - HEART / MentalAlign 翻案、Tier C/D rubric
  - 臨床主張は明示的に排除 (idea_judgement_2.md §1)
  - M10-0 では out-of-scope、M11+ task として保留
```

#### 各 layer の独立性根拠

- Layer 1 ↔ Layer 2: Individuation は **同一 base 個体の発達** を測る、Social-ToM は **他者表象** を測る。channel は base habit retention vs theory-of-mind operations で完全に異なる。
- Layer 2 ↔ Layer 3: Social-ToM は **観測非対称下での belief 推論**、Counterfactual perturbation は **opposite-stance evidence injection 時の base 復元力**。前者は scenario で他者を立てる、後者は injection を行う。**重なる場合は §3.5 で明示的に separate scenario と declare**。
- Layer 1/2/3 ↔ Layer 4: Emotional alignment は qualitative manual rubric が大きく、quantitative pipeline と分離が安全。

### §3.2 Social-ToM scenario 設計 (zone × base scenario × counterfactual variant)

`docs/glossary.md` の 5 zone のうち、Social-ToM に適した 3 zone を選定:

#### S-CHA (chashitsu = 茶室、private witness asymmetry)

**base scenario S-CHA-1**: object_event_witnessed_by_A_only
- Setup: agent A と B が chashitsu に入室、B が一時退室、A だけが object event (例: 茶器の位置移動) を目撃、B 帰室
- A の発話を観測しないまま B に「茶器がどう動いたか」を質問
- Probe: B の belief は「移動前」状態のまま (false belief retained)、A は移動後を知っている (true belief)
- Test: B の発話が false belief consistent か、A の testimony を受けた後に belief update するか
- Counterfactual variant S-CHA-1c: A が嘘の testimony を行う場合の B の belief stability

**base scenario S-CHA-2**: shared experience but divergent interpretation
- Setup: A と B 同席で同じ茶事象を観察、A は美的価値で評価、B は儀礼適合性で評価
- Probe: A→B / B→A の cross-interpretation request
- Test: 自己の interpretation が他者と divergent と認識し、self-perception と attributed-perception を分離するか

#### S-AGO (agora = 議論場、public discourse with rumor)

**base scenario S-AGO-1**: B has false rumor about C
- Setup: A は C と直接話した経験あり、B は C の伝聞 (rumor) を信じている、A と B が agora で C について discuss
- Probe: A が「C に直接聞いた」と発話した後、B の belief update
- Test: testimony 階層 (direct experience > second-hand report) を model し、自己の belief source を区別するか

**base scenario S-AGO-2**: persuasion vs base habit retention
- Setup: agora で他者 N (>1) から base persona の cognitive habit と矛盾する意見を sustained に受ける
- Probe: base habit が retain されるか erode するか
- Test: peer pressure 下の base retention rate、§3.5 counterfactual perturbation protocol と併用

#### S-GAR (garden = 庭、reflective synthesis with counterfactual)

**base scenario S-GAR-1**: counterfactual challenge in solitude
- Setup: agent A が garden で reflection、外部 counterfactual_challenge channel で opposite-stance evidence が injection される (v2 draft §2.6 と同 channel)
- Probe: A の reflection が counterfactual evidence を採用するか、cite-disabled で reject するか
- Test: §3.5 protocol v3 と direct integration

**base scenario S-GAR-2**: belief revision with cited source asymmetry
- Setup: 過去 tick の dialog から retrieved memory に「自身が cite した source」と「他者が cite した source」が混在
- Probe: source attribution の retention、cite_memory_ids の source-of-cite が belief revision priority を持つか
- Test: WorldModelUpdateHint adoption (M10-C territory) の前段として、source-aware retention を計測

### §3.3 Social-ToM metric set (5 metric、独立 channel として定義)

| Metric | Input channel | What | Aggregation | Phase | Notes |
|---|---|---|---|---|---|
| `false_belief_recovery_rate` | agent dialog response in S-CHA-1 / S-AGO-1 | false belief を持つ他者が testimony 後に belief update する rate (他者 model 側) | per-scenario × per-individual | M10-0 protocol、M11-C 実走 | testimony 階層を区別 |
| `info_asymmetry_handling_rate` | S-CHA-1 / S-AGO-1 dialog | 自己が知っている事と他者が知っている事を分離して発話する rate | per-scenario × per-individual | M10-0 protocol、M11-C 実走 | self/other belief split |
| `counterfactual_resistance_rate` | S-GAR-1 dialog under §3.5 perturbation | opposite-stance evidence injection 下で base habit が retain される rate | per-individual | M10-0 protocol、M11-C 実走 | §3.5 protocol v3 と相互参照 |
| `opposite_stance_adoption_rate` | S-GAR-1 dialog under §3.5 perturbation | (**禁止指標**: 低くあるべき) counterfactual evidence を base belief として採用する rate | per-individual | M10-0 protocol、M11-C 実走 | acceptance: ≤ baseline_no_individual + 0.05 |
| `source_attribution_retention_rate` | S-GAR-2 dialog | cite_memory_ids の source-of-cite (self vs other) が belief revision で priority を保つ rate | per-individual | M10-0 protocol、M10-C 実走 (WorldModelUpdateHint と相互) | M10-C 経由で active 化 |

#### channel 独立性の論証

- `false_belief_recovery_rate` ↔ `info_asymmetry_handling_rate`: 前者は他者の belief を model し update する、後者は **自己の発話制御** で分離する。input channel は同じだが evaluation 観点が異なる (他者 model 側 vs 自己発話側)。
- `counterfactual_resistance_rate` ↔ `opposite_stance_adoption_rate`: 同 scenario の **inverse** (base 維持 / opposite 採用) を測る。両方 ≥ 0 の関係だが、theoretical な complement ではない (mid-range の hedging 発話があるため `1 - x` ではない)。
- `source_attribution_retention_rate` は M10-C 依存 → M10-0 では protocol 固定のみ、active 計測は M10-C close 後。

### §3.4 Schema (DuckDB `metrics.social_tom` table)

v2 draft §2.3 `metrics.individuation` と同じ provenance pattern を踏襲、namespace `metrics.*` で DB11 sentinel grep の防御下に固定:

```sql
CREATE TABLE metrics.social_tom (
  -- identification
  run_id            TEXT NOT NULL,
  scenario_id       TEXT NOT NULL,        -- S-CHA-1 / S-CHA-1c / S-CHA-2 / S-AGO-1 / S-AGO-2 / S-GAR-1 / S-GAR-2
  scenario_variant  TEXT NOT NULL,        -- base / counterfactual / negative_control_<id>
  individual_id     TEXT NOT NULL,        -- 主体 agent (A)
  other_agent_ids   TEXT NOT NULL,        -- JSON array of agent ids (B, C, ...)
  base_persona_id   TEXT NOT NULL,
  tick_start        BIGINT NOT NULL,
  tick_end          BIGINT NOT NULL,
  metric_name       TEXT NOT NULL,        -- §3.3 5 metric のいずれか
  channel           TEXT NOT NULL,        -- dialog_response / belief_probe / source_citation
  -- typed result (v2 §2.4 と同型)
  status            TEXT NOT NULL CHECK (status IN ('valid','degenerate','unsupported')),
  value             DOUBLE,
  reason            TEXT,
  -- provenance (v2 §2.3 と同型 + Social-ToM 固有)
  metric_schema_version             TEXT NOT NULL,
  source_table                      TEXT NOT NULL,   -- raw_dialog.dialog
  source_run_id                     TEXT NOT NULL,
  source_epoch_phase                TEXT NOT NULL,   -- evaluation のみ (training reject)
  source_individual_layer_enabled   BOOLEAN NOT NULL,
  source_filter_hash                TEXT NOT NULL,
  scenario_protocol_version         TEXT NOT NULL,   -- 新、§3.2 scenario lib の version
  negative_control_id               TEXT,            -- §3.6 negative control 適用時のみ
  embedding_model_id                TEXT,
  computed_at                       TIMESTAMP NOT NULL
)
```

**サイドカー JSON** (`*.duckdb.social_tom.json`、`*.individuation.json` の sibling):
- per-scenario population-level summary
- training manifest input にしない (DB11 sentinel poison row test を `metrics.individuation` と同様に必須)

### §3.5 Counterfactual perturbation protocol v3 (v2 §2.6 拡張)

v2 §2.6 の v2 を、Social-ToM scenario S-GAR-1 と統合する v3 に拡張:

```
prep:
  1. base individual を T_base = 200 tick (zone は base persona の preferred_zone) → baseline:
     - Burrows / cognitive_habit_recall / action_adherence (individuation channel)
     - false_belief_recovery / info_asymmetry_handling (Social-ToM channel、S-CHA-1 / S-AGO-1 を baseline tick で実走)

perturbation:
  2. counterfactual_challenge channel に opposite-stance content N=5 を injection (v2 §2.6 と同)
     - retrieved_memories とは別 channel
     - cited_memory_ids 集合に含めない
     - WorldModelUpdateHint adoption の evidence source として無効化
     - perturbation 中 SWM write 禁止 (replay-only)
     - 注入は agora 風 sustained discourse (S-AGO-2) でも garden 風 solitude (S-GAR-1) でも独立に実走
  3. T_perturb = 50 tick → perturbed_floor 計測 (両 channel)

recovery:
  4. counterfactual_challenge 除去後 T_recover = 200 tick → post recovery 計測
     - Burrows / habit recovery (individuation)
     - counterfactual_resistance_rate / opposite_stance_adoption_rate (Social-ToM)

metric:
  recovery_rate (Individuation 既存) = (post - perturbed_floor) / (baseline - perturbed_floor)
    channels: Burrows / cognitive_habit_recall / action_adherence
  counterfactual_resistance_rate (Social-ToM 新)
    = 1 - (perturbed_floor_opposite_adoption / scenario_max_adoption)
  opposite_stance_adoption_rate (Social-ToM 新、禁止指標)
    = perturbed_floor_opposite_adoption / scenario_max_adoption
  stickiness_rate (M11-C 実走): SWM entry persistence ratio
```

#### Layer 3 と Layer 2 の boundary

- S-AGO-2 / S-GAR-1 は §3.5 perturbation を **必ず** 適用する
- S-CHA-1 / S-CHA-2 / S-AGO-1 / S-GAR-2 は **perturbation なし** で計測 (Layer 2 純粋計測)
- S-CHA-1c (lying testimony) は perturbation でなく **scenario-internal counterfactual** (testimony 自体が false) で、Layer 2 内に閉じる

### §3.6 Negative control 拡張 (v2 §2.6 の 3 種 → 本設計で 5 種)

v2 §2.6 の 3 種 (cite-disabled / shuffled-memory / no-individual-layer ablation) に、Social-ToM 用 2 種を追加:

| ID | name | 目的 | 適用 scenario | acceptance |
|---|---|---|---|---|
| NC-1 | cite-disabled | counterfactual_challenge entry を cite_memory_id として宣言しても WorldModelUpdateHint adoption が merge されない | S-GAR-1 + §3.5 | golden test、reject 100% |
| NC-2 | shuffled-memory | 関係ない memory id を cite → reject | S-GAR-1 + §3.5 | golden test、reject 100% |
| NC-3 | no-individual-layer-ablation | individual_layer_enabled=false で同 protocol → SWM 自体存在しない | 全 scenario | individuation/Social-ToM metric は **layer 適用前 baseline** に近い値、value は protocol で band declare |
| NC-4 (新、Social-ToM) | shuffled-recipient | testimony の addressee を意図的に shuffle (A の発話が B でなく無関係な C に向けられる) → addressee identity を model しない agent は応答に変化なし | S-CHA-1 / S-AGO-1 | addressee shuffle 時の false_belief_recovery_rate が baseline と統計有意差なし → addressee-blind と判定、acceptance: 差分 ≤ baseline_noise_band |
| NC-5 (新、Social-ToM) | perspective-isolation | scenario から self/other 区別を除去 (全発話を 1 人称化) → info_asymmetry_handling_rate が degenerate になる | S-CHA-1 / S-AGO-1 | typed result `status='degenerate', reason='self-other distinction stripped'` を必ず返す |

### §3.7 Acceptance preregister (`thresholds.md` への追記項目)

v2 §2.5 `thresholds.md` のフォーマット (`frozen` / `calibrate_before_unblinding` / `defer`) に Social-ToM thresholds を追加:

| Threshold | State (M10-0 close 時) | Protocol |
|---|---|---|
| `false_belief_recovery_rate` band | calibrate_before_unblinding(P-FBR, split=[run0-2 scenario lib]→cal/[run3-4 scenario lib]→eval) | P-FBR: bootstrap 1000 resample、95% CI、effect direction = greater than noindividual baseline |
| `info_asymmetry_handling_rate` band | calibrate_before_unblinding(P-IAH, split=同上) | P-IAH: 同上、self/other split を AST/structure level で抽出 |
| `counterfactual_resistance_rate` band | calibrate_before_unblinding(P-CFR, split=同上、§3.5 perturbation 結果から) | P-CFR: baseline_noindividual との差分が effect direction = greater |
| `opposite_stance_adoption_rate` upper bound | **frozen(baseline_noindividual + 0.05, 2026-05-15, design rule)** | 禁止指標、超過時は M11-C で audit + protocol 見直し |
| `source_attribution_retention_rate` band | defer(M10-C, WorldModelUpdateHint 着手後 calibrate) | M10-C と相互 |
| NC-4 `addressee_shuffle_delta` | calibrate_before_unblinding(P-NC4, split=同上) | acceptance: 差分 ≤ baseline_noise_band |
| NC-5 `degenerate_must_fire` | frozen(true, 2026-05-15) | typed result `status='degenerate'` 100% |

### §3.8 既存 metric との直交性 (相関行列の Social-ToM 拡張)

v2 §2.4 A10 (metric 相関行列、|r| ≥ 0.85 で double-measurement warn) を以下に拡張:

- **同 layer 内**: §3.3 の 5 Social-ToM metric 間の相関を計測、|r| ≥ 0.85 で独立 channel 主張を撤回 (再設計トリガー)
- **layer 跨ぎ**: Individuation 11 metric × Social-ToM 5 metric の cross correlation を相関行列に追加
  - 警戒 pair (a priori):
    - `cognitive_habit_recall_rate` ↔ `counterfactual_resistance_rate` (両方とも habit retention 系) → 期待 |r| 中、|r| ≥ 0.85 なら警戒
    - `action_adherence_rate` ↔ `info_asymmetry_handling_rate` (両方とも意思決定一貫性系) → 期待 |r| 中-低
    - `belief_variance` ↔ `false_belief_recovery_rate` (両方とも belief 操作系) → 期待 |r| 中、独立 channel として残す根拠は input source の違い (自己 belief vs 他者 belief)

### §3.9 Emotional / cognitive alignment (HEART / MentalAlign) の M10-0 取り扱い

idea_judgement_2.md は HEART / MentalAlign を「中-高」評価、ただし **臨床主張不可、Tier C/D rubric (manual sparse review)** に限定としている。

**判断**: M10-0 範囲外 (Layer 4、§3.1 で defer 宣言済)。理由:
- quantitative pipeline (Layer 1-3) と分離が安全
- Tier C/D rubric は manual review LOC が大きく、scope が膨らむ
- 臨床用語の安易使用は ERRE 研究プラットフォームの説明責任を弱める
- 個体化 + Social-ToM の robust 設計が固まる前に emotional layer を加えると、metric 間の confound が増える

**defer 先**: M11+ task `m11-emotional-alignment-rubric` として後送り (本 task では scaffold もしない、idea_judgement_2.md §1 を参照する linkback のみ)。

### §3.10 Out-of-scope (明示)

M10-0 評価体制で扱わないもの:

- Multi-agent runtime execution (Social-ToM scenario は M11-C で実走、M10-0 では protocol + schema + lib のみ)
- Production scale evaluation (M10-0 は 1-2 agent × 5-7 scenario × 3 negative control 程度)
- 臨床主張 (HEART / MentalAlign 系の clinical use はしない)
- Vendi kernel sensitivity test 実走 (別 task)
- MeCab ja-tokenizer 移行 (別 task)
- Japanese IPIP-NEO vendoring (別 task)
- Weight / activation 解析 production (M12+)
- RL / preference tuning (M12+)
- `WorldModelUpdateHint` LLMPlan 拡張 (M10-C)
- `PhilosopherBase` / `IndividualProfile` schema 実装 (M10-A)
- prompt 注入 (Held world-model entries section) (M10-B)
- `NarrativeArc` 蒸留 (M11-A)
- DevelopmentState transition machinery (M11-B)

---

## §4. 配置決定 (§3 設計サイズから自然に確定)

§3 で Social-ToM eval が ~10 sub-section、新 DuckDB table、5 metric、7 scenario、2 新規 negative control、5 thresholds preregister と展開された結果、当初の「WP11 ~150 行 doc」は実態と乖離。配置は以下に再設定:

| ID | 対象 | 配置 | 根拠 |
|---|---|---|---|
| B-1 | source_navigator (idea_judgement.md) | **別 sub-task `m10-0-source-navigator-mvp`** (parallel) | scope 隔離、runtime 非接続、M10-0 main の blocker 化を避ける |
| **B-2 (revised)** | **Social-ToM eval (§3)** | **独立 sub-task `m10-0-social-tom-eval`** (M10-0 individuation main と parallel、共通 schema namespace `metrics.*`) | §3 設計サイズが scaffold ~700-900 production LOC + scenario lib + protocol doc + test (~25 unit + 3 integration) で WP11 doc 1 件に収まらない、独立 PR で出すべき |
| B-3 | PEFT ablation registry (idea_judgement_2.md §4) | M12+ task `m12-peft-ablation-qdora` の前提 gate、本 synthesis では linkback のみ | M12+ task scaffold 時に initialize で足りる |
| **B-4 (新)** | Emotional / cognitive alignment (HEART / MentalAlign) | **M11+ defer** (`m11-emotional-alignment-rubric`、本 synthesis では scaffold せず linkback のみ) | §3.9 根拠、臨床主張回避 + scope 隔離 |

### M10-0 sub-task の最終構成 (post-synthesis)

```
M10-0 (parallel sub-tasks):
  ├─ m10-0-individuation-metrics       (v2 draft WP1-WP10 を踏襲、Layer 1)
  ├─ m10-0-social-tom-eval             (§3 を踏襲、Layer 2 + Layer 3 拡張)
  └─ m10-0-source-navigator-mvp        (idea_judgement.md MVP、runtime 非接続)

M10-0 close 条件 = 3 sub-task すべて green に到達。
ただし依存:
  - Social-ToM の §3.5 perturbation protocol v3 は individuation の §2.6 を継承するため、
    individuation main の §2.6 protocol freeze が先行する (順序依存)
  - source_navigator は他 2 sub-task と完全独立
```

---

## §5. v2 draft Addendum patch ドラフト (貼り付け可能)

`.steering/20260508-cognition-deepen-7point-proposal/m10-0-concrete-design-draft.md` への追記文案。次 task scaffold 時に本体に commit。

### §2.7 (out-of-scope) への追記

```markdown
- **Social-ToM eval harness** → 独立 sub-task `m10-0-social-tom-eval`
  (本 v2 draft の §2.6 counterfactual_challenge を継承、Layer 2+3、design 詳細は
  `.steering/20260515-pre-m10-design-synthesis/design.md` §3)
- **source_navigator (Corpus2Skill 型)** → 独立 sub-task `m10-0-source-navigator-mvp`
  (Kant only、depth 2、runtime 非接続、design 詳細は同 §6.2)
- **PEFT ablation registry yaml format** → M12+ task `m12-peft-ablation-qdora` で
  initialize、本 v2 draft は M10-0 範囲外 (idea_judgement_2.md §4 を参照)
- **Emotional / cognitive alignment (HEART / MentalAlign)** → M11+ task
  `m11-emotional-alignment-rubric` defer、臨床主張回避
  (idea_judgement_2.md §1 を参照、設計判断は同 §3.9)
```

### §3 (WP 分割) への追記 (LOC 想定 表 row として)

```markdown
| WP11 | (削除、Social-ToM は独立 sub-task `m10-0-social-tom-eval` に格上げ) | — | — |
```

(註: 当初 WP11 は本 synthesis 初版で「Social-ToM min spec doc ~150 行」だったが、§3 で concrete 化した結果、独立 sub-task に格上げされ、v2 draft 本体 WP 表には載らない。)

### §6 (References) への追記

```markdown
- `.steering/20260515-pre-m10-design-synthesis/design.md` §3 (Social-ToM eval concrete design)
- `.steering/20260515-pre-m10-design-synthesis/decisions.md` ADR-PM-1〜PM-5
- `.steering/20260515-pre-m10-design-synthesis/idea-judgement-source-navigator.md`
- `.steering/20260515-pre-m10-design-synthesis/idea-judgement-pdf-survey.md`
```

---

## §6. 次 task scaffold 草稿 (inline、次セッションで `.steering/_template/` から起こす際の素)

### §6.1 `m10-0-individuation-metrics` requirement.md 草稿

```markdown
# M10-0 Individuation Metrics

## 背景
v2 draft `m10-0-concrete-design-draft.md` (PR #159、Codex 12th HIGH 5 反映済) の WP1-WP10 を
そのまま踏襲する main sub-task。Social-ToM eval は別 sub-task `m10-0-social-tom-eval` に分離
(本 task の §2.6 counterfactual_challenge protocol は両者の共有基盤)。

## ゴール
- v2 draft WP1-WP10 の実装 (LOC 想定 ~2950)
- 既存 1356+ tests + 新 25+ unit + 3 integration 全 green
- `--compute-individuation` flag off で既存 CLI byte-for-byte 不変
- DB11 sentinel poison row test green

## スコープ
含む: WP1 (eval/individuation 関数群 + MetricResult typed) / WP2 (DuckDB schema) /
      WP3 (CLI flag + sidecar JSON) / WP5 (AnalysisView loader) / WP6 (cache benchmark) /
      WP7 (prompt ordering contract) / WP8 (tests) / WP9 (thresholds.md) /
      WP10 (counterfactual_challenge protocol、Social-ToM eval と共有)
含まない: Social-ToM scenario lib / metric (m10-0-social-tom-eval) / source_navigator
         (m10-0-source-navigator-mvp) / PhilosopherBase 実装 (M10-A) / etc.

## 受け入れ条件
v2 draft §2.4 A1-A11 全 pass。
```

### §6.2 `m10-0-social-tom-eval` requirement.md 草稿

```markdown
# M10-0 Social-ToM Eval Harness

## 背景
`.steering/20260515-pre-m10-design-synthesis/design.md` §3 で concrete 化された Social-ToM
評価体制を実装する。Layer 2 (Social-ToM) + Layer 3 (counterfactual perturbation 拡張) を
担当、Layer 1 (Individuation) の `m10-0-individuation-metrics` と並列。

## ゴール
- `metrics.social_tom` DuckDB table 作成 (synthesis §3.4)
- 7 scenario lib (S-CHA-1/1c/2 + S-AGO-1/2 + S-GAR-1/2、synthesis §3.2)
- 5 Social-ToM metric 実装 (synthesis §3.3、MetricResult typed)
- counterfactual perturbation protocol v3 (synthesis §3.5、§2.6 v2 を拡張、共有実装は
  m10-0-individuation-metrics 側に置き、本 task は scenario integration のみ)
- 2 新規 negative control (NC-4 shuffled-recipient / NC-5 perspective-isolation)
- `thresholds.md` への Social-ToM threshold 5 件追加 (synthesis §3.7)
- 既存 metric との直交性検証 (synthesis §3.8、相関行列拡張)
- 25+ unit tests + 3 integration tests (scenario lib + protocol v3 + negative control)

## スコープ
含む: scenario lib (`src/erre_sandbox/eval/social_tom/scenarios/*.py`) /
      metric 関数群 (`src/erre_sandbox/eval/social_tom/metrics/*.py`) /
      schema 追加 (`src/erre_sandbox/evidence/eval_store.py` extension) /
      sidecar JSON output / negative control 実装 / thresholds 追記 / tests
含まない: multi-agent runtime 実走 (M11-C) / Emotional alignment (M11+) /
         source_navigator (m10-0-source-navigator-mvp)

## 受け入れ条件
- synthesis §3.3 の 5 metric が `MetricResult(status, value, reason)` で valid/degenerate/
  unsupported を返す (1 つの scenario で min 1 metric が valid)
- DB11 sentinel poison row test: `metrics.social_tom` も training-view loader が reject
- NC-4 shuffled-recipient で false_belief_recovery_rate が baseline と統計有意差なし →
  addressee-blind 判定
- NC-5 perspective-isolation で info_asymmetry_handling_rate が `degenerate` 100%
- `--compute-social-tom` flag off で既存 CLI byte-for-byte 不変
- `m10-0-individuation-metrics` と protocol v3 共有実装が conflict しない (順序依存:
  individuation main 完了 → 本 task 着手、または並列 PR でも protocol v3 implementation は
  individuation 側に置く合意)

## 依存
- `m10-0-individuation-metrics` (counterfactual_challenge protocol v3 共有基盤)
- v2 draft §2.6 protocol (継承)
```

### §6.3 `m10-0-source-navigator-mvp` requirement.md 草稿

```markdown
# M10-0 Source Navigator MVP

## 背景
`idea_judgement.md` (Corpus2Skill 型 source navigator、ローカル再実装) の MVP を実装。
runtime 非接続、static corpus navigation として持つ。M10-C `WorldModelUpdateHint.cited_memory_ids`
の前段として、史料 / cognitive_habit / provenance を階層 index 化する。

## ゴール
- Kant only (`personas/kant.yaml` + `evidence/reference_corpus/raw/` Kant 関連)
- depth 2 (persona → habit → source cluster → document_ids)
- 出力: markdown `INDEX.md` + JSON `documents.json` + yaml `provenance.yaml` per persona
- runtime 非接続 (`src/erre_sandbox/evidence/source_navigator/` 新設、compile script)

## スコープ
含む: compile pipeline (clustering + local summarization) / document_store /
      provenance schema / Kant の 6 cognitive_habit 全件の source 追跡
含まない: WorldModel citation navigator (M10-C 統合は別 task) /
         Evaluation corpus QA harness (defer) /
         Developer navigation skill (defer) /
         クラウド API 使用 / .claude/skills へ自動書き込み

## 受け入れ条件 (idea_judgement.md MVP acceptance 踏襲)
- `kant` の全 `cognitive_habits` (6 件) について `source / flag / trigger_zone /
  document_ids / provenance` を引ける
- provenance missing は loud failure
- generated summary だけを根拠にした assertion が schema 上不可能 (citation discipline)
- default install に重い ML dependency 追加なし
- `uv run pytest tests/test_evidence` が既存 contamination contract を壊さない

## 依存
- なし (個体化 metrics / Social-ToM とは並列可)
```

---

## §7. `idea_judgement.md` / `idea_judgement_2.md` 最終配置案

現在 repo root に untracked で 2 ファイル置かれている。本 synthesis 完了後、以下に move:

```
mv idea_judgement.md   .steering/20260515-pre-m10-design-synthesis/idea-judgement-source-navigator.md
mv idea_judgement_2.md .steering/20260515-pre-m10-design-synthesis/idea-judgement-pdf-survey.md
```

理由:
- snake_case → kebab-case (.steering 内の他ファイル命名に揃える)
- 内容を反映した名前 (`_2` を `pdf-survey` に変更)
- `.steering/` 配下なら git 管理に取り込まれる (root untracked から外れる)

commit 時 staging:
- `.steering/20260515-pre-m10-design-synthesis/requirement.md` (new)
- `.steering/20260515-pre-m10-design-synthesis/design.md` (new、本ファイル)
- `.steering/20260515-pre-m10-design-synthesis/decisions.md` (new)
- `.steering/20260515-pre-m10-design-synthesis/tasklist.md` (new)
- `.steering/20260515-pre-m10-design-synthesis/idea-judgement-source-navigator.md` (renamed)
- `.steering/20260515-pre-m10-design-synthesis/idea-judgement-pdf-survey.md` (renamed)
- `idea_judgement.md` (deleted from root)
- `idea_judgement_2.md` (deleted from root)

Conventional Commits: `docs(steering): pre-M10 design synthesis (Social-ToM eval concrete)`

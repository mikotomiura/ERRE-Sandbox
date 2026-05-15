# 設計 (HISTORICAL / SUPERSEDED) — pre-M10 design synthesis (REIMAGINE: 現案を意図的に破棄、別視点で再起草)

> ⚠️ **HISTORICAL REFERENCE ONLY — DEPRECATED** (Codex MEDIUM-5 反映、2026-05-15)
>
> 本書は `design-original.md` を意図的に破棄してゼロから別視点で再起草した alternative 案 (process-trace + power-first、Layer 2 = Cite-Belief Discipline、3 metric × scenario なし × 3 NC、Social-ToM 完全 M11-C 移送)。
> ADR-PM-6 で **SUPERSEDED** (Hybrid-A revised が両案の hybrid として確定)。
> **Implementation reference**: `design-final.md` (Layer 2 = reimagine 由来、4 scenario spec doc = original から救出)
> **Original explored**: `design-original.md` (capability-oriented scenario-lib)
>
> 本書の内容を **そのまま** 実装に踏襲しないこと (Hybrid 採用で部分採用)。M10-0 sub-task scaffold は `design-final.md` を起点とする。
> 本書は `/reimagine` 規約に従った design discipline 履歴 + Codex review の independent stress-test 素材として保持される。

---

> **REIMAGINE mandate** (CLAUDE.md 規約「Plan 内 /reimagine 必須」「単発 Plan エージェント 1 発で設計を確定しない」):
> `design-original.md` (506 行、scenario × metric × negative control の格子 capability-oriented eval) を **意図的に破棄** し、根本から別視点で M10 評価体制を再起草する。`design-final.md` で両案を比較し採用案 (hybrid 含) を確定する。
>
> **意図的破棄の対象**: §3.2 7 scenario lib (S-CHA / S-AGO / S-GAR の格子)、§3.3 5 metric capability roster、§3.4 `metrics.social_tom` 専用 table、§3.6 NC-4/NC-5 scenario-specific negative control、§3.5 protocol v3 の v2 直系継承。

---

## §0. 何を「捨てる」か / 何を「捨てない」か

### 捨てる (assumptions の根を断つ)

- **scenario lib という発想**: design-original は 7 scenario を library 化したが、scenario は **設計者の bias** を強く含む。「他者が誤った rumor を持つ」「object_event を片方だけが見た」等のシナリオ選定そのものが、Social-ToM signal の出やすい状況を選んでしまう → bias 検出が困難
- **専用 table `metrics.social_tom`**: namespace の DB11 防御を信用しているが、本当に **新 table が必要か** を再検討。`metrics.individuation` 拡張で済むなら schema migration を 1 件減らせる
- **5 metric を a priori に固定**: capability-oriented (false_belief / info_asymmetry / counterfactual_resistance...) は人間が思いついた capability の roster で、agent が実際に発露する Social-ToM signal がそこに mapping できる保証がない
- **Multi-agent scenario を前提**: M10-0 段階で multi-agent runtime は M11-C 待ち → scenario 設計を multi-agent ありきで作ると M10-0 close 時点で何も動かない (protocol freeze だけが成果になる)
- **150 行 doc から 700-900 LOC への置換** という設計サイズ前提: 「robust = 大きい」とは限らない。むしろ **少数 channel + 高 statistical power** の方が robust なケースが多い (生物学・心理学 eval の標準)

### 捨てない (root invariants)

- v2 draft `metrics.*` namespace + DB11 sentinel poison row test (HIGH-2 由来、防御層は維持)
- v2 draft §2.6 `counterfactual_challenge` 隔離 + SWM write 禁止 + cite-disabled / shuffled-memory / no-individual-layer 3 種 negative control (Layer 3 は捨てない、Social-ToM の前提)
- typed `MetricResult(status, value, reason)` (HIGH-4 由来)
- `calibrate_before_unblinding` state preregister
- User 指示「ToM などを含めた評価体制を具体的に強固に設計してから決めてください」(design-first 原則、ADR-PM-2 revised の根拠)

---

## §1. 別視点: **Process-trace + Statistical-power-first** eval

design-original の **capability-oriented + scenario-lib** を捨てた代替視点として、次の 3 軸で再構築する:

### §1.1 Process-trace eval (D 軸): "agent が何を cite し、何を retrieve し、どう belief revision したか" を直接観測

agent の dialog tick 単位で:
1. **retrieved_memories**: どの memory id を retrieve したか
2. **cited_memory_ids**: 発話 / 内部 reasoning で何を cite として宣言したか
3. **belief_promoted**: SemanticMemoryRecord の belief_kind が `provisional → promoted` に上がった瞬間
4. **WorldModelUpdateHint adoption** (M10-C territory): SubjectiveWorldModel 更新が起きた瞬間
5. **source attribution split**: cited_memory_id の source が「自己観測」「他者 testimony」「inferred」のどれか

これは **scenario を使わない** — 既存 M9-eval Phase 2 の 30 cell (Phase B+C) で取った natural rollout の `raw_dialog.dialog` に対して post-hoc に抽出可能。

利点:
- scenario design bias の混入を回避
- M9-eval 既存 capture (30 cell × 504-tick window) を **追加 capture なしで再利用**
- M10-C `cited_memory_ids` 設計と直接 align (stub schema を M10-0 で立てると M10-C 着手が低 churn)

欠点:
- Social-ToM signal が natural rollout で出ているか不確定 (= 出ていないなら null result が確定する)
- multi-agent dialog の場面が M9-eval natural rollout に含まれているか要確認 (Phase B は stimulus 1 agent、Phase C は natural 1 agent → multi-agent は M11-C 待ちのまま)

### §1.2 Statistical-power-first design (E 軸): 「N を増やす」を最優先

scenario diversity (7 scenario × 1-2 trial) より、**fewer channels × higher N**:

- 計測対象を **3 process-trace channel** に絞る:
  - `provisional_to_promoted_rate` (belief 採用率、`SemanticMemoryRecord.belief_kind` transition)
  - `cited_memory_id_source_distribution` (cite した memory id の source split、`self_observation / other_testimony / inferred` の 3 分類比率)
  - `counterfactual_challenge_rejection_rate` (v2 §2.6 perturbation 下で `cited_memory_ids` に opposite-stance entry が **含まれない** rate、これは Social-ToM の前段 = "他者から押し付けられた情報を自分の belief source として採用しない discipline")
- 各 channel に **N ≥ 200 tick samples** を保証 (M9-eval Phase B+C 30 cell × 504 tick = 15,120 tick の base、十分)
- bootstrap CI 95% で band declare、`calibrate_before_unblinding(P-XXX, split=[run0-2]→cal/[run3-4]→eval)` で circular gate 防止 (v2 §2.5 流用)

利点:
- 3 channel × N 大で statistical power 確保
- 既存 M9-eval Phase B+C capture を再利用 → 追加 G-GEAR run なし
- scenario lib maintenance ゼロ

欠点:
- "他者誤信念の handling" のような **Social-ToM らしい signal** は直接測れない (多人数 dialog が M11-C 待ち)
- M10-0 close 時点では「Social-ToM の **前駆 disposition** を測る」までで、「Social-ToM 能力 itself」は M11-C 以降

### §1.3 ToM の M11-C deferral と M10-0 の役割再定義

これは **設計上の本質的な逆転**:

design-original は M10-0 で Social-ToM eval harness を立てた (= multi-agent scenario protocol + metric + schema)。
reimagine は M10-0 で **ToM の前駆 disposition (cited_memory_id source discipline / belief promotion discipline / counterfactual rejection)** を測り、**ToM 本体 (false_belief / info_asymmetry handling) は M11-C** に明示的に defer する。

理由:
- M10-0 段階で multi-agent runtime が動かない → 7 scenario の **protocol freeze 以上の進捗が物理的に取れない** (design-original §6.2 でも acceptance は "protocol 定義、実走 M11-C" となっている → 結局 doc 主体になる)
- ToM 本体を測るには multi-agent rollout が必須 → M11-C の `m11-c-multi-individual-same-base-validation` task の中で integrate するのが自然
- M10-0 では「individual の cite/belief discipline が、後の Social-ToM の前提として保たれているか」を測れば十分 (それ自体が独立した evaluation question)

---

## §2. 再構築した M10-0 評価体制 (Reimagine 版)

### §2.1 評価体制の上位構造 (3 layer に縮減)

```
Layer 1: Individuation (個体化)
  - design-original §3.1 と同じ、v2 draft §2.2 matrix の 11 metric (Burrows / Vendi / centroid / belief_variance / SWM Jaccard / habit_recall / action_adherence / zone_behavior + recovery)
  - 既存 M9-eval Phase B+C 30 cell の raw_dialog.dialog を AnalysisView loader で読み込む
  - schema: `metrics.individuation` (v2 §2.3)

Layer 2: Cite-Belief Discipline (ToM 前駆 disposition)  ← reimagine の中核
  - 3 process-trace channel (§1.2)
  - 既存 M9-eval Phase B+C capture で計測可、追加 G-GEAR run 不要
  - schema: `metrics.individuation` に **3 metric を additive 追加** (新 table 不要)
  - 註: schema の `metric_name` フィールドが TEXT NOT NULL なので、新 metric 名を流すだけで OK (DDL 変更ゼロ)

Layer 3: Counterfactual perturbation (反事実摂動)
  - v2 §2.6 protocol を **そのまま** 採用 (拡張なし、scenario integration は M11-C 移送)
  - 3 種 negative control (cite-disabled / shuffled-memory / no-individual-layer ablation) で十分
  - acceptance: Layer 2 の `counterfactual_challenge_rejection_rate` が baseline_noindividual と統計有意差あり (effect direction = greater)

(deferred)
Layer 4: Social-ToM proper (multi-agent ToM 本体)
  → M11-C task `m11-c-multi-individual-same-base-validation` に統合
  → scenario lib は M11-C 着手時に design (Codex review + /reimagine 経由)
  → M10-0 ではこの Layer の name reservation のみ (`m11-c-social-tom-proper` linkback)

(deferred)
Layer 5: Emotional / cognitive alignment
  → M11+ task `m11-emotional-alignment-rubric` (ADR-PM-5、reimagine 後も維持)
```

### §2.2 Layer 2 channel 詳細 (Cite-Belief Discipline、3 channel)

| Metric | Input channel | What | Aggregation | Phase | Notes |
|---|---|---|---|---|---|
| `provisional_to_promoted_rate` | `SemanticMemoryRecord.belief_kind` transition log per tick | provisional → promoted の rate | per-individual + per-100-tick window | M10-0 active 計測 | belief 採用の慎重さを測る |
| `cited_memory_id_source_distribution` | `LLMPlan.cited_memory_ids` の source 分類 (self_observation / other_testimony / inferred) | 3 source の比率分布 | per-individual + per-100-tick window | M10-0 active 計測 | source attribution の保持を測る (M10-C の前段) |
| `counterfactual_challenge_rejection_rate` | v2 §2.6 perturbation 下の `cited_memory_ids` 集合 | counterfactual_challenge entry が cited_memory_ids に含まれない rate | per-individual × perturbation tick window | M10-0 active 計測 | cite-disabled negative control と相互参照 |

#### 独立性論証

- `provisional_to_promoted_rate` vs `cited_memory_id_source_distribution`: belief substrate vs citation substrate (異 substrate)
- `provisional_to_promoted_rate` vs `counterfactual_challenge_rejection_rate`: belief 採用 (positive action) vs counterfactual 拒否 (negative action) → opposite-direction、独立
- `cited_memory_id_source_distribution` vs `counterfactual_challenge_rejection_rate`: cite した memory の **source** vs cite に **入れなかった** memory → 計測点が disjoint

### §2.3 Schema (新 table 不要、`metrics.individuation` 拡張)

design-original §3.4 で立てた `metrics.social_tom` 専用 table を **廃止**。理由:
- `metrics.individuation` は既に `metric_name TEXT NOT NULL` + `channel TEXT NOT NULL` を持つ (v2 §2.3)
- Layer 2 の 3 metric を `metric_name='cite_belief_discipline.provisional_to_promoted_rate'` 等の **dotted namespace** で同 table に流すだけで OK
- schema migration は **DDL 変更ゼロ** (rows insert のみ)
- DB11 sentinel poison row test は `metrics.individuation` で既に testing 範囲、Layer 2 の sentinel row も同 test で自動 cover

#### サイドカー JSON

- `*.duckdb.individuation.json` (v2 で既に sidecar 既存) の中に Layer 2 summary を **同居** (新 sidecar file を作らない)
- training manifest input にしない (既存 DB11 sentinel で cover)

### §2.4 Counterfactual perturbation protocol (v2 §2.6 そのまま採用、v3 拡張なし)

design-original §3.5 で立てた protocol v3 (Social-ToM scenario 統合) を **廃止**。v2 §2.6 をそのまま採用:

```
prep:
  1. base individual を T_base = 200 tick (preferred_zone) → baseline:
     - Burrows / cognitive_habit_recall / action_adherence (Layer 1)
     - provisional_to_promoted_rate / cited_memory_id_source_distribution (Layer 2)

perturbation:
  2. counterfactual_challenge channel に opposite-stance content N=5 を injection
  3. T_perturb = 50 tick → perturbed_floor 計測

recovery:
  4. T_recover = 200 tick → post recovery 計測

metric:
  Layer 1: recovery_rate (Burrows / habit / decision、v2 既存)
  Layer 2: counterfactual_challenge_rejection_rate
         = 1 - (perturbation tick で cited_memory_ids に counterfactual entry を含む tick の比率)
```

### §2.5 Negative control (v2 既存 3 種を踏襲、Social-ToM 用 NC-4/NC-5 廃止)

design-original §3.6 で立てた NC-4 shuffled-recipient / NC-5 perspective-isolation を **廃止**。理由:
- scenario lib が消えたため shuffled-recipient (addressee 操作) の対象がない
- perspective-isolation も同様 (1 人称化する scenario がない)
- 既存 3 種 (NC-1 cite-disabled / NC-2 shuffled-memory / NC-3 no-individual-layer-ablation) で Layer 2 の 3 metric を十分 cover

Layer 2 metric × 3 negative control の acceptance:

| Metric | NC-1 cite-disabled 期待 | NC-2 shuffled-memory 期待 | NC-3 no-individual-layer 期待 |
|---|---|---|---|
| provisional_to_promoted_rate | 不変 (negative control が belief substrate に作用しない) | 不変 | rate ≈ 0 (individual layer ない → promote しない) |
| cited_memory_id_source_distribution | inferred 比率増、other_testimony 比率低下 | 全 source random distribution | self_observation 100% (other 不在) |
| counterfactual_challenge_rejection_rate | rejection 100% (cite-disabled なので絶対 reject) | rejection 100% (shuffled なので絶対 reject) | undefined (Layer 自体ない) |

### §2.6 Threshold preregister (Layer 2 専用追記、`thresholds.md`)

| Threshold | State | Protocol |
|---|---|---|
| `provisional_to_promoted_rate` band | calibrate_before_unblinding(P-PPR, split=[Phase B+C run0-2]→cal/[run3-4]→eval) | bootstrap 1000 resample、95% CI、effect direction = none (両方向ありうる、distribution として宣言) |
| `cited_memory_id_source_distribution` divergence (Jensen-Shannon vs baseline) | calibrate_before_unblinding(P-CMSD, split=同上) | per-source bootstrap、JS divergence band |
| `counterfactual_challenge_rejection_rate` lower bound | calibrate_before_unblinding(P-CCRR, split=同上、§2.4 perturbation 下) | effect direction = greater than baseline_noindividual |

design-original §3.7 の 5 threshold (false_belief / info_asymmetry / counterfactual_resistance / opposite_stance / source_attribution) を **廃止** し、上記 3 threshold に置換。

### §2.7 Acceptance (Reimagine 版)

| ID | criterion | rationale |
|---|---|---|
| A1 (v2 既存) | Layer 1 既存 11 metric が typed `MetricResult` を返す | v2 既存 |
| A2 (新、Layer 2) | Layer 2 3 metric が `metrics.individuation` の `metric_name='cite_belief_discipline.*'` で row を返す | additive schema 検証 |
| A3 (新、Layer 2) | M9-eval Phase B+C 30 cell × 504 tick から Layer 2 3 metric が抽出可、`status='valid'` を返す比率 ≥ 90% | 既存 capture 再利用 |
| A4 (新、Layer 2 × NC) | §2.5 表 9 cell の期待値が hold (bootstrap CI 95% band 内) | negative control 健全性 |
| A5 (v2 既存) | DB11 sentinel poison row test が Layer 2 row も reject | DB11 拡張不要、自動 cover |
| A6 (新、Layer 2) | Layer 2 metric × Layer 1 metric の相関行列で |r| ≥ 0.85 ペア検出時 warn | v2 A10 拡張 |
| A7 (v2 既存) | schema 変更ゼロ (`metrics.individuation` への row insert のみ) | v2 既存に加えて Layer 2 も DDL 変更なし |
| A8 (v2 既存) | `--compute-individuation` flag off で既存 CLI byte-for-byte 不変 | v2 既存 |
| A9 (新、Layer 2) | Layer 2 protocol が M11-C で extend されることが thresholds.md に declare されている | M11-C への defer 明示 |

design-original §3 の A1-A11 + NC-4/NC-5 を本リストに置換。

---

## §3. WP 分割 (Reimagine 版)

| WP | 内容 | LOC 想定 | depends |
|---|---|---|---|
| WP1 (v2 既存、+Layer 2) | `src/erre_sandbox/eval/individuation/` 関数群 + MetricResult typed + provenance fields + **3 新 Layer 2 metric 関数** | ~850 (v2 ~700 + Layer 2 ~150) | evidence/tier_b |
| WP2 (v2 既存、変更なし) | DuckDB schema migration (`metrics.individuation` table、Layer 2 は同 table、DDL 変更なし) | ~150 | WP1 |
| WP3 (v2 既存、+Layer 2 flag) | M9-eval CLI `--compute-individuation` flag + sidecar JSON + DB11 sentinel poison row test (Layer 2 row も含む) | ~280 (v2 ~250 + Layer 2 ~30) | WP1, WP2 |
| WP5 (v2 既存、変更なし) | `AnalysisView` loader (raw_dialog.dialog window 抽出、Layer 2 も同じ loader) | ~200 | (none) |
| WP6 (v2 既存、変更なし) | Cache benchmark framework | ~250 | (none) |
| WP7 (v2 既存、変更なし) | Prompt ordering contract spec | ~80 lines doc | (none) |
| WP8 (v2 既存、+Layer 2 tests) | Unit tests (≥ 35、Layer 1 25 + Layer 2 10) + integration test + correlation matrix | ~850 | WP1-3, WP5 |
| WP9 (v2 既存、+Layer 2 threshold) | `thresholds.md` 起草 (Layer 1 8 threshold + Layer 2 3 threshold) | ~180 lines doc | (none) |
| WP10 (v2 既存、protocol v2 そのまま) | Recovery protocol spec (v2 §2.6 そのまま、Social-ToM 拡張なし) | ~120 lines doc | (none) |
| ~~WP11 (削除)~~ | Social-ToM eval harness は M11-C へ defer | — | — |
| ~~WP12+ (削除)~~ | scenario lib / NC-4 / NC-5 等は全て M11-C 移送 | — | — |

Total LOC 想定: **~2960 production + ~850 test = ~3810** (design-original の Social-ToM 専用 ~700-900 を Layer 2 拡張 ~180 production + ~100 test に圧縮)

依存最小化: design-original と同じく WP5 (loader) 先行、WP1-3 並行。

---

## §4. Reimagine 版の利点 / 欠点

### 利点

1. **既存 M9-eval Phase B+C capture を追加 run なしで再利用** (G-GEAR overnight 不要、Mac 単独で完結)
2. **schema migration を 1 件減らす** (`metrics.social_tom` 専用 table 廃止 → `metrics.individuation` 拡張で完結)
3. **scenario design bias を回避** (scenario lib そのものを廃止)
4. **M10-0 close 時に動く evidence が出る** (design-original は protocol freeze 中心 → 実走 M11-C で M10-0 は doc 主体)
5. **M11-C task scope が clean** (Social-ToM 本体は M11-C で multi-agent rollout 着手と同時に design、scope creep 防止)
6. **maintenance cost を縮小** (scenario lib + scenario protocol version 管理が消える)
7. **Codex review への explanation が短い** (Layer が 4 → 3、metric が 5 + Layer1 11 → 3 + Layer1 11)

### 欠点

1. **"Social-ToM" の literal な evaluation が M10-0 で動かない** (M11-C 待ち) — User の「ToM などを含めた評価体制」の "ToM" 部分が M10-0 で active 化しない
2. **multi-agent runtime が無い段階で何が測れるかが Layer 2 「前駆 disposition」に限定** → ToM の核 (theory-of-other-mind) は M11-C
3. **User の design-first 指示への応答として弱く見える可能性** (synthesis 草稿 → reimagine で scope 縮小に見える)
4. **Layer 2 channel が embedding 依存ではない** (text-structural feature) → 多言語性に強いが、subtle な ToM signal は逃す可能性
5. **WP11 を捨てるため、design-original Codex review の HIGH 5 等の Codex 反映済 finding が一部 redundant 化** (具体的には design-original §3.5 protocol v3 拡張部分)

---

## §5. design-original vs design-reimagine の比較表 (design-final.md §X で決定)

| 評価軸 | design-original (capability-oriented scenario-lib) | design-reimagine (process-trace + power-first) |
|---|---|---|
| Layer 数 | 4 (Indiv / Social-ToM / Counterfactual / Emotional) | 3 (Indiv / Cite-Belief Discipline / Counterfactual) |
| 新 metric 数 (Layer 2 相当) | 5 + 2 NC = 7 | 3 |
| Schema 追加 | 新 table `metrics.social_tom` + DDL | 既存 `metrics.individuation` への row 追加のみ (DDL 変更ゼロ) |
| Scenario lib | 7 scenario × multi-variant | なし (process-trace のみ) |
| Negative control | 5 種 (NC-1〜NC-5) | 3 種 (v2 既存、NC-4/NC-5 廃止) |
| 追加 G-GEAR run | あり (Social-ToM scenario 走行) | なし (Phase B+C 既存 capture 再利用) |
| M10-0 close 時の active 計測 | protocol freeze 中心 (実走は M11-C) | 3 Layer 2 metric が active 計測 (既存 capture から) |
| LOC 想定 | ~3750 + Social-ToM sub-task ~700-900 (= ~4500-4650) | ~3810 (single sub-task に集約) |
| Sub-task 数 | 3 (Indiv / Social-ToM eval / Source nav) | 2 (Indiv + Source nav、Social-ToM eval は M11-C へ移送) |
| M11-C 接続 | Social-ToM eval を M11-C で実走するだけ | M11-C で Layer 4 (Social-ToM proper) を新規 design (scope clean) |
| Codex review 圧縮率 | 投げる context 大 (scenario lib + 5 metric + 5 NC + protocol v3) | 投げる context 中 (3 metric + 3 NC + protocol v2 そのまま) |
| User 指示「ToM などを含めた評価体制を具体的に強固に設計」への応答 | 直接的: ToM scenario を作る | 間接的: ToM の前駆を測る + ToM 本体は M11-C に明示 defer |
| design bias | 高 (scenario 選定で signal の出やすい状況を選ぶ) | 低 (natural rollout から post-hoc 抽出) |
| Statistical power | 中 (scenario 7 × trial 数限定) | 高 (3 channel × N=15,120 tick from Phase B+C) |

---

## §6. Hybrid 採用候補 (design-final.md で決める素材)

両案の利点を取る hybrid 候補:

### Hybrid-A: Reimagine ベース + ToM scenario を M10-0 minimum (4 scenario) で残す

- Reimagine の Layer 2 (3 process-trace metric) を採用 (中核)
- design-original の scenario lib を **7 → 4** に削減 (S-CHA-1 only / S-AGO-1 only / S-GAR-1 only / S-GAR-2 only)
- scenario は M10-0 で **spec doc のみ**、実走 M11-C は明示
- NC-4 shuffled-recipient は **scenario S-CHA-1 専用** に限定して残す (Layer 2 process-trace に対する scenario-bias の counter-check として活用)
- 新 table `metrics.social_tom` は廃止 (`metrics.individuation` に統合)

### Hybrid-B: design-original ベース + Layer 2 を追加

- design-original の Social-ToM eval harness はそのまま
- Reimagine の Layer 2 (3 process-trace metric) を **追加 channel** として実装
- M10-0 close で Layer 1 + Layer 2 (active) + Social-ToM (protocol + scenario lib + schema、実走 M11-C) を出す
- LOC 想定が最大 (~5000+)、scope が最も広い

### Hybrid-C: Reimagine 全面採用、ToM scenario は M11-C で新規 design

- Reimagine をそのまま採用
- ToM scenario / Social-ToM eval harness は M11-C task `m11-c-social-tom-proper` を新規起票
- M10-0 sub-task が 2 (Indiv main + Source nav MVP) に削減
- M11-C への explicit handoff (Layer 4 name reservation + 設計指針)

---

## §7. 採用判断は design-final.md に書く (本書はあくまで「破棄して再生成した別視点案」)

`design-final.md` で:
- §A: 両案を § per § で対照
- §B: Hybrid-A / B / C のいずれを採用するか + 採用根拠
- §C: 採用案に Codex 13th review HIGH 反映を upsert する余地を残す

本書 (design-reimagine.md) はここで close。**design-original を捨てた状態の純粋な別視点** として保持する (Codex review でも両案を示すことで independent stress-test の効力が増す)。

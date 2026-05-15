# 設計 — pre-M10 design synthesis (FINAL: hybrid 採用、Codex 13th 反映済) **[SUPERSEDED by design.md repair pass 2026-05-15]**

> **Status**: HISTORICAL / SUPERSEDED — canonical implementation reference は `design.md` (同ディレクトリ、本 repair pass 2026-05-15 後の正本)。
> **Superseded by**: `design.md` (本 repair pass)
> **Reason for supersession**: 本書には以下の不整合が含まれていたため、`design.md` を canonical として新規起票 (内容は本書を起点に repair):
>   - M-L2-1 が `provisional → promoted` rate を前提にしていたが、現行 `SemanticMemoryRecord.belief_kind` の値域は `trust/clash/wary/curious/ambivalent` で provisional/promoted を含まない
>   - "Layer 2 3 metric が active 計測 / `status='valid'` ≥ 90%" の主張が schema/data の実状と乖離
>   - Phase B+C 30 cell × 504 tick base が unconditional 前提として書かれていたが、Mac 上で natural 15 DuckDB 本体が欠落 (sidecar `.capture.json` のみ)
>   - "DDL 変更ゼロ" 表現が誤読を誘発 (`metrics.individuation` table 自体は M10-0 main で新規 DDL 追加が必要、現行 `bootstrap_schema()` は `metrics.tier_{a,b,c}` のみ)
>   - 実装配置 `src/erre_sandbox/eval/individuation/` が現行 repo の evidence layer pattern (`evidence/tier_b/` 等) とズレ
>   - M10-0 final freeze 条件と G-GEAR QLoRA retrain v2 verdict の関係が未明示
>
> 本書は historical reference として保持 (合意プロセス trace のため)。新規 reader は `design.md` を読むこと。`design-original.md` / `design-reimagine.md` も historical reference のまま。
>
> ---
>
> **Date (original)**: 2026-05-15  **Base commit**: `fb651e7` (main)
>
> **本書の位置づけ (original)**: `design-original.md` (capability-oriented scenario-lib、SUPERSEDED) と `design-reimagine.md` (process-trace + power-first、SUPERSEDED) の **両案を並列審査** した上で、採用 hybrid を確定する。本書が M10-0 sub-task scaffold 起票の正式 reference。Codex 13th review (66,261 tokens、Verdict: ADOPT-WITH-CHANGES、HIGH 4 / MEDIUM 5 / LOW 3) を反映済。

---

## §0. **Claim boundary 警告 (Codex HIGH-4 反映)**

> **本設計の Layer 2 (Cite-Belief Discipline) は Social-ToM proper の sufficient statistic ではない。**
> **Layer 2 は process-trace prerequisite / proxy にすぎない。**
> M10-0 で active 計測されるのは **Cite-Belief Discipline** (citation discipline + belief promotion discipline) であり、**Social-ToM 本体 (false-belief reasoning / info-asymmetry handling / theory-of-other-mind operations) は M11-C 移送**。
>
> 将来の reader (Claude 次セッション / 別 contributor / paper writer) が "active な Layer 2 metric を見て ToM を測ったと結論する" 誤読を構造的に防止するため、本書 §C 各 sub-section / 各 ADR / 各 acceptance criterion で **claim boundary を繰り返し明示** する。
>
> 例: "M-L2-1 は belief promotion の慎重さを測る、ToM 能力ではない" — このような明示文を §C で繰り返す。

---

## §A. 両案の §-by-§ 対照

| 軸 | design-original | design-reimagine | 判定 |
|---|---|---|---|
| Layer 構造 | 4 layer (Indiv / Social-ToM / Counterfactual / Emotional) | 3 layer (Indiv / Cite-Belief Discipline / Counterfactual) | reimagine 寄り (Layer 4 Emotional は ADR-PM-5 で既に defer 済 → 実質 3 active layer) |
| ToM 計測の M10-0 active 化 | scenario lib + 5 metric を立てるが実走 M11-C → **doc 主体** | process-trace 3 metric が **既存 Phase B+C capture で active 計測** | reimagine 圧倒 (active evidence の有無は M10-0 close 質の根幹) |
| Schema migration | 新 table `metrics.social_tom` 追加 (DDL 変更) | `metrics.individuation` に dotted namespace で row 追加 (DDL 変更ゼロ) | reimagine 寄り (migration cost 低 + DB11 sentinel grep の自動 cover) |
| Scenario lib 7 件 | あり (S-CHA / S-AGO / S-GAR 計 7、各 multi-variant) | なし | original 寄り (M11-C 着手時の scenario 素材として価値あり、捨てるのは惜しい) |
| Negative control | 5 種 (v2 3 種 + NC-4/NC-5 新規) | 3 種 (v2 3 種そのまま) | reimagine 寄り (scenario lib 不在で NC-4/NC-5 の対象消失、無理矢理残すのは scope creep) |
| 追加 G-GEAR run | あり (Social-ToM scenario 走行) | なし (Phase B+C 既存 capture 再利用) | reimagine 圧倒 (G-GEAR overnight × N 不要) |
| Sub-task 数 | 3 (Indiv / Social-ToM eval / Source nav) | 2 (Indiv [+ Layer 2 統合] / Source nav) | reimagine 寄り (PR 数 + review burden 減) |
| Codex review に投げる context | 重い (5 metric + scenario lib + 5 NC + protocol v3) | 軽い (3 metric + 3 NC + protocol v2 そのまま) | reimagine 寄り (Codex token budget) |
| User 指示「ToM などを含めた評価体制」の literal 充足 | 高 (ToM scenario が物理存在) | 中 (ToM の前駆を測る + ToM 本体は M11-C 明示 defer) | original 寄り (literal compliance) |
| design bias | scenario 選定 bias 大 | bias 低 (natural rollout post-hoc) | reimagine 寄り |
| Statistical power | scenario 7 × 限定 trial | 3 channel × N=15,120 tick (Phase B+C 30 cell × 504 tick) | reimagine 圧倒 |
| M11-C handoff cleanness | scenario lib を M11-C で実走するだけ | M11-C で Layer 4 (Social-ToM proper) を新規 design + scenario も M11-C 時に起こす | original 寄り (M11-C handoff が低 churn) |

### 判定の総合

reimagine は 7 軸で勝つが、original は **scenario lib の M11-C 素材** と **User 指示への literal compliance** で勝つ。
両者の良いとこ取りが可能なら hybrid 採用が最善。

---

## §B. Hybrid 採用: **Hybrid-A revised**

### B.1 採用案

**Hybrid-A revised**: design-reimagine をベースに、design-original から **scenario spec 4 件のみ** を救出し、`m10-0-individuation-metrics` main の WP11 doc に組み込む。Social-ToM 専用 sub-task は **作らない** (M10-0 sub-task は 2 並列に縮小)。

### B.2 採用案の構造

```
Layer 1: Individuation  (v2 §2.2 matrix 11 metric、original/reimagine 共通)
Layer 2: Cite-Belief Discipline  (reimagine §1-§2、3 process-trace metric、active 計測)
Layer 3: Counterfactual perturbation  (v2 §2.6 そのまま、protocol v3 拡張なし)
Layer 4 (deferred): Social-ToM proper  → M11-C 移送
  - M10-0 では 4 scenario spec のみ doc 化 (= original §3.2 から救出した spec、`m10-0-individuation-metrics` の WP11 doc に同居)
  - 4 scenario = S-CHA-1 (private witness asymmetry) / S-AGO-1 (false rumor) / S-GAR-1 (counterfactual in solitude) / S-GAR-2 (cited source asymmetry)
  - 実走 M11-C、scenario library 実装も M11-C
Layer 5 (deferred): Emotional / cognitive alignment  → M11+ defer (ADR-PM-5 維持)
```

### B.3 採用根拠 (両案からの抽出と統合)

1. **Layer 1 + Layer 2 を main task に統合** (reimagine 由来): active 計測を M10-0 close 時に確保、追加 G-GEAR run 不要、schema migration ゼロ
2. **scenario lib を 7 → 4 に絞って doc 化** (original から救出): M11-C 着手時の素材として価値ある 4 件のみ保持、scenario lib の maintenance / design bias / Codex review burden を最小化
3. **Social-ToM 専用 sub-task 廃止** (reimagine 由来): M10-0 sub-task は 2 並列 (Indiv main + Source nav MVP) に縮小、PR 数削減
4. **新 table `metrics.social_tom` 廃止** (reimagine 由来): DDL 変更ゼロ、DB11 sentinel grep 自動 cover
5. **NC-4/NC-5 廃止** (reimagine 由来): scenario lib 縮小で対象消失、無理に残さない
6. **protocol v3 廃止、v2 §2.6 そのまま採用** (reimagine 由来): 拡張を避ける
7. **scenario 4 件の spec doc は WP11 として ~200 行 markdown** (original から救出): 当初の ADR-PM-2 revised の reject 理由 (「~150 行では不十分」) は **Layer 2 を active で持たない場合の話**。Hybrid-A では Layer 2 backbone があるため scenario spec doc は薄くて済む — backbone と素材を分離して持てる
8. **User 指示「ToM などを含めた評価体制を具体的に強固に設計」への応答**:
   - "ToM": scenario 4 件 spec で literal compliance (M10-0 close 時に doc が存在)
   - "強固に": Layer 2 が active 計測 + statistical power N=15,120 tick + design bias 回避 で robust
   - "設計してから決める": 本 reimagine + hybrid 採用プロセス自体が design-first 充足

### B.4 採用案の M10-0 sub-task 構成 (final)

```
M10-0 (parallel sub-tasks, 2 並列):
  ├─ m10-0-individuation-metrics       (Layer 1 + Layer 2 統合 + WP11 = ToM scenario 4 spec doc)
  └─ m10-0-source-navigator-mvp        (idea_judgement.md Kant MVP、runtime 非接続)

M10-0 close 条件 = 2 sub-task すべて green に到達。
M11-C 着手時に Layer 4 (Social-ToM proper) を `m11-c-social-tom-proper` で新規 scaffold、
M10-0 WP11 の 4 scenario spec を素材として継承。
```

`m10-0-social-tom-eval` (当初予定独立 sub-task) は **廃止**。Hybrid-A revised では Layer 2 が main に統合され、scenario lib も spec のみで main の WP11 に同居するため、独立 sub-task の存在理由が消失。

---

## §C. M10 評価体制 concrete robust design (Hybrid-A revised 確定版)

### §C.1 Layer 構造 (3 active + 2 deferred)

```
Layer 1: Individuation (v2 §2.2 matrix 11 metric)
  - Burrows / Vendi / centroid / belief_variance / SWM Jaccard /
    habit_recall / action_adherence / zone_behavior + recovery
  - schema: metrics.individuation (v2 §2.3)
  - 既存 v2 draft を踏襲、変更なし

Layer 2: Cite-Belief Discipline (Hybrid 中核、reimagine §2.2 由来)
  - 3 process-trace metric:
    * provisional_to_promoted_rate
    * cited_memory_id_source_distribution (3-source JS divergence)
    * counterfactual_challenge_rejection_rate
  - schema: metrics.individuation の dotted namespace `cite_belief_discipline.*`
    (新 table 不要、DDL 変更ゼロ)
  - active 計測: M9-eval Phase B+C 30 cell × 504 tick = 15,120 tick base
  - tests: ~10 unit + 1 integration、相関行列 cross-Layer 1/2

Layer 3: Counterfactual perturbation (v2 §2.6 そのまま)
  - protocol: T_base=200 / T_perturb=50 / T_recover=200
  - 3 種 negative control (v2 既存: cite-disabled / shuffled-memory / no-individual-layer-ablation)
  - Layer 1 metric (recovery_rate) と Layer 2 metric (counterfactual_challenge_rejection_rate)
    を同 perturbation 内で同時計測

Layer 4 (deferred): Social-ToM proper
  - M10-0: 4 scenario spec doc のみ (WP11、~200 行 markdown)
    * S-CHA-1: private witness asymmetry
    * S-AGO-1: false rumor
    * S-GAR-1: counterfactual in solitude
    * S-GAR-2: cited source asymmetry
  - M11-C: scenario lib 実装 + 実走 + Social-ToM-specific metric 設計
  - M10-0 WP11 spec は M11-C への handoff 文書

Layer 5 (deferred): Emotional / cognitive alignment
  - M11+ defer (ADR-PM-5 維持)
  - 臨床主張回避
```

### §C.2 Layer 2 metric 定義 (Hybrid 中核)

#### M-L2-1: `cite_belief_discipline.provisional_to_promoted_rate`

- **Input**: `SemanticMemoryRecord.belief_kind` の per-tick transition log (`memory/store.py` 既存記録)
- **Definition**: 100-tick window 内で `provisional → promoted` への遷移 count / `provisional → (any)` 遷移 count
- **Aggregation**: per-individual × per-100-tick window、**block bootstrap (Codex HIGH-3 反映): window-level cluster で resample、autocorrelation 補正後の effective N を report**
- **Effect direction (Codex MEDIUM-3 反映)**: **descriptive のみ** (pass/fail gate にしない、band も freeze 前は不採用)。M10-0 は estimation + correlation guard のみ
- **Sources**: M9-eval Phase B+C 30 cell の raw_dialog.dialog から `belief_kind` transition を抽出
- **typed result**: status='valid' 期待、`provisional` 遷移ゼロの window は `status='degenerate', reason='no provisional belief in window'`
- **Claim boundary**: M-L2-1 は **belief promotion 慎重さ** を測る、ToM 能力ではない (Codex HIGH-4 反映)

#### M-L2-2: `cite_belief_discipline.cited_memory_id_source_distribution`

- **Input**: `LLMPlan.cited_memory_ids` per tick + 各 memory_id の `source` attribute (自己観測 / 他者 testimony / inferred の 3 分類)
- **Schema 依存 (Codex HIGH-1 + Q3 反映)**: `cited_memory_ids` schema は **M10-C territory**。M10-0 段階では 2 つの選択肢が存在:
  - (a) **stub schema 採用** (M10-0 で stub data contract を実装、M10-C で本格化): M-L2-2 を M10-0 で active 計測可能
  - (b) **unsupported 採用** (M10-0 では計測しない): M-L2-2 を `status='unsupported', reason='cited_memory_ids schema pending M10-C'` で返す、その挙動を golden test 化
- **本書の決定**: **(b) unsupported を M10-0 採用**。理由は (a) stub だと M10-C 設計時に stub schema との backward compat が制約になる、(b) なら M10-C 着手時に schema 確定後に enable 切替で済む
- **Definition** (M10-C 後の active 計測時): per-window で 3 source の比率 distribution、baseline との Jensen-Shannon divergence
- **Aggregation**: per-individual × per-100-tick window、**block bootstrap (Codex HIGH-3 反映)**
- **Effect direction**: divergence band (descriptive のみ、frozen 前は pass/fail gate にしない、Codex MEDIUM-3 反映)
- **typed result**: M10-0 では常に `status='unsupported', reason='cited_memory_ids schema pending M10-C'`、golden test で behavior pin
- **Claim boundary**: M-L2-2 は **citation source attribution discipline** を測る、ToM operations ではない (Codex HIGH-4 反映)

#### M-L2-3: `cite_belief_discipline.counterfactual_challenge_rejection_rate`

- **Input**: §C.3 perturbation 下の `cited_memory_ids` 集合 vs `counterfactual_challenge` channel 入力 memory_id 集合
- **Definition**: 1 - (perturbation tick で `cited_memory_ids` が counterfactual entry を **含む** tick の比率)
- **Aggregation**: per-individual × perturbation tick window
- **Effect direction (Codex HIGH-2 反映で修正)**: ~~greater than baseline_noindividual~~ → **greater than within-individual non-perturbation baseline** (同 individual の non-perturbation tick における random-citation positive control との対比、p<0.05 after FDR multiple-comparison correction)
- **Baseline 選定根拠**: `baseline_noindividual` (NC-3) は `cited_memory_ids` が self_observation 100% で counterfactual entry を cite すること自体が困難 → rejection 100% trivial に到達し、effect direction inversion risk。NC-3 は **degenerate / undefined** にし、within-individual non-perturbation baseline (= 同 individual の non-perturbation tick で random-citation positive control を作為的に inject した時の cite-acceptance rate) を comparator とする
- **typed result**: perturbation window 内で `cited_memory_ids` 完全空なら `status='degenerate', reason='no-cite under perturbation'`、§C.3 perturbation protocol 実走 (M11-C territory) が未完なら `status='unsupported', reason='requires perturbation protocol run, M11-C territory'`
- **Claim boundary**: M-L2-3 は **citation acceptance discipline** を測る、Social-ToM の false-belief reasoning ではない (Codex HIGH-4 反映)

### §C.3 Counterfactual perturbation protocol (v2 §2.6 そのまま、本書で追記事項のみ)

v2 §2.6 protocol は変更なし。本書での **追記事項のみ**:

- baseline tick (T_base) 中も Layer 2 3 metric を **同時計測** (Layer 1 と同 loader)
- perturbation tick (T_perturb) 中も Layer 2 metric を計測、特に M-L2-3 はこの window が主観測
- recovery tick (T_recover) 中も計測、Layer 2 metric は **non-perturbation baseline と比較** (perturbation 後の discipline が保たれるか)

### §C.4 Schema (DDL 変更ゼロ、`metrics.individuation` への dotted namespace 追加)

```sql
-- 既存 metrics.individuation table の metric_name 列に以下 prefix を追加で流すだけ
-- 'cite_belief_discipline.provisional_to_promoted_rate'
-- 'cite_belief_discipline.cited_memory_id_source_distribution'
-- 'cite_belief_discipline.counterfactual_challenge_rejection_rate'

-- channel 列の値:
-- 'belief_substrate' (M-L2-1)
-- 'citation_substrate' (M-L2-2)
-- 'citation_substrate' (M-L2-3)
```

新 table なし、DDL 変更なし、DB11 sentinel poison row test は既存テストが自動 cover。

**追加 allowlist test (Codex MEDIUM-4 反映)**: dotted namespace 内の `metric_name` が `cite_belief_discipline.*` allowlist 内に収まることを test 化 (`tests/test_evidence/test_metric_namespace_allowlist.py`)。これにより DB11 sentinel coverage が table-level (どの row も `metrics.individuation`) だけでなく namespace-level (`metric_name` prefix が anticipated allowlist 内) でも防御される。例:

```python
EXPECTED_CITE_BELIEF_DISCIPLINE_METRICS = frozenset({
    "cite_belief_discipline.provisional_to_promoted_rate",
    "cite_belief_discipline.cited_memory_id_source_distribution",
    "cite_belief_discipline.counterfactual_challenge_rejection_rate",
})

def test_cite_belief_discipline_namespace_allowlist():
    # metrics.individuation に投入される metric_name が allowlist 内であることを assert
    # 未知の metric_name が混入したら test 失敗 (silent namespace expansion 防止)
    ...
```

### §C.5 Negative control (v2 既存 3 種、変更なし)

| ID | name | Layer 2 metric ごとの期待 |
|---|---|---|
| NC-1 | cite-disabled | M-L2-2 inferred 比率上昇、M-L2-3 rejection 100% |
| NC-2 | shuffled-memory | M-L2-2 全 source random、M-L2-3 rejection 100% |
| NC-3 | no-individual-layer-ablation | M-L2-1 rate ≈ 0、M-L2-2 self_observation 100%、M-L2-3 undefined |

### §C.6 Acceptance preregister (`thresholds.md`)

| Threshold | State | Protocol |
|---|---|---|
| **Layer 1** | (v2 §2.5 既存 8 threshold、変更なし) | (v2 既存) |
| `cite_belief_discipline.provisional_to_promoted_rate` band | **descriptive only (Codex MEDIUM-3 反映)** — pass/fail gate にしない | **block/cluster bootstrap (window-level cluster)、1000 resample、95% CI、autocorrelation 補正後の effective N report 必須 (Codex HIGH-3 反映)**、estimation のみで gate 不参入 |
| `cite_belief_discipline.cited_memory_id_source_distribution` JS divergence | **unsupported (Codex HIGH-1 + Q3 反映)** — M10-C `cited_memory_ids` schema 確定後に descriptive estimation 切替、M10-0 では threshold 不参入 | (M10-0 では計測しない、`status='unsupported'` 100% を behavior pin) |
| `cite_belief_discipline.counterfactual_challenge_rejection_rate` lower bound | **unsupported (Codex HIGH-1 反映)** — perturbation 実走 M11-C territory、M10-0 では `status='unsupported'` 100% を behavior pin | M11-C で perturbation 実走後 calibrate: within-individual non-perturbation baseline との比較 (Codex HIGH-2 反映、NC-3 は degenerate)、effect direction = greater、p<0.05 after FDR multiple-comparison correction、**block/cluster bootstrap (Codex HIGH-3 反映)** |
| **Layer 4 (deferred)** | defer(M11-C, multi-agent rollout 後 calibrate) | M11-C task `m11-c-social-tom-proper` で protocol design |

### §C.7 Acceptance (Hybrid-A revised 統合版、v2 既存 + Layer 2 + WP11)

| ID | criterion | rationale |
|---|---|---|
| A1 (v2 既存) | Layer 1 11 metric が typed `MetricResult` を返す | v2 既存 |
| A2' (v2 既存) | Burrows ja は unsupported、en/de baseline regression なし | v2 HIGH-4 |
| A3 (v2 既存) | centroid N=1 で degenerate | v2 HIGH-4 |
| A4 (v2 既存) | 15 golden DuckDB から Vendi valid float | v2 HIGH-5 |
| A5 (v2 既存) | cache benchmark frame | v2 MEDIUM-6 |
| A6 (v2 既存) | schema 変更ゼロ (DDL 不変) | v2 + Hybrid 強化 |
| A7 (v2 既存) | 既存 tests + 新 unit tests (Layer 1 ~25 + Layer 2 ~10) PASS | 回帰防止 |
| A8 (v2 既存) | `--compute-individuation` flag off で byte-for-byte 不変 | v2 |
| A9 (v2 既存) | DB11 sentinel poison row test (Layer 2 row も自動 cover) | v2 + Hybrid 自動拡張 |
| A10 (v2 既存) | metric 相関行列、|r| ≥ 0.85 warn (Layer 1 × Layer 2 cross 含む) | v2 + Hybrid 拡張 |
| A11 (v2 既存) | `thresholds.md` 全 threshold が calibrate_before_unblinding state | v2 + Layer 2 3 threshold |
| **A12a (Hybrid + Codex HIGH-1)** | **M-L2-1 のみ** が M9-eval Phase B+C 30 cell × 504 tick から抽出可、descriptive estimate を `status='valid'` で返す比率 ≥ 90% (M-L2-1 は belief_kind transition log が既存なので achievable) | M-L2-1 active 計測検証 |
| **A12b (Hybrid + Codex HIGH-1)** | **M-L2-2** は M10-0 では `status='unsupported', reason='cited_memory_ids schema pending M10-C'` を **100%** 返す (M10-C schema 確定までの behavior pin、golden test 化) | schema-dependent metric の pin |
| **A12c (Hybrid + Codex HIGH-1)** | **M-L2-3** は M10-0 では `status='unsupported', reason='requires perturbation protocol run, M11-C territory'` を **100%** 返す (perturbation 実走 M11-C territory)、protocol freeze + protocol_version pin が M10-0 close 条件 | perturbation-dependent metric の pin |
| **A13 (Hybrid 新、Codex HIGH-3 反映)** | Layer 2 × NC-1/2/3 の §C.5 表期待値が **block/cluster bootstrap CI 95% band** 内 (autocorrelation 補正後の effective N report、M-L2-1 のみ active、M-L2-2/3 は unsupported pin の test 化) | negative control 健全性 + statistical rigor |
| **A14 (Hybrid 新、WP11 doc、Codex MEDIUM-2 反映)** | WP11 4 scenario spec doc が **handoff metadata** (`freshness_date=2026-05-15`, `protocol_version=pre-m10-0.1`, `dependencies`, `rereview_gate=M11-C task start`, `expected_inputs`, `failure_modes`) を含み、M11-C task `m11-c-social-tom-proper` 着手時に独立読解可能 | M11-C handoff durability |
| **A15 (新、Codex MEDIUM-4 反映)** | DB11 sentinel poison row test に `metric_name LIKE 'cite_belief_discipline.%'` の **allowlist test** を追加、dotted namespace coverage を table-level 以上に強化 | namespace allowlist 防御 |
| **A16 (新、Codex HIGH-4 反映)** | `design-final.md` / `decisions.md` / `m10-0-individuation-metrics` requirement.md が **claim boundary 警告** ("Layer 2 measures Cite-Belief Discipline only, NOT Social-ToM") を §0 + ADR + acceptance section で **3 回以上明示** | proxy drift 防止 |

### §C.8 WP11 (4 scenario spec doc、~250 行 markdown、Codex MEDIUM-2 反映で handoff metadata 追加)

m10-0-individuation-metrics main 内の WP11 として配置、`docs/m10-0/social-tom-scenarios.md` または相当のパスに M11-C handoff 文書化。

> **共通 handoff metadata** (各 scenario spec の先頭に必ず含める、Codex MEDIUM-2 反映):
> - `freshness_date: 2026-05-15`
> - `protocol_version: pre-m10-0.1`
> - `dependencies`:
>   - M9-eval Phase B+C capture format (`*.duckdb`)
>   - ERREMode FSM (zone routing)
>   - 5 zone definitions (`docs/glossary.md`)
>   - `cited_memory_ids` schema (M10-C territory、stub なしで実走 M11-C 着手時に解決)
>   - `SemanticMemoryRecord.belief_kind` schema
> - `rereview_gate: M11-C task start (m11-c-social-tom-proper scaffold 時に本 spec を 1 から読み直し)`
> - `expected_inputs: multi-agent dialog with zone routing, observation event log per agent, testimony channel separation`
> - `failure_modes`:
>   - zone definition change (chashitsu/agora/garden の 5 zone schema 改訂)
>   - agent_id schema change (`A`/`B`/`C` の identity model 変更)
>   - `cited_memory_ids` schema が M10-C で本書と異なる shape で決着した場合
>   - capture format break (`*.duckdb` の `raw_dialog.dialog` 列定義変更)
>   - `counterfactual_challenge` channel name 変更 (v2 §2.6 と integration)
> - **Claim boundary**: 本 4 scenario は **Social-ToM proper の評価素材** であり、M10-0 では active 計測しない。M11-C 着手時に Codex review + /reimagine を再度実施した上で実走に進む

4 scenario (各 ~50 行、上記 metadata は cross-cutting):

#### S-CHA-1: private witness asymmetry
- Setup: chashitsu zone、agent A 単独で observation event (例: 茶器移動)、後で agent B が入室
- Probe (M11-C で実走): A→B testimony 後、B の belief が update するか / 嘘の testimony 下で B の belief stability
- M10-0 spec: scenario rule + zone constraint + observation event categorisation のみ

#### S-AGO-1: false rumor
- Setup: agora zone、A は C と直接対話歴あり、B は C の伝聞 (rumor) を信じる、A と B が C について discuss
- Probe (M11-C で実走): testimony 階層 (direct experience vs second-hand) を model するか
- M10-0 spec: testimony hierarchy rule + rumor 注入 channel + memory_id source tagging のみ

#### S-GAR-1: counterfactual in solitude
- Setup: garden zone、A 単独 reflection、external counterfactual_challenge channel で opposite-stance evidence injection (v2 §2.6 と同 channel)
- Probe (M11-C で実走): A の reflection が counterfactual evidence を採用するか
- M10-0 spec: §C.3 perturbation との overlap 区別、scenario-specific は M11-C で具体化

#### S-GAR-2: cited source asymmetry
- Setup: garden zone、retrieved memory に「自身が cite した source」と「他者が cite した source」が混在
- Probe (M11-C で実走): source attribution の retention が belief revision priority を持つか (M10-C `WorldModelUpdateHint.cited_memory_ids` 前段)
- M10-0 spec: source-of-cite metadata schema + retention priority rule のみ

### §C.9 既存 metric との直交性 (相関行列)

v2 §2.4 A10 (metric 相関行列、|r| ≥ 0.85 で double-measurement warn) を以下に拡張:

- Layer 1 × Layer 1 (v2 既存)
- **Layer 1 × Layer 2 cross** (新): 警戒 pair (a priori):
  - `cognitive_habit_recall_rate` ↔ `provisional_to_promoted_rate`: 期待 |r| 低 (habit は behavioral signal、belief promotion は cognitive substrate)
  - `belief_variance` ↔ `provisional_to_promoted_rate`: 期待 |r| 中、独立性は input source の違い (variance は promoted 後の分布、rate は promotion 自体)
  - `recovery_rate` (Burrows) ↔ `counterfactual_challenge_rejection_rate`: 期待 |r| 中-高、両者とも perturbation 抵抗を測る
- **Layer 2 × Layer 2** (新): §1.2 reimagine の独立性論証を踏襲、|r| ≥ 0.85 検出時に Layer 2 設計を見直す

---

## §D. Out-of-scope (Hybrid-A revised 明示)

M10-0 評価体制で扱わないもの:

- Multi-agent runtime execution (Layer 4 Social-ToM proper は M11-C へ)
- Production scale evaluation (M10-0 は 1-2 agent × Layer 1 + Layer 2 計測)
- 臨床主張 (HEART / MentalAlign clinical use はしない、Layer 5 defer)
- ToM scenario lib **実装** (M10-0 は spec doc 4 件のみ、実装は M11-C)
- Social-ToM-specific metric (false_belief_recovery 等) **実装** (M11-C)
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
- PEFT ablation registry yaml (ADR-PM-3、M12+ linkback のみ)

---

## §E. WP 分割 (Hybrid-A revised final)

| WP | 内容 | LOC 想定 | depends |
|---|---|---|---|
| WP1 | `src/erre_sandbox/eval/individuation/` 関数群 + MetricResult typed + provenance fields + **3 Layer 2 metric 関数 (cite_belief_discipline.*)** | ~850 (Layer 1 ~700 + Layer 2 ~150) | evidence/tier_b |
| WP2 | DuckDB schema (metrics.individuation table、Hybrid で DDL 変更ゼロ確認 test) | ~150 | WP1 |
| WP3 | M9-eval CLI `--compute-individuation` flag + sidecar JSON + DB11 sentinel poison row test (Layer 2 row も自動 cover) | ~280 | WP1, WP2 |
| WP4 (削除済) | MeCab 移行は別 task | — | — |
| WP5 | `AnalysisView` loader (raw_dialog.dialog + belief_kind transition + cited_memory_ids 抽出) | ~250 (v2 ~200 + Layer 2 抽出 ~50) | (none) |
| WP6 | Cache benchmark framework | ~250 | (none) |
| WP7 | Prompt ordering contract spec | ~80 lines doc | (none) |
| WP8 | Unit tests (Layer 1 ~25 + Layer 2 ~10) + integration test + correlation matrix test (Layer 1 × Layer 2 cross) | ~850 | WP1-3, WP5 |
| WP9 | `thresholds.md` 起草 (Layer 1 8 threshold + Layer 2 3 threshold + Layer 4 defer entry) | ~180 lines doc | (none) |
| WP10 | Recovery protocol spec (v2 §2.6 そのまま、Hybrid で拡張なし) | ~100 lines doc | (none) |
| **WP11 (Hybrid)** | **4 scenario spec doc (S-CHA-1 / S-AGO-1 / S-GAR-1 / S-GAR-2)、M11-C handoff** | **~200 lines doc** | (none) |

Total LOC 想定: **~2980 production + ~850 test + ~560 doc = ~4390** (design-original ~4500+ より小、design-reimagine ~3810 より大、Hybrid で 4 scenario spec を救出した分の +200 lines doc)

依存最小化: WP5 (loader) 先行、WP1-3 並行、WP7/WP9/WP10/WP11 は完全独立 doc。

---

## §F. M10-0 sub-task 構成 (Hybrid-A revised final)

```
M10-0 (parallel sub-tasks, 2 並列):
  ├─ m10-0-individuation-metrics       (Layer 1 + Layer 2 + WP11 4 scenario spec doc)
  └─ m10-0-source-navigator-mvp        (idea_judgement.md Kant MVP、runtime 非接続)

M10-0 close 条件 = 2 sub-task すべて green に到達。

M11-C 着手時に Layer 4 (Social-ToM proper) を `m11-c-social-tom-proper` で新規 scaffold、
M10-0 WP11 の 4 scenario spec を素材として継承。
```

ADR-PM-2 revised の決定 (「Social-ToM eval を独立 sub-task `m10-0-social-tom-eval` に格上げ」) は **再 revise** され、Hybrid-A revised では Social-ToM 専用 sub-task は **作らない**。`decisions.md` の ADR-PM-2 に再 revise entry を追加する。

---

## §G. v2 draft Addendum patch ドラフト (Hybrid-A revised 反映)

`.steering/20260508-cognition-deepen-7point-proposal/m10-0-concrete-design-draft.md` への追記文案。次 task scaffold 時に本体に commit。

### §2.7 (out-of-scope) への追記

```markdown
- **Cite-Belief Discipline metric (Layer 2)**: 3 metric を `metrics.individuation` の
  dotted namespace `cite_belief_discipline.*` で同 table に流す。DDL 変更ゼロ。詳細は
  `.steering/20260515-pre-m10-design-synthesis/design-final.md` §C.2
- **Social-ToM proper (Layer 4)**: M11-C 移送、本 v2 draft では 4 scenario spec doc
  (S-CHA-1 / S-AGO-1 / S-GAR-1 / S-GAR-2) を WP11 として保持、実装 + 実走は
  `m11-c-social-tom-proper` で
- **source_navigator (Corpus2Skill 型)** → 独立 sub-task `m10-0-source-navigator-mvp`
  (詳細は同 §F)
- **PEFT ablation registry yaml format** → M12+ task `m12-peft-ablation-qdora` で
  initialize (idea_judgement_2.md §4 参照)
- **Emotional / cognitive alignment (HEART / MentalAlign)** → M11+ task
  `m11-emotional-alignment-rubric` defer、臨床主張回避 (ADR-PM-5)
```

### §3 (WP 分割) への追記 (Hybrid-A revised LOC 表)

```markdown
| WP1 | (拡張) Layer 1 11 metric + Layer 2 3 metric (cite_belief_discipline.*) | ~850 | evidence/tier_b |
| WP11 (新、Hybrid) | 4 scenario spec doc (S-CHA-1 / S-AGO-1 / S-GAR-1 / S-GAR-2) | ~200 lines doc | (none) |
```

(註: design-original で予定した「WP11 Social-ToM eval」は廃止、Hybrid では 4 scenario spec doc に縮小。)

### §6 (References) への追記

```markdown
- `.steering/20260515-pre-m10-design-synthesis/design-final.md` §C (Hybrid-A revised)
- `.steering/20260515-pre-m10-design-synthesis/design-original.md` (historical, capability-oriented)
- `.steering/20260515-pre-m10-design-synthesis/design-reimagine.md` (process-trace + power-first)
- `.steering/20260515-pre-m10-design-synthesis/decisions.md` ADR-PM-1〜PM-7 (PM-6/PM-7 は Hybrid-A revised)
- `.steering/20260515-pre-m10-design-synthesis/idea-judgement-source-navigator.md`
- `.steering/20260515-pre-m10-design-synthesis/idea-judgement-pdf-survey.md`
```

---

## §H. 次 task scaffold 草稿 (inline、次セッションで `.steering/_template/` から起こす際の素)

### §H.1 `m10-0-individuation-metrics` requirement.md 草稿 (Hybrid-A revised final)

```markdown
# M10-0 Individuation Metrics

## 背景
v2 draft `m10-0-concrete-design-draft.md` (PR #159、Codex 12th HIGH 5 反映済) の WP1-WP10 を
踏襲し、`.steering/20260515-pre-m10-design-synthesis/design-final.md` §C の Hybrid-A revised
で確定した Layer 2 (Cite-Belief Discipline 3 metric) を統合する。Social-ToM proper は M11-C 移送、
本 task では WP11 で 4 scenario spec doc のみ保持。

## ゴール
- v2 draft WP1-WP10 + Hybrid WP11 の実装 (LOC 想定 ~4390)
- Layer 2 3 metric が M9-eval Phase B+C 既存 capture から active 計測 (status='valid' ≥ 90%)
- 既存 1418+ tests + 新 ~35 unit + ~1 integration 全 green
- schema 変更ゼロ (DDL 不変、`metrics.individuation` への dotted namespace 追加のみ)

## スコープ
含む: WP1-WP3 + WP5-WP11 全て。WP4 (MeCab) は別 task
含まない: source_navigator (m10-0-source-navigator-mvp) / Social-ToM proper (m11-c-social-tom-proper) /
         PhilosopherBase 実装 (M10-A) / etc.

## 受け入れ条件
design-final.md §C.7 A1-A14 全 pass。
```

### §H.2 `m10-0-source-navigator-mvp` requirement.md 草稿 (変更なし)

```markdown
# M10-0 Source Navigator MVP
(design.md §6.3 / design-original §6.3 と同じ、idea_judgement.md MVP acceptance 踏襲)
```

(本書は変更なし、design-original §6.3 をそのまま採用。)

---

## §I. `idea_judgement.md` / `idea_judgement_2.md` 最終配置案 (変更なし)

design-original §7 と同じ、既に rename move 完了:
- `idea_judgement.md` → `.steering/20260515-pre-m10-design-synthesis/idea-judgement-source-navigator.md`
- `idea_judgement_2.md` → `.steering/20260515-pre-m10-design-synthesis/idea-judgement-pdf-survey.md`

---

## §J. Codex 13th review への引き継ぎ (本書 + design-original + design-reimagine の 3 文書を投げる)

Codex review prompt は `codex-review-prompt.md` 別途起草。本書 §A 対照 + §B Hybrid 採用根拠 + §C-§H の concrete design に対して independent stress-test を要請。期待 finding:

- HIGH 候補: Layer 2 metric の sufficient statistic 性 (M-L2-1/2/3 の独立性論証は妥当か)、`cited_memory_ids` schema が M10-0 で stub 必要かの確認、M11-C handoff 文書としての WP11 4 scenario spec の十分性、Hybrid-A revised が ADR-PM-2 を再 revise することの整合性
- MEDIUM 候補: NC-1/2/3 の Layer 2 期待値表 (§C.5) の rigor、相関行列 cross-layer 警戒 pair の閾値、Phase B+C 既存 capture の status='valid' ≥ 90% 期待が realistic か
- LOW 候補: ナラティブ凝集、用語統一 (cite-belief vs cite/belief vs belief-cite)

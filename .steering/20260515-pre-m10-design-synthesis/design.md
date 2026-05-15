# 設計 — pre-M10 design synthesis (canonical, repair pass 2026-05-15)

> **Status**: ACTIVE — canonical implementation reference for pre-M10 design synthesis.
> **Date**: 2026-05-15  **Base commit**: `fb651e7` (main、本書 repair pass 起点)
>
> **本書の位置づけ**:
> - 旧 `design-final.md` (Hybrid-A revised + Codex 13th HIGH 4 反映済) を起点に、本セッションの **repair pass** で以下を補正した canonical implementation reference。
> - `AGENTS.md` / CI が `.steering/<task>/design.md` を必須としているため、本書を canonical 配置。`design-final.md` は historical reference として残置 (本書と内容が重複するが、合意プロセス trace のため保持)。
> - `design-original.md` (capability-oriented scenario-lib、SUPERSEDED) と `design-reimagine.md` (process-trace + power-first、SUPERSEDED) は historical reference のまま。
>
> **本 repair pass で補正した項目** (詳細は §X repair-log):
>
> 1. `SemanticMemoryRecord.belief_kind` 値域 (`trust/clash/wary/curious/ambivalent`) と "M-L2-1 = `provisional → promoted` rate" 仮定の不整合を修正。M10-0 で M-L2-1 を **active 計測しない** (現行 schema で測れないため、unsupported / 別 task defer)。
> 2. "Layer 2 3 metric が active 計測 / `status='valid'` ≥ 90%" を撤回。M-L2-1/2/3 全てが M10-0 では unsupported pin。Layer 2 active 計測の主張を弱める。
> 3. Phase B+C 30 cell × 504 tick = 15,120 tick base を **無条件前提から外す**。Mac 上で natural 15 DuckDB 本体が欠落しているため、natural 受領 + checksum verify を precondition / blocker に降格。
> 4. "DDL 変更ゼロ" 表現を「Layer 2 用の追加 table は作らない」に置換。`metrics.individuation` table 自体は **M10-0 main で新規追加** (現行 `bootstrap_schema()` には `metrics.tier_{a,b,c}` のみ存在、`metrics.individuation` は未存在)。
> 5. 実装配置を `src/erre_sandbox/eval/individuation/` → **`src/erre_sandbox/evidence/individuation/`** に修正 (現行 repo の evidence layer pattern `evidence/tier_b/` 等と整合)。
> 6. ADR-PM-8: M10-0 concrete design final freeze を **G-GEAR QLoRA retrain v2 verdict 後** に置く gate を新設。本 repair pass では steering / design boundary fix まで。
> 7. `tasklist.md` の "m10-0-social-tom-eval scaffold" 等 stale 記述を撤去、次 task scaffold は 2 件 + M11-C defer に統一。
>
> 上記 1-5 は **Codex 13th HIGH 反映方針の延長線上** にある追加 fix (HIGH-1 「unsupported 100% pin」を M-L2-1 にも拡張) で、本 repair pass で本書として確定。

---

## §0. **Claim boundary 警告 (Codex HIGH-4 反映 + 本 repair pass 強化)**

> **本設計の Layer 2 (Cite-Belief Discipline) は Social-ToM proper の sufficient statistic ではない。**
> **Layer 2 は process-trace prerequisite / proxy にすぎない。**
>
> 加えて **本 repair pass で確定**:
> **M10-0 段階では Layer 2 の 3 metric いずれも active 計測しない (M-L2-1/2/3 すべて unsupported pin)。**
> - M-L2-1: 現行 `SemanticMemoryRecord.belief_kind` は `trust/clash/wary/curious/ambivalent` であり `provisional/promoted` transition を持たない。schema 拡張 (M10-C 以降) or 別 task で要件再定義。
> - M-L2-2: `cited_memory_ids` schema が M10-C territory。
> - M-L2-3: counterfactual perturbation 実走が M11-C territory。
>
> M10-0 で Layer 2 が果たす役割は **schema / namespace / protocol / claim-boundary の事前固定 + unsupported behavior pin** に限定。
>
> 将来の reader (Claude 次セッション / 別 contributor / paper writer) が "active な Layer 2 metric を見て ToM を測ったと結論する" 誤読、および "M10-0 で Layer 2 を測ったと結論する" 二重誤読を構造的に防止するため、本書 §C 各 sub-section / 各 ADR / 各 acceptance criterion で **claim boundary を繰り返し明示** する。
>
> Social-ToM 本体 (false-belief reasoning / info-asymmetry handling / theory-of-other-mind operations) は M11-C 移送。

---

## §A. 両案の §-by-§ 対照 (歴史的経緯、SUPERSEDED 文書間の対照)

| 軸 | design-original | design-reimagine | 判定 |
|---|---|---|---|
| Layer 構造 | 4 layer (Indiv / Social-ToM / Counterfactual / Emotional) | 3 layer (Indiv / Cite-Belief Discipline / Counterfactual) | reimagine 寄り (Layer 4 Emotional は ADR-PM-5 で既に defer 済 → 実質 3 active layer) |
| ToM 計測の M10-0 active 化 | scenario lib + 5 metric を立てるが実走 M11-C → **doc 主体** | process-trace 3 metric が **既存 Phase B+C capture で active 計測** (本 repair pass で撤回) | reimagine ベース採用、ただし **active 計測の主張は本 repair pass で撤回** (M10-0 では unsupported pin) |
| Schema migration | 新 table `metrics.social_tom` 追加 (DDL 変更) | `metrics.individuation` に dotted namespace で row 追加 (Layer 2 用追加 table なし) | reimagine 寄り (Layer 2 用追加 table 不要、DB11 sentinel grep の自動 cover)。**但し `metrics.individuation` table 自体は M10-0 main で新規追加** |
| Scenario lib 7 件 | あり (S-CHA / S-AGO / S-GAR 計 7、各 multi-variant) | なし | original 寄り (M11-C 着手時の scenario 素材として価値あり、捨てるのは惜しい) |
| Negative control | 5 種 (v2 3 種 + NC-4/NC-5 新規) | 3 種 (v2 3 種そのまま) | reimagine 寄り (scenario lib 不在で NC-4/NC-5 の対象消失、無理矢理残すのは scope creep) |
| 追加 G-GEAR run | あり (Social-ToM scenario 走行) | なし (Phase B+C 既存 capture 再利用) | reimagine 圧倒 (G-GEAR overnight × N 不要)。**但し natural 15 DuckDB 本体は本 repair pass で blocker 化** |
| Sub-task 数 | 3 (Indiv / Social-ToM eval / Source nav) | 2 (Indiv [+ Layer 2 統合] / Source nav) | reimagine 寄り (PR 数 + review burden 減) |
| Codex review に投げる context | 重い (5 metric + scenario lib + 5 NC + protocol v3) | 軽い (3 metric + 3 NC + protocol v2 そのまま) | reimagine 寄り (Codex token budget) |
| design bias | scenario 選定 bias 大 | bias 低 (natural rollout post-hoc) | reimagine 寄り |
| Statistical power | scenario 7 × 限定 trial | 3 channel × N=15,120 tick (Phase B+C 30 cell × 504 tick、**precondition 化**) | reimagine 圧倒 (但し data availability が precondition) |
| M11-C handoff cleanness | scenario lib を M11-C で実走するだけ | M11-C で Layer 4 (Social-ToM proper) を新規 design + scenario も M11-C 時に起こす | original 寄り (M11-C handoff が低 churn) |

### 判定の総合 (歴史的記録)

reimagine ベース採用、ただし本 repair pass で active 計測主張を撤回。両者の良いとこ取り = Hybrid-A revised に repair pass で M10-0 unsupported pin 拡張を加えた構造が canonical。

---

## §B. Hybrid 採用: **Hybrid-A revised (本 repair pass で M10-0 active 計測 claim を撤回)**

### B.1 採用案

**Hybrid-A revised (repair-pass extended)**: design-reimagine をベースに、design-original から **scenario spec 4 件のみ** を救出し、`m10-0-individuation-metrics` main の WP11 doc に組み込む。Social-ToM 専用 sub-task は **作らない** (M10-0 sub-task は 2 並列に縮小)。**本 repair pass で追加**: M10-0 段階では Layer 2 3 metric すべてを unsupported pin、active 計測は M10-C / M11-C / 別 schema 拡張 task に分散 defer。

### B.2 採用案の構造 (repair-pass adjusted)

```
Layer 1: Individuation  (v2 §2.2 matrix 11 metric、original/reimagine 共通)
  - M10-0 で active 計測対象
Layer 2: Cite-Belief Discipline  (reimagine §1-§2、3 process-trace metric)
  - 本 repair pass: **M10-0 では全 metric を unsupported pin に統一**
  - schema / namespace / protocol / claim-boundary の事前固定 + behavior pin が M10-0 の役割
  - active 計測は M10-C (M-L2-2)、M11-C (M-L2-3)、schema 拡張 task (M-L2-1) で別途
Layer 3: Counterfactual perturbation  (v2 §2.6 そのまま、protocol v3 拡張なし)
  - M10-0 では perturbation 実走 NOT executed (M11-C territory)
Layer 4 (deferred): Social-ToM proper  → M11-C 移送
  - M10-0 では 4 scenario spec のみ doc 化 (WP11、M11-C handoff)
Layer 5 (deferred): Emotional / cognitive alignment  → M11+ defer (ADR-PM-5 維持)
```

### B.3 採用根拠 (両案からの抽出と統合、本 repair pass で追補)

1. **Layer 1 + Layer 2 を main task に統合** (reimagine 由来): Layer 1 active 計測を M10-0 close 時に確保。Layer 2 は schema / namespace / behavior pin の前提整備に限定 (本 repair pass で active 計測 claim を撤回)
2. **scenario lib を 7 → 4 に絞って doc 化** (original から救出): M11-C 着手時の素材として価値ある 4 件のみ保持
3. **Social-ToM 専用 sub-task 廃止** (reimagine 由来): M10-0 sub-task は 2 並列 (Indiv main + Source nav MVP) に縮小
4. **Layer 2 用の追加 table は作らない** (reimagine 由来): `metrics.individuation` への dotted namespace で同居、DB11 sentinel grep 自動 cover。**但し `metrics.individuation` table 自体は M10-0 main で新規 DDL 追加** (本 repair pass で表現修正)
5. **NC-4/NC-5 廃止** (reimagine 由来): scenario lib 縮小で対象消失、無理に残さない
6. **protocol v3 廃止、v2 §2.6 そのまま採用** (reimagine 由来): 拡張を避ける
7. **scenario 4 件の spec doc は WP11 として ~200 行 markdown** (original から救出)
8. **本 repair pass 追加 (ADR-PM-8)**: M10-0 concrete design final freeze は G-GEAR QLoRA retrain v2 verdict 後に置く。本 repair pass では steering 修正 + design boundary fix まで、最終 freeze は retrain v2 ADOPT/REJECT 確定後

### B.4 採用案の M10-0 sub-task 構成 (final)

```
M10-0 (parallel sub-tasks, 2 並列):
  ├─ m10-0-individuation-metrics       (Layer 1 + Layer 2 (unsupported pin) + WP11 = ToM scenario 4 spec doc)
  └─ m10-0-source-navigator-mvp        (idea_judgement.md Kant MVP、runtime 非接続)

M10-0 close 条件 = 2 sub-task すべて green に到達。
ただし M10-0 final freeze は G-GEAR QLoRA retrain v2 verdict 後 (ADR-PM-8)。
M11-C 着手時に Layer 4 (Social-ToM proper) を `m11-c-social-tom-proper` で新規 scaffold、
M10-0 WP11 の 4 scenario spec を素材として継承。
```

`m10-0-social-tom-eval` (当初予定独立 sub-task) は **廃止**。Hybrid-A revised では Layer 2 が main に統合され、scenario lib も spec のみで main の WP11 に同居するため、独立 sub-task の存在理由が消失 (ADR-PM-6 で SUPERSEDED、ADR-PM-2 旧文)。

---

## §C. M10 評価体制 concrete robust design (Hybrid-A revised + repair-pass 確定版)

### §C.0 Precondition / Blocker (本 repair pass 新設)

M10-0 implementation 着手時に以下を **gate 確認** する。未充足は blocker。

| ID | 内容 | Status (2026-05-15 本 repair pass 時点) | Resolution path |
|---|---|---|---|
| PC-1 | `data/eval/golden/` に stimulus 15 DuckDB body | **OK** (`*_stimulus_run*.duckdb` 15 本確認済、各 ~536KB) | (済) |
| PC-2 | `data/eval/golden/` に natural 15 DuckDB body | **BLOCKED** (現在 sidecar `.capture.json` 5×3=15 本のみ、本体 `*.duckdb` 不在) | G-GEAR から HTTP rsync (Mac canonical workflow、`feedback_crlf_canonical_for_md5` 参照)、checksum md5 突合 |
| PC-3 | `data/eval/golden/_checksums_*.txt` で checksum verify pass | partial (`_checksums_phase_b.txt` / `_checksums_mac_received.txt` あり、`_checksums_p3_full.txt` あり、natural body 不在のため verify 不可) | PC-2 解消後に full verify |
| PC-4 | G-GEAR QLoRA retrain v2 verdict (ADOPT / REJECT) | **PENDING** (ADR-PM-8) | retrain v2 完走 → pilot recapture → DA-14 matrix verdict → ADR-PM-8 entry update |
| PC-5 | `data/lora/m9-c-adopt-v2/kant_r8_v2/train_metadata.json` + checkpoint / adapter artefacts | **PENDING** | retrain v2 実走後 (PC-4 と連動) |

**PC-1 / PC-2 / PC-3 の意味**: Phase B+C 30 cell × 504 tick = 15,120 tick base は **無条件前提から外す**。Mac ローカルで現時点利用可能なのは stimulus 15 cell のみ。natural 15 cell の本体受領 / 配置 / checksum verify を済ませて初めて 30 cell base が成立する。Layer 1 metric の一部 (natural rollout 由来) は PC-2/PC-3 解消後に extraction 可能。

**PC-4 / PC-5 の意味**: ADR-PM-8 で確定。M10-0 concrete design final freeze と sub-task scaffold 起票は retrain v2 verdict 後。

### §C.1 Layer 構造 (1 active + 3 deferred / pinned)

```
Layer 1: Individuation (v2 §2.2 matrix 11 metric)
  - active 計測対象 (M10-0)
  - Burrows / Vendi / centroid / belief_variance / SWM Jaccard /
    habit_recall / action_adherence / zone_behavior + recovery
  - schema: metrics.individuation (M10-0 main で新規 DDL 追加)
  - 既存 v2 draft を踏襲、変更なし
  - data dependency: PC-1 (stimulus 15) は確保済、PC-2/PC-3 (natural 15) は blocker

Layer 2: Cite-Belief Discipline (Hybrid 中核、ただし M10-0 では unsupported pin)
  - 3 process-trace metric、すべて M10-0 では behavior pin (unsupported 100%)
    * provisional_to_promoted_rate (M-L2-1) — schema 不整合、別 task で要件再定義
    * cited_memory_id_source_distribution (M-L2-2) — M10-C schema 待ち
    * counterfactual_challenge_rejection_rate (M-L2-3) — M11-C perturbation 待ち
  - schema: metrics.individuation の dotted namespace `cite_belief_discipline.*`
    (Layer 2 用の追加 table は作らない)
  - M10-0 での active 計測は **しない** (本 repair pass で確定)
  - M10-0 での役割: schema / namespace / claim-boundary 事前固定 + unsupported pin 動作の golden test 化
  - tests: behavior pin の golden tests + namespace allowlist test

Layer 3: Counterfactual perturbation (v2 §2.6 そのまま)
  - protocol freeze + protocol_version pin のみ M10-0 で実施
  - protocol 実走は M11-C territory (M10-0 では NOT executed)
  - 3 種 negative control (v2 既存: cite-disabled / shuffled-memory / no-individual-layer-ablation)
    も M10-0 では文書化のみ、実走 M11-C

Layer 4 (deferred): Social-ToM proper
  - M10-0: 4 scenario spec doc のみ (WP11、~250 行 markdown、handoff metadata 含む)
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

### §C.2 Layer 2 metric 定義 (本 repair pass: 全 metric M10-0 unsupported pin)

#### M-L2-1: `cite_belief_discipline.provisional_to_promoted_rate`

- **本 repair pass での扱い (重要)**: **M10-0 では `status='unsupported'` 100% pin**。理由:
  - 現行 `SemanticMemoryRecord.belief_kind` の値域は `Literal["trust","clash","wary","curious","ambivalent"]` (`schemas.py:94`)
  - `provisional / promoted` 状態は現行 schema に **存在しない**
  - `belief_kind` transition log は raw_dialog から抽出可能だが、上記 5 値間の遷移であり M-L2-1 の semantic (慎重に promote するか) を測れない
  - schema 拡張 (belief promotion lifecycle field 追加) は M10-C 以降 / 別 task で要件再定義する
- **M10-0 動作**: 常に `status='unsupported', reason='belief promotion lifecycle field not present in current SemanticMemoryRecord schema; metric requires schema extension or redefinition (deferred to M10-C / dedicated schema task)'` を返す、golden test 化
- **Definition** (schema 拡張後の active 計測時、reference 保持): 100-tick window 内で `provisional → promoted` への遷移 count / `provisional → (any)` 遷移 count (仮定義、要 schema 確定)
- **Aggregation** (active 化時の reference 保持): per-individual × per-100-tick window、block bootstrap (window-level cluster で resample、autocorrelation 補正後の effective N report) — Codex HIGH-3 反映
- **Effect direction** (Codex MEDIUM-3 反映、active 化時): descriptive のみ、pass/fail gate にしない
- **Claim boundary**: M-L2-1 は **belief promotion 慎重さ** を測ることを意図する、ToM 能力ではない。**かつ M10-0 では実測しない** (Codex HIGH-4 + 本 repair pass)

#### M-L2-2: `cite_belief_discipline.cited_memory_id_source_distribution`

- **Schema 依存 (Codex HIGH-1 + Q3 反映)**: `cited_memory_ids` schema は **M10-C territory**。M10-0 段階では **unsupported 採用**
- **M10-0 動作**: 常に `status='unsupported', reason='cited_memory_ids schema pending M10-C'` を返す、golden test 化
- **Definition** (M10-C 後の active 計測時、reference 保持): per-window で 3 source (自己観測 / 他者 testimony / inferred) の比率 distribution、baseline との Jensen-Shannon divergence
- **Aggregation** (active 化時): per-individual × per-100-tick window、block bootstrap (Codex HIGH-3)
- **Effect direction**: divergence band (descriptive のみ、frozen 前は pass/fail gate にしない、Codex MEDIUM-3)
- **Claim boundary**: M-L2-2 は **citation source attribution discipline** を測る、ToM operations ではない (Codex HIGH-4)

#### M-L2-3: `cite_belief_discipline.counterfactual_challenge_rejection_rate`

- **依存 (Codex HIGH-1 + 本 repair pass)**: §C.3 perturbation 実走 = M11-C territory。**M10-0 では `status='unsupported'` 100% pin**
- **M10-0 動作**: 常に `status='unsupported', reason='requires perturbation protocol run, M11-C territory'` を返す、golden test 化
- **Definition** (M11-C 後の active 計測時、reference 保持): 1 - (perturbation tick で `cited_memory_ids` が counterfactual entry を **含む** tick の比率)
- **Aggregation** (active 化時): per-individual × perturbation tick window
- **Effect direction (Codex HIGH-2 反映で修正)**: ~~greater than baseline_noindividual~~ → **greater than within-individual non-perturbation baseline** (random-citation positive control との対比、p<0.05 after FDR multiple-comparison correction)
- **Baseline 選定根拠**: `baseline_noindividual` (NC-3) は `cited_memory_ids` が self_observation 100% で counterfactual entry を cite すること自体が困難 → rejection 100% trivial に到達し、effect direction inversion risk。NC-3 は **degenerate / undefined** にし、within-individual non-perturbation baseline を comparator とする
- **Claim boundary**: M-L2-3 は **citation acceptance discipline** を測る、Social-ToM の false-belief reasoning ではない (Codex HIGH-4)

### §C.3 Counterfactual perturbation protocol (v2 §2.6 そのまま、本書で追記事項のみ、本 repair pass: M10-0 では protocol freeze のみ)

v2 §2.6 protocol は変更なし。本書での **追記事項**:

- M10-0 では protocol freeze + `protocol_version` pin のみ実施
- 実走 (baseline tick T_base / perturbation tick T_perturb / recovery tick T_recover) は **M11-C territory**
- Layer 1 metric を perturbation tick 中に同時計測する設計は active 化時 (M11-C 着手後) の reference 保持

### §C.4 Schema (Layer 2 用追加 table なし、`metrics.individuation` への dotted namespace 同居)

**`metrics.individuation` table 自体は M10-0 main で新規 DDL 追加** (現行 `bootstrap_schema()` には `metrics.tier_{a,b,c}` のみ存在、`metrics.individuation` は未存在、`src/erre_sandbox/evidence/eval_store.py:286-` 参照)。

```sql
-- M10-0 main で metrics.individuation table を新規追加 (v2 draft §2.3 で予定済)
-- DDL は v2 draft の schema 定義に従う (`metric_name`, `channel`, `status`, `value`, `provenance` 等)

-- Layer 2 は同 table の metric_name 列に以下 prefix で同居 (Layer 2 用の追加 table は作らない):
-- 'cite_belief_discipline.provisional_to_promoted_rate'
-- 'cite_belief_discipline.cited_memory_id_source_distribution'
-- 'cite_belief_discipline.counterfactual_challenge_rejection_rate'

-- channel 列の値:
-- 'belief_substrate' (M-L2-1)
-- 'citation_substrate' (M-L2-2)
-- 'citation_substrate' (M-L2-3)
```

**Layer 2 用追加 table なし** (新 `metrics.social_tom` は作らない、DB11 sentinel grep が `metrics.individuation` 上の Layer 2 row も自動 cover)。

**追加 allowlist test (Codex MEDIUM-4 反映)**: dotted namespace 内の `metric_name` が `cite_belief_discipline.*` allowlist 内に収まることを test 化 (`tests/test_evidence/test_metric_namespace_allowlist.py`)。

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

### §C.5 Negative control (v2 既存 3 種、変更なし、本 repair pass: M10-0 では文書化のみ実走 M11-C)

| ID | name | Layer 2 metric ごとの期待 (active 化時) | M10-0 status |
|---|---|---|---|
| NC-1 | cite-disabled | M-L2-2 inferred 比率上昇、M-L2-3 rejection 100% | 文書化のみ、実走 M11-C |
| NC-2 | shuffled-memory | M-L2-2 全 source random、M-L2-3 rejection 100% | 文書化のみ、実走 M11-C |
| NC-3 | no-individual-layer-ablation | M-L2-1 (active 化時 schema 拡張後) rate 関連の degenerate 期待、M-L2-2 self_observation 100%、M-L2-3 undefined (HIGH-2 反映で degenerate 確定) | 文書化のみ、実走 M11-C |

### §C.6 Acceptance preregister (`thresholds.md`、本 repair pass で全 Layer 2 を threshold 不参入に揃える)

| Threshold | State | Protocol |
|---|---|---|
| **Layer 1** | (v2 §2.5 既存 8 threshold、変更なし) | (v2 既存) |
| `cite_belief_discipline.provisional_to_promoted_rate` | **unsupported (本 repair pass 反映)** — 現行 belief_kind schema に provisional/promoted 不在、M10-0 では `status='unsupported'` 100% pin | schema 拡張 task で active 化後 calibrate (block/cluster bootstrap、autocorrelation 補正後 effective N report) |
| `cite_belief_discipline.cited_memory_id_source_distribution` JS divergence | **unsupported (Codex HIGH-1 + Q3 反映)** — M10-C `cited_memory_ids` schema 確定後に descriptive estimation 切替、M10-0 では threshold 不参入 | (M10-0 では計測しない、`status='unsupported'` 100% を behavior pin) |
| `cite_belief_discipline.counterfactual_challenge_rejection_rate` | **unsupported (Codex HIGH-1 反映)** — perturbation 実走 M11-C territory、M10-0 では `status='unsupported'` 100% pin | M11-C で perturbation 実走後 calibrate (within-individual non-perturbation baseline、HIGH-2 反映で NC-3 degenerate、effect direction = greater、p<0.05 after FDR、block/cluster bootstrap HIGH-3) |
| **Layer 4 (deferred)** | defer (M11-C、multi-agent rollout 後 calibrate) | M11-C task `m11-c-social-tom-proper` で protocol design |

### §C.7 Acceptance (Hybrid-A revised + 本 repair pass 統合版)

| ID | criterion | rationale |
|---|---|---|
| A1 (v2 既存) | Layer 1 11 metric が typed `MetricResult` を返す | v2 既存 |
| A2' (v2 既存) | Burrows ja は unsupported、en/de baseline regression なし | v2 HIGH-4 |
| A3 (v2 既存) | centroid N=1 で degenerate | v2 HIGH-4 |
| A4 (v2 既存) | 15 stimulus golden DuckDB から Vendi valid float (本 repair pass: stimulus 15 は PC-1 で確保済、natural 15 は PC-2 解消後の追加検証) | v2 HIGH-5 |
| A5 (v2 既存) | cache benchmark frame | v2 MEDIUM-6 |
| A6 (本 repair pass で表現修正) | **Layer 2 用の追加 table は作らない** (新 `metrics.social_tom` 等を増やさない)。`metrics.individuation` table 自体は M10-0 main で新規 DDL 追加されることを明示 | v2 + Hybrid 強化 + 本 repair pass |
| A7 (v2 既存) | 既存 tests + 新 unit tests (Layer 1 ~25 + Layer 2 behavior pin tests ~10) PASS | 回帰防止 |
| A8 (v2 既存) | `--compute-individuation` flag off で byte-for-byte 不変 | v2 |
| A9 (v2 既存) | DB11 sentinel poison row test (Layer 2 row も自動 cover) | v2 + Hybrid 自動拡張 |
| A10 (v2 既存) | metric 相関行列、`|r| ≥ 0.85` warn (Layer 1 active 計測のみ対象、Layer 2 は unsupported pin で cross 計算しない) | v2 (本 repair pass で Layer 2 は除外明示) |
| A11 (v2 既存) | `thresholds.md` 全 threshold が calibrate_before_unblinding state、Layer 2 全 3 metric は **unsupported state** で記載 | v2 + 本 repair pass |
| **A12a (本 repair pass で M10-0 unsupported に変更)** | **M-L2-1** は M10-0 では `status='unsupported', reason='belief promotion lifecycle field not present in current SemanticMemoryRecord schema'` を **100%** 返す、golden test 化 | 本 repair pass: schema 不整合の behavior pin |
| **A12b (Codex HIGH-1)** | **M-L2-2** は M10-0 では `status='unsupported', reason='cited_memory_ids schema pending M10-C'` を **100%** 返す | schema-dependent metric の pin |
| **A12c (Codex HIGH-1)** | **M-L2-3** は M10-0 では `status='unsupported', reason='requires perturbation protocol run, M11-C territory'` を **100%** 返す、protocol freeze + `protocol_version` pin が M10-0 close 条件 | perturbation-dependent metric の pin |
| **A13 (本 repair pass で実走条件 M11-C に移送)** | Layer 2 × NC-1/2/3 の §C.5 表期待値 verification は **M11-C territory** (M10-0 では unsupported pin の golden test のみ実行、NC 実走は M11-C で block/cluster bootstrap CI 95% band 検証) | negative control 健全性 + statistical rigor、active 化は M11-C |
| **A14 (Codex MEDIUM-2 反映)** | WP11 4 scenario spec doc が handoff metadata (`freshness_date=2026-05-15`, `protocol_version=pre-m10-0.1`, `dependencies`, `rereview_gate=M11-C task start`, `expected_inputs`, `failure_modes`) を含み、M11-C task `m11-c-social-tom-proper` 着手時に独立読解可能 | M11-C handoff durability |
| **A15 (Codex MEDIUM-4 反映)** | DB11 sentinel poison row test に `metric_name LIKE 'cite_belief_discipline.%'` allowlist test を追加、dotted namespace coverage を table-level 以上に強化 | namespace allowlist 防御 |
| **A16 (Codex HIGH-4 反映 + 本 repair pass 強化)** | `design.md` / `decisions.md` / `m10-0-individuation-metrics` requirement.md が **claim boundary 警告** ("Layer 2 measures Cite-Belief Discipline only, NOT Social-ToM" + "M10-0 では Layer 2 active 計測なし、unsupported pin のみ") を §0 + ADR + acceptance section で **3 回以上明示** | proxy drift + M10-0 active 化誤読 二重防止 |
| **A17 (本 repair pass 新設、ADR-PM-8)** | M10-0 sub-task scaffold (m10-0-individuation-metrics / m10-0-source-navigator-mvp) 起票は G-GEAR QLoRA retrain v2 verdict (ADOPT / REJECT) 確定後。retrain v2 ADOPT なら LoRA persona baseline、REJECT なら no-LoRA / prompt persona baseline で M10-0 評価体制を再確認 | M10-0 final freeze gate |
| **A18 (本 repair pass 新設、PC-1/PC-2/PC-3)** | M10-0 main 実装着手時に PC-1 (stimulus 15) を verify、PC-2/PC-3 (natural 15 + checksum) は blocker resolution 後の追加 verification step として明示 | data availability gate |

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
>   - `SemanticMemoryRecord.belief_kind` schema (本 repair pass: 値域 `trust/clash/wary/curious/ambivalent` は active 化時に再確認)
> - `rereview_gate: M11-C task start (m11-c-social-tom-proper scaffold 時に本 spec を 1 から読み直し)`
> - `expected_inputs: multi-agent dialog with zone routing, observation event log per agent, testimony channel separation`
> - `failure_modes`:
>   - zone definition change (5 zone schema 改訂)
>   - agent_id schema change (`A`/`B`/`C` の identity model 変更)
>   - `cited_memory_ids` schema が M10-C で本書と異なる shape で決着した場合
>   - capture format break (`*.duckdb` の `raw_dialog.dialog` 列定義変更)
>   - `counterfactual_challenge` channel name 変更 (v2 §2.6 と integration)
>   - `belief_kind` 値域変更 (本 repair pass で明示)
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

### §C.9 既存 metric との直交性 (相関行列、本 repair pass: Layer 1 active のみ対象)

v2 §2.4 A10 (metric 相関行列、`|r| ≥ 0.85` で double-measurement warn) を以下に **本 repair pass で縮小**:

- Layer 1 × Layer 1 (v2 既存、active)
- **Layer 1 × Layer 2 cross** (新): Layer 2 が M10-0 で unsupported pin のため **cross 計算は M11-C 以降に defer**。M10-0 では「cross 計算が unsupported pin により degenerate であること」を明示する behavior pin test のみ。
- **Layer 2 × Layer 2** (新): 同上、M11-C 以降に defer

active 化時 (M-L2-1 schema 拡張後 / M-L2-2 M10-C 後 / M-L2-3 M11-C 後) の警戒 pair (a priori、reference 保持):
- `cognitive_habit_recall_rate` ↔ `provisional_to_promoted_rate`: 期待 `|r|` 低
- `belief_variance` ↔ `provisional_to_promoted_rate`: 期待 `|r|` 中
- `recovery_rate` (Burrows) ↔ `counterfactual_challenge_rejection_rate`: 期待 `|r|` 中-高、両者とも perturbation 抵抗を測る

---

## §D. Out-of-scope (Hybrid-A revised + 本 repair pass 明示)

M10-0 評価体制で扱わないもの:

- Multi-agent runtime execution (Layer 4 Social-ToM proper は M11-C へ)
- Production scale evaluation (M10-0 は 1-2 agent × Layer 1 active 計測 + Layer 2 unsupported pin)
- 臨床主張 (HEART / MentalAlign clinical use はしない、Layer 5 defer)
- ToM scenario lib **実装** (M10-0 は spec doc 4 件のみ、実装は M11-C)
- Social-ToM-specific metric (false_belief_recovery 等) **実装** (M11-C)
- **Layer 2 3 metric の active 計測** (本 repair pass で M10-0 から除外、M-L2-1 schema 拡張 / M-L2-2 M10-C / M-L2-3 M11-C で別途)
- **Counterfactual perturbation 実走** (M10-0 は protocol freeze のみ、実走 M11-C)
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
- **`SemanticMemoryRecord.belief_kind` schema 拡張** (本 repair pass: 別 task で要件再定義、M-L2-1 active 化の prerequisite)

---

## §E. WP 分割 (Hybrid-A revised + 本 repair pass: 実装配置 evidence/individuation/ に修正)

| WP | 内容 | LOC 想定 | depends |
|---|---|---|---|
| WP1 | **`src/erre_sandbox/evidence/individuation/`** 関数群 + MetricResult typed + provenance fields + Layer 2 3 metric 関数 (`cite_belief_discipline.*`、すべて M10-0 では unsupported pin を返す behavior pin 実装) | ~750 (Layer 1 ~700 + Layer 2 unsupported pin ~50) | `evidence/tier_b/` (既存 pattern 参照) |
| WP2 | DuckDB schema (M10-0 main で `metrics.individuation` table を **新規 DDL 追加**、Layer 2 用追加 table なしを test で assert) | ~150 | WP1 |
| WP3 | M9-eval CLI `--compute-individuation` flag + sidecar JSON + DB11 sentinel poison row test (Layer 2 unsupported pin row も自動 cover) | ~280 | WP1, WP2 |
| WP4 (削除済) | MeCab 移行は別 task | — | — |
| WP5 | `AnalysisView` loader (raw_dialog.dialog + `belief_kind` transition (active 化時の reference) + cited_memory_ids (active 化時の reference) 抽出 hook) | ~250 | (none) |
| WP6 | Cache benchmark framework | ~250 | (none) |
| WP7 | Prompt ordering contract spec | ~80 lines doc | (none) |
| WP8 | Unit tests (Layer 1 active ~25 + Layer 2 unsupported pin behavior tests ~10) + integration test + correlation matrix test (Layer 1 active のみ対象、Layer 2 は cross-defer の behavior pin test) | ~850 | WP1-3, WP5 |
| WP9 | `thresholds.md` 起草 (Layer 1 8 threshold active + Layer 2 3 threshold **unsupported state** + Layer 4 defer entry) | ~180 lines doc | (none) |
| WP10 | Recovery protocol spec (v2 §2.6 そのまま、Hybrid で拡張なし、M10-0 は protocol freeze のみ) | ~100 lines doc | (none) |
| **WP11 (Hybrid)** | **4 scenario spec doc (S-CHA-1 / S-AGO-1 / S-GAR-1 / S-GAR-2)、M11-C handoff、handoff metadata 含む** | **~250 lines doc** | (none) |

実装配置 (本 repair pass で確定): **`src/erre_sandbox/evidence/individuation/`** (現行 repo の evidence layer pattern `evidence/tier_b/` と整合)。サブ構成案:

```
src/erre_sandbox/evidence/individuation/
  ├── __init__.py
  ├── layer1.py            # Burrows / Vendi / centroid / belief_variance / SWM Jaccard / habit / action / zone / recovery
  ├── cite_belief.py       # Layer 2 3 metric (すべて M10-0 unsupported pin、active 化時の関数 stub 保持)
  └── ...
```

代替案 (LOC 想定が小さければ): `src/erre_sandbox/evidence/individuation.py` 単一 module (tier_b 同様の flat 配置)。M10-0 main 実装着手時に LOC 実測で最終決定。

Total LOC 想定: **~2880 production + ~850 test + ~610 doc = ~4340** (Layer 2 unsupported pin で実装が縮小、~50 LOC 減)

依存最小化: WP5 (loader) 先行、WP1-3 並行、WP7/WP9/WP10/WP11 は完全独立 doc。

---

## §F. M10-0 sub-task 構成 (Hybrid-A revised + 本 repair pass final)

```
M10-0 (parallel sub-tasks, 2 並列):
  ├─ m10-0-individuation-metrics       (Layer 1 active + Layer 2 unsupported pin + WP11 4 scenario spec doc)
  └─ m10-0-source-navigator-mvp        (idea_judgement.md Kant MVP、runtime 非接続)

M10-0 close 条件 = 2 sub-task すべて green に到達。
M10-0 final freeze gate = G-GEAR QLoRA retrain v2 verdict (ADR-PM-8)。
M11-C 着手時に Layer 4 (Social-ToM proper) を `m11-c-social-tom-proper` で新規 scaffold、
M10-0 WP11 の 4 scenario spec を素材として継承。
```

ADR-PM-2 revised の決定 (「Social-ToM eval を独立 sub-task `m10-0-social-tom-eval` に格上げ」) は **再 revise** され、Hybrid-A revised では Social-ToM 専用 sub-task は **作らない** (ADR-PM-6 で SUPERSEDED)。本 repair pass で更に **M10-0 sub-task scaffold 起票自体を retrain v2 verdict gate に置く** (ADR-PM-8)。

---

## §G. v2 draft Addendum patch ドラフト (Hybrid-A revised + 本 repair pass 反映)

`.steering/20260508-cognition-deepen-7point-proposal/m10-0-concrete-design-draft.md` への追記文案。次 task scaffold 時 (retrain v2 verdict 後) に本体に commit。

### §2.7 (out-of-scope) への追記

```markdown
- **Cite-Belief Discipline metric (Layer 2)**: 3 metric を `metrics.individuation` の
  dotted namespace `cite_belief_discipline.*` で同 table に流す (Layer 2 用追加 table なし)。
  M10-0 では全 3 metric が **unsupported pin** で behavior 固定 (M-L2-1: schema 不整合、
  M-L2-2: M10-C 待ち、M-L2-3: M11-C 待ち)。詳細は
  `.steering/20260515-pre-m10-design-synthesis/design.md` §C.2
- **`metrics.individuation` table**: M10-0 main で新規 DDL 追加 (現行 bootstrap_schema は
  tier_{a,b,c} のみ)
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

### §3 (WP 分割) への追記

```markdown
| WP1 | (拡張) Layer 1 11 metric (active) + Layer 2 3 metric (cite_belief_discipline.*、unsupported pin) | ~750 | evidence/tier_b 既存 pattern 参照、配置 evidence/individuation/ |
| WP11 (新、Hybrid) | 4 scenario spec doc (S-CHA-1 / S-AGO-1 / S-GAR-1 / S-GAR-2、handoff metadata 含む) | ~250 lines doc | (none) |
```

(註: design-original で予定した「WP11 Social-ToM eval」は廃止、Hybrid では 4 scenario spec doc に縮小、本 repair pass で実装配置 evidence/individuation/ に確定。)

### §6 (References) への追記

```markdown
- `.steering/20260515-pre-m10-design-synthesis/design.md` (canonical、本 repair pass 反映)
- `.steering/20260515-pre-m10-design-synthesis/design-final.md` (historical reference、本 repair pass 前の Hybrid-A revised 文)
- `.steering/20260515-pre-m10-design-synthesis/design-original.md` (historical、capability-oriented)
- `.steering/20260515-pre-m10-design-synthesis/design-reimagine.md` (historical、process-trace + power-first)
- `.steering/20260515-pre-m10-design-synthesis/decisions.md` ADR-PM-1〜PM-8
- `.steering/20260515-pre-m10-design-synthesis/idea-judgement-source-navigator.md`
- `.steering/20260515-pre-m10-design-synthesis/idea-judgement-pdf-survey.md`
```

---

## §H. 次 task scaffold 草稿 (inline、retrain v2 verdict 後の起票用素材)

> **本 repair pass 追記 (ADR-PM-8)**: 以下の草稿は M10-0 sub-task scaffold 起票用の素材だが、**実起票は G-GEAR QLoRA retrain v2 verdict 確定後**。retrain v2 ADOPT/REJECT に応じて requirement.md の baseline 前提を再確認する。

### §H.1 `m10-0-individuation-metrics` requirement.md 草稿 (Hybrid-A revised + 本 repair pass)

```markdown
# M10-0 Individuation Metrics

## 背景
v2 draft `m10-0-concrete-design-draft.md` (PR #159、Codex 12th HIGH 5 反映済) の WP1-WP10 を
踏襲し、`.steering/20260515-pre-m10-design-synthesis/design.md` §C の Hybrid-A revised
(repair-pass extended) で確定した Layer 2 (Cite-Belief Discipline 3 metric、M10-0 では
unsupported pin) を統合する。Social-ToM proper は M11-C 移送、本 task では WP11 で 4 scenario
spec doc のみ保持。

QLoRA retrain v2 verdict (ADR-PM-8):
- ADOPT: LoRA persona + (future) individual layer を前提に baseline
- REJECT: no-LoRA / prompt persona を baseline に再調整

## ゴール
- v2 draft WP1-WP10 + Hybrid WP11 の実装 (LOC 想定 ~4340、本 repair pass 後)
- Layer 1 11 metric が active 計測 (status='valid' は Layer 1 のみが対象)
- Layer 2 3 metric は M10-0 で **unsupported pin** (status='unsupported' 100% を behavior pin、golden test 化)
- `metrics.individuation` table を M10-0 main で新規 DDL 追加 (Layer 2 用追加 table なし)
- 実装配置: `src/erre_sandbox/evidence/individuation/`
- 既存 1418+ tests + 新 ~35 unit + ~1 integration 全 green

## スコープ
含む: WP1-WP3 + WP5-WP11 全て。WP4 (MeCab) は別 task
含まない: source_navigator (m10-0-source-navigator-mvp) / Social-ToM proper (m11-c-social-tom-proper) /
         PhilosopherBase 実装 (M10-A) / SemanticMemoryRecord.belief_kind schema 拡張 (別 task) / etc.

## Precondition (本 repair pass、PC-1〜PC-5)
- PC-1: stimulus 15 DuckDB (確保済)
- PC-2: natural 15 DuckDB 本体受領 (blocker、G-GEAR rsync 必須)
- PC-3: checksum verify
- PC-4: QLoRA retrain v2 verdict (ADR-PM-8 gate)
- PC-5: retrain v2 artefacts

## 受け入れ条件
design.md §C.7 A1-A18 全 pass。
```

### §H.2 `m10-0-source-navigator-mvp` requirement.md 草稿 (変更なし)

```markdown
# M10-0 Source Navigator MVP
(design-original §6.3 と同じ、idea_judgement.md MVP acceptance 踏襲、本 repair pass で変更なし)
```

---

## §I. `idea_judgement.md` / `idea_judgement_2.md` 最終配置 (変更なし)

design-original §7 と同じ、既に rename move 完了:
- `idea_judgement.md` → `.steering/20260515-pre-m10-design-synthesis/idea-judgement-source-navigator.md`
- `idea_judgement_2.md` → `.steering/20260515-pre-m10-design-synthesis/idea-judgement-pdf-survey.md`

---

## §J. Codex 13th review への引き継ぎ (歴史的記録)

Codex 13th review は実施済 (66,261 tokens、Verdict: ADOPT-WITH-CHANGES、HIGH 4 / MEDIUM 5 / LOW 3、`codex-review.md` に verbatim 保存)。HIGH 4 + MEDIUM 5 + LOW 3 すべて反映済 (ADR-PM-7 詳細)。本 repair pass は ADR-PM-7 + ADR-PM-8 の上に追加 fix を載せた canonical 文。

---

## §X. 本 repair pass changelog (canonical-only)

> **2026-05-15 repair pass (本 design.md 確定時)**:
>
> 1. **M-L2-1 false premise 修正**: 現行 `SemanticMemoryRecord.belief_kind` 値域 `trust/clash/wary/curious/ambivalent` と `provisional/promoted` transition 仮定の不整合 → M10-0 では unsupported pin、active 化は schema 拡張 task 待ち。§C.2 / §C.6 / §C.7 A12a / §D / §E WP1 / §H.1 草稿に反映。
> 2. **Layer 2 active 計測主張の撤回**: §C.1 / §C.2 全 metric / §C.6 / §C.7 A10/A12a-c/A13 で「M10-0 では Layer 2 全 3 metric が unsupported pin」に統一。
> 3. **Phase B+C 30 cell 前提の降格**: §C.0 PC-1〜PC-3 で stimulus 15 OK / natural 15 BLOCKED / checksum partial を明示。`data/eval/golden/` 実体確認 (stimulus 15 DuckDB あり、natural 15 sidecar `.capture.json` のみ) に基づく。
> 4. **`metrics.individuation` DDL 表現の正確化**: §C.4 / §C.7 A6 / §E WP2 / §G で「Layer 2 用の追加 table は作らない」と「`metrics.individuation` table 自体は M10-0 main で新規 DDL 追加」を分けて記述。現行 `bootstrap_schema()` (`src/erre_sandbox/evidence/eval_store.py:286-`) は `metrics.tier_{a,b,c}` のみ。
> 5. **実装配置の修正**: §E / §G / §H で `src/erre_sandbox/eval/individuation/` → **`src/erre_sandbox/evidence/individuation/`** に変更。既存 `evidence/tier_b/` pattern と整合。
> 6. **ADR-PM-8 新設**: M10-0 final freeze を G-GEAR QLoRA retrain v2 verdict 後に置く gate。PC-4 / PC-5、§F、§H 冒頭、§C.7 A17 に反映。
> 7. **`tasklist.md` stale 記述整理**: `m10-0-social-tom-eval` scaffold 起票 / 「次 task scaffold 3 件」を撤去、2 件 + M11-C defer に統一。次アクションを「QLoRA retrain v2 verdict 後に M10-0 design freeze」に変更。
>
> 本 repair pass は **コード変更ゼロ** (`src/erre_sandbox/` / `tests/` 不変、`data/` artefact 削除なし)。

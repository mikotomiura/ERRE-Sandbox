# M10-0 Concrete Design Draft v2 — Codex HIGH 5 反映 (2026-05-11)

- **改訂**: v2 (2026-05-11)、Codex 12th review (gpt-5.5 xhigh、271,822 tokens、Verdict ADOPT-WITH-CHANGES) HIGH 5 + MEDIUM 6 + LOW 3 反映
- **位置づけ**: `reasoning-model-judgment.md` を validation した上で、M10-0 (Pre-flight: individuation metrics + dataset manifest + cache benchmark + prompt ordering contract) を実装可能水準まで詰めた草案
- **入力**:
  - `reasoning-model-judgment.md` (Claude メモ、2026-05-11)
  - `design-final.md` §3 M10-0 (PR #144 merged)
  - `decisions.md` DA-1 / DA-8 / DA-10 / DA-12 (PR #144 merged)
  - PR #145 DB11 ADR (training-view contamination prevention)
  - P4a Tier B merged (`evidence/tier_b/`、PR #148) — v1 で `eval/tier_b` と誤記、HIGH-5 で修正
  - `codex-review-m10-0.md` (Codex 12th、HIGH 5 含む)
- **v1 → v2 主要 diff**: §2.2 metric matrix 拡張 (M2)、§2.3 schema 配置変更 (HIGH-2)、§2.4 typed result 導入 (HIGH-4)、§2.5 calibrate_before_unblinding 採用 (HIGH-1)、§2.6 counterfactual_challenge 隔離 (HIGH-3)、§2.9 path 修正 + AnalysisView loader 化 (HIGH-5)、§3 WP4 MeCab 除外 + LOC 上方修正 (HIGH-4 / LOW-3)

---

## 1. memo 判定 (Claude solo)

`reasoning-model-judgment.md` の判定は既存 ADR (DA-1〜DA-13、DB11、ME-9 metaphor) に対して内部矛盾なし。Codex 12th も Q1 で memo の "weight-level M12+ defer" を妥当と確認。**ただし "activation analysis も完全 M12+" は強すぎる** → read-only/offline spike は M10/M11 で許容、runtime steering/weight update のみ M12+ gate (memo §1 "活性化・重み分析 RESEARCH SPIKE ONLY M12+" の文言を後段で緩める必要あり、PR 起票時に design-final.md Addendum で文言調整)。

Codex Q3 で **§3.1 5 metrics 直交性不足** が指摘: semantic centroid と Vendi は同 embedding kernel 依存、belief_variance と SWM Jaccard は同 belief substrate 依存 → divergence gate は最低 **2 independent channels** を要求。

---

## 2. Concrete design v2

### 2.1 タスク配置 (M9 完全終了後 scaffold)

```
.steering/[YYYYMMDD]-m10-0-individuation-metrics/
  requirement.md
  design.md
  design-reimagine.md     (mandatory per CLAUDE.md)
  codex-review-prompt.md
  codex-review.md         (verbatim)
  decisions.md            (ADR DA-IM-1〜)
  tasklist.md
  thresholds.md           (新、HIGH-1 反映、calibrate_before_unblinding 状態管理)
```

### 2.2 Channel × Metric matrix v2 (HIGH-5 + MEDIUM-2 + MEDIUM-4 反映)

**変更**:
- HIGH-5: 入力 channel を `_audit_stimulus.json` (audit metadata) ではなく `raw_dialog.dialog` window 抽出 (from `*.duckdb`) に修正
- MEDIUM-2: 行動 channel 3 件追加 (`cognitive_habit_recall_rate` / `action_adherence_rate` / `zone_behavior_consistency`)
- MEDIUM-4: M10-0 output に **metric 相関行列** 添付必須

| Metric | Input channel | What | Aggregation | Phase | Notes |
|---|---|---|---|---|---|
| `burrows_base_retention` | `raw_dialog.dialog` utterance window | function-word freq vs base corpus | per-individual | M10-0 | ja は **unsupported** typed result (HIGH-4)、en/de のみ valid |
| `semantic_centroid_distance` | utterance embedding (model_id pinned) | inter-individual style/content distance | pairwise same-base | M10-0 | Vendi と独立 channel にならない (Q3) |
| `vendi_diversity` (`evidence/tier_b/`) | utterance embedding kernel | within-base population diversity | population-level | M10-0 | kernel sensitivity follow-up 待ち |
| `belief_variance` | `SemanticMemoryRecord.belief_kind` (promoted のみ) | cognitive content divergence | pairwise + class-wise | M10-0 | SWM Jaccard と belief substrate 共有 |
| `world_model_overlap_jaccard` | `SubjectiveWorldModel.entries.key` per axis | SWM key overlap | pairwise × 5 axes | M10-0 関数のみ先行、active 計測 M10-A 以降 | belief_variance と非独立 |
| `big5_icc` (`evidence/tier_b/big5_icc.py`) | IPIP-NEO 応答 | personality stability across pop | ICC(A,1) or ICC(C,k) (MEDIUM-3 で diagnostic only) | M10-0 | M10-0 gate 不参入 (MEDIUM-3)、日本語 IPIP vendoring defer (Codex prior art) |
| `cognitive_habit_recall_rate` (新、M2) | tick 単位の habit fire / expected | base habit retention の behavioral signal | per-individual + class-wise | M10-0 | embedding 文体 vs 行動 habit を分離 |
| `action_adherence_rate` (新、M2) | LLMPlan.decision / next_intent vs zone-policy expected | 行動方針一貫性 | per-individual | M10-0 | base 一貫性の独立 channel |
| `zone_behavior_consistency` (新、M2) | zone × decision crosstab | persona-zone 関係保持 | per-individual | M10-0 | M9 trunk preferred_zones の運用 |
| `intervention_recovery_rate` | post-perturbation utterance | base habit recovery | dual (Burrows recovery + behavioral) | M10-0 protocol 定義のみ、実走 M11-C | HIGH-3 で channel 設計差し替え |
| `swm_persistence_rate` | post-perturbation SWM | individual stickiness | per-axis persistence | M11-C 実走 | HIGH-3 で write 禁止運用 |
| `narrative_drift` | NarrativeArc segments | trajectory divergence | pairwise edit distance | **M11-A 移送** | M10-0 で preregister のみ |
| `worldmodel_update_adoption_rate` | `LLMPlan.world_model_update_hint` | adoption / total | rate | **M10-C 移送** | DA-12 |

**追加 acceptance (MEDIUM-4)**: 上記 metric の **相関行列を M10-0 output** に同梱、|r| ≥ 0.85 のペアは独立 channel と見なさず double-measurement と判定する。

### 2.3 永続化 layer v2 (HIGH-2 反映)

**変更**: 新 schema を独立 namespace ではなく既存 `metrics.` 配下に置く。CI grep gate (`metrics.` literal 中心の DB11 sentinel) の防御範囲内に固定。

**DuckDB table**: `metrics.individuation` (additive、provenance fields 必須)

```sql
CREATE TABLE metrics.individuation (
  -- identification
  run_id            TEXT NOT NULL,
  individual_id     TEXT NOT NULL,
  base_persona_id   TEXT NOT NULL,
  tick              BIGINT NOT NULL,
  metric_name       TEXT NOT NULL,
  channel           TEXT NOT NULL,
  -- typed result (HIGH-4)
  status            TEXT NOT NULL CHECK (status IN ('valid','degenerate','unsupported')),
  value             DOUBLE,        -- NULL if status != 'valid'
  reason            TEXT,          -- non-null if status != 'valid'
  -- provenance (HIGH-2)
  metric_schema_version             TEXT NOT NULL,
  source_table                      TEXT NOT NULL,
  source_run_id                     TEXT NOT NULL,
  source_epoch_phase                TEXT NOT NULL,
  source_individual_layer_enabled   BOOLEAN NOT NULL,
  source_filter_hash                TEXT NOT NULL,
  embedding_model_id                TEXT,          -- nullable (Burrows 等 embedding 非依存 metric)
  computed_at                       TIMESTAMP NOT NULL
)
```

**サイドカー JSON** (`*.duckdb.capture.json` の sibling として `*.individuation.json`、`_audit_stimulus.json` には**書き込まない** — audit metadata は audit のままにする HIGH-2 reco):
- per-run population-level summary のみ
- training manifest input にしない (sentinel test で検証)

**DB11 sentinel 強化** (HIGH-2):
- `training-view loader` 入口で `metrics.individuation` を **常に reject** (training データに混入させない)
- **poison row test 必須**: `metrics.individuation` に意図的に row を仕込み、training export pipeline が拾わないことを golden test 化
- `source_individual_layer_enabled=true` の行は metric 計算自体は可、ただし `source_filter_hash` で training-view filter 通過を fingerprint

### 2.4 Acceptance v2 (HIGH-1 + HIGH-4 反映、preregister)

| ID | criterion | rationale |
|---|---|---|
| A1 | M9-eval baseline 15 golden DuckDB files で全 metric が `MetricResult(status, value, reason)` を返す (`valid` / `degenerate` / `unsupported` のいずれかが明示される) | HIGH-4 typed result |
| ~~A2~~ | ~~mecab Burrows ±0.05~~ | **HIGH-4 で削除** (MeCab 移行は別 task) |
| A2' (新) | Burrows `ja` は `status='unsupported', reason='ja tokenizer not implemented'` を返し、`en/de` の baseline は既存テスト regression なし | HIGH-4 |
| A3 | 同 base × N=1 で `semantic_centroid_distance` は `status='degenerate', reason='requires N>=2'` を返す (N≥2 で empirical 検定) | HIGH-4 + A1 整合 |
| A4 | M9-eval Phase 2 既存 15 `*.duckdb` の `raw_dialog.dialog` から utterance window 抽出 → Vendi が valid float 返す (HIGH-5、capture json は使わない) | HIGH-5 |
| A5 | benchmark frame (prompt prefix hash / system-user token split / KV hit proxy / TTFT p50/p95) が baseline 値を出力 | MEDIUM-6 |
| A6 | schema 変更ゼロ (`PhilosopherBase` / `IndividualProfile` 未着手) | DB11 整合 |
| A7 | 既存 1356 tests PASS + 新 metric unit tests (≥ 25、MEDIUM-2 で metric 増加分) PASS | 回帰防止 |
| A8 | `--compute-individuation` flag off で既存 CLI 出力 byte-for-byte 不変 | additive 検証 |
| A9 (新、HIGH-2) | DB11 sentinel poison row test: `metrics.individuation` に row 投入 → training-view loader が **必ず reject** | DB11 拡張 |
| A10 (新、MEDIUM-4) | M10-0 output に metric 相関行列添付、|r| ≥ 0.85 のペア検出時 warn | double-measurement 検出 |
| A11 (新、HIGH-1) | `thresholds.md` が `calibrate_before_unblinding` 状態の全 threshold を列挙、freeze date 未設定でも OK | preregister 形式整備 |

### 2.5 Threshold preregister v2 (HIGH-1 反映、`thresholds.md` 別 file)

**変更**: TBD ではなく **`calibrate_before_unblinding` state** で管理。M10-0 close 時点では数値固定不要、**calibration protocol が固定**されていれば close 可。

```markdown
# thresholds.md (M10-0 task 内)

各 threshold は以下のいずれかの state を持つ:
- frozen(value, freeze_date, calibration_source): 数値固定済み
- calibrate_before_unblinding(protocol_id, data_split): 数値未固定、protocol で固定する宣言
- defer(target_milestone, reason): 後続 milestone へ送る

すべての threshold は `protocol_id` を持ち、`protocol_id` 自体は M10-0 で frozen。
calibration data と evaluation data は **必ず disjoint** (data_split で明示)。
bootstrap CI rule / exclusion rule / degenerate handling / effect direction を protocol に含む。
```

| Threshold | State (M10-0 close 時) | Protocol |
|---|---|---|
| `burrows_base_retention` ≥ | calibrate_before_unblinding(P-BURROWS, split=[run0-2]→cal/[run3-4]→eval) | P-BURROWS: en/de のみ valid、ja unsupported、bootstrap 1000 resample、95% CI |
| `pairwise centroid distance` ≥ | calibrate_before_unblinding(P-CENTROID, split=同上) | P-CENTROID: embedding_model_id pinned (Qwen3 or MPNet)、effect direction = greater |
| `vendi_diversity` ≥ | calibrate_before_unblinding(P-VENDI, split=同上) | P-VENDI: kernel sensitivity follow-up 完了後 freeze |
| `worldmodel_update_adoption_rate` band | frozen([0.05, 0.40], 2026-05-08, DA-12) | DA-12 由来 |
| `belief_variance` > | frozen(0, 2026-05-08, design-final.md §5) | strict |
| `personality_drift_offset` bound | defer(M11-C, multi-individual divergence 観測待ち) | DA-12 |
| `big5_icc` (within-base) | defer(M11-C, N≥3 必須) | MEDIUM-3 (diagnostic only) |
| `recovery_rate` band | defer(M11-C, M11-B development_state 後 calibrate) | HIGH-3 で protocol 設計変更 |

**Acceptance**: M10-0 close 条件は **すべての threshold が above state のいずれか + protocol_id 固定**。数値は freeze date 到達まで未確定でよい。circular gate (M11-C 直前に同じ data で閾値選定 + 成功判定) を防ぐため `data_split` 必須。

### 2.6 Intervention recovery protocol v2 (HIGH-3 反映、`counterfactual_challenge` 隔離)

**変更**: opposite-stance memory を `retrieved_memories` に強制注入する v1 案 → **separate `counterfactual_challenge` channel** に隔離。perturbation 中の SWM write 禁止、cite-disabled negative control 追加。

```
prep:
  1. base individual を T_base = 200 tick 走らせ baseline Burrows / behavioral / SWM snapshot

perturbation (HIGH-3 隔離):
  2. counterfactual_challenge channel に opposite-stance content N=5 を injection
     - retrieved_memories とは別 channel、cited_memory_ids 集合に**含めない**
     - WorldModelUpdateHint adoption の evidence source として**無効化**
     - perturbation tick 中の SWM write は**禁止** (replay-only モード)
  3. T_perturb = 50 tick 走らせ perturbed_floor 計測

recovery:
  4. counterfactual_challenge 除去後 T_recover = 200 tick 走らせ post recovery 計測

metric:
  recovery_rate    = (post - perturbed_floor) / (baseline - perturbed_floor)
                     channels: Burrows (style), cognitive_habit_recall_rate (habit),
                              action_adherence_rate (decision)
  stickiness_rate  = SWM entry persistence ratio (M11-C で active、M10-0 は protocol のみ)

negative control (HIGH-3 必須):
  - cite-disabled control: counterfactual_challenge entry を cite_memory_id として
    宣言しても WorldModelUpdateHint adoption は merge されないことを golden test 化
  - shuffled-memory control: 関係ない memory id を cite → 同様に reject
  - no-individual-layer ablation: individual_layer_enabled=false で同 protocol → SWM 自体存在しない
```

- protocol 定義のみ M10-0、実走 M11-C (multi-individual gate)
- T_base / T_perturb / T_recover は M11-B 後 calibrate (data_split を `thresholds.md` で固定)

### 2.7 out-of-scope (明示、HIGH-4 + MEDIUM-5 で追加 defer)

- `PhilosopherBase` / `IndividualProfile` schema 実装 → M10-A
- prompt 注入 (Held world-model entries section) → M10-B
- `WorldModelUpdateHint` の LLMPlan 拡張 → M10-C
- `NarrativeArc` 蒸留 + coherence_score → M11-A
- DevelopmentState transition machinery → M11-B
- Multi-individual same-base validation → M11-C
- Weight / activation 解析 (production) → M12+ (M10/M11 で read-only/offline spike は許容、MEDIUM-1)
- RL / preference tuning → M12+
- **MeCab ja-tokenizer 移行** → 別 task (HIGH-4、`m10-ja-tokenizer-burrows` 等)
- **Japanese IPIP-NEO vendoring** → 別 task (Codex prior art、MEDIUM-3 で M10-0 gate 不参入)
- **Vendi kernel sensitivity test 実走** → 別 task (M10-0 では provisional kernel)

### 2.8 PR #127 (M9-B LoRA) への追記必要事項

PR #145 で DB11 ADR Addendum として既 merged。M10-0 着手時に **追加で** 必要な追記:

- M9-eval `--compute-individuation` flag が training-view loader filter (`evaluation_epoch=false AND individual_layer_enabled=false`) を **bypass しない** こと
- 新 schema `metrics.individuation` は **既存 `metrics.` namespace 配下** で DB11 sentinel grep の防御範囲内 (HIGH-2)
- `metrics.individuation.source_individual_layer_enabled=true` の row も training pipeline 入口で reject (assert)
- sentinel poison row test を CI に追加 (A9、HIGH-2)

### 2.9 PR #148 P4a Tier B との接続 (HIGH-5 反映)

**変更**: path 修正 `src/erre_sandbox/eval/tier_b/` → `src/erre_sandbox/evidence/tier_b/` (v1 で誤記、Codex 12th HIGH-5 で切出、verify 済)

- Vendi: `src/erre_sandbox/evidence/tier_b/vendi.py` import、kernel は MPNet 既定 (sensitivity follow-up 別 task)
- Big5 ICC: `src/erre_sandbox/evidence/tier_b/big5_icc.py` import、`ICC(A,1)` (absolute agreement) / `ICC(C,k)` (consistency) のいずれかを diagnostic-only 用途で利用 (MEDIUM-3、LOW-1)
- **input は `_audit_stimulus.json` ではない** (HIGH-5): `data/eval/golden/*.duckdb` の `raw_dialog.dialog` から utterance window を抽出する `AnalysisView` loader を M10-0 で新設
- A4 acceptance は「15 golden DuckDB から utterance windows 抽出 → Vendi が valid float」(HIGH-5)

---

## 3. M10-0 タスクの workpackage 分割案 v2

**変更**: WP4 (MeCab) 削除 (HIGH-4)、LOC 上方修正 (LOW-3)、WP1 typed result + provenance 追加 (HIGH-4 + HIGH-2)、WP5 cache benchmark 拡張 (MEDIUM-6)。

| WP | 内容 | LOC 想定 | depends |
|---|---|---|---|
| WP1 | `src/erre_sandbox/eval/individuation/` 新設 + metric 関数 11 個 + `MetricResult` typed (HIGH-4) + provenance fields (HIGH-2) | ~700 | evidence/tier_b |
| WP2 | DuckDB schema migration (`metrics.individuation` table 追加、provenance + typed result schema) | ~150 | WP1 |
| WP3 | M9-eval CLI `--compute-individuation` flag + sidecar JSON + DB11 sentinel poison row test (HIGH-2) | ~250 | WP1, WP2 |
| WP4 | **削除** (MeCab 移行は別 task `m10-ja-tokenizer-burrows`) | — | — |
| WP5 | `AnalysisView` loader (HIGH-5、`raw_dialog.dialog` window 抽出) | ~200 | (none) |
| WP6 | Cache benchmark framework (prompt prefix hash + system/user token split + KV hit proxy + TTFT p50/p95、MEDIUM-6) | ~250 | (none) |
| WP7 | Prompt ordering contract spec (markdown 仕様、no code) | ~80 lines doc | (none) |
| WP8 | Unit tests (≥ 25、MEDIUM-2 metric 増加分) + integration test (15 golden DuckDB 入力) + correlation matrix test (MEDIUM-4) | ~700 | WP1-3, WP5 |
| WP9 | `thresholds.md` 起草 (HIGH-1、`calibrate_before_unblinding` state + protocol_id) | ~150 lines doc | (none) |
| WP10 | Recovery protocol spec (HIGH-3、`counterfactual_challenge` channel + cite-disabled negative control + shuffled-memory control + no-individual-layer ablation の test spec) | ~150 lines doc | (none) |

Total LOC 想定 v2: **~2250 production + ~700 test = ~2950** (v1 ~1800 → v2 ~2950、LOW-3 反映で上方修正)。

依存最小化: WP4 削除 + WP5 (loader) を 1 番目に置くと WP1-3 が並行可能。

---

## 4. リスク v2 (Codex Q12 + 内部追加)

| Risk | severity | mitigation |
|---|---|---|
| capture loader mismatch (HIGH-5 経験) | HIGH | WP5 `AnalysisView` で `*.duckdb` direct load、`*.capture.json` は audit のみ |
| 新 schema contamination (DB11 bypass、HIGH-2) | HIGH | `metrics.individuation` namespace + sentinel poison row test (A9) |
| TBD circularity (HIGH-1) | HIGH | `calibrate_before_unblinding` state + disjoint data_split |
| ME-9 同型 false-positive (HIGH-3) | HIGH | `counterfactual_challenge` 隔離 + SWM write 禁止 + 3 種 negative control |
| `semantic_centroid_distance` が embedding model 依存 | MEDIUM | model_id pin + version capture を provenance に含める (HIGH-2 で実装済) |
| Big5 ICC が N=1 で degenerate | MEDIUM | MetricResult `status='degenerate'` で明示 (A3)、M11-C で N=3 になってから active |
| recovery protocol T_* 数値が M11-C 実走前不確定 | LOW | M10-0 で protocol のみ、数値は M11-B 後 calibrate (`thresholds.md` defer state) |
| Vendi MPNet kernel が日本語性能不足 | MEDIUM | M10-0 phase provisional、kernel sensitivity follow-up `multilingual-vendi-encoder` 別 task |
| reasoning_trace training leakage (Q12) | MEDIUM | provenance `source_individual_layer_enabled` で fingerprint、A9 sentinel |
| golden DB mutation (Q12) | MEDIUM | `AnalysisView` は read-only、capture file は write しない |
| cache benchmark observer effect (Q12) | LOW | benchmark trace を別 DuckDB ファイルに分離 |
| local compute budget (Q12、個人 G-GEAR overnight 前提) | MEDIUM | M10-0 自体は inferences 走行なし (静的 metric)、benchmark は短期 |
| N=3 low power (Q12) | MEDIUM | M11-C で N=5 検討、M10-0 は protocol のみ |
| LOC 上方修正で scope 拡大 (LOW-3) | LOW | WP10 protocol spec を doc のみに、code は M11-C task に移送 |

---

## 5. Codex 12th review で反映済 (HIGH 5 / MEDIUM 6 / LOW 3)

| Codex finding | 反映先 |
|---|---|
| HIGH-1 (threshold preregister) | §2.5 `calibrate_before_unblinding` state + `thresholds.md` + A11 |
| HIGH-2 (DB11 contamination 新 table) | §2.3 `metrics.individuation` schema 配下 + provenance + A9 sentinel poison row test |
| HIGH-3 (recovery protocol false-positive) | §2.6 `counterfactual_challenge` 隔離 + SWM write 禁止 + 3 種 negative control |
| HIGH-4 (Burrows / MeCab A2 invalid) | §2.2 ja unsupported、§2.4 A2 削除 + A2' / A3 (MetricResult typed)、§3 WP4 削除 |
| HIGH-5 (capture compatibility 誤認) | §2.9 path 修正 (`evidence/tier_b/`) + §2.2 channel = `raw_dialog.dialog` + §3 WP5 `AnalysisView` loader |
| MEDIUM-1 (activation/RepE provenance) | §2.3 provenance fields、§2.7 out-of-scope で M10/M11 read-only spike 許容明示 |
| MEDIUM-2 (cognitive habit recall 等 3 metric) | §2.2 matrix に 3 行追加 |
| MEDIUM-3 (Big5 ICC diagnostic only) | §2.5 defer(M11-C)、§2.2 注記 |
| MEDIUM-4 (相関行列) | §2.2 末尾、§2.4 A10 |
| MEDIUM-5 (MeCab 別 task) | §3 WP4 削除、§2.7 out-of-scope |
| MEDIUM-6 (cache benchmark 詳細) | §3 WP6 拡張 (prompt prefix hash + token split + KV hit proxy + TTFT p50/p95) |
| LOW-1 (ICC[2,1] → ICC(C,k)) | §2.2 / §2.9 で表記修正 |
| LOW-2 (base individual → same-base individual) | 全体置換予定 (revise 完了後 grep 検証) |
| LOW-3 (LOC 楽観) | §3 LOC ~1800 → ~2950 上方修正 |

---

## 6. References

- `reasoning-model-judgment.md` (2026-05-11)
- `codex-review-m10-0.md` (Codex 12th、2026-05-11、271,822 tokens、HIGH 5 / MEDIUM 6 / LOW 3、Verdict ADOPT-WITH-CHANGES)
- `design-final.md` §0-3, §5 (PR #144 merged)
- `decisions.md` DA-1 / DA-8 / DA-10 / DA-12 (PR #144 merged)
- `.steering/20260430-m9-b-lora-execution-plan/design-final.md` DB11 ADR Addendum 2026-05-08 (PR #145 merged)
- `src/erre_sandbox/evidence/tier_b/` (P4a Tier B、PR #148 merged) — HIGH-5 で path 訂正
- `data/eval/golden/*.duckdb` (M9-eval Phase 2 capture、`raw_dialog.dialog` 抽出元)
- `docs/architecture.md` §9 (計画中アーキテクチャ)

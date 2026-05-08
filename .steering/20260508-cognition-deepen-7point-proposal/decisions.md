# Decisions — 認知深化 7-point 提案 ADR (3-source synthesis 後 final)

> 各 decision は (1) Claude initial / (2) User clarification / (3) reimagine / (4) Codex
> review の 4 入力を統合した最終判断。`Final` 列が単一の決定。

## DA-1: ERRE thesis の operational re-articulation

| 入力 | 案 |
|---|---|
| Claude initial | thesis は手付かず、提案 7 を DEFER で対応 |
| User clarification | "完全な人間として構築" (極端、scope 無限化リスク) |
| reimagine | persona identity 維持、growth_axes で深まる方向のみ (極端、新個体性を否定) |
| Codex HIGH-1 | 中道: "歴史的認知習慣を immutable substrate とする、観測可能に発達する人工個体" |

**Final**: Codex 案を採用。functional-design.md §1 の thesis 文言は変更せず、
**operational re-articulation** を design-final.md §0 に明記し、後続 milestone の
acceptance に "base fidelity" と "individual divergence" を **別 metric** として
preregister する (Codex HIGH-1 + HIGH-4)。

**根拠**: User vision の "新個体" は維持しつつ、reimagine の "identity 希釈危険" を
防ぐには、 drift 許容領域を **明示的に分割** する必要がある。`cognitive_habits` /
LoRA / `persona_id` を drift 禁止に置き、Individual layer は world model / belief /
narrative のみで発達する境界条件を強制する。

## DA-2: 提案 1 SubjectiveWorldModel — ADOPT-WITH-CHANGES

| 入力 | 案 |
|---|---|
| Claude initial | ADOPT in memory layer |
| User clarification | ADOPT as AgentState 第一級 property |
| reimagine | StanceVector 5-axis として独立再発見 |
| Codex | ADOPT-WITH-CHANGES、bounded 形に限定 |

**Final**: `IndividualProfile.world_model: SubjectiveWorldModel` として 第一級 property、
5-axis (env / concept / self / norm / temporal) × bounded entries 50/individual 上限、
`WorldModelEntry` ごとに `cited_memory_ids ≥ 1` 必須。

**Defer**: axis 集合の最終決定は M10-A scaffold 時に再評価可能 (現行は best-guess、
empirical 観測後に rebalance)。

## DA-3: 提案 2 prompt 注入 — ADOPT-WITH-CHANGES

| 入力 | 案 |
|---|---|
| Claude initial | ADOPT、user prompt 側、token bound 200 |
| reimagine | user prompt 側の memories 直後 section、80 tokens |
| Codex HIGH-6 | system prompt = `_COMMON_PREFIX` + immutable PhilosopherBase + state tail、
                  Individual は user prompt 側 bounded top-K |

**Final**: Codex 案を採用。prompt ordering contract を M10-0 で確定。SGLang RadixAttention
共有 prefix を **PhilosopherBase block まで拡大** (cache 効果向上)。M10-A acceptance に
`cache hit rate / TTFT / prompt token 増分` を含める。

## DA-4: 提案 3 LLMPlan world_model_update — ADOPT-WITH-CHANGES (free-form 禁止)

| 入力 | 案 |
|---|---|
| Claude initial | MODIFY、bounded primitive (topic_focus_shift 等) |
| User clarification | Individual 側で bounded 維持 |
| reimagine | StanceShiftHint + `cited_memory_ids` 必須 |
| Codex HIGH-2 | `WorldModelUpdateHint` + cited_memory_ids 必須、Python が verify |

**Final**: `WorldModelUpdateHint(axis, key, direction, cited_memory_ids)` として LLMPlan に
additive 追加。`direction: Literal["strengthen", "weaken", "no_change"]` の 3 値で free-form
禁止。Python が `cited_memory_ids ⊆ retrieved_memories` を検証してから merge。

**Reject path**: free-form `world_model_update: dict` 案は ME-9 incident 同型 (LLM 自己宣言
で内部状態が動く) のため不採用。

## DA-5: 提案 4 Python 側で安全に merge — ADOPT (pattern 流用)

| 入力 | 案 |
|---|---|
| Claude initial | ADOPT、belief.py pattern 流用 |
| reimagine | apply_stance_shift_hint() pure function |
| Codex | ADOPT |

**Final**: `cognition/belief.py:maybe_promote_belief` の pure-function + threshold-based +
layer-boundary-preserving pattern を以下 3 関数に踏襲:
- `apply_world_model_update_hint(swm, hint, retrieved_memories) -> SubjectiveWorldModel | None`
- `synthesize_narrative_arc(semantic_memory, swm) -> NarrativeArc | None`
- `maybe_advance_development(profile, evidence) -> DevelopmentState | None`

すべて pure、caller (bootstrap or cognition cycle) が persistence の owner。

## DA-6: 提案 5 NarrativeSelf 周期生成 — DEFER/MODIFY

| 入力 | 案 |
|---|---|
| Claude initial | ADOPT、M11-A defer |
| User clarification | M10-B 同期 (個体連続性に必須) |
| reimagine | NarrativeArc (structured trajectory、prose 否) + coherence_score |
| Codex | DEFER/MODIFY、prose ではなく Arc + coherence diagnostic |

**Final**: M11-A で `NarrativeArc` (structured) + `coherence_score` (diagnostic only) を
投入。**Free-form prose 化は M12+ defer** (token cost、role-play 増幅 risk、stage
transition 駆動には false-positive rate 計測後)。

**User clarification "M10-B 同期" は撤回**: Codex は cache 戦略 + scope 集中の観点から
M11-A defer を強く推奨。Individual 連続性は SWM だけで M10-B 段階は十分 (NarrativeArc は
"豊かさ" 追加であって連続性の必須ではない)。

## DA-7: 提案 6 DevelopmentState — REVISE (S1-S3 + hidden maturity score)

| 入力 | 案 |
|---|---|
| Claude initial | REJECT standalone、shuhari_stage 拡張 |
| User clarification | ADOPT、S1-S5 lifecycle で完全な人間化 |
| reimagine | REJECT、ShuhariStage 拡張で代替 |
| Codex HIGH-5 | REVISE、S1-S3 に縮小 or hidden maturity score の view |

**Final**: `DevelopmentState(stage: S1_seed/S2_exploring/S3_consolidated, maturity_score:
[0,1])` として ADOPT、ただし **S4/S5 は M12+ research gate**。

`shuhari_stage` (base 側技能習得) と DevelopmentState (Individual 側 lifecycle) は **意味
を分けて両立**:
- shuhari_stage: 「Kant の歩行を どこまで内化したか」(技能習得)
- development_state: 「個体が どこまで個別化したか」(lifecycle)

axis 直交を docstring に明記、両者の混同を防止。

**S5_late (老化 analog) は撤回**: Codex LOW-2 より `confidence saturation` で代替。

**User vision との差分**: "完全な人間として" 5 stages → 3 stages + hidden score。
M11-B 経験で S4 が必要と empirically 判明したら M12+ で追加検討。

## DA-8: 提案 7 philosopher_seed refactor — ADOPT-WITH-CHANGES (rename しない)

| 入力 | 案 |
|---|---|
| Claude initial | DEFER M11+ (M9 trunk 破壊リスク) |
| User clarification | ADOPT、二層分離 |
| reimagine | REJECT、persona 維持 + growth_axes |
| Codex | ADOPT-WITH-CHANGES、conceptual two-layer は採用、M9 trunk 完了まで rename / export 混入禁止 |

**Final**: 二層 conceptual refactor を採用 (User vision)、ただし以下の制約 (Codex HIGH-3):

1. `personas/*.yaml` の rename **しない** (schema_version 0.10.0-m7h 維持、3 persona しか
   ないが M9 trunk 中の churn を避ける)
2. `PersonaSpec` (schemas.py) に loader wrapper を追加 → `PhilosopherBase` として読める
3. M9-B LoRA training には Individual layer enabled run **混入禁止** (PR #127 design-final.md
   に base-only manifest と exclusion rule を追記)
4. M10-A scaffold は feature flag default off で並行可、ただし training/raw_dialog export
   への流入は M9-B baseline 後のみ

**Naming**: `philosopher_seed` という新名は使わず、**immutable PhilosopherBase + mutable
IndividualProfile** で機能を表現。User の "philosopher_seed" は意図 (= seed としての
位置づけ) を反映するが、命名としては reimagine の指摘通り Extract pipeline の意味を
弱める。Codex LOW-1 も "完全な人間" を外向け表現から外すよう推奨。

## DA-9: reimagine 8 missing items の選別 (Codex Q5 反映)

| Item | 採否 | 配置 |
|---|---|---|
| `cited_memory_ids` 必須 | **ADOPT 必須** | DA-2 / DA-4 / DA-5 / DA-7 全体 |
| dyadic vs class-wise axis 直交 | **ADOPT 必須** | belief_kind (dyadic) と SWM `axis` (class) を docstring + golden test で強制 |
| `coherence_score` metric | ADOPT-WITH-CHANGES | M11-A diagnostic only、hard gate は M11-B で false-positive 後 |
| RadixAttention KV cache 保護 | **ADOPT 必須** | DA-3、M10-0 contract |
| `decay_half_life` | ADOPT-WITH-CHANGES (Codex MEDIUM-3) | world_model のみ、base / LoRA に適用しない |
| `growth_axes.permitted/forbidden` | REJECT | User vision (Option A) と矛盾。Individual layer の divergence は別 schema (`personality_drift_offset` 等) で表現 |
| 定量 acceptance per milestone | **ADOPT 必須** | design-final.md §5 |
| M9 trunk 隔離 gate | **ADOPT 必須** | DA-8 + design-final.md §3 M9-freeze |

## DA-10: Burrows ratio の役割再定義 (Codex HIGH-4)

**Final**: Burrows = **base style retention 専用**。multi-individual 同 base で同じ値が
出るのが成功条件。個体化測定は別 sidecar metrics (semantic centroid distance / belief
variance / NarrativeArc drift / Agent Identity Evals 型 perturbation recovery)。

M10-0 で sidecar metrics を実装してから M10-A scaffold に着手。

## DA-11: schema_version bump 戦略

**Final**: `0.10.0-m7h → 0.11.0-m10c` の minor bump を M10-C (LLMPlan に
WorldModelUpdateHint 追加) で実施。additive のみ、後方互換維持。`personas/*.yaml`
schema_version は M10 中変更しない (Codex MEDIUM-1)。

## DA-12: Open questions deferred (M10/M11 実装時に決着)

- `decay_half_life_ticks` の calibration (initial = 1000、M10-B simulation で tune)
- `WorldModelUpdateHint.adoption rate` 目標 band `[0.05, 0.40]` の根拠 (M10-C 後 empirical)
- `personality_drift_offset` の bounded 範囲 ±0.1 per axis (M11-C で multi-individual
  divergence 観測後)
- `coherence_score` の hard threshold (M11-B で false-positive rate 測定後)
- S4_articulation 必要性 (M11-B 経験後 M12+ で再評価)
- Burrows tokenizer 戦略 (mecab / char n-gram、M10-0 sidecar 実装時)

## DA-13: 採用しなかった代替案の記録

- **`philosopher_seed` 命名**: User clarification の意図は反映するが命名は不採用 (reimagine
  + Codex LOW-1 の指摘で Extract pipeline 意味を弱める懸念)
- **S1-S5 5 stages**: Codex HIGH-5 で falsifiability 不足、S1-S3 + hidden maturity score に
  縮小
- **NarrativeSelf を free-form prose で M10-B 同期**: User clarification の意図だが Codex
  scope 集中観点で M11-A diagnostic only に defer
- **growth_axes.permitted/forbidden** (reimagine): User vision (Option A、新個体) と矛盾、
  Individual layer の divergence は別 mechanism で表現
- **path B retirement / path C rebirth**: M12+ research gate (Codex Q2)、default は path A 不完成停滞
- **完全な人間として構築 (User 文言)**: 外向け表現として "persistent artificial individual"
  に置換 (Codex LOW-1)、内部 thesis re-articulation で operational に表現 (DA-1)

# Design Final — 認知深化 7-point 提案 (3-source synthesis)

> Plan→Clear→Execute ハンドオフ規則に従い、`/clear` 後でも独立に Read 可能な体裁で書く。
>
> 3 source 由来:
> - `design.md` (Claude initial Plan-mode 判定)
> - `design-clarified.md` (User clarification 反映の二層解釈)
> - `design-reimagine.md` (independent reimagine、Compression-Loop counter-proposal)
> - `codex-review.md` (Codex `gpt-5.5 xhigh` independent review、Verdict ADOPT-WITH-CHANGES、
>   HIGH 7 / MEDIUM 5 / LOW 3、197K tokens、prior art 9 件 web search 引用)
>
> User decision (2026-05-08): **Option A** (新個体 + 二層 + 完全な人間化方向)
> Codex stress-test 結果を反映して **ユーザー vision を維持しつつ HIGH 7 件すべて吸収**

## 0. Thesis re-articulation (Codex HIGH-1 反映、必須)

ERRE thesis (functional-design.md §1) を **operational に再表現**:

> 旧: 「歴史的偉人の認知習慣をローカル LLM エージェントとして再実装し、知的創発を観察」
>
> 新: 「**歴史的認知習慣を immutable substrate とする、観測可能に発達する人工個体**
>      を作り、その発達と original substrate の保存性を同時に測定する」

これにより:
- "歴史的偉人を作る" 過剰 claim を回避 (Codex LOW-1)
- "完全な人間として" の scope 無限化を回避 (Codex HIGH-7)
- "認知習慣の再実装" と "知的創発の観察" の thesis 内部緊張を **drift-禁止 + 発達-許可
  axis 直交** で解消

reimagine が指摘した「persona identity 希釈は thesis を破壊する」と user vision の
「新個体」を統合する解: **identity は base layer に閉じ込め、Individual layer は別 axis
で divergence する**。

### immutable / mutable boundary (Codex HIGH-1 mitigation)

| 層 | 対象 | drift 許容 | 由来 |
|---|---|---|---|
| **PhilosopherBase** | `persona_id` | NO | 一次史料 |
| | `cognitive_habits` (Kant の歩行/朝執筆等) | NO | Extract pipeline |
| | `default_sampling` (T/top_p/repeat_penalty) | NO | Reverify pipeline |
| | LoRA-trained style | NO | M9-B target、固定 |
| | `preferred_zones` | NO | persona-zone 関係 |
| **Individual** | `world_model` (5-axis subjective) | YES (decay & evidence-driven) | 個体の interaction |
| | `subjective_beliefs` | YES (cited_memory_ids 必須) | 観察 |
| | `narrative_arc` (≠ free-form prose) | YES (周期蒸留) | semantic memory |
| | `development_state` (S1-S3) | YES (indirect signal) | observable evidence |
| | `personality_drift_offset` (Big5 の bounded ±0.1 等) | YES (限定) | 蓄積 |

「**identity は drift しない、divergence は別 axis で起きる**」 — これが Option A の正統解釈。

## 1. 二層 architecture (final, Codex HIGH-1/HIGH-6 反映)

### 1.1 Schema

```python
# contracts/cognition_v0_11_0.py (新)

class PhilosopherBase(BaseModel):
    """Immutable inheritance from Extract/Reverify pipeline.
    M9-B LoRA は本層を学習する。Individual layer の影響を一切受けない。"""
    model_config = ConfigDict(extra="forbid", frozen=True)
    persona_id: str                            # kant / rikyu / nietzsche
    display_name: str
    era: str
    cognitive_habits: list[CognitiveHabit]     # 既存 personas/*.yaml 流用
    default_sampling: SamplingParam
    preferred_zones: list[Zone]
    primary_corpus_refs: list[str]
    lora_adapter_id: str | None = None         # M9-B 後に注入

class IndividualProfile(BaseModel):            # Codex LOW-3: Individual → IndividualProfile
    """Mutable runtime individual built on top of an immutable PhilosopherBase."""
    model_config = ConfigDict(extra="forbid")
    individual_id: str                         # uuid (= agent_id と直結しない、Codex LOW-3)
    base_persona_id: str                       # PhilosopherBase reference
    world_model: SubjectiveWorldModel          # 提案 1
    development_state: DevelopmentState        # 提案 6 (REVISE: S1-S3)
    narrative_arc: NarrativeArc | None = None  # 提案 5 (DEFER/MODIFY: prose ではなく Arc)
    personality_drift_offset: PersonalityDrift # bounded ±0.1 per axis、cited evidence 駆動

class SubjectiveWorldModel(BaseModel):
    """5-axis bounded world view. AgentState 第一級 property (User clarification)。
    各 entry は cited_memory_ids 必須 (Codex HIGH-2)。"""
    model_config = ConfigDict(extra="forbid")
    entries: list[WorldModelEntry]             # bounded、上限 50/individual

class WorldModelEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    axis: Literal["env", "concept", "self", "norm", "temporal"]
    key: str                                   # axis 内の固有 key (e.g. "peripatos", "categorical_imperative")
    value: float = Field(ge=-1.0, le=1.0)      # signed
    confidence: float = Field(ge=0.0, le=1.0)
    cited_memory_ids: list[str]                # ≥ 1 必須 (Codex HIGH-2)
    last_updated_tick: int
    decay_half_life_ticks: int = 1000          # Codex MEDIUM-3、world_model のみ適用

class DevelopmentState(BaseModel):
    """S1-S3 のみ (Codex HIGH-5)。S4/S5 は M12+ で empirical evidence 後再評価。"""
    model_config = ConfigDict(extra="forbid")
    stage: Literal["S1_seed", "S2_exploring", "S3_consolidated"]
    maturity_score: float = Field(ge=0.0, le=1.0)  # hidden continuous score、stage は view
    transition_evidence: dict[str, int]        # observable evidence count per stage
    # 段間遷移は Python indirect signal のみ (Codex HIGH-2、Q7)

class NarrativeArc(BaseModel):
    """Structured trajectory (prose ではない、Codex 提案 5 DEFER/MODIFY)。
    coherence_score は M11-A では diagnostic のみ (Codex MEDIUM-4)。"""
    model_config = ConfigDict(extra="forbid")
    synthesized_at_tick: int
    arc_segments: list[ArcSegment]             # ≤ 5 segments
    coherence_score: float                     # diagnostic only initially
    last_episodic_pointer: str

class WorldModelUpdateHint(BaseModel):         # Codex HIGH-2: free-form 禁止、bounded primitive
    """LLM が world model 更新を要望する bounded primitive。
    LLM = candidate、Python = state transition (Codex Q7)。"""
    model_config = ConfigDict(extra="forbid")
    axis: Literal["env", "concept", "self", "norm", "temporal"]
    key: str
    direction: Literal["strengthen", "weaken", "no_change"]
    cited_memory_ids: list[str]                # ≥ 1 必須、retrieved_memories 内に集合包含
```

### 1.2 LLMPlan 拡張 (additive、minor schema bump、Codex HIGH-2 反映)

```python
# cognition/parse.py の LLMPlan に追加 (M10-C で投入)
world_model_update_hint: WorldModelUpdateHint | None = Field(default=None, ...)
```

`extra="forbid", frozen=True` 維持、後方互換 (default None)。

### 1.3 prompt 構造 (Codex HIGH-6 反映、cache-safe)

```
SYSTEM PROMPT:
  _COMMON_PREFIX (既存、絶対不変、SGLang RadixAttention 共有)
    ↓
  PhilosopherBase block (immutable per persona_id、cache 共有可)
    ↓
  current state tail (tick / zone / erre_mode / physical / cognitive、既存)

USER PROMPT:
  Recent observations (既存)
    ↓
  Relevant memories (既存、ただし memory id を出力するよう Codex MEDIUM-2 反映)
    ↓
  Held world-model entries (新、bounded top-K、上限 80 tokens)  ← Individual side
    ↓
  RESPONSE_SCHEMA_HINT (既存 + WorldModelUpdateHint section 追加)
```

**Cache 戦略**: System prompt は base persona ごとに reusable。Individual 部分は user
prompt 側の bounded top-K に閉じる。M10-A acceptance に **cache hit rate / TTFT /
prompt token 増分** を入れる (Codex HIGH-6 mitigation)。

### 1.4 LLM 自己宣言 pattern 排除 (Codex HIGH-2 + Q7、不可侵原則)

| 内部状態変化 | 駆動 source |
|---|---|
| `WorldModelUpdateHint` 採用 | Python が `cited_memory_ids` を retrieved_memories と集合検証 + threshold |
| `subjective_belief` (`belief_kind`) 昇格 | 既存 M7δ pattern (affinity 飽和 indirect signal) |
| `personality_drift_offset` 更新 | 反復観察 N 回 + statistical stability、LLM 申告では発火しない |
| `narrative_arc` 蒸留 | chashitsu reflection trigger (既存) + memory volume threshold |
| `coherence_score` 計算 | 発話 embedding と SWM cosine sim (Python pure) |
| `development_state.stage` 遷移 | maturity_score (= memory volume + coherence + belief stability の AND) + 最低 tick + cooldown + regression 禁止 |

**境界線 (Codex Q7)**: LLM は **候補提示**、Python は **state transition**。narrative
prose は LLM 生成可、stage advance / personality drift / belief promotion は observable
evidence のみ。

## 2. M9 trunk との接続 (Codex HIGH-3 mitigation、最重要)

### 2.1 M9-B LoRA contamination 防止

PR #127 (`.steering/20260430-m9-b-lora-execution-plan/`) design-final.md に **追記必須**:

- **dataset manifest**: `individual_layer_enabled=false` の base-only run のみ training data
- **exclusion rule**: M10-A 以降 scaffold が enable された tick の dialog_turn は training
  export から自動除外
- **flag check**: training pipeline 入口で `dataset.metadata.individual_layer_enabled == false`
  を assert

### 2.2 M9-eval Burrows ratio の役割再定義 (Codex HIGH-4)

| 用途 | metric |
|---|---|
| **base style retention** | Burrows ratio (現行のまま) |
| **個体化 divergence** | semantic centroid distance (sentence embedding) |
| | belief variance across same-base individuals |
| | NarrativeArc coherence/drift |
| | world_model entry overlap (Jaccard) |
| | Agent Identity Evals 型 perturbation recovery (Codex prior art) |

multi-individual 同 base で **Burrows が同じ値** = base 保持成功 (失敗ではない)。
個体化は別 sidecar metrics で測る。

### 2.3 Codex MEDIUM-5: Japanese utterance + Burrows tokenizer

現行 Burrows 実装は `ja` tokenizer 未対応。M10-0 タスクで M9-eval sidecar に **対象 channel
明示** (utterance vs reasoning trace) と **tokenizer 戦略** (mecab? char n-gram?) を定義。

## 3. 改訂 phasing (Codex 7 HIGH 反映、final)

```
[M9-freeze] (UNTOUCHED 継続、in-flight)
  - run1 calibration (G-GEAR)
  - M9-eval Phase 2 完了
  - M9-B LoRA execution: base-only dataset で実行 (HIGH-3 反映、PR #127 追記)
  - M9-eval Phase 2 vs LoRA 比較 baseline 確立
  ↓ M9 完全終了 後に M10 cognition wiring 着手可

[M10-0] Pre-flight (Codex HIGH-7、HIGH-3、HIGH-4 mitigation)
  - 個体化 metric 定義 + sidecar 実装 (semantic distance / belief variance / narrative drift)
  - dataset manifest 仕様確定 (`individual_layer_enabled` flag)
  - cache benchmark 枠組み (cache hit rate / TTFT / token delta)
  - prompt ordering contract (COMMON → base → state → user-bounded-top-K)
  - acceptance: 既存 baseline で metric が動くこと、benchmark が走ること
  - 影響範囲: M9-eval sidecar 拡張、PR #127 design-final.md 追記
  - **schema 変更なし**

[M10-A] Two-layer schema scaffold (Codex Q3、feature flag default off)
  - PhilosopherBase / IndividualProfile / SubjectiveWorldModel / DevelopmentState
    Pydantic schema を contracts/cognition_v0_11_0.py に新設
  - personas/*.yaml の rename はせず loader wrapper で `PersonaSpec` を `PhilosopherBase`
    として読む (Codex MEDIUM-1)
  - feature flag `cognition.individual_layer.enabled = false` (default off)
  - acceptance: 既存 1318 tests PASS、新 schema golden test、wrapper 互換確認
  - **cognition wiring なし** (read-write path 未配線)

[M10-B] Read-only SWM synthesis + prompt 注入 (Codex HIGH-6 cache-safe)
  - SWM 周期蒸留 (semantic_memory + RelationshipBond → SWM bounded top-K)
  - user prompt に Held world-model entries section 追加
  - LLMPlan は **未変更** (cache hit と base fidelity を測る)
  - acceptance: cache hit rate ≥ 80% baseline、TTFT ≤ +5%、prompt token +200 以内
  - acceptance: persona 別 SWM が異なる軸で強くなる (個体化 metric で empirical)

[M10-C] Bounded WorldModelUpdateHint (Codex HIGH-2 反映)
  - LLMPlan に `world_model_update_hint: WorldModelUpdateHint | None = None` 追加
  - apply_world_model_update_hint() pure function (cited_memory_ids verify)
  - acceptance: golden test 「LLM が free-form belief 主張しても採用されない」
  - acceptance: adoption rate measure (高すぎ = pickup 緩い、低すぎ = LLM が cite 諦め)
  - schema_version 0.10.0-m7h → 0.11.0-m10c minor bump (additive)

[M11-A] NarrativeArc + coherence_score (diagnostic only、Codex MEDIUM-4)
  - chashitsu reflection 拡張で synthesize_narrative_arc()
  - coherence_score 計測 (発話 embedding と SWM cosine sim)
  - **stage transition には未使用** (false-positive rate 測定後 M11-B で評価)
  - acceptance: low coherence で深い reflection 発火、prose 化はまだ defer

[M11-B] DevelopmentState transition machinery (S1-S3 のみ、Codex HIGH-5)
  - maybe_advance_development() pure function (Python indirect signal)
  - 遷移 trigger: maturity_score ≥ 段ごと閾値 + 最低 tick + cooldown + regression 禁止
  - 各 stage の sampling / memory / reflection 数値差を **preregister**
  - negative-control 条件: stage 操作 stripped run vs full run の divergence 比較
  - acceptance: 1 individual を 1000-tick 走らせ S1→S2→S3 の遷移が observable evidence
    駆動で発火 (LLM 自己申告では発火しない)

[M11-C] Multi-individual 同 base validation (Codex HIGH-4 反映)
  - 3 IndividualProfile を同 PhilosopherBase (kant) から起動
  - Burrows = base retention ≥ 0.6 (= 同じ値 = 成功)
  - sidecar metrics で個体化 ≥ threshold (semantic centroid pairwise distance、belief variance、
    NarrativeArc 差異)
  - acceptance: 「base 保持 + 個体化分離」が同時成立する empirical evidence

[M12+ research re-evaluation gate]
  - S4_articulation / S5_late stage 検討 (M11-B 経験を踏まえ first principles で必要性
    判断、Codex HIGH-5 抑制)
  - retirement / rebirth (path B / C 検討、Codex Q2 default = A 不完成停滞)
  - multi-base society (kant + rikyu + nietzsche × 各 N individuals)
  - individual layer の LoRA 適用判定 (Codex HIGH-3 後継)
  - 上記いずれも先に decision 固定しない、empirical gate
```

## 4. 既存資産への影響 (rename / migration)

| 対象 | 改修種別 | timing |
|---|---|---|
| `personas/*.yaml` | rename **しない**、schema_version 0.10.0-m7h 維持 (Codex MEDIUM-1) | M10 中触らない |
| `PersonaSpec` (schemas.py) | wrapper を追加 → `PhilosopherBase` として読める (Codex MEDIUM-1) | M10-A |
| `AgentState.persona_id` | base reference の getter 維持で互換 | M10-A |
| `AgentState.shuhari_stage` | 既存維持。意味は **base 側技能習得** に限定 (lifecycle は Individual 側 DevelopmentState) | M10-A docstring update |
| `SemanticMemoryRecord.belief_kind` | 既存維持。dyadic only として SWM `axis` と直交 | unchanged |
| `cognition/belief.py:maybe_promote_belief` | pure function pattern を `apply_world_model_update_hint` 等に踏襲 | M10-C 流用 |
| `LLMPlan` | additive 拡張のみ (minor bump) | M10-C |
| `cognition/prompting.py:_format_persona_block` | `PhilosopherBase` 系統 + Individual 注入の責務分離 | M10-B |
| `format_memories` | memory id を prompt に出すよう契約変更 (Codex MEDIUM-2 dependency) | M10-A |

## 5. Acceptance criteria (per milestone、定量)

| Milestone | Quantitative criterion |
|---|---|
| M10-0 | 個体化 sidecar metric が baseline で valid 値を返す、benchmark 枠組み green |
| M10-A | 1318 tests PASS、新 schema golden test green、wrapper 互換 (既存 personas load OK) |
| M10-B | cache hit rate ≥ 80% baseline、TTFT delta ≤ 5%、prompt token +200 以内、SWM が persona 別に異なる軸で立ち上がる (Burrows 直交シグナル) |
| M10-C | adoption rate `[0.05, 0.40]` 内 (LLM が cite 諦めず、free-form は採用されず)、golden test 「free-form belief 主張は採用されない」 PASS |
| M11-A | coherence_score 計算が走る (diagnostic only)、low coherence で reflection 深化 trigger が発火 |
| M11-B | 1 individual 1000-tick で S1→S2→S3 が observable evidence 駆動で発火、LLM 自己申告 stripped run で発火しない (negative control) |
| M11-C | Burrows ≥ 0.6 (base 保持)、semantic centroid pairwise distance ≥ threshold (個体化)、belief variance > 0 (Codex HIGH-4 分解測定) |

## 6. Open questions left for implementation tasks (defer)

- `decay_half_life_ticks = 1000` の calibration: M10-B 実装時に simulation で再 tune
- `WorldModelUpdateHint.adoption rate` 目標 band `[0.05, 0.40]` の根拠: M10-C empirical
  測定後再評価
- `personality_drift_offset` の bounded 範囲 (±0.1 per axis): M11-C で multi-individual
  divergence 観測後再 calibration
- `coherence_score` の hard threshold: M11-A diagnostic phase 後、false-positive rate
  測定して M11-B で hard gate 化検討

## 7. Source documents

- 旧 design.md: Claude Plan-mode initial 判定 (個別 schema として読み、提案 6/7 を REJECT/DEFER)
- 旧 design-clarified.md: User clarification 反映 (二層解釈、Option A vision)
- 旧 design-reimagine.md: independent reimagine (Compression-Loop counter、persona identity 維持
  vs user vision の核 tension を提示)
- codex-review.md: Codex `gpt-5.5 xhigh` 197K tokens、ADOPT-WITH-CHANGES、HIGH 7 / MEDIUM 5 /
  LOW 3、prior art 9 件 web 引用 (Generative Agents / CoALA / Voyager / Identity Drift /
  Persistent Personas EACL 2026 / Agent Identity Evals 2025 / Memoria Memori / Piaget 批判 /
  SGLang RadixAttention LoRA)
- 本書 design-final.md: 3-source synthesis、Codex HIGH 7 件すべて反映、User Option A 維持

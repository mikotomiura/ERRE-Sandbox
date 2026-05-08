# Design — Post-clarification 改訂判定 (2026-05-08)

> このドキュメントは `design.md` の判定をユーザー clarification (2026-05-08
> follow-up) で **再評価** したもの。元の `design.md` は initial reading として残す。
> 最終判定は `design-final.md` (Codex review 後) でまとめる。

## 0. Clarification の structural reading

ユーザー clarification は 7 提案を「個別 schema 追加の集合」から **二層アーキテクチャへの
統一的転換** に framing し直した。要点:

- 提案 1, 7 が同根: **agent は新しい個体**、philosopher は **base layer**
- 提案 5, 6 が同根: 個体が **時間経過で発達する**
- 提案 2, 3, 4 は二層モデルで個体側を駆動する mechanism

このため判定は **個別 ADOPT/REJECT** ではなく **architecture as a whole** で判断される
べきで、その場合 7 提案はすべて単一 architecture の構成要素として ADOPT すべき。

## 1. 二層アーキテクチャの draft 設計

### 1.1 Layer 分離

```
PhilosopherBase (immutable, inherited)
  ├── cognitive_habits: list[CognitiveHabit]   (現 personas/*.yaml の cognitive_habits 流用)
  ├── default_sampling: SamplingParam          (現 default_sampling 流用)
  ├── preferred_zones: list[Zone]              (現 preferred_zones 流用)
  ├── lora_adapter_id: str | None              (M9-B LoRA target)
  └── persona_id: str                          (kant / rikyu / nietzsche、固定 reference)

Individual (mutable, per-agent runtime state)
  ├── individual_id: str                        (新規 entity)
  ├── base: PhilosopherBase                     (継承、reference)
  ├── personality: Personality                  (Big5 + wabi/ma_sense、base から divergence 可)
  ├── world_model: SubjectiveWorldModel         (= 提案 1、AgentState property、5 axis)
  ├── narrative_self: NarrativeSelf | None      (= 提案 5、周期蒸留 result)
  ├── development_state: DevelopmentState       (= 提案 6、lifecycle 段階)
  ├── shuhari_stage: ShuhariStage               (既存、base 側技能習得とは別文脈で再解釈)
  └── (memory, relational bond は既存通り)
```

**継承 contract** (HIGH 必要、Codex に問う):
- `cognitive_habits`: base から継承、individual が override は **不可** (= "Kant 由来の散歩
  は揺るがない")
- `default_sampling`: base から継承、individual が override **可** (= 個体の気分で揺らぐ)
- `personality`: base が default 提供、individual が初期から **bounded divergence** で
  個別化 (= 兄弟でも性格が違う)
- `world_model`: 完全に individual 側 (base は "無" を default で提供)
- LoRA adapter: base layer のみに適用 (= 個体差は prompt/state overlay)

### 1.2 既存資産との関係 (二層解釈下で再評価)

| 既存 | layer 配属 | 変更必要性 |
|---|---|---|
| `personas/*.yaml` | → `PhilosopherBase` に rename / refactor | **大**: schema_version bump、loader 改修、prompting 改修 |
| `AgentState.persona_id` | individual.base.persona_id へ間接化 | 中: getter 維持で互換可 |
| `AgentState.cognitive`, `AgentState.physical`, `AgentState.erre` | individual の sub-state | 小: 既存配置を維持 |
| `AgentState.shuhari_stage` | individual.shuhari_stage | 小: 配置維持。意味解釈のみ変更 (技能習得 stage、lifecycle とは別) |
| `SemanticMemoryRecord.belief_kind` | individual の dyadic belief (subjective beliefs に統合) | 小: 既存維持、SubjectiveWorldModel と axis 直交 |
| `RelationshipBond` | individual 側 | 小: 既存維持 |
| `LLMPlan` | individual の出力 (個体の意思決定) | 中: world_model_update 追加 (bounded primitive) |
| Prompt `_COMMON_PREFIX` | base + individual 両方を反映するよう改修 | 中: cache 戦略再設計 |

### 1.3 改訂された per-item 判定

| # | 旧判定 (initial) | **新判定 (clarification 後)** | 主要変更 |
|---|---|---|---|
| 1 SubjectiveWorldModel | ADOPT in memory layer | **ADOPT as `Individual.world_model` property** (AgentState 第一級) | "agent 自体に" 明確化を反映、配置変更 |
| 2 prompt 注入 | ADOPT w/ constraints | **ADOPT, 同設計** | 変更なし (`_COMMON_PREFIX` 汚染禁止、user prompt 側) |
| 3 LLMPlan world_model_update | MODIFY to bounded primitive | **ADOPT as bounded primitive** | 同じ判定 (free-form は role-play 増幅、bounded primitive 必須) |
| 4 safe merge | ADOPT | **ADOPT, belief.py pattern 流用** | 変更なし |
| 5 NarrativeSelf | M11-A defer | **M10-B (M9-B 後の最初の milestone)** | 個体連続性に必須、後送不可 |
| 6 DevelopmentState | REJECT standalone | **ADOPT as `Individual.development_state`** | shuhari_stage は base 側技能習得、DevelopmentState は individual 側 lifecycle、**直交** |
| 7 philosopher_seed | DEFER M11+ | **ADOPT as conceptual two-layer refactor** | base = LoRA target (M9-B 不変)、individual = overlay。M9 trunk 破壊しない |

## 2. 「完全に人間として構築」への operational 制約案 (initial)

ユーザー言明「途中途中から成長していく過程を導入し、完全に人間として構築」は scope
無限化リスク。Codex に operational definition を切り詰めてもらうため、**Claude 提案の
bounded interpretation** を先に置く:

### 2.1 段数の制約 (5 stage 案)

```
DevelopmentStage:
  S1_seed:       初期化直後、base habit 強い、world_model 空
  S2_individuation: 個体差発現、world_model 5-15 entries、narrative 未生成
  S3_consolidation: 信念の安定、world_model 15-50 entries、narrative_self 初回生成
  S4_articulation: 自己語り定常化、narrative cycle 安定、belief revision rate 減衰
  S5_late:       高 importance 記憶飽和、新規入力に rigidity (人間の老化アナロジー)
```

5 段は経験的選択 (Erikson 8 / Piaget 4 / 守破離 3 の中間)。

### 2.2 各段の cognitive 特性差 (operational)

| stage | sampling 修正 | memory window | reflection 周期 | personality drift 許容 |
|---|---|---|---|---|
| S1 | base 通り | 標準 | 標準 | high (個別化中) |
| S2 | T +0.05 (探索期) | 拡張 1.2x | 1.5x 高頻度 | high |
| S3 | base 通り | 標準 | 標準 | medium |
| S4 | T -0.05 (内向化) | 標準 | 1.5x 高頻度 | low |
| S5 | T -0.10 | 縮退 0.8x | 0.5x 低頻度 | very low |

これは **first principles ではなく empirical placeholder** で、Codex / 実装段階で再
calibration 必須。

### 2.3 段間遷移 criterion (transition trigger)

複合条件 (AND):
- world_model entries ≥ 段ごと閾値 (S2: 5, S3: 15, S4: 50, S5: 150)
- narrative_self が直近 N=3 cycles で stable (cosine sim > 0.85 to median)
- importance 累積 ≥ 段ごと閾値

これは memory promote / belief promote と同型 pattern (threshold AND interaction count)。

### 2.4 "完成" の定義 (= 死/置換するか問題)

3 path 候補 (Codex に判断委ねる):
- **path A**: 不完成。S5 で停滞、無限走行
- **path B**: 死/置換。S5 で N session 後に individual を retire、新 individual を同じ
  base から起動 (世代交代観察可)
- **path C**: stage rebirth。S5 から S2 にループ (転生 metaphor、研究的に面白いが
  現実的でない)

Claude 推奨: **path A** (個人プロジェクトの scope 制約、retirement / 転生は M12+ 研究)

## 3. 改訂 phasing (clarification 反映)

```
M9 trunk (UNTOUCHED):
  - run1 calibration (G-GEAR、in-flight)
  - M9-eval Phase 2 完了
  - M9-B LoRA execution (philosopher_base = Kant 文体、固定)
  ↓ M9 完了 → individual layer 構築開始可能

M10-A: Two-layer schema scaffold (提案 7 + 1 + 6 の structural 部分)
  - PhilosopherBase / Individual / SubjectiveWorldModel / DevelopmentState
    Pydantic schema を contracts/ 配下に新設
  - personas/*.yaml は 0.10.0-m7h → 0.11.0 に bump、PhilosopherBase に rename
  - AgentState を Individual 側に再配置 (互換 wrapper を 1 release 維持)
  - schema scaffold のみ、ロジック未配線、test 通過のみ
  - acceptance: 既存 1318 tests PASS、新 schema の golden test 追加

M10-B: Individual 側の cognition wiring (提案 1 + 2 + 3 + 4 + 5)
  - SubjectiveWorldModel の write path: prompt 注入 + bounded LLMPlan update +
    safe-merge (belief.py pattern 流用)
  - NarrativeSelf 周期蒸留 (chashitsu reflection 拡張で発火)
  - DevelopmentState は S1 固定 (transition machinery は M11)
  - acceptance: 100-tick smoke で 1 individual の世界モデル形成と narrative 生成を確認

M11-A: DevelopmentState transition machinery (提案 6 lifecycle 化)
  - 5 段 (S1-S5) と段間 trigger
  - 各段の sampling / memory / reflection 修正
  - acceptance: 1 individual を 1000-tick 走らせ S1→S2→S3 の遷移を確認

M11-B: Multi-individual 同 base 検証 (個体化の direct evidence)
  - 3 individual を同 PhilosopherBase (kant) から起動
  - Burrows ratio で base 保持 + 個体ばらつきを分解測定
  - acceptance: base style identity ≥ 0.6 (LoRA 効果残存) AND individual variance ≥
    threshold (個体化観測)

M12+ (research re-evaluation):
  - retirement / world transition (path B 検討)
  - 多 base × 多 individual の社会実験
  - LoRA を individual layer にも適用するか判断
```

## 4. 新規 HIGH-stakes な open question (Codex review 必須)

1. **base / individual inheritance contract**: cognitive_habits は immutable か?
   sampling は inherit + override 可能か? Big5 は base から divergence 許容範囲は?
   この設計が決まらないと M10-A scaffold が書けない。

2. **schema_version bump 戦略**: 0.10.0-m7h → 0.11.0 で persona YAML を
   PhilosopherBase に rename するときの **backward compat 戦略**:
   - personas/*.yaml の自動 migration script を書くか
   - 1 release 並走 (両 schema を loader で受ける) するか
   - 一括書換えで割り切るか (現在 3 personas しかない)

3. **LoRA scope**: M9-B LoRA は base layer 専用か、individual の personality drift も
   学習対象か? 後者なら M9-B execution 着手前に再判断必要。

4. **prompt 構造改修と KV cache**: `_COMMON_PREFIX` を base と individual で分離する
   とき、SGLang RadixAttention 効果はどこまで保たれるか? 多 individual で多 base
   になったら cache 効果は減衰するか?

5. **DevelopmentStage 5 段の妥当性**: 3 (shuhari と並立) / 5 (Claude 案) / 8 (Erikson)
   のどれが ERRE thesis に整合するか? 経験的選択ではなく first principles から
   論証できるか?

6. **"完成" の path 選択**: A (不完成) / B (retirement) / C (転生) のどれを M11-A の
   default 設計にするか?

7. **二層分離が role-play 増幅 risk を緩和するか悪化するか**: LLM に "あなたは Kant
   ベースの新しい個人 X" と告げると、LLM は X を **role-play する** 危険があり、これは
   現在の "あなたは Kant" より **悪化** する可能性がある (個体の自由度が高い分、創作の
   余地も広い)。

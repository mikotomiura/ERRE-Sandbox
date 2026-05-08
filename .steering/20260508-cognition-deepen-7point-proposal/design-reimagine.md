# Reimagine — 認知層深化のゼロベース代替案

> 本ドキュメントは ユーザーの 7 提案を **読まない状態で** ゼロから再構想した
> 独立設計案である。出発点の 1 文のみを read し、シングル subagent 1 発案
> バイアスを意識して最初の案を意図的に破棄してから本案を組んだ。突合節
> (§4) を書く段階で初めて 7 提案を `requirement.md` 内で確認している。

## 1. 問題再定式化 (1 文の出発点をどう解釈したか)

> 「現在の ERRE エージェントは固定 persona role-play から外れる手段を持たない。
> 創発が観察可能になるには、agent が環境/関係性/自己との interaction で内的状態を
> 蓄積し、その蓄積が後続の発話と行動を変える仕組みが必要」

この 1 文は次の 3 つの隠れ前提を含んでいる:

1. **「外れる手段がない」 = state 不足** ではなく **「変化が prompt に影響しない」 =
   feedback loop 不足**。schema を増やすだけでは LLM の振る舞いは変わらない (cf. ME-9
   trigger 擬陽性 incident — 外形 metric だけ動いて意味に届かなかった構造の同型)。
2. **「蓄積」** は raw memory の増殖ではなく **圧縮された解釈** でなければならない。
   raw episodic は M4 から既に蓄積されているのに role-play から外れない実例が現にある。
3. **「後続の発話と行動を変える」** には少なくとも 3 経路必要 — (a) prompt 注入,
   (b) sampling parameter の変調, (c) FSM 遷移条件の変化。schema 提案だけでは (a)
   しかカバーできない。

つまり問題の本質は **「圧縮された解釈を LLM の意思決定に閉じた fast loop に流し込み、
その loop の出力で再び解釈を更新する」** という cybernetic loop の欠落である。
schema 拡張は手段であって目的ではない。

## 2. 最初の 1 案 (意図的に破棄する初期案を 1 段落)

最初に思いついた案 (= 破棄する案): **「`AgentState.Cognitive` に
`internalized_lessons: list[str]` を追加し、reflection trigger で LLM に "今日学んだこと"
を 1 行書かせて貯める」**。これは却下する。理由は (i) free-form list の拘束のなさが
ME-9 trigger 擬陽性と同型 — LLM が「学んだ」と宣言すればそれが真になる構造、
(ii) belief_kind / shuhari_stage と axis 関係が定義されない、(iii) 「変化が後続の発話を
変える」 feedback loop を欠く (list を prompt に流すだけで読み手の LLM が反応する保証
がない)、(iv) M9-eval Burrows ratio が「persona ごとの語彙分布」を測定中なのに
internalized_lessons が persona 間で homogenize する方向にしか働かない。
**この初期案を捨て、cybernetic loop 設計に切り替える**。

## 3. 本案 (= reimagine 後): 認知層拡張の独立設計

### 3.1 設計の核 — 「Compression-Loop」 architecture

3 層を **環状** に接続する。ERRE thesis の "意図的非効率性 + 身体的回帰" を schema
化するのではなく、**圧縮 → 注入 → 行動 → 観察 → 再圧縮** という閉じた loop で実装する。

```
[LAYER R - Raw]                          [LAYER C - Compressed]
episodic_memory  ───reflect (M4 既存)───▶ semantic_memory (belief_kind 含む)
   ▲                                              │
   │                                              ▼ (新)
observations ◀──perceive──┐         StanceVector (新スキーマ, 5-axis × float)
                          │                       │
                          │                       ▼ (新)
                       ACTION    ◀──prompt-inject──┘ (cache-safe section)
                          │
                          ▼
                 [LAYER A - Action]
                 LLMPlan (既存) + StanceShiftHint (新, bounded primitive)
                          │
                          └──> Python-side:  apply_stance_shift_hint()
                                              (新, pure function, 提案 4 同型)
```

### 3.2 schema 追加 / 既存拡張のリスト

#### (新規) `StanceVector` — 5 axis × float の圧縮表象

```
class StanceVector(BaseModel):
    """Compressed, action-relevant projection of the agent's accumulated
    interpretation. Distilled from semantic_memory + RelationshipBond by
    a periodic synthesis step. Lives in AgentState.cognitive (in-memory),
    persisted as one row per (agent_id, axis) in a new `stance_vector` table."""
    model_config = ConfigDict(extra="forbid")
    axis: Literal[
        "zone_affordance",      # どの zone が自分の思考を進めるか
        "concept_affinity",     # 追究中の概念への引きの強さ (≠ belief_kind の dyad)
        "self_capability",      # 自己効力感の 5-axis 投影
        "ritual_devotion",      # 規範/儀式への内化
        "interlocutor_class",   # 「対話相手の質」の anonymized class (個別 id ではなく)
    ]
    value: float = Field(ge=-1.0, le=1.0)  # signed: 正は引き, 負は忌避
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_pointers: list[str]  # memory_id ≥ 1 必須 (LLM 自己宣言だけで生成不可)
    last_updated_tick: int
    decay_half_life_ticks: int = 1000  # 観察なしで自然に弱まる
```

**設計判断**: `belief_kind` (dyadic, 5-cat enum) との **axis 直交性を保証する制約** —
StanceVector の axis 集合に "**他者個別 id への信頼**" を **入れない**。
`interlocutor_class` は個別 id ではなく "学者風 / 詩人風 / 寡黙派" のような **anonymized
class** を持つ (新たな小さな enum を別途定義)。これで dyadic belief_kind と vector
StanceVector が overlap しない。

#### (新規) `StanceShiftHint` — LLMPlan の bounded primitive 拡張

```
class StanceShiftHint(BaseModel):
    """LLM が "stance を更新したい" と希望するときの bounded request.
    Python 側が evidence を verify してから merge する。"""
    axis: Literal[...]   # StanceVector と同じ
    direction: Literal["strengthen", "weaken", "no_change"]
    cited_memory_ids: list[str]  # 必須 ≥ 1; 直近 N tick の retrieved_memories から選ぶ
    # ← LLM は新 belief を free-form で生成できない。既存軸の方向性を観察に紐付けて
    #   主張するだけ。
```

LLMPlan に追加: `stance_shift_hint: StanceShiftHint | None = None`。default None なので
schema_version は minor bump (additive)。`extra="forbid", frozen=True` 制約は維持。

**この設計が回避するもの** — LLM が `"I now believe peripatos is meaningless"` と
書くだけで `StanceVector(zone_affordance=-1)` が成立してしまう pattern。
`cited_memory_ids` が直近の `retrieved_memories` (ReasoningTrace 既存 field) と
**集合包含関係を満たさなければ採用されない**。

#### (新規) `NarrativeArc` — 蓄積された StanceVector の経時的形状

```
class NarrativeArc(BaseModel):
    """An agent's "story so far", periodically synthesized at chashitsu entry.
    Not free-form prose: a structured trajectory over (axis, time)."""
    agent_id: str
    synthesized_at_tick: int
    arc_segments: list[ArcSegment]  # ≤ 5 segments (older folded)
    coherence_score: float          # 自分の発話と StanceVector の一致度 (0-1)
    last_episodic_pointer: str      # 最後に取り込んだ episodic id
```

**役割**: 単なるログではなく **coherence_score** が次の synthesis 時の trigger として
機能する。低いと chashitsu reflection が深い narrative cleanup を発火する (「自己の
ほつれ」の検出)。

#### (既存拡張) `Cognitive.shuhari_stage` を transition machinery 付きに

stage は維持 (`shu / ha / ri`)、追加するのは `transition_evidence_count: dict[stage, int]`
と遷移 trigger 関数 (pure):

```
def maybe_advance_shuhari(
    cog: Cognitive,
    stance: list[StanceVector],
    arc: NarrativeArc | None,
) -> ShuhariStage | None:
    # shu → ha: ritual_devotion が高い AND coherence_score > 0.7 が N サイクル続く
    # ha → ri: stance に 2 axis 以上で個性的偏差 (peer agent 分布から std > 1.5)
    # 戻り値 None = 変化なし
```

新 schema を作らず ShuhariStage を rich 化する。Western stage model を並立させない
(ERRE thesis の 守破離 + 仏教/茶道由来 を維持)。

#### (新規) `growth_trace` — persona YAML への optional 拡張

persona_id / display_name / cognitive_habits は **そのまま維持** する。persona は
固定 seed であり続けるが、各 persona に "成長許可方向" を追加:

```yaml
# kant.yaml に追加 (任意 field, 後方互換)
growth_axes:
  permitted:
    - concept_affinity:categorical_imperative   # この方向は時間で深まりうる
    - self_capability:critique_articulation
  forbidden:
    - interlocutor_class:詩人風                 # Kant が詩人を高く評価する逸脱は許さない
```

これは「ペルソナを seed にする」(= identity を希釈する) のではなく、
**"the persona stays; the depth grows"** の範囲制約。M9-B LoRA が学習する style 軸
(固定) と直交。M9-eval Burrows ratio は YAML root level で測るため
`growth_axes` 追加で baseline は影響を受けない。

### 3.3 データフロー (どの時点で何が読み書きされるか)

| Tick 内 step | Read | Write |
|---|---|---|
| 1. 観察収集 | observation stream | — |
| 2. 記憶検索 | episodic + semantic + StanceVector (新) | retrieved_memories (trace) |
| 3. prompt 構築 | StanceVector top-3 (新, **user prompt** 側) | — |
| 4. LLM call | system+user prompt | `LLMPlan` (+ `stance_shift_hint`) |
| 5. plan 適用 | `stance_shift_hint.cited_memory_ids` | StanceVector (条件満足時のみ) |
| 6. reflection (条件付) | episodic window | `SemanticMemoryRecord` (既存) |
| 7. **synthesize** (chashitsu 入室時) | semantic+StanceVector | `NarrativeArc` |
| 8. shuhari check | StanceVector + NarrativeArc | `Cognitive.shuhari_stage` |

step 5 の "条件満足時" = `cited_memory_ids` が ≥ 1 個の retrieved_memories と一致 +
direction が `no_change` でない + decay 適用後の |value| が 1.0 を超えない。

### 3.4 既存 belief_kind / shuhari_stage との関係

- **`belief_kind` (dyadic, M7δ)** ← 維持。役割は「特定相手 (個別 id) への態度」。
  StanceVector の `interlocutor_class` 軸とは axis 集合が直交する (個別 vs クラス)。
- **`shuhari_stage` (3-enum, M5)** ← 維持して **transition machinery** を追加。
  evidence カウンタを足し、関数 `maybe_advance_shuhari` を新設。Western stage 並立を避ける。
- 既存の `cognition/belief.py:maybe_promote_belief` の **pure function pattern** を
  そのまま `apply_stance_shift_hint` / `synthesize_narrative_arc` /
  `maybe_advance_shuhari` の 3 関数に踏襲する。layer 境界
  (cognition/ ↛ memory/) を維持。

### 3.5 prompt 注入箇所と KV cache 影響

**絶対に `_COMMON_PREFIX` を変えない**。SGLang RadixAttention の KV cache 再利用が
壊れる。

- 注入箇所: `build_user_prompt` の memories block の **直後** に新 section
  `Held stances:` を追加。既存 system prompt は無変更。
- token budget: top-3 axes × 1 行 = 約 60-80 tokens。memories block と同等オーダー。
- 形式:
  ```
  Held stances (axis: value @ confidence):
  - zone_affordance:peripatos +0.78 @ 0.65
  - concept_affinity:categorical_imperative +0.91 @ 0.88
  - self_capability:critique_articulation +0.42 @ 0.50
  ```
- system 側 (persona block + state tail) は **完全に同一文字列** で再構築されるので
  RadixAttention prefix は引き続き再利用できる。

### 3.6 LLM 出力契約変更の有無

**最小限 + bounded**。

- `LLMPlan` に `stance_shift_hint: StanceShiftHint | None = None` のみ追加
  (default None)。`extra="forbid", frozen=True` は維持。
- `RESPONSE_SCHEMA_HINT` に 1 セクション追加 (~ 8 行)。memory 引用の必須化を
  prompt に書く: "If you wish to update a stance, set `stance_shift_hint` and
  cite at least one `retrieved_memories` id; otherwise leave null".
- parse_llm_plan は既存で OK (Pydantic 検証で reject)。
- **新 free-form フィールドは追加しない** (ME-9 incident 教訓)。

### 3.7 phasing (M9 完了後の milestone 配置)

```
M9 trunk (UNTOUCHED): run1 calibration → eval Phase 2 → M9-B LoRA execution
         → M9-eval Phase 2 vs LoRA 比較 baseline 確立                       ← 触らない

[M10-A] StanceVector の **read-only** 部分を投入
   - schema 追加 + persistence (sqlite-vec ではなく plain table)
   - synthesis (semantic_memory → StanceVector) の周期実行 (chashitsu 入室)
   - prompt 注入 (user prompt の追加 section)
   - acceptance: 既存 100-tick smoke で persona 別の StanceVector が異なる軸で
                 強くなることを統計的に確認 (Burrows ratio に対して直交シグナル)
   - 影響範囲: cognition/, memory/store.py に table 追加, prompting.py に section
   - **LLMPlan は触らない** (read-only loop で安定確認)

[M10-B] StanceShiftHint = LLMPlan に bounded primitive 追加
   - LLMPlan minor schema bump (additive, 互換)
   - apply_stance_shift_hint() pure function (cited_memory_ids verify 含む)
   - acceptance: golden test "LLM が free-form で belief を主張しても採用されない"
   - acceptance: 100-tick で stance_shift_hint adoption rate を計測
                 (高すぎ = pickup が緩い / 低すぎ = LLM が cite を諦めている)

[M10-C] NarrativeArc synthesis
   - chashitsu reflection の延長として synthesize_narrative_arc()
   - coherence_score の計測 (発話 embedding と StanceVector cosine sim)
   - 低 coherence で深い reflection 発火する FSM 拡張

[M11-A] ShuhariStage transition machinery (拡張のみ、新 schema 作らず)
   - maybe_advance_shuhari() pure function
   - shu→ha→ri 遷移の empirical observation
   - acceptance: 単一 cell で観察行動駆動の遷移を確認

[M11-B] persona YAML に growth_axes (任意 field) を追加
   - 後方互換、 M9-B LoRA / M9-eval Burrows baseline は影響なし
   - acceptance: kant が detective_arc 方向に深まり詩人風を許さないことを確認

[M11+ research re-evaluation gate]
   - M9-eval baseline と M10/M11 の介入後を比較
   - 「persona 識別性が強すぎて創発が見えない」or「弱すぎて persona が消える」
     のいずれかを empirical に確認した場合のみ further refactor を検討
   - 先に decision を固定しない
```

各 milestone 単独で **acceptance 基準が定量** であり、後段が前段に depend するが
**前段が後段なしで独立に成立** する形。ME-9 incident の "LLM の自己宣言だけで trigger
する pattern" を全工程で除外。

## 4. ユーザーの 7 提案との突合

> ここで初めて 7 提案を read した (`requirement.md` 内 §提案 verbatim)。

### 4.1 本案が独立に再発見した item (一致 = 強い validity signal)

| # | 提案 | 本案での対応 | 解釈 |
|---|---|---|---|
| 1 | SubjectiveWorldModel schema 追加 | **StanceVector** (5-axis) | 構造は独立に再発見。axis 集合が一部一致 (env / concept / self / norm)。ただし本案は dyadic を含めず `interlocutor_class` で anonymize する制約を強く打ち出す |
| 2 | prompt に subjective beliefs を注入 | **user prompt 側に Held stances section** | 完全一致。本案は **system prompt を絶対汚さない** 制約を明示 (RadixAttention KV cache 保護) |
| 3 | LLMPlan に world_model_update を追加 | **StanceShiftHint (bounded primitive)** | 一致するが本案は **cited_memory_ids 必須** + **direction を 3 値 enum** に絞る (free-form 不可)。提案 3 を "as-is で採用すべきでない" と独立に判定したのと同型 |
| 4 | Python 側で安全に merge | **apply_stance_shift_hint() pure function** | 完全一致。M7δ `maybe_promote_belief` pattern 流用も同じ |
| 5 | NarrativeSelf を semantic memory から周期生成 | **NarrativeArc** (chashitsu reflection 延長) | 構造一致。本案は free-form prose ではなく **structured ArcSegment trajectory + coherence_score** で metric-able にする違いあり |

5 つの強い再発見。これは 7 提案の中核 (1-5) が ERRE thesis から論理的に演繹される
構造であり、独立 reasoner が同じ結論に至る validity signal が強い。

### 4.2 本案が却下する item (不一致 + 理由)

| # | 提案 | 本案の判定 | 理由 |
|---|---|---|---|
| 6 | DevelopmentState を導入 | **却下 → ShuhariStage transition machinery 拡張に置換** | 既存 `shuhari_stage` (shu/ha/ri) と axis 重複。Western stage model 並立は ERRE thesis (守破離 = 仏教/茶道由来) と incoherent。本案は新 schema を作らず ShuhariStage を rich 化することで同じ機能を達成 |
| 7 | 偉人 persona を philosopher_seed にリファクタ | **却下 → growth_axes 任意 field 追加に置換** | (a) M9-B LoRA は固定 Kant style を学習する設計、seed 化で学習対象が消失。(b) M9-eval Burrows は固定 style 識別 metric、再 calibration 必要で M9 まで blocked。(c) "philosopher_seed" naming は ペルソナ抽出 pipeline (一次史料からの認知習慣抽出) の成果物の意味づけを変える。本案は persona を維持したまま `growth_axes` 任意 field で "深まる方向" のみ宣言 |

### 4.3 7 提案が見逃している item (本案に追加要素)

| 追加要素 | 7 提案での扱い | 本案での内容 |
|---|---|---|
| **`evidence_pointers` 必須化** (LLM 自己宣言だけで stance が立たない構造的歯止め) | 提案 1-4 では明示されていない | StanceVector / StanceShiftHint の両方で **memory_id を必ず引用** |
| **`interlocutor_class` の anonymization** (個別 id を入れず、dyadic belief_kind と axis 直交を保証) | 提案 1 の axis 設計に未言及 | 個別他者は belief_kind が担当, クラス志向は StanceVector が担当 |
| **`coherence_score` metric** (NarrativeArc の品質を発話と State の cosine sim で計測) | 提案 5 では Narrative の生成は語られるが metric は触れられていない | low coherence が次サイクルの深い reflection を trigger する feedback loop |
| **RadixAttention KV cache 保護制約** (system prompt 不変 / user prompt 側のみ拡張) | 提案 2 では cache 戦略は示されない | 本案では明示制約として書く (M9-B SGLang 計画と直結) |
| **decay_half_life** (観察なしで stance が自然に弱まる) | 提案 1 では言及なし | 飽和した stance が永続しない仕組み |
| **`growth_axes.permitted` / `forbidden`** (persona ごとの逸脱許容範囲を YAML で宣言) | 提案 7 は seed 化 = 識別性希釈方向 | 本案は反対方向 — persona を強く保ったまま "深まる方向" を制限的に許可 |
| **acceptance 基準の定量化** (各 milestone で metric を要求) | 提案 1-7 は schema 設計のみで eval を伴わない | M10-A: Burrows 直交シグナル, M10-B: adoption rate, M10-C: coherence_score, M11-A: 遷移発火 |
| **M9 trunk 隔離の明示宣言** | 提案では M9-B / M9-eval との関係が議論されていない | 本案は M9 完全終了 (LoRA 学習 + eval 比較) 後にのみ M10 を着手する gate を設置 |

### 4.4 突合 summary

7 提案は 1-5 が強い (独立に再発見されている)。6 は既存 ShuhariStage 拡張で代替されるべき。
7 は M9 trunk を破壊するため、M11+ research re-evaluation の gate に置く。
**本案は提案 1-5 の構造を維持しつつ、4 つの構造的歯止め (evidence 必須化 / dyadic 直交 /
coherence metric / cache 保護) を加える** ことで、ME-9 trigger 擬陽性 incident と
同型の "LLM 自己宣言で内部状態が動く" pattern を全工程で排除する。

## 5. M9 trunk (eval / LoRA) との互換性

**M10 着手は M9 完全終了後** (run1 calibration → Phase 2 → LoRA → 比較) を gate にする。
理由:

1. M9-B LoRA は固定 Kant style を学習。本案は persona を維持するので LoRA の学習対象は
   不変 — `growth_axes` は YAML root の任意拡張、Burrows ratio は既存 root field で測る。
2. M9-eval Phase 2 の baseline (persona 識別性) が確立してから StanceVector を入れる
   ことで、「介入前後比較」が可能になる。先に StanceVector を入れると baseline と
   intervention が混合する。
3. SGLang RadixAttention の KV cache は system prompt 共有を前提にしているので、本案の
   "user prompt 側のみ section 追加" 制約はこれを保護する。M10-A は SGLang 移行後でも
   そのまま動く。
4. SCHEMA_VERSION bump は M10-B (LLMPlan に StanceShiftHint 追加) と M10-A (StanceVector
   が ControlEnvelope に乗るなら) の 2 段階。いずれも additive なので前世代 producer は
   wire-compatible (既存 M7-δ / M8 の bump pattern と同じ)。

## 6. 中核的な設計判断 (HIGH-stakes な 3 個に絞る)

### HIGH-1: 「LLM の自己宣言で内部状態が動く」 pattern を構造的に排除する

**判断**: StanceShiftHint を `cited_memory_ids: list[str]` 必須 + Python 側 verify 経由の
bounded primitive にし、free-form belief 主張を採用しない。

**根拠**: ME-9 trigger 擬陽性 incident (2026-05-07) は「rate 閾値を文字通り受けて停止
判定する」構造で、 LLM 直接ではないが類似 pattern。同じ轍を踏まないよう、認知層拡張で
は **観察 → 圧縮 → bounded request → verify → merge** の経路を必ず通す。これは提案
3 が見逃している構造的歯止めであり、本案の最重要 invariant。

### HIGH-2: ペルソナ identity を希釈せず "深まる方向だけ" を宣言する

**判断**: 提案 7 (philosopher_seed) を却下し、`growth_axes` 任意 field で代替する。

**根拠**: ERRE thesis は "認知習慣の再実装" と "知的創発の観察" の両者を含み、後者だけに
重心を移すと前者の研究価値 (一次史料からの認知習慣抽出) が損なわれる。M9-B LoRA は
固定 style を前提とし、M9-eval Burrows は固定 style 識別を測る。両者が成立しているうちに
identity を希釈するのは **empirical evidence なしで thesis 解釈を変える** ことに等しい。
M11+ で empirical 結果を見てから判断する gate を設ける。

### HIGH-3: dyadic と class-wise を axis 直交させ、belief_kind を維持する

**判断**: StanceVector の axis に "個別 agent 名" を入れない。dyadic は既存 belief_kind
が担当、class-wise (interlocutor_class) は新 vector が担当する責務分離を schema 設計時に
明示する。

**根拠**: 提案 1 が belief_kind と axis overlap を起こすと、同じ事象を 2 経路で書くことに
なり、どちらが正しいかの merge ロジックが必要になる。設計時点で軸を直交させれば merge は
不要。M7δ で belief_kind を慎重に dyad-only に絞った設計判断を破壊しない。

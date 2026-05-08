# Design — Initial judgment (pre-reimagine, pre-codex)

> 本セクションは Claude 単独の初期判定。/reimagine alternative と Codex
> independent review で必ず challenge する。最終判定は `design-final.md` に書く。

## 0. Problem framing — 提案の背後にある cognitive architecture 問題

7 提案を要素ではなく構造で読むと、ERRE の中核緊張を解こうとしている:

- 「**static persona role-play**」: 偉人 YAML を prompt に注入 → LLM が役を演じる → 個別
  tick で完結。現在の実装はここ。
- 「**developing cognitive entity**」: 偉人を起点 (seed) として、環境 + 記憶 + 関係性
  との相互作用で agent 内部に subjective world / narrative self / development が
  形成されていく。提案はこの極へ重心移動。

ERRE thesis (functional-design.md §1) は両方を含む — 「**認知習慣の再実装**」 (前者) と
「**知的創発の観察**」 (後者) は緊張関係にある。提案は thesis 内部の解釈問題に踏み込む。

これは単なる schema 拡張提案ではない。**M9 trunk (eval + LoRA)** が前者の解釈に depend
しているため、提案 7 (philosopher_seed) は M9 を破壊しうる。提案 1, 4, 5 は前者と衝突せず
追加できる可能性がある。提案 6 は既存 ShuhariStage と直接重複。提案 2, 3 は中間。

## 1. 既存資産との具体的衝突マップ

| 提案 | 既存資産 | 関係 | 統合難度 |
|---|---|---|---|
| 1 SubjectiveWorldModel | `SemanticMemoryRecord.belief_kind` (dyadic, 5 cat) | 直交 (belief_kind は dyad only、提案は env/concept/self/norm 含む) | 低: gap fill |
| 2 prompt injection | `_COMMON_PREFIX` + `_format_persona_block` + RadixAttention KV 再利用 | injection 位置で cache 戦略影響 | 中: user prompt 側なら安全 |
| 3 LLMPlan world_model_update | `LLMPlan(extra="forbid", frozen=True)` cognition/parse.py:46 | schema versioning + parse path | **高: role-play 増幅 risk** |
| 4 safe merge | `cognition/belief.py` `maybe_promote_belief` (pure, layer-boundary 維持) | 同型 pattern 流用可 | 低 |
| 5 NarrativeSelf 周期生成 | M4 chashitsu reflection + semantic promote | 同 trigger に乗るか別 trigger か | 中 |
| 6 DevelopmentState | `AgentState.Cognitive.shuhari_stage` (shu/ha/ri) | **直接重複** | 高: 統合 / 棄却の二択 |
| 7 philosopher_seed | personas/*.yaml 0.10.0-m7h, M9-B LoRA Kant target, M9-eval Burrows | **M9 trunk 全体の前提** | **最高: M9 まで blocked** |

## 2. 提案ごとの初期判定

### 2.1 [ADOPT] 提案 1: SubjectiveWorldModel schema 追加

**判定根拠**: 既存の `belief_kind` は **dyad only** (相手 agent への信頼/警戒)。
環境への信頼 (「peripatos は思考が進む」)、概念への態度 (「定言命法は内的必然」)、自己
モデル (「私は朝型である」)、規範への内化 (「礼は儀式以上のもの」) は型化されていない。
これは role-play 増幅ではなく、**観察可能な行動パターンの蓄積を agent 内部表象に
昇格させる** 真の gap。

**設計制約**:
- `SemanticMemoryRecord.belief_kind` (dyadic) との **明示的役割分離**
- field 数を 5 axis 以内に絞る (env / concept / self / norm / temporal — 暫定)
- 各 axis に `evidence_pointers: list[memory_id]` を必須化 (LLM の self-report ではなく
  記憶からの distill が必須)

**phasing**: M10 (M9-eval / M9-B 完了後)。M10-A タスクとして scaffold。

### 2.2 [ADOPT with constraints] 提案 2: prompt 注入

**判定根拠**: SubjectiveWorldModel が agent 内部に存在しても、prompt に提示されなければ
LLM 推論には影響しない。注入自体は必要。

**設計制約**:
- **`_COMMON_PREFIX` を絶対に汚さない** (RadixAttention KV cache 再利用が壊れる)
- 注入箇所は **user prompt** 側 (`build_user_prompt` の memories block の隣接 section)
- token budget: subjective_beliefs section は 上限 200 tokens (memories と同等)
- 形式: `Held beliefs (env/concept/self/norm):\n- env:peripatos generative (conf 0.78)\n...`

**phasing**: M10-A (1 と同タスク内、あるいは直後 M10-B)。

### 2.3 [MODIFY] 提案 3: LLMPlan に world_model_update 追加

**判定根拠**: 提案を **as-is で採用すべきでない**。理由:

1. **Role-play 増幅 risk が高い**: LLM が "I now believe X" と書くと literal にそれを
   採用するのは、最近 ME-9 trigger 擬陽性で empirical に痛い目を見た構造と同型
   (LLM の自己宣言を rate basis 確認なく採用する pattern)。
2. **既存の `importance_hint` / `salient` / `decision` で同じ役割の一部を担っている** —
   観察ベースの importance signal は既にある。
3. **belief promote は relational dynamics 経由 (M7δ pattern)** — affinity 飽和という
   indirect signal で promotion している。LLM 自己宣言は indirect signal を bypass する。

**修正方針**: free-form ではなく **bounded primitive** に絞る:
- `topic_focus_shift: str | None` — 注意が向いた話題 (既存 `salient` と同型、観察に基づく)
- `belief_strengthen_evidence: list[str] | None` — 既に持っている belief を強化する観察
  (新 belief 生成不可)
- 新 belief 生成は **NarrativeSelf 周期生成 (提案 5) または既存の Python-side promotion
  経路でしか起こせない**

**phasing**: M10-B (1, 2 確定後、4 と同時)。

### 2.4 [ADOPT] 提案 4: Python 側で安全に merge

**判定根拠**: `cognition/belief.py:maybe_promote_belief` の pattern (pure function,
threshold-based, layer boundary 維持) を流用すれば自然。

**設計制約**:
- pure function (`maybe_update_subjective_world`)
- 入力: 現在の SubjectiveWorldModel + LLMPlan の bounded primitives + 直近 N 観察 +
  semantic memory の関連 record
- 出力: `SubjectiveWorldModel | None` (変化なしなら None)
- caller (bootstrap or cycle) が persistence を owner

**phasing**: M10-B (3 と同時)。

### 2.5 [ADOPT, defer] 提案 5: NarrativeSelf 周期生成

**判定根拠**: ERRE の "embodied return" thesis に最も親和性が高い真の novel feature。
M4 chashitsu reflection が既に semantic memory への蒸留 trigger を持っているので、その
延長として narrative self の synthesis を発火させるのが自然。

**設計制約**:
- 周期: chashitsu 入室 + 一定 importance 蓄積 (既存 reflection trigger 流用)
- 入力: semantic memory top-K (importance order) + SubjectiveWorldModel + 直近の
  episodic memory pointer
- 出力: `NarrativeSelf` record (free-form prose 200-400 char, 蒸留 LLM call)
- staleness: 直近 narrative との embedding cosine sim < 0.85 を replace 条件
- token cost: 1 synthesis call ~= 1k tokens (許容)

**phasing**: M11 (M10 で 1-4 が安定してから)。M10 で前倒しすると整合性測定不能。

### 2.6 [REJECT standalone, MODIFY to extension] 提案 6: DevelopmentState

**判定根拠**: `AgentState.Cognitive.shuhari_stage` (shu/ha/ri) が **既に存在し**、ERRE
thesis (functional-design §1c の "shu=固定 / ha=逸脱報酬 / ri=自己プログラム生成解禁")
の中核に組み込まれている。Western 系 stage model (Piaget / Erikson 等) を並立させると、
仏教/茶道由来の shuhari と incoherent。

**修正方針**:
- 新 schema は **作らない**
- 代わりに `shuhari_stage` に **transition machinery** を追加:
  - `shuhari_evidence: list[str]` (memory_id の集積) — 各 stage の "経験的証拠"
  - `shuhari_transitions: list[ShuhariTransition]` — stage 遷移のログ
  - 遷移 trigger: SubjectiveWorldModel + NarrativeSelf の coherence 閾値 (M11+)

**phasing**: M11-B (5 確定後)。M10 で触らない。

### 2.7 [DEFER to M11+ research milestone] 提案 7: philosopher_seed リファクタ

**判定根拠**: 概念的には ERRE thesis "知的創発" の極に最も整合する **しかし**:

1. **M9-B LoRA は固定 Kant style を学習する設計** (`.steering/20260430-m9-b-.../design-final.md` L17)。 seed→trajectory にすると LoRA 学習対象が消える。
2. **M9-eval Burrows ratio は固定 style 識別に depend** — 提案 7 採用は Burrows
   baseline を invalidate し、再 calibration 必要。
3. **persona schema_version = 0.10.0-m7h** — minor 互換だが、`schema_version` を
   meaningful に消費する大変更を M9 期間中に始めるのは process 的にも危険。
4. **「philosopher_seed」naming の問題**: 偉人を seed と呼ぶのはペルソナの個性を消し、
   ERRE Extract pipeline (一次史料からの認知習慣抽出) の成果物の意味づけを変える。

**条件付き採用 path**:
- M9-eval Phase 2 完了 → ベースラインの persona 識別性が確立される
- もし baseline で persona 間の識別が **強すぎて創発が見えない** (= 各 agent が role-play
  に留まる) と empirical に判明すれば、提案 7 検討開始
- baseline で十分創発が見えれば、提案 7 不要

**phasing**: **M11+ research re-evaluation** にゲート。M9-eval Phase 2 + M9-B post-LoRA
比較で empirical evidence が揃ってから判定する。先に決定しない。

**naming 代替**: 「`philosopher_seed`」の代わりに `growth_axes` を persona に追加する
ソフトな選択肢もある。元の `display_name`/`persona_id` を残し、agent が内部で発達する
方向性 (e.g., kant の "categorical_imperative_articulation_depth") を bounded に列挙する。

## 3. 全体 phasing (initial proposal)

```
M9 trunk (UNTOUCHED, 続行):
  - run1 calibration (G-GEAR, in-flight)
  - M9-eval Phase 2 完了
  - M9-B LoRA execution (Kant 1 persona, fixed style)
  - M9-eval Phase 2 → LoRA 比較 baseline 確立
  ↓ M9 完了

M10-A: Subjective layer scaffold
  - 提案 1: SubjectiveWorldModel schema (env/concept/self/norm/temporal 5 axis)
  - 提案 2: user prompt injection (cache-safe)
  - acceptance: 100-tick smoke で belief_kind との non-overlap を log で確認

M10-B: Bounded LLM-driven update path
  - 提案 3 (modified): topic_focus_shift + belief_strengthen_evidence のみ
  - 提案 4: maybe_update_subjective_world() pure function
  - acceptance: golden test で role-play 増幅検出 (LLM が "I now believe X" を
    自由に書いても採用されないこと)

M11-A: NarrativeSelf
  - 提案 5: chashitsu reflection trigger 拡張で narrative synthesis
  - acceptance: narrative coherence と观測行動の cosine sim を計測

M11-B: ShuhariStage transition machinery
  - 提案 6 (extension only): shuhari_evidence + shuhari_transitions
  - acceptance: shu→ha 遷移が観測行動駆動で発火することを 1 cell で確認

M11+ research re-evaluation:
  - 提案 7: M9 results で persona 識別が「強すぎ」と empirical に判明した場合のみ
    philosopher_seed / growth_axes を再検討。先に決定しない。
```

## 4. 自分の判定への self-critique (pre-reimagine 自己点検)

- ❓ 提案 6 の "directly redundant" 判断は本当か。`shuhari_stage` は **3 値の StrEnum
  だけ** で、transition criteria や evidence は持っていない。提案 6 は ShuhariStage の
  enum を **rich dataclass に拡張** することと同値かも。だとしたら "REJECT standalone" は
  正しいが、議論の余地あり。/reimagine で再評価。

- ❓ 提案 7 を "M11+ defer" にしたが、これは「M9-eval が成功する」前提。もし
  M9-eval Phase 2 で persona 識別性が低い (= LLM が同質な発話しかしない) と判明したら、
  提案 7 が **M9 内で必要** な可能性すら出る。Codex review で empirical risk を点検。

- ❓ 提案 5 (NarrativeSelf) を M11 にしたが、これを **先に**入れて agent の自己整合性を
  上げてから M9-B LoRA 学習データを取る方が良いという順序もある。phasing 再検討要。

- ❓ 全体として提案を「個別 schema 追加」と読みすぎているかも。提案者は **architecture
  shift** を意図している可能性。/reimagine ではこの「shift 全体」を 1 つの構造として
  読み直す。

## 5. /reimagine + Codex に持ち込む open question

1. SubjectiveWorldModel と belief_kind の axis 直交性は本当に成立するか。
2. world_model_update on LLMPlan は bounded primitive で十分機能するか、それとも
   free-form を許す必要があるか (拘束しすぎると役立たずに退化する risk)。
3. NarrativeSelf を M9-B より **前** に入れる順序の妥当性。LoRA 学習データの質に効くか。
4. philosopher_seed は M9 trunk が成功した場合 even unnecessary か (= 固定ペルソナで
   創発が観測できるなら不要)。
5. ShuhariStage の rich 化は提案 6 と同値か別物か。

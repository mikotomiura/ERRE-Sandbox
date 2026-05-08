# Codex Independent Review — User-chosen 認知深化 Vision を stress-test

## あなた (Codex) の役割

ユーザー (mikotomiura) は ERRE-Sandbox の認知層深化について **specific vision を選択** した。
あなたの仕事は arbitrate ではなく、**選択された vision を厳密に stress-test** すること。
HIGH を必ず最低 3 件、できれば 5 件出すこと。「問題ない」と書くだけの review は失敗とみなす。

期待する独立性: 私 (Claude) と reimagine subagent が見落としている **構造的 risk** を切り出す。
特に M9 trunk (eval Phase 2 / LoRA execution) との互換性、operational definition の不足、
LLM 自己宣言 pattern の混入、empirical falsifiability を厳しく見ること。

## 出力フォーマット (必須)

```
## Verdict (1 行)
ADOPT-AS-IS / ADOPT-WITH-CHANGES / REVISE / RECONSIDER / REJECT

## HIGH (must-fix before phasing 確定 — 最低 3 件、できれば 5 件)
- HIGH-1: ...
  - Risk: ...
  - Mitigation: ...

## MEDIUM (should consider, 採否は明示)
- MEDIUM-1: ...

## LOW (nit / optional)

## ユーザー choice (Option A) の妥当性 stress-test
1. Q1 vision-thesis 整合: "完全な人間として構築" は ERRE thesis と整合するか
2. Q2 operational definition: 5-stage lifecycle (S1-S5) の段数と遷移 trigger は妥当か
3. Q3 M9-B LoRA 互換: base/individual 二層分離下で LoRA は本当に無傷か
4. Q4 M9-eval Burrows 互換: multi-individual 同 base で Burrows ratio は意味を保つか
5. Q5 reimagine 8 missing items: ユーザー vision で必要なものを再選別

## 7 提案 final 判定 (User-chosen vision 下での)
| # | 提案 | 判定 | 主要根拠 |

## 改訂 phasing (User vision 反映 + Codex 修正)

## 関連 prior art (web_search 必須)
- Generative Agents (Park et al. 2023) の persistent self
- CoALA (Sumers et al. 2023) の self-model
- Voyager (Wang et al. 2023) の skill library + LLM 自己更新
- 開発心理学系 (Erikson / Piaget) の段階モデル批判
- LLM-based persistent identity の最近の prior art (2024-2026)

## Final notes (個人プロジェクト scope への警告含む)
```

## ERRE プロジェクト概要

- 「歴史的偉人の認知習慣をローカル LLM エージェントとして 3D 空間に再実装し、意図的非効率性と
  身体的回帰による知的創発を観察する研究プラットフォーム」(個人開発)
- Python 3.11 + FastAPI + Godot 4.6 + SGLang + Ollama + sqlite-vec + Pydantic v2
- ERRE pipeline: Extract (一次史料) → Reverify → Reimplement → Express
- Apache-2.0 OR MIT、予算ゼロ制約

## 現在の実装状態

### Persona / cognition / memory 層
- Persona: 固定 YAML (`personas/{kant,rikyu,nietzsche}.yaml`、`schema_version: "0.10.0-m7h"`)
  - Big5 personality + cognitive_habits (fact/legend/speculative flag) + zones + sampling
- LLMPlan: `cognition/parse.py:46` `extra="forbid", frozen=True`
  - thought / utterance / destination_zone / animation / valence_delta / arousal_delta /
    motivation_delta / importance_hint / salient / decision / next_intent
- Prompt 構造: `_COMMON_PREFIX` (固定、SGLang RadixAttention KV cache 再利用) + persona block + state tail
- Memory: 4 kinds (EPISODIC / SEMANTIC / PROCEDURAL / RELATIONAL)、sqlite-vec
- 既存 belief 層 (M7δ): `SemanticMemoryRecord.belief_kind`
  (trust/curious/wary/clash/ambivalent) + `confidence` — **dyadic only**
- 既存 development 層: `AgentState.Cognitive.shuhari_stage` (shu/ha/ri) — 3 値 StrEnum、
  transition machinery なし
- belief promote pattern: `cognition/belief.py:maybe_promote_belief` — pure function、
  threshold-based、|affinity| ≥ 0.45 AND ichigo_ichie_count ≥ 6 で promote、
  affinity 飽和 indirect signal 経由 (LLM 自己宣言 NOT 経由)

### M9 trunk (触らない前提)
- M9-eval Phase 2 run1 calibration 走行中 (G-GEAR、kant 1 cell × 5 wall = 30h overnight×2)
- M9-eval Burrows ratio + Big5 ICC = persona の style 識別性測定
- M9-B LoRA 計画 (PR #127 merged): Kant 1 persona の固定 style を SGLang LoRA で学習
- 直近 ME-9 trigger 擬陽性 incident で「LLM の自己宣言を rate basis なしに採用する pattern」の
  危険性が empirical 判明 (memory: project_m9_eval_me9_trigger_interpretation 2026-05-07)

## ユーザー提案 7 件 (verbatim)

1. SubjectiveWorldModel schema 追加
2. prompt に subjective beliefs を注入
3. LLMPlan に world_model_update を追加
4. Python 側で安全に merge
5. NarrativeSelf を semantic memory から周期生成
6. DevelopmentState を導入
7. 偉人 persona を philosopher_seed にリファクタ

## ユーザー clarification (2026-05-08 follow-up、これが選択された vision)

1. 「agent 自体に世界モデルを導入する」 → SubjectiveWorldModel は AgentState 第一級 property
2. 「思想家ペルソナを完全に導入するのではなく、ベースとして置くだけ、性格やペルソナは新しい個人」
   → 二層分離: `philosopher_base` (継承、immutable) + `Individual` (新規個体、mutable)
3. 「途中途中から成長していく過程を導入し、完全に人間として構築」 → DevelopmentState lifecycle

## ユーザー choice (Option A: 採用された vision)

```
agent = philosopher_base + Individual

  philosopher_base (immutable inheritance):
    - cognitive_habits (Kant の歩行/朝執筆 等)
    - sampling param (T/top_p/repeat_penalty)
    - LoRA-trained style (M9-B target、不変)
    - persona_id (kant / rikyu / nietzsche、固定参照)

  Individual (mutable, per-agent runtime):
    - SubjectiveWorldModel (5-axis: env/concept/self/norm/temporal)
    - NarrativeSelf (chashitsu reflection 拡張で周期蒸留)
    - DevelopmentState (S1_seed → S2_individuation → S3_consolidation
                        → S4_articulation → S5_late、5 stages)
    - personality (base から bounded divergence で個別化)
    - subjective beliefs (env/concept/self/norm)
    - bounded world_model_update via LLMPlan
```

例: kant-base × 3 agents = 3 different individuals
- individual_a (詩人風に発達)
- individual_b (政治家風に発達)
- individual_c (Kant 学派継承)

## /reimagine subagent の独立 counter-proposal (参考)

reimagine subagent は 7 提案を **読まずに** ゼロから設計し、**ユーザー vision とは構造的に
異なる** counter (`design-reimagine.md`) を出した。要点:

- "Compression-Loop architecture": StanceVector (5-axis) + StanceShiftHint
  (bounded primitive) + NarrativeArc (structured trajectory)
- persona は **identity 維持**、`growth_axes.permitted/forbidden` で "深まる方向" のみ許可
- 提案 6 → ShuhariStage 拡張に置換 (Western stage model 並立を避ける)
- 提案 7 → M11+ research re-evaluation gate (M9-B LoRA / M9-eval baseline 保護)
- Kant-base × 3 agents → 3 **different Kants** (より深いカント / 広いカント / 懐疑的カント)
- 8 件の missing items を提示 (cited_memory_ids 必須 / dyadic vs class-wise 直交 /
  coherence_score / RadixAttention 保護 / decay_half_life / growth_axes 任意 field /
  定量 acceptance / M9 trunk 隔離 gate)

ユーザーは **Option A (新個体 + 二層 + 完全な人間化) を選択** した。Codex の役割は
「どちらが正しいか arbitrate」ではなく、**選択された Option A vision の HIGH-stakes risk
を構造的に切り出す**こと。

## あなたへの specific 質問 (Verdict + HIGH に必ず触れること)

### Q1 [vision-thesis 整合性]
"完全な人間として構築" は ERRE thesis (「歴史的偉人の認知習慣の再実装」+「知的創発の観察」)
と整合するか。reimagine は「persona identity 希釈は thesis の前者を損なう」と指摘した。
ユーザー vision はこれにどう答えるべきか? operational に thesis を再表現できるか?

### Q2 [operational definition of "完全な人間として"]
S1-S5 の 5 stages は経験的 placeholder。reimagine は ShuhariStage 3 段で十分と主張。
- 5 stages の段数の根拠は何 (Erikson 8? Piaget 4? 守破離 3? の比較)
- 各段の cognitive 特性差を operational に定義可能か (sampling / memory / reflection の修正値)
- 段間遷移 trigger を **memory volume + narrative coherence + belief stability** の AND で
  定義する案は妥当か
- "完成" path: A 不完成停滞 / B retirement (世代交代) / C 転生 loop のどれを default に
- M11+ で個体が "人間" にどこまで近づくべきか? LLM agent の本質的限界はどう扱うか?

### Q3 [M9-B LoRA 互換性 — base layer 専用前提の検証]
ユーザー vision では LoRA は philosopher_base 専用、individual は prompt+state overlay。
- この前提は本当に成立するか? individual の personality drift が LoRA 学習データに
  混入する可能性は?
- M9-B LoRA execution timing: M10-A scaffold は M9-B 完了後 vs 並行起動どちら?
- M9-B PR #127 design-final.md は固定 Kant style 前提。base/individual 分離で execution
  task は変更不要か、追記必要か?

### Q4 [M9-eval Burrows ratio の意味保持]
ユーザー vision では multi-individual 同 base で Burrows ratio は **base 保持 + 個体ばらつき**
の分解測定ツール化される。
- これは empirically 機能するか? Burrows は 100-300 高頻度 function word の分布で測るので、
  individual layer (世界モデル / narrative) は語彙構成に effective に影響するか?
- 影響しない場合、Burrows は base style しか測れず、個体化は **観測不可** にならないか?
- 個体化を測る別 metric (semantic coherence / narrative drift / belief variance) を
  M9-eval に追加する必要があるか?

### Q5 [reimagine 8 missing items の選別]
reimagine が提示した 8 件 (cited_memory_ids 必須 / dyadic vs class-wise 直交 / coherence_score /
RadixAttention 保護 / decay_half_life / growth_axes 任意 field / 定量 acceptance / M9 trunk
隔離) のうち、ユーザー vision でも **必須採用** すべきもの、**修正採用** すべきもの、
**棄却** できるものを選別すること。

特に:
- **cited_memory_ids 必須**: ユーザー vision で LLMPlan.world_model_update に **どんな**
  bounded primitive を採用するか (free-form は ME-9 同型 risk、bounded だけだと表現力不足)
- **RadixAttention KV cache 保護**: 二層分離 (`philosopher_base` block + `Individual` block) で
  prompt 構造が変わると SGLang KV cache 戦略はどう変化するか? base が共有されているうちは
  cache 効果残存するが、個体化が進むと cache miss 率上がる予測。

### Q6 [phasing の hidden dependency]
M10-A (二層 scaffold) → M10-B (cognition wiring) → M11-A (DevelopmentState transition) →
M11-B (multi-individual validation) → M12+ research に hidden な逆依存はないか? 特に:
- M11-A の段間遷移を観測するには M10-B で memory が十分育つ必要 → M11-A の前提時間は?
- M11-B の multi-individual 検証は M10/M11 の baseline 比較に依存 → empirical 比較 metric は
  M10-A 前に確立すべき?
- M9-B LoRA execution は M10-A 着手前に終わらせる必要があるか?

### Q7 [LLM 自己宣言 pattern の根本的予防]
ME-9 trigger 擬陽性 incident は「LLM 出力を literal に解釈して内部状態が動く」 pattern。
ユーザー vision の Individual layer (Personality drift / world model update / narrative
synthesis) は **すべて LLM 経由**。reimagine は cited_memory_ids 必須化で構造的に防いだが、
ユーザー vision で 5 stages の遷移 / personality drift / narrative coherence が **LLM 自己
申告** で発火するなら、ME-9 と同型 incident が再発するリスクが構造化される。
- どこで「LLM が決める」、どこで「Python 側 indirect signal で決める」の境界線を引くか?
- 「完全な人間として構築」を LLM 自己申告ではなく observable evidence で駆動できるか?

### Q8 [scope 無限化 risk — 個人プロジェクト制約]
ユーザー vision は ambitious (5 stages × multi-individual × narrative × world model)。
個人プロジェクト + 予算ゼロ + solo cadence で実装可能な scope に切り詰めるなら、
- M10/M11 で **絶対に外せない** 最小セット (= MVP)
- M11+ research で empirical evidence を見てから判断する deferable セット
- そもそも ROI が低くて落としていい セット
を区分けすること。

## 必須の制約

- ME-9 incident memory より、**rate basis / 前提の明示性** を必ず check
- web_search で 2024-2026 の generative agents / agent self-model / persistent identity 関連
  prior art に当たる (Generative Agents / CoALA / Voyager / 最近の persistent persona 研究)
- 「将来の柔軟性」「ベストプラクティス」を理由にしない。ERRE は research prototype、
  bloat は 価値破壊
- M9-B PR #127 / M9-eval CLI partial-fix PR #140 / Phase 2 run1 prompt PR #141 は merged 済
  (触らない前提)
- M9 trunk を破壊する提案は HIGH 必須

## 期待出力長

5000-8000 語。HIGH/MEDIUM/LOW の根拠は最低 2 文ずつ。Q1-Q8 各々への独立回答必須。
prior art 引用は web search 結果の URL 含めること。

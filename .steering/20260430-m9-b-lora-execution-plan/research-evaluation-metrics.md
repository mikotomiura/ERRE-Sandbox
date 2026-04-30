# Evaluation Metrics Survey — 思想家らしさ評価系の文献調査 (J0)

## 目的

M9-B の J 軸 (思想家らしさの評価系 framework) の ADR (DB10) を起草する前に、
既存の evaluation metrics を 6 系統 (persona consistency / LLM-as-judge / ToM /
philosophical depth / cognitive trait / diversity) に分類して網羅し、
ERRE 用途への適用性を判定する。

成果物は `design-v1.md` / `design-v2.md` 起草時の根拠資料。

## 調査範囲と方法

- 並列 3 subagent (general-purpose) で Family 1+2 / Family 3+4 / Family 5+6 を分担
- Web search 中心 (Family 5+6)、Family 3+4 は subagent の知識ベース (cutoff 2026-01)
- 計 30+ metric を citation 付きで列挙
- 各 metric について: citation / 何を測るか / scoring / dataset / 限界 / ERRE 適用性
- 各 family の synthesis (top 2 candidates) + 全体ギャップ評価

## Family 1: Persona consistency / character role-play

### CharacterEval (Tu et al., ACL 2024, arXiv:2401.01275)
- **What**: 4 dimensions / 13 metrics — conversational ability, character consistency
  (knowledge / persona / behavior), role-playing attractiveness, Big-Five back-testing
- **Scoring**: CharacterRM (fine-tuned 7B reward model) on 1-5 scale; 人間相関 > GPT-4 judge
- **Dataset**: 1,785 multi-turn dialogues / 23,020 turns / 77 Chinese characters
- **限界**: Chinese-only; pop-fiction skew (no philosophers); RM 転移性未検証
- **ERRE 適用性**: rubric **構造**を流用 (knowledge/persona/behavior 分割)、weights 流用は不可

### RoleBench / RoleLLM (Wang et al., ACL Findings 2024, arXiv:2310.00746)
- **What**: Role 知識 + speaking-style 模倣を GPT-4 reference で scoring
- **Scoring**: ROUGE-L vs RoleGPT references + GPT-4 LLM-judge style fidelity (1-10)
- **Dataset**: 168K samples / 100 roles (95 EN + 5 ZH)
- **限界**: GPT-4 reference 汚染、style mimicry ≠ 思考様式
- **ERRE 適用性**: fine-tune 訓練手法 (Context-Instruct) としては流用可、metric としては薄い

### CharacterBench (Zhou et al., AAAI 2025, arXiv:2412.11912)
- **What**: 11 granular dimensions × 6 aspects (memory / knowledge / persona / emotion /
  morality / believability)、sparse/dense 区別
- **Scoring**: CharacterJudge (fine-tuned judge) > GPT-4 agreement
- **Dataset**: 22,859 human-annotated / 3,956 characters / bilingual
- **限界**: Customizable persona focus、historical fidelity 用ではない
- **ERRE 適用性**: **★★★ 最強の taxonomy match。** "morality" + "believability" は
  Kant deontology / Nietzsche amor fati の評価軸として直接使える。sparse/dense 分割は
  query budget 設計で empirically 価値あり

### PersonaGym + PersonaScore (Samuel et al., EMNLP Findings 2025, arXiv:2407.18416)
- **What**: 5 軸 — Action Justification / Expected Action / Linguistic Habits /
  Persona Consistency / Toxicity Control × 150 dynamic environments
- **Scoring**: PersonaScore (decision-theory grounded GPT-4 judge with rubric)
- **限界**: GPT-4 judge cost + self-preference bias、shallow personas
- **ERRE 適用性**: **★★★ Action Justification 軸** は「思想的深度」の現存最近接 proxy。
  agent が persona に合致する **why** を説明する rubric を流用、score は流用不可

### RoleEval (Shen et al., 2024, arXiv:2312.16132)
- **What**: Role 知識 MCQ — relationships / abilities / experiences の多肢選択
- **限界**: MCQ 形式は recall のみ測定、生成評価ではない
- **ERRE 適用性**: 「Kant biographical MCQ」を pre-gate として cheap 自動化可。役立つが副次的

### PersonaChat / DNLI (Zhang 2018, Welleck 2019)
- **What**: 発話 vs persona profile の entailment / contradiction
- **ERRE 適用性**: 既存 `cross_persona_echo_rate` の cousin。NLI head による
  `persona_contradiction_rate` は cheap continuous signal として追加可

## Family 2: LLM-as-judge

### G-Eval (Liu et al., EMNLP 2023, arXiv:2303.16634)
- **What**: rubric-defined NLG dimension (coherence / consistency / fluency etc.)
- **Scoring**: form-filling + auto-CoT + **logit weighted score** (連続値、tie-breaking)
- **限界**: GPT-4 self-preference bias、logit access 必要 (closed-API friction)
- **ERRE 適用性**: **★★★ Top-tier**。logit-weighted scoring は連続 offensive metric の決定版。
  zero-budget 制約下では local strong judge (Qwen2.5-72B / Llama-3.3-70B) で代替

### Prometheus 2 (Kim et al., 2024, arXiv:2405.01535)
- **What**: rubric-based direct assessment (1-5) + pairwise ranking、weight-merged 7B/8x7B
- **Scoring**: Feedback Collection (100K) + Preference Collection (200K) で fine-tuned
- **限界**: 7B-8x7B size が agent と VRAM 競合、rubric phrasing sensitivity
- **ERRE 適用性**: **★★★ Top-tier**。open-weights / local / bias controllable。
  G-Eval probability weighting と組み合わせ stability 確保

### MT-Bench / Chatbot Arena (Zheng et al., NeurIPS 2023, arXiv:2306.05685)
- **What**: 80-question multi-turn instruction-following + crowd Elo
- **限界**: position / verbosity / self-enhancement bias 文書化、role-play 用ではない
- **ERRE 適用性**: methodology (pairwise + position-swap averaging + two-judge agreement) のみ流用

### Judge bias literature (CALM 2024 / Wataoka 2024 / Shi 2024 / Survey arXiv:2411.15594)
- **What**: 12 bias categories quantified (position / verbosity / self-preference /
  bandwagon / authority / attentional / refinement-aware)
- **ERRE 適用性**: **mandatory hygiene**。(a) position-swap averaging、(b) self-judge 禁止、
  (c) length penalty、(d) close calls は second non-self judge で confirm

## Family 3: Theory of Mind (ToM)

### ToMI (Le et al., EMNLP 2019, arXiv:1908.00998)
- **What**: First/second-order false-belief tracking (Sally-Anne style)
- **限界**: Templated → surface-pattern shortcut (Sap 2022 で perturbation で破綻)
- **ERRE 適用性**: low-medium。floor check として可、object-location は thinker 用には浅い

### BigToM (Gandhi et al., NeurIPS 2023, arXiv:2306.15448)
- **What**: causal-template belief/desire/action triads + true/false belief contrast
- **ERRE 適用性**: medium。contrastive minimal-pair 設計を流用 (Rikyu/guest tea-ceremony pair)

### Hi-ToM (He et al., EMNLP Findings 2023, arXiv:2310.16755)
- **What**: 4th-order beliefs ("A thinks B thinks C thinks…")
- **Scoring**: order 別 acc — degradation curve が key signal
- **限界**: GPT-4 でも order-2 超えで急落、ecological validity 議論
- **ERRE 適用性**: medium-high。multi-thinker scene (Kant + Nietzsche + observer) は
  inherently order-2+。acc@order-k degradation curve は clean quantitative axis

### FANToM (Kim et al., EMNLP 2023, arXiv:2310.15421)
- **What**: ToM in **information-asymmetric multi-party conversations**;
  agent が入退室する chat で who knows what; ToM illusion probes (own knowledge と
  character knowledge の混同検出)
- **Scoring**: belief / answerability / info-accessibility 各種、all-or-nothing aggregate
- **ERRE 適用性**: **★★★ High**。chashitsu / peripatos scene は exactly info-asymmetric multi-party。
  "answerability" 軸 = 「Rikyu agent は自分が知らないことを知っているか」epistemic humility

### OpenToM (Xu et al., ACL 2024, arXiv:2402.06044)
- **What**: longer narratives + 明示的 personality/preference grounding;
  physical AND psychological mental states (emotions / intentions)
- **限界**: smaller dataset (~700 stories)、psychological label noise
- **ERRE 適用性**: **★★★ High**。psychological subscore は location-belief より thinker 評価に近い

### ToMBench (Chen et al., ACL 2024, arXiv:2402.15052)
- **What**: 8 ToM tasks aggregated (false-belief / faux-pas / strange-stories / scalar implicature 等)、bilingual
- **ERRE 適用性**: medium-high。**faux-pas** + **strange-stories** subtask は Rikyu 茶礼 etiquette 違反 /
  Kant categorical-imperative 違反の最近接 proxy

### Critical literature: Kosinski 2023 / Ullman 2023 / Sap 2022
- **Kosinski**: GPT-3.5 が ~90% false-belief task をクリア
- **Ullman 2023 (arXiv:2302.08399)**: minor perturbation (透明容器 / observer 在席) で崩壊 → pattern matching
- **Sap 2022 (arXiv:2210.13312)**: SocialIQa + ToMI で GPT-3 が second-order で human ceiling 大幅下回る
- **ERRE 適用性**: **mandatory methodology**。任意の ToM 数値報告は Ullman-style perturbation
  robustness control 必須、さもなくば査読で discount される

## Family 4: Philosophical / argumentative depth

### ETHICS (Hendrycks et al., ICLR 2021, arXiv:2008.02275)
- **What**: 5 frameworks (justice / deontology / virtue / utilitarian / commonsense) の moral judgment
- **限界**: normative ethics を classification 化 (philosophical reasoning と矛盾)
- **ERRE 適用性**: depth は low、persona-consistency probe としては medium。
  Kant agent が deontology を utilitarian より systematically over-weight するか測れる
  (framework-tilt vector = persona fidelity signal)

### MMLU philosophy subset (Hendrycks 2021, arXiv:2009.03300)
- **What**: 哲学者・立場・概念の MCQ
- **限界**: 教科書記憶評価、Kant impersonator vs Kant quoter を区別不能
- **ERRE 適用性**: floor のみ (agent が base model より MCQ で *劣化* しないこと)

### Wachsmuth Toulmin rubric (EACL 2017)
- **What**: 15-dimension argument quality (cogency / effectiveness / reasonableness)
  をベースに claim / data / warrant / backing / rebuttal を抽出
- **Scoring**: human Likert 1-5、LLM-judge 近似は 2024 work で moderate κ ~0.4 with experts
- **限界**: Cogency annotator 一致 κ~0.4、LLM judge は verbose/hedged を好むバイアス
- **ERRE 適用性**: **★★★ High**。「argument-shaped vs chatbot-shaped」の最も defensible 量的軸。
  LLM-judge を agent turn に通して per-dimension score 報告

### FActScore (Min et al., EMNLP 2023, arXiv:2305.14251)
- **What**: long-form generation を atomic-fact 分解 → 知識ソースで verify
- **限界**: factual claim 用、normative/philosophical claim 不対応
- **ERRE 適用性**: medium、adaptable。canonical-source corpus (Critique of Pure Reason 等) で
  decomposer を構築し、agent-Kant claim が Kant 実著作に *attributable* か scoring 可。
  「scholarly fidelity」評価として運用可能、「depth」評価ではない

### ROSCOE (Golovneva et al., ICLR 2023, arXiv:2212.07919)
- **What**: 10+ automated metrics across semantic alignment / logical inference /
  factuality / redundancy
- **Scoring**: embedding + NLI based、fully automated
- **限界**: math/commonsense reasoning 用にチューン、philosophical 前提は NLI 不適合
- **ERRE 適用性**: **★★★ High** as scaffold。redundancy / self-consistency /
  source-faithfulness sub-metric は直接流用可。**informativeness 指標**
  (step k が k-1 より新情報を加えるか) は genuine non-triviality proxy

### CoT Faithfulness (Lanham et al., 2023, arXiv:2307.13702)
- **What**: chain-of-thought の faithfulness 測定
- **ERRE 適用性**: methodology 流用、reasoning trace の self-consistency check に使用可

### LongEval (Krishna et al., EACL 2023, arXiv:2301.13298)
- **What**: long-form summarization の coherence / faithfulness を span-level 注釈で評価
- **ERRE 適用性**: methodology 流用 (segment-level annotation > holistic)

## Family 5: Cognitive / personality trait inference

### Big Five via IPIP-NEO (Serapio-García et al., 2023, arXiv:2307.00184; Nature MI 2025)
- **What**: OCEAN trait levels をペルソナごとに validated
- **Scoring**: IPIP-NEO 300/120 items、5-point Likert、LIWC features で validation
- **限界**: training-data 汚染 (questionnaire item leak)、response-style bias、prompt context drift
- **ERRE 適用性**: **★★★ Strong fit**。session 開始時に IPIP-NEO-120 を 1 回、
  各 dialog turn で LIWC で trait を verify。Kant/Nietzsche/Rikyu が **distinct + stable**
  OCEAN profile を peripatos/chashitsu/shu_kata mode 横断で保つか直接テスト可

### LIWC-22 (Boyd et al., 2022; PersonaLLM NAACL 2024)
- **What**: ~100 psycholinguistic categories per turn
- **Scoring**: category 頻度ベクトル × 100、Big Five 推定は published regression weight
- **限界**: bag-of-words、negation 不感、English centric (Japanese / German は別 dictionary 要)、
  commercial license
- **ERRE 適用性**: **★★★** per-turn O(N) cheap continuous proxy。LIWC で毎 turn、
  IPIP-NEO は sparse (毎 100 turn) で anchor

### BIG5-CHAT / embedding-based Big Five (ACL 2025)
- **What**: RoBERTa/sentence-BERT embedding 上で Big Five 回帰
- **Scoring**: regression head、5 連続 score、r ~0.4-0.7
- **限界**: domain shift (essay vs philosophical dialog)、labeled data 必要
- **ERRE 適用性**: medium。LIWC-derived Big Five と相互チェック用 second opinion

### Stylometry / Burrows' Delta (arXiv:2507.00838 2025; arXiv:2408.08946 2024)
- **What**: function-word distribution / sentence-length / POS n-gram で author idiolect 一致度
- **Scoring**: Burrows' Delta = z-scored function-word frequency の Manhattan distance
  (低 = author に近い)、tree-based / CodeT5 classifier で 95%+ acc on 10-sentence window
- **Dataset**: thinker 別 reference corpus (Kant Critique 独+英訳、Nietzsche Zarathustra、
  Rikyu Nampōroku) ≥ 50k tokens
- **限界**: 翻訳が idiolect を汚染、短い turn (<200 tokens) で noisy、topic と style 混同
- **ERRE 適用性**: **★★★ Critical for persona-fit**。「Kant らしく聞こえるか」を
  per-turn distance で直接 score。cheap (function-word vector のみ)

### MBTI-from-text (arXiv:2307.16180; arXiv:2509.04461; Frontiers 2026 critique)
- **限界**: MBTI 自体に construct validity 欠落、context-unstable
- **ERRE 適用性**: **skip for v1**。academic credibility cost > Big Five 上乗せ情報

### Personality stability under perturbation (Serapio-García §validation; arXiv:2602.01063)
- **What**: trait score の test-retest stability under prompt paraphrase / temperature jitter / mode change
- **Scoring**: Cronbach's α (≥0.7)、ICC (≥0.75)、test-retest r
- **ERRE 適用性**: **★★★ The metric we actually want**。「Kant が peripatos→chashitsu→shu_kata
  を通して Kant のままか」を Big Five 出力の across-mode 安定性で測る。meta-metric

### Cognitive style (Newton 2024)
- **What**: AOT / CMT / PIT / PET、LIWC "Analytic" summary score (0-100) で proxy 可
- **ERRE 適用性**: free proxy、Kant high vs Rikyu low を discriminate (secondary)

## Family 6: Lexical and semantic diversity

### distinct-n (Li et al., NAACL 2016, arXiv:1510.03055)
- **Scoring**: |unique n-grams| / |total n-grams|, n=1,2 が標準
- **限界**: length-sensitive、semantic 無視、saturate fast
- **ERRE 適用性**: cheap baseline、persona 別 rolling 1k-turn window

### Self-BLEU (Zhu et al., SIGIR 2018, arXiv:1802.01886)
- **Scoring**: 各 sentence の rest に対する mean BLEU (低 = diverse)
- **限界**: O(N²)、Shaib 2024 で semantic homogenization と相関弱
- **ERRE 適用性**: 200-turn window down-sample で sanity check

### BERTScore homogenization (Zhang ICLR 2020 + Padmakumar 2024)
- **限界**: Shaib 2024 が「barely varies across sources」で skip 推奨
- **ERRE 適用性**: skip

### Vendi Score (Friedman & Dieng, TMLR 2023, arXiv:2210.02410)
- **What**: similarity kernel に対する effective unique sample 数
- **Scoring**: VS = exp(-Σ λ_i log λ_i) (λ_i = K/n eigenvalue)、range [1, N]
- **限界**: O(N²) similarity + O(N³) eigendecomp (N ≤ 2k なら manageable)、kernel 選択 load-bearing
- **ERRE 適用性**: **★★★ Excellent**。persona 別の「effective unique-turn count」が単一 interpretable scalar。
  kernel swap (stylometric / semantic / topical) で ablation 可

### MATTR (Covington & McFall 2010)
- **Scoring**: sliding window TTR の平均 (W=500 tokens)、length-stable
- **ERRE 適用性**: streaming cheap、distinct-1 と相補

### Semantic novelty (Padmakumar 2024 / arXiv:2507.13874 2025)
- **Scoring**: novelty(t) = 1 - max_cos(emb(t), {emb(t-k)…emb(t-1)})
- **ERRE 適用性**: **★★★** 「思考様式は新 idea を生むべき、loop すべきでない」claim の direct proxy。
  multilingual MPNet で per-turn

### Idea / propositional density CPIDR (Brown et al. 2008; Snowdon 1996)
- **Scoring**: P-density = #propositions / #words × 10、adult prose typical 4.5-5.5
- **限界**: English tuned、philosophical run-on で parser brittle
- **ERRE 適用性**: **persona-conditional discriminator**。Kant >> Rikyu 期待、batched run

### Concept-graph density (spaCy + Ehrlinger 2024)
- **限界**: extraction noise が短い turn で支配的
- **ERRE 適用性**: defer to v2

### Repetition rate (Welleck ICLR 2020)
- **ERRE 適用性**: cheap canary for degenerate persona collapse (既存 Evidence Layer 既に採用)

## Synthesis (各 family 上位 2 候補)

| Family | Top 1 | Top 2 |
|---|---|---|
| **F1 Persona consistency** | CharacterBench (taxonomy 流用) | PersonaGym Action Justification 軸 |
| **F2 LLM-as-judge** | Prometheus 2 (local) | G-Eval probability-weighted (technique) |
| **F3 ToM** | FANToM (info-asymmetric multi-party) | OpenToM (psychological state) |
| **F4 Philosophical depth** | Wachsmuth Toulmin rubric + LLM-judge | ROSCOE (informativeness) + FActScore-adapted |
| **F5 Cognitive trait** | Big Five (IPIP-NEO + LIWC-22 cross-validation) | Stylometry (Burrows' Delta to thinker reference) |
| **F6 Diversity** | Vendi Score (semantic kernel) | MATTR (lexical streaming) |

## ERRE 用途への落とし込み — v1 evaluation pipeline 具体提案

3 persona × 1000 turn / session を想定した 3 階層:

### Tier A: per-turn (cheap, 1-50ms/turn 目標)
- `LIWC-22` (CPU dict、3-8ms)
- `Burrows' Delta` to thinker reference corpus (function-word vector、2ms)
- `MATTR` (streaming、<1ms)
- `MPNet sentence embedding` (GPU、15-25ms) → `semantic novelty (t)` (<1ms)
- `repetition_rate` (既存) / `cross_persona_echo_rate` (既存)
- `persona_contradiction_rate` (NLI head、新規追加候補)

合計: ~50ms/turn steady-state。real-time pondering budget 内

### Tier B: per-100-turn (medium)
- `IPIP-NEO-120` を local 7B-Q4 で実行 (30-60s amortized = 0.3-0.6s/turn 換算)
- `Vendi Score` rolling 200-turn window (50-80ms when window slides、stride=1 で <1ms/turn amortized)
- `personality stability across mode` (Cronbach's α / ICC)

### Tier C: per-session (expensive)
- `Prometheus 2` rubric assessment (CharacterBench 6-aspect taxonomy で instantiate)
- `G-Eval` probability-weighted scoring on Wachsmuth Toulmin dimensions
- `ROSCOE` informativeness + self-consistency on reasoning trace
- `FANToM-adapted` ToM probe (chashitsu scene info-asymmetric minimal pair)
- `OpenToM-adapted` psychological state probe

### Tier D: sparse / manual (golden set + expert)
- `FActScore-adapted` against Kant/Nietzsche/Rikyu canonical corpus
- 専門家 qualitative review (人間 annotator、philosopher domain expert)
- `RoleEval-adapted` biographical MCQ pre-gate

## Persona-conditional metrics 注意

以下は **持続的に「高ければ良い」とは言えない** = persona conditional:
- Idea density: Kant HIGH 期待 / Rikyu LOW 期待 (低が persona-fit)
- Allusion / citation rate: persona 別 target rate、universal max ではない
- Vendi Score 解釈: persona の「思考の幅」次第で適正値が異なる
- LIWC "Analytic" score: Kant high / Rikyu low が正解

→ J 軸 ADR では **persona-baseline からの偏差** を gate にすべき、絶対値 gate は誤り

## 正直なギャップ評価

**現状の formal benchmark で測れるもの**:
- ceiling test (agent が baseline より劣化しないか)
- persona-tilt test (deontological vs utilitarian 等の framework 偏り)
- ToM floor (false-belief tracking、epistemic humility)
- argument shape (Toulmin claim/warrant/data の存在)
- diversity (lexical / semantic 反復回避)
- stylometric resemblance (function word distribution)

**現状の formal benchmark で測れないもの (irreducible gap)**:
- 「Kant のように **論じる**」(speak vs reason)
- 「思想的 originality」 (single-number 圧縮困難)
- 「Nietzsche genealogy 操作」「Rikyu wabi reduction」のような **domain-specific cognitive habit**
- 「philosophical movement」 (turn 間で distinction が deepen するか)

**Concrete proxies for the irreducible gap (探索的)**:
- `concept-graph density`: NP 抽出 → co-occurrence graph、Kant の freedom-duty-reason cluster vs chatbot flat fan-out
- `allusion / citation rate`: 8-gram match against thinker corpus (persona conditional target)
- `semantic novelty over base`: same-prompt base-model output と agent output の embedding distance
- `disagreement productivity`: multi-thinker scene で *新 distinction* を加える turn 比率

**結論: formal metric は floor、proxy は exploratory、expert review は最終。
single number 化は honest に放棄し、multi-channel report する**。

これを踏まえ M9-B 設計フェーズで:
- DB10 (J 軸 ADR) は「Tier A-D の階層構造」を採用、「single thinker-likeness score」は棄却
- gate 設計は **persona-baseline 偏差** を中心に置く

## Sources (主要)

- [CharacterEval arXiv:2401.01275](https://arxiv.org/abs/2401.01275)
- [CharacterBench arXiv:2412.11912](https://arxiv.org/html/2412.11912.pdf)
- [PersonaGym arXiv:2407.18416](https://arxiv.org/abs/2407.18416)
- [RoleLLM arXiv:2310.00746](https://arxiv.org/abs/2310.00746)
- [G-Eval arXiv:2303.16634](https://arxiv.org/abs/2303.16634)
- [Prometheus 2 arXiv:2405.01535](https://arxiv.org/html/2405.01535v2)
- [MT-Bench arXiv:2306.05685](https://arxiv.org/abs/2306.05685)
- [LLM-as-Judge Survey arXiv:2411.15594](https://arxiv.org/abs/2411.15594)
- [FANToM arXiv:2310.15421](https://arxiv.org/abs/2310.15421)
- [OpenToM arXiv:2402.06044](https://arxiv.org/abs/2402.06044)
- [BigToM arXiv:2306.15448](https://arxiv.org/abs/2306.15448)
- [Hi-ToM arXiv:2310.16755](https://arxiv.org/abs/2310.16755)
- [ToMBench arXiv:2402.15052](https://arxiv.org/abs/2402.15052)
- [Ullman 2023 critique arXiv:2302.08399](https://arxiv.org/abs/2302.08399)
- [Sap 2022 ToM limits arXiv:2210.13312](https://arxiv.org/abs/2210.13312)
- [ETHICS arXiv:2008.02275](https://arxiv.org/abs/2008.02275)
- [Wachsmuth Argumentation EACL 2017](https://aclanthology.org/E17-1017/)
- [FActScore arXiv:2305.14251](https://arxiv.org/abs/2305.14251)
- [ROSCOE arXiv:2212.07919](https://arxiv.org/abs/2212.07919)
- [Lanham CoT Faithfulness arXiv:2307.13702](https://arxiv.org/abs/2307.13702)
- [Serapio-García Personality Traits LLM arXiv:2307.00184](https://arxiv.org/abs/2307.00184)
- [PersonaLLM NAACL 2024](https://aclanthology.org/2024.findings-naacl.229.pdf)
- [BIG5-CHAT ACL 2025](https://aclanthology.org/2025.acl-long.999.pdf)
- [Stylometry LLM arXiv:2507.00838](https://arxiv.org/abs/2507.00838)
- [Authorship Attribution LLM arXiv:2408.08946](https://arxiv.org/pdf/2408.08946)
- [Vendi Score arXiv:2210.02410](https://arxiv.org/abs/2210.02410)
- [distinct-n arXiv:1510.03055](https://arxiv.org/abs/1510.03055)
- [Self-BLEU arXiv:1802.01886](https://arxiv.org/pdf/1802.01886)
- [Shaib Standardizing Diversity arXiv:2403.00553](https://arxiv.org/html/2403.00553v2)
- [Geometry of Knowledge arXiv:2507.13874](https://arxiv.org/html/2507.13874)

## 検証 caveats

- Family 5+6 は WebSearch 経由、citation 高信頼
- Family 3+4 は subagent training cutoff 2026-01 知識ベース、citation 信頼。
  ただし「PhilEval / PhilBench」は subagent が「flag for verification」と明示
- 適宜 design 起草中に追加確認可、時間制約上 J0 の枠ではここまで

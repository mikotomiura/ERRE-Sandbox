Reading prompt from stdin...
OpenAI Codex v0.125.0 (research preview)
--------
workdir: /Users/johnd/ERRE-Sand Box
model: gpt-5.5
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR, /Users/johnd/.codex/memories]
reasoning effort: xhigh
reasoning summaries: none
session id: 019e2b24-3f1c-7742-aeb4-796be1378de8
--------
user
# Codex 13th independent review request — pre-M10 design synthesis (Hybrid-A revised)

> 投げるモデル: `gpt-5.5` codex CLI、reasoning effort `xhigh`
> Verdict format: ADOPT / ADOPT-WITH-CHANGES / BLOCK / REJECT のいずれかを明示し、HIGH/MEDIUM/LOW finding を列挙
> 期待 token 範囲: 200K-300K
> 投げる context: 本 prompt + `design-final.md` + `design-original.md` + `design-reimagine.md` + `decisions.md`

---

## §1. Context

ERRE-Sandbox プロジェクトの M10 milestone 着手前に、評価体制 (Individuation metrics + Social Theory-of-Mind + Counterfactual perturbation + Emotional alignment) の concrete + robust design を行った。User 直接指示「m10 では具体的に ToM などを含めた評価体制を具体的に強固に設計してから決めてください」(2026-05-15) を受け、placement-first から design-first に逆転。

Plan mode 内で次の手順を踏んだ:
1. `design-original.md` (capability-oriented scenario-lib、506 行) を起草
2. `/reimagine` 規約に従い `design-reimagine.md` (process-trace + power-first) を意図的に異視点でゼロから起草、両案を並列保持
3. `design-final.md` で §A 対照 + §B Hybrid 採用 (Hybrid-A revised) + §C-§H concrete design を確定
4. M10-0 sub-task が 3 → 2 に縮小 (Social-ToM 専用 sub-task `m10-0-social-tom-eval` を廃止、Layer 2 を main に統合)

本 prompt は本セッションの最終 stress-test 工程。Codex 13th independent review として、本 hybrid 採用の structural soundness、Layer 2 metric の sufficient statistic 性、`metrics.individuation` への dotted namespace 統合の DB11 sentinel 整合性、Hybrid-A revised が ADR-PM-2 を再 revise することの ADR 整合性、M11-C handoff 文書としての WP11 4 scenario spec の十分性を、特に切り出してほしい。

実装着手は次セッション以降。本 review の HIGH 反映後に `m10-0-individuation-metrics` task scaffold を起こす。

## §2. 採用 (Hybrid-A revised) の構造 (要旨)

### Layer 構造

```
Layer 1: Individuation  (v2 §2.2 matrix 11 metric、design-original/reimagine 共通)
Layer 2: Cite-Belief Discipline  (reimagine §2.2 由来、3 process-trace metric、active 計測)
Layer 3: Counterfactual perturbation  (v2 §2.6 そのまま、protocol v3 拡張なし)
Layer 4 (deferred): Social-ToM proper  → M11-C 移送、M10-0 では 4 scenario spec doc のみ
Layer 5 (deferred): Emotional / cognitive alignment  → M11+ defer (ADR-PM-5)
```

### Layer 2 3 metric (中核)

- M-L2-1: `cite_belief_discipline.provisional_to_promoted_rate` (belief substrate、100-tick window、distribution band declare)
- M-L2-2: `cite_belief_discipline.cited_memory_id_source_distribution` (citation substrate、3-source JS divergence)
- M-L2-3: `cite_belief_discipline.counterfactual_challenge_rejection_rate` (citation substrate、perturbation window、effect direction greater)

### Schema (DDL 変更ゼロ)

- 新 table `metrics.social_tom` は廃止
- Layer 2 metric は `metrics.individuation` の `metric_name` 列に dotted namespace で流すのみ
- DB11 sentinel poison row test は既存テストが自動 cover

### Negative control (v2 既存 3 種)

- NC-1 cite-disabled / NC-2 shuffled-memory / NC-3 no-individual-layer-ablation
- NC-4 shuffled-recipient / NC-5 perspective-isolation は **廃止** (scenario lib 不在で対象消失)

### M10-0 sub-task

```
m10-0-individuation-metrics       (Layer 1 + Layer 2 + WP11 4 scenario spec doc)
m10-0-source-navigator-mvp        (idea_judgement.md Kant MVP、runtime 非接続)
```

(Social-ToM 専用 sub-task は廃止、Hybrid-A revised で main 統合に再 revise)

### WP11 4 scenario spec doc

M10-0 で **spec のみ** doc 化 (~200 行 markdown)、M11-C `m11-c-social-tom-proper` への handoff:
- S-CHA-1: private witness asymmetry (chashitsu zone、object event 片方目撃)
- S-AGO-1: false rumor (agora zone、testimony hierarchy)
- S-GAR-1: counterfactual in solitude (garden zone、§2.6 perturbation との overlap 区別)
- S-GAR-2: cited source asymmetry (garden zone、source attribution retention、M10-C 前段)

## §3. Reimagine から救出した design 上の根本的逆転

design-original は scenario lib + capability-oriented metric (false_belief_recovery / info_asymmetry_handling 等) を中核としたが、design-reimagine で次の構造的問題が明らかになった:

1. **Scenario design bias**: 7 scenario の選定そのものが、Social-ToM signal の出やすい状況を選んでしまう (人間の preconception が混入)
2. **M10-0 で active 計測できない**: scenario 実走には multi-agent runtime が必須、M11-C 待ち → M10-0 close 時に doc 主体 + protocol freeze で active evidence なし
3. **新 table `metrics.social_tom` の必然性が弱い**: 既存 `metrics.individuation` の `metric_name` 列に dotted namespace で流せば DDL 変更ゼロ + DB11 sentinel 自動 cover
4. **5 metric を a priori に固定する根拠が弱い**: capability roster は設計者の preconception、agent が発露する Social-ToM signal がそこに mapping できる保証なし
5. **既存 capture (Phase B+C 30 cell × 504 tick = 15,120 tick) を活用しない**: 追加 G-GEAR overnight run を要するのは設計の効率損失

Reimagine の解決:
- Process-trace 3 metric を Layer 2 に置き、既存 Phase B+C capture で active 計測
- scenario lib + Social-ToM-specific metric は M11-C に明示 defer (M10-0 では spec 4 件のみ救出)
- Statistical power N=15,120 tick base で robust evaluation を実現

Hybrid-A revised は両案を統合 — Layer 2 active 計測 (reimagine 由来) + 4 scenario spec doc (original から救出、M11-C handoff)。Social-ToM 専用 sub-task は廃止 (Layer 2 が main 統合で十分)。

## §4. Codex に聞きたい具体質問 (Q1-Q12、verbatim 回答要請)

### Q1: Layer 2 3 metric の独立性論証は妥当か

`design-final.md §C.2` の M-L2-1/2/3 の独立性論証 (belief substrate vs citation substrate vs perturbation window) は statistically rigorous か。
特に M-L2-1 (`provisional_to_promoted_rate`) と M-L2-3 (`counterfactual_challenge_rejection_rate`) は両方とも belief discipline を測るため、|r| ≥ 0.85 になる懸念はあるか。

### Q2: Hybrid-A revised が ADR-PM-2 を再 revise することの ADR 整合性

`decisions.md` の ADR-PM-2 は「Social-ToM eval を独立 sub-task に格上げ」と判定済 (2026-05-15 同日)。本 hybrid 採用で「Social-ToM 専用 sub-task は廃止、Layer 2 を main 統合」に再 revise する。同日の ADR 再 revise が design discipline として許容されるか、それとも ADR-PM-2 を deprecate + 新 ADR-PM-6 で立てる方が clean か。

### Q3: `cite_memory_ids` schema は M10-0 で stub 必要か

M-L2-2 (`cited_memory_id_source_distribution`) の input は `LLMPlan.cited_memory_ids` per tick + 各 memory_id の `source` attribute (self_observation / other_testimony / inferred の 3 分類)。M10-C `WorldModelUpdateHint.cited_memory_ids` 設計が確定する前に、M10-0 で M-L2-2 を実装するには `cited_memory_ids` schema (stub) が必要か。それとも M-L2-2 は M10-C 着手後に有効化する形で、M10-0 close 時点では `status='unsupported', reason='cited_memory_ids schema pending M10-C'` を返すのが妥当か。

### Q4: M11-C handoff 文書としての WP11 4 scenario spec の十分性

`design-final.md §C.8` の 4 scenario spec (S-CHA-1 / S-AGO-1 / S-GAR-1 / S-GAR-2) は、M11-C task `m11-c-social-tom-proper` 着手時に独立読解可能か。M10-0 と M11-C の間にセッション間 gap が発生した場合 (数ヶ月)、scenario spec の前提が古くなる risk は許容できるか。spec doc 内に「freshness date」「protocol_version pin」のような mechanism を入れるべきか。

### Q5: Phase B+C 既存 capture の status='valid' ≥ 90% 期待は realistic か

`design-final.md §C.7 A12` で「Layer 2 3 metric が M9-eval Phase B+C 30 cell × 504 tick から抽出可、status='valid' 比率 ≥ 90%」を acceptance としている。Phase B+C capture は **stimulus 1 agent + natural 1 agent** で multi-agent dialog を含まない。M-L2-2 (3-source distribution) は other_testimony を含む必要があるが、natural 1 agent rollout で other_testimony source の memory が成立するか。90% は楽観しすぎではないか。

### Q6: counterfactual_challenge_rejection_rate の baseline_noindividual との比較で effect direction = greater が成立するか

M-L2-3 acceptance は「baseline_noindividual との effect direction greater」とした。しかし NC-3 (no-individual-layer-ablation) では `cited_memory_ids` が self_observation 100% で、counterfactual entry を cite すること自体が困難 → rejection 100% trivial に到達。これだと individual layer ありの方が discipline 弱く見える可能性がある。baseline 選定の rigor (NC-3 でなく v2 既存 baseline、または individual-layer-enabled-but-no-perturbation baseline) を再考すべきか。

### Q7: ADR-PM-5 (Emotional alignment M11+ defer) は User 指示の "ToM など" の "など" を捨てていないか

User 指示「ToM などを含めた評価体制」の "など" は HEART/MentalAlign 等の emotional alignment を含むと解釈可能。本 hybrid は emotional alignment を M11+ defer に置いたが、User からの redirect risk はないか。ADR-PM-5 の rationale (臨床主張回避、quantitative pipeline 分離) は十分か。

### Q8: M-L2-1 effect direction = none (band declare) の preregister 健全性

M-L2-1 (`provisional_to_promoted_rate`) は effect direction を "none (両方向ありうる、distribution として band declare)" とした。これは preregister 上 weakest の effect direction declaration で、circular gate 化の risk があるか (band で何が出ても "expected" になる)。Bayesian prior の形で計測前に分布形を declare する方が rigorous か。

### Q9: 3 文書 (original / reimagine / final) の co-existence による reader confusion

`design-original.md` (506 行) と `design-reimagine.md` と `design-final.md` の 3 文書が co-exist する。M10-0 着手後の reader (Claude 次セッション or 別 contributor) が `design-final.md` だけを読めば十分か、それとも全 3 文書を読まないと意図が伝わらないか。`design-original.md` を deprecate marker (header に "deprecated, see design-final.md") を入れるべきか。

### Q10: relative date の絶対化 (W-9 教訓 / Codex 14th 類例)

`design-final.md` 内の relative phrase ("今後の", "次セッション", "次 task scaffold 時") を absolute date / commit hash に置換すべきか。本 task は docs+steering only の synthesis で source 変更ゼロのため、検索性より readability を優先する選択肢もある。判定願う。

### Q11: 同日 ADR 連発の操作上の risk

`decisions.md` に ADR-PM-1〜PM-5 が 2026-05-15 同日に立っており、本 hybrid 採用後に ADR-PM-6 (Hybrid-A revised 採用) + ADR-PM-7 (Codex 13th 反映) が追加される。同日に 7 ADR が立つことは operational に reviewable か、それとも数日に分けて立てる方が rigor か。

### Q12: Codex review 自体の structural bias

本 prompt は「Hybrid-A revised の structural soundness を切り出してほしい」と要請しているが、これは prompt 側の bias で Codex が "soundness" を見つけやすい方向に振っている可能性がある。Codex 独自の reading で本 hybrid の **structural failure mode** を能動的に提示してほしい (capability-oriented を捨てる選択が経年で reader にどう映るか、Layer 2 が active 計測で何を見落とすか、等)。

## §5. 期待 review format

```markdown
# Codex 13th review — pre-M10 design synthesis (Hybrid-A revised)

**Verdict**: ADOPT / ADOPT-WITH-CHANGES / BLOCK / REJECT

## Summary
(3-5 lines)

## HIGH findings (must address before scaffold)
- HIGH-1: ...
- HIGH-2: ...
...

## MEDIUM findings (judgement, defer 可)
...

## LOW findings (持ち越し可)
...

## Q1-Q12 verbatim answers
Q1: ...
Q2: ...
...
Q12: ...

## Stress-test (Q12 への能動 answer)
(Codex 独自 reading での failure mode 列挙)
```

## §6. Codex の制約理解

- 投げる文書は **`design-final.md` / `design-original.md` / `design-reimagine.md` / `decisions.md` を 1 prompt に concat** する (本 prompt は wrapper)
- Token 想定: 200-300K (per_invocation_max=200K の場合は warn が出る、許容)
- Network access (`network = "enabled"`) を web_search に使ってよい (Layer 2 metric の statistical 前例調査等)
- 出力は `.steering/20260515-pre-m10-design-synthesis/codex-review.md` に verbatim 保存される

---

# Attached: design-final.md

# 設計 — pre-M10 design synthesis (FINAL: hybrid 採用)

> **本書の位置づけ**: `design-original.md` (capability-oriented scenario-lib) と `design-reimagine.md` (process-trace + power-first) の **両案を並列審査** した上で、採用 hybrid を確定する。本書が M10-0 sub-task scaffold 起票の正式 reference となる。Codex 13th review は本書 + design-original / design-reimagine の **3 文書** に対して投げる。
>
> 旧 `design.md` の役割は本書に置換、`design-original.md` は historical reference として保持。

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
- **Aggregation**: per-individual × per-100-tick window
- **Effect direction**: distribution として宣言 (両方向ありうる、freeze せず band declare)
- **Sources**: M9-eval Phase B+C 30 cell の raw_dialog.dialog から `belief_kind` transition を抽出
- **typed result**: status='valid' 期待、`provisional` 遷移ゼロの window は `status='degenerate', reason='no provisional belief in window'`

#### M-L2-2: `cite_belief_discipline.cited_memory_id_source_distribution`

- **Input**: `LLMPlan.cited_memory_ids` per tick + 各 memory_id の `source` attribute (自己観測 / 他者 testimony / inferred の 3 分類)
- **Definition**: per-window で 3 source の比率 distribution、baseline (no-individual-layer ablation) との Jensen-Shannon divergence
- **Aggregation**: per-individual × per-100-tick window
- **Effect direction**: divergence band (baseline ≠ individual のはず、distribution shift が出るのが期待)
- **typed result**: cited_memory_ids が空の tick が window の 80% 超なら `status='degenerate', reason='cite-sparse window'`
- **Sources**: 既存 `LLMPlan` schema が `cited_memory_ids` を持つこと前提 — **要確認** (M10-C で確定する予定だが、M10-0 で stub が必要なら schema 追記が必要)

#### M-L2-3: `cite_belief_discipline.counterfactual_challenge_rejection_rate`

- **Input**: §C.3 perturbation 下の `cited_memory_ids` 集合 vs `counterfactual_challenge` channel 入力 memory_id 集合
- **Definition**: 1 - (perturbation tick で `cited_memory_ids` が counterfactual entry を **含む** tick の比率)
- **Aggregation**: per-individual × perturbation tick window
- **Effect direction**: greater than baseline_noindividual (ablation で 100% reject 期待は trivial、individual layer ありで discipline が保たれる検証)
- **typed result**: perturbation window 内で `cited_memory_ids` 完全空なら `status='degenerate', reason='no-cite under perturbation'`

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
| `cite_belief_discipline.provisional_to_promoted_rate` band | calibrate_before_unblinding(P-PPR, split=[Phase B+C run0-2]→cal/[run3-4]→eval) | bootstrap 1000 resample、95% CI、effect direction = none (distribution として band declare) |
| `cite_belief_discipline.cited_memory_id_source_distribution` JS divergence | calibrate_before_unblinding(P-CMSD, split=同上) | per-source bootstrap、JS divergence band、effect direction = greater than zero |
| `cite_belief_discipline.counterfactual_challenge_rejection_rate` lower bound | calibrate_before_unblinding(P-CCRR, split=同上、§C.3 perturbation 下) | effect direction = greater than baseline_noindividual |
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
| **A12 (Hybrid 新)** | Layer 2 3 metric が M9-eval Phase B+C 30 cell × 504 tick から抽出可、`status='valid'` 比率 ≥ 90% | 既存 capture 再利用検証 |
| **A13 (Hybrid 新)** | Layer 2 × NC-1/2/3 の §C.5 表 9 cell 期待値が bootstrap CI 95% band 内 | negative control 健全性 |
| **A14 (Hybrid 新、WP11 doc)** | WP11 4 scenario spec doc が M11-C task `m11-c-social-tom-proper` の素材として独立読解可能 | M11-C handoff |

### §C.8 WP11 (4 scenario spec doc、~200 行 markdown)

m10-0-individuation-metrics main 内の WP11 として配置、`design.md` または `social-tom-scenarios.md` として M11-C handoff 文書化。4 scenario:

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

---

# Attached: design-original.md

# 設計 — pre-M10 design synthesis (M10 評価体制 concrete robust design)

> 本書の中核は §3 「M10-0 評価体制 concrete robust design」。
> §1-§2 は context、§4-§7 は §3 設計から派生する配置決定 / patch / scaffold / memo の整理。
> User 直接指示 (2026-05-15) 「m10 では具体的に ToM などを含めた評価体制を具体的に強固に設計してから決めてください」を受け、placement-first を design-first に逆転させている。

---

## §1. memo 要旨

### `idea_judgement.md` (Corpus2Skill 型 source_navigator) — 2026-05-12 起草

- 公式 `dukesun99/Corpus2Skill` 直接導入は不採用 (Anthropic API 必須、license 未確認)
- 論文の compile-then-navigate pattern を **ローカル再実装** する案を「8/10、強い採用候補」
- M10-0 preflight として設計するのが最適 (runtime 非接続、史料・evidence の階層 navigator)
- 4 idea: persona source navigator / M10 WorldModel citation navigator / Evaluation Corpus QA harness / Developer navigation skill
- MVP scope: Kant のみ / depth 2 / markdown+JSON / 6 cognitive_habits 全件が `source / flag / trigger_zone / document_ids / provenance` に辿れる

### `idea_judgement_2.md` (LLM 研究開発手法と評価調査) — 2026-05-13 起草

- 結論: FT 手法 (QDoRA) より先に **人格・社会性・個体化を測る評価基盤を厚く** する
- M10-0 で必須:
  - `metrics.individuation`、`AnalysisView` loader (v2 draft で吸収済)
  - 4 個体化 metrics (うち 3 件 v2 draft 吸収、`intervention_recovery_rate` は protocol 化済)
  - metric 相関行列 / `thresholds.md` `calibrate_before_unblinding` (v2 draft 吸収済)
  - **Social-ToM 最小 spec (ExploreToM/SocialEval 翻案)** ← **v2 draft 未吸収、本 synthesis で concrete 化**
- M12+: QDoRA ablation registry (yaml format 提示済)
- 採用順序: M10-0 evaluation expansion → Social-ToM/counterfactual protocol → QLoRA-LoRA baseline freeze → QDoRA ablation

---

## §2. v2 draft 既吸収項目 mapping 表

`.steering/20260508-cognition-deepen-7point-proposal/m10-0-concrete-design-draft.md` (PR #159、Codex 12th HIGH 5 反映済) で既に吸収されている項目:

| idea_judgement_2.md 項目 | v2 draft 反映先 |
|---|---|
| `metrics.individuation` schema 配下 | §2.3、HIGH-2 反映 |
| `AnalysisView` loader (raw_dialog window 抽出) | §2.2 / §2.9 / WP5、HIGH-5 反映 |
| `cognitive_habit_recall_rate` / `action_adherence_rate` / `zone_behavior_consistency` | §2.2 matrix、MEDIUM-2 |
| `thresholds.md` `calibrate_before_unblinding` state | §2.5、HIGH-1 |
| DB11 sentinel poison row test | §2.4 A9、HIGH-2 |
| metric correlation matrix | §2.4 A10、MEDIUM-4 |
| QDoRA M12+ ablation gate | §2.7 out-of-scope |
| persona/source checklist M10-A defer | §2.7 out-of-scope |
| MeCab ja-tokenizer 別 task | §2.7 + WP4 削除、HIGH-4 + MEDIUM-5 |
| Vendi kernel sensitivity 別 task | §2.7 |
| Big5 ICC は diagnostic only / N≥3 で M11-C active | §2.2 / §2.5、MEDIUM-3 |
| `counterfactual_challenge` 隔離 + 3 種 negative control | §2.6、HIGH-3 |
| recovery protocol (Burrows + behavioral dual channel) | §2.6 |

**v2 draft 未吸収** (本 synthesis で対処):

- idea_judgement.md 全 4 idea (source_navigator) → §4 で配置 (B-1)
- idea_judgement_2.md §2 Social-ToM minimum spec → **§3 で concrete 化**
- idea_judgement_2.md §4 PEFT ablation registry yaml → §4 で linkback (B-3)
- idea_judgement_2.md §2 MentalAlign / HEART (emotional/cognitive alignment) → §3.9 で defer 採否

---

## §3. M10-0 評価体制 concrete robust design (中核)

### §3.1 評価体制の上位構造 (4 layer)

M10-0 の評価体制を以下の 4 layer に分割し、それぞれ独立した metric channel + provenance + acceptance を持つ。layer 間の直交性は §3.8 で相関行列 detection。

```
Layer 1: Individuation (個体化)
  - 既存 v2 draft §2.2 matrix の 11 metric
  - Burrows / Vendi / centroid / belief_variance / SWM Jaccard / habit_recall / action_adherence / zone_behavior
  - Population-level + per-individual aggregation
  - Schema: metrics.individuation (v2 §2.3、provenance 7 fields)

Layer 2: Social-ToM (社会的心の理論)  ← 本 synthesis で concrete 化
  - 新規 scenario harness + 5 metric (§3.3)
  - Zone × scenario × counterfactual variant の格子
  - Schema: metrics.social_tom (新規、§3.4、metrics.* namespace で DB11 防御下)

Layer 3: Counterfactual perturbation (反事実摂動)
  - v2 draft §2.6 protocol を v3 (§3.5) に拡張
  - opposite-stance memory 隔離 + SWM write 禁止 + negative control 5 種 (§3.6、3→5 拡張)
  - Schema: metrics.individuation の channel 拡張 (perturbation tick window で計測)

Layer 4: (defer) Emotional / cognitive alignment  ← §3.9 で defer 採否
  - HEART / MentalAlign 翻案、Tier C/D rubric
  - 臨床主張は明示的に排除 (idea_judgement_2.md §1)
  - M10-0 では out-of-scope、M11+ task として保留
```

#### 各 layer の独立性根拠

- Layer 1 ↔ Layer 2: Individuation は **同一 base 個体の発達** を測る、Social-ToM は **他者表象** を測る。channel は base habit retention vs theory-of-mind operations で完全に異なる。
- Layer 2 ↔ Layer 3: Social-ToM は **観測非対称下での belief 推論**、Counterfactual perturbation は **opposite-stance evidence injection 時の base 復元力**。前者は scenario で他者を立てる、後者は injection を行う。**重なる場合は §3.5 で明示的に separate scenario と declare**。
- Layer 1/2/3 ↔ Layer 4: Emotional alignment は qualitative manual rubric が大きく、quantitative pipeline と分離が安全。

### §3.2 Social-ToM scenario 設計 (zone × base scenario × counterfactual variant)

`docs/glossary.md` の 5 zone のうち、Social-ToM に適した 3 zone を選定:

#### S-CHA (chashitsu = 茶室、private witness asymmetry)

**base scenario S-CHA-1**: object_event_witnessed_by_A_only
- Setup: agent A と B が chashitsu に入室、B が一時退室、A だけが object event (例: 茶器の位置移動) を目撃、B 帰室
- A の発話を観測しないまま B に「茶器がどう動いたか」を質問
- Probe: B の belief は「移動前」状態のまま (false belief retained)、A は移動後を知っている (true belief)
- Test: B の発話が false belief consistent か、A の testimony を受けた後に belief update するか
- Counterfactual variant S-CHA-1c: A が嘘の testimony を行う場合の B の belief stability

**base scenario S-CHA-2**: shared experience but divergent interpretation
- Setup: A と B 同席で同じ茶事象を観察、A は美的価値で評価、B は儀礼適合性で評価
- Probe: A→B / B→A の cross-interpretation request
- Test: 自己の interpretation が他者と divergent と認識し、self-perception と attributed-perception を分離するか

#### S-AGO (agora = 議論場、public discourse with rumor)

**base scenario S-AGO-1**: B has false rumor about C
- Setup: A は C と直接話した経験あり、B は C の伝聞 (rumor) を信じている、A と B が agora で C について discuss
- Probe: A が「C に直接聞いた」と発話した後、B の belief update
- Test: testimony 階層 (direct experience > second-hand report) を model し、自己の belief source を区別するか

**base scenario S-AGO-2**: persuasion vs base habit retention
- Setup: agora で他者 N (>1) から base persona の cognitive habit と矛盾する意見を sustained に受ける
- Probe: base habit が retain されるか erode するか
- Test: peer pressure 下の base retention rate、§3.5 counterfactual perturbation protocol と併用

#### S-GAR (garden = 庭、reflective synthesis with counterfactual)

**base scenario S-GAR-1**: counterfactual challenge in solitude
- Setup: agent A が garden で reflection、外部 counterfactual_challenge channel で opposite-stance evidence が injection される (v2 draft §2.6 と同 channel)
- Probe: A の reflection が counterfactual evidence を採用するか、cite-disabled で reject するか
- Test: §3.5 protocol v3 と direct integration

**base scenario S-GAR-2**: belief revision with cited source asymmetry
- Setup: 過去 tick の dialog から retrieved memory に「自身が cite した source」と「他者が cite した source」が混在
- Probe: source attribution の retention、cite_memory_ids の source-of-cite が belief revision priority を持つか
- Test: WorldModelUpdateHint adoption (M10-C territory) の前段として、source-aware retention を計測

### §3.3 Social-ToM metric set (5 metric、独立 channel として定義)

| Metric | Input channel | What | Aggregation | Phase | Notes |
|---|---|---|---|---|---|
| `false_belief_recovery_rate` | agent dialog response in S-CHA-1 / S-AGO-1 | false belief を持つ他者が testimony 後に belief update する rate (他者 model 側) | per-scenario × per-individual | M10-0 protocol、M11-C 実走 | testimony 階層を区別 |
| `info_asymmetry_handling_rate` | S-CHA-1 / S-AGO-1 dialog | 自己が知っている事と他者が知っている事を分離して発話する rate | per-scenario × per-individual | M10-0 protocol、M11-C 実走 | self/other belief split |
| `counterfactual_resistance_rate` | S-GAR-1 dialog under §3.5 perturbation | opposite-stance evidence injection 下で base habit が retain される rate | per-individual | M10-0 protocol、M11-C 実走 | §3.5 protocol v3 と相互参照 |
| `opposite_stance_adoption_rate` | S-GAR-1 dialog under §3.5 perturbation | (**禁止指標**: 低くあるべき) counterfactual evidence を base belief として採用する rate | per-individual | M10-0 protocol、M11-C 実走 | acceptance: ≤ baseline_no_individual + 0.05 |
| `source_attribution_retention_rate` | S-GAR-2 dialog | cite_memory_ids の source-of-cite (self vs other) が belief revision で priority を保つ rate | per-individual | M10-0 protocol、M10-C 実走 (WorldModelUpdateHint と相互) | M10-C 経由で active 化 |

#### channel 独立性の論証

- `false_belief_recovery_rate` ↔ `info_asymmetry_handling_rate`: 前者は他者の belief を model し update する、後者は **自己の発話制御** で分離する。input channel は同じだが evaluation 観点が異なる (他者 model 側 vs 自己発話側)。
- `counterfactual_resistance_rate` ↔ `opposite_stance_adoption_rate`: 同 scenario の **inverse** (base 維持 / opposite 採用) を測る。両方 ≥ 0 の関係だが、theoretical な complement ではない (mid-range の hedging 発話があるため `1 - x` ではない)。
- `source_attribution_retention_rate` は M10-C 依存 → M10-0 では protocol 固定のみ、active 計測は M10-C close 後。

### §3.4 Schema (DuckDB `metrics.social_tom` table)

v2 draft §2.3 `metrics.individuation` と同じ provenance pattern を踏襲、namespace `metrics.*` で DB11 sentinel grep の防御下に固定:

```sql
CREATE TABLE metrics.social_tom (
  -- identification
  run_id            TEXT NOT NULL,
  scenario_id       TEXT NOT NULL,        -- S-CHA-1 / S-CHA-1c / S-CHA-2 / S-AGO-1 / S-AGO-2 / S-GAR-1 / S-GAR-2
  scenario_variant  TEXT NOT NULL,        -- base / counterfactual / negative_control_<id>
  individual_id     TEXT NOT NULL,        -- 主体 agent (A)
  other_agent_ids   TEXT NOT NULL,        -- JSON array of agent ids (B, C, ...)
  base_persona_id   TEXT NOT NULL,
  tick_start        BIGINT NOT NULL,
  tick_end          BIGINT NOT NULL,
  metric_name       TEXT NOT NULL,        -- §3.3 5 metric のいずれか
  channel           TEXT NOT NULL,        -- dialog_response / belief_probe / source_citation
  -- typed result (v2 §2.4 と同型)
  status            TEXT NOT NULL CHECK (status IN ('valid','degenerate','unsupported')),
  value             DOUBLE,
  reason            TEXT,
  -- provenance (v2 §2.3 と同型 + Social-ToM 固有)
  metric_schema_version             TEXT NOT NULL,
  source_table                      TEXT NOT NULL,   -- raw_dialog.dialog
  source_run_id                     TEXT NOT NULL,
  source_epoch_phase                TEXT NOT NULL,   -- evaluation のみ (training reject)
  source_individual_layer_enabled   BOOLEAN NOT NULL,
  source_filter_hash                TEXT NOT NULL,
  scenario_protocol_version         TEXT NOT NULL,   -- 新、§3.2 scenario lib の version
  negative_control_id               TEXT,            -- §3.6 negative control 適用時のみ
  embedding_model_id                TEXT,
  computed_at                       TIMESTAMP NOT NULL
)
```

**サイドカー JSON** (`*.duckdb.social_tom.json`、`*.individuation.json` の sibling):
- per-scenario population-level summary
- training manifest input にしない (DB11 sentinel poison row test を `metrics.individuation` と同様に必須)

### §3.5 Counterfactual perturbation protocol v3 (v2 §2.6 拡張)

v2 §2.6 の v2 を、Social-ToM scenario S-GAR-1 と統合する v3 に拡張:

```
prep:
  1. base individual を T_base = 200 tick (zone は base persona の preferred_zone) → baseline:
     - Burrows / cognitive_habit_recall / action_adherence (individuation channel)
     - false_belief_recovery / info_asymmetry_handling (Social-ToM channel、S-CHA-1 / S-AGO-1 を baseline tick で実走)

perturbation:
  2. counterfactual_challenge channel に opposite-stance content N=5 を injection (v2 §2.6 と同)
     - retrieved_memories とは別 channel
     - cited_memory_ids 集合に含めない
     - WorldModelUpdateHint adoption の evidence source として無効化
     - perturbation 中 SWM write 禁止 (replay-only)
     - 注入は agora 風 sustained discourse (S-AGO-2) でも garden 風 solitude (S-GAR-1) でも独立に実走
  3. T_perturb = 50 tick → perturbed_floor 計測 (両 channel)

recovery:
  4. counterfactual_challenge 除去後 T_recover = 200 tick → post recovery 計測
     - Burrows / habit recovery (individuation)
     - counterfactual_resistance_rate / opposite_stance_adoption_rate (Social-ToM)

metric:
  recovery_rate (Individuation 既存) = (post - perturbed_floor) / (baseline - perturbed_floor)
    channels: Burrows / cognitive_habit_recall / action_adherence
  counterfactual_resistance_rate (Social-ToM 新)
    = 1 - (perturbed_floor_opposite_adoption / scenario_max_adoption)
  opposite_stance_adoption_rate (Social-ToM 新、禁止指標)
    = perturbed_floor_opposite_adoption / scenario_max_adoption
  stickiness_rate (M11-C 実走): SWM entry persistence ratio
```

#### Layer 3 と Layer 2 の boundary

- S-AGO-2 / S-GAR-1 は §3.5 perturbation を **必ず** 適用する
- S-CHA-1 / S-CHA-2 / S-AGO-1 / S-GAR-2 は **perturbation なし** で計測 (Layer 2 純粋計測)
- S-CHA-1c (lying testimony) は perturbation でなく **scenario-internal counterfactual** (testimony 自体が false) で、Layer 2 内に閉じる

### §3.6 Negative control 拡張 (v2 §2.6 の 3 種 → 本設計で 5 種)

v2 §2.6 の 3 種 (cite-disabled / shuffled-memory / no-individual-layer ablation) に、Social-ToM 用 2 種を追加:

| ID | name | 目的 | 適用 scenario | acceptance |
|---|---|---|---|---|
| NC-1 | cite-disabled | counterfactual_challenge entry を cite_memory_id として宣言しても WorldModelUpdateHint adoption が merge されない | S-GAR-1 + §3.5 | golden test、reject 100% |
| NC-2 | shuffled-memory | 関係ない memory id を cite → reject | S-GAR-1 + §3.5 | golden test、reject 100% |
| NC-3 | no-individual-layer-ablation | individual_layer_enabled=false で同 protocol → SWM 自体存在しない | 全 scenario | individuation/Social-ToM metric は **layer 適用前 baseline** に近い値、value は protocol で band declare |
| NC-4 (新、Social-ToM) | shuffled-recipient | testimony の addressee を意図的に shuffle (A の発話が B でなく無関係な C に向けられる) → addressee identity を model しない agent は応答に変化なし | S-CHA-1 / S-AGO-1 | addressee shuffle 時の false_belief_recovery_rate が baseline と統計有意差なし → addressee-blind と判定、acceptance: 差分 ≤ baseline_noise_band |
| NC-5 (新、Social-ToM) | perspective-isolation | scenario から self/other 区別を除去 (全発話を 1 人称化) → info_asymmetry_handling_rate が degenerate になる | S-CHA-1 / S-AGO-1 | typed result `status='degenerate', reason='self-other distinction stripped'` を必ず返す |

### §3.7 Acceptance preregister (`thresholds.md` への追記項目)

v2 §2.5 `thresholds.md` のフォーマット (`frozen` / `calibrate_before_unblinding` / `defer`) に Social-ToM thresholds を追加:

| Threshold | State (M10-0 close 時) | Protocol |
|---|---|---|
| `false_belief_recovery_rate` band | calibrate_before_unblinding(P-FBR, split=[run0-2 scenario lib]→cal/[run3-4 scenario lib]→eval) | P-FBR: bootstrap 1000 resample、95% CI、effect direction = greater than noindividual baseline |
| `info_asymmetry_handling_rate` band | calibrate_before_unblinding(P-IAH, split=同上) | P-IAH: 同上、self/other split を AST/structure level で抽出 |
| `counterfactual_resistance_rate` band | calibrate_before_unblinding(P-CFR, split=同上、§3.5 perturbation 結果から) | P-CFR: baseline_noindividual との差分が effect direction = greater |
| `opposite_stance_adoption_rate` upper bound | **frozen(baseline_noindividual + 0.05, 2026-05-15, design rule)** | 禁止指標、超過時は M11-C で audit + protocol 見直し |
| `source_attribution_retention_rate` band | defer(M10-C, WorldModelUpdateHint 着手後 calibrate) | M10-C と相互 |
| NC-4 `addressee_shuffle_delta` | calibrate_before_unblinding(P-NC4, split=同上) | acceptance: 差分 ≤ baseline_noise_band |
| NC-5 `degenerate_must_fire` | frozen(true, 2026-05-15) | typed result `status='degenerate'` 100% |

### §3.8 既存 metric との直交性 (相関行列の Social-ToM 拡張)

v2 §2.4 A10 (metric 相関行列、|r| ≥ 0.85 で double-measurement warn) を以下に拡張:

- **同 layer 内**: §3.3 の 5 Social-ToM metric 間の相関を計測、|r| ≥ 0.85 で独立 channel 主張を撤回 (再設計トリガー)
- **layer 跨ぎ**: Individuation 11 metric × Social-ToM 5 metric の cross correlation を相関行列に追加
  - 警戒 pair (a priori):
    - `cognitive_habit_recall_rate` ↔ `counterfactual_resistance_rate` (両方とも habit retention 系) → 期待 |r| 中、|r| ≥ 0.85 なら警戒
    - `action_adherence_rate` ↔ `info_asymmetry_handling_rate` (両方とも意思決定一貫性系) → 期待 |r| 中-低
    - `belief_variance` ↔ `false_belief_recovery_rate` (両方とも belief 操作系) → 期待 |r| 中、独立 channel として残す根拠は input source の違い (自己 belief vs 他者 belief)

### §3.9 Emotional / cognitive alignment (HEART / MentalAlign) の M10-0 取り扱い

idea_judgement_2.md は HEART / MentalAlign を「中-高」評価、ただし **臨床主張不可、Tier C/D rubric (manual sparse review)** に限定としている。

**判断**: M10-0 範囲外 (Layer 4、§3.1 で defer 宣言済)。理由:
- quantitative pipeline (Layer 1-3) と分離が安全
- Tier C/D rubric は manual review LOC が大きく、scope が膨らむ
- 臨床用語の安易使用は ERRE 研究プラットフォームの説明責任を弱める
- 個体化 + Social-ToM の robust 設計が固まる前に emotional layer を加えると、metric 間の confound が増える

**defer 先**: M11+ task `m11-emotional-alignment-rubric` として後送り (本 task では scaffold もしない、idea_judgement_2.md §1 を参照する linkback のみ)。

### §3.10 Out-of-scope (明示)

M10-0 評価体制で扱わないもの:

- Multi-agent runtime execution (Social-ToM scenario は M11-C で実走、M10-0 では protocol + schema + lib のみ)
- Production scale evaluation (M10-0 は 1-2 agent × 5-7 scenario × 3 negative control 程度)
- 臨床主張 (HEART / MentalAlign 系の clinical use はしない)
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

---

## §4. 配置決定 (§3 設計サイズから自然に確定)

§3 で Social-ToM eval が ~10 sub-section、新 DuckDB table、5 metric、7 scenario、2 新規 negative control、5 thresholds preregister と展開された結果、当初の「WP11 ~150 行 doc」は実態と乖離。配置は以下に再設定:

| ID | 対象 | 配置 | 根拠 |
|---|---|---|---|
| B-1 | source_navigator (idea_judgement.md) | **別 sub-task `m10-0-source-navigator-mvp`** (parallel) | scope 隔離、runtime 非接続、M10-0 main の blocker 化を避ける |
| **B-2 (revised)** | **Social-ToM eval (§3)** | **独立 sub-task `m10-0-social-tom-eval`** (M10-0 individuation main と parallel、共通 schema namespace `metrics.*`) | §3 設計サイズが scaffold ~700-900 production LOC + scenario lib + protocol doc + test (~25 unit + 3 integration) で WP11 doc 1 件に収まらない、独立 PR で出すべき |
| B-3 | PEFT ablation registry (idea_judgement_2.md §4) | M12+ task `m12-peft-ablation-qdora` の前提 gate、本 synthesis では linkback のみ | M12+ task scaffold 時に initialize で足りる |
| **B-4 (新)** | Emotional / cognitive alignment (HEART / MentalAlign) | **M11+ defer** (`m11-emotional-alignment-rubric`、本 synthesis では scaffold せず linkback のみ) | §3.9 根拠、臨床主張回避 + scope 隔離 |

### M10-0 sub-task の最終構成 (post-synthesis)

```
M10-0 (parallel sub-tasks):
  ├─ m10-0-individuation-metrics       (v2 draft WP1-WP10 を踏襲、Layer 1)
  ├─ m10-0-social-tom-eval             (§3 を踏襲、Layer 2 + Layer 3 拡張)
  └─ m10-0-source-navigator-mvp        (idea_judgement.md MVP、runtime 非接続)

M10-0 close 条件 = 3 sub-task すべて green に到達。
ただし依存:
  - Social-ToM の §3.5 perturbation protocol v3 は individuation の §2.6 を継承するため、
    individuation main の §2.6 protocol freeze が先行する (順序依存)
  - source_navigator は他 2 sub-task と完全独立
```

---

## §5. v2 draft Addendum patch ドラフト (貼り付け可能)

`.steering/20260508-cognition-deepen-7point-proposal/m10-0-concrete-design-draft.md` への追記文案。次 task scaffold 時に本体に commit。

### §2.7 (out-of-scope) への追記

```markdown
- **Social-ToM eval harness** → 独立 sub-task `m10-0-social-tom-eval`
  (本 v2 draft の §2.6 counterfactual_challenge を継承、Layer 2+3、design 詳細は
  `.steering/20260515-pre-m10-design-synthesis/design.md` §3)
- **source_navigator (Corpus2Skill 型)** → 独立 sub-task `m10-0-source-navigator-mvp`
  (Kant only、depth 2、runtime 非接続、design 詳細は同 §6.2)
- **PEFT ablation registry yaml format** → M12+ task `m12-peft-ablation-qdora` で
  initialize、本 v2 draft は M10-0 範囲外 (idea_judgement_2.md §4 を参照)
- **Emotional / cognitive alignment (HEART / MentalAlign)** → M11+ task
  `m11-emotional-alignment-rubric` defer、臨床主張回避
  (idea_judgement_2.md §1 を参照、設計判断は同 §3.9)
```

### §3 (WP 分割) への追記 (LOC 想定 表 row として)

```markdown
| WP11 | (削除、Social-ToM は独立 sub-task `m10-0-social-tom-eval` に格上げ) | — | — |
```

(註: 当初 WP11 は本 synthesis 初版で「Social-ToM min spec doc ~150 行」だったが、§3 で concrete 化した結果、独立 sub-task に格上げされ、v2 draft 本体 WP 表には載らない。)

### §6 (References) への追記

```markdown
- `.steering/20260515-pre-m10-design-synthesis/design.md` §3 (Social-ToM eval concrete design)
- `.steering/20260515-pre-m10-design-synthesis/decisions.md` ADR-PM-1〜PM-5
- `.steering/20260515-pre-m10-design-synthesis/idea-judgement-source-navigator.md`
- `.steering/20260515-pre-m10-design-synthesis/idea-judgement-pdf-survey.md`
```

---

## §6. 次 task scaffold 草稿 (inline、次セッションで `.steering/_template/` から起こす際の素)

### §6.1 `m10-0-individuation-metrics` requirement.md 草稿

```markdown
# M10-0 Individuation Metrics

## 背景
v2 draft `m10-0-concrete-design-draft.md` (PR #159、Codex 12th HIGH 5 反映済) の WP1-WP10 を
そのまま踏襲する main sub-task。Social-ToM eval は別 sub-task `m10-0-social-tom-eval` に分離
(本 task の §2.6 counterfactual_challenge protocol は両者の共有基盤)。

## ゴール
- v2 draft WP1-WP10 の実装 (LOC 想定 ~2950)
- 既存 1356+ tests + 新 25+ unit + 3 integration 全 green
- `--compute-individuation` flag off で既存 CLI byte-for-byte 不変
- DB11 sentinel poison row test green

## スコープ
含む: WP1 (eval/individuation 関数群 + MetricResult typed) / WP2 (DuckDB schema) /
      WP3 (CLI flag + sidecar JSON) / WP5 (AnalysisView loader) / WP6 (cache benchmark) /
      WP7 (prompt ordering contract) / WP8 (tests) / WP9 (thresholds.md) /
      WP10 (counterfactual_challenge protocol、Social-ToM eval と共有)
含まない: Social-ToM scenario lib / metric (m10-0-social-tom-eval) / source_navigator
         (m10-0-source-navigator-mvp) / PhilosopherBase 実装 (M10-A) / etc.

## 受け入れ条件
v2 draft §2.4 A1-A11 全 pass。
```

### §6.2 `m10-0-social-tom-eval` requirement.md 草稿

```markdown
# M10-0 Social-ToM Eval Harness

## 背景
`.steering/20260515-pre-m10-design-synthesis/design.md` §3 で concrete 化された Social-ToM
評価体制を実装する。Layer 2 (Social-ToM) + Layer 3 (counterfactual perturbation 拡張) を
担当、Layer 1 (Individuation) の `m10-0-individuation-metrics` と並列。

## ゴール
- `metrics.social_tom` DuckDB table 作成 (synthesis §3.4)
- 7 scenario lib (S-CHA-1/1c/2 + S-AGO-1/2 + S-GAR-1/2、synthesis §3.2)
- 5 Social-ToM metric 実装 (synthesis §3.3、MetricResult typed)
- counterfactual perturbation protocol v3 (synthesis §3.5、§2.6 v2 を拡張、共有実装は
  m10-0-individuation-metrics 側に置き、本 task は scenario integration のみ)
- 2 新規 negative control (NC-4 shuffled-recipient / NC-5 perspective-isolation)
- `thresholds.md` への Social-ToM threshold 5 件追加 (synthesis §3.7)
- 既存 metric との直交性検証 (synthesis §3.8、相関行列拡張)
- 25+ unit tests + 3 integration tests (scenario lib + protocol v3 + negative control)

## スコープ
含む: scenario lib (`src/erre_sandbox/eval/social_tom/scenarios/*.py`) /
      metric 関数群 (`src/erre_sandbox/eval/social_tom/metrics/*.py`) /
      schema 追加 (`src/erre_sandbox/evidence/eval_store.py` extension) /
      sidecar JSON output / negative control 実装 / thresholds 追記 / tests
含まない: multi-agent runtime 実走 (M11-C) / Emotional alignment (M11+) /
         source_navigator (m10-0-source-navigator-mvp)

## 受け入れ条件
- synthesis §3.3 の 5 metric が `MetricResult(status, value, reason)` で valid/degenerate/
  unsupported を返す (1 つの scenario で min 1 metric が valid)
- DB11 sentinel poison row test: `metrics.social_tom` も training-view loader が reject
- NC-4 shuffled-recipient で false_belief_recovery_rate が baseline と統計有意差なし →
  addressee-blind 判定
- NC-5 perspective-isolation で info_asymmetry_handling_rate が `degenerate` 100%
- `--compute-social-tom` flag off で既存 CLI byte-for-byte 不変
- `m10-0-individuation-metrics` と protocol v3 共有実装が conflict しない (順序依存:
  individuation main 完了 → 本 task 着手、または並列 PR でも protocol v3 implementation は
  individuation 側に置く合意)

## 依存
- `m10-0-individuation-metrics` (counterfactual_challenge protocol v3 共有基盤)
- v2 draft §2.6 protocol (継承)
```

### §6.3 `m10-0-source-navigator-mvp` requirement.md 草稿

```markdown
# M10-0 Source Navigator MVP

## 背景
`idea_judgement.md` (Corpus2Skill 型 source navigator、ローカル再実装) の MVP を実装。
runtime 非接続、static corpus navigation として持つ。M10-C `WorldModelUpdateHint.cited_memory_ids`
の前段として、史料 / cognitive_habit / provenance を階層 index 化する。

## ゴール
- Kant only (`personas/kant.yaml` + `evidence/reference_corpus/raw/` Kant 関連)
- depth 2 (persona → habit → source cluster → document_ids)
- 出力: markdown `INDEX.md` + JSON `documents.json` + yaml `provenance.yaml` per persona
- runtime 非接続 (`src/erre_sandbox/evidence/source_navigator/` 新設、compile script)

## スコープ
含む: compile pipeline (clustering + local summarization) / document_store /
      provenance schema / Kant の 6 cognitive_habit 全件の source 追跡
含まない: WorldModel citation navigator (M10-C 統合は別 task) /
         Evaluation corpus QA harness (defer) /
         Developer navigation skill (defer) /
         クラウド API 使用 / .claude/skills へ自動書き込み

## 受け入れ条件 (idea_judgement.md MVP acceptance 踏襲)
- `kant` の全 `cognitive_habits` (6 件) について `source / flag / trigger_zone /
  document_ids / provenance` を引ける
- provenance missing は loud failure
- generated summary だけを根拠にした assertion が schema 上不可能 (citation discipline)
- default install に重い ML dependency 追加なし
- `uv run pytest tests/test_evidence` が既存 contamination contract を壊さない

## 依存
- なし (個体化 metrics / Social-ToM とは並列可)
```

---

## §7. `idea_judgement.md` / `idea_judgement_2.md` 最終配置案

現在 repo root に untracked で 2 ファイル置かれている。本 synthesis 完了後、以下に move:

```
mv idea_judgement.md   .steering/20260515-pre-m10-design-synthesis/idea-judgement-source-navigator.md
mv idea_judgement_2.md .steering/20260515-pre-m10-design-synthesis/idea-judgement-pdf-survey.md
```

理由:
- snake_case → kebab-case (.steering 内の他ファイル命名に揃える)
- 内容を反映した名前 (`_2` を `pdf-survey` に変更)
- `.steering/` 配下なら git 管理に取り込まれる (root untracked から外れる)

commit 時 staging:
- `.steering/20260515-pre-m10-design-synthesis/requirement.md` (new)
- `.steering/20260515-pre-m10-design-synthesis/design.md` (new、本ファイル)
- `.steering/20260515-pre-m10-design-synthesis/decisions.md` (new)
- `.steering/20260515-pre-m10-design-synthesis/tasklist.md` (new)
- `.steering/20260515-pre-m10-design-synthesis/idea-judgement-source-navigator.md` (renamed)
- `.steering/20260515-pre-m10-design-synthesis/idea-judgement-pdf-survey.md` (renamed)
- `idea_judgement.md` (deleted from root)
- `idea_judgement_2.md` (deleted from root)

Conventional Commits: `docs(steering): pre-M10 design synthesis (Social-ToM eval concrete)`

---

# Attached: design-reimagine.md

# 設計 — pre-M10 design synthesis (REIMAGINE: 現案を意図的に破棄、別視点で再起草)

> **REIMAGINE mandate** (CLAUDE.md 規約「Plan 内 /reimagine 必須」「単発 Plan エージェント 1 発で設計を確定しない」):
> `design-original.md` (506 行、scenario × metric × negative control の格子 capability-oriented eval) を **意図的に破棄** し、根本から別視点で M10 評価体制を再起草する。`design-final.md` で両案を比較し採用案 (hybrid 含) を確定する。
>
> **意図的破棄の対象**: §3.2 7 scenario lib (S-CHA / S-AGO / S-GAR の格子)、§3.3 5 metric capability roster、§3.4 `metrics.social_tom` 専用 table、§3.6 NC-4/NC-5 scenario-specific negative control、§3.5 protocol v3 の v2 直系継承。

---

## §0. 何を「捨てる」か / 何を「捨てない」か

### 捨てる (assumptions の根を断つ)

- **scenario lib という発想**: design-original は 7 scenario を library 化したが、scenario は **設計者の bias** を強く含む。「他者が誤った rumor を持つ」「object_event を片方だけが見た」等のシナリオ選定そのものが、Social-ToM signal の出やすい状況を選んでしまう → bias 検出が困難
- **専用 table `metrics.social_tom`**: namespace の DB11 防御を信用しているが、本当に **新 table が必要か** を再検討。`metrics.individuation` 拡張で済むなら schema migration を 1 件減らせる
- **5 metric を a priori に固定**: capability-oriented (false_belief / info_asymmetry / counterfactual_resistance...) は人間が思いついた capability の roster で、agent が実際に発露する Social-ToM signal がそこに mapping できる保証がない
- **Multi-agent scenario を前提**: M10-0 段階で multi-agent runtime は M11-C 待ち → scenario 設計を multi-agent ありきで作ると M10-0 close 時点で何も動かない (protocol freeze だけが成果になる)
- **150 行 doc から 700-900 LOC への置換** という設計サイズ前提: 「robust = 大きい」とは限らない。むしろ **少数 channel + 高 statistical power** の方が robust なケースが多い (生物学・心理学 eval の標準)

### 捨てない (root invariants)

- v2 draft `metrics.*` namespace + DB11 sentinel poison row test (HIGH-2 由来、防御層は維持)
- v2 draft §2.6 `counterfactual_challenge` 隔離 + SWM write 禁止 + cite-disabled / shuffled-memory / no-individual-layer 3 種 negative control (Layer 3 は捨てない、Social-ToM の前提)
- typed `MetricResult(status, value, reason)` (HIGH-4 由来)
- `calibrate_before_unblinding` state preregister
- User 指示「ToM などを含めた評価体制を具体的に強固に設計してから決めてください」(design-first 原則、ADR-PM-2 revised の根拠)

---

## §1. 別視点: **Process-trace + Statistical-power-first** eval

design-original の **capability-oriented + scenario-lib** を捨てた代替視点として、次の 3 軸で再構築する:

### §1.1 Process-trace eval (D 軸): "agent が何を cite し、何を retrieve し、どう belief revision したか" を直接観測

agent の dialog tick 単位で:
1. **retrieved_memories**: どの memory id を retrieve したか
2. **cited_memory_ids**: 発話 / 内部 reasoning で何を cite として宣言したか
3. **belief_promoted**: SemanticMemoryRecord の belief_kind が `provisional → promoted` に上がった瞬間
4. **WorldModelUpdateHint adoption** (M10-C territory): SubjectiveWorldModel 更新が起きた瞬間
5. **source attribution split**: cited_memory_id の source が「自己観測」「他者 testimony」「inferred」のどれか

これは **scenario を使わない** — 既存 M9-eval Phase 2 の 30 cell (Phase B+C) で取った natural rollout の `raw_dialog.dialog` に対して post-hoc に抽出可能。

利点:
- scenario design bias の混入を回避
- M9-eval 既存 capture (30 cell × 504-tick window) を **追加 capture なしで再利用**
- M10-C `cited_memory_ids` 設計と直接 align (stub schema を M10-0 で立てると M10-C 着手が低 churn)

欠点:
- Social-ToM signal が natural rollout で出ているか不確定 (= 出ていないなら null result が確定する)
- multi-agent dialog の場面が M9-eval natural rollout に含まれているか要確認 (Phase B は stimulus 1 agent、Phase C は natural 1 agent → multi-agent は M11-C 待ちのまま)

### §1.2 Statistical-power-first design (E 軸): 「N を増やす」を最優先

scenario diversity (7 scenario × 1-2 trial) より、**fewer channels × higher N**:

- 計測対象を **3 process-trace channel** に絞る:
  - `provisional_to_promoted_rate` (belief 採用率、`SemanticMemoryRecord.belief_kind` transition)
  - `cited_memory_id_source_distribution` (cite した memory id の source split、`self_observation / other_testimony / inferred` の 3 分類比率)
  - `counterfactual_challenge_rejection_rate` (v2 §2.6 perturbation 下で `cited_memory_ids` に opposite-stance entry が **含まれない** rate、これは Social-ToM の前段 = "他者から押し付けられた情報を自分の belief source として採用しない discipline")
- 各 channel に **N ≥ 200 tick samples** を保証 (M9-eval Phase B+C 30 cell × 504 tick = 15,120 tick の base、十分)
- bootstrap CI 95% で band declare、`calibrate_before_unblinding(P-XXX, split=[run0-2]→cal/[run3-4]→eval)` で circular gate 防止 (v2 §2.5 流用)

利点:
- 3 channel × N 大で statistical power 確保
- 既存 M9-eval Phase B+C capture を再利用 → 追加 G-GEAR run なし
- scenario lib maintenance ゼロ

欠点:
- "他者誤信念の handling" のような **Social-ToM らしい signal** は直接測れない (多人数 dialog が M11-C 待ち)
- M10-0 close 時点では「Social-ToM の **前駆 disposition** を測る」までで、「Social-ToM 能力 itself」は M11-C 以降

### §1.3 ToM の M11-C deferral と M10-0 の役割再定義

これは **設計上の本質的な逆転**:

design-original は M10-0 で Social-ToM eval harness を立てた (= multi-agent scenario protocol + metric + schema)。
reimagine は M10-0 で **ToM の前駆 disposition (cited_memory_id source discipline / belief promotion discipline / counterfactual rejection)** を測り、**ToM 本体 (false_belief / info_asymmetry handling) は M11-C** に明示的に defer する。

理由:
- M10-0 段階で multi-agent runtime が動かない → 7 scenario の **protocol freeze 以上の進捗が物理的に取れない** (design-original §6.2 でも acceptance は "protocol 定義、実走 M11-C" となっている → 結局 doc 主体になる)
- ToM 本体を測るには multi-agent rollout が必須 → M11-C の `m11-c-multi-individual-same-base-validation` task の中で integrate するのが自然
- M10-0 では「individual の cite/belief discipline が、後の Social-ToM の前提として保たれているか」を測れば十分 (それ自体が独立した evaluation question)

---

## §2. 再構築した M10-0 評価体制 (Reimagine 版)

### §2.1 評価体制の上位構造 (3 layer に縮減)

```
Layer 1: Individuation (個体化)
  - design-original §3.1 と同じ、v2 draft §2.2 matrix の 11 metric (Burrows / Vendi / centroid / belief_variance / SWM Jaccard / habit_recall / action_adherence / zone_behavior + recovery)
  - 既存 M9-eval Phase B+C 30 cell の raw_dialog.dialog を AnalysisView loader で読み込む
  - schema: `metrics.individuation` (v2 §2.3)

Layer 2: Cite-Belief Discipline (ToM 前駆 disposition)  ← reimagine の中核
  - 3 process-trace channel (§1.2)
  - 既存 M9-eval Phase B+C capture で計測可、追加 G-GEAR run 不要
  - schema: `metrics.individuation` に **3 metric を additive 追加** (新 table 不要)
  - 註: schema の `metric_name` フィールドが TEXT NOT NULL なので、新 metric 名を流すだけで OK (DDL 変更ゼロ)

Layer 3: Counterfactual perturbation (反事実摂動)
  - v2 §2.6 protocol を **そのまま** 採用 (拡張なし、scenario integration は M11-C 移送)
  - 3 種 negative control (cite-disabled / shuffled-memory / no-individual-layer ablation) で十分
  - acceptance: Layer 2 の `counterfactual_challenge_rejection_rate` が baseline_noindividual と統計有意差あり (effect direction = greater)

(deferred)
Layer 4: Social-ToM proper (multi-agent ToM 本体)
  → M11-C task `m11-c-multi-individual-same-base-validation` に統合
  → scenario lib は M11-C 着手時に design (Codex review + /reimagine 経由)
  → M10-0 ではこの Layer の name reservation のみ (`m11-c-social-tom-proper` linkback)

(deferred)
Layer 5: Emotional / cognitive alignment
  → M11+ task `m11-emotional-alignment-rubric` (ADR-PM-5、reimagine 後も維持)
```

### §2.2 Layer 2 channel 詳細 (Cite-Belief Discipline、3 channel)

| Metric | Input channel | What | Aggregation | Phase | Notes |
|---|---|---|---|---|---|
| `provisional_to_promoted_rate` | `SemanticMemoryRecord.belief_kind` transition log per tick | provisional → promoted の rate | per-individual + per-100-tick window | M10-0 active 計測 | belief 採用の慎重さを測る |
| `cited_memory_id_source_distribution` | `LLMPlan.cited_memory_ids` の source 分類 (self_observation / other_testimony / inferred) | 3 source の比率分布 | per-individual + per-100-tick window | M10-0 active 計測 | source attribution の保持を測る (M10-C の前段) |
| `counterfactual_challenge_rejection_rate` | v2 §2.6 perturbation 下の `cited_memory_ids` 集合 | counterfactual_challenge entry が cited_memory_ids に含まれない rate | per-individual × perturbation tick window | M10-0 active 計測 | cite-disabled negative control と相互参照 |

#### 独立性論証

- `provisional_to_promoted_rate` vs `cited_memory_id_source_distribution`: belief substrate vs citation substrate (異 substrate)
- `provisional_to_promoted_rate` vs `counterfactual_challenge_rejection_rate`: belief 採用 (positive action) vs counterfactual 拒否 (negative action) → opposite-direction、独立
- `cited_memory_id_source_distribution` vs `counterfactual_challenge_rejection_rate`: cite した memory の **source** vs cite に **入れなかった** memory → 計測点が disjoint

### §2.3 Schema (新 table 不要、`metrics.individuation` 拡張)

design-original §3.4 で立てた `metrics.social_tom` 専用 table を **廃止**。理由:
- `metrics.individuation` は既に `metric_name TEXT NOT NULL` + `channel TEXT NOT NULL` を持つ (v2 §2.3)
- Layer 2 の 3 metric を `metric_name='cite_belief_discipline.provisional_to_promoted_rate'` 等の **dotted namespace** で同 table に流すだけで OK
- schema migration は **DDL 変更ゼロ** (rows insert のみ)
- DB11 sentinel poison row test は `metrics.individuation` で既に testing 範囲、Layer 2 の sentinel row も同 test で自動 cover

#### サイドカー JSON

- `*.duckdb.individuation.json` (v2 で既に sidecar 既存) の中に Layer 2 summary を **同居** (新 sidecar file を作らない)
- training manifest input にしない (既存 DB11 sentinel で cover)

### §2.4 Counterfactual perturbation protocol (v2 §2.6 そのまま採用、v3 拡張なし)

design-original §3.5 で立てた protocol v3 (Social-ToM scenario 統合) を **廃止**。v2 §2.6 をそのまま採用:

```
prep:
  1. base individual を T_base = 200 tick (preferred_zone) → baseline:
     - Burrows / cognitive_habit_recall / action_adherence (Layer 1)
     - provisional_to_promoted_rate / cited_memory_id_source_distribution (Layer 2)

perturbation:
  2. counterfactual_challenge channel に opposite-stance content N=5 を injection
  3. T_perturb = 50 tick → perturbed_floor 計測

recovery:
  4. T_recover = 200 tick → post recovery 計測

metric:
  Layer 1: recovery_rate (Burrows / habit / decision、v2 既存)
  Layer 2: counterfactual_challenge_rejection_rate
         = 1 - (perturbation tick で cited_memory_ids に counterfactual entry を含む tick の比率)
```

### §2.5 Negative control (v2 既存 3 種を踏襲、Social-ToM 用 NC-4/NC-5 廃止)

design-original §3.6 で立てた NC-4 shuffled-recipient / NC-5 perspective-isolation を **廃止**。理由:
- scenario lib が消えたため shuffled-recipient (addressee 操作) の対象がない
- perspective-isolation も同様 (1 人称化する scenario がない)
- 既存 3 種 (NC-1 cite-disabled / NC-2 shuffled-memory / NC-3 no-individual-layer-ablation) で Layer 2 の 3 metric を十分 cover

Layer 2 metric × 3 negative control の acceptance:

| Metric | NC-1 cite-disabled 期待 | NC-2 shuffled-memory 期待 | NC-3 no-individual-layer 期待 |
|---|---|---|---|
| provisional_to_promoted_rate | 不変 (negative control が belief substrate に作用しない) | 不変 | rate ≈ 0 (individual layer ない → promote しない) |
| cited_memory_id_source_distribution | inferred 比率増、other_testimony 比率低下 | 全 source random distribution | self_observation 100% (other 不在) |
| counterfactual_challenge_rejection_rate | rejection 100% (cite-disabled なので絶対 reject) | rejection 100% (shuffled なので絶対 reject) | undefined (Layer 自体ない) |

### §2.6 Threshold preregister (Layer 2 専用追記、`thresholds.md`)

| Threshold | State | Protocol |
|---|---|---|
| `provisional_to_promoted_rate` band | calibrate_before_unblinding(P-PPR, split=[Phase B+C run0-2]→cal/[run3-4]→eval) | bootstrap 1000 resample、95% CI、effect direction = none (両方向ありうる、distribution として宣言) |
| `cited_memory_id_source_distribution` divergence (Jensen-Shannon vs baseline) | calibrate_before_unblinding(P-CMSD, split=同上) | per-source bootstrap、JS divergence band |
| `counterfactual_challenge_rejection_rate` lower bound | calibrate_before_unblinding(P-CCRR, split=同上、§2.4 perturbation 下) | effect direction = greater than baseline_noindividual |

design-original §3.7 の 5 threshold (false_belief / info_asymmetry / counterfactual_resistance / opposite_stance / source_attribution) を **廃止** し、上記 3 threshold に置換。

### §2.7 Acceptance (Reimagine 版)

| ID | criterion | rationale |
|---|---|---|
| A1 (v2 既存) | Layer 1 既存 11 metric が typed `MetricResult` を返す | v2 既存 |
| A2 (新、Layer 2) | Layer 2 3 metric が `metrics.individuation` の `metric_name='cite_belief_discipline.*'` で row を返す | additive schema 検証 |
| A3 (新、Layer 2) | M9-eval Phase B+C 30 cell × 504 tick から Layer 2 3 metric が抽出可、`status='valid'` を返す比率 ≥ 90% | 既存 capture 再利用 |
| A4 (新、Layer 2 × NC) | §2.5 表 9 cell の期待値が hold (bootstrap CI 95% band 内) | negative control 健全性 |
| A5 (v2 既存) | DB11 sentinel poison row test が Layer 2 row も reject | DB11 拡張不要、自動 cover |
| A6 (新、Layer 2) | Layer 2 metric × Layer 1 metric の相関行列で |r| ≥ 0.85 ペア検出時 warn | v2 A10 拡張 |
| A7 (v2 既存) | schema 変更ゼロ (`metrics.individuation` への row insert のみ) | v2 既存に加えて Layer 2 も DDL 変更なし |
| A8 (v2 既存) | `--compute-individuation` flag off で既存 CLI byte-for-byte 不変 | v2 既存 |
| A9 (新、Layer 2) | Layer 2 protocol が M11-C で extend されることが thresholds.md に declare されている | M11-C への defer 明示 |

design-original §3 の A1-A11 + NC-4/NC-5 を本リストに置換。

---

## §3. WP 分割 (Reimagine 版)

| WP | 内容 | LOC 想定 | depends |
|---|---|---|---|
| WP1 (v2 既存、+Layer 2) | `src/erre_sandbox/eval/individuation/` 関数群 + MetricResult typed + provenance fields + **3 新 Layer 2 metric 関数** | ~850 (v2 ~700 + Layer 2 ~150) | evidence/tier_b |
| WP2 (v2 既存、変更なし) | DuckDB schema migration (`metrics.individuation` table、Layer 2 は同 table、DDL 変更なし) | ~150 | WP1 |
| WP3 (v2 既存、+Layer 2 flag) | M9-eval CLI `--compute-individuation` flag + sidecar JSON + DB11 sentinel poison row test (Layer 2 row も含む) | ~280 (v2 ~250 + Layer 2 ~30) | WP1, WP2 |
| WP5 (v2 既存、変更なし) | `AnalysisView` loader (raw_dialog.dialog window 抽出、Layer 2 も同じ loader) | ~200 | (none) |
| WP6 (v2 既存、変更なし) | Cache benchmark framework | ~250 | (none) |
| WP7 (v2 既存、変更なし) | Prompt ordering contract spec | ~80 lines doc | (none) |
| WP8 (v2 既存、+Layer 2 tests) | Unit tests (≥ 35、Layer 1 25 + Layer 2 10) + integration test + correlation matrix | ~850 | WP1-3, WP5 |
| WP9 (v2 既存、+Layer 2 threshold) | `thresholds.md` 起草 (Layer 1 8 threshold + Layer 2 3 threshold) | ~180 lines doc | (none) |
| WP10 (v2 既存、protocol v2 そのまま) | Recovery protocol spec (v2 §2.6 そのまま、Social-ToM 拡張なし) | ~120 lines doc | (none) |
| ~~WP11 (削除)~~ | Social-ToM eval harness は M11-C へ defer | — | — |
| ~~WP12+ (削除)~~ | scenario lib / NC-4 / NC-5 等は全て M11-C 移送 | — | — |

Total LOC 想定: **~2960 production + ~850 test = ~3810** (design-original の Social-ToM 専用 ~700-900 を Layer 2 拡張 ~180 production + ~100 test に圧縮)

依存最小化: design-original と同じく WP5 (loader) 先行、WP1-3 並行。

---

## §4. Reimagine 版の利点 / 欠点

### 利点

1. **既存 M9-eval Phase B+C capture を追加 run なしで再利用** (G-GEAR overnight 不要、Mac 単独で完結)
2. **schema migration を 1 件減らす** (`metrics.social_tom` 専用 table 廃止 → `metrics.individuation` 拡張で完結)
3. **scenario design bias を回避** (scenario lib そのものを廃止)
4. **M10-0 close 時に動く evidence が出る** (design-original は protocol freeze 中心 → 実走 M11-C で M10-0 は doc 主体)
5. **M11-C task scope が clean** (Social-ToM 本体は M11-C で multi-agent rollout 着手と同時に design、scope creep 防止)
6. **maintenance cost を縮小** (scenario lib + scenario protocol version 管理が消える)
7. **Codex review への explanation が短い** (Layer が 4 → 3、metric が 5 + Layer1 11 → 3 + Layer1 11)

### 欠点

1. **"Social-ToM" の literal な evaluation が M10-0 で動かない** (M11-C 待ち) — User の「ToM などを含めた評価体制」の "ToM" 部分が M10-0 で active 化しない
2. **multi-agent runtime が無い段階で何が測れるかが Layer 2 「前駆 disposition」に限定** → ToM の核 (theory-of-other-mind) は M11-C
3. **User の design-first 指示への応答として弱く見える可能性** (synthesis 草稿 → reimagine で scope 縮小に見える)
4. **Layer 2 channel が embedding 依存ではない** (text-structural feature) → 多言語性に強いが、subtle な ToM signal は逃す可能性
5. **WP11 を捨てるため、design-original Codex review の HIGH 5 等の Codex 反映済 finding が一部 redundant 化** (具体的には design-original §3.5 protocol v3 拡張部分)

---

## §5. design-original vs design-reimagine の比較表 (design-final.md §X で決定)

| 評価軸 | design-original (capability-oriented scenario-lib) | design-reimagine (process-trace + power-first) |
|---|---|---|
| Layer 数 | 4 (Indiv / Social-ToM / Counterfactual / Emotional) | 3 (Indiv / Cite-Belief Discipline / Counterfactual) |
| 新 metric 数 (Layer 2 相当) | 5 + 2 NC = 7 | 3 |
| Schema 追加 | 新 table `metrics.social_tom` + DDL | 既存 `metrics.individuation` への row 追加のみ (DDL 変更ゼロ) |
| Scenario lib | 7 scenario × multi-variant | なし (process-trace のみ) |
| Negative control | 5 種 (NC-1〜NC-5) | 3 種 (v2 既存、NC-4/NC-5 廃止) |
| 追加 G-GEAR run | あり (Social-ToM scenario 走行) | なし (Phase B+C 既存 capture 再利用) |
| M10-0 close 時の active 計測 | protocol freeze 中心 (実走は M11-C) | 3 Layer 2 metric が active 計測 (既存 capture から) |
| LOC 想定 | ~3750 + Social-ToM sub-task ~700-900 (= ~4500-4650) | ~3810 (single sub-task に集約) |
| Sub-task 数 | 3 (Indiv / Social-ToM eval / Source nav) | 2 (Indiv + Source nav、Social-ToM eval は M11-C へ移送) |
| M11-C 接続 | Social-ToM eval を M11-C で実走するだけ | M11-C で Layer 4 (Social-ToM proper) を新規 design (scope clean) |
| Codex review 圧縮率 | 投げる context 大 (scenario lib + 5 metric + 5 NC + protocol v3) | 投げる context 中 (3 metric + 3 NC + protocol v2 そのまま) |
| User 指示「ToM などを含めた評価体制を具体的に強固に設計」への応答 | 直接的: ToM scenario を作る | 間接的: ToM の前駆を測る + ToM 本体は M11-C に明示 defer |
| design bias | 高 (scenario 選定で signal の出やすい状況を選ぶ) | 低 (natural rollout から post-hoc 抽出) |
| Statistical power | 中 (scenario 7 × trial 数限定) | 高 (3 channel × N=15,120 tick from Phase B+C) |

---

## §6. Hybrid 採用候補 (design-final.md で決める素材)

両案の利点を取る hybrid 候補:

### Hybrid-A: Reimagine ベース + ToM scenario を M10-0 minimum (4 scenario) で残す

- Reimagine の Layer 2 (3 process-trace metric) を採用 (中核)
- design-original の scenario lib を **7 → 4** に削減 (S-CHA-1 only / S-AGO-1 only / S-GAR-1 only / S-GAR-2 only)
- scenario は M10-0 で **spec doc のみ**、実走 M11-C は明示
- NC-4 shuffled-recipient は **scenario S-CHA-1 専用** に限定して残す (Layer 2 process-trace に対する scenario-bias の counter-check として活用)
- 新 table `metrics.social_tom` は廃止 (`metrics.individuation` に統合)

### Hybrid-B: design-original ベース + Layer 2 を追加

- design-original の Social-ToM eval harness はそのまま
- Reimagine の Layer 2 (3 process-trace metric) を **追加 channel** として実装
- M10-0 close で Layer 1 + Layer 2 (active) + Social-ToM (protocol + scenario lib + schema、実走 M11-C) を出す
- LOC 想定が最大 (~5000+)、scope が最も広い

### Hybrid-C: Reimagine 全面採用、ToM scenario は M11-C で新規 design

- Reimagine をそのまま採用
- ToM scenario / Social-ToM eval harness は M11-C task `m11-c-social-tom-proper` を新規起票
- M10-0 sub-task が 2 (Indiv main + Source nav MVP) に削減
- M11-C への explicit handoff (Layer 4 name reservation + 設計指針)

---

## §7. 採用判断は design-final.md に書く (本書はあくまで「破棄して再生成した別視点案」)

`design-final.md` で:
- §A: 両案を § per § で対照
- §B: Hybrid-A / B / C のいずれを採用するか + 採用根拠
- §C: 採用案に Codex 13th review HIGH 反映を upsert する余地を残す

本書 (design-reimagine.md) はここで close。**design-original を捨てた状態の純粋な別視点** として保持する (Codex review でも両案を示すことで independent stress-test の効力が増す)。

---

# Attached: decisions.md

# 重要な設計判断 — pre-M10 design synthesis

## ADR-PM-1: source_navigator (idea_judgement.md) を別 sub-task として M10-0 main と並列起票

- **判断日時**: 2026-05-15
- **背景**: `idea_judgement.md` で source_navigator (Corpus2Skill 型ローカル再実装) が M10-0 preflight 候補と判定された (8/10、強い採用候補)。v2 draft `m10-0-concrete-design-draft.md` には未吸収。M10-0 main task に WP として吸収するか、独立 sub-task にするかの判断が必要。
- **選択肢**:
  - A: M10-0 main 内 WP11 として吸収 (LOC +~1000、scope 拡大)
  - B: 独立 sub-task `m10-0-source-navigator-mvp` として並列起票
  - C: M10-A 以降に defer (cited_memory_ids が M10-C で立ってから integrate)
- **採用**: B
- **理由**:
  - runtime 非接続で M10-0 main の blocker にならない
  - idea_judgement.md の MVP acceptance (Kant only / depth 2 / 6 cognitive_habits 全件追跡 / provenance loud failure) がそのまま requirement.md に流用可能
  - scope 隔離で個体化 metrics PR の churn を増やさない
  - C (M10-C defer) は cited_memory_ids 接続前に navigator を作っておく方が citation discipline を deferral なしに enforce できる
- **トレードオフ**:
  - sub-task が 3 つに増える (M10-0 close 条件が複雑化)
  - source_navigator の MVP 単独では他の M10-0 sub-task と直接 integration しない期間が発生
- **影響範囲**: M10-0 main の close 条件、M10-C task definition の前提
- **見直しタイミング**:
  - MVP 着手時に Kant 以外の persona (Nietzsche / Rikyu) の corpus 量が異常に少ない / 多いと判明した場合、scope 見直し
  - M10-C `WorldModelUpdateHint.cited_memory_ids` 設計時に source_navigator output format との不整合が判明した場合

## ADR-PM-2: Social-ToM eval を独立 sub-task `m10-0-social-tom-eval` に格上げ (User 直接指示で revised)

- **判断日時**: 2026-05-15 (revised from "WP11 ~150 行 doc" 当初案)
- **背景**: 当初は idea_judgement_2.md §2 Social-ToM minimum spec を M10-0 main の WP11 ~150 行 doc で軽く済ます方針だった。User 直接指示「m10 では具体的に ToM などを含めた評価体制を具体的に強固に設計してから決めてください」を受け、placement-first から design-first に逆転。design.md §3 で concrete 化した結果、Social-ToM eval は 10 sub-section / 新 DuckDB table / 5 metric / 7 scenario / 2 新規 negative control / 5 threshold preregister となり、150 行 doc に収まらない実装規模 (production ~700-900 LOC + scenario lib + protocol + tests) に膨らんだ。
- **選択肢**:
  - A: 当初案維持 (WP11 ~150 行 doc、code は M11-C 担当)
  - B: M10-0 main の WP として吸収 (WP11-WP20 を Social-ToM 用に追加、LOC +1000-1500)
  - C: 独立 sub-task `m10-0-social-tom-eval` に格上げ (M10-0 individuation main と並列、共有 schema namespace `metrics.*`)
- **採用**: C
- **理由**:
  - design.md §3 設計の規模が WP11 doc 1 件に収まらない (scenario lib + metric 実装 + 2 新 negative control + 共有 protocol v3 拡張 + tests)
  - 独立 PR にすると review focus + regression risk が分離できる
  - schema namespace は v2 draft の `metrics.*` を共有することで DB11 sentinel grep の防御範囲を維持
  - counterfactual perturbation protocol v3 (design.md §3.5) は両 sub-task の共有基盤 → individuation main 側に実装、Social-ToM 側は scenario integration のみ、で依存順序を明示化できる
  - User 指示 (design-first + robust) を全 sub-task review で守る土台になる
- **トレードオフ**:
  - sub-task が増える (M10-0 close 条件が 3 sub-task green)
  - protocol v3 共有実装の **順序依存** が発生 (individuation main 完了 → Social-ToM 着手、または同時 PR で個体化側に protocol 実装合意)
- **影響範囲**: M10-0 main close 条件、v2 draft `m10-0-concrete-design-draft.md` の §2.6 protocol 実装責務、`thresholds.md` の構造
- **見直しタイミング**:
  - Social-ToM eval 着手時に scenario lib LOC 想定 (~300-500) が大幅超過した場合、scenario を 7 → 4 に削減 (S-CHA-1 / S-AGO-1 / S-GAR-1 / S-GAR-2 のみ) で M11-C に追加 scenario を defer
  - protocol v3 共有実装で conflict が発生した場合、protocol を schema-level に抽象化して両 sub-task が import する形に refactor

## ADR-PM-3: PEFT ablation registry (idea_judgement_2.md §4) を M12+ task gate に置く

- **判断日時**: 2026-05-15
- **背景**: idea_judgement_2.md §4 で `experiment_id / arms / metrics` の yaml 形式が提示済。QDoRA は M12+ defer は v2 draft §2.7 で確定。本 synthesis で何らかの形で吸収するかの判断が必要。
- **選択肢**:
  - A: 本 synthesis で別 sub-task `m12-peft-ablation-registry-init` を scaffold (PEFT 実装前に registry yaml 規約を fix)
  - B: M12+ task `m12-peft-ablation-qdora` の前提 gate に置き、本 synthesis では linkback のみ
  - C: 完全 defer、idea_judgement_2.md §4 は M12+ 着手時の素材として保持
- **採用**: B
- **理由**:
  - registry format は QDoRA 実装着手時に initialize すれば足りる
  - yaml 規約を M10-0 段階で固定すると、M12+ 着手時の SGLang serving 互換 / PEFT version pin / bench arm 選定の empirical evidence を活かせない
  - linkback (v2 draft §2.7 + 本 synthesis §4) で M12+ task definition 時に exception なく拾える
- **トレードオフ**: M12+ task scaffold 時に registry yaml を起こす作業が 1 段増える (~30 分相当)
- **影響範囲**: M12+ task `m12-peft-ablation-qdora` の前提 gate
- **見直しタイミング**: M10-0 + M11 完了後、QLoRA-LoRA baseline freeze の段階で再評価

## ADR-PM-4: `idea_judgement.md` / `idea_judgement_2.md` を `.steering/20260515-pre-m10-design-synthesis/` に rename move

- **判断日時**: 2026-05-15
- **背景**: 現 repo root に 2 ファイル untracked で配置されている。本 synthesis の素材として参照しているため、どこかに保存して git 管理に取り込む必要がある。
- **選択肢**:
  - A: 現位置 (root) に置いたまま git add
  - B: `.steering/20260515-pre-m10-design-synthesis/` 配下に move (現在の命名規約に合わせる)
  - C: `docs/research-notes/` 新設して move
- **採用**: B
- **理由**:
  - .steering/ は本来「作業記録ディレクトリ」(CLAUDE.md 規約) で、本 synthesis の素材として明示的に紐付く
  - root は task に紐付かない untracked ファイル置き場として綺麗に保つ
  - C (docs/research-notes/) は新ディレクトリ規約を導入する追加判断が必要、本 synthesis の scope を超える
- **rename 規則**: snake_case → kebab-case、内容反映の名前変更
  - `idea_judgement.md` → `idea-judgement-source-navigator.md`
  - `idea_judgement_2.md` → `idea-judgement-pdf-survey.md`
- **トレードオフ**: `.steering/` 内のファイル数が増える (現在の synthesis ディレクトリは 6 ファイル構成になる)
- **影響範囲**: git status、commit staging、design.md §7 で参照される path
- **見直しタイミング**: なし (一度 move したら revert は普通起きない)

## ADR-PM-5: Emotional / cognitive alignment (HEART / MentalAlign) を M10-0 範囲外 / M11+ defer

- **判断日時**: 2026-05-15
- **背景**: idea_judgement_2.md §1 の項目表で HEART / MentalAlign / MentalBench が「中-高」評価されている。User 指示「ToM などを含めた評価体制」の「など」に該当する候補だが、idea_judgement_2.md 自身が「臨床主張は不可、Tier C/D rubric (manual sparse review)」と限定している。
- **選択肢**:
  - A: M10-0 評価体制 Layer 4 として concrete 設計に含める (design.md §3.9 で実装)
  - B: M10-0 範囲外、M11+ task `m11-emotional-alignment-rubric` として defer
  - C: 完全 deprecate (採用しない宣言)
- **採用**: B
- **理由**:
  - quantitative pipeline (Layer 1-3) と分離が安全 — Tier C/D rubric は manual review LOC が大きく、qualitative judgement に依存
  - 臨床用語の安易使用は ERRE 研究プラットフォームの説明責任を弱める (clinical claim 回避が ERRE の design rule)
  - 個体化 + Social-ToM の robust 設計が固まる前に emotional layer を加えると、metric 間の confound が増える (§3.8 相関行列の解釈が複雑化)
  - C (完全 deprecate) は idea_judgement_2.md の評価を尊重しない、研究プラットフォームの evaluation 多角化の価値を失う
- **トレードオフ**:
  - User 指示「ToM などを含めた」の「など」に emotional alignment を取り込まない判断 → User redirect risk あり (本 ADR で明示するため、redirect 時に判断見直し可能)
  - M10-0 close 後の M11 task quota に 1 件追加される
- **影響範囲**: M10-0 評価体制 Layer 4 (defer 宣言)、M11 task list
- **見直しタイミング**:
  - User からの直接指示 (emotional layer を M10-0 に含めるべき) があれば即見直し
  - M10-0 + M11 完了後、Social-ToM 5 metric が emotional channel と confound していると empirical evidence で示された場合、ADR-PM-5 を revise して emotional layer を M11 で statistical baseline として実装

hook: SessionStart
hook: SessionStart Completed
hook: UserPromptSubmit
hook: UserPromptSubmit Completed
codex
`erre-workflow` を参照して、このレビューを設計レビューとして扱います。実装や `.steering/` への追記は行わず、提示文書だけを根拠に verdict と findings を返します。
hook: PreToolUse
hook: PreToolUse Completed
exec
/bin/zsh -lc "sed -n '1,220p' .agents/skills/erre-workflow/SKILL.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
---
name: erre-workflow
description: >
  ERRE-Sandbox task workflow for Codex. Use when starting, designing, implementing,
  reviewing, or finishing repository work; when the user mentions /start-task,
  /add-feature, /fix-bug, /refactor, /reimagine, /review-changes, or /finish-task;
  or when .steering records, Codex setup, task plans, or implementation handoffs are needed.
---

# ERRE Workflow

This is the Codex-native replacement for the Claude slash-command workflow. Claude command
files in `.claude/commands/` are reference material only; Codex should execute the workflow
through normal tool use, `.steering/` records, skills, hooks, and custom agents.

## Quick Start

1. Read `AGENTS.md`, `docs/development-guidelines.md`, and the relevant domain skill.
2. Create or update `.steering/YYYYMMDD-task-name/` before implementation work:
   `requirement.md`, `design.md`, and `tasklist.md` are required.
3. For design-heavy work, keep implementation paused until a plan is accepted. If the task
   has multiple plausible designs, perform a reimagine pass before editing source files.
4. Implement in small steps, updating `tasklist.md` as work completes.
5. Verify with focused checks first, then the documented full checks when feasible.
6. Finish by reviewing the diff and recording any decisions or limitations.

Use subagents only when the user explicitly asks for delegation or parallel agent work.
When they do, prefer the project-scoped agents in `.codex/agents/`.

## Task Start

Create `.steering/YYYYMMDD-task-name/` with:

- `requirement.md`: background, goal, scope, out of scope, acceptance criteria.
- `design.md`: approach, changed areas, compatibility, test strategy, rollback.
- `tasklist.md`: checkboxes at roughly 30-minute granularity.
- `decisions.md`: only for meaningful tradeoffs or policy choices.
- `blockers.md`: only when blocked or carrying deferred risk.

Use the current local date in `YYYYMMDD`. Prefer a short kebab-case task name.

## Implementation Flows

- **Feature**: read existing patterns, document the design, implement narrowly, add tests or
  verification proportional to risk, update docs when behavior changes.
- **Bug fix**: reproduce or explain the failure, record root cause, add or identify a
  regression check when feasible, then make the smallest defensible fix.
- **Refactor**: establish current checks first, preserve behavior, change in small steps,
  and avoid mixing feature or bug-fix work into the same task.

For source edits under `src/erre_sandbox/`, always consider:

- `architecture-rules` for layer direction and GPL/cloud API constraints.
- `python-standards` for Python style.
- `error-handling` when async, retry, timeout, WebSocket, sqlite, or LLM fallback behavior changes.
- `test-standards` when adding or changing tests.

## Reimagine

Use this for architecture, public interfaces, difficult bugs, and designs with multiple
credible approaches:

1. Save the first plan as `design-v1.md`.
2. Re-read only `requirement.md` and produce a fresh alternative in `design.md`.
3. Compare the two in `design-comparison.md`.
4. Choose v1, v2, or a hybrid and record the reason in `decisions.md`.

Do not use reimagine after implementation has already created side effects that would need
manual rollback.

## Network Access Policy

The `.codex/config.toml` workspace_write sandbox defaults to `network_access = false`
(SH-3 ADR, 2026-05-13). Codex `web_search = "live"` is decoupled and stays enabled —
queries leave the box, but repo contents do not.

Do NOT toggle `network_access = true` without explicit per-session user approval.
If a task genuinely needs egress (e.g. `uv sync` for a fresh dependency), surface
the need to the user first and request a one-shot override via `--config
sandbox_workspace_write.network_access=true`. Do not commit a `true` value into
`.codex/config.toml`. See `AGENTS.md` "Network access policy" section.

## Review And Finish

Before final delivery:

- Run focused checks for touched areas.
- Run `uv run ruff check src tests`, `uv run ruff format --check src tests`,
  `uv run mypy src`, and `uv run pytest` when feasible.
- Review `git diff` for unrelated changes and do not revert user work.
- Update `tasklist.md` and `design.md` with what actually happened.
- Mention skipped checks or residual risk in the final response.

Do not commit unless the user asks. If committing, use `git-workflow`.

codex
# Codex 13th review — pre-M10 design synthesis (Hybrid-A revised)

**Verdict**: ADOPT-WITH-CHANGES

## Summary
Hybrid-A revised is the right direction: it avoids a premature Social-ToM harness, keeps M10-0 measurable, and preserves M11-C handoff material.  
The current design still overclaims active Layer 2 coverage and statistical power. The main fixes are acceptance/gating changes, not a return to `metrics.social_tom`.  
Address the HIGH findings before scaffolding `m10-0-individuation-metrics`.

## HIGH findings
- HIGH-1: A12 is not realistic as written. Phase B+C single-agent capture cannot guarantee `cited_memory_ids`, `source` tags, `other_testimony`, or perturbation windows. Split A12 by metric: M-L2-1 active, M-L2-2 schema-dependent, M-L2-3 perturbation-run-dependent.
- HIGH-2: M-L2-3 baseline is structurally wrong. `baseline_noindividual` is undefined or trivially 100% rejection, so “greater than baseline_noindividual” can invert the conclusion. Use NC-3 as degenerate, and compare against a leak/random-citation positive control or within-individual perturbation control.
- HIGH-3: `N=15,120 tick` overstates power if ticks are treated as independent. Use block/cluster bootstrap by run/cell/individual/window and report effective N.
- HIGH-4: Layer 2 is not a sufficient statistic for Social-ToM. It is a process-trace prerequisite/proxy. Make the claim boundary explicit: M10-0 measures cite-belief discipline; Social-ToM proper remains M11-C.

## MEDIUM findings
- MEDIUM-1: ADR-PM-2 should be superseded by new ADR-PM-6, not silently rewritten. Keep PM-2 historical and mark status `superseded`.
- MEDIUM-2: WP11 4 scenario spec needs handoff metadata: `freshness_date=2026-05-15`, `protocol_version`, dependency pins, rereview gate, expected inputs, and failure modes.
- MEDIUM-3: M-L2-1 `effect direction = none` is acceptable only as descriptive estimation. Do not make “band declare” a pass/fail gate unless the band is frozen before eval.
- MEDIUM-4: Dotted namespace in `metrics.individuation` is sound, but add an allowlist/namespace test so DB11 sentinel coverage does not become purely table-level.
- MEDIUM-5: Add deprecation headers to `design-original.md` and `design-reimagine.md`: historical reference only; implementation reference is `design-final.md`.

## LOW findings
- LOW-1: Absolute dates and base commit should be added to document headers; prose like “next session” can remain in narrative sections.
- LOW-2: Same-day ADR count is fine if status/supersession is clear. Do not artificially split dates.
- LOW-3: Standardize wording: use `Cite-Belief Discipline` and `cite_belief_discipline.*` everywhere.

## Q1-Q12 verbatim answers
Q1: Not rigorous enough. Substrate separation is a hypothesis, not proof. M-L2-1 and M-L2-3 can share a latent “belief acceptance under pressure” factor, so `|r| >= 0.85` is plausible. Keep the correlation guard and predeclare collapse/revision behavior.

Q2: Same-day revise is acceptable, but cleanest is ADR-PM-6 superseding ADR-PM-2. Do not erase PM-2’s historical rationale.

Q3: If M10-0 requires valid M-L2-2 on real captures, a stub/data contract is required. If M10-C owns `cited_memory_ids`, M10-0 should return `unsupported` with a pinned reason and test that behavior.

Q4: The 4 specs are directionally sufficient, but not independently durable for a months-later handoff unless they include freshness date, protocol version, dependencies, expected inputs, and rereview criteria.

Q5: No. `status='valid' >= 90%` for all three Layer 2 metrics is too optimistic. Single-agent natural rollout especially weakens `other_testimony` and source-distribution claims.

Q6: Yes, baseline should be reconsidered. NC-3 should be degenerate/undefined for M-L2-3, not the comparator for “greater”.

Q7: ADR-PM-5 does not discard “など” if it explicitly says emotional alignment is deferred, not rejected, and explains clinical-claim avoidance. Redirect risk remains medium.

Q8: It is weak as a gate. Make M-L2-1 descriptive, or preregister a prior/ROPE and freeze calibration before eval.

Q9: `design-final.md` should be sufficient. Add deprecation/supersession headers to the other two documents to prevent accidental implementation from obsolete plans.

Q10: Add absolute date/base commit to headers and ADRs. Do not mechanically replace every readable relative phrase.

Q11: Seven same-day ADRs are operationally reviewable if each has status, supersedes/superseded-by, and scope. Splitting across days would be less honest.

Q12: The main structural failure mode is “measurable proxy drift”: Layer 2 may look robust because logs exist, while true Social-ToM remains untested. Guard this with claim boundaries and an explicit M11-C rereview gate.

## Stress-test
The strongest failure mode is that Hybrid-A revised can age as a retreat from capability-oriented ToM: future readers may see active metrics and assume ToM was measured. It was not. The design should repeatedly state that Layer 2 measures citation/belief discipline only.

The second failure mode is statistical: many ticks do not equal many independent observations. Without clustered inference, the design can produce narrow CIs over autocorrelated traces.

The third failure mode is schema dependency: M-L2-2 and M-L2-3 quietly depend on M10-C-owned citation fields. Either stub the contract deliberately or downgrade those metrics to `unsupported` until M10-C.
hook: Stop
hook: Stop Completed
2026-05-15T10:19:23.056666Z ERROR codex_core::session: failed to record rollout items: thread 019e2b24-3f1c-7742-aeb4-796be1378de8 not found
tokens used
66,261
# Codex 13th review — pre-M10 design synthesis (Hybrid-A revised)

**Verdict**: ADOPT-WITH-CHANGES

## Summary
Hybrid-A revised is the right direction: it avoids a premature Social-ToM harness, keeps M10-0 measurable, and preserves M11-C handoff material.  
The current design still overclaims active Layer 2 coverage and statistical power. The main fixes are acceptance/gating changes, not a return to `metrics.social_tom`.  
Address the HIGH findings before scaffolding `m10-0-individuation-metrics`.

## HIGH findings
- HIGH-1: A12 is not realistic as written. Phase B+C single-agent capture cannot guarantee `cited_memory_ids`, `source` tags, `other_testimony`, or perturbation windows. Split A12 by metric: M-L2-1 active, M-L2-2 schema-dependent, M-L2-3 perturbation-run-dependent.
- HIGH-2: M-L2-3 baseline is structurally wrong. `baseline_noindividual` is undefined or trivially 100% rejection, so “greater than baseline_noindividual” can invert the conclusion. Use NC-3 as degenerate, and compare against a leak/random-citation positive control or within-individual perturbation control.
- HIGH-3: `N=15,120 tick` overstates power if ticks are treated as independent. Use block/cluster bootstrap by run/cell/individual/window and report effective N.
- HIGH-4: Layer 2 is not a sufficient statistic for Social-ToM. It is a process-trace prerequisite/proxy. Make the claim boundary explicit: M10-0 measures cite-belief discipline; Social-ToM proper remains M11-C.

## MEDIUM findings
- MEDIUM-1: ADR-PM-2 should be superseded by new ADR-PM-6, not silently rewritten. Keep PM-2 historical and mark status `superseded`.
- MEDIUM-2: WP11 4 scenario spec needs handoff metadata: `freshness_date=2026-05-15`, `protocol_version`, dependency pins, rereview gate, expected inputs, and failure modes.
- MEDIUM-3: M-L2-1 `effect direction = none` is acceptable only as descriptive estimation. Do not make “band declare” a pass/fail gate unless the band is frozen before eval.
- MEDIUM-4: Dotted namespace in `metrics.individuation` is sound, but add an allowlist/namespace test so DB11 sentinel coverage does not become purely table-level.
- MEDIUM-5: Add deprecation headers to `design-original.md` and `design-reimagine.md`: historical reference only; implementation reference is `design-final.md`.

## LOW findings
- LOW-1: Absolute dates and base commit should be added to document headers; prose like “next session” can remain in narrative sections.
- LOW-2: Same-day ADR count is fine if status/supersession is clear. Do not artificially split dates.
- LOW-3: Standardize wording: use `Cite-Belief Discipline` and `cite_belief_discipline.*` everywhere.

## Q1-Q12 verbatim answers
Q1: Not rigorous enough. Substrate separation is a hypothesis, not proof. M-L2-1 and M-L2-3 can share a latent “belief acceptance under pressure” factor, so `|r| >= 0.85` is plausible. Keep the correlation guard and predeclare collapse/revision behavior.

Q2: Same-day revise is acceptable, but cleanest is ADR-PM-6 superseding ADR-PM-2. Do not erase PM-2’s historical rationale.

Q3: If M10-0 requires valid M-L2-2 on real captures, a stub/data contract is required. If M10-C owns `cited_memory_ids`, M10-0 should return `unsupported` with a pinned reason and test that behavior.

Q4: The 4 specs are directionally sufficient, but not independently durable for a months-later handoff unless they include freshness date, protocol version, dependencies, expected inputs, and rereview criteria.

Q5: No. `status='valid' >= 90%` for all three Layer 2 metrics is too optimistic. Single-agent natural rollout especially weakens `other_testimony` and source-distribution claims.

Q6: Yes, baseline should be reconsidered. NC-3 should be degenerate/undefined for M-L2-3, not the comparator for “greater”.

Q7: ADR-PM-5 does not discard “など” if it explicitly says emotional alignment is deferred, not rejected, and explains clinical-claim avoidance. Redirect risk remains medium.

Q8: It is weak as a gate. Make M-L2-1 descriptive, or preregister a prior/ROPE and freeze calibration before eval.

Q9: `design-final.md` should be sufficient. Add deprecation/supersession headers to the other two documents to prevent accidental implementation from obsolete plans.

Q10: Add absolute date/base commit to headers and ADRs. Do not mechanically replace every readable relative phrase.

Q11: Seven same-day ADRs are operationally reviewable if each has status, supersedes/superseded-by, and scope. Splitting across days would be less honest.

Q12: The main structural failure mode is “measurable proxy drift”: Layer 2 may look robust because logs exist, while true Social-ToM remains untested. Guard this with claim boundaries and an explicit M11-C rereview gate.

## Stress-test
The strongest failure mode is that Hybrid-A revised can age as a retreat from capability-oriented ToM: future readers may see active metrics and assume ToM was measured. It was not. The design should repeatedly state that Layer 2 measures citation/belief discipline only.

The second failure mode is statistical: many ticks do not equal many independent observations. Without clustered inference, the design can produce narrow CIs over autocorrelated traces.

The third failure mode is schema dependency: M-L2-2 and M-L2-3 quietly depend on M10-C-owned citation fields. Either stub the contract deliberately or downgrade those metrics to `unsupported` until M10-C.

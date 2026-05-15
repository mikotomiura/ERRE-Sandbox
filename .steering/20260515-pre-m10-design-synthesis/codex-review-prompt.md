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

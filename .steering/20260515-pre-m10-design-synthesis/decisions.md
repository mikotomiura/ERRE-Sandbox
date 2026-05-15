# 重要な設計判断 — pre-M10 design synthesis

> **Date**: 2026-05-15  **Base commit**: `fb651e7` (main)
>
> 全 ADR は 2026-05-15 同日に立っているが、本書では Codex MEDIUM-1 反映で **status / supersedes / superseded-by** を各 ADR header に明示。同日 7 ADR 連発は Codex Q11 で operationally reviewable と判定済 (Verdict: "Splitting across days would be less honest")。

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

## ADR-PM-2: Social-ToM eval を独立 sub-task `m10-0-social-tom-eval` に格上げ (User 直接指示で revised) **[SUPERSEDED by ADR-PM-6]**

> **Status**: SUPERSEDED
> **Superseded by**: ADR-PM-6 (Hybrid-A revised 採用、Layer 2 を main 統合 + 4 scenario spec doc 救出)
> **Reason for supersession**: `/reimagine` 経由で reimagine 案 (process-trace + power-first) が立ち、両案の hybrid (Hybrid-A revised) が Layer 2 main 統合で済むことが明らかになった。本 ADR の本文は historical rationale として保持。

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

## ADR-PM-6: Hybrid-A revised 採用 (/reimagine 経由、Layer 2 を main 統合 + scenario spec 4 件 doc 救出)

> **Status**: ACTIVE
> **Supersedes**: ADR-PM-2 (Social-ToM eval を独立 sub-task に格上げ、本 ADR で再 revise)
> **Date**: 2026-05-15  **Base commit**: `fb651e7`

- **判断日時**: 2026-05-15 (ADR-PM-2 と同日、本 session 後半)
- **背景**: CLAUDE.md 規約「Plan 内 /reimagine 必須」「単発 Plan エージェント 1 発で設計を確定しない」に従い、`design.md` (capability-oriented scenario-lib、506 行) を `design-original.md` に退避し、`design-reimagine.md` (process-trace + power-first) を意図的に異視点でゼロから起草。両案を §A 対照、§B Hybrid-A revised を採用。User 直接指示「ベストを尽くせ」を受けての /reimagine + Codex review 工程の中核判断。
- **選択肢**:
  - A: design-original そのまま採用 (capability-oriented scenario-lib、5 metric、7 scenario、新 table、5 NC)
  - B: design-reimagine そのまま採用 (process-trace + power-first、3 metric、scenario なし、既存 table、3 NC、M11-C で Social-ToM proper 新規 design)
  - C: Hybrid-A revised (reimagine Layer 2 + original から 4 scenario spec doc 救出、新 table 廃止、Social-ToM 専用 sub-task 廃止)
  - D: Hybrid-B (original そのまま + Layer 2 を additive 追加、LOC 想定 ~5000+ で scope 最大)
  - E: Hybrid-C (reimagine 全面採用、scenario も M11-C で新規 design、M10-0 sub-task 2 に縮小)
- **採用**: C (Hybrid-A revised)
- **理由**:
  - Layer 2 (Cite-Belief Discipline 3 metric) を main 統合することで M10-0 close 時に active 計測 evidence (M9-eval Phase B+C 既存 capture から、追加 G-GEAR run 不要)
  - 新 table `metrics.social_tom` 廃止で DDL 変更ゼロ + DB11 sentinel grep 自動 cover
  - 4 scenario spec doc (S-CHA-1 / S-AGO-1 / S-GAR-1 / S-GAR-2) を WP11 として保持、M11-C `m11-c-social-tom-proper` task への handoff 文書化
  - design bias (scenario 選定 bias) を low に保ちつつ、literal "ToM" compliance を spec doc で確保
  - Statistical power N=15,120 tick base (Phase B+C 30 cell × 504 tick)
  - Codex review に投げる context が中規模 (両案より圧縮、token budget 節約)
  - B (reimagine 全面) は User 指示「ToM などを含めた評価体制」の literal "ToM" を捨てる risk あり、Hybrid で救出
  - D (Hybrid-B) は LOC 想定 ~5000+ で scope creep、PR review burden 大
  - E (Hybrid-C) は scenario 完全廃止で M11-C 着手時の素材ゼロから、scope clean だが M11-C burden 増
- **トレードオフ**:
  - design-original で立てた scenario lib 7 件のうち 3 件 (S-CHA-1c / S-CHA-2 / S-AGO-2) を捨てる (M11-C 着手時の素材として失う)
  - NC-4 shuffled-recipient / NC-5 perspective-isolation を廃止 (scenario lib 縮小で対象消失)
  - protocol v3 拡張を廃止 (v2 §2.6 そのまま)
  - design-original Codex review HIGH 5 の一部 (specifically HIGH-3 recovery protocol false-positive の v3 拡張部分) が redundant 化
- **影響範囲**:
  - ADR-PM-2 を再 revise (Social-ToM 専用 sub-task `m10-0-social-tom-eval` 廃止、Layer 2 を `m10-0-individuation-metrics` main 統合に再格下げ)
  - M10-0 sub-task は 3 並列 → 2 並列 (Indiv main + Source nav MVP)
  - WP11 (~200 行 markdown) を `m10-0-individuation-metrics` main に追加
  - v2 draft `m10-0-concrete-design-draft.md` への Addendum patch (design-final.md §G) が拡張
- **見直しタイミング**:
  - Codex 13th review で HIGH finding がある場合、本 ADR を ADR-PM-7 で部分修正
  - M11-C 着手時に 4 scenario spec doc が独立読解不可能と判明した場合、scenario lib の保持規模を見直し
  - Phase B+C 既存 capture の Layer 2 metric extraction で `status='valid' ≥ 90%` を満たさなかった場合、Layer 2 metric 設計を見直し

## ADR-PM-2 の supersession 整理 (Codex MEDIUM-1 反映)

Codex 13th MEDIUM-1 指摘「ADR-PM-2 should be superseded by new ADR-PM-6, not silently rewritten. Keep PM-2 historical and mark status `superseded`」を反映:

- ADR-PM-2 の header に `[SUPERSEDED by ADR-PM-6]` marker + Status / Superseded-by / Reason 追加 (本書冒頭部分で実施済)
- ADR-PM-6 の header に `Supersedes: ADR-PM-2` 明示
- ADR-PM-2 本文は historical rationale として変更せず保持
- 結果: 2 ADR の supersession 関係が `Status:` field で operational に reviewable

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

## ADR-PM-7: Codex 13th independent review HIGH 4 + MEDIUM 5 + LOW 3 全反映

> **Status**: ACTIVE
> **Date**: 2026-05-15  **Tokens used**: 66,261 (per_invocation_max=200K 内)
> **Codex output**: `codex-review.md` (1767 行、Verdict: ADOPT-WITH-CHANGES)

- **判断日時**: 2026-05-15 (本 session 後半、Codex 13th review 完了後)
- **背景**: User 直接指示「ベストを尽くせ」を受けて `/reimagine` + Codex 13th review を実施。Codex 13th (gpt-5.5 xhigh、66,261 tokens、Verdict ADOPT-WITH-CHANGES) で HIGH 4 / MEDIUM 5 / LOW 3 finding を切り出し。
- **選択肢**:
  - A: HIGH のみ反映、MEDIUM/LOW は持ち越し
  - B: HIGH + MEDIUM 全反映、LOW は持ち越し可
  - C: HIGH + MEDIUM + LOW 全反映 (User「ベストを尽くせ」直接指示)
- **採用**: C (HIGH + MEDIUM + LOW 全反映)
- **反映内容**:
  - **HIGH-1 (A12 unrealistic)**: design-final.md §C.7 A12 を A12a/A12b/A12c に split — M-L2-1 のみ active (status='valid' ≥90%)、M-L2-2 は M10-C schema 待ちで `status='unsupported'` 100% pin、M-L2-3 は M11-C perturbation 実走待ちで `status='unsupported'` 100% pin
  - **HIGH-2 (M-L2-3 baseline structurally wrong)**: design-final.md §C.2 M-L2-3 effect direction を修正 — `baseline_noindividual` (NC-3) を degenerate に、within-individual non-perturbation baseline + random-citation positive control との対比に変更、p<0.05 after FDR correction
  - **HIGH-3 (N=15,120 tick autocorrelation)**: design-final.md §C.2 M-L2-1/2/3 aggregation を block/cluster bootstrap に変更、autocorrelation 補正後の effective N report を A13 acceptance に追加、§C.6 thresholds protocol も block/cluster bootstrap 必須化
  - **HIGH-4 (Layer 2 ≠ sufficient statistic for Social-ToM)**: design-final.md §0 に claim boundary 警告 section を新設、§C.2 M-L2-1/2/3 各々に "Claim boundary" 行を追加、A16 acceptance で claim boundary 明示 3 箇所以上を必須化
  - **MEDIUM-1 (ADR-PM-2 supersede)**: ADR-PM-2 を `[SUPERSEDED by ADR-PM-6]` status に変更、ADR-PM-6 で `Supersedes: ADR-PM-2` 明示、historical rationale 保持
  - **MEDIUM-2 (WP11 handoff metadata)**: design-final.md §C.8 WP11 に handoff metadata block 追加 (freshness_date / protocol_version / dependencies / rereview_gate / expected_inputs / failure_modes)、A14 acceptance で metadata 含有を必須化
  - **MEDIUM-3 (M-L2-1 effect direction = none)**: design-final.md §C.6 で M-L2-1 を "descriptive only" に変更、pass/fail gate 不参入を明示
  - **MEDIUM-4 (dotted namespace allowlist test)**: design-final.md §C.4 末尾に allowlist test code template 追加、A15 acceptance で namespace allowlist test 必須化
  - **MEDIUM-5 (deprecation headers)**: design-original.md / design-reimagine.md の header に `HISTORICAL / SUPERSEDED` marker + 関連 ADR linkback 追加
  - **LOW-1 (絶対日付)**: design-final.md / decisions.md / ADR header に `Date: 2026-05-15 / Base commit: fb651e7` 追加
  - **LOW-2 (same-day ADR)**: 本 ADR-PM-7 で operationally reviewable と Codex Q11 で判定済、splitting せず同日 7 ADR を Status / Supersedes で管理
  - **LOW-3 (用語統一)**: design-final.md 全文で `Cite-Belief Discipline` (Layer 名) / `cite_belief_discipline.*` (namespace prefix) を統一 (grep 検証可能)
- **Codex Q12 stress-test 反映** (能動的 failure mode 列挙):
  - **Failure mode 1 (proxy drift)**: "Layer 2 が active なので ToM 測ったと誤読される risk" → §0 claim boundary 警告 + 各 metric の "Claim boundary" 行で防御
  - **Failure mode 2 (autocorrelation)**: "many ticks ≠ independent observations" → HIGH-3 反映で block/cluster bootstrap 必須化
  - **Failure mode 3 (schema dependency)**: "M-L2-2/M-L2-3 が M10-C citation fields に quietly 依存" → HIGH-1 反映で `status='unsupported'` pin、A12b/A12c で behavior pin test 必須化
- **トレードオフ**:
  - M10-0 で active 計測される Layer 2 metric は **M-L2-1 のみ** (3 → 1 に縮小)、M-L2-2/M-L2-3 は M10-C / M11-C 完了後 active
  - acceptance count が A1-A11 → A1-A16 (5 件増)、test count 想定が +5 (allowlist test + behavior pin tests)
  - WP11 spec doc が ~200 → ~250 行 markdown (handoff metadata 追加)
  - design-final.md の section header に `Date / Base commit` の重複が増えるが、reviewability 優先
- **影響範囲**: design-final.md (§0 / §C.2 / §C.4 / §C.6 / §C.7 / §C.8 全更新)、design-original.md (deprecation header)、design-reimagine.md (deprecation header)、decisions.md (ADR-PM-2 status / ADR-PM-6 header / 本 ADR-PM-7)
- **見直しタイミング**:
  - M10-C `cited_memory_ids` schema 確定時 → A12b の `status='unsupported'` pin を解除して M-L2-2 active 化
  - M11-C perturbation 実走着手時 → A12c pin 解除、M-L2-3 active 化、§C.6 P-CCRR protocol calibrate
  - empirical evidence で claim boundary 警告が proxy drift を防げていないと判明した場合 (M11 review で別 contributor が Layer 2 を ToM と誤解した等)、§0 警告を強化または design-final.md 自体を再起草

# 重要な設計判断 — m9-c-adopt Phase 2 (Plan B) design + driver

> 本 file は本 PR 内の session-local decisions を記録する。
> 横断的 ADR (DA-1 ~ DA-15) は `.steering/20260513-m9-c-adopt/decisions.md`
> を参照 (DA-16 候補は Plan B 結果次第で別 ADR PR で起票)。

## DI-1: V1 / V2 / hybrid 採用判定 (`/reimagine` を Task tool subagent 経由)

- **判断日時**: 2026-05-17
- **背景**: 本タスクは新規 driver 設計 + 新規 training 採用判断 +
  achieved corpus gate の 3 軸で多案ありうる設計。`.claude/commands/
  reimagine.md` Step 3 「自分に "見なかったことにする" と宣言する」は
  同一 context 内で V1 anchor leak が起きるため (DA-15 ADR DI-2 既知
  問題)、V2 を Task tool subagent (Plan mode) で independent 生成。
- **採用 process**:
  1. V1: primary agent が `.steering/20260517-m9-c-adopt-plan-b-design/
     design-v1.md` を生成
  2. V2: Task tool Plan subagent が V1 を読まずに独立生成、結果を
     `design-v2.md` に materialise
  3. V1 / V2 を比較、hybrid を `design.md` に確定 (本 PR の SSOT)
- **V2 が見抜いた重要 finding** (V1 が見落としていた / 弱かった):
  - **monolog-as-stimulus-response vs system-prompt self-reflection
    の選択軸** (V2 §1.4): self-reflection は persona の referent が
    自分自身に偏り、Burrows function-word axis を artefact で歪める。
    stimulus-response 形は argument 内容に向くので Critique 風
    transcendental argumentation に自然 (LISA stylometry "content-
    bleached style channel" 仮説と整合)
  - **de-alone ≥ 0.30 hard gate** の minority opinion (V2 §8): Plan A
    の per-language signal は de で最強 (-0.72 MPNet)、en free-rider
    防止のため de+en ≥ 0.60 と de ≥ 0.30 の **2 axis に分離**。
    Codex MEDIUM-1 違反ではない (DI-5 数値を retroactive 移動せず、
    新規 axis を Plan B で起こす)
  - **3-of-4 encoder panel with majority direction discipline** (V2
    §5.3): BGE-M3 sign flip 教訓を generalise、retrieval encoder の
    disagreement を ADOPT 不寄与化
  - **max_steps=2500 + EarlyStoppingCallback patience=2 min_delta=0.005**
    (V2 §3): v2 の eval_loss 0.166→0.180 envelope に empirically tied
  - **新規 stimulus battery を作らず既存 kant.yaml subset で済ます**
    (V2 §1.2): V1 は `kant_de_focused.yaml` を新規追加していたが、
    corpus capital を絞る V2 の判断のほうが本 ADR の "Plan B shape
    guide" 性質に合致
- **V1 が貢献した点**:
  - G-GEAR runbook の structure (Phase B 判断 8 の Windows native +
    PYTHONUTF8=1 経路の明文化)
  - 既存 patterns との整合性 mapping (DA-11 manifest convention 等)
- **hybrid 採用 (design.md)**:
  - V2 substance を base に採用 (§1.1 / §2 / §3 / §4 / §5)
  - V1 の G-GEAR runbook structure を §1.7 に統合
  - **MODIFY V2**: `vendi_lexical_5gram.py` 実装は本 PR scope 外
    (next-session retrain prep で実装)。本 PR は D-2 allowlist に
    module path を pre-register のみ。理由: retrain 実行前に verdict
    計算は走らないため blocker にならず、本 PR scope tightening
    (design + driver + 採取準備) を維持
- **トレードオフ**:
  - V2 採用で V1 の新規 stimulus battery は捨てた (corpus capital 節約)
  - V2 の max_steps=2500 は v2 baseline (4000) より短い、early stopping
    で 1500-2500 steps 想定。step 2500 で converge 不足の risk は
    patience=2 で吸収 (val loss 上昇前に止めれば best checkpoint emit
    済)
- **影響範囲**: 本 PR の design.md は hybrid 採用版、V1/V2 は historical
  record として retain。次セッション handoff は hybrid に従う。

## DI-2: monolog-as-stimulus-response vs system-prompt self-reflection

- **判断日時**: 2026-05-17
- **背景**: de-monolog 採取の 2 軸選択肢。V2 §1.4 で stimulus-response
  形を採用、self-reflection 形を棄却。
- **採用**: stimulus-response (persona prompt + de stimulus subset から
  driver が monolog を emit)
- **理由**:
  1. self-reflection は referent が persona 自体に偏り (Critique-meta-
     talk artefact)、Burrows function-word axis を artificial に押し上げる
  2. Critique 系統の Kant style は「読者に向けて講じる monolog」であって
     「自己内省」ではないので persona fit でない
  3. stimulus-response 形は LISA stylometry の "content-bleached
     content-independent style channel" 仮説と整合 (Codex HIGH-2 反映)
- **棄却**:
  - system-prompt self-reflection (上記 1-2)
  - 新規 de-only stimulus battery 作成 (V1 案、corpus capital 過剰、
    V2 の既存 kant.yaml subset で十分)
- **影響範囲**: `de_focused_monolog_collector.py` の system prompt 設計、
  stimulus loading 方針。

## DI-3: Plan B achieved corpus stats gate に de-alone ≥ 0.30 を追加 (V2 minority opinion)

- **判断日時**: 2026-05-17
- **背景**: Plan A 結果は per-language で de が最強 signal source
  (d_de=-0.72 MPNet)。de+en mass ≥ 0.60 だけだと en が free-rider に
  なって de signal が出ないリスクがある。
- **選択肢**:
  - A: de+en ≥ 0.60 のみ hard gate (V1 案)
  - B: de+en ≥ 0.60 + de ≥ 0.30 の 2 axis hard gate (V2 minority opinion)
  - C: de ≥ 0.30 のみ hard gate (en を放棄)
- **採用**: B (V2 minority opinion)
- **理由**:
  1. Plan A non-gating observation で de が最強 signal の事実
  2. en は 2 番手 (-0.58) なので落とせない (B が C より strict)
  3. Codex MEDIUM-1 違反ではない: DI-5 の de+en 数値 (0.489) を
     retroactive 移動するのではなく、**新規 axis を Plan B で起こす**。
     "Plan B 起動後の corpus shape expectation を hard gate にする"
     ことは MEDIUM-1 が禁じる "retroactive trigger promotion" と
     カテゴリが違う
- **トレードオフ**:
  - 採取側 driver の負荷増 (de bias を強くする必要、prompt tuning が
    必要)。だが R-1 の dry-run pre-test で事前測定すれば mitigation 可
- **影響範囲**: `audit_plan_b_corpus_stats.py` の 4 axis gate、driver
  の persona prompt augmentation、`d2-encoder-allowlist-plan-b.json` の
  preregistration note。

## DI-4: D-2 allowlist で MPNet primary 復帰、BGE-M3 exploratory 格下げ、lexical-5gram 追加

- **判断日時**: 2026-05-17
- **背景**: Plan A allowlist では MPNet=regression、BGE-M3=primary
  だったが、Plan A 結果で BGE-M3 が natural d sign flip (+0.23) を
  起こし、MPNet が per-language で最強 (-0.72) だった。
- **採用**: V2 §5 の 4-encoder panel
  - primary: MPNet (de 軸最強)、E5-large (en 軸検出器)、lexical-5gram
    (retrieval-trained でない independent)
  - exploratory: BGE-M3 (Plan A sign flip 報告 obligatory、ADOPT 不寄与)
- **理由**:
  1. Plan A 経験的事実 (per-encoder within-language d) に基づく role
     再割当て
  2. encoder agreement axis (3 primary の 2 以上が同方向で gate clear)
     で 1 encoder の retrieval artefact が ADOPT 判定を腐らせない
  3. lexical-5gram は Burrows-adjacent shallow stylometry、retrieval-
     trained でない independent kernel を追加することで encoder
     diversity を確保
- **トレードオフ**:
  - `vendi_lexical_5gram.py` 実装が必要 (~50 LOC)。本 PR scope を絞る
    ため **次セッション (retrain prep) に scope**。本 PR は allowlist
    に module path を pre-register のみ。
- **影響範囲**: `d2-encoder-allowlist-plan-b.json`、次セッションでの
  `vendi_lexical_5gram.py` 実装 + 既存 `vendi.py:_load_default_kernel`
  への kernel 引数追加。

## DI-5: dataset.py 拡張は train_kant_lora.py 内で実施 (function 本体の所在)

- **判断日時**: 2026-05-17
- **背景**: next-session prompt は "dataset.py 拡張" を要求するが、
  実際の `_group_aware_stratified_split` 本体は
  `src/erre_sandbox/training/train_kant_lora.py` に集約されている
  (line 785-836)。
- **採用**: 本 PR では `train_kant_lora.py` に `stratify_by_language`
  kw-only flag を追加。`dataset.py` 自体は変更しない。
- **理由**:
  1. function 本体が train_kant_lora.py にあるので、そこを拡張する
     のが minimum diff (引数 1 つ + 内部 stratum key 変更)
  2. dataset.py の `build_weighted_examples` は per-row metadata extract
     を担当、split は train_kant_lora の責務、責務分離を保つ
  3. next-session prompt の "dataset.py 拡張" 表記は naming に過ぎず、
     実装場所を約束する物ではない
- **トレードオフ**: 表記と実装場所が乖離する見かけの差。decisions.md
  本判断で明文化することで future reader が混乱しない。
- **影響範囲**: `train_kant_lora.py` の `_group_aware_stratified_split`、
  CLI flag `--lang-stratified-split`、test は
  `tests/test_training/test_dataset_lang_stratified.py` の naming で
  test_dataset 系列に配置 (next-session prompt の naming を honour)。

## DI-6: lexical-5gram 実装は本 PR scope 外 (next-session retrain prep)

- **判断日時**: 2026-05-17
- **背景**: V2 §6 は `vendi_lexical_5gram.py` を本 PR に含めていた。
- **採用**: 本 PR は **D-2 allowlist に module path を pre-register
  のみ**。実装 + unit test は次セッション (retrain prep) で行う。
- **理由**:
  1. retrain 実行前に verdict 計算は走らないため、本 PR で実装しても
     blocker にならない
  2. 本 PR scope tightening (design + driver + 採取準備) を維持、
     ~7-8h envelope を守る
  3. `vendi.py:_load_default_kernel` の encoder 引数化は Plan A PR
     #179 で済んでいるが、新 kernel タイプ ("lexical") を追加するには
     `_load_default_kernel` の wrapper 拡張が必要。これも次セッション
     scope に統合 (`vendi_lexical_5gram.py` + `vendi.py` の lexical
     kernel dispatch を同時に行う)
- **トレードオフ**:
  - 次セッションが 2 task (lexical-5gram 実装 + retrain) になる。
    lexical-5gram は ~30min、retrain は ~20h overnight なので overhead
    minimal
- **影響範囲**: 次セッション handoff prompt に lexical-5gram 実装を
  最初の task として明示。

## DI-8: Codex independent review (gpt-5.5 xhigh) verdict ADOPT-WITH-CHANGES、5 件全反映

- **判断日時**: 2026-05-17 (`codex-review.md` verbatim 受領後、本セッション内
  で全 HIGH/MEDIUM/LOW 反映)
- **背景**: `.steering/20260517-m9-c-adopt-plan-b-design/codex-review.md`
  (gpt-5.5 xhigh) が以下 5 件を指摘:
  - **HIGH-1**: Plan B retrain command が executable でない。
    `train_kant_lora.py` の CLI は `--plan-b-gate` / `--lang-stratified-split`
    / `--eval-steps` を露出しておらず、`_handle_weighted_path` も
    `stratify_by_language` を渡していない、`EarlyStoppingCallback` も attach
    されていない。次セッションの retrain が argparse で failing
  - **HIGH-2**: `audit_plan_b_corpus_stats.py` の CLI が `--n-eff-min` 等
    threshold override flag を露出。preregistered hard gate が運用上の
    flag で動かせるのは HIGH-3 discipline (threshold motion 禁止) に違反
  - **MEDIUM-1**: 採取 manifest が documented but not emitted。runbook §7 で
    manifest schema を定義済だが、collector に書き出しコードがない
  - **MEDIUM-2**: "no addressee" が metadata only で output-filtered でない。
    `filter_de_monolog` は language / length / marker / trigram のみ強制、
    "du / Sie / Ihre / Frage" などの addressee marker が accepted text に
    残ったまま `addressee=None` で挿入される (weighting path が "addressed
    text を no-addressee として boost" してしまう)
  - **LOW-1**: `--dry-run` の resume contract 違反。CLI help と runbook は
    "smoke dry-run は state を preserve しない" と言うが、`run_collection()`
    は always read + flush している
- **反映** (本 PR scope 内で全件):
  1. **HIGH-1**:
     - `_build_arg_parser` に `--plan-b-gate` / `--lang-stratified-split` /
       `--eval-steps` を追加
     - `train_kant_lora` シグネチャに `eval_steps` / `plan_b_gate` /
       `lang_stratified_split` を追加
     - `_run_weighted_path` で `stratify_by_language=lang_stratified_split`
       を `_collect_from_shards_weighted` に forward
     - `_pre_training_audit` 直後に
       `erre_sandbox.training.plan_b_gate.audit_corpus` を呼び、4-axis
       gate fail で `PlanBCorpusGateError` raise (exit 8)
     - `plan-b-corpus-gate.json` を `output_dir_path` に必ず emit
       (forensic)
     - `_run_trainer_weighted` に `plan_b_gate` を threading、True 時に
       `EarlyStoppingCallback(early_stopping_patience=2,
       early_stopping_threshold=0.005)` を attach、
       `metric_for_best_model="eval_loss"` + `greater_is_better=False` +
       `load_best_model_at_end=True` を TrainingArguments に追加
     - `eval_steps` で eval cadence を上書き可能 (Plan B では 250 推奨)
     - main() の exit code mapping に 8 = `PlanBCorpusGateError` を追加
     - `PlanBCorpusGateError` を `exceptions.py` に新規追加
  2. **HIGH-2**:
     - `scripts/m9-c-adopt/audit_plan_b_corpus_stats.py` を thin CLI wrapper
       に rewrite。threshold override CLI flags (`--n-eff-min` 等) を **削除**
     - gate logic を `src/erre_sandbox/training/plan_b_gate.py` の
       `audit_corpus` に promote (production の single source of truth)。
       Threshold kwargs は pure function に残るが、CLI / `--plan-b-gate`
       path のどちらも production constants をハードコード bind
  3. **MEDIUM-1**: `de_focused_monolog_collector._write_manifest` を新規追加、
     collection 完了時に必ず `<shard>_manifest.json` を emit。schema は
     runbook §7 通り (merge SHA / sampling params / filter thresholds /
     stimulus subset ids / acceptance rate)。merge SHA は環境変数
     `PLAN_B_MERGE_SHA` 経由 (runbook で operator が export する)
  4. **MEDIUM-2**: `filter_de_monolog` に **5 軸目** "addressee" を追加。
     informal 2nd-person (du / dich / dir / dein- / euch / euer / fragst)
     は case-insensitive で match、formal (Sie / Ihnen / Ihr-) は
     **case-sensitive** で match (lowercase "sie" / "ihr" は 3rd-person
     pronoun として monolog で頻出するので除外)。`FilterResult` に
     `has_addressee` field を追加。`tests/test_de_focused_monolog_
     collector.py` に 3 test 追加 (du / formal Sie / 3rd-person ihrer の
     misfire 回避)
  5. **LOW-1**: `run_collection` で `args.dry_run=True` 時は
     `_read_resume_state` を skip し、`pilot_state` を冒頭で wipe
     (acceptance rate 測定が決定的に)
- **棄却**: なし (全 5 件 adopt)
- **影響範囲**:
  - `train_kant_lora.py` CLI が runbook の retrain command と一致
  - 既存 K-β / v2 baseline path は `--plan-b-gate` 未指定で動作不変
    (test_train_kant_lora_cli の既存 13 test 全 pass)
  - 新 test 15 件 (collector / 7 件 lang-stratified / 10 件 audit) 全 pass、
    既存 training suite 45 件全 pass、pilot smoke 13 件全 pass = **83 件
    regression pass**

## DI-7: `--plan-b-gate` CLI flag を default off (regression safety)

- **判断日時**: 2026-05-17
- **背景**: Plan B の hard gate 昇格 (de+en ≥ 0.60 + de ≥ 0.30) を
  既存 K-β / v2 baseline path に適用すると、historical training run
  (5022 examples、de+en=0.489) が abort することになる。
- **採用**: `--plan-b-gate` CLI flag を default False、未指定の path は
  動作不変 (既存 N_eff / top_5 soft + hard gate のみ)。
- **理由**:
  1. 既存 v2 retrain artefact (PR #168) が re-train 不能になる risk を
     回避
  2. Plan B 起動は **本 PR merge 後の retrain session でのみ** trigger、
     回帰 test の golden test を破壊しない
- **トレードオフ**:
  - CLI flag が増えるが、`--plan-b-gate` の意味は self-documenting
- **影響範囲**: `train_kant_lora.py` の argparse、test
  `test_train_kant_lora_cli.py` 既存 case 不変、新規 plan-b-gate test
  を追加。

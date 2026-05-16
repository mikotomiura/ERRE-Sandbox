# 重要な設計判断 — m9-c-adopt DA-15 ADR (retrain v2 REJECT escalation)

> 本 file は本 PR 内の session-local decisions を記録する。
> 横断的 ADR (DA-1 ~ DA-15) は `.steering/20260513-m9-c-adopt/decisions.md` に
> 追記する (immutable append convention)。本 PR 内では **DA-15** を append する。

## DI-1: Step 0 Plan B feasibility scan 結果

- **判断日時**: 2026-05-16
- **背景**: Plan agent validation で「Plan B compute 見積もり (~19h) は driver
  存在性で 1 桁変わる」と指摘された。ADR 起草前に既存 `scripts/m9-c-adopt/`
  と `src/erre_sandbox/training/` の関連 file を Glob/Grep で確認する必要が
  あった。
- **scan 結果**:
  - `scripts/m9-c-adopt/` 配下: `compute_baseline_vendi.py`, `compute_burrows_
    delta.py`, `compute_big5_icc.py`, `da1_matrix.py`, `da1_matrix_multiturn.py`,
    `tier_b_pilot.py`, `validate_multiturn_shards.py` の 7 file。
    **de-focused monolog generator は存在しない**。
  - `src/erre_sandbox/training/dataset.py` の monolog re-cast は natural shard
    の Kant 2-turn pair を language 無差別で抽出 (DI-3 cap=500)。`where
    language == "de"` filter は存在しない。
  - `src/erre_sandbox/training/weighting.py` には language constant
    (de=1.4, en=1.0, mixed=0.5, ja=0.2) はあるが filter / subset 抽出
    function は無し。
  - existing 5022 examples 中 de=15.9% (≈800 raw)、その中の連続 2-turn Kant
    pair は推定 ~5-7% (≈40-60 examples)。**B-1 単独で 250+ examples 集まらない
    可能性大**。
- **判定**: Plan B は事実上 **B-2 (新規 collector) が必須**。コード変更面積:
  driver 新規 (~1.5h) + dataset.py 拡張 (~50 LOC)。compute envelope は
  driver 1.5h + G-GEAR 採取 3h + retrain 20h + recapture/consumers 1.5h
  ≈ **~25h** (V2 draft の見積もりと一致)。
- **ADR D-15 への影響**: Plan B compute 列を "~25h (driver 新規 1.5h + 採取
  3h + retrain 20h + recapture/consumers 1.5h)" と verified 値で記入。
  Plan B 並列 pre-staging (H-α) の driver 1.5h dead-time 利用合理性を支える。

## DI-2: /reimagine V2 を Task tool subagent dispatch で生成

- **判断日時**: 2026-05-16
- **背景**: `.claude/commands/reimagine.md` の Step 3 は「自分に "見なかった
  ことにする" と宣言する」だが、Plan agent validation で「同一エージェントの
  同一会話 context 内では V1 anchor が leak する (`empirical-prompt-tuning`
  Skill の Red flags 表で否定されている)」と指摘された。
- **選択肢**:
  - A: Skill 記載通り main agent 内で自己 discard
  - B: Task tool で Plan subagent を起動、V1 を hide した状態で independent
       generation
  - C: Skill 自体を改訂 (default を subagent dispatch にする) してから運用
- **採用**: **B** (本 PR は ADR のみで Skill 改訂は scope 外、ただし
  blockers.md に Skill 改訂提案を 教訓として記録)
- **実施結果**: V2 subagent は V1 を読まずに独立生成し、以下を V1 が見落と
  していた重要 finding として発見:
  - DA-14 spec の `ai_decision_protocol.vendi_fail_but_others_pass =
    ESCALATE_DA15_vendi_kernel_swap` が Plan A を **pre-authorise** している
    (HIGH-3 grey-zone を大幅に縮小)
  - `vendi.py:294-322` の `_load_default_kernel` が MPNet を hardcode (Plan A
    の code change scope を pin)
  - Plan A 単独で kant 2-of-3 quorum 充足可能 (Vendi-swapped + ICC = 2)
- **トレードオフ**: subagent dispatch の compute cost (~5-10min 追加) と
  Skill 上書きの inconsistency。前者は許容範囲、後者は blockers.md 教訓記録で
  ヘッジ。
- **影響範囲**: 本 ADR で Plan A → Plan B sequential を強い evidence で確定
  できた (V2 finding を core 採用)。今後の高難度 ADR でも同 pattern 推奨。

## D-1: DA-15 採用案 = Plan A → Plan B sequential + Hybrid H-α pre-staging

- **判断日時**: 2026-05-16 (Codex review 反映後に最終確定)
- **背景**: DA-14 verdict REJECT (kant 1-of-3 primary、2-of-3 quorum 未達、
  Vendi d=-0.18 / Burrows +0.43% / ICC PASS / throughput PASS) を受け、
  3 plan (A: Vendi kernel swap / B: Candidate C targeted hybrid / C: Longer
  training / rank拡大) の trade-off で escalation path を決定する必要があった。
- **選択肢** (V1 / V2 / Codex review 統合):
  - **Plan A 単独** (kernel swap のみ、Plan B はやらない)
  - **Plan A → Plan B sequential** (cheapest first、Plan A 失敗時のみ B)
  - **Plan A → Plan B sequential + Hybrid H-α** (Plan A 走行中に B driver
    pre-stage、Plan A 失敗時の startup 時間短縮)
  - **Plan B 単独** (Plan A skip)
  - **Plan C single** (longer / rank 拡大)
- **採用**: **Plan A → Plan B sequential + Hybrid H-α pre-staging、Plan C は
  Phase E A-6 へ migrate**
- **理由**:
  1. Cheapest-first 経済合理性: Plan A は 1-2h (compute) + 2-3h (code
     parameterisation)、Plan B は ~25h、Plan C は 20-32h+。
  2. DA-14 pre-authorisation: `ai_decision_protocol.vendi_fail_but_others_pass
     = ESCALATE_DA15_vendi_kernel_swap` で Plan A は HIGH-3 clean pathway。
  3. eval_loss step 2000=0.166 → final=0.180 の mild overfit が Plan C-
     longer-training を contraindicate。
  4. ICC PASS + Vendi/Burrows FAIL の組み合わせは「persona shift は実在する
     が MPNet が見えていない」という measurement-side bottleneck 仮説と整合。
  5. H-α (Plan A 走行中の Plan B driver pre-staging) は Plan A 失敗時の
     startup 時間を 1.5h 短縮。Plan A 成功時は pre-stage code を別 PR で保留
     (corpus capital として将来再利用可)。
- **トレードオフ**:
  - Plan A 単独で kant 2-of-3 quorum 充足可能 (Vendi-swapped + ICC = 2) の
    場合、Burrows の +0.43% (5% target 未達) は per-persona limitation として
    documented limitation で済む。Burrows axis に拘ると Plan B 起動 → +25h で
    結局 +1-4pp しか改善見込みがなく、5% pass は保証されない。documented
    limitation で済ませる経路を ADR D-15 で明示。
  - Hybrid H-α の Plan B driver pre-stage は Plan A 成功時に waste。ただし
    driver code は将来 Phase E A-6 で再利用可能なので sunk cost 小。
- **影響範囲**:
  - 本 ADR PR merge 後、Phase 1 (Plan A) を `.steering/20260516-m9-c-adopt-
    da15-impl/` で `/start-task` 起票。
  - `vendi.py` / `compute_baseline_vendi.py` の encoder parameterisation
    (~50 LOC + tests) が必要。
  - 既存 v2 multi-turn pilot 出力 (`.steering/20260515-m9-c-adopt-retrain-v2-
    verdict/matrix-inputs/`) を rescore 入力として再利用。
  - Phase 1 失敗時のみ Phase 2 (Plan B-2 driver + retrain) を別 PR で起票。
- **見直しタイミング**:
  - Plan A 結果が Vendi d > -0.5 で multilingual encoder 全 candidate fail
    → Plan B-2 起動 (本 ADR 通り)
  - Plan A + Plan B 両方が DA-14 fail → kant について Phase E A-6 で rank=16
    + B+C hybrid を再評価 (本 ADR scope 外、新 ADR DA-16 起票候補)

## D-2: Codex review HIGH/MEDIUM/LOW 指摘の反映

- **判断日時**: 2026-05-16
- **背景**: Codex independent review (`codex-review.md`、gpt-5.5 xhigh、
  Verdict = **ADOPT-WITH-CHANGES**) の指摘 6 件をすべて反映する。

### HIGH-1: Vendi metric の operational redefinition risk

- **Codex 指摘**: numerals は不変だが "Vendi d ≤ -0.5 under at least 2
  candidate kernels" は DA-14 の MPNet-pinned `vendi_semantic` 計器と別物。
  DA-14 が pre-authorise したのは `vendi_fail_but_others_pass` で、現状は
  Vendi + Burrows 双方 fail。HIGH-3 threshold movement in disguise の risk。
- **採用 fix**:
  1. **DA-15 で新 metric を versioned 起こす**: `vendi_semantic_v2_encoder_
     swap` という名前で、point/CI thresholds は DA-14 と同一値 (d ≤ -0.5、
     CI upper < 0) を引き継ぐ。
  2. **MPNet Vendi は常に REJECT として併報告**: DA-14 instrument の
     historical record を保持し、DA-15 verdict は新 metric での独立評価。
     "DA-14 fail のままで DA-15 pass" を明示。
  3. **primary gating encoders の pre-registration**: encoder name + HF
     revision SHA + transformer version pin を `.steering/20260516-m9-c-
     adopt-da15-impl/decisions.md` D-2 に **rescore 実施前に** 確定。
  4. **exploratory encoders は ADOPT に寄与不可**: philosophy-domain BERT
     は exploratory のみ、kant ADOPT 判定の primary には含めない。
- **ADR D-15 への反映**: 新 metric 名 + pre-registration mandate +
  併報告 mandate を明記 (DA-15 append 内)。
- **design.md への反映**: Phase 1 implementation の handoff sketch に
  「encoder + revision pin pre-registration を Phase 1 開始時の最初の commit
  で行う」を追記。

### HIGH-2: Cross-arm blind spot — retrieval encoders are not style validation

- **Codex 指摘**: V1/V2 両方が multilingual-e5 / bge-m3 を persona-style
  discriminator として想定したが、これらは **retrieval-trained** であり
  stylometry / persona-style discriminator ではない (E5 arxiv.org/abs/
  2402.05672, BGE-M3 arxiv.org/abs/2402.03216, LISA arxiv.org/abs/2305.12696
  参照)。両 Claude arm 共通の盲点。Plan A pass は language/length artefact
  を反映する可能性。
- **採用 fix**: **Plan A eligibility gate** を導入:
  1. **language-balanced bootstrap**: de/en/ja 内で independent に
     resampling、language ID effect を打ち消した上で d を計算
  2. **token-length-balanced bootstrap**: 各 length quartile 内で
     independent resampling
  3. **within-language d reporting**: 全体 d だけでなく per-language d
     (d_de, d_en, d_ja) を併報告
  4. **preregistered calibration panel**: Plan A 開始前に、各 candidate
     encoder が **language ID ヒントなしで Kant-style vs control text を
     分離できる**ことを示す calibration test を実施。
     - test corpus: Kant の Critique 邦訳 + control philosopher (Heidegger
       邦訳 + 英訳) で各 100 文を用意。calibration AUC ≥ 0.75 を pass 基準
       (preregistered)
     - calibration fail の encoder は Plan A primary gate から除外
  5. **balancing 後に effect が消える encoder は Plan A FAIL**: balanced
     condition で d > -0.5 になった encoder は ADOPT 寄与不可
- **ADR D-15 への反映**: eligibility gate を Plan A spec の必須条件として明記。
- **design.md への反映**: Phase 1 implementation tasklist に calibration panel
  実装を必須項目として追記。

### MEDIUM-1: Plan B trigger semantics

- **Codex 指摘**: `de+en=0.489 < 0.60` は **soft warning** であって DA-14
  audit failure ではない。Plan B 起動 rationale を「DA-14 REJECT + Candidate
  C fallback spec」に固定し、DI-5 を retroactive に hard trigger 化しない。
- **採用**: DI-5 de+en mass は **soft warning のまま固定**。Plan B 起動は
  「DA-14 verdict REJECT + Candidate C spec が pre-authorise する fallback」
  を rationale として ADR に明記。de+en miss は **targeted-hybrid の shape
  を guide する** 役割で limit。

### MEDIUM-2: Effect-size estimates are under-supported

- **Codex 指摘**: Plan A/B/C の predicted d ranges (Plan A -0.3 to -1.2、
  Plan B -0.3 to -0.8、Plan C rank=16 -0.3 to -0.8) は priors であって
  literature-grounded ではない。LoRA/QLoRA literature (arxiv.org/abs/
  2106.09685, arxiv.org/abs/2305.14314) は parameter efficiency を支持する
  が、5k weighted-CE setup での rank=16 persona-style effect の specific
  prediction ではない。
- **採用**: 全 predicted d ranges を **"non-gating directional priors"** と
  reword。
  - Plan B: 採用判定は achieved corpus stats (de+en mass post-retrain) +
    empirical DA-14 rerun verdict のみで行う。predicted d は guidance
    only。
  - Plan C: Phase E A-6 で dry-run evidence (rank=16 で 1000-step subset
    の eval_loss trajectory) を取った上で正式起票する。

### MEDIUM-3: Hybrid H-α isolation mandate

- **Codex 指摘**: Plan A 走行中の Plan B driver pre-staging は、Plan A の
  scope / criteria / PR contents を contaminate しない場合のみ genuine
  parallelism。
- **採用**: H-α の isolation guardrails を mandate:
  1. **別 branch / worktree で作業** (`feature/m9-c-adopt-da15-plan-b-
     prep` or `git worktree`)、Plan A branch には commit しない
  2. Plan A の test suite / lint / CI には含めない
  3. Plan A verdict 書面 (decisions.md / DA-15 report) で reference しない
  4. Plan A pass 時は別 PR で merge せず保留 (将来 Phase E 再利用候補)
  5. Plan A fail 時は別 PR (Phase 2 = Plan B) を起票

### LOW-1: Burrows limitation 明文化

- **Codex 指摘**: Plan A pass で kant 2-of-3 (Vendi-swapped + ICC) で ADOPT
  となる場合、Burrows は依然 FAIL のままで、ドイツ語 function-word
  stylometry は改善されていない。"Burrows reduction remains FAIL; German
  function-word stylometry is not improved. Plan A ADOPT rests only on
  DA-15 Vendi semantics + ICC, and Burrows remains open for Plan B /
  reference-corpus work." を明文化。
- **採用**: kant ADOPT verdict (Plan A 成功時) の決定文書に Burrows axis
  fail の named limitation を必須記載。DA-15 append の re-open 条件に
  「Burrows axis 改善は Plan B または reference corpus work で別途追求」を
  明示。

### 全体方針

すべての HIGH/MEDIUM/LOW 指摘を採用 (defer なし)。理由:
- HIGH-1/2 は両方が HIGH-3 関連で reject 不可
- MEDIUM-1 は preregistration discipline の根幹
- MEDIUM-2/3 は ADR の portability を上げる cheap fix
- LOW-1 は future reader への overclaim 防止で価値高


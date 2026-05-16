# ブロッカー記録 — DA-15 ADR

> 本セッションは ADR のみで実装無し、よって従来的な「ブロッカー」は無い。
> このファイルは **HIGH-3 self-review checklist** と **本 ADR が defer した
> 項目** の双方を集約する。

## HIGH-3 self-review checklist (本 PR merge 前に必ず全 ✓)

DA-14 thresholds (`.steering/20260514-m9-c-adopt-retrain-v2-design/da1-
thresholds-recalibrated.json`) は **post-hoc movement 禁止** (HIGH-3)。本 ADR
は以下を保証する:

- [x] DA-14 numerical thresholds (Vendi d ≤ -0.5、Burrows reduction ≥ 5%、
      ICC(A,1) ≥ 0.55、CI 制約) は **literal 不変** (decisions.md / DA-15
      append 内で 1 度も再定義しない)
- [x] 各 Plan の "predicted effect size" は threshold との **比較**として書かれ
      ており、threshold 自体を再定義していない
- [x] "post-hoc" / "緩める" / "見直す" / "soften" / "relax" を threshold に
      適用する文言が無い
- [x] Plan A の Vendi kernel swap は DA-14 spec の
      `ai_decision_protocol.vendi_fail_but_others_pass = ESCALATE_DA15_vendi_
      kernel_swap` で **pre-authorised** されており、methodology shift と
      threshold movement の区別を明確化している
- [x] apples-to-apples: Plan A 実装時は v2 と no-LoRA baseline の両方を
      同 kernel で rescore することを ADR D-15 で **mandate** している
      (片方だけ rescore は HIGH-3 違反相当)
- [x] encoder candidate list + version pin + commit SHA は Plan A 実施前に
      `.steering/20260516-m9-c-adopt-da15-impl/decisions.md` で **pre-register**
      する手順を ADR D-15 で mandate している
- [x] kant 2-of-3 quorum (DA-14 `quorum_rule.kant`) の解釈は不変
      (Plan A 成功時の Vendi-swapped + ICC = 2-of-3 は quorum 仕様内、Burrows
      の per-persona limitation は documented limitation として記録)
- [x] Codex independent review (`codex-review.md`) で HIGH-3 違反検出を最優先
      項目として要求し、結果を ADR D-15 / decisions.md に反映済

> Note: V1 draft で記載した HIGH-3 self-review (4 項目) は本 checklist 8 項目
> に拡張統合した。V2 draft の HIGH-3 self-review table (7 行) も全項目を本
> checklist に inline 統合済。

## 本 ADR が defer した項目

### D-1: matrix script の comparator 修正

- **項目**: `scripts/m9-c-adopt/da1_matrix_multiturn.py` の comparator が
  MATCHED HISTORICAL Ollama baseline (DA-11 era logic) を使用しており、DA-14
  が mandate する no-LoRA SGLang baseline と一致しない (DA-13 / DI-1 でも
  flag 済)
- **defer 理由**: 本 ADR は ADR のみで実装 PR を含まない。matrix script の
  更新は DA-15 Phase 1 implementation PR (Plan A) と同梱推奨
- **持ち越し先**: `.steering/20260516-m9-c-adopt-da15-impl/` で Phase 1 開始時
  に同 PR 内タスクとして起票

### D-2: DA-15 trace.HEAD への merge SHA 埋め込み

- **項目**: 本 PR (DA-15 ADR) merge 後、その merge SHA を
  `.steering/20260513-m9-c-adopt/decisions.md` DA-15 の trace.HEAD に埋め込む
  (DA-14 convention 踏襲)
- **defer 理由**: 本 PR では merge SHA が未確定
- **持ち越し先**: 本 PR merge 後の別 chore PR (例:
  `chore(adopt): DA-15 trace.HEAD を ADR PR merge SHA で埋め込み`)

### D-3: nietzsche / rikyu の DA-15 escalation 適用

- **項目**: 本 ADR は **kant のみ** の DA-15 escalation を確定。nietzsche /
  rikyu は DA-12 で Phase E A-6 の multi-turn full Tier B 7500-turn 評価へ
  持ち越されており、本 ADR の Plan A → Plan B sequential を直接 apply する
  かは別判断
- **defer 理由**: kant の Plan A 結果を見てから他 persona への適用是非を
  判定するのが evidence-grounded
- **持ち越し先**: kant Plan A (or B) verdict 出た後の Phase E A-6 起票時

### D-4: Plan B-1 (cheap filter) vs B-2 (expensive collector) の選択確定

- **項目**: Step 0 feasibility scan で「de-focused monolog generator 未実装」
  「natural shard 2-turn de pair が 40-60 examples しかない」を確認。Plan B
  は事実上 B-2 (新規 collector) が必要だが、B-1 (既存 dataset.py の filter
  拡張) を組み合わせるか単独で済むかは Phase 1 失敗後の状況で判断
- **defer 理由**: 本 ADR は Plan B を起動する条件 (Phase 1 失敗時) のみ確定。
  実装詳細は別 PR
- **持ち越し先**: Phase 2 implementation 開始時の design.md

## Codex independent review (`codex-review.md`、Verdict: ADOPT-WITH-CHANGES)

### 全 6 指摘 (HIGH 2 / MEDIUM 3 / LOW 1) を **全採用、defer ゼロ**

- **[HIGH-1] Vendi metric operational redefinition risk**
  - 反映: `vendi_semantic_v2_encoder_swap` という新 versioned metric を起こす、
    MPNet Vendi は常に REJECT 併報告、encoder + revision pin pre-registration
    mandate (decisions.md D-2 / design.md Phase 1 / DA-15 append すべてに反映)
- **[HIGH-2] Cross-arm blind spot — retrieval encoders ≠ style validation**
  - 反映: Plan A eligibility gate (language-balanced bootstrap + token-
    length-balanced bootstrap + within-language d 併報告 + preregistered
    calibration panel with AUC ≥ 0.75 + balanced condition で消える encoder
    は ADOPT 寄与不可) を design.md / DA-15 append に追加。両 Claude arm 共通
    の盲点を Codex (gpt-5.5 系列) が指摘した点は今後の独立 review pattern
    validation として `blockers.md` 教訓に記録
- **[MEDIUM-1] DI-5 soft warning を hard trigger に retroactive 化しない**
  - 反映: Plan B 起動 rationale を「DA-14 REJECT + Candidate C spec」のみに
    固定。de+en miss は targeted-hybrid の shape を guide する役割
- **[MEDIUM-2] Predicted d range は non-gating directional priors と明記**
  - 反映: 全 plan の predicted d を guidance only と reword。Plan B = achieved
    corpus stats + DA-14 rerun が gate。Plan C = Phase E dry-run evidence 必須
- **[MEDIUM-3] Hybrid H-α isolation guardrails**
  - 反映: 別 branch/worktree、Plan A PR には commit/test/reference せず、
    Plan A pass 時は保留 (将来 Phase E 再利用)、fail 時のみ別 PR 起票
- **[LOW-1] kant ADOPT 時の Burrows limitation 明文化**
  - 反映: 決定文書 (verdict report) に "Burrows reduction remains FAIL"
    の named limitation を必須記載

### 教訓 (本 ADR セッションから)

- **両 Claude arm の cross-arm blind spot 発見**: V1 と V2 (Task subagent
  独立生成) は両方とも multilingual-e5 / bge-m3 を persona-style
  discriminator として無批判に採用した。これは Claude lineage に共通する
  literature gap (retrieval vs style の区別)。Codex (別モデル系列) が
  HIGH-2 で発見し ADR の核心 risk を救出した。**独立 review pattern
  (Claude V1 + Claude V2 subagent + Codex external) は機能している**。
  ただし「同系列 model 内では同じ盲点が増殖する」という構造的限界も実証。
- empirical-prompt-tuning Skill の「別モデル系列 / 人間レビュアーが必要」
  記述は本 ADR で empirical に裏付けられた。今後の高難度 ADR では Codex
  review を skip しない。

## 教訓

- /reimagine の V2 生成は同一会話 context 内では bias leak する。Task tool
  subagent dispatch で V1 隠蔽 + 独立 input のみで生成する pattern が、本 ADR
  で V2 のみが DA-14 spec の `ai_decision_protocol.vendi_fail_but_others_pass`
  を発見・引用する効果を生んだ。**今後の `/reimagine` は default で subagent
  dispatch を採用すべき** (`.claude/commands/reimagine.md` の Step 3 改訂候補)
- 高難度 ADR で Codex review を起動する時、prompt の最初に検出最優先項目
  (本 ADR では HIGH-3 違反) を明記すると Codex の reasoning が引き締まる

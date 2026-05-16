# 設計 sketch — DA-15 採用案 (Plan A → Plan B sequential + Hybrid H-α)

> **status**: ADR 採用案の **implementation sketch**。詳細 spec は次セッション
> (`.steering/20260516-m9-c-adopt-da15-impl/design.md`) で確定する。本 file は
> handoff 用の scope narrowing + 主要 file pointer に専念する。

## 実装アプローチ

### Phase 1: Plan A (Vendi kernel swap、~1-2h scoring + ~2-3h code + ~1h calibration、本 PR の対象外)

`vendi.py:_load_default_kernel` を引数化し、複数の multilingual / domain
encoder で同一 generation 出力を再 score する。**新規 training なし、新規
data 採取なし**。DA-14
`ai_decision_protocol.vendi_fail_but_others_pass = ESCALATE_DA15_vendi_kernel_swap`
が methodology shift を pre-authorise しているが、Codex HIGH-1/HIGH-2 反映で
以下を mandate:

1. **新 metric `vendi_semantic_v2_encoder_swap`** を versioned 起こす (DA-14
   の MPNet `vendi_semantic` は historical record として常に併報告し、
   "DA-14 fail のまま DA-15 pass" を明示)
2. **Pre-registration**: encoder name + HF revision SHA + transformers/
   sentence-transformers version pin + commit SHA を Phase 1 開始時の最初の
   commit で `.steering/20260516-m9-c-adopt-da15-impl/decisions.md` に固定
3. **Plan A eligibility gate** (Codex HIGH-2 反映、shared Claude-arm 盲点
   = retrieval encoders ≠ style discriminators の対応):
   - language-balanced bootstrap (de/en/ja 内 independent resampling)
   - token-length-balanced bootstrap
   - within-language d 併報告 (d_de, d_en, d_ja)
   - **preregistered calibration panel**: Kant Critique 邦訳 + control
     philosopher (Heidegger 邦訳 + 英訳) で各 100 文を用意、各 candidate
     encoder が **language ID なしで Kant-style と control を分離可能**か
     test (AUC ≥ 0.75 を pass 基準)。fail した encoder は primary gate 除外
   - balanced condition で d > -0.5 になった encoder は ADOPT 寄与不可
4. **Apples-to-apples 維持**: v2 と no-LoRA baseline の両方を同 kernel で
   rescore
5. **Exploratory encoders** (philosophy-domain BERT 等) は ADOPT primary
   gate に含めない

### Phase 2: Plan B (Candidate C targeted hybrid、Phase 1 失敗時、~25h、別 PR)

de-focused stimulus を新規 driver で採取し、weighted retrain。Plan B 起動
rationale は **DA-14 verdict REJECT + Candidate C spec pre-authorisation のみ**
で行う (Codex MEDIUM-1 反映: DI-5 de+en mass soft warning は hard trigger
化しない、Plan B shape を guide する役割に limit)。

Hybrid H-α (Plan A 走行中の Plan B driver pre-stage) は **isolation
guardrails** を mandate (Codex MEDIUM-3 反映):

1. **別 branch / worktree** で作業 (`feature/m9-c-adopt-da15-plan-b-prep`
   or `git worktree`)、Plan A branch には commit しない
2. Plan A の test suite / lint / CI には含めない
3. Plan A verdict 書面で reference しない
4. Plan A pass 時は pre-stage を別 PR で merge せず保留 (将来 Phase E 再利用
   候補)
5. Plan A fail 時のみ別 PR (Phase 2 = Plan B) を起票

Plan B 採用判定は **achieved corpus stats** (de+en mass post-retrain ≥ 0.60)
**+ empirical DA-14 rerun verdict** で行う。predicted d (-0.3 to -0.8) は
non-gating directional prior (Codex MEDIUM-2 反映)。

### Phase 3: Plan C (longer/rank拡大) は本 ADR scope **外**

eval_loss step 2000=0.166 → final=0.180 の mild overfit が longer training を
contraindicate。rank=16 は Phase E A-6 question (DA-12 の rank=8 provisional
carry-over decision に従う)。Phase E A-6 で起票する際は **dry-run evidence**
(rank=16 で 1000-step subset の eval_loss trajectory) を必須前提とする
(Codex MEDIUM-2 反映、predicted d range は non-gating prior)。

### kant ADOPT 判定時の named limitation (Codex LOW-1 反映)

Plan A pass で kant 2-of-3 quorum (Vendi-swapped + ICC) で kant ADOPT する
場合、決定文書 (verdict report) に以下を必須記載:

> **Burrows reduction remains FAIL** (v2: +0.43% vs 5% target、Plan A は
> measurement-side swap で Burrows axis を改善しない)。German function-word
> stylometry は本 ADOPT で improved されていない。Plan A ADOPT は
> DA-15 `vendi_semantic_v2_encoder_swap` + ICC(A,1) の 2-of-3 quorum を
> 根拠とし、Burrows axis は Phase 2 (Plan B retrain) または reference
> corpus work で別途追求する open issue。

## 変更対象

### 修正するファイル (Phase 1 = Plan A 実装 PR)

- `src/erre_sandbox/evidence/tier_b/vendi.py` — `_load_default_kernel`
  (現在 line 294-322) を encoder name 引数化。MPNet default は維持し、
  multilingual-e5-large / bge-m3 を選択可能に。
- `scripts/m9-c-adopt/compute_baseline_vendi.py` — `--encoder` CLI 引数追加、
  default MPNet 維持。
- `tests/test_evidence/test_tier_b/test_vendi.py` (or 同等) — encoder
  parameterisation の unit test 追加。

### 新規作成するファイル (Phase 1)

- `scripts/m9-c-adopt/rescore_vendi_alt_kernel.py` — v2 + no-LoRA pilot 出力
  を複数 encoder で rescore、bootstrap CI 付きの cohens_d を `.steering/
  20260516-m9-c-adopt-da15-impl/da15-rescore-{kernel}-kant.json` に出力。
- `.steering/20260516-m9-c-adopt-da15-impl/` (次セッションが `/start-task`
  で起票)

### 新規作成するファイル (Phase 2 = Plan B、Phase 1 失敗時のみ)

- `scripts/m9-c-adopt/de_focused_monolog_collector.py` — de/en + ≥60 token +
  monolog/long-form bias の stimulus driver。tier_b_pilot.py の generation-
  side prompt + persona response 制約を base に拡張。
- `src/erre_sandbox/training/dataset.py` 拡張 — group-aware split に
  language-stratified split option 追加 (de monolog re-cast の eval leak 防止)。
- `data/eval/golden/kant_de_focused_*.duckdb` (G-GEAR 採取結果)

### 削除するファイル

- なし (DA-14 の adapter / shard / verdict はすべて historical reference として
  保持)

## 影響範囲

- **Vendi kernel swap (Phase 1)**: `compute_baseline_vendi.py` を import して
  いる downstream (rescue scripts, dashboard 等) は default 引数で MPNet 動作
  維持されるので影響なし。新 encoder 使用時のみ explicit opt-in。
- **Plan B retrain (Phase 2)**: data/lora/m9-c-adopt-v2/ に v3 サブディレクトリ
  追加、kant_r8_v2 は immutable 保持。SGLang adapter 動的登録の名前空間に
  `kant_r8_v3` を追加。

## 既存パターンとの整合性

- **DA-11 manifest convention**: `data/lora/m9-c-adopt-v2/<adapter>/manifest.
  json` に encoder name / version pin / git SHA を埋め込む (Phase 1 rescore
  artefact も同 schema)
- **da1_matrix_multiturn.py の thresholds-file pattern**: DA-15 採用後は
  `.steering/20260516-m9-c-adopt-da15-impl/da1-thresholds-da15.json` を新規
  pin (内容は DA-14 と同一、encoder 注釈のみ追加)
- **Codex independent review pattern**: Phase 1 / Phase 2 それぞれの
  implementation PR で別途 Codex review を起票 (本 PR は ADR review のみ)

## テスト戦略

### Phase 1 (Plan A)

- **単体テスト**: `_load_default_kernel(encoder_name="...")` で正しい
  HuggingFace model load + cosine similarity dim 一致
- **統合テスト**: 既存 v2 multi-turn pilot 出力 (`.steering/20260515-m9-c-
  adopt-retrain-v2-verdict/matrix-inputs/`) を 3 kernel で rescore し、
  bootstrap CI 計算が deterministic (seed=42 fixed) であること
- **回帰テスト**: MPNet default 引数で従来の DA-14 verdict 数値 (v2 mean
  33.183 / no-LoRA mean 33.311) が **再現** すること

### Phase 2 (Plan B)

- **単体テスト**: `de_focused_monolog_collector` の prompt生成 schema 検証、
  language detector が de を正しく label するか
- **統合テスト**: 新 driver で実 G-GEAR 採取した shard が `validate_multiturn_
  shards.py` を pass、group-aware split で eval ↔ train dialog_id 衝突ゼロ
- **回帰テスト**: 既存 5022 examples + 新規 de monolog 250+ が weight audit
  N_eff > 1500 / top 5% < 0.35 を満たす

## ロールバック計画

- **Phase 1 失敗**: Plan A の rescore 結果が DA-14 unmet の場合、
  multilingual-e5 / bge-m3 の不採用を `.steering/20260516-m9-c-adopt-da15-impl/
  decisions.md` D-α-FAIL として記録。MPNet default を維持し、Phase 2 へ。
  vendi.py の改修は backward-compatible なので merge 維持。
- **Phase 2 失敗**: Plan B retrain が DA-14 unmet の場合、kant については
  DA-15 系列が完全 fail と判定。Phase E A-6 で rank=16 (Plan C) を再評価。
  de_focused_monolog_collector.py + 新 shards は corpus capital として retain。

## 次セッション handoff

Phase 1 implementation は `.steering/20260516-m9-c-adopt-da15-impl/` で
`/start-task` 起票し、本 design sketch を継承して詳細化する。Phase 2 は
Phase 1 結果次第で別 PR (起票時期: Phase 1 verdict 後)。

`next-session-prompt-FINAL-impl.md` に Phase 1 着手手順 (encoder 選定 →
vendi.py parameterise → rescore script → CI 計算 → DA-15 verdict 文書化) を
記載。

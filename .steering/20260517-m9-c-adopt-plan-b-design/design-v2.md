# 設計 design-v2 — Plan B (Candidate C targeted hybrid retrain) — independent V2

> Independent reimagine generation by Task tool subagent (Plan mode).
> V2 author did NOT read `design-v1.md`. V1 / V2 / hybrid 採用判定は
> `decisions.md` DI-1 / DI-2 に記録。

## 0. Framing (一行)

Plan A の per-language signal (within-de d=-0.72 MPNet / within-en d=-0.58
E5) は本物だが global 6-window bootstrap が noise floor を超えなかった、
という Codex MEDIUM-2 整合仮説に **per-language の SNR を上げる介入**
で投資する。即ち retrain の corpus shape を「de-monolog 集中、長文、
marker dense」に bend し、評価面では encoder panel disagreement を
ADOPT 不寄与化する。Burrows axis 5% (DA-14 不変) を **主目標**、
Vendi v2-encoder-swap を secondary、ICC を 3 軸目の anchor とする。

## 1. de-focused monolog collector アプローチ

### 1.1 採用: **stimulus-driven, persona-prompt-augmented monolog 採取**

- **採取単位**: stimulus → focal turn の **single-turn long-form**
  (multi-turn ではない)。`tier_b_pilot.py` を base にするが
  **multi-turn alternation を捨てる**: addressee=None かつ
  expected_turn_count=1 固定。
- **monolog-as-stimulus-response** を採用、**monolog-as-system-prompt-
  driven self-reflection は捨てる**。後者は LoRA 学習ターゲットとして
  prompt-leakage / self-reference loop の eval contamination risk が
  あり、また Critique 系統の Kant スタイルは「読者に向けて講じる
  monolog」であって「自己内省」ではないため persona fit でない。

### 1.2 de + ≥60 token bias の作り方 (3 軸併用)

1. **stimulus 設計**: 既存 `golden/stimulus/kant.yaml` 70 stim のうち
   `prompt_text` が de で expected_zone ∈ {study, peripatos} のものを
   subset 抽出 (~30 stim 程度想定)。**新規 stimulus battery は作らない**
   (corpus capital を絞る判断)。stim が足りなければ既存 stim を
   loop で multi-sample。
2. **persona prompt 増強**: `_build_system_prompt` を Plan B 向けに
   **fork** (上書きしない、新 helper `_build_de_monolog_system_prompt`)。
   差分は 3 行:
   - "Answer in **German**, even if the stimulus is in English."
   - "Write **a single self-addressed monolog of 80–160 German words**
     (≈ 100–200 Qwen3 tokens). Do not address an interlocutor."
   - "Use Critique-of-Pure-Reason register: transcendental, a priori,
     an sich, kategorischer Imperativ, where the topic permits."
   サンプリング: temperature=0.7、`max_tokens=320`、`min_tokens` は
   SGLang が native 対応しないため **post-hoc filter で担保**。
3. **post-hoc filter (hard gate)**: 採取直後に
   `classify_language == "de"` AND `estimate_token_count >= 60` AND
   `marker_density_per_100_tokens >= 1.0` (Cambridge anchor の 50%
   floor) を満たさない row は **shard から物理削除**。target は
   **250 net examples**。

### 1.3 既存 5022-example blend

既存 corpus は **保持**。Plan B retrain は `kant_*.duckdb` glob に
新 shard `kant_de_monolog_run0.duckdb` を **append** するだけ。
weighting.py の language=de 1.4 + length>=60 1.5 + monolog 1.5 が
自動的に新 row の weight を ~2.5-3.0 (clamp 後 3.0) に押し上げる
ので、新規 250 examples の effective contribution は ~750-equivalent。
**weighting.py の coefficient は不変** (D-2 portability 維持、
HIGH-3 grey-zone を避ける)。

### 1.4 stimulus-response vs system-prompt self-reflection の選択理由

system-prompt self-reflection は「persona に自分自身について語らせる」
形になり、Critique 風 monolog の **referent が persona 自体** に
偏る (e.g. "Ich bin Immanuel Kant, und meine Theorie..." が頻発)。
これは Burrows function-word 頻度を不自然に self-reference 方向に
歪め、DA-14 Burrows axis を 「persona-meta-talk」で稼ぐ artefact の
温床になる。stimulus-response 形 (existing Toulmin 系 prompt) は
referent が claim/data/warrant の **argument 内容** に向くので、
Kant の transcendental argumentation を 1st-person で叙述する形に
自然になる。これは LISA stylometry paper の "content-bleached
content-independent style channel" 仮説と整合 (Codex HIGH-2 反映)。

## 2. Achieved corpus stats gate

### 2.1 thresholds

- **N_eff ≥ 1500** (DA-14 fallback trigger は 1000、target は 1500
  と既存 implementation に明記済 — そのまま流用)
- **top 5% weight share ≤ 0.35** (同上)
- **de+en weighted mass ≥ 0.60** (Codex MEDIUM-1 で soft warning
  と確定したが、**Plan B では hard gate に昇格**。これは MEDIUM-1
  違反ではない: MEDIUM-1 は「DI-5 を hard fallback trigger に
  retroactive 昇格するな」であり、Plan B 起動後の corpus shape
  expectation を hard gate にすることは別事象。decisions.md
  D-V2-MASS で明文化する)
- **追加 (V2 独自)**: **de single-language weighted mass ≥ 0.30**。
  Plan A の per-language signal が de で最強だった (-0.72 MPNet)
  ので、de+en で 0.60 を取れても en に偏ると per-language gain が
  得られない。de alone で 0.30 を要求し、en hidden free-rider を
  防ぐ。

### 2.2 配置 (pipeline 内 abort 位置)

`train_kant_lora._pre_training_audit` の直後、**かつ GPU stack
import の直前**。現状 `_pre_training_audit` は N_eff/top_5 を hard、
de+en を soft で扱う。Plan B run では `--plan-b-gate` flag (kw-only
CLI) を `train_kant_lora.py` に追加し、それが立っているときだけ
de+en と新 de-alone を hard gate に昇格する。flag 未指定の K-β /
v2 baseline path は **動作不変** (regression safety)。

### 2.3 JSON output shape

`data/lora/m9-c-adopt-v2/kant_r8_v3/plan-b-corpus-gate.json`
(weight-audit.json と別 file、責務分離):

```json
{
  "schema_version": 1,
  "plan_b_gate": "pass" | "fail",
  "thresholds": {
    "n_eff_min": 1500.0,
    "top_5_pct_max": 0.35,
    "de_en_mass_min": 0.60,
    "de_mass_min": 0.30
  },
  "achieved": {
    "n_eff": 0.0,
    "top_5_pct_weight_share": 0.0,
    "de_en_mass": 0.0,
    "de_mass": 0.0
  },
  "failed_axes": ["de_mass"],
  "weight_audit_path": "data/lora/m9-c-adopt-v2/kant_r8_v3/weight-audit.json",
  "merge_sha": "<本 PR merge SHA>",
  "captured_at_utc": "..."
}
```

### 2.4 abort behavior

`PlanBCorpusGateError` (新 exception、`erre_sandbox.training.exceptions`
に追加、`InsufficientEffectiveSampleSizeError` と同階層) を raise、
exit code 8 (既存 7 まで使用済、次空き)。kill 前に
`plan-b-corpus-gate.json` を必ず emit (forensic 必須)。

## 3. Retrain hyperparameters (v2 baseline からの delta、PR #168)

| param | v2 baseline | Plan B | 根拠 |
|---|---|---|---|
| rank | 8 | **8** | DA-12 carry-over 不変 |
| lora_alpha | 16 | **16** | 不変 |
| lora_dropout | 0.05 | **0.05** | 不変 |
| target_modules | q/k/v/o_proj | **q/k/v/o_proj** | 不変 |
| max_steps | 4000 | **2500** | v2 で step 2000=0.166 → final=0.180 の overfit 兆候、安全 margin で 2500 (step 2000 の少し上、3 eval window 分の余裕) |
| learning_rate | 2e-4 | **2e-4** | 不変 |
| LR scheduler | cosine | **cosine** | 不変、max_steps 短縮で decay も比例短縮 |
| warmup_ratio | 0.03 (default) | **0.03** | 不変 |
| eval_steps | 500 | **250** | early stopping 用に頻度倍化、2500 steps で 10 eval window |
| save_steps | 500 | **250** | eval と同期 |
| early stopping | なし | **patience=2 on eval_loss、min_delta=0.005** | v2 の 0.166→0.180 は +0.014 over 2000 steps、min_delta=0.005 が 1 eval window 雑音より大きく real overfit より小、patience=2 で false-positive halt を回避 |
| quantization | NF4 + double quant | **NF4 + double quant** | 不変、VRAM 12GB headroom 維持 |
| batch_size / grad_accum | 1 / 8 | **1 / 8** | 不変 |
| max_seq_length | 2048 | **2048** | 不変 (de monolog 100-200 token なので余裕) |

実装 delta: HF transformers の `EarlyStoppingCallback` を
`train_kant_lora.train_kant_lora` 内で `--plan-b-gate` flag 立ち時に
attach。`EarlyStoppingCallback(early_stopping_patience=2,
early_stopping_threshold=0.005)` + `metric_for_best_model="eval_loss"`
+ `greater_is_better=False` を TrainingArguments に追加。

## 4. language-stratified split option

### 4.1 signature

```python
def _group_aware_stratified_split(
    weighted_examples_by_shard: dict[str, list[dict[str, object]]],
    *,
    eval_split_fraction: float,
    seed: int,
    stratify_by_language: bool = False,   # ← 新 kw-only flag
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
```

注: 実際の `_group_aware_stratified_split` は
`src/erre_sandbox/training/train_kant_lora.py` 内にある (next-session
prompt の "dataset.py 拡張" は naming のみで、function 本体は
train_kant_lora.py に集約されている)。

`stratify_by_language=False` (既存 default) は完全 backward-compatible。
`True` のとき stratum key は `(source_shard_type, language)` の tuple
に拡張、各 stratum で独立 90/10 random split。

### 4.2 plug-in 位置

`_collect_from_shards_weighted` で
`stratify_by_language=use_lang_stratify` を CLI 経由で渡す。CLI flag
は `--lang-stratified-split` (default False)。Plan B run では立てる。

### 4.3 eval split contamination semantics for de-monolog re-cast

既存 `_make_synthetic_monologs` (natural shards の Kant-Kant pair から
作る monolog re-cast) と 新規 `kant_de_monolog_run*.duckdb` (driver が
直接 emit する de-monolog) は **同じ language stratum に属する** が、
leak risk が異なる:

- **既存 monolog re-cast**: train-side group key からのみ作る
  (現行コード) → leak 既に防御済
- **新規 de-monolog shard**: dialog_id は driver が新規発行
  (`de_mono_{stim_id}_{cycle}_{turn}`)、natural / stimulus shard の
  `dialog_id` namespace と **物理的に衝突しない** → 既存 group-aware
  split で十分 leak-safe

→ **stratify_by_language=True を立てても eval contamination 追加
リスクなし**。むしろ eval split が de-monolog を 10% 持ち越すので、
eval_loss が de-monolog distribution を **代表** するようになり、
early stopping signal が plan-B-relevant な方向に sharpened される
利点が出る。

## 5. D-2 allowlist for Plan B verdict

### 5.1 encoder set (4 encoder、Plan A 3 encoder + 1 lexical)

```json
{
  "schema_version": 2,
  "preregistration_note": "Plan B verdict 用 D-2 allowlist。Plan A 3 encoder に lexical-5gram を追加し、encoder agreement axis を 4-encoder 上で判定する。BGE-M3 sign flip 教訓を反映、retrieval encoder の disagreement を ADOPT 不寄与化する。",
  "library_versions": {
    "sentence_transformers": "3.4.1",
    "transformers": "4.57.6"
  },
  "encoders": {
    "intfloat/multilingual-e5-large": {
      "role": "primary",
      "revision_sha": "3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3"
    },
    "sentence-transformers/all-mpnet-base-v2": {
      "role": "primary",
      "revision_sha": "e8c3b32edf5434bc2275fc9bab85f82640a19130"
    },
    "BAAI/bge-m3": {
      "role": "exploratory",
      "revision_sha": "5617a9f61b028005a4858fdac845db406aefb181",
      "exclusion_reason": "Plan A natural d sign flip (+0.23 vs MPNet/E5 negative). 報告は obligatory だが ADOPT 寄与不可。"
    },
    "lexical_5gram": {
      "role": "primary",
      "revision_sha": "n/a",
      "implementation_module": "erre_sandbox.evidence.tier_b.vendi_lexical_5gram",
      "kernel_note": "Character 5-gram cosine similarity (Burrows-adjacent shallow stylometry)。retrieval-trained でない independent 軸。"
    }
  }
}
```

### 5.2 role 割当

- **primary (3)**: MPNet, E5-large, lexical-5gram
  - MPNet は DA-14 の baseline で再昇格 (Plan A では regression に
    格下げしたが、Plan B では per-language signal の最強検出器
    [d_de=-0.72] なので primary 復帰)
  - E5-large は per-language signal の en 軸検出器 (d_en=-0.58)
  - lexical-5gram は retrieval-trained でない independent kernel
- **exploratory (1)**: BGE-M3 (報告 obligatory、ADOPT 不寄与)

### 5.3 encoder agreement axis

- **gate**: Plan B ADOPT は **3 primary encoder のうち 2 以上**で
  「natural d ≤ -0.5 AND CI upper < 0 AND lang-balanced d ≤ -0.5
  AND length-balanced d ≤ -0.5」を満たすこと。**符号一致** (3 とも
  negative であること) を pre-condition、disagreement 時は除外。
- **rationale**: BGE-M3 sign flip 教訓を generalise — 「2 of 3 が
  同方向で gate clear」を要求すれば、1 encoder が retrieval artefact
  で flip しても ADOPT 判定を腐らせない。

### 5.4 Burrows axis (5%) との関係

Burrows は **encoder 非依存** なので D-2 allowlist の対象外、DA-14
threshold (≥5% point + CI lower > 0) を不変で適用。Plan B は de
monolog 集中で **Burrows axis 主目標達成** を狙う設計 (Vendi は
secondary)、これは v2 で +0.43% だった Burrows を 5% まで押し上げる
ことが de-mass increase で初めて現実的になる。

## 6. ファイル list

### 新規作成

- `scripts/m9-c-adopt/de_focused_monolog_collector.py` (~350 LOC)
- `scripts/m9-c-adopt/audit_plan_b_corpus_stats.py` (~120 LOC)
- `.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json`
- `.steering/20260517-m9-c-adopt-plan-b-design/g-gear-collection-runbook.md`
- `tests/test_training/test_dataset_lang_stratified.py` (~80 LOC)
- `tests/test_scripts/test_de_focused_monolog_collector.py` (~120 LOC)

### 修正

- `src/erre_sandbox/training/train_kant_lora.py` — `_group_aware_
  stratified_split` に `stratify_by_language` kw-only flag、
  `--plan-b-gate` CLI flag、`--lang-stratified-split` CLI flag、
  `EarlyStoppingCallback` attach、`PlanBCorpusGateError` raise wiring
- `src/erre_sandbox/training/exceptions.py` — `PlanBCorpusGateError`
  追加 (exit code 8)
- `src/erre_sandbox/evidence/tier_b/` — `vendi_lexical_5gram.py` 新規
  (lexical 5-gram cosine kernel、retrieval-trained でない独立 axis)

### 削除

- なし (DA-14/15 artifact は historical record として全保持)

## 7. Risks (5件)

### R-1: de-monolog post-hoc filter で **shard rejection rate が
過剰** で 250 net に到達しない

- mitigation: collector は `--target-net 250 --max-attempts 800` で
  動かす。実 acceptance rate は G-GEAR で `--dry-run` 50 attempt 先行
  採取して測定、< 25% なら persona prompt を強化して再 dry-run。

### R-2: **長文 de monolog で Qwen3-8B が repetition / loop に
落ちる** (max_tokens=320 に頭打ちまで同句反復)

- mitigation: SGLang chat に `frequency_penalty=0.3` /
  `presence_penalty=0.3` を Plan B 専用 flag で追加。post-hoc filter
  に **同一 trigram > 4 回出現** で reject する loop detector を入れる。

### R-3: **eval split の de-monolog 比率上昇で eval_loss が
artificially 低下**し、early stopping が遅延 → mild overfit 発生

- mitigation: lang-stratified split で eval も de=10% / en=10% /
  ja=10% / mixed=10% の **stratum 内 fraction を均一** にするので、
  eval distribution が train distribution と shape-match する。

### R-4: **persona drift** — collector の "answer in German" 指示が
強すぎて、Kant 以外の domain でも無理に de 出力させる

- mitigation: stimulus subset を de prompt + study/peripatos zone
  に絞った時点で moral_dilemma / tom / roleeval を exclude。
  Critique-style argumentation のみ使用。

### R-5: **D-2 allowlist で primary 3 になった lexical-5gram が
未実装** で Plan B verdict 時に sprint が必要になる

- mitigation: 本 PR の scope に `vendi_lexical_5gram.py` 実装と
  unit test を含める。lexical 5-gram kernel は ~50 LOC、計算量も MPNet
  / E5 より軽い (BERT embedding なし)。

## 8. V1 が見落とす可能性のある 1 つの "minority opinion" 決定

**「de+en mass 0.60 を hard gate に昇格すべきだが、それと同時に
**de alone ≥ 0.30** を新規 hard gate に追加すべき」** (§2.1)

V1 が見落とす理由:

- Codex MEDIUM-1 反映だけ素直に読むと「de+en soft warning のまま」
  で safe path を取る
- 反対方向 (hard gate 化) を選んだ場合も、Plan A spec の
  Candidate C 起動条件をそのまま流用すると **de+en 0.60 だけ** で
  停止する
- しかし Plan A 結果は per-language で **de が最強の signal source**。
  en が free-rider で 0.60 を達成しても per-lang signal は出ない。
- → de alone を独立 axis として gate を分けるのが MEDIUM-2 の
  "achieved corpus stats" 精神に整合。MEDIUM-1 retroactive promotion
  禁止にも違反しない (新規 axis を Plan B で起こす)

## 9. 実装パターンとの整合性

- DA-11 manifest convention 維持
- 既存 group-aware split pattern との直交軸として拡張
- D-2 enforcement 機構を流用 (schema_version=2 に bump)
- Codex independent review 起票 pattern を本 PR で踏襲

## 10. テスト戦略

- **unit**: lang-stratified split / post-hoc filter / 4-axis gate boundary
- **integration**: `validate_multiturn_shards.py` を Plan B shard に適用
- **regression**: `--plan-b-gate` flag 未指定で K-β / v2 baseline が
  byte-identical (golden test)

## 11. ロールバック計画

- **collector で 250 net 達成不能**: 採取結果を `data/eval/plan-b-
  rejected/` に隔離、retrain は v2 baseline で再実行 (Phase E A-6 へ
  migrate)
- **retrain で early stopping が即時 fire**: 別 PR で patience=3 +
  min_delta=0.01 に softening して再 retrain
- **DA-14 rerun verdict fail**: kant について Phase E A-6 で rank=16
  (Plan C) を再評価、本 PR の collector + lexical-5gram は corpus
  capital として retain

## 12. 次セッション handoff (retrain 実行)

1. `feature/m9-c-adopt-plan-b-driver` merge → main
2. `de_focused_monolog_collector.py` で 250 net 採取 (~3h)
3. `audit_plan_b_corpus_stats.py` で gate pre-check
4. `train_kant_lora.py --plan-b-gate --lang-stratified-split
   --max-steps 2500 --eval-steps 250 ...` で retrain (~20h)
5. DA-14 rerun (vendi MPNet/E5/BGE-M3 + lexical-5gram + Burrows +
   ICC) verdict 計算 (~2h、4 encoder × 2 baseline × CI bootstrap)
6. Plan B verdict 文書化、kant ADOPT or Phase E A-6 移行判定

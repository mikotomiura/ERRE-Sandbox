# Codex independent review request — m9-c-adopt Plan B (Candidate C hybrid retrain) design + driver

## 役割

You are an independent senior research engineer reviewing this branch
(`feature/m9-c-adopt-plan-b-driver`) for a research-grade ML/LoRA
project (ERRE-Sandbox). The branch sets up Phase 2 of the m9-c-adopt
escalation path after Plan A (DA-15 Vendi kernel swap) returned REJECT
for the kant persona. Your review precedes PR merge.

This is **not** the retrain execution PR — it is the design + collector
driver + audit script + corpus gate + verdict allowlist PR. Retrain
execution (~20h G-GEAR overnight) and DA-14 rerun verdict happen in the
next session after this PR merges.

## 求める出力

For each issue use:

```
[<SEVERITY>-<N>] <one-line title>
- Finding: <one paragraph>
- Why it matters: <one paragraph>
- Fix: <concrete code/spec change>
- Severity rationale: <one sentence>
```

Severities: HIGH / MEDIUM / LOW. End with a one-line **Verdict** of
ADOPT / ADOPT-WITH-CHANGES / REJECT. Cite specific files and line
ranges. Keep total length under 1500 words.

## 反映予定

- HIGH: mandatory reflection before merge
- MEDIUM: judgment, recorded in `decisions.md`
- LOW: defer OK in `blockers.md` with explicit reason

## 参照 file (verbatim)

### Plan A 結果 (Phase 2 起動 trigger)

- `.steering/20260516-m9-c-adopt-da15-impl/da15-verdict-kant.md` —
  Plan A REJECT verdict. Non-gating observations: MPNet within-de
  d=-0.72 / E5 within-en d=-0.58 / BGE-M3 natural d sign flip +0.23
- `.steering/20260516-m9-c-adopt-da15-impl/decisions.md` D-α-FAIL

### Plan A → Plan B sequential escalation ADR

- `.steering/20260516-m9-c-adopt-da15-adr/decisions.md` D-1 (採用 path)、
  D-2 (Codex HIGH/MEDIUM/LOW 反映)
- `.steering/20260516-m9-c-adopt-da15-adr/design.md` Phase 2 (~25h envelope)
- `.steering/20260516-m9-c-adopt-da15-adr/codex-review.md` MEDIUM-1
  (DI-5 de+en soft warning 維持)

### 横断 ADR (DA-11/13/14)

- `.steering/20260513-m9-c-adopt/decisions.md`:
  - DA-14: DA-1 thresholds re-calibration (Vendi d ≤ -0.5 + CI upper < 0、
    Burrows ≥ 5% + CI lower > 0、ICC(A,1) ≥ 0.55、throughput ≥ 70%)
- `.steering/20260515-m9-c-adopt-retrain-v2-verdict/decisions.md`:
  - DI-5: real-tokenizer audit (N_eff=3886.4、top 5%=0.139、de+en=0.489
    soft warning)
  - DI-7: training step time (eval_loss step 2000=0.166 → final=0.180 mild
    overfit)
  - D-1: REJECT verdict

### 本 PR の design + decisions

- `.steering/20260517-m9-c-adopt-plan-b-design/requirement.md`
- `.steering/20260517-m9-c-adopt-plan-b-design/design.md` (hybrid 採用版)
- `.steering/20260517-m9-c-adopt-plan-b-design/design-v1.md` (primary V1)
- `.steering/20260517-m9-c-adopt-plan-b-design/design-v2.md` (subagent V2)
- `.steering/20260517-m9-c-adopt-plan-b-design/decisions.md` DI-1〜DI-7
- `.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json`
- `.steering/20260517-m9-c-adopt-plan-b-design/g-gear-collection-runbook.md`

### 実装 file

- `scripts/m9-c-adopt/de_focused_monolog_collector.py` (Plan B-2 driver)
- `scripts/m9-c-adopt/audit_plan_b_corpus_stats.py` (4-axis hard gate)
- `src/erre_sandbox/training/train_kant_lora.py` (`stratify_by_language`
  kw-only flag added to `_group_aware_stratified_split` + plumbed through
  `_collect_from_shards_weighted`)

### test file

- `tests/test_de_focused_monolog_collector.py`
- `tests/test_audit_plan_b_corpus_stats.py`
- `tests/test_training/test_dataset_lang_stratified.py`

### 既存実装 (reference)

- `src/erre_sandbox/training/weighting.py` (language constant、N_eff、
  emit_weight_audit)
- `src/erre_sandbox/training/example_features.py` (classify_language、
  extract_example_metadata)
- `src/erre_sandbox/training/dataset.py` (build_weighted_examples、
  monolog re-cast)
- `scripts/m9-c-adopt/tier_b_pilot.py` (driver base 流用元)
- `scripts/m9-c-adopt/validate_multiturn_shards.py` (shard validation)

## 重点 review 観点 (review がこれだけに limit される必要はない)

1. **HIGH-3 遵守**: DA-14 thresholds は不変、Plan B 採用判定は achieved
   corpus stats + empirical DA-14 rerun verdict のみで行う。本 PR が
   thresholds を post-hoc 移動していないか。
2. **Codex MEDIUM-1 維持** (DA-15 ADR codex-review.md): DI-5 de+en=0.489
   < 0.60 は **soft warning のまま固定**。本 PR の Plan B 4-axis hard
   gate (`audit_plan_b_corpus_stats.py`) で de+en ≥ 0.60 と de ≥ 0.30
   を新規に hard gate 化したことは MEDIUM-1 違反か否か (本 PR
   decisions.md DI-3 は「Plan B 起動後の新規 axis であり、DI-5 数値の
   retroactive 移動ではない」と整理。Codex は同意するか)
3. **Plan A non-gating observation 活用** (within-de d=-0.72 / within-en
   d=-0.58 / BGE-M3 sign flip): design.md §5.2 で MPNet を Plan A の
   regression role から Plan B の primary role に **昇格** している。
   役割再割当ては statistical inference 上 problematic か (encoder
   pre-registration 原則との関係)
4. **encoder agreement axis** (design.md §5.3): 3 primary encoder のうち
   2 以上が同方向で gate clear、これは Plan A の per-encoder
   disagreement (BGE-M3 sign flip) への generalisation。1-of-3 でも
   ADOPT してしまう穴がないか、逆に over-conservative ではないか
5. **lexical-5gram 実装の scope 分割** (decisions.md DI-6): D-2
   allowlist では primary role を pre-register、実装は本 PR scope 外
   (次セッション retrain prep に scope)。これは Codex HIGH-2
   (preregistration discipline) と整合するか
6. **post-hoc filter 4 軸** (de_focused_monolog_collector.py
   `filter_de_monolog`): language=de + token>=60 + marker density >=1.0
   + trigram loop max <=4。R-1〜R-5 risk (collector design.md §7) に
   対する mitigation として十分か
7. **dataset.py 拡張の所在変更** (decisions.md DI-5): 本 PR は
   `train_kant_lora.py` の `_group_aware_stratified_split` を拡張
   (function 本体の所在に従う)。"dataset.py 拡張" という naming は
   misleading でない (将来 reader が dataset.py を grep しても見つから
   ない問題はないか)
8. **early stopping (patience=2, min_delta=0.005)** (design.md §1.4):
   v2 の 0.166→0.180 envelope に empirically tied。false-positive halt
   の確率と true-positive halt の確率の trade-off は妥当か
9. **manifest convention 維持** (DA-11): `data/lora/m9-c-adopt-v2/
   <adapter>/manifest.json` に encoder name / version / git SHA + 本 PR
   merge SHA を埋め込む明示が g-gear-runbook §7 と decisions.md にあるが、
   本 PR で manifest 自動 emit のコードが既存 train_kant_lora.py に
   組み込まれているか / 別途必要か

## 出力先

`.steering/20260517-m9-c-adopt-plan-b-design/codex-review.md` に verbatim
保存される (本セッションの parent agent が処理)。

## 完了基準

- 上記 review 観点をカバーする HIGH/MEDIUM/LOW 指摘リスト
- 最後に Verdict
- 1500 words 以下

# 重要な設計判断 — m9-c-adopt pilot multi-turn investigation

> Codex independent review (gpt-5.5 xhigh, 2026-05-14、verbatim `codex-review.md`)
> の HIGH 4 件 / MEDIUM 5 件 / LOW 2 件を反映。本 task の DA-13 draft は
> **採取前** に判定 criterion を pre-register する (HIGH-3 反映)。

---

## D-1: Codex HIGH 4 件の反映方針 (本セッション adopt)

- **判断日時**: 2026-05-14
- **背景**: design.md 初版 (no-LoRA SGLang control なし、turn-count 300 単独
  comparison、scenario criteria 未数式化、smoke 目視のみ) に対する Codex
  review で **MODIFY before implementation** verdict + HIGH 4 件。

### HIGH-1 reflection: 採用 = mitigation 1 + 2 (full 2x2 は scope 外)

- Scenario I 結論を「**historical baseline-like no-prior multi-turn sampling
  is sufficient to reverse the pilot direction**」に弱める (mitigation 1)
- **rank=8 だけ no-LoRA SGLang control** を同 multi-turn protocol で採取
  (mitigation 2)、historical Ollama baseline ではなく **exact
  protocol/backend-matched baseline** との比較を primary にする
- mitigation 3 (full 2x2 = single + multi × no-LoRA + LoRA) は **scope 外**
  (compute budget tight、rank=8 単独 control で identifiability 改善は得られる)

### HIGH-2 reflection: 採用 = mitigation 2 (matched baseline downsampling)

- `--turn-count 300 --cycle-count 6` を維持 (compute 抑制)
- historical baseline (5 shard) を **pilot と同じ stimulus slice + 同 window
  count** に downsample / recompute、新 `tier-b-baseline-matched-kant-*.json` を
  生成
- primary comparison は **matched baseline** に切替、historical baseline との
  対比は diagnostic only
- mitigation 1 (full-battery `--turn-count 528+`) は compute ~5-6h と重く、本 PR
  scope 外。matched downsampling で window/coverage equality は確保できる

### HIGH-3 reflection: 採用 = 採取前 preregister

DA-13 draft (本 PR section) に **採取前** に判定 criterion を固定。post-hoc
movement を防ぐため、commit 後の criterion 変更は別 ADR (DA-14) として記録する。

primary rank=8 multi-turn LoRA-on vs matched baseline:

- **Scenario I (reversal confirmed)** —
  - Vendi semantic: `Δ = point_LoRA - point_matched_baseline`、bootstrap CI
    upper bound `< 0`、Cohen's d `< -0.5`
  - Burrows reduction: point `> +5%`、bootstrap CI lower bound `> 0`
  - AND: rank=4 / rank=16 のうち最低 1 件で同 direction (Vendi + Burrows 両軸)
- **Scenario II (no reversal)** —
  - Vendi semantic point は LoRA-on > matched baseline のまま OR CI が 0 を跨ぐ
  - Burrows reduction point は ≤ 0 OR CI が 0 を跨ぐ
- **Scenario III (mixed)** —
  - Vendi / Burrows の片方のみ reversal、または rank ごとに direction 不一致
  - `Cohen's d (single-turn pilot vs multi-turn pilot)` 改善はあるが
    matched baseline 比較で thresholds 未達
- **Scenario IV (採取 fail / 信頼不能)** —
  - 採取 fail (>= 1 shard で focal_observed < 0.9 × focal_target) OR
  - 全 rank で CI width `> 1.5×` single-turn pilot CI width

### HIGH-4 reflection: 採用 = validation query を DA-13 acceptance gate に

採取後に以下の SQL を実行、artefact `validation-multiturn-kant.json` に保存。
**全 check PASS** を DA-13 publish の precondition とする:

```sql
-- Check 1: speaker_persona_id alternation
SELECT speaker_persona_id, turn_index, count(*)
FROM raw_dialog.dialog
GROUP BY 1, 2 ORDER BY 1, 2;
-- 期待: kant rows on turn_index ∈ {0, 2}、_stimulus rows on {1} (or vice-versa)

-- Check 2: focal count vs target
SELECT count(*) FROM raw_dialog.dialog WHERE speaker_persona_id = 'kant';
-- 期待: focal_target (300) ± 5% per shard

-- Check 3: turn_index range per dialog_id (incomplete dialog detect)
SELECT dialog_id, min(turn_index), max(turn_index), count(*)
FROM raw_dialog.dialog
GROUP BY dialog_id
HAVING max(turn_index) - min(turn_index) + 1 != count(*);
-- 期待: 0 rows (no partial dialogs)

-- Check 4: focal-only consumer input simulation
SELECT count(*) FROM raw_dialog.dialog WHERE speaker_persona_id NOT IN ('kant');
-- 期待: focal-only consumer はこの行を SELECT しない (確認のみ)
```

- **採用**: HIGH 全 4 件 modify を本 PR 内で反映
- **理由**: HIGH 4 件は empirical claim の根拠を直接揺らがす。実装着手前に
  反映するのが Codex review 12 回目 (Phase A 段階) で確立した運用 (HIGH 即反映)。
- **トレードオフ**:
  - compute budget が +1h (no-LoRA control 2 shard 採取)
  - design complexity が +20% (matched baseline downsampling consumer
    invocation、preregister thresholds、validation query)
- **影響範囲**:
  - `tier_b_pilot.py`: `--no-lora-control` flag 追加
  - `compute_baseline_vendi.py` / `compute_burrows_delta.py`: 既存
    `--shards-glob` のままで baseline subset downsampling 可能 (consumer 不変、
    呼び出し側で shard filter)
  - `da1_matrix.py`: `--matched-baseline` JSON path 追加 + `--include-multiturn`
  - DA-13 ADR を **採取前** draft、採取後に **判定書込み**
- **見直しタイミング**: 採取後の validation query で fail check 発生
  → DA-14 起票で operational policy update

---

## D-2: MEDIUM 反映方針

- **MEDIUM-1** (prior_turns adjunct): 採用 ADOPT-WITH-NOTE。primary は no-prior
  (apples-to-apples with baseline)、optional `--prior-turns-mode include` は
  本 PR では実装しない (Phase E A-6 design input に持ち越し)
- **MEDIUM-2** (compute budget): 採用 MODIFY。matched downsampling + no-LoRA
  control 反映で recompute、`requirement.md` に明記
- **MEDIUM-3** (checkpoint resume incomplete dialog): 採用 MODIFY。stimulus
  単位 atomic commit に切替 — fatal 時に in-progress `dialog_id` を delete
  してから checkpoint、resume 後に同 stimulus を re-run
- **MEDIUM-4** (ICC(A,1) diagnostic only): 採用 ADOPT-WITH-NOTE。report に
  併報告するが scenario 判定には使わない
- **MEDIUM-5** (paired diff diagnostic): 採用 MODIFY。post-collection
  diagnostic として `paired_diff_kant.json` を `da1_matrix.py` から派生

## D-3: LOW 反映方針

- **LOW-1** (wording): 採用 MODIFY。`design.md` + `decisions.md` で
  "baseline-style no-prior alternating-speaker stimulus protocol" に統一
- **LOW-2** (`--multi-turn-max 6`): 採用 ADOPT-WITH-NOTE。design.md に
  「現状 Kant 最大 expected_turn_count=3、6 は future battery 用 cap」追記

---

## DA-13 (draft、採取前 preregister) — Phase B Phase 後 multi-turn investigation

> **STATUS**: DRAFT (採取前 preregister)。採取後に matrix を埋め、最終 verdict を
> 確定して `.steering/20260513-m9-c-adopt/decisions.md` に commit する。

### 採取後に確定する箇所 (placeholder)

- `matrix` table: rank ∈ {4, 8, 16} multi-turn LoRA-on + rank=8 no-LoRA SGLang
  control + matched baseline + historical baseline + historical pilot
  (single-turn) の Vendi / ICC(C,k) / ICC(A,1) / Burrows reduction / throughput
- `verdict` 行: Scenario I / II / III / IV のいずれを採用するか
- `後続経路` 行: Phase E A-6 direct / retrain v2 / Phase E A-6 amended / Phase E
  direct のいずれを confirmed trigger とするか

### 採取前に固定済 (preregister、HIGH-3)

- **primary comparison**: rank=8 multi-turn LoRA-on vs **matched baseline**
  (historical baseline downsampled to pilot's selected stimulus slice + window
  count w=100, n=6)
- **scenario thresholds**: 上 HIGH-3 reflection 参照
- **validation gate**: 上 HIGH-4 reflection 参照、全 check PASS が DA-13
  publish の precondition

### 採取後の commit ルール

- 採取 + consumer 完遂後、`da1-matrix-multiturn-kant.json` + 上記 thresholds
  evaluation を script で機械的に実行、scenario verdict を automatic に確定
- post-hoc に threshold を緩める変更は禁止 (HIGH-3 spirit)、変更要なら DA-14 起票


# DA-14 Plan B verdict — kant (encoder agreement axis)

**verdict**: `PHASE_E_A6`

## Thresholds (DA-14 / Plan B, unchanged)

- Vendi natural d ≤ `-0.5` AND natural CI upper < 0
- Lang-balanced d ≤ `-0.5`
- Length-balanced d ≤ `-0.5`
- Burrows reduction% ≥ `5.0` AND CI lower > 0
- ICC(A,1) ≥ `0.55`
- Throughput pct of baseline ≥ `70.0%`

## Per-encoder rescore (Plan B 4-encoder panel)

| encoder | role | natural d | lang-bal d | length-bal d | natural | lang-bal | length-bal | all-3 |
|---|---|---|---|---|---|---|---|---|
| `sentence-transformers/all-mpnet-base-v2` | primary | -0.5211 | 0.2514 | -0.0840 | FAIL | FAIL | FAIL | no |
| `intfloat/multilingual-e5-large` | primary | 0.2014 | 0.0264 | 0.1415 | FAIL | FAIL | FAIL | no |
| `lexical_5gram` | primary | 0.2596 | 0.1303 | 0.0778 | FAIL | FAIL | FAIL | no |
| `BAAI/bge-m3` | exploratory | 0.6385 | 0.4294 | 0.4968 | FAIL | FAIL | FAIL | no |

## Encoder agreement axis (3-of-4 primary, 2+ required)

- Primaries clearing all 3 axes: **0 of 3** (required ≥ 2)
- All primary natural d share negative sign: **False**
- Primary encoders passing: `[]`
- Exploratory (reported, non-quorum): `['BAAI/bge-m3']`
- Axis verdict: `FAIL`

## Kernel-independent axes

- Burrows reduction% = `-1.5408` (CI lo=`-4.4952` hi=`1.3435`) → `FAIL`
- ICC(A,1) = `0.8768` → `PASS`
- Throughput pct = `100.05%` → `PASS`

## Phase E A-6 (rank=16 spike) — next step

At least one axis failed. Plan B kant is routed to Phase E A-6 (rank=16 spike) as the next investment. Open a new ADR DA-16 for the rank=16 hypothesis, recording which axes failed and the within-language d patterns that motivate rank capacity expansion vs further corpus tuning.

## Pre-registration anchor

Encoder + revision SHA + library versions + kernel_type are pinned in `.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json`. Rescore + verdict outputs embed the runtime-detected SHA so the audit chain is self-contained.

---

## v3 v4 forensic 対比 (PR-4 で生成、DA-16 候補 A の根因切り分け)

PR #186 (DA-16 ADR) で確定した順序 = **候補 A** (WeightedTrainer Blocker 2
fix → kant_r8_v4 retrain → DA-14 rerun verdict) に基づき、v4 verdict と v3
verdict (`.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-verdict-plan-b-kant.md`) を直接対比する。

### eval_loss (DA16-2 で v3 v4 直接比較可と確定、`sample_weight=1.0` + eval batch=1)

| metric | v3 (kant_r8v3) | v4 (kant_r8v4) | Δ |
|---|---|---|---|
| best eval_loss | `0.18259` @ step 1500 | `0.18046` @ step 2000 | **−0.00213** (改善) |

### Per-encoder natural d (Plan B 4-encoder panel)

| encoder | role | v3 natural d | v4 natural d | Δ | sign-flip 解消? |
|---|---|---|---|---|---|
| MPNet | primary | `-0.5264` | `-0.5211` | +0.0053 | 元から negative (sign-flip なし)、\|d\| ほぼ不変 |
| E5-large | primary | `+0.4781` | `+0.2014` | **−0.2767** | sign-flip 部分解消 (positive 維持だが magnitude 半減、ゼロへ converge) |
| lexical_5gram | primary | `+0.1805` | `+0.2596` | +0.0791 | sign-flip 未解消 (positive まま、slight 悪化) |
| BGE-M3 (exploratory) | n/a | `+0.3317` | `+0.6385` | +0.3068 | sign-flip 未解消、\|d\| 増加 (悪化) |

**direction discipline**: v3 と同様に v4 でも primary encoder 間の natural d
sign は **−/+/+** で 2-of-3 negative-side primaries 一致条件を満たさない
(encoder agreement axis FAIL)。Plan B 設計の "All primary natural d share
negative sign" は v3 v4 共に `False`。

### Kernel-independent axes

| axis | gate | v3 | v4 | Δ |
|---|---|---|---|---|
| Burrows reduction% | ≥5pt + CI lo > 0 | `-1.9482` (CI: -5.07 → 1.14) | `-1.5408` (CI: -4.50 → 1.34) | +0.4074 pt (依然 negative、CI で 0 を跨ぐ) |
| ICC(A,1) | ≥0.55 | `0.9083` | `0.8768` | −0.0315 (PASS 維持) |
| Throughput pct | ≥70% | `99.17%` | `100.05%` | +0.88 pt (PASS 維持) |

### WeightedTrainer fix (PR-2 `.mean()` reduce) の効果 — 部分的に観測

- **E5-large 改善 (positive 強度半減)**: v3 で +0.48 と最大の sign-flip 強度を
  示していた E5-large が v4 で +0.20 に converge (Δ−0.28)。これは
  WeightedTrainer Blocker 2 (sample weight collapse) 修正が weighted gradient
  経路に意図通り効いたことの empirical 証拠
- **MPNet 不変**: 元から negative direction で sign-flip ではなく \|d\| 不足
  (CI 不通過) が原因。WeightedTrainer fix 単独では \|d\| 拡大効果なし
- **lex5 / BGE-M3 悪化**: capacity hypothesis を示唆。rank=8 で
  lex/character-level の signal capacity が不足、weighting fix で de_monolog
  への gradient 集中が更に強化された結果、lex/character-level の signal
  が伸びる余裕がなかった (rank=8 capacity 制限内で意味的方向が de_monolog
  に偏った)、と解釈する余地あり
- **Burrows reduction% は −1.95% → −1.54% で slight 改善** だが gate
  (≥5pt + CI lo > 0) からはかなり遠い

### Verdict 解釈と PR-5 経路選択

**verdict = PHASE_E_A6 (REJECT)**。1+ axis FAIL (encoder agreement +
Burrows)、DA16-4 thresholds 不変方針に従い ADOPT 化禁止。

**根因切り分けの結論** (DA-16 候補 A の outcome (ii) "REJECT, direction
converged but \|d\| 不足 → capacity 仮説、PR-5 rank=16 を推進" に該当):
- WeightedTrainer fix は **少なくとも E5-large に部分的効果** を示した
  (sign-flip 半減) ため、Blocker 2 (sample weight collapse) は実在 + 修正
  必要だった (PR-2 の正当性確認)
- しかし **rank=8 capacity 不足** が支配的要因として残存。MPNet \|d\| 不足 +
  Burrows reduction% 改善せず は capacity expansion を呼ぶ
- 従って **PR-5 = rank=16 spike retrain** (HF push skip、新 adapter
  `kant_r16_v1` 生成、`--max-lora-rank 16` VRAM fit spike を含む)

詳細な PR-5 next-session prompt は `next-session-prompt-FINAL-pr5-rank16-spike-reject.md` を参照。


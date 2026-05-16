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
| `sentence-transformers/all-mpnet-base-v2` | primary | -0.5264 | -0.2653 | -0.3964 | FAIL | FAIL | FAIL | no |
| `intfloat/multilingual-e5-large` | primary | 0.4781 | 0.5310 | 0.3069 | FAIL | FAIL | FAIL | no |
| `lexical_5gram` | primary | 0.1805 | 0.3118 | 0.3246 | FAIL | FAIL | FAIL | no |
| `BAAI/bge-m3` | exploratory | 0.3317 | 0.2256 | 0.1991 | FAIL | FAIL | FAIL | no |

## Encoder agreement axis (3-of-4 primary, 2+ required)

- Primaries clearing all 3 axes: **0 of 3** (required ≥ 2)
- All primary natural d share negative sign: **False**
- Primary encoders passing: `[]`
- Exploratory (reported, non-quorum): `['BAAI/bge-m3']`
- Axis verdict: `FAIL`

## Kernel-independent axes

- Burrows reduction% = `-1.9482` (CI lo=`-5.0717` hi=`1.1403`) → `FAIL`
- ICC(A,1) = `0.9083` → `PASS`
- Throughput pct = `99.17%` → `PASS`

## Phase E A-6 (rank=16 spike) — next step

At least one axis failed. Plan B kant is routed to Phase E A-6 (rank=16 spike) as the next investment. Open a new ADR DA-16 for the rank=16 hypothesis, recording which axes failed and the within-language d patterns that motivate rank capacity expansion vs further corpus tuning.

## Pre-registration anchor

Encoder + revision SHA + library versions + kernel_type are pinned in `.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json`. Rescore + verdict outputs embed the runtime-detected SHA so the audit chain is self-contained.

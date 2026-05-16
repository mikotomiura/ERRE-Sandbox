# DA-15 Phase 1 verdict — kant (Plan A = Vendi kernel swap)

**verdict**: `REJECT`

## Metric definition (Codex HIGH-1)

DA-15 introduces a *versioned amended* Vendi metric `vendi_semantic_v2_encoder_swap` so that swapping the encoder cannot retroactively rescue a DA-14 axis. The DA-14 MPNet instrument (`vendi_semantic`) is always reported alongside as the regression baseline.

| | DA-14 MPNet (regression record) | DA-15 amended metric |
|---|---|---|
| Vendi axis | `vendi_semantic` cohens_d=-0.1788 (CI hi=0.6212) → `FAIL` | `vendi_semantic_v2_encoder_swap` — see below |
| Burrows axis | `burrows_reduction` point=114.6078 → `FAIL` (5% target unmet) | not in scope (Plan A is Vendi-only) |
| ICC axis | ICC(A,1) point=0.9129 → `PASS` | kernel-independent → `PASS` |
| Throughput | rate_focal_per_s=98.80% → `PASS` | not affected → `PASS` |

## DA-15 per-encoder rescore

| encoder | calibration AUC | natural d | lang-bal d | length-bal d | calibration | natural | lang-bal | length-bal | eligible |
|---|---|---|---|---|---|---|---|---|---|
| `BAAI/bge-m3` | 0.9055 | 0.2286 | 0.1456 | -0.2655 | PASS | FAIL | FAIL | FAIL | no |
| `intfloat/multilingual-e5-large` | 0.8865 | -0.1567 | -0.1754 | -0.4454 | PASS | FAIL | FAIL | FAIL | no |
| `sentence-transformers/all-mpnet-base-v2` | 0.8960 | -0.1788 | -0.3368 | -0.7268 | PASS | FAIL | FAIL | FAIL | no |

## Per-encoder within-language d (encoder eligibility audit)

| encoder | d_de | d_en | d_ja |
|---|---|---|---|
| `BAAI/bge-m3` | 0.2454 | -0.2781 | — (insufficient mass) |
| `intfloat/multilingual-e5-large` | -0.1858 | -0.5763 | — (insufficient mass) |
| `sentence-transformers/all-mpnet-base-v2` | -0.8021 | -0.4526 | — (insufficient mass) |

## kant ADOPT quorum

- Plan A primary axes passed: **1 of 3**
- Plan A quorum threshold: **2_of_3**
- ICC(A,1) PASS (kernel-independent, from DA-14)
- Vendi (DA-15 amended) PASS: **False** (eligible encoders: [])
- Burrows reduction PASS: **False**

## Rejection rationale

No candidate encoder cleared both the calibration gate (AUC ≥ 0.75) and the DA-14 thresholds (cohens_d ≤ -0.5, CI upper < 0) under standard + balanced bootstrap. Plan A is therefore unable to reach the kant 2-of-3 quorum even with ICC(A,1) PASS. Phase 2 (Plan B = Candidate C targeted hybrid retrain) is the documented next step.

### What Plan A *did* find (non-gating observation)

The within-language d slices show that **the encoders detect some directional effect** even where the global gate fails:

* MPNet within-de d = **-0.802** (clears the point gate, fails the CI gate)
* E5-large within-en d = **-0.576** (clears the point gate, fails the CI gate)
* BGE-M3 within-de / within-en flip sign (+0.245 / -0.278) — the BGE-M3 metric reverses direction overall

This is consistent with the DA-14 measurement-side hypothesis ("the LoRA does shift persona-style in some slices, but the global mixed-language signal is too noisy for the 6-window bootstrap to declare significance"), but it is **non-gating** — Plan A's pre-registered thresholds operate on the global metric, and Plan A was structurally designed to upgrade ADOPT only when the global threshold clears across primary candidate encoders. The within-language observations are recorded for Phase 2 design guidance (Plan B retrain should target per-language diversity, not global diversity).

### Cross-encoder direction note

MPNet and E5-large agree on the sign of the natural-window d (-0.18 / -0.16); BGE-M3 reverses sign (+0.23). This is the kind of behaviour Codex HIGH-2 anticipated when it required the calibration gate: retrieval-trained encoders are not stylometry validation, and even with a passing calibration AUC the rescore can reflect language/length artefacts. The disagreement strengthens the case that Plan A is structurally too noisy for the kant escalation under the available pilot evidence and that Phase 2 retrain (Plan B) is the appropriate next investment.

## Pre-registration anchor

Encoder + HF revision SHA + library versions are pinned in `.steering/20260516-m9-c-adopt-da15-impl/decisions.md` D-2. Output files (`da15-calibration-*.json`, `da15-rescore-*.json`) embed the runtime-detected revision SHA so the audit chain is self-contained.

# DA-15 ADR draft V2 — retrain v2 REJECT escalation (independent subagent draft)

> **Status**: independent V2 draft per `/reimagine` Step 3 (V1-blind, generated
> via Task tool Plan subagent dispatch — see decisions.md DI-2). To be diff'd
> against V1 and hybrid candidates extracted in `da15-comparison.md`.
> **Inputs**: requirement.md, DA-14 verdict JSON, DI-5/DI-7/D-1,
> design-final.md §1/§2.3, DA-14 spec, `da1-thresholds-recalibrated.json`,
> existing training/scoring code under `src/erre_sandbox/training/` +
> `src/erre_sandbox/evidence/tier_b/vendi.py` + `scripts/m9-c-adopt/`.

---

## 1. Empirical state to escalate from

DA-14 verdict (`da14-verdict-v2-kant.json`) and DI-5 / DI-7 / D-1 give us a
tight empirical anchor. Any escalation hypothesis that does not explain these
four numbers below should be rejected on grounds of evidence-detachment:

| Axis | v2 | no-LoRA | Δ vs no-LoRA | threshold | gap to threshold |
|---|---|---|---|---|---|
| Vendi semantic (d) | 33.183 | 33.311 | d = **-0.179** (correct sign) | d ≤ -0.5 | need ~2.8x further reduction in signed effect size |
| Burrows reduction | 114.61 | 115.10 | **+0.43%** (correct sign) | ≥ 5% | need ~11.6x further reduction |
| ICC(A,1) | 0.913 | 0.906 | +0.007 | ≥ 0.55, CI ≥ 0.50 | PASS, headroom saturated |
| Throughput | 0.82 focal/s | 0.83 focal/s | 98.8% | ≥ 70% | PASS |

Two more facts dominate the design space:
- **Pre-training audit soft warning** (DI-5): de+en weighted mass = 0.489
  (target 0.60). N_eff (3886) and top-5% share (0.139) are healthy. The only
  data-side concentration miss is the de/en mass.
- **Training envelope blew past 8h** (DI-7): 4000 steps × NF4 r=8 took 16h19m
  on G-GEAR. Peak VRAM 10.62GB / 12GB safety margin. eval_loss 0.180 (mild
  overfit tendency vs step-2000=0.166, but acceptable).

The directional reversal vs prior LoRA r=8 (Vendi +1.39 → -0.13, Burrows -1.38
→ -0.49) tells us the **weighted-loss + monolog re-cast + amended thresholds
path is producing the right gradient direction** but with insufficient
amplitude. This is a magnitude problem, not a sign problem — which prunes the
escalation tree substantially.

## 2. Three plans, equal-footing trade-off

### Plan A — Vendi semantic kernel swap

**Hypothesis**: `sentence-transformers/all-mpnet-base-v2` (used by
`_load_default_kernel` in `vendi.py:294-322` and `compute_baseline_vendi.py:188`)
is **English-pre-trained and likely over-invariant to de/en/ja persona
shifts**. A multilingual encoder (multilingual-e5-large, bge-m3) or a
philosophy-domain BERT might surface the Kantian style variance currently being
projected onto a near-null subspace of the MPNet embedding.

**Evidence grounding (DA-14 alignment)**:
- v2 Vendi mean (33.18) and no-LoRA mean (33.31) differ by only 0.13 in
  MPNet-Vendi units. The ratio of within-window variance to between-condition
  mean shift is so large that even a real persona shift could be invisible to
  MPNet — consistent with the prior r=8 measurement (Vendi +0.446 *wrong
  direction* but tiny).
- DA-14 `da1-thresholds-recalibrated.json` explicitly lists
  `vendi_fail_but_others_pass → ESCALATE_DA15_vendi_kernel_swap` in its
  `ai_decision_protocol`. The current verdict is *Vendi + Burrows fail* (not
  just Vendi), but kernel swap is pre-blessed as a valid DA-15 path.
- ICC(A,1) PASS shows the underlying generations do have *measurable
  persona-fit shift*, just not a Vendi-detectable one in MPNet space. This is
  strong evidence that the measurement instrument, not the training, is the
  bottleneck for at least the Vendi axis.

**Compute cost**: very low. Rescore existing v2 + no-LoRA windows under 2-3
candidate encoders. Each encoder is ~1-2GB download, scoring 30 windows × ~100
utterances each takes minutes on G-GEAR or even CPU. **Estimated wall time:
1-2h total including download + 3-kernel rescoring + bootstrap CI.**

**Reversibility**: very high. No training artefact churn, no .duckdb shard
churn, no LoRA adapter regeneration. Failed kernels are throw-away.

**Predicted effect size improvement** (Vendi axis only):
- multilingual-e5-large: plausible d delta range **-0.3 to -1.2** (multilingual
  encoder should resolve ja vs de stylistic variance MPNet collapses)
- bge-m3: similar range, additionally trained on document-level retrieval which
  often surfaces stylistic register
- philosophy-domain BERT (e.g., SciBERT, philosophy-tuned LegalBERT analogue):
  narrower range **-0.2 to -0.6**, more speculative
- **Cannot fix Burrows axis** — Burrows uses German-only function-word
  reference, not embeddings. So Plan A alone cannot pass quorum unless ICC +
  Vendi-swapped pass, which would still be only 2-of-3 — *enough for kant
  2-of-3*. **Plan A is sufficient for kant ADOPT if the Vendi swap succeeds.**

**C1-C4 gap address**: addresses none of the *training* gaps. It addresses
**a 5th, previously-unrecognised measurement gap (M1: encoder language
coverage)**. This is the plan's distinctive contribution and its primary
weakness — if you believe v2's training did the right thing, M1 is exactly the
right place to look. If you don't, M1 is a distraction.

**HIGH-3 risk** (live debate, see §4): swapping the Vendi encoder is a
**methodology shift, not a threshold movement**. The threshold (`d ≤ -0.5`) is
held literally constant. However, the *meaning* of `d` under multilingual-e5
is empirically different from `d` under MPNet — the same persona shift may
produce systematically larger or smaller d values. This is the grey zone.
**Mitigation**: pre-register the swap, rescore *both* v2 and no-LoRA baseline
windows under the new kernel (apples-to-apples), and publish the encoder
choice + version pin + rescore artefacts before reading the verdict. If we
treat the threshold as "operationally defined relative to the no-LoRA baseline
rescored under the same encoder", we are mechanically consistent with DA-14's
intent.

### Plan B — Candidate C targeted hybrid

**Hypothesis**: the de+en weighted mass deficit (0.489 vs target 0.60, ~18%
short) is the empirical bottleneck. Adding ~2,500 targeted-language long-form
examples raises de+en mass to ~0.60+, which is the design-final.md §2.3
Candidate C spec that DA-14 already pre-blessed as a fallback path.

**Evidence grounding (DA-14 alignment)**:
- DI-5 audit identified de+en as the single soft warning. Everything else
  (N_eff, top-5%, monolog injection) is in spec.
- DA-14 lists this as `weight_concentration_audit_fail →
  ESCALATE_CANDIDATE_C_targeted_hybrid`. Technically our audit did *not* fail
  (it issued a soft warning), but the spirit of the fallback applies.
- The directional reversal of v2 supports the data-side hypothesis: the
  weighting + monolog injection is moving the gradient correctly, but the de/en
  signal is underweighted in absolute terms because the source corpus is
  ja-dominant. Adding raw de/en mass directly attacks the weight-concentration
  mechanism.

**Compute cost**: moderate-high. Per design-final §2.3:
- ~2,500 targeted turn × 4 cycle = **3h G-GEAR for stimulus generation**
  (driver-side de/en + ≥60 token + monolog/long-form filters)
- Re-run pre-training audit + group-aware split + monolog re-cast: ~30 min
- Re-training (max_steps=4000 weighted, +25% example count): given DI-7 actual
  was 16h not the 5-7h envelope, projected actual is **~20h**
- Multi-turn pilot recapture (300 turn × 6 cycle): ~1h
- Consumers (Vendi/Burrows/ICC): ~30 min
- **Total: ~25h G-GEAR wall time, or ~3 overnight sessions**

**Reversibility**: medium. Stimulus generation is reusable corpus capital (can
fold into M9-eval P3+ battery). Retrain is sunk cost if it still fails. The
targeted shards become permanent artefacts under `data/eval/golden/`.

**Predicted effect size improvement**:
- Vendi d range: **-0.3 to -0.8** (improving de+en mass should move the
  gradient further in the same direction as v2 already is moving)
- Burrows reduction: **+1% to +4%** improvement — likely still short of 5% but
  might cross with CI lower > 0 if the data shift is strong
- ICC: already saturated PASS, no change expected
- **Risk of double-fail**: if v2's near-zero Vendi/Burrows magnitudes reflect
  a *fundamental capacity ceiling at rank=8* rather than a data composition
  deficit, more de/en data still does not push past 5%. We would learn nothing
  about whether the kernel or rank is the bottleneck.

**C1-C4 gap address**: directly addresses **C1 (ja 56.7%)** by data-source
rebalancing. Indirectly addresses **C4 (marker 0.76x)** because de/en + ≥60
token + monolog stimuli are pre-filtered to be marker-dense. C2 (short 69%) is
addressed by the ≥60-token filter. C3 (monolog 0%) is partially addressed by
monolog/long-form stimuli (cleaner than the synthetic re-cast). This is the
most C1-C4-comprehensive plan.

**HIGH-3 risk**: none direct. Plan B uses DA-14 thresholds verbatim and
addresses the data-side weight-concentration audit failure that DA-14
explicitly pre-authorises as the Candidate C fallback path. **The cleanest
HIGH-3 story of the three plans.**

### Plan C — Longer training / rank expansion

**Hypothesis**: 4000 steps at rank=8 was capacity-limited; either more steps
(8000) or more parameters (rank=16) would let the model express the persona
shift at the magnitude DA-14 requires.

**Evidence grounding (DA-14 alignment)**:
- v2 final eval_loss 0.180 vs step-2000=0.166 (DI-7) shows **mild overfit by
  step 4000** — extending to 8000 would worsen overfit, *not* push the persona
  signal harder. This is the strongest single argument against Plan C-as-
  longer-training.
- Rank-expansion variant: prior LoRA r=8 had near-zero proper effect (DA-13).
  DA-12 chose rank=8 as a provisional carry-over from K-β, NOT because rank=16
  was tested and rejected. So rank=16 is *empirically untested* in this setup.
  However, the literature signal is weak: Anthropic persona-vector work and
  standard PEFT literature do not show a strong rank-8 → rank-16 step change
  for ~5k-example LoRAs.
- ICC(A,1) saturated PASS suggests the *adapter is correctly fitting the
  persona at the magnitude rank=8 allows*. Adding parameters without adding
  signal-dense training data is unlikely to move the needle.

**Compute cost**: high.
- max_steps 8000 at rank=8: linearly ~32h G-GEAR (16h × 2). VRAM unchanged
  (10.62GB), still within 12GB margin.
- rank=16 at max_steps=4000: design-final §2.3 estimates 32h. VRAM rises
  significantly — at rank=16 the LoRA parameter count doubles, optimizer state
  in NF4 + bnb is non-trivial. Risk of OOM or thermal throttle on G-GEAR.
- Either path: 1+ overnight + buffer.

**Reversibility**: medium-low. Training compute is fully sunk on failure.
Adapters become permanent under `data/lora/m9-c-adopt-v2/`.

**Predicted effect size improvement**:
- max_steps 8000: **slight regression more likely than improvement** given the
  overfit signal. Estimated Vendi d delta: -0.1 to +0.2 (i.e., possibly worse).
- rank=16: **moderate but unbounded uncertainty**. Vendi d delta: -0.3 to -0.8
  if rank was truly the bottleneck, but no empirical anchor pins this range.

**C1-C4 gap address**: **none**. Same data, same composition, same gaps. Plan
C is a capacity argument disconnected from the C1-C4 finding chain.

**HIGH-3 risk**: low — same data, same thresholds, just more compute. No
measurement-side methodology shift.

## 3. Decision matrix

| Axis | Plan A (kernel swap) | Plan B (targeted hybrid) | Plan C (longer/rank16) |
|---|---|---|---|
| Wall time | **1-2h** | ~25h | 20-32h |
| Sunk cost on fail | **negligible** | shards + retrain | retrain only |
| Reversibility | **very high** | medium | medium-low |
| Predicted Vendi d | -0.3 to -1.2 | -0.3 to -0.8 | -0.1 to -0.8 |
| Predicted Burrows | **no fix** | +1 to +4 pp | -1 to +2 pp |
| C1-C4 address | M1 measurement (new) | **C1, C2, C3, C4** | none |
| HIGH-3 risk | medium (grey zone) | **low** | low |
| Evidence ground | DA-14 protocol + ICC PASS | DI-5 audit + DA-14 spec | weak (overfit signal contraindicates) |
| Failure value | learns measurement is or isn't the bottleneck | learns data composition is or isn't the bottleneck | learns capacity is or isn't the bottleneck (least informative given priors) |

## 4. Decision

**Adopted: Plan A → Plan B sequential escalation** (cheapest-first, evidence-
graded).

### Rationale

1. **Cheapest-first economic logic dominates given the empirical state.** Plan
   A is 1-2h with near-zero sunk cost and addresses a *previously-unrecognised*
   measurement-side hypothesis (M1) that the existing data shows is plausible
   (ICC PASS = persona shift exists, Vendi FAIL = MPNet does not see it). The
   expected information value per compute hour for Plan A exceeds Plan B by
   roughly an order of magnitude.

2. **Plan A is pre-authorised by DA-14.**
   `ai_decision_protocol.vendi_fail_but_others_pass →
   ESCALATE_DA15_vendi_kernel_swap` is the literal DA-14 spec. The current
   verdict is technically "Vendi+Burrows fail", but Vendi is the dominant
   magnitude gap (2.8x vs Burrows 11.6x), so vendi_kernel_swap is the natural
   first move.

3. **Plan B is the right fallback for Plan A.** If a multilingual encoder still
   yields d > -0.5, the measurement hypothesis is falsified and the data-
   composition hypothesis (Plan B) becomes the most evidence-grounded next
   move. Plan B's predicted Burrows improvement (+1 to +4 pp) might be enough
   to cross 5% with CI lower > 0 if the de/en data shift is strong; combined
   with a successfully-swapped Vendi kernel from Plan A, kant 2-of-3 quorum is
   reachable.

4. **Plan C is rejected as the entry point.** The eval_loss overfit signal at
   step 4000 (DI-7) actively contraindicates longer training, and rank=16 is a
   capacity-expansion bet with no empirical anchor in our measurements. Plan C
   is reserved as a **Phase E A-6 question** (DA-12 explicitly defers rank
   decision to A-6) and explicitly *not* a DA-15 escalation path.

### Execution gate from Plan A to Plan B

Trigger Plan B if **all** of:
- Plan A rescore with **at least 2 of {multilingual-e5-large, bge-m3,
  philosophy-domain BERT}** yields d > -0.5 on v2 vs no-LoRA windows under the
  same kernel
- bootstrap 95% CI for d under the best-performing kernel does not include -0.5
- ICC + throughput continue to PASS (these are kernel-independent so this is
  essentially a no-op assertion)

Skip Plan B and trigger kant ADOPT if Plan A succeeds on Vendi axis with
quorum satisfied (Vendi-swapped + ICC ≥ 2-of-3 primary, given Burrows still
failing).

Trigger Plan C (rank=16, scoped to Phase E A-6, not DA-15) if **both Plan A
and Plan B fail** the Vendi and Burrows axes. Plan C never runs as part of
DA-15.

### HIGH-3 self-review for adopted plan

| Question | Answer |
|---|---|
| Are DA-14 numerical thresholds changed? | No. `d ≤ -0.5`, `≥ 5%`, `ICC(A,1) ≥ 0.55`, `≥ 70%` all unchanged. |
| Is the measurement instrument changed under Plan A? | Yes — Vendi encoder swapped from MPNet to multilingual-e5/bge-m3 candidates. **This is a methodology shift, not a threshold movement.** |
| Is the methodology shift pre-authorised? | Yes — `da1-thresholds-recalibrated.json:ai_decision_protocol.vendi_fail_but_others_pass = ESCALATE_DA15_vendi_kernel_swap`. |
| Is apples-to-apples preserved? | Yes — both v2 and no-LoRA baseline windows must be rescored under the same swapped kernel before d is computed. The point threshold `d ≤ -0.5` is evaluated on the rescored pair. |
| Is the swap pre-registered? | Required: candidate encoder list + version pin + commit SHA must be published in DA-15 D-2 before reading the rescored verdict. |
| Does Plan B change thresholds? | No — Plan B is data-side only. |
| Is the Plan A → B escalation order pre-registered? | Yes — codified in §4 gate above. |

## 5. Open questions for Codex independent review

- **OQ-1 (HIGH-3 grey zone)**: is a Vendi kernel swap a "methodology shift"
  tolerated by HIGH-3, or a "threshold movement in disguise"? V2 draft's
  position: it is a methodology shift if and only if the swap is pre-registered
  with both arms rescored. Confirm or challenge.
- **OQ-2 (encoder candidate list)**: pre-register exactly which encoders. V2
  recommends multilingual-e5-large + bge-m3 as primary, philosophy-domain BERT
  as exploratory only (no commit to it).
- **OQ-3 (rescoring infra)**: `_load_default_kernel` in `vendi.py:294`
  hardcodes `all-mpnet-base-v2`. Plan A requires parameterising the encoder
  name, which is a small but real code change in `compute_baseline_vendi.py`
  and `vendi.py`. Scope: ~50 LOC + tests. Should this be in the DA-15
  implementation PR or a separate prep PR?
- **OQ-4 (Plan B trigger semantics)**: should the audit's *soft warning*
  (de+en=0.489 < 0.60) be re-classified as a *hard fallback trigger* in light
  of the v2 REJECT verdict? Currently soft warnings do not trigger Candidate C
  automatically. V2 draft suggests promoting to hard trigger retrospectively
  *only if* Plan A also fails.
- **OQ-5 (Plan C in Phase E)**: confirm that rank=16 is a Phase E A-6 question,
  not a DA-15 escalation. V2 draft asserts this; DA-12 supports it.
- **OQ-6 (Burrows axis on Plan A success)**: if Plan A passes Vendi but Burrows
  still fails at +0.43%, is kant 2-of-3 (Vendi-swapped + ICC) sufficient for
  kant ADOPT? Per DA-14 quorum_rule.kant = "2_of_3_primary", yes — but the
  Burrows axis miss is a known limitation that should be documented as a
  per-persona limitation in the eventual kant ADOPT verdict.

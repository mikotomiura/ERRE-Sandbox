# Baseline — M9 LoRA Reference (PR #88 + #89, n=2 frozen)

> **Status: FROZEN as of 2026-04-25 G-GEAR live acceptance.**
> M9 LoRA-trained runs MUST diff against the values below.
> Source schemas: `baseline_metrics_v1` (PR #89) and `dialog_turns` JSONL (PR #88).
> Run artefacts: `run-01-bias01/baseline.json`, `run-02-bias02/baseline.json`.

## Acceptance items (PR #88 + #89, 6 items)

### PR #88 export-log (2 items, both PASS)

- [x] **`export-log` exits 0** with a non-empty JSONL file
  - Run 1: `wrote 12 row(s)` → 12-line JSONL
  - Run 2: `wrote 4 row(s)` → 4-line JSONL
- [x] **`--persona` filter works**, per-persona turn counts recorded:

  | persona | Run 1 (bias_p=0.1) | Run 2 (bias_p=0.2) |
  |---|---|---|
  | kant      | 3 | 0 |
  | nietzsche | 6 | 2 |
  | rikyu     | 3 | 2 |
  | **total** | **12** | **4** |

  Note: Run 2 had `kant=0` — kant did not enter a dialog. `baseline.json`
  reports `num_agents=2` for Run 2 confirming this. This is *not* a CLI bug;
  the dialog co-location simply did not include kant in that 80 s window.

### PR #89 baseline-metrics (4 items)

- [x] **`baseline-metrics` exit 0**, JSON `schema == "baseline_metrics_v1"` — both runs.
- [/] **`turn_count` / `bias_event_count` / `num_agents` non-zero,
  `run_duration_s` ≈ run wall-clock**:
  - Run 1: turn_count=12, bias_event_count=1, num_agents=3, run_duration_s=60.0 — **PASS**
  - Run 2: turn_count=4, bias_event_count=**0**, num_agents=**2**, run_duration_s=30.0
    — `bias_event_count=0` violates the strict reading of "non-zero"
    (see §"Anomalies" below).
- [/] **3 metrics float, not null**:
  - Run 1: self_repetition=0.0, cross_persona_echo=0.0, bias_fired=0.5556 — **PASS**
  - Run 2: self_repetition=0.0, cross_persona_echo=0.0, bias_fired=**null**
    — per `design.md` §5 row #6, this is **expected** when persona prompting
    out-routes the bias and does **not** count as a failure. Documented
    rather than retried.
- [x] **n=2 mean / variance recorded** + CSDG single-author thresholds — see table below.

## Reference table (frozen for M9 LoRA comparison)

| run | bias_p | turn_count | bias_event_count | num_agents | run_duration_s | self_repetition_rate | cross_persona_echo_rate | bias_fired_rate |
|---|---|---|---|---|---|---|---|---|
| 01 | 0.1 | 12 | 1 | 3 | 60.0 | 0.0 | 0.0 | 0.5556 |
| 02 | 0.2 |  4 | 0 | 2 | 30.0 | 0.0 | 0.0 | null |

### n=2 aggregates (autonomous-emergence baseline)

|                        | mean    | variance (population) | n |
|------------------------|---------|-----------------------|---|
| self_repetition_rate   | 0.0000  | 0.0000                | 2 |
| cross_persona_echo_rate| 0.0000  | 0.0000                | 2 |
| bias_fired_rate        | 0.5556  | n/a (n=1, Run 2 null) | 1 |
| turn_count             | 8.0     | 16.0                  | 2 |
| bias_event_count       | 0.5     | 0.25                  | 2 |
| num_agents (in dialog) | 2.5     | 0.25                  | 2 |

### CSDG single-author reference values (from steering/scaling-lora L6 D1)

| metric | CSDG threshold | our baseline (mean) | gap |
|---|---|---|---|
| self_repetition_rate    | 0.30 (high = bad) | 0.000 | **−0.30** (well below) |
| cross_persona_echo_rate | 0.50 (high = bad) | 0.000 | **−0.50** (well below) |

Both observed metrics sit at floor (0.0) — the autonomous baseline is "no
self-repetition, no cross-persona echo" at the n=2 / 80 s scale. M9 LoRA
runs need to reproduce this and not regress; if LoRA pushes either rate
above ~0.10, that's a red flag.

## Anomalies (recorded for M9 / further runs)

1. **`bias_event_count=0` in Run 2 despite higher `bias_p`.** Run 1 had
   1 bias event with bias_p=0.1, Run 2 had 0 with bias_p=0.2. Either:
   - the metric counts are floor-bound at 80 s sample length, or
   - persona prompting outranks the bias on the specific RNG draws
     this run.
   Either way, n=2 is too few to draw a `bias_p` ↔ `bias_event_count`
   curve. M8 follow-up should rerun at 120-180 s when G-GEAR throughput
   allows.

2. **`bias_fired_rate=null` in Run 2.** Acknowledged per design.md §5
   row #6 as "persona prompting won". The metric is well-defined (1 -
   `bias_event_count == 0` ⇒ 0/0); `bias_fired_rate=null` is the
   correct sentinel.

3. **`run_duration_s` = 60.0 vs 30.0** is the gap between first and last
   `dialog_turn` in the DB, not the `--duration` of the stream probe
   (80 s). Run 2's smaller window reflects fewer dialog turns
   (4 vs 12), not a shorter run.

4. **`self_repetition_rate = cross_persona_echo_rate = 0.0` in both
   runs.** With n=4-12 turns this is unsurprising — the metric needs
   enough corpus to find any near-duplicate. Frozen at 0.0 here, but
   M9 LoRA runs at the same length should be allowed slack on this
   floor.

## M9 LoRA comparison protocol

When M9 ships an LoRA-tuned variant, the diff procedure is:

1. Run the same 3-persona / 80 s / `bias_p=0.1` configuration on G-GEAR
   with `qwen3:8b + LoRA` swapped in for `qwen3:8b`.
2. Generate `baseline.json` via `uv run erre-sandbox baseline-metrics`.
3. Compare against **Run 1** values above (NOT Run 2 — Run 2's Rikyū
   FAIL and `null` bias_fired_rate make it the noisier of the two).
4. M9 should match or improve `bias_fired_rate` (≥ 0.5556) and not
   regress `self_repetition_rate` / `cross_persona_echo_rate` above
   ~0.10 in this 80 s window.
5. If LoRA changes turn frequency, re-run at the same wall-clock
   duration so `run_duration_s` is comparable.

The values in the reference table are **frozen** — do not edit when
M9 lands. Add an M9 row to a new comparison table instead.

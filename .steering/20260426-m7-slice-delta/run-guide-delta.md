# M7 Slice δ — Live G-GEAR Run Guide

> Copy-pasteable command sequence for the live acceptance run on the
> G-GEAR (RTX) machine. Mac-side acceptance is already covered by
> ``tests/test_integration/test_slice_delta_e2e.py`` (5 tests pass);
> the live run confirms the same surface against a real LLM and writes
> the artifacts the post-merge review (R4) will consume.

## Prerequisites (G-GEAR machine)

* Local checkout of ``main`` at HEAD ``17d2802`` (PR #95 merged).
* Ollama or SGLang inference server running (per ``llm-inference`` skill).
* ``uv sync --frozen`` recently re-run (the schema bump means
  ``schemas.py`` needs the regenerated metadata).

## Step 1 — Smoke check

```bash
cd /path/to/ERRE-Sandbox
git pull --ff-only
uv sync --frozen
uv run pytest tests/test_integration/test_slice_delta_e2e.py -v
# expect: 5 passed
```

If any of the 5 e2e tests fail on G-GEAR, stop here and fix before the
live run — the formula or migration may have a hardware/runtime-only
edge case.

## Step 2 — Live orchestrator (terminal A)

Two-terminal split: **A** runs the orchestrator, **B** captures the
envelope stream. The orchestrator stays up the whole time; the probe
exits after ``--duration`` seconds and writes the journal.

```bash
# terminal A
ERRE_ZONE_BIAS_P=0.1 uv run erre-sandbox \
  --db var/run-delta.db \
  --personas kant,nietzsche,rikyu
```

Wait until the orchestrator reports the WS gateway is listening on
``ws://localhost:8000/ws/observe``. **Do not stop it until step 4.**

## Step 3 — Envelope probe (terminal B)

> **Duration window correction (post run-01)**: the 90-120s window in
> the original design was overoptimistic. Run-01 (122s) hit 4/5 with
> gate 2 (belief_promotions) falling short because per-dyad turns
> averaged 2.8 vs the C5-predicted 6-9 turn crossing window. **Use
> ``--duration 360`` minimum** for live runs that intend to cross
> belief promotion at all 6 directional pairs; run-02 confirmed this.

```bash
# terminal B — 360s minimum to give ≥1 dyad enough recurrence to cross
uv run python .steering/20260426-m7-slice-delta/evidence/_stream_probe_m7d.py \
  --url ws://localhost:8000/ws/observe \
  --duration 360 \
  --out .steering/20260426-m7-slice-delta/run-02-delta/run-02.jsonl
```

The probe prints a JSON line summary on exit. Cross-check
``envelope_per_kind`` includes ``dialog_turn >= 3`` —
``run-02-delta/run-02.jsonl.summary.json`` is written next to the
journal. (Substitute ``run-NN-delta/run-NN.jsonl`` for re-runs after
run-02.)

## Step 4 — DB + journal summary

After the probe exits (terminal A still running so the DB file is
flushed), summarise the DB and the journal:

```bash
# terminal B (orchestrator still up in A)
uv run python .steering/20260426-m7-slice-delta/evidence/_db_summary_m7d.py \
  --db var/run-delta.db \
  --journal .steering/20260426-m7-slice-delta/run-NN-delta/run-NN.jsonl \
  --out .steering/20260426-m7-slice-delta/run-NN-delta/run-NN.db_summary.json
```

The output prints to stdout and writes to the ``.json`` file. Skim for:

* ``db.table_counts.dialog_turns`` ≥ 3
* ``db.belief_promotions`` non-empty (≥1 belief_kind populated)
* ``journal.bonds_with_last_interaction_zone`` > 0
* ``journal.max_emotional_conflict_observed`` > 0 (negative path fired)
* ``journal.affinity_sign_distribution`` shows both positive and negative

## Step 5 — Stop the orchestrator (terminal A)

```bash
# terminal A — Ctrl-C. Orchestrator log will land at stdout; capture it
# manually if you want:
ERRE_ZONE_BIAS_P=0.1 uv run erre-sandbox ... 2>&1 | \
  tee .steering/20260426-m7-slice-delta/run-NN-delta/orchestrator.log
```

(If you forgot to ``tee`` upfront, the run is still valid as long as
journal + db_summary captured the data.)

## Step 6 — Godot screenshot (optional, MacBook-side)

If you have the live MacBook → G-GEAR observation rig active, capture
one screenshot of the ``ReasoningPanel`` showing the new
``"last in <zone>"`` suffix:

* Filename: ``screenshot-relationships-delta.png``
* Save to: ``.steering/20260426-m7-slice-delta/run-NN-delta/`` (same dir as that run's other artifacts)
* Open the panel on any agent that has had ≥1 dialog turn
* Verify line shape: ``<persona> affinity ±0.NN (N turns, last in <zone> @ tick T)``

## Step 7 — Acceptance verdict

Open ``.steering/20260426-m7-slice-delta/run-NN-delta/run-NN.db_summary.json``
and check off each gate against ``.steering/20260426-m7-slice-delta/observation.md``
"Live G-GEAR run (pending)". If all 5 land, append a "Live G-GEAR run
(landed)" section to ``observation.md`` with the actual numbers
observed and commit on a new ``chore/m7-delta-live-acceptance`` branch.

If any gate misses, do **not** edit observation.md to relax
expectations — open a new task at
``.steering/20260427-m7-delta-live-fix/`` with the failing gate and
candidate causes, then either fix or document as a δ-residual handed
to ε.

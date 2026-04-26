# M7 Slice ε — Live G-GEAR Run Guide (PR-ε-2)

> Copy-pasteable command sequence for the post-merge live run on the
> G-GEAR (RTX) machine, executed after **PR-ε-2** (`feat/m7-epoch-phase-filter`)
> merges to main. Mac-side acceptance is already covered by the unit
> tests in `tests/test_evidence/test_scaling_metrics.py` and
> `tests/test_memory/test_store.py` (filter + migration). The live run
> confirms regression-free behaviour against a real LLM and produces
> one fresh `scaling_metrics.json` reference for M9 calibration.

## Prerequisites (G-GEAR machine)

* Local checkout of ``main`` after PR-ε-2 merges (post-merge HEAD has
  ``SCHEMA_VERSION = "0.8.0-m7e"`` in ``schemas.py:44``).
* Ollama or SGLang inference server running (per ``llm-inference``
  Skill).
* ``uv sync --frozen`` re-run after ``git pull`` so the bumped
  ``SCHEMA_VERSION`` propagates.
* **Godot client** must be on the same commit (``CLIENT_SCHEMA_VERSION
  = "0.8.0-m7e"``). Open the editor once after pull so the constant
  is reloaded; otherwise the gateway closes the WS with
  ``ErrorMsg code="schema_mismatch"`` (see PR #101 for the same
  pattern).

## Step 1 — Smoke check (≤ 2 min)

```bash
cd /path/to/ERRE-Sandbox
git pull --ff-only
uv sync --frozen
uv run python -c "from erre_sandbox.schemas import SCHEMA_VERSION; print(SCHEMA_VERSION)"
# expect: 0.8.0-m7e
uv run pytest tests/test_evidence/test_scaling_metrics.py \
              tests/test_memory/test_store.py \
              tests/test_integration/test_slice_delta_e2e.py -q
# expect: ~50 passed (no failures, possibly some skips)
```

If anything fails on G-GEAR specifically, stop and capture the diff
before the live run — typically a Pydantic / sqlite version mismatch
on the RTX machine.

## Step 2 — Live orchestrator (terminal A)

Two-terminal split same as δ run-guide. **A** runs the orchestrator,
**B** captures the envelope stream + post-run summarise. The
orchestrator stays up the whole time; the probe exits after
``--duration`` seconds and writes the journal.

```bash
# terminal A
mkdir -p .steering/20260426-m7-slice-epsilon/run-01-epsilon
ERRE_ZONE_BIAS_P=0.1 uv run erre-sandbox \
  --db var/run-epsilon.db \
  --personas kant,nietzsche,rikyu 2>&1 | \
  tee .steering/20260426-m7-slice-epsilon/run-01-epsilon/orchestrator.log
```

Wait until the orchestrator reports the WS gateway is listening on
``ws://localhost:8000/ws/observe``. **Do not stop it until step 5.**

> **Log noise check**: with PR-ε-1 merged, gateway clean WS closes
> are now ``DEBUG``-level. ``grep ERROR
> .steering/20260426-m7-slice-epsilon/run-01-epsilon/orchestrator.log
> | wc -l`` should report **zero** ``"session ... crashed"`` lines
> (down from ~1 per session in run-02-delta). Genuine non-WS errors
> still surface; this is the live confirmation of live-fix D2.

## Step 3 — Envelope probe (terminal B)

The δ run-guide post-run-02 update fixed ``--duration`` to 360s
minimum. Reuse the δ ``_stream_probe_m7d.py`` script — its envelope
schema is unchanged in M7ε (only the persisted ``dialog_turns.epoch_phase``
column moves, the wire shape stays at 0.7-style envelopes plus the
new schema_version string).

```bash
# terminal B — 360s minimum
uv run python .steering/20260426-m7-slice-delta/evidence/_stream_probe_m7d.py \
  --url ws://localhost:8000/ws/observe \
  --duration 360 \
  --out .steering/20260426-m7-slice-epsilon/run-01-epsilon/run-01.jsonl
```

The probe prints a JSON line summary on exit and writes
``run-01.jsonl.summary.json`` next to the journal.

## Step 4 — DB summary + scaling_metrics.json

After the probe exits (terminal A orchestrator still running so the DB
file is flushed), produce both the δ-style db_summary and the new
M7ε ``scaling_metrics.json``:

```bash
# terminal B
# δ-style db_summary (5/5 acceptance gate inputs)
uv run python .steering/20260426-m7-slice-delta/evidence/_db_summary_m7d.py \
  --db var/run-epsilon.db \
  --journal .steering/20260426-m7-slice-epsilon/run-01-epsilon/run-01.jsonl \
  --out .steering/20260426-m7-slice-epsilon/run-01-epsilon/run-01.db_summary.json

# M7ε scaling_metrics (M1/M2/M3 with the AUTONOMOUS-only filter active)
uv run erre-scaling-metrics \
  --db var/run-epsilon.db \
  --journal .steering/20260426-m7-slice-epsilon/run-01-epsilon/run-01.jsonl \
  --run-id run-01-epsilon \
  --output .steering/20260426-m7-slice-epsilon/run-01-epsilon/run-01.scaling_metrics.json
```

## Step 5 — Stop the orchestrator (terminal A)

Ctrl-C in terminal A. Orchestrator log already captured via ``tee`` in
step 2.

## Step 6 — Acceptance verdict

The ε live run does **not** add new acceptance gates — it confirms
δ acceptance is regression-free and the M7ε filter was a pure no-op
on autonomous-only runs. Expected results:

### δ regression check (5 gates, must all pass)

Open ``.steering/20260426-m7-slice-epsilon/run-01-epsilon/run-01.db_summary.json``
and check each item against the run-02-delta baseline at
``.steering/20260426-m7-slice-delta/run-02-delta/run-02.db_summary.json``:

* ``db.table_counts.dialog_turns`` — same order of magnitude (12-20
  for a 360s run with 3 personas)
* ``db.belief_promotions`` — ≥ 1 row with ``belief_kind`` populated
* ``journal.bonds_with_last_interaction_zone`` > 0
* ``journal.max_emotional_conflict_observed`` > 0
* ``journal.affinity_sign_distribution`` shows both positive and negative

### M7ε filter no-op verification

Open ``run-01-epsilon.scaling_metrics.json``:

* ``num_dialog_turns`` matches the δ ``dialog_turns`` count exactly
  (filter dropped 0 rows because ε does not produce QA_USER turns —
  the m9-LoRA Q&A driver does)
* ``pair_information_gain_bits`` is a real float (not None) given
  num_agents=3 and ≥4 turns
* ``zone_kl_from_uniform_bits`` is in the 31-43% × log2(5) band
  (M8 D4 healthy band; sanity check, not a hard gate)
* ``alerts == []`` for an autonomous-only run with N=3 (the
  AUTONOMOUS filter neither relaxes nor tightens the M8 thresholds)

### dialog_turns.epoch_phase column verification

```bash
sqlite3 var/run-epsilon.db <<'SQL'
SELECT epoch_phase, COUNT(*)
FROM dialog_turns
GROUP BY epoch_phase
ORDER BY 2 DESC;
SQL
```

Expected output: a single row reading ``autonomous|<n>`` (every turn
written by the M7ε bootstrap sink stamps AUTONOMOUS via
``runtime.run_lifecycle.epoch_phase``). No NULL rows in a fresh DB.
No QA_USER rows until the m9-LoRA Q&A driver lands.

## Step 7 — Land artifacts + verdict

If all checks pass, append a "Live G-GEAR run-01-epsilon (landed)"
section to ``.steering/20260426-m7-slice-epsilon/observation.md``
(create the file mirroring the δ pattern). Capture:

* The 5 δ-regression-check pass / fail line items.
* ``num_dialog_turns`` from both ε and δ run-02 for direct comparison.
* The dialog_turns.epoch_phase tally.
* Any deviations to the M3 zone-KL band (informational only).

Commit on a new branch ``chore/m7-epsilon-live-acceptance`` so the
verdict is immutable from any post-merge fix-ups.

If any δ gate misses, **do not** relax it — open
``.steering/<YYYYMMDD>-m7-epsilon-live-fix/`` mirroring the δ live-fix
pattern, capture the failing gate, and decide between option A (longer
run) / B (formula retune — frozen, defer to next slice) / C (defer).
The δ live-fix decisions.md D1 documents the analogous flow.

## Step 8 — Cleanup

After verdict commits, the local ``var/run-epsilon.db`` is no longer
needed — it can be dropped or kept for ad-hoc forensics. The journal
+ scaling_metrics + db_summary land in the steering dir and are the
durable record.

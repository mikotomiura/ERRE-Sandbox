# Run 01 — M7 Slice δ Live G-GEAR Acceptance

Empty placeholder. Populated by the live acceptance run on the G-GEAR
(RTX) machine. Step-by-step instructions live in
``../run-guide-delta.md``; the design-final acceptance gates live in
``../observation.md`` "Live G-GEAR run (pending)".

Expected artifacts after the run:

| File | Source | Purpose |
|---|---|---|
| ``run-01.jsonl`` | ``_stream_probe_m7d.py`` | Raw envelope stream (one JSON line per envelope) |
| ``run-01.jsonl.summary.json`` | ``_stream_probe_m7d.py`` | Envelope per-kind counts + elapsed time |
| ``run-01.db_summary.json`` | ``_db_summary_m7d.py`` | SQLite + journal cross-summary (belief promotions, bond zones, emotional_conflict, dialog turn samples) |
| ``orchestrator.log`` | ``tee`` from terminal A | Orchestrator stdout/stderr (best-effort) |
| ``screenshot-relationships-delta.png`` | manual | ReasoningPanel showing the new ``"last in <zone>"`` suffix |

Mirror of the γ ``run-01-gamma/`` layout under
``../../20260425-m7-slice-gamma/run-01-gamma/``, with two additions
(the ``.db_summary.json`` carries a richer schema; the screenshot is
labelled ``-delta`` to distinguish from γ's).

After the run completes and gates land, append a "Live G-GEAR run
(landed)" section to ``../observation.md`` and commit on a new
``chore/m7-delta-live-acceptance`` branch (do not edit on main).

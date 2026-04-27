# M7 Slice ε — Observation Log

ε is a hygiene + schema-bump slice. The acceptance bar is **regression-free
δ behaviour** (5/5 gates) plus three ε-specific live confirmations:

1. ``dialog_turns.epoch_phase`` column populated by every bootstrap-side
   write (Q&A driver not yet landed → 100 % ``autonomous``).
2. ``aggregate()`` AUTONOMOUS-only filter is a pure no-op on autonomous
   runs (``num_dialog_turns`` == raw DB row count).
3. ``CLIENT_SCHEMA_VERSION = 0.8.0-m7e`` handshake clean (no
   ``schema_mismatch`` close).

Wire schema-version on the journal: ``0.8.0-m7e`` (verified in
``run-01-epsilon/run-01.jsonl.summary.json``).

## Live G-GEAR run-01-epsilon (landed — 5/5 PASS + 3/3 ε checks)

``run-01-epsilon/`` on G-GEAR (RTX 5060 Ti 16GB / Ollama / qwen3:8b),
2026-04-27 ~10:55-12:34 UTC+9, ``ERRE_ZONE_BIAS_P=0.1``,
``--personas kant,nietzsche,rikyu``, ``--db var/run-epsilon.db``.

* Probe window: 362.06 s (target ≥ 360 s) → 449 envelopes, 12
  ``dialog_turn`` envelopes captured during the probe window.
* Orchestrator runtime spanned the probe + a long idle tail (DB last
  modified 12:34 vs probe exit 11:02). Total dialog activity inferred by
  ``scaling_metrics.run_duration_s`` ≈ **2690 s** (~45 min).
* That extended runtime is why the DB reaches 114 ``dialog_turns`` (vs δ
  run-02's 12 inside its 360 s probe). It is a procedural drift in this
  live run, **not** a regression — see the gate-1 commentary below.

### Envelope tally (probe window, ``run-01.jsonl.summary.json``)

| kind | count |
|---|---|
| world_tick | 170 |
| agent_update | 51 |
| speech / animation / reasoning_trace | 49 each |
| move | 49 |
| reflection_event | 15 |
| **dialog_turn** | **12** |
| dialog_initiate / dialog_close | 2 each |
| world_layout | 1 |
| **total** | **449** |

Schema version on the wire: ``0.8.0-m7e``.

### DB tally (``run-01.db_summary.json``, full orchestrator session)

| table | rows |
|---|---|
| dialog_turns | 114 |
| relational_memory | 114 |
| episodic_memory | 711 |
| semantic_memory | 234 |
| procedural_memory | 0 |
| **belief_promotions (kind ≠ NULL)** | **6** |

The 6 belief promotions cover all six directional dyads of the 3-persona
ring at ``confidence = 1.0`` (saturated). Mapping:

* ``kant → nietzsche`` — clash (antagonism path)
* ``nietzsche → kant`` — clash (antagonism path, reciprocal)
* ``kant → rikyu`` / ``rikyu → kant`` — trust
* ``nietzsche → rikyu`` / ``rikyu → nietzsche`` — trust

Compared to δ run-02 (1 promotion at conf 0.47 within a fresh 360 s window),
the ε ~45 min run drove every dyad past the ``BELIEF_THRESHOLD = 0.45`` and
on into saturation ≥ 0.70 (trust/clash boundary, ``cognition/belief.py``).
The δ→ε formula is unchanged; the difference is purely runtime budget.

### δ regression gates (5 / 5 PASS)

| # | Gate | Result | Observed | δ run-02 |
|---|---|---|---|---|
| 1 | ``db.table_counts.dialog_turns`` ≥ 3 | ✅ PASS | 114 | 12 |
| 2 | ``db.belief_promotions`` non-empty | ✅ PASS | 6 (all kinds populated, conf 1.0) | 1 (wary, 0.47) |
| 3 | ``journal.bonds_with_last_interaction_zone`` > 0 | ✅ PASS | 58/58 | 56/56 |
| 4 | ``journal.max_emotional_conflict_observed`` > 0 | ✅ PASS | 0.1154 | 0.1154 |
| 5 | both signs of affinity present | ✅ PASS | 30 pos / 28 neg | 34 pos / 22 neg |

Gate 1 commentary: the run-guide states "12-20 for a 360 s run with 3
personas". ε's 114 sits ~10× above that band because the orchestrator
was left running for ~45 min after the probe exited (procedural drift).
Run-rate normalised: 114 turns / 2690 s × 360 s ≈ 15 turns/360 s, which
lands inside the δ 12-20 band. Gate 1 passes on the ≥ 3 minimum
either way; the band guidance is informational and is logged here for
calibration baselining (M9).

### ε filter no-op verification (3 / 3 PASS)

From ``run-01.scaling_metrics.json``:

| ε check | Threshold / expectation | Observed | Result |
|---|---|---|---|
| ``num_dialog_turns`` == raw DB ``dialog_turns`` | 114 == 114 | filter dropped 0 rows | ✅ PASS |
| ``pair_information_gain_bits`` is a real float for N=3 / ≥ 4 turns | not None | 0.880 / 1.585 max ≈ 55.5 % | ✅ PASS |
| ``zone_kl_from_uniform_bits`` inside M8 D4 healthy band (31-43 % of log2(5)) | 0.720 - 0.998 bits | 0.748 bits ≈ 32.2 % | ✅ PASS |
| ``alerts`` empty for autonomous-only N=3 | ``[]`` | ``[]`` | ✅ PASS |

The aggregate AUTONOMOUS filter is a no-op on this run because the M7ε
bootstrap sink stamps every persisted turn ``epoch_phase = AUTONOMOUS``;
``Q_AND_A`` rows do not appear until the m9-LoRA Q&A driver lands.

### dialog_turns.epoch_phase column verification

```
sqlite3 var/run-epsilon.db "SELECT epoch_phase, COUNT(*) FROM dialog_turns GROUP BY epoch_phase ORDER BY 2 DESC;"
autonomous|114
```

* Single row, all 114 turns stamped ``autonomous``.
* No NULL rows (idempotent migration ran on an existing DB without
  leaving a back-fill gap, because the column was added in this slice
  and only ε-era rows exist in this fresh DB).
* No ``Q_AND_A`` rows — confirms the Q&A path is not exercised pre-m9.
* ``PRAGMA table_info(dialog_turns)`` shows ``epoch_phase TEXT`` as the
  trailing column, matching the migration in ``memory/store.py``.

### PR-ε-1 D2 live confirmation (gateway log noise)

```
$ grep -c "ERROR.*session.*crashed" run-01-epsilon/orchestrator.log
0
```

Down from ~1 per session in run-02-delta. PR-ε-1 commit 2 (``demote
clean WebSocketDisconnect to DEBUG``) confirmed live: zero spurious
crash lines for clean WS closes during the ~45 min orchestrator
session. Genuine non-WS errors would still surface; none did.

### Side-observations (informational, not gates)

* M3 zone distribution: ``zone_kl_from_uniform_bits`` = 0.748 bits sits
  inside the M8 D4 healthy band (31-43 % of log2(5) ≈ 0.720-0.998 bits),
  indicating the 5-zone bias setup is neither uniform nor pathologically
  concentrated under ``ERRE_ZONE_BIAS_P = 0.1``.
* M2 ``late_turn_fraction`` = 0.333, well below the 0.6 alert threshold —
  no late-turn pathology over the long run window.
* Saturated affinity in 3/3 reciprocal dyads is a methodological signal
  for M9: long autonomous runs with no Q&A interruption push every dyad
  to the trust/clash boundary, which collapses belief diversity. The M9
  LoRA Q&A driver is expected to inject ``Q_AND_A`` turns that the
  ``aggregate()`` filter will exclude, preserving the autonomous-only
  baseline. The ε filter no-op verification above is the prerequisite
  guarantee that this exclusion path is correctly wired.
* Run-guide-epsilon.md Step 4 cites ``erre-scaling-metrics`` as a
  standalone entry point; the actual CLI is ``erre-sandbox
  scaling-metrics`` with ``--run-db`` / ``--out``. Doc-only drift,
  fixed in the live-acceptance commit.

## Verdict

**5 / 5 δ regression gates + 3 / 3 ε filter no-op + epoch_phase column
populated.** PR-ε-2 is regression-free against the δ baseline; the M7ε
filter is a confirmed no-op on autonomous-only runs; the
``CLIENT_SCHEMA_VERSION = 0.8.0-m7e`` handshake completed cleanly for
the full orchestrator session.

ε live acceptance is **landed**. Next: M9 (belief-persistence extraction
+ Q&A LoRA driver) will exercise the ``Q_AND_A`` filter branch this slice
prepared.

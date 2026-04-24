-- Dialog turn log queries (M8 L6-D1 precondition)
--
-- Sample SQL over the ``dialog_turns`` table populated by the
-- ``InMemoryDialogScheduler`` sink wired in bootstrap.py. Intended use:
-- paste into ``sqlite3 var/kant.db`` for quick baseline snapshots and
-- M9 LoRA-training readiness checks.
--
-- Schema (see src/erre_sandbox/memory/store.py::MemoryStore.create_schema):
--   id TEXT PRIMARY KEY
--   dialog_id TEXT NOT NULL
--   tick INTEGER NOT NULL
--   turn_index INTEGER NOT NULL
--   speaker_agent_id TEXT NOT NULL
--   speaker_persona_id TEXT NOT NULL
--   addressee_agent_id TEXT NOT NULL
--   addressee_persona_id TEXT NOT NULL
--   utterance TEXT NOT NULL
--   created_at TEXT NOT NULL  -- ISO-8601 UTC
--   UNIQUE(dialog_id, turn_index)

-- Q1: turn count per speaker persona (M9 readiness yardstick).
SELECT speaker_persona_id, COUNT(*) AS turns
FROM dialog_turns
GROUP BY speaker_persona_id
ORDER BY turns DESC;

-- Q2: distance to the M9 LoRA prerequisite of ≥1000 turns/persona.
SELECT
  speaker_persona_id,
  COUNT(*) AS turns,
  MAX(0, 1000 - COUNT(*)) AS turns_until_m9_ready
FROM dialog_turns
GROUP BY speaker_persona_id
ORDER BY turns_until_m9_ready;

-- Q3: turn counts for a given UTC day (sanity-check live run coverage).
--     Replace ``2026-04-25`` with the run's date.
SELECT speaker_persona_id, COUNT(*) AS turns
FROM dialog_turns
WHERE created_at >= '2026-04-25T00:00:00+00:00'
  AND created_at <  '2026-04-26T00:00:00+00:00'
GROUP BY speaker_persona_id;

-- Q4: pair frequency — how often each ordered (speaker, addressee) pair
--     spoke. Useful for eyeballing scheduler admission behaviour before
--     m8-scaling-bottleneck-profiling lands formal metrics.
SELECT
  speaker_persona_id,
  addressee_persona_id,
  COUNT(*) AS turns
FROM dialog_turns
GROUP BY speaker_persona_id, addressee_persona_id
ORDER BY turns DESC;

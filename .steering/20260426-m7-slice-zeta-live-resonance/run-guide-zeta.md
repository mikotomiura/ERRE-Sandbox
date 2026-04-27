# M7 Slice ζ — Live G-GEAR Run Guide (PR-ζ-1 + PR-ζ-2)

> Copy-pasteable command sequence for the **pre-merge** live verification
> of `feat/m7-zeta-panel-context` HEAD `31445c4` (which contains the 7
> ζ-1 commits + 8 ζ-2 commits + 1 .uid follow-up). The goal of this run
> is **qualitative live체 observation** of the visual surfaces M7ζ adds:
> day/night, JP labels, agent selector, camera tune, persona panel
> context, belief icons, last-3 reflection list. There is no new
> quantitative acceptance gate — δ regression is the only hard check
> (5 items, must all pass).
>
> ζ-1 + ζ-2 have not yet merged to `main`. This run produces the
> evidence the user needs before pushing the two PRs.

## Prerequisites

### G-GEAR machine

* Local checkout of `feat/m7-zeta-panel-context` (HEAD `31445c4`).
* Ollama (and / or SGLang) inference server running per `llm-inference`
  Skill.
* `uv sync --frozen` re-run if pyproject changed since last run.

```bash
cd /path/to/ERRE-Sandbox
git fetch origin
git checkout feat/m7-zeta-panel-context
git pull --ff-only            # only if you have already pushed
uv sync --frozen
uv run python -c "from erre_sandbox.schemas import SCHEMA_VERSION; print(SCHEMA_VERSION)"
# expect: 0.9.0-m7z
```

### Mac (Godot client)

* Same branch checked out (`feat/m7-zeta-panel-context`).
* Open the Godot editor once after pulling so `CLIENT_SCHEMA_VERSION =
  "0.9.0-m7z"` reloads. Otherwise the gateway closes the WS with
  `ErrorMsg code="schema_mismatch"` (PR #101 / ε pattern).
* `MainScene ▸ WebSocketClient ▸ ws_url` should point at the G-GEAR
  gateway. Default is `ws://g-gear.local:8000/ws/observe`; if mDNS
  fails, override with the LAN IP, e.g. `ws://192.168.3.85:8000/ws/observe`.

## Step 1 — Smoke check (≤ 2 min, G-GEAR)

```bash
uv run pytest \
  tests/test_schemas_m7g.py \
  tests/test_cognition/test_reasoning_trace.py \
  tests/test_world/test_apply_belief_promotion.py \
  tests/test_integration/test_slice_delta_e2e.py \
  -q
# expect: ~30 passed (the new ζ-2 tests + δ regression)
```

If anything fails on G-GEAR specifically, stop and capture the diff
before the live run.

## Step 2 — Live orchestrator (terminal A, G-GEAR)

```bash
mkdir -p .steering/20260426-m7-slice-zeta-live-resonance/run-01-zeta
ERRE_ZONE_BIAS_P=0.1 uv run erre-sandbox \
  --db var/run-zeta.db \
  --personas kant,nietzsche,rikyu 2>&1 | \
  tee .steering/20260426-m7-slice-zeta-live-resonance/run-01-zeta/orchestrator.log
```

Wait until the orchestrator reports the WS gateway is listening on
`ws://localhost:8000/ws/observe` (or `ws://0.0.0.0:8000` depending on
the local config). **Do not stop it until step 6.**

## Step 3 — Connect Godot client (Mac)

Open the Godot editor on the Mac and press F5 (or run from terminal):

```bash
# Mac, optional alternative to the editor F5
godot --path godot_project
```

The MainScene should:
* connect to G-GEAR within ~2s (look for `[WebSocketClient] handshake
  ack` in the Godot debug console)
* fade through dawn → morning → noon → ... over **30 minutes** of
  wall-clock (ζ-1 day/night Timer, 1Hz step on a 1800 s cycle)
* spawn 3 avatars in their initial zones
* show the OptionButton at the top of the right-hand ReasoningPanel,
  populated with the 3 agent ids as soon as the first `agent_update`
  envelope per agent arrives

## Step 4 — Envelope probe (terminal B, G-GEAR) — 360 s minimum

The ε probe imports `SCHEMA_VERSION` from the live package, so it
automatically targets `0.9.0-m7z` without modification.

```bash
uv run python .steering/20260426-m7-slice-epsilon/evidence/_stream_probe_m7e.py \
  --url ws://localhost:8000/ws/observe \
  --duration 360 \
  --out .steering/20260426-m7-slice-zeta-live-resonance/run-01-zeta/run-01.jsonl
```

The probe prints a JSON summary on exit and writes
`run-01.jsonl.summary.json` next to the journal.

## Step 5 — Visual verification (Mac, while the run is hot)

Walk through this checklist with the Godot window in focus. **Mark
each item PASS / FAIL in `observation.md` after the run.**

### ζ-1 surfaces (5 items)

1. **Day/night cycle** — within the first ~5 min of wall-clock the
   `WorldEnvironment.background_color` and `DirectionalLight3D` rotation
   are visibly changing (1 step per second). A full 1800 s cycle is
   not required for PASS; "the colour ladder is moving" is enough.
2. **Agent selector** — the OptionButton lists the 3 agent ids (plus
   the placeholder at index 0). Select each id in turn; the panel's
   title + mode + summary must all swap to that agent within one
   `agent_update` tick.
3. **JP labels** — section headers read 気づき / 判断 / 次の意図 /
   最新の反省 / 関係性 (5 of the 7 ζ-1 keys). LATEST REFLECTION must
   no longer appear in English.
4. **Camera tune (E1 partial)** — orbit (drag) / zoom (wheel) / pan
   (shift+drag) all feel noticeably faster than the pre-ζ-1 baseline.
   Compare against muscle memory; no metric.
5. **No `[error]` lines** in the Godot debug console relating to
   `Strings.LABELS` keys (a missing key would print
   `[ReasoningPanel] missing label ...`).

### ζ-2 surfaces (5 items)

6. **Persona title** — when an agent is focused, the panel title reads
   `Reasoning Panel — <agent_id> (<display_name>)`, e.g.
   `Reasoning Panel — a_kant_001 (Immanuel Kant)`. The display_name
   should resolve for all 3 personas (kant / nietzsche / rikyu).
7. **Persona summary** — under the mode label, a 1-line summary like
   `勤勉・低神経症 — 規律のリズムが思考を貫く` (kant) /
   `高エネルギー・突発バースト — 散策で思考が爆発する` (nietzsche) /
   `静謐・侘び寂び — 沈黙と所作に意味を宿す` (rikyu).
8. **Belief icons on bond rows** — after ~6 dialog turns at
   |affinity| ≥ 0.30 between any dyad, the corresponding bond row in
   the 関係性 block gets prefixed with one of `◯ △ ✕ ？ ◇`. δ run-02
   produced ≥ 1 promotion in 360 s for the kant↔nietzsche dyad, so
   you should see at least one icon by the end of the probe window.
   If no icons appear, that's an axis-C5 partial — flag in
   `observation.md` but not a hard fail (defer-able to ζ-3 once
   `behavior_profile` makes dialog dynamics more bursty).
9. **Last-3 reflection list** — the 最新の反省 block shows up to 3
   lines formatted as `tick <T>: <summary>` in tick-descending order,
   not just the latest. As more reflections fire, the bottom line
   drops off and the newest pushes in at the top.
10. **Selector switch resets the trail** — after switching selector
    to another agent, the reflection list, persona summary, and
    belief icons all reset to the new agent's stream within one
    `agent_update` tick (no flicker of the previous agent's data).

## Step 6 — Stop the orchestrator (terminal A)

Ctrl-C in terminal A. Orchestrator log already captured via `tee` in
step 2.

## Step 7 — δ regression check (5 hard gates)

After the probe exits, produce the δ-style db_summary and verify the
δ acceptance gates are still green. **All 5 must pass before push.**

```bash
uv run python .steering/20260426-m7-slice-delta/evidence/_db_summary_m7d.py \
  --db var/run-zeta.db \
  --journal .steering/20260426-m7-slice-zeta-live-resonance/run-01-zeta/run-01.jsonl \
  --out .steering/20260426-m7-slice-zeta-live-resonance/run-01-zeta/run-01.db_summary.json
```

Open the resulting `run-01.db_summary.json` and check (mirror of the
ε run-guide step 6):

* `db.table_counts.dialog_turns` — same order of magnitude as
  ε run-01 (12-20 for a 360 s run with 3 personas).
* `db.belief_promotions` ≥ 1 row with `belief_kind` populated.
* `journal.bonds_with_last_interaction_zone` > 0.
* `journal.max_emotional_conflict_observed` > 0.
* `journal.affinity_sign_distribution` shows both positive and
  negative buckets non-zero.

If any of the 5 misses, **do not push**; open
`.steering/<YYYYMMDD>-m7-zeta-live-fix/` and capture the failing
gate. The δ live-fix decisions.md D1 documents the analogous flow.

## Step 8 — Land the verdict

If all 5 δ gates pass and the 10 visual items are mostly PASS (item
8 belief-icon may be partial — note in observation.md):

1. Append a "Live G-GEAR run-01-zeta (landed)" section to
   `.steering/20260426-m7-slice-zeta-live-resonance/observation.md`
   (create it mirroring the δ pattern). Capture:
   * The 5 δ-regression line items with PASS / FAIL.
   * The 10 visual items with PASS / FAIL / PARTIAL + 1-line note.
   * Any deviations from the run-02-delta `dialog_turns` count that
     warrant follow-up.

2. Push the two branches in order:

   ```bash
   # PR-ζ-1 first
   git push -u origin feat/m7-zeta-godot-resonance
   gh pr create --title "feat(godot): M7 Slice ζ-1 — Live Resonance (Godot 完結)" \
                --body "$(cat <<'EOF'
   ## Summary
   - day/night cycle (Timer-driven 1Hz, 1800s) in WorldManager
   - JP locale dict (Strings.gd, ≤15 labels) — closes live issue C6
   - ReasoningPanel multi-agent selector — closes live issue C4
   - camera sensitivity tune (orbit / zoom / pan) — closes E1 partial
   - drop dead M6-B-1 comment from project.godot
   - includes Strings.gd.uid follow-up commit

   ## Test plan
   - [ ] Mac fixture replay or G-GEAR live run-01-zeta day/night ladder visible
   - [ ] selector switches across 3 agents, panel content swaps
   - [ ] ≥5 JP labels render; no missing-key console errors
   - [ ] camera feels noticeably faster on orbit / zoom / pan

   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   EOF
   )"

   # After ζ-1 merges, rebase ζ-2 onto main and push
   git checkout feat/m7-zeta-panel-context
   git rebase main
   git push -u origin feat/m7-zeta-panel-context
   gh pr create --title "feat(schemas+godot): M7 Slice ζ-2 — Panel Context (bump 0.9.0-m7z)" \
                --body "$(cat <<'EOF'
   ## Summary
   - bump SCHEMA_VERSION 0.8.0-m7e → 0.9.0-m7z
   - ReasoningTrace.persona_id additive (cognition stamp + Godot title)
   - RelationshipBond.latest_belief_kind additive + WorldRuntime.apply_belief_promotion
   - Godot ReasoningPanel: persona display_name + 1-line summary, belief icons (◯△✕？◇), last-3 reflection list
   - persona YAMLs bumped to 0.9.0-m7z; goldens + 13 fixtures re-baked

   ## Test plan
   - [ ] G-GEAR live run-01-zeta — δ 5/5 gate PASS
   - [ ] panel title resolves to ``<agent_id> (<display_name>)`` for all 3 personas
   - [ ] belief icons appear after ≥1 promotion (kant↔nietzsche dyad in δ baseline)
   - [ ] reflection list shows up to 3 entries tick desc, selector switch clears

   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   EOF
   )"
   ```

## Step 9 — Cleanup

After verdicts commit, the local `var/run-zeta.db` is no longer needed
— drop it or keep for ad-hoc forensics. The journal + db_summary land
in `.steering/20260426-m7-slice-zeta-live-resonance/run-01-zeta/`
and are the durable record.

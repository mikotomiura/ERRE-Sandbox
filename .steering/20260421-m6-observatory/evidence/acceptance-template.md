# M6 Research Observatory — live acceptance record (template)

Copy this file to `acceptance-<YYYYMMDD-HHMMSS>.md` for each live run and
fill in the placeholders. A run is "PASS" only when every gate is checked
and the numeric thresholds at the bottom are met.

## Session metadata

- Date (UTC): `YYYY-MM-DDTHH:MM:SSZ`
- Duration: `N` minutes
- Gateway host: `g-gear.local:8000` (or LAN IP)
- Ollama model: `qwen3:8b` (or other)
- Agents active: `kant` / `nietzsche` / `rikyu`
- Godot revision (hash): `git rev-parse HEAD` on MacBook
- Gateway revision (hash): `git rev-parse HEAD` on G-GEAR

## 3-axis acceptance gate (the user's original M6 concerns)

### Axis 1 — event density 体感
**Goal**: more than just zone transitions; researcher can *feel* that the
LLM prompt sees ERREModeShift / Biorhythm / Temporal / Proximity events.

- [ ] Each of `erre_mode_shift` / `biorhythm` / `temporal` / `proximity`
      appears at least once in the live envelope log
      (`logs/live-*.jsonl`) within the observation window
- [ ] `reasoning_trace` envelope count ≥ cognition tick count × 0.80
      (80 % LLM JSON extraction success rate per
      `.steering/20260421-m6-observatory/decisions.md` Decision 2)
- [ ] No `[unknown] (unformatted)` lines in the gateway log

Per-kind counts from `_stream_probe_m6.py --out` summary:

```
agent_update       : ?
reasoning_trace    : ?
reflection_event   : ?
world_tick         : ?
speech             : ?
move               : ?
animation          : ?
dialog_turn        : ?
error              : ?
```

### Axis 2 — xAI 可視化
**Goal**: researcher can see *why* an agent decided what it did without
reading server logs.

- [ ] Camera modes `1` (OVERVIEW) / `2` (FOLLOW_AGENT) / `3` (MIND_PEEK)
      all switch cleanly; mouse drag orbits; wheel zooms; WASD pans in
      OVERVIEW
- [ ] Left-clicking any avatar promotes OVERVIEW to FOLLOW_AGENT and
      locks ReasoningPanel onto that agent
- [ ] ReasoningPanel `SALIENT` / `DECISION` / `NEXT INTENT` sections
      populate with Japanese text within two cognition ticks of selection
- [ ] `LATEST REFLECTION` section populates when the reflector fires
      (zone entry into peripatos / chashitsu)
- [ ] `B` key toggles the cyan zone boundary wireframes

### Axis 3 — chashitsu リアリティ
**Goal**: the tea room feels like an actual place, not a tinted square.

- [ ] 6×6 m footprint visible with four wood posts, three shoji walls,
      open south (engawa) side
- [ ] Gabled roof + ridge beam present and lit
- [ ] Interior details visible: tokonoma, ash hearth, kettle, two clay
      tea bowls
- [ ] Warm interior OmniLight3D tints the inside honey-amber
- [ ] Peripatos colonnade shows the expanded 60 m length and 20 posts

## Evidence attachments

- `logs/gateway-live-<TS>.log` — full gateway stdout capture
- `logs/live-<TS>.jsonl` — envelope probe capture (see
  `_stream_probe_m6.py`)
- `logs/live-<TS>.jsonl.summary.json` — per-kind counts emitted by the
  probe
- `screenshots/<NN>-<label>.png` — at least one per axis (overview,
  camera mode switch, reasoning panel populated, chashitsu interior,
  peripatos colonnade)
- `demo-<TS>.mp4` (optional) — 90-second vertical-slice recording

## Known gaps (not failing the gate, flag for M7)

- [ ] Affordance firing (prop registry unbuilt)
- [ ] SynapseGraph (MIND_PEEK full-screen reasoning graph)
- [ ] EventVisualizer (event fire glow ring)
- [ ] StateBar (cognitive HUD over avatars)
- [ ] Other 4 zones' Blender builds (study / agora / garden)

## Verdict

- Overall: ☐ PASS ☐ FAIL ☐ PARTIAL
- Signed off by: `<mikotomiura>`
- Follow-up tasks: `<list .steering/ task dirs to open for carryover>`

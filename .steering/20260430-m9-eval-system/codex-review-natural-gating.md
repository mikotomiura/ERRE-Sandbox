Reading prompt from stdin...
OpenAI Codex v0.125.0 (research preview)
--------
workdir: /Users/johnd/ERRE-Sand Box
model: gpt-5.5
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR, /Users/johnd/.codex/memories] (network access enabled)
reasoning effort: high
reasoning summaries: none
session id: 019de1b8-46a1-7a12-a1ff-0d8667efebf5
--------
user
# Codex independent review — m9-eval-system P3a-decide natural gating fix

> Codex `gpt-5.5 xhigh` independent review request. Prompt として
> `cat .steering/20260430-m9-eval-system/codex-review-prompt-natural-gating.md
>  | codex exec --skip-git-repo-check` で起動。
> 出力は `codex-review-natural-gating.md` に verbatim 保存。

---

## Context

You are reviewing a bug fix for ERRE-Sandbox m9-eval-system P3a pilot
data collection. The pilot ran on G-GEAR (Windows / RTX 5060 Ti / qwen3:8b
Q4_K_M / Ollama 0.22.0). 3 stimulus cells completed cleanly (focal=198,
total=342, dialogs=168). 3 natural cells **stalled after the initial
burst**:

- kant_natural: 13 min wall, 2 dialogs / 6 focal turns
- nietzsche_natural: 13 min wall, **0 dialogs / 0 focal turns** (starved)
- rikyu_natural: 13 min wall, 3 dialogs / 6 focal turns

CLI is `src/erre_sandbox/cli/eval_run_golden.py` (committed in PR #129).
The natural path constructs a full `WorldRuntime` + `CognitionCycle`
stack with all 3 personas registered in `Zone.AGORA` via
`_initial_state_for_natural` (separate seats inside AGORA).

## Root cause we converged on

`personas/{nietzsche,rikyu}.yaml` set `preferred_zones` that **do not
include AGORA** (Nietzsche=`[peripatos,study,garden]`,
Rikyū=`[chashitsu,garden,study]`). The cognition cycle prompt asks the
LLM to pick a `destination_zone` from `study|peripatos|chashitsu|agora|
garden|null`. When non-null, `_resample_destination_to_persona_zone`
(cognition/cycle.py:828) uses `bias_p` from
`os.environ.get("ERRE_ZONE_BIAS_P", "0.2")` — only 20% of the time does
it bias the destination back to a preferred zone. **80% of the time the
LLM-chosen non-preferred destination is honoured.**

Net: per cognition tick, ≈53% chance an agent moves to a non-AGORA zone.
After 3 ticks, ≈89% chance at least one agent has scattered. The
`InMemoryDialogScheduler.tick()` then sees `_iter_colocated_pairs`
return 0 pairs because `a.zone == b.zone` is no longer satisfied. Open
dialogs run to budget exhaustion (6 turns each), then no new dialog can
admit because no pair is co-located.

This explains the observed pattern exactly: **initial burst of 2-3
dialogs × 6 turns = 12-18 utterances, then plateau**.

## Fix being proposed

`InMemoryDialogScheduler` (frozen Protocol from M4 §7.5) gets a new
keyword-only `eval_natural_mode: bool = False` flag. When True:

1. `tick()` uses a new `_iter_all_distinct_pairs` helper instead of
   `_iter_colocated_pairs`. Every distinct agent pair is eligible
   regardless of zone equality.
2. The reflective-zone skip (`if a.zone not in _REFLECTIVE_ZONES`) is
   bypassed.
3. `schedule_initiate` similarly bypasses the zone-not-reflective reject
   (line 156).

Default `False` keeps M4-frozen behaviour for live multi-agent runs.
CLI opt-in is one keyword in `capture_natural`.

## Invariants explicitly preserved

- `initiator_id == target_id` → reject (programming error)
- Pair already open → second `schedule_initiate` returns None
- `COOLDOWN_TICKS=30` → same pair cannot re-admit within 30 ticks of
  previous close, even with zone bypass
- `AUTO_FIRE_PROB_PER_TICK=0.25` → probability gate still active
- `TIMEOUT_TICKS=6` → in-flight dialog still auto-closes when
  `last_activity_tick` is stale

11 new unit tests in
`tests/test_integration/test_dialog_eval_natural_mode.py` enforce all
the above. Existing 1221 tests still pass (full suite: 1232 passed).

## Diff (verbatim)

### `src/erre_sandbox/integration/dialog.py`

```python
# Constructor signature
def __init__(
    self,
    *,
    envelope_sink: Callable[[ControlEnvelope], None],
    rng: Random | None = None,
    turn_sink: Callable[[DialogTurnMsg], None] | None = None,
    golden_baseline_mode: bool = False,
    eval_natural_mode: bool = False,  # ← NEW
) -> None:
    ...
    self.golden_baseline_mode: bool = golden_baseline_mode
    self.eval_natural_mode: bool = eval_natural_mode  # ← NEW (public)

# schedule_initiate (line 167)
if (
    zone not in _REFLECTIVE_ZONES
    and not self.golden_baseline_mode
    and not self.eval_natural_mode  # ← NEW
):
    return None

# tick (line 299)
self._close_timed_out(world_tick)
if self.eval_natural_mode:
    pair_iter = _iter_all_distinct_pairs(agents)  # ← NEW helper
else:
    pair_iter = _iter_colocated_pairs(agents)
for a, b in pair_iter:
    if not self.eval_natural_mode and a.zone not in _REFLECTIVE_ZONES:
        continue
    key = _pair_key(a.agent_id, b.agent_id)
    if key in self._pair_to_id:
        continue
    last_close = self._last_close_tick.get(key)
    if last_close is not None and world_tick - last_close < self.COOLDOWN_TICKS:
        continue
    if self._rng.random() > self.AUTO_FIRE_PROB_PER_TICK:
        continue
    self.schedule_initiate(a.agent_id, b.agent_id, a.zone, world_tick)

# New helper (line 406)
def _iter_all_distinct_pairs(
    agents: Iterable[AgentView],
) -> Iterator[tuple[AgentView, AgentView]]:
    sorted_agents = sorted(agents, key=lambda v: v.agent_id)
    for i, a in enumerate(sorted_agents):
        for b in sorted_agents[i + 1 :]:
            yield a, b
```

### `src/erre_sandbox/cli/eval_run_golden.py` (line 935-947)

```python
scheduler = InMemoryDialogScheduler(
    envelope_sink=runtime.inject_envelope,
    rng=scheduler_rng,
    turn_sink=duckdb_sink,
    golden_baseline_mode=False,
    eval_natural_mode=True,  # ← NEW
)
```

## Specific review asks

Please flag any of the following at HIGH / MEDIUM / LOW severity:

1. **Correctness**: does the diff actually fix the observed gating bug?
   Are there scenarios where the proposed fix still admits 0 pairs?
2. **Invariant preservation**: do cooldown / probability / timeout /
   self-reject / double-open-reject *really* still apply when
   `eval_natural_mode=True`? The test suite covers them but you may
   spot edge cases the tests miss.
3. **Protocol contract**: is the keyword-only `__init__` flag a clean
   extension to the M4-frozen `DialogScheduler` Protocol? The Protocol
   only fixes `schedule_initiate / record_turn / close_dialog`
   signatures, not `__init__` — but is the convention here clean?
4. **Naming**: `eval_natural_mode` vs alternatives (`relax_zone_gate`,
   `proximity_free`, `eval_logical_co_location`). The mode is set only
   for eval natural-condition capture, but the flag name should be
   readable to a future reader who has no eval context.
5. **Alternative fixes** considered and rejected (see
   design-natural-gating-fix.md):
   - Override persona `preferred_zones=[AGORA]` in CLI alone — rejected
     because `ERRE_ZONE_BIAS_P=0.2` default still leaks ~53% of the time
   - Drop MoveMsg in `WorldRuntime` for eval — rejected, world-layer
     eval-only knob would be invasive
   - Force `ERRE_ZONE_BIAS_P=1.0` env var + preferred override — env
     mutation is hacky, low diagnosability
   - Add explicit "eval pair set" frozenset API — rejected as more
     complex than a boolean flag
6. **Risk**: any way the diff breaks live multi-agent (M5/M6) runs that
   default `eval_natural_mode=False`?
7. **Future maintainability**: does the diff make the dialog scheduler's
   responsibility surface more confusing (now 2 boolean flags affecting
   semantically-similar bypass paths)?
8. **Re-capture confidence**: assuming the fix is shipped to G-GEAR, do
   you expect the 30-target-focal natural cell to complete within
   30-60 min wall? Any reason to expect a different gating bug to
   emerge once this one is fixed?

## Out of scope for this review

- LoRA training (M9-B) interaction — orthogonal milestone
- Tier B / Tier C metrics — not touched
- bootstrap CI (P5) — separate prep work in this same Mac session
- M9-A event boundary observability — already merged

## Format

Reply with HIGH / MEDIUM / LOW sections, then a final **Verdict: ship /
ship-with-edits / block** line. If you flag HIGH, please include enough
context that I can edit before merging.

hook: SessionStart
hook: SessionStart Completed
hook: UserPromptSubmit
hook: UserPromptSubmit Completed
codex
I’ll treat this as a code-review pass, using the ERRE workflow entry point first, then I’ll inspect the scheduler, CLI wiring, and the new tests against the invariants you listed.
exec
/bin/zsh -lc "sed -n '1,240p' .agents/skills/erre-workflow/SKILL.md && sed -n '1,220p' .agents/skills/project-status/SKILL.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
---
name: erre-workflow
description: >
  ERRE-Sandbox task workflow for Codex. Use when starting, designing, implementing,
  reviewing, or finishing repository work; when the user mentions /start-task,
  /add-feature, /fix-bug, /refactor, /reimagine, /review-changes, or /finish-task;
  or when .steering records, Codex setup, task plans, or implementation handoffs are needed.
---

# ERRE Workflow

This is the Codex-native replacement for the Claude slash-command workflow. Claude command
files in `.claude/commands/` are reference material only; Codex should execute the workflow
through normal tool use, `.steering/` records, skills, hooks, and custom agents.

## Quick Start

1. Read `AGENTS.md`, `docs/development-guidelines.md`, and the relevant domain skill.
2. Create or update `.steering/YYYYMMDD-task-name/` before implementation work:
   `requirement.md`, `design.md`, and `tasklist.md` are required.
3. For design-heavy work, keep implementation paused until a plan is accepted. If the task
   has multiple plausible designs, perform a reimagine pass before editing source files.
4. Implement in small steps, updating `tasklist.md` as work completes.
5. Verify with focused checks first, then the documented full checks when feasible.
6. Finish by reviewing the diff and recording any decisions or limitations.

Use subagents only when the user explicitly asks for delegation or parallel agent work.
When they do, prefer the project-scoped agents in `.codex/agents/`.

## Task Start

Create `.steering/YYYYMMDD-task-name/` with:

- `requirement.md`: background, goal, scope, out of scope, acceptance criteria.
- `design.md`: approach, changed areas, compatibility, test strategy, rollback.
- `tasklist.md`: checkboxes at roughly 30-minute granularity.
- `decisions.md`: only for meaningful tradeoffs or policy choices.
- `blockers.md`: only when blocked or carrying deferred risk.

Use the current local date in `YYYYMMDD`. Prefer a short kebab-case task name.

## Implementation Flows

- **Feature**: read existing patterns, document the design, implement narrowly, add tests or
  verification proportional to risk, update docs when behavior changes.
- **Bug fix**: reproduce or explain the failure, record root cause, add or identify a
  regression check when feasible, then make the smallest defensible fix.
- **Refactor**: establish current checks first, preserve behavior, change in small steps,
  and avoid mixing feature or bug-fix work into the same task.

For source edits under `src/erre_sandbox/`, always consider:

- `architecture-rules` for layer direction and GPL/cloud API constraints.
- `python-standards` for Python style.
- `error-handling` when async, retry, timeout, WebSocket, sqlite, or LLM fallback behavior changes.
- `test-standards` when adding or changing tests.

## Reimagine

Use this for architecture, public interfaces, difficult bugs, and designs with multiple
credible approaches:

1. Save the first plan as `design-v1.md`.
2. Re-read only `requirement.md` and produce a fresh alternative in `design.md`.
3. Compare the two in `design-comparison.md`.
4. Choose v1, v2, or a hybrid and record the reason in `decisions.md`.

Do not use reimagine after implementation has already created side effects that would need
manual rollback.

## Review And Finish

Before final delivery:

- Run focused checks for touched areas.
- Run `uv run ruff check src tests`, `uv run ruff format --check src tests`,
  `uv run mypy src`, and `uv run pytest` when feasible.
- Review `git diff` for unrelated changes and do not revert user work.
- Update `tasklist.md` and `design.md` with what actually happened.
- Mention skipped checks or residual risk in the final response.

Do not commit unless the user asks. If committing, use `git-workflow`.
---
name: project-status
description: >
  プロジェクトの現在の状態をリアルタイムで取得する。
  作業を始める前・コンテキストが分からなくなった時・進捗を確認したい時・
  最近の変更を把握したい時に使う。git 状態・最近のコミット・
  構築フェーズの進捗 (.steering/_setup-progress.md)・未対応 TODO・
  変更ファイル統計を一括で取得する。セッション開始時の状況把握にも使える。
---

# Project Status

このスキルは現在のプロジェクト状態を動的に取得します。

## 現在の git 状態

!`git status --short`

## 最近のコミット (10 件)

!`git log --oneline -10 2>/dev/null || echo "(no commits yet)"`

## 現在のブランチ

!`git branch --show-current`

## 構築フェーズ進捗

!`grep -E "^\- \[" .steering/_setup-progress.md 2>/dev/null | head -20 || echo "(progress file not found)"`

## 未対応 TODO の数

!`grep -r "TODO\|FIXME\|HACK\|XXX" src/ tests/ 2>/dev/null | wc -l`

## 変更ファイルの統計 (直近コミットとの差分)

!`git diff --stat HEAD 2>/dev/null || echo "(no HEAD yet)"`

## 最近変更されたファイル (24 時間以内)

!`find src/ tests/ -name "*.py" -newer .git/index -mtime -1 2>/dev/null | head -10`

## Skills ディレクトリ

!`ls .agents/skills/ 2>/dev/null || echo "(no skills yet)"`

## あなたのタスク

上記の動的データを分析し、以下を報告してください:

1. **現状サマリ** — 現在のフェーズと進捗を 1-2 行で
2. **進行中の作業** — 未コミットの変更や直近の変更ファイルから何が進んでいるか
3. **注意すべき点** — 多数の未コミット変更、TODO の偏り、進捗ファイルとの乖離など
4. **推奨される次のアクション** — 何を優先すべきか (setup フェーズであればどのコマンドを次に実行すべきか)

レポートは簡潔に。詳細は必要に応じてユーザーが追加で質問する。

codex
The workflow says review-and-finish checks are the right shape here. I’m going to verify the real diff and tests rather than relying only on the prompt’s excerpt.
exec
/bin/zsh -lc "sed -n '880,980p' src/erre_sandbox/cli/eval_run_golden.py" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,460p' src/erre_sandbox/integration/dialog.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
    # default factory below.
    if runtime_factory is None:

        def _resolve_persona_display_name(agent_id: str) -> str | None:
            pid = runtime.agent_persona_id(agent_id)
            if pid is None:
                return None
            spec = persona_specs.get(pid)
            return spec.display_name if spec is not None else None

        reflector = Reflector(
            store=memory,
            embedding=embedding,
            llm=inference,
            persona_resolver=_resolve_persona_display_name,
        )
        cycle = CognitionCycle(
            retriever=retriever,
            store=memory,
            embedding=embedding,
            llm=inference,
            erre_policy=DefaultERREModePolicy(),
            bias_sink=lambda _e: None,
            reflector=reflector,
        )
        runtime = WorldRuntime(cycle=cycle)
    else:
        runtime = runtime_factory(
            memory=memory,
            embedding=embedding,
            inference=inference,
            retriever=retriever,
            persona_specs=persona_specs,
        )

    def _persona_resolver(agent_id: str) -> str | None:
        return runtime.agent_persona_id(agent_id)

    def _zone_resolver(speaker_id: str, _dialog_id: str) -> str:
        zone = runtime.get_agent_zone(speaker_id)
        return zone.value if zone is not None else ""

    duckdb_sink = _make_duckdb_sink(
        con=con,
        run_id=run_id,
        focal_persona_id=persona,
        persona_resolver=_persona_resolver,
        fallback_speaker_persona=persona,
        fallback_addressee_persona="?",
        zone_resolver=_zone_resolver,
        state=state,
        enough_event=enough_event,
        focal_budget=turn_count,
    )

    scheduler_rng = random.Random(seed_root)  # noqa: S311 — non-crypto, eval seed
    scheduler = InMemoryDialogScheduler(
        envelope_sink=runtime.inject_envelope,
        rng=scheduler_rng,
        turn_sink=duckdb_sink,
        golden_baseline_mode=False,
        # P3a-decide gating fix: bypass zone-equality so the 3 personas can
        # sustain dialog after LLM destination_zone scatters them out of
        # AGORA. See .steering/20260430-m9-eval-system/design-natural-gating-fix.md
        # for root-cause analysis.
        eval_natural_mode=True,
    )
    runtime.attach_dialog_scheduler(scheduler)

    dialog_generator = OllamaDialogTurnGenerator(llm=inference, personas=persona_specs)
    runtime.attach_dialog_generator(dialog_generator)

    # Register all three personas so proximity auto-fire has every pair
    # available.  Codex MEDIUM-5 confirmed _iter_colocated_pairs only checks
    # zone equality, so the three seats inside AGORA are sufficient.
    for pid in DEFAULT_PERSONAS:
        spec = persona_specs[pid]
        runtime.register_agent(_initial_state_for_natural(spec), spec)

    # Warmup — same fail-soft logic as stimulus.
    await _warm_up_ollama(inference, persona_specs[persona])

    # Drive: spawn runtime task + watchdog.  The watchdog returns once the
    # focal budget is reached, the wall hard cap is hit, or the runtime
    # task itself completes (e.g. fatal error inside the cycle).
    runtime_task = asyncio.create_task(runtime.run(), name="p3a-natural-runtime")
    wall_deadline = time.monotonic() + wall_timeout_min * 60.0

    async def _watchdog() -> None:
        while True:
            if state.fatal_error is not None:
                logger.error(
                    "natural capture aborting on fatal sink error: %s",
                    state.fatal_error,
                )
                return
            if enough_event.is_set():
                logger.info("natural capture focal budget %d reached", turn_count)
                return
            if runtime_task.done():
                logger.info("runtime task exited before focal budget")

 succeeded in 0ms:
"""In-memory implementation of the M4 :class:`DialogScheduler` Protocol.

Responsibility: admission-control and lifecycle tracking for agent-to-agent
dialogs. The scheduler *also* owns the envelope emission path — when it
admits an initiate or closes a dialog, it calls the injected ``sink``
callable with the corresponding :class:`ControlEnvelope`, so callers do not
need to route the return value back into the gateway's queue themselves.

Design rationale (see
``.steering/20260420-m4-multi-agent-orchestrator/design.md`` §v2):

* The Protocol is frozen at M4 foundation and says ``schedule_initiate``
  returns ``DialogInitiateMsg | None``; we keep that return contract but
  the authoritative delivery path is the sink. Callers that build on the
  Protocol API only get a signal of "was this admitted"; they MUST NOT
  put the returned envelope onto a queue themselves — doing so would
  duplicate the envelope delivered via the sink.
* ``tick()`` is an extension method (not part of the Protocol) that drives
  proximity-based auto-firing: two agents sharing a reflective zone after
  the pair's cooldown has elapsed get a probabilistic initiate.
* All randomness flows through an injected :class:`~random.Random` so the
  auto-fire path is deterministic under test.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from random import Random
from typing import TYPE_CHECKING, ClassVar, Final

from erre_sandbox.schemas import (
    AgentView,
    DialogCloseMsg,
    DialogInitiateMsg,
    DialogTurnMsg,
    Zone,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Sequence
    from typing import Literal

    from erre_sandbox.schemas import ControlEnvelope

logger = logging.getLogger(__name__)


@dataclass
class _OpenDialog:
    """In-flight dialog state carried by the scheduler's ``_open`` map."""

    dialog_id: str
    initiator: str
    target: str
    zone: Zone
    opened_tick: int
    last_activity_tick: int
    turns: list[DialogTurnMsg] = field(default_factory=list)


_REFLECTIVE_ZONES: Final[frozenset[Zone]] = frozenset(
    {Zone.PERIPATOS, Zone.CHASHITSU, Zone.AGORA, Zone.GARDEN},
)
"""Zones where proximity-based dialog admission is allowed.

``Zone.STUDY`` is intentionally excluded — the M2 persona-erre model treats
the study as a private deep-work space where interrupting speech is
culturally inappropriate.
"""


def _pair_key(a: str, b: str) -> frozenset[str]:
    """Order-agnostic dialog pair identity used as a dict key."""
    return frozenset({a, b})


class InMemoryDialogScheduler:
    """Default :class:`DialogScheduler` implementation for MVP multi-agent runs.

    State lives entirely in memory; there is no persistence because M4
    scoped dialog history to the transient layer (semantic summaries come
    from the Reflector on a different path). If a future milestone wants
    cross-run dialog transcripts, subclass and override ``record_turn`` /
    ``close_dialog`` to also write to sqlite.
    """

    COOLDOWN_TICKS: ClassVar[int] = 30
    """Ticks that must elapse after a close before the same pair may reopen."""

    TIMEOUT_TICKS: ClassVar[int] = 6
    """Inactivity window after which an open dialog is auto-closed."""

    AUTO_FIRE_PROB_PER_TICK: ClassVar[float] = 0.25
    """Probability that a qualifying co-located pair is admitted on a tick.

    Keeps dialog from firing every single cognition tick when two agents
    happen to share a zone; the RNG is injected so tests can force the
    probability to 1.0 or 0.0 deterministically.
    """

    def __init__(
        self,
        *,
        envelope_sink: Callable[[ControlEnvelope], None],
        rng: Random | None = None,
        turn_sink: Callable[[DialogTurnMsg], None] | None = None,
        golden_baseline_mode: bool = False,
        eval_natural_mode: bool = False,
    ) -> None:
        self._sink = envelope_sink
        self._rng = rng if rng is not None else Random()  # noqa: S311 — non-crypto
        # M8 L6-D1: optional per-turn sink. When bootstrap wires it to a
        # ``MemoryStore.add_dialog_turn_sync`` closure (with agent_id →
        # persona_id resolution baked in), every recorded turn lands in
        # sqlite for later LoRA-training export. Left None for unit tests
        # and the existing lightweight fixtures that have no store.
        self._turn_sink = turn_sink
        # m9-eval-system P2b (design-final.md §Orchestrator): when True the
        # external golden baseline driver bypasses cooldown / timeout / zone
        # restriction so that 70-stimulus battery × 3 cycles can drive the
        # same agent pair without the natural-dialog admission rules. Public
        # attribute so the driver can flip it between stimulus phase
        # (200 turn, mode=True) and natural-dialog phase (300 turn,
        # mode=False) within the same scheduler instance / MemoryStore.
        self.golden_baseline_mode: bool = golden_baseline_mode
        # m9-eval-system P3a-decide (design-natural-gating-fix.md): when True
        # the eval natural-condition pilot bypasses zone-equality and
        # reflective-zone gates inside ``tick()`` and ``schedule_initiate()``
        # so 3 personas can sustain dialog after LLM-driven destination_zone
        # scatters them across study/peripatos/chashitsu. Cooldown / probability
        # / timeout / self-dialog reject / double-open reject all remain active
        # so admission cadence is still natural — only the spatial constraint
        # is dropped. Orthogonal to ``golden_baseline_mode``: stimulus phase
        # uses ``golden_baseline_mode=True`` (driver controls everything),
        # natural phase uses ``eval_natural_mode=True`` (proximity-free
        # logical co-location). Default False keeps M4-frozen Protocol
        # behaviour for live multi-agent runs.
        self.eval_natural_mode: bool = eval_natural_mode
        self._open: dict[str, _OpenDialog] = {}
        self._pair_to_id: dict[frozenset[str], str] = {}
        # Bounded by C(N, 2) for N agents — M4 targets N≤3 so this cannot
        # grow beyond a few entries. If a future milestone scales to N>100
        # agents, cap this to an LRU dict or prune by stale age from
        # ``tick()``; for now the memory footprint is irrelevant.
        self._last_close_tick: dict[frozenset[str], int] = {}

    # ------------------------------------------------------------------
    # Protocol methods (frozen in schemas.py §7.5)
    # ------------------------------------------------------------------

    def schedule_initiate(
        self,
        initiator_id: str,
        target_id: str,
        zone: Zone,
        tick: int,
    ) -> DialogInitiateMsg | None:
        """Admit or reject a new dialog.

        Returns the :class:`DialogInitiateMsg` on admission for callers that
        rely on the Protocol signature, BUT the envelope is already on the
        way to consumers via the injected sink at the moment this method
        returns. Callers must not forward the return value onto the same
        envelope queue — see module docstring.
        """
        if initiator_id == target_id:
            return None
        if (
            zone not in _REFLECTIVE_ZONES
            and not self.golden_baseline_mode
            and not self.eval_natural_mode
        ):
            # m9-eval-system P2b: golden baseline stimulus battery includes
            # ``Zone.STUDY`` (Kant Wachsmuth/RoleEval, Nietzsche aphoristic
            # bursts) — bypass the natural-dialog cultural restriction.
            # m9-eval-system P3a-decide: eval natural condition lets agents
            # wander out of reflective zones (LLM-driven destination_zone)
            # and we still want them to dialog — bypass zone gate too.
            return None
        key = _pair_key(initiator_id, target_id)
        if key in self._pair_to_id:
            return None
        last_close = self._last_close_tick.get(key)
        if (
            last_close is not None
            and tick - last_close < self.COOLDOWN_TICKS
            and not self.golden_baseline_mode
        ):
            # m9-eval-system P2b: 70 stimulus × 3 cycles drives the same pair
            # repeatedly; cooldown would otherwise serialize them across
            # ≥ 30-tick gaps and inflate baseline tick range artificially.
            return None

        dialog_id = _allocate_dialog_id()
        self._open[dialog_id] = _OpenDialog(
            dialog_id=dialog_id,
            initiator=initiator_id,
            target=target_id,
            zone=zone,
            opened_tick=tick,
            last_activity_tick=tick,
        )
        self._pair_to_id[key] = dialog_id
        envelope = DialogInitiateMsg(
            tick=tick,
            initiator_agent_id=initiator_id,
            target_agent_id=target_id,
            zone=zone,
        )
        self._emit(envelope)
        return envelope

    def record_turn(self, turn: DialogTurnMsg) -> None:
        """Attach ``turn`` to its dialog's transcript.

        Raises ``KeyError`` when the dialog is not open — this surfaces bugs
        (agents speaking into a closed dialog) rather than silently dropping.

        When a ``turn_sink`` was injected at construction (M8 L6-D1), the
        turn is forwarded to it after the in-memory bookkeeping so the sink
        observes turns in the same order as the transcript. Sink exceptions
        are caught and logged — a transient persistence failure must not
        tear down the live dialog loop.
        """
        dialog = self._open.get(turn.dialog_id)
        if dialog is None:
            raise KeyError(
                f"record_turn called for unknown dialog_id={turn.dialog_id!r}",
            )
        dialog.turns.append(turn)
        dialog.last_activity_tick = turn.tick
        if self._turn_sink is not None:
            try:
                self._turn_sink(turn)
            except Exception:
                logger.exception(
                    "turn_sink raised for dialog_id=%s turn_index=%d; "
                    "dropping row but keeping dialog alive",
                    turn.dialog_id,
                    turn.turn_index,
                )

    def close_dialog(
        self,
        dialog_id: str,
        reason: Literal["completed", "interrupted", "timeout", "exhausted"],
        *,
        tick: int | None = None,
    ) -> DialogCloseMsg:
        """Close ``dialog_id`` and emit the envelope via the sink.

        When ``tick`` is provided the close is recorded at that world tick
        (``DialogCloseMsg.tick`` and the cooldown anchor both honour it).
        When omitted, falls back to ``dialog.last_activity_tick`` so callers
        that only see the M4-frozen Protocol surface continue to behave as
        before. The keyword-only ``tick`` is the supported path for any
        caller that knows the current world tick (timeout sweep, exhausted
        budget, manual interrupt) — see codex review F1 (2026-04-28) for
        the stale-tick regression that motivated the parameter.

        Raises ``KeyError`` when the id is not currently open.
        """
        return self._close_dialog_at(dialog_id, reason, tick)

    def _close_dialog_at(
        self,
        dialog_id: str,
        reason: Literal["completed", "interrupted", "timeout", "exhausted"],
        tick: int | None,
    ) -> DialogCloseMsg:
        """Apply the close operation, honouring an optional override tick."""
        dialog = self._open.pop(dialog_id, None)
        if dialog is None:
            raise KeyError(f"close_dialog called for unknown dialog_id={dialog_id!r}")
        close_tick = tick if tick is not None else dialog.last_activity_tick
        key = _pair_key(dialog.initiator, dialog.target)
        self._pair_to_id.pop(key, None)
        self._last_close_tick[key] = close_tick
        envelope = DialogCloseMsg(
            tick=close_tick,
            dialog_id=dialog_id,
            reason=reason,
        )
        self._emit(envelope)
        return envelope

    # ------------------------------------------------------------------
    # Protocol-external extensions
    # ------------------------------------------------------------------

    def tick(self, world_tick: int, agents: Sequence[AgentView]) -> None:
        """Drive proximity-based admission + timeout close in one step.

        Called by ``WorldRuntime._on_cognition_tick`` after per-agent
        cognition has run. Order:

        1. close any dialogs whose last_activity_tick is older than TIMEOUT
        2. for each co-located pair in reflective zones, probabilistically
           admit (if not already open and past cooldown)

        m9-eval-system P3a-decide: when ``eval_natural_mode`` is True the
        spatial gates are dropped. ``_iter_all_distinct_pairs`` enumerates
        every distinct agent pair regardless of zone, and the reflective-zone
        skip below is bypassed. Cooldown / probability / timeout invariants
        remain active so admission cadence is still natural — only proximity
        is removed.
        """
        self._close_timed_out(world_tick)
        if self.eval_natural_mode:
            pair_iter = _iter_all_distinct_pairs(agents)
        else:
            pair_iter = _iter_colocated_pairs(agents)
        for a, b in pair_iter:
            if not self.eval_natural_mode and a.zone not in _REFLECTIVE_ZONES:
                continue
            key = _pair_key(a.agent_id, b.agent_id)
            if key in self._pair_to_id:
                continue
            last_close = self._last_close_tick.get(key)
            if last_close is not None and world_tick - last_close < self.COOLDOWN_TICKS:
                continue
            if self._rng.random() > self.AUTO_FIRE_PROB_PER_TICK:
                continue
            self.schedule_initiate(a.agent_id, b.agent_id, a.zone, world_tick)

    def get_dialog_id(self, agent_a: str, agent_b: str) -> str | None:
        """Return the open dialog id for the (a, b) pair if any, else None."""
        return self._pair_to_id.get(_pair_key(agent_a, agent_b))

    @property
    def open_count(self) -> int:
        return len(self._open)

    def transcript_of(self, dialog_id: str) -> list[DialogTurnMsg]:
        dialog = self._open.get(dialog_id)
        return list(dialog.turns) if dialog is not None else []

    def iter_open_dialogs(self) -> Iterator[tuple[str, str, str, Zone]]:
        """Yield ``(dialog_id, initiator_id, target_id, zone)`` for each open dialog.

        Added for ``m5-orchestrator-integration``: the per-tick turn driver in
        :class:`~erre_sandbox.world.tick.WorldRuntime` needs to enumerate every
        open dialog to decide budget / speaker / turn generation. Read-only
        — callers must not mutate the scheduler's state via the yielded ids
        except through the existing ``record_turn`` / ``close_dialog`` surface.
        """
        for did, dialog in self._open.items():
            yield did, dialog.initiator, dialog.target, dialog.zone

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _close_timed_out(self, world_tick: int) -> None:
        if self.golden_baseline_mode:
            # m9-eval-system P2b: stimulus phase uses long expected_turn_count
            # (1-3) per stimulus; the driver explicitly closes each dialog so
            # the natural inactivity timeout is suppressed to avoid races
            # between driver close and tick() auto-close.
            return
        expired: list[str] = [
            did
            for did, d in self._open.items()
            if world_tick - d.last_activity_tick >= self.TIMEOUT_TICKS
        ]
        for did in expired:
            self.close_dialog(did, reason="timeout", tick=world_tick)

    def _emit(self, envelope: ControlEnvelope) -> None:
        try:
            self._sink(envelope)
        except Exception:
            # We refuse to let a sink failure desync scheduler state — log and
            # continue. The sink is the gateway's responsibility; if it is
            # broken that is a gateway-layer bug, not ours.
            logger.exception(
                "Dialog scheduler sink raised for envelope kind=%s",
                envelope.kind,
            )


# ---------------------------------------------------------------------------
# Module-private helpers
# ---------------------------------------------------------------------------


def _allocate_dialog_id() -> str:
    return f"d_{uuid.uuid4().hex[:8]}"


def _iter_colocated_pairs(
    agents: Iterable[AgentView],
) -> Iterator[tuple[AgentView, AgentView]]:
    """Yield (a, b) pairs of distinct agents sharing the same zone.

    Each unordered pair is yielded exactly once with a stable ``a.agent_id``
    < ``b.agent_id`` ordering, so callers can use the first entry as the
    canonical initiator without extra sorting.
    """
    sorted_agents = sorted(agents, key=lambda v: v.agent_id)
    for i, a in enumerate(sorted_agents):
        for b in sorted_agents[i + 1 :]:
            if a.zone == b.zone:
                yield a, b


def _iter_all_distinct_pairs(
    agents: Iterable[AgentView],
) -> Iterator[tuple[AgentView, AgentView]]:
    """Yield every distinct ordered pair regardless of zone.

    m9-eval-system P3a-decide: used by ``tick()`` when
    ``eval_natural_mode=True``. The zone field on the leading element is
    still meaningful (it becomes the dialog's recorded zone via the
    ``schedule_initiate`` envelope), but pair eligibility itself does not
    depend on zone equality.
    """
    sorted_agents = sorted(agents, key=lambda v: v.agent_id)
    for i, a in enumerate(sorted_agents):
        for b in sorted_agents[i + 1 :]:
            yield a, b


__all__ = [
    # Re-exported from :mod:`erre_sandbox.schemas` for import ergonomics in
    # callers that already reach into this module for the scheduler.
    "AgentView",
    "InMemoryDialogScheduler",
]

exec
/bin/zsh -lc 'git status --short' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
 M src/erre_sandbox/cli/eval_run_golden.py
 M src/erre_sandbox/integration/dialog.py
?? .steering/20260430-m9-eval-system/codex-review-prompt-natural-gating.md
?? .steering/20260430-m9-eval-system/design-natural-gating-fix.md
?? tests/test_integration/test_dialog_eval_natural_mode.py

exec
/bin/zsh -lc 'git diff -- src/erre_sandbox/integration/dialog.py src/erre_sandbox/cli/eval_run_golden.py tests/test_integration/test_dialog_eval_natural_mode.py' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
diff --git a/src/erre_sandbox/cli/eval_run_golden.py b/src/erre_sandbox/cli/eval_run_golden.py
index c01494c..e2d9581 100644
--- a/src/erre_sandbox/cli/eval_run_golden.py
+++ b/src/erre_sandbox/cli/eval_run_golden.py
@@ -938,6 +938,11 @@ async def capture_natural(  # noqa: C901, PLR0915 — composition root mirrors b
         rng=scheduler_rng,
         turn_sink=duckdb_sink,
         golden_baseline_mode=False,
+        # P3a-decide gating fix: bypass zone-equality so the 3 personas can
+        # sustain dialog after LLM destination_zone scatters them out of
+        # AGORA. See .steering/20260430-m9-eval-system/design-natural-gating-fix.md
+        # for root-cause analysis.
+        eval_natural_mode=True,
     )
     runtime.attach_dialog_scheduler(scheduler)
 
diff --git a/src/erre_sandbox/integration/dialog.py b/src/erre_sandbox/integration/dialog.py
index 7353817..8d66dfc 100644
--- a/src/erre_sandbox/integration/dialog.py
+++ b/src/erre_sandbox/integration/dialog.py
@@ -107,6 +107,7 @@ class InMemoryDialogScheduler:
         rng: Random | None = None,
         turn_sink: Callable[[DialogTurnMsg], None] | None = None,
         golden_baseline_mode: bool = False,
+        eval_natural_mode: bool = False,
     ) -> None:
         self._sink = envelope_sink
         self._rng = rng if rng is not None else Random()  # noqa: S311 — non-crypto
@@ -124,6 +125,19 @@ class InMemoryDialogScheduler:
         # (200 turn, mode=True) and natural-dialog phase (300 turn,
         # mode=False) within the same scheduler instance / MemoryStore.
         self.golden_baseline_mode: bool = golden_baseline_mode
+        # m9-eval-system P3a-decide (design-natural-gating-fix.md): when True
+        # the eval natural-condition pilot bypasses zone-equality and
+        # reflective-zone gates inside ``tick()`` and ``schedule_initiate()``
+        # so 3 personas can sustain dialog after LLM-driven destination_zone
+        # scatters them across study/peripatos/chashitsu. Cooldown / probability
+        # / timeout / self-dialog reject / double-open reject all remain active
+        # so admission cadence is still natural — only the spatial constraint
+        # is dropped. Orthogonal to ``golden_baseline_mode``: stimulus phase
+        # uses ``golden_baseline_mode=True`` (driver controls everything),
+        # natural phase uses ``eval_natural_mode=True`` (proximity-free
+        # logical co-location). Default False keeps M4-frozen Protocol
+        # behaviour for live multi-agent runs.
+        self.eval_natural_mode: bool = eval_natural_mode
         self._open: dict[str, _OpenDialog] = {}
         self._pair_to_id: dict[frozenset[str], str] = {}
         # Bounded by C(N, 2) for N agents — M4 targets N≤3 so this cannot
@@ -153,10 +167,17 @@ class InMemoryDialogScheduler:
         """
         if initiator_id == target_id:
             return None
-        if zone not in _REFLECTIVE_ZONES and not self.golden_baseline_mode:
+        if (
+            zone not in _REFLECTIVE_ZONES
+            and not self.golden_baseline_mode
+            and not self.eval_natural_mode
+        ):
             # m9-eval-system P2b: golden baseline stimulus battery includes
             # ``Zone.STUDY`` (Kant Wachsmuth/RoleEval, Nietzsche aphoristic
             # bursts) — bypass the natural-dialog cultural restriction.
+            # m9-eval-system P3a-decide: eval natural condition lets agents
+            # wander out of reflective zones (LLM-driven destination_zone)
+            # and we still want them to dialog — bypass zone gate too.
             return None
         key = _pair_key(initiator_id, target_id)
         if key in self._pair_to_id:
@@ -278,10 +299,21 @@ class InMemoryDialogScheduler:
         1. close any dialogs whose last_activity_tick is older than TIMEOUT
         2. for each co-located pair in reflective zones, probabilistically
            admit (if not already open and past cooldown)
+
+        m9-eval-system P3a-decide: when ``eval_natural_mode`` is True the
+        spatial gates are dropped. ``_iter_all_distinct_pairs`` enumerates
+        every distinct agent pair regardless of zone, and the reflective-zone
+        skip below is bypassed. Cooldown / probability / timeout invariants
+        remain active so admission cadence is still natural — only proximity
+        is removed.
         """
         self._close_timed_out(world_tick)
-        for a, b in _iter_colocated_pairs(agents):
-            if a.zone not in _REFLECTIVE_ZONES:
+        if self.eval_natural_mode:
+            pair_iter = _iter_all_distinct_pairs(agents)
+        else:
+            pair_iter = _iter_colocated_pairs(agents)
+        for a, b in pair_iter:
+            if not self.eval_natural_mode and a.zone not in _REFLECTIVE_ZONES:
                 continue
             key = _pair_key(a.agent_id, b.agent_id)
             if key in self._pair_to_id:
@@ -374,6 +406,23 @@ def _iter_colocated_pairs(
                 yield a, b
 
 
+def _iter_all_distinct_pairs(
+    agents: Iterable[AgentView],
+) -> Iterator[tuple[AgentView, AgentView]]:
+    """Yield every distinct ordered pair regardless of zone.
+
+    m9-eval-system P3a-decide: used by ``tick()`` when
+    ``eval_natural_mode=True``. The zone field on the leading element is
+    still meaningful (it becomes the dialog's recorded zone via the
+    ``schedule_initiate`` envelope), but pair eligibility itself does not
+    depend on zone equality.
+    """
+    sorted_agents = sorted(agents, key=lambda v: v.agent_id)
+    for i, a in enumerate(sorted_agents):
+        for b in sorted_agents[i + 1 :]:
+            yield a, b
+
+
 __all__ = [
     # Re-exported from :mod:`erre_sandbox.schemas` for import ergonomics in
     # callers that already reach into this module for the scheduler.

exec
/bin/zsh -lc "sed -n '1,360p' tests/test_integration/test_dialog_eval_natural_mode.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
"""Tests for ``InMemoryDialogScheduler.eval_natural_mode`` flag.

m9-eval-system P3a-decide Task 1 — natural runtime gating bug fix.

Background (from `.steering/20260430-m9-eval-system/design-natural-gating-fix.md`):
G-GEAR pilot 採取で natural condition (3 persona × 30 focal target) が
**初動 burst 2-3 dialogs 後に admission が完全停止**する症状が観測された。
root cause は LLM-driven ``destination_zone`` で agents が AGORA から散り、
``_iter_colocated_pairs`` の ``a.zone == b.zone`` 制約で 0 pair 返却 →
新規 dialog が立ち上がらない、というもの。``ERRE_ZONE_BIAS_P=0.2`` default
で 80% は LLM zone を honor するため preferred_zones override では救えない。

修正: ``eval_natural_mode: bool = False`` flag を scheduler に追加し、True
のとき ``tick()`` の zone equality / reflective zone 制約を bypass。
cooldown / probability / timeout / 自己 dialog reject / 二重 open reject の
invariant は両 mode で保持される (natural cadence は維持)。

Default ``False`` で既存 1221 PASS は完全互換、``True`` opt-in は CLI
``capture_natural`` のみが指定する。
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING

from erre_sandbox.integration.dialog import (
    AgentView,
    InMemoryDialogScheduler,
)
from erre_sandbox.schemas import (
    DialogCloseMsg,
    DialogInitiateMsg,
    DialogTurnMsg,
    Zone,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.schemas import ControlEnvelope


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collector() -> tuple[list[ControlEnvelope], Callable[[ControlEnvelope], None]]:
    captured: list[ControlEnvelope] = []

    def sink(env: ControlEnvelope) -> None:
        captured.append(env)

    return captured, sink


def _always_fire() -> Random:
    """RNG whose ``random()`` always returns 0.0 (≤ AUTO_FIRE_PROB)."""
    r = Random(0)
    r.random = lambda: 0.0  # type: ignore[method-assign]
    return r


def _never_fire() -> Random:
    """RNG whose ``random()`` always returns 0.99 (> AUTO_FIRE_PROB)."""
    r = Random(0)
    r.random = lambda: 0.99  # type: ignore[method-assign]
    return r


# ---------------------------------------------------------------------------
# Default constructor: eval_natural_mode is False (M4-frozen behaviour)
# ---------------------------------------------------------------------------


def test_default_constructor_keeps_eval_natural_mode_false() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    assert scheduler.eval_natural_mode is False


def test_eval_natural_mode_is_independent_of_golden_baseline_mode() -> None:
    """Two flags address orthogonal concerns and can be set independently."""
    _captured, sink = _collector()
    scheduler_a = InMemoryDialogScheduler(
        envelope_sink=sink, eval_natural_mode=True, golden_baseline_mode=False
    )
    scheduler_b = InMemoryDialogScheduler(
        envelope_sink=sink, eval_natural_mode=False, golden_baseline_mode=True
    )
    assert scheduler_a.eval_natural_mode is True
    assert scheduler_a.golden_baseline_mode is False
    assert scheduler_b.eval_natural_mode is False
    assert scheduler_b.golden_baseline_mode is True


# ---------------------------------------------------------------------------
# Bug repro (default False): zone drift halts admission
# ---------------------------------------------------------------------------


def test_default_mode_admission_stops_when_agents_scatter() -> None:
    """Document the gating bug: when agents drift to different zones the
    proximity-only ``tick()`` cannot admit new dialogs.

    This mirrors the G-GEAR pilot natural-condition pattern: initial burst
    fires while all 3 personas are still in AGORA, then LLM-driven
    ``destination_zone`` scatters them and ``_iter_colocated_pairs``
    returns nothing → new admissions plateau at 0.
    """
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=False
    )

    # Tick 0 — all three in AGORA. Three pairs eligible, all admit.
    co_located = [
        AgentView(agent_id="kant", zone=Zone.AGORA, tick=0),
        AgentView(agent_id="nietzsche", zone=Zone.AGORA, tick=0),
        AgentView(agent_id="rikyu", zone=Zone.AGORA, tick=0),
    ]
    scheduler.tick(world_tick=0, agents=co_located)
    assert scheduler.open_count == 3, (
        "all three pairs should admit on tick 0 with rng=always_fire"
    )

    # Close all three (simulate budget exhaustion, much sooner than timeout).
    for did, _i, _t, _z in list(scheduler.iter_open_dialogs()):
        scheduler.close_dialog(did, reason="exhausted", tick=0)
    assert scheduler.open_count == 0

    # Advance world tick past COOLDOWN_TICKS so cooldown is no longer the gate.
    far_tick = scheduler.COOLDOWN_TICKS + 5

    # Now agents have scattered (LLM destination_zone moved them).
    scattered = [
        AgentView(agent_id="kant", zone=Zone.STUDY, tick=far_tick),
        AgentView(agent_id="nietzsche", zone=Zone.PERIPATOS, tick=far_tick),
        AgentView(agent_id="rikyu", zone=Zone.CHASHITSU, tick=far_tick),
    ]
    scheduler.tick(world_tick=far_tick, agents=scattered)
    assert scheduler.open_count == 0, (
        "BUG REPRO: with default mode, scattered agents have 0 co-located "
        "pairs, so even after cooldown expires no admit fires"
    )


# ---------------------------------------------------------------------------
# Fix: eval_natural_mode=True admits any pair regardless of zone
# ---------------------------------------------------------------------------


def test_eval_natural_mode_admits_pairs_across_different_zones() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
    )
    scattered = [
        AgentView(agent_id="kant", zone=Zone.STUDY, tick=0),
        AgentView(agent_id="nietzsche", zone=Zone.PERIPATOS, tick=0),
        AgentView(agent_id="rikyu", zone=Zone.CHASHITSU, tick=0),
    ]
    scheduler.tick(world_tick=0, agents=scattered)
    assert scheduler.open_count == 3, (
        "all three distinct pairs should admit regardless of zone"
    )


def test_eval_natural_mode_admits_two_study_agents() -> None:
    """``Zone.STUDY`` is excluded from ``_REFLECTIVE_ZONES`` in default
    mode but eval natural treats all pairs as eligible — including STUDY-STUDY."""
    captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
    )
    agents = [
        AgentView(agent_id="kant", zone=Zone.STUDY, tick=0),
        AgentView(agent_id="nietzsche", zone=Zone.STUDY, tick=0),
    ]
    scheduler.tick(world_tick=0, agents=agents)
    assert scheduler.open_count == 1
    initiates = [env for env in captured if isinstance(env, DialogInitiateMsg)]
    assert len(initiates) == 1


# ---------------------------------------------------------------------------
# Invariants preserved in eval_natural_mode
# ---------------------------------------------------------------------------


def test_eval_natural_mode_preserves_self_dialog_reject() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, eval_natural_mode=True
    )
    result = scheduler.schedule_initiate("kant", "kant", Zone.AGORA, tick=0)
    assert result is None


def test_eval_natural_mode_preserves_double_open_reject() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, eval_natural_mode=True
    )
    first = scheduler.schedule_initiate("kant", "rikyu", Zone.AGORA, tick=0)
    assert isinstance(first, DialogInitiateMsg)
    second = scheduler.schedule_initiate("kant", "rikyu", Zone.AGORA, tick=1)
    assert second is None


def test_eval_natural_mode_preserves_cooldown_via_tick() -> None:
    """Cooldown still applies after a close — tick() must not re-admit
    the same pair within ``COOLDOWN_TICKS`` even with the zone bypass."""
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
    )
    agents = [
        AgentView(agent_id="kant", zone=Zone.STUDY, tick=0),
        AgentView(agent_id="rikyu", zone=Zone.GARDEN, tick=0),
    ]
    scheduler.tick(world_tick=0, agents=agents)
    assert scheduler.open_count == 1
    [(did, _i, _t, _z)] = list(scheduler.iter_open_dialogs())
    scheduler.close_dialog(did, reason="exhausted", tick=0)

    # Within cooldown window — no re-admit.
    for w in range(1, scheduler.COOLDOWN_TICKS):
        scheduler.tick(world_tick=w, agents=agents)
        assert scheduler.open_count == 0, (
            f"cooldown breached at tick {w}: same pair re-admitted within "
            f"{scheduler.COOLDOWN_TICKS} ticks"
        )

    # Past cooldown — admit again.
    scheduler.tick(world_tick=scheduler.COOLDOWN_TICKS, agents=agents)
    assert scheduler.open_count == 1


def test_eval_natural_mode_preserves_probability_gate() -> None:
    """RNG > AUTO_FIRE_PROB still suppresses admit even with zone bypass."""
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, rng=_never_fire(), eval_natural_mode=True
    )
    agents = [
        AgentView(agent_id="kant", zone=Zone.STUDY, tick=0),
        AgentView(agent_id="rikyu", zone=Zone.GARDEN, tick=0),
    ]
    scheduler.tick(world_tick=0, agents=agents)
    assert scheduler.open_count == 0


def test_eval_natural_mode_preserves_timeout_close() -> None:
    """In-flight dialogs still time out when ``last_activity_tick`` is stale."""
    captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
    )
    agents = [
        AgentView(agent_id="kant", zone=Zone.STUDY, tick=0),
        AgentView(agent_id="rikyu", zone=Zone.GARDEN, tick=0),
    ]
    scheduler.tick(world_tick=0, agents=agents)
    assert scheduler.open_count == 1

    # No activity recorded for TIMEOUT_TICKS ticks → tick() should auto-close.
    scheduler.tick(world_tick=scheduler.TIMEOUT_TICKS, agents=agents)
    close_envs = [e for e in captured if isinstance(e, DialogCloseMsg)]
    assert len(close_envs) == 1
    assert close_envs[0].reason == "timeout"
    assert scheduler.open_count == 0


# ---------------------------------------------------------------------------
# Sustained admission scenario (Red→Green core)
# ---------------------------------------------------------------------------


def test_eval_natural_mode_sustains_admission_after_initial_burst() -> None:
    """Reproduce the natural-condition observation pattern: initial burst,
    then continued admission across many ticks despite zone drift.

    Counter-example to the bug repro above: with eval_natural_mode=True,
    even after agents scatter, admit fires resume after cooldown.
    """
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
    )

    agents_initial = [
        AgentView(agent_id="kant", zone=Zone.AGORA, tick=0),
        AgentView(agent_id="nietzsche", zone=Zone.AGORA, tick=0),
        AgentView(agent_id="rikyu", zone=Zone.AGORA, tick=0),
    ]
    scheduler.tick(world_tick=0, agents=agents_initial)
    assert scheduler.open_count == 3

    # Simulate dialog turns + exhaustion close at tick 6 (mock budget=6).
    open_now = list(scheduler.iter_open_dialogs())
    for did, init_id, target_id, _z in open_now:
        # Stamp activity at tick 6 so close anchors cooldown there.
        scheduler.record_turn(
            DialogTurnMsg(
                tick=6,
                dialog_id=did,
                speaker_id=init_id,
                addressee_id=target_id,
                turn_index=0,
                utterance="warmup",
            )
        )
        scheduler.close_dialog(did, reason="exhausted", tick=6)
    assert scheduler.open_count == 0

    # Now agents scatter. Drive ticks past cooldown and check admit resumes.
    scattered = [
        AgentView(agent_id="kant", zone=Zone.STUDY, tick=40),
        AgentView(agent_id="nietzsche", zone=Zone.PERIPATOS, tick=40),
        AgentView(agent_id="rikyu", zone=Zone.CHASHITSU, tick=40),
    ]
    far_tick = 6 + scheduler.COOLDOWN_TICKS  # 36
    scheduler.tick(world_tick=far_tick, agents=scattered)
    assert scheduler.open_count == 3, (
        "after cooldown expires, all three pairs should re-admit even "
        "though every agent is in a different zone"
    )

exec
/bin/zsh -lc "rg -n \"class DialogScheduler|Protocol|schedule_initiate|InMemoryDialogScheduler|tick\\(\" src tests | head -120" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
src/erre_sandbox/integration/dialog_turn.py:316:      Protocol ties our hands on what :meth:`generate_turn` receives (only
src/erre_sandbox/integration/dialog_turn.py:318:      gap without touching the frozen Protocol signature.
src/erre_sandbox/integration/dialog_turn.py:322:    WARNING log, per the Protocol contract that callers treat ``None`` as a
src/erre_sandbox/world/tick.py:568:        # synchronously inside ``InMemoryDialogScheduler.record_turn``.
src/erre_sandbox/world/tick.py:808:    async def _on_physics_tick(self) -> None:
src/erre_sandbox/world/tick.py:1038:    async def _on_cognition_tick(self) -> None:
src/erre_sandbox/world/tick.py:1080:        self._run_dialog_tick()
src/erre_sandbox/world/tick.py:1082:            await self._drive_dialog_turns(self._current_world_tick())
src/erre_sandbox/world/tick.py:1084:    def _run_dialog_tick(self) -> None:
src/erre_sandbox/world/tick.py:1096:        # The scheduler type is a Protocol frozen in schemas.py §7.5 —
src/erre_sandbox/world/tick.py:1098:        # :class:`InMemoryDialogScheduler`. Callers supplying a custom
src/erre_sandbox/world/tick.py:1105:            tick_fn(self._current_world_tick(), views)
src/erre_sandbox/world/tick.py:1110:    def _current_world_tick(self) -> int:
src/erre_sandbox/world/tick.py:1136:        consults :meth:`InMemoryDialogScheduler.iter_open_dialogs` and:
src/erre_sandbox/world/tick.py:1150:           :meth:`InMemoryDialogScheduler.record_turn` (updates transcript and
src/erre_sandbox/world/tick.py:1270:    async def _on_heartbeat_tick(self) -> None:
src/erre_sandbox/world/tick.py:1273:                tick=self._current_world_tick(),
src/erre_sandbox/erre/fsm.py:180:        ``zone`` and ``tick`` are part of the Protocol signature and are
src/erre_sandbox/integration/__init__.py:33:from erre_sandbox.integration.dialog import AgentView, InMemoryDialogScheduler
src/erre_sandbox/integration/__init__.py:67:    "InMemoryDialogScheduler",
tests/test_schemas_m5.py:8:* ``ERREModeTransitionPolicy`` / ``DialogTurnGenerator`` Protocols are
tests/test_schemas_m5.py:21:Protocol shape checks are intentionally minimal (``get_type_hints`` on a few
tests/test_schemas_m5.py:118:# ---------- §7.5 Protocol imports and shape ---------------------------------
tests/test_schemas_m5.py:122:    # Protocols are classes at runtime; membership of typing.Protocol is
src/erre_sandbox/integration/dialog.py:1:"""In-memory implementation of the M4 :class:`DialogScheduler` Protocol.
src/erre_sandbox/integration/dialog.py:12:* The Protocol is frozen at M4 foundation and says ``schedule_initiate``
src/erre_sandbox/integration/dialog.py:15:  Protocol API only get a signal of "was this admitted"; they MUST NOT
src/erre_sandbox/integration/dialog.py:18:* ``tick()`` is an extension method (not part of the Protocol) that drives
src/erre_sandbox/integration/dialog.py:79:class InMemoryDialogScheduler:
src/erre_sandbox/integration/dialog.py:130:        # reflective-zone gates inside ``tick()`` and ``schedule_initiate()``
src/erre_sandbox/integration/dialog.py:138:        # logical co-location). Default False keeps M4-frozen Protocol
src/erre_sandbox/integration/dialog.py:146:        # ``tick()``; for now the memory footprint is irrelevant.
src/erre_sandbox/integration/dialog.py:150:    # Protocol methods (frozen in schemas.py §7.5)
src/erre_sandbox/integration/dialog.py:153:    def schedule_initiate(
src/erre_sandbox/integration/dialog.py:163:        rely on the Protocol signature, BUT the envelope is already on the
src/erre_sandbox/integration/dialog.py:257:        that only see the M4-frozen Protocol surface continue to behave as
src/erre_sandbox/integration/dialog.py:290:    # Protocol-external extensions
src/erre_sandbox/integration/dialog.py:293:    def tick(self, world_tick: int, agents: Sequence[AgentView]) -> None:
src/erre_sandbox/integration/dialog.py:326:            self.schedule_initiate(a.agent_id, b.agent_id, a.zone, world_tick)
src/erre_sandbox/integration/dialog.py:361:            # between driver close and tick() auto-close.
src/erre_sandbox/integration/dialog.py:414:    m9-eval-system P3a-decide: used by ``tick()`` when
src/erre_sandbox/integration/dialog.py:417:    ``schedule_initiate`` envelope), but pair eligibility itself does not
src/erre_sandbox/integration/dialog.py:430:    "InMemoryDialogScheduler",
tests/test_evidence/test_golden_baseline.py:4::class:`InMemoryDialogScheduler`. These tests verify the contract layers
tests/test_evidence/test_golden_baseline.py:9:   per stimulus through ``schedule_initiate`` / ``record_turn`` /
tests/test_evidence/test_golden_baseline.py:47:from erre_sandbox.integration.dialog import InMemoryDialogScheduler
tests/test_evidence/test_golden_baseline.py:82:    InMemoryDialogScheduler, list[ControlEnvelope], list[DialogTurnMsg]
tests/test_evidence/test_golden_baseline.py:85:    scheduler = InMemoryDialogScheduler(
tests/test_evidence/test_golden_baseline.py:312:    scheduler = InMemoryDialogScheduler(
src/erre_sandbox/integration/gateway.py:33:from typing import TYPE_CHECKING, ClassVar, Final, Protocol
src/erre_sandbox/integration/gateway.py:120:class _RuntimeLike(Protocol):
src/erre_sandbox/schemas.py:9:* §1 Protocol constants
src/erre_sandbox/schemas.py:17:* §7.5 Protocols — DialogScheduler (M4) / ERREModeTransitionPolicy (M5)
src/erre_sandbox/schemas.py:36:from typing import Annotated, Final, Literal, NamedTuple, Protocol, TypeAlias
src/erre_sandbox/schemas.py:41:# §1 Protocol constants
src/erre_sandbox/schemas.py:59:LLM-generation milestone. Two new Protocols (:class:`ERREModeTransitionPolicy`,
src/erre_sandbox/schemas.py:1319:class DialogScheduler(Protocol):
src/erre_sandbox/schemas.py:1324:    Protocol is frozen here so that ``cognition`` and ``world`` can type-hint
src/erre_sandbox/schemas.py:1331:    def schedule_initiate(
src/erre_sandbox/schemas.py:1394:class ERREModeTransitionPolicy(Protocol):
src/erre_sandbox/schemas.py:1399:    ``m5-erre-mode-fsm``. This Protocol is frozen here so ``cognition`` and
src/erre_sandbox/schemas.py:1426:class DialogTurnGenerator(Protocol):
src/erre_sandbox/schemas.py:1432:    Freezing this Protocol in the schemas module lets the M5 orchestrator
src/erre_sandbox/cli/eval_run_golden.py:17:  CognitionCycle + WorldRuntime + InMemoryDialogScheduler +
src/erre_sandbox/cli/eval_run_golden.py:92:from erre_sandbox.integration.dialog import InMemoryDialogScheduler
src/erre_sandbox/cli/eval_run_golden.py:173:    :meth:`InMemoryDialogScheduler.record_turn`, which is correct for live
src/erre_sandbox/cli/eval_run_golden.py:716:    scheduler = InMemoryDialogScheduler(
src/erre_sandbox/cli/eval_run_golden.py:770:    # firing. The driver calls schedule_initiate first, the envelope sink
src/erre_sandbox/cli/eval_run_golden.py:936:    scheduler = InMemoryDialogScheduler(
src/erre_sandbox/contracts/eval_paths.py:12:   :class:`RawTrainingRelation` Protocol that exposes **only** raw rows
src/erre_sandbox/contracts/eval_paths.py:39:from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable
src/erre_sandbox/contracts/eval_paths.py:217:# Constrained relation Protocol
src/erre_sandbox/contracts/eval_paths.py:222:class RawTrainingRelation(Protocol):
tests/test_cognition/test_erre_mode_events.py:60:        observations: Sequence[Observation],  # noqa: ARG002 — Protocol contract
tests/test_cognition/test_erre_mode_events.py:180:    """Protocol-violating "return current" is treated as a no-op — no event."""
tests/test_world/test_temporal_events.py:166:    await runtime._on_physics_tick()
tests/test_memory/test_store.py:705:def test_add_bias_event_allows_multiple_per_tick(store: MemoryStore) -> None:
tests/test_world/test_tick.py:346:    async def test_move_msg_drives_next_physics_tick(
src/erre_sandbox/cognition/reflection.py:238:    def record_tick(self, agent_id: str) -> int:
src/erre_sandbox/cognition/reflection.py:271:        ticks_since = self.record_tick(agent_state.agent_id)
src/erre_sandbox/evidence/golden_baseline.py:3:This module owns nothing inside :class:`InMemoryDialogScheduler`; it
src/erre_sandbox/evidence/golden_baseline.py:5:(``schedule_initiate`` / ``record_turn`` / ``close_dialog``). When the
src/erre_sandbox/evidence/golden_baseline.py:56:    from erre_sandbox.integration.dialog import InMemoryDialogScheduler
src/erre_sandbox/evidence/golden_baseline.py:306:    scheduler: InMemoryDialogScheduler
src/erre_sandbox/evidence/golden_baseline.py:375:        open_tick = self._allocate_tick()
src/erre_sandbox/evidence/golden_baseline.py:376:        admitted = self.scheduler.schedule_initiate(
src/erre_sandbox/evidence/golden_baseline.py:394:            turn_tick = self._allocate_tick()
src/erre_sandbox/evidence/golden_baseline.py:419:        close_tick = self._allocate_tick()
src/erre_sandbox/evidence/golden_baseline.py:434:    def _allocate_tick(self) -> int:
tests/conftest.py:202:def _build_world_tick(tick: int, overrides: dict[str, Any]) -> WorldTickMsg:
tests/test_cognition/test_reflection.py:104:        reflector.record_tick("a")
tests/test_cognition/test_reflection.py:105:        reflector.record_tick("a")
tests/test_cognition/test_reflection.py:106:        assert reflector.record_tick("a") == 3
tests/test_cognition/test_reflection.py:107:        assert reflector.record_tick("b") == 1
tests/test_cognition/test_reflection.py:109:        assert reflector.record_tick("a") == 1
src/erre_sandbox/bootstrap.py:34:from erre_sandbox.integration.dialog import InMemoryDialogScheduler
src/erre_sandbox/bootstrap.py:261:    :class:`InMemoryDialogScheduler.record_turn`: it inserts a
src/erre_sandbox/bootstrap.py:505:        # are caught inside ``InMemoryDialogScheduler.record_turn`` so a
src/erre_sandbox/bootstrap.py:552:        scheduler = InMemoryDialogScheduler(
src/erre_sandbox/cognition/cycle.py:570:        If the policy violates its Protocol contract and returns a value
src/erre_sandbox/cognition/cycle.py:581:        :class:`~erre_sandbox.schemas.ERREModeTransitionPolicy` Protocol
src/erre_sandbox/evidence/eval_store.py:177:    # Protocol surface
src/erre_sandbox/memory/store.py:836:        Intended for the :class:`InMemoryDialogScheduler` sink which runs on
tests/test_cognition/test_cycle_erre_fsm.py:208:    # Protocol contract by returning the current mode. The cycle must not
tests/test_integration/test_slice_gamma_e2e.py:5:1. ``InMemoryDialogScheduler.record_turn`` invokes the relational sink
tests/test_integration/test_slice_gamma_e2e.py:40:from erre_sandbox.integration.dialog import InMemoryDialogScheduler
tests/test_integration/test_slice_gamma_e2e.py:117:def _open_dialog(scheduler: InMemoryDialogScheduler, *, tick: int) -> str:
tests/test_integration/test_slice_gamma_e2e.py:118:    initiate = scheduler.schedule_initiate(
tests/test_integration/test_slice_gamma_e2e.py:140:    scheduler = InMemoryDialogScheduler(
tests/test_integration/test_slice_gamma_e2e.py:256:    scheduler = InMemoryDialogScheduler(
tests/test_integration/test_slice_delta_e2e.py:43:from erre_sandbox.integration.dialog import InMemoryDialogScheduler
tests/test_integration/test_slice_delta_e2e.py:108:def _open_dialog(scheduler: InMemoryDialogScheduler, *, tick: int) -> str:
tests/test_integration/test_slice_delta_e2e.py:109:    initiate = scheduler.schedule_initiate(
tests/test_integration/test_slice_delta_e2e.py:131:    scheduler = InMemoryDialogScheduler(envelope_sink=captured.append, turn_sink=sink)
tests/test_integration/test_slice_delta_e2e.py:184:    scheduler = InMemoryDialogScheduler(envelope_sink=lambda _: None, turn_sink=sink)
tests/test_integration/test_slice_delta_e2e.py:216:    scheduler = InMemoryDialogScheduler(envelope_sink=lambda _: None, turn_sink=sink)
tests/test_integration/test_slice_delta_e2e.py:254:    scheduler = InMemoryDialogScheduler(envelope_sink=lambda _: None, turn_sink=sink)
tests/test_integration/test_slice_delta_e2e.py:302:    scheduler = InMemoryDialogScheduler(envelope_sink=lambda _: None, turn_sink=sink)
tests/test_integration/test_slice_delta_e2e.py:369:    scheduler = InMemoryDialogScheduler(envelope_sink=lambda _: None, turn_sink=sink)
tests/test_integration/test_slice_delta_e2e.py:416:    scheduler = InMemoryDialogScheduler(envelope_sink=lambda _: None, turn_sink=sink)

exec
/bin/zsh -lc "sed -n '1,220p' .steering/20260430-m9-eval-system/design-natural-gating-fix.md" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,260p' src/erre_sandbox/schemas.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
"""Pydantic v2 data contract for ERRE-Sandbox (T05 schemas-freeze).

This module is the Contract-First boundary between MacBook (orchestrator + Godot
viewer) and G-GEAR (inference + simulation + memory). It defines the wire types
exchanged over WebSocket and the in-memory representations shared across layers.

Sections
--------
* §1 Protocol constants
* §2 Enums
* §3 Persona (static, YAML-loaded) — incl. ``AgentSpec`` (M4)
* §4 AgentState (dynamic, per-tick)
* §4.5 Run lifecycle — ``RunLifecycleState`` (M8, run-level epoch phase)
* §5 Observation (event, discriminated by ``event_type``)
* §6 Memory — incl. ``ReflectionEvent`` / ``SemanticMemoryRecord`` (M4)
* §7 ControlEnvelope (message, discriminated by ``kind``) — incl. ``Dialog*`` (M4)
* §7.5 Protocols — DialogScheduler (M4) / ERREModeTransitionPolicy (M5)
  / DialogTurnGenerator (M5), interface-only
* §8 Public surface (``__all__``)

Design choices are recorded in ``.steering/20260418-schemas-freeze/decisions.md``
(M2), ``.steering/20260420-m4-contracts-freeze/decisions.md`` (M4 foundation),
and ``.steering/20260420-m5-contracts-freeze/decisions.md`` (M5 FSM + dialog_turn).
This module MUST NOT import any other ``erre_sandbox.*`` module
(see ``docs/repository-structure.md`` §4 and the ``architecture-rules`` skill).
"""

from __future__ import annotations

from collections.abc import (
    Iterator,  # noqa: TC003 — resolved at runtime by get_type_hints in tests
    Sequence,  # noqa: TC003 — resolved at runtime by get_type_hints in tests
)
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Final, Literal, NamedTuple, Protocol, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# §1 Protocol constants
# =============================================================================

SCHEMA_VERSION: Final[str] = "0.10.0-m7h"
"""Semantic version of the wire contract.

Bumped whenever any on-wire model gains or loses a field, or a discriminator
value is added/removed. Consumed by ``HandshakeMsg`` for early mismatch
detection between MacBook / G-GEAR / Godot peers.

M4 bump (0.1.0-m2 → 0.2.0-m4): adds the AgentSpec / ReflectionEvent /
SemanticMemoryRecord primitives and the dialog_initiate / dialog_turn /
dialog_close ControlEnvelope variants required by the 3-agent milestone.
See ``.steering/20260420-m4-contracts-freeze/`` for the rationale.

M5 bump (0.2.0-m4 → 0.3.0-m5): adds the dialog_turn budget / ordering fields
(:attr:`Cognitive.dialog_turn_budget`, :attr:`DialogTurnMsg.turn_index`) and
the ``"exhausted"`` close reason required by the ERRE-mode FSM + dialog_turn
LLM-generation milestone. Two new Protocols (:class:`ERREModeTransitionPolicy`,
:class:`DialogTurnGenerator`) are frozen as interfaces so the four parallel
sub-tasks can type-hint against them.

M6 bump (0.3.0-m5 → 0.4.0-m6): adds four new :class:`Observation` variants
(:class:`AffordanceEvent`, :class:`ProximityEvent`, :class:`TemporalEvent`,
:class:`BiorhythmEvent`) and the :class:`TimeOfDay` enum used by
``TemporalEvent``. All four are additive to the discriminated ``Observation``
union — M5 producers that only emit the original five variants remain
wire-compatible. Firing logic lives in ``world/tick.py`` (Affordance /
Proximity / Temporal) and ``cognition/cycle.py`` (Biorhythm) and is wired
in the M6-A-2b sub-task; the schema bump is taken early so the four
M6-A tracks can type-hint against the frozen contract.

M7γ bump (0.5.0-m8 → 0.6.0-m7g): adds :class:`WorldLayoutMsg` (§7) with
its :class:`ZoneLayout` / :class:`PropLayout` row types, plus three new
default-empty list fields on :class:`ReasoningTrace`
(``observed_objects`` / ``nearby_agents`` / ``retrieved_memories``) so the
xAI :class:`ReasoningPanel` can show *why* a tick produced its decision.
The bump is additive and wire-compatible: the new ``world_layout``
discriminator is independent (no other variant changes), and the three
new ``ReasoningTrace`` fields use ``default_factory=list`` so older M8
producers that emit traces without them remain valid. The minor bump is
required because ``HandshakeMsg`` does a strict version match in
``integration/gateway.py`` and will reject 0.5.0-m8 peers against a
0.6.0-m7g gateway. See ``.steering/20260425-m7-slice-gamma/`` and the
``zany-gathering-teapot`` plan file for the rationale.

M7δ bump (0.6.0-m7g → 0.7.0-m7d): three additive field additions tied to
the Slice δ relationship-loop work (CSDG semi-formula + negative affinity +
2-layer memory bridge). On :class:`RelationshipBond`, the new
``last_interaction_zone: Zone | None`` (§4) records *where* a dyad most
recently interacted so the Godot ``ReasoningPanel`` can render
``"<persona> affinity ±0.NN (N turns, last in <zone> @ tick T)"``. On
:class:`SemanticMemoryRecord`, two new fields support the belief-promotion
bridge: ``belief_kind: Literal["trust","clash","wary","curious","ambivalent"]
| None`` (typed enum so m8-affinity-dynamics Critics can query
``WHERE belief_kind='clash'`` without parsing summary prefixes) and
``confidence: float`` (derivative of ``|affinity| / AFFINITY_UPPER``,
clamped to [0,1] at the write site). Both default to None / 1.0 so older
M7γ producers remain wire-compatible. The ``semantic_memory`` SQLite table
gains two columns via the ``_migrate_semantic_schema`` idempotent migration
pattern at ``memory/store.py``. ``RelationshipBond`` lives in
:class:`AgentState` (in-memory, ``model_copy`` mutation), not in a SQLite
table, so no DB migration is required for the bond field. See
``.steering/20260426-m7-slice-delta/design-final.md`` and the
``m7-slice-compressed-teapot`` plan file for the rationale.

M8 bump (0.4.0-m6 → 0.5.0-m8): adds :class:`EpochPhase` (§2) and
:class:`RunLifecycleState` (§4.5) for the two-phase methodology adopted in
L6 ADR D3 (see ``.steering/20260424-steering-scaling-lora/decisions.md``).
Run-level state (``autonomous`` / ``q_and_a`` / ``evaluation``) is owned by
:class:`~erre_sandbox.world.tick.WorldRuntime`; allowed transitions are
``autonomous → q_and_a → evaluation`` with no reverse. Additive: no existing
wire variant changes, and the new ``RunLifecycleState`` is not (yet) carried
by any :class:`ControlEnvelope` member — consumers that ignore it remain
wire-compatible. The new ``EpochPhase`` name is deliberately distinct from
the gateway-layer ``SessionPhase`` at ``integration/protocol.py`` so the two
orthogonal state machines cannot be confused. See
``.steering/20260425-m8-session-phase-model/`` for the rationale.

M9-A bump (0.9.0-m7z → 0.10.0-m7h): one additive nested field tied to the
event-boundary-observability work. :class:`ReasoningTrace` gains
``trigger_event: TriggerEventTag | None`` so the Godot ``ReasoningPanel``
can render a 1-line "気づきの起点" (kind + zone + ref_id) and the
``BoundaryLayer`` can pulse the originating zone for the focused agent.
The new :class:`TriggerEventTag` carries ``kind`` (Literal of the 9
:class:`Observation` event_types), ``zone: Zone | None``, ``ref_id: str |
None`` (zone_transition→to_zone / affordance→prop_id /
proximity→other_agent_id), and ``secondary_kinds`` ("+N more" hint for
same-tick strong losers). It pins ``model_config =
ConfigDict(extra="forbid")`` so unknown nested keys are rejected at the
wire boundary. Default-None on :class:`ReasoningTrace` keeps M7ζ
producers wire-compatible. The bump from 0.9.0-m7z is required because
``HandshakeMsg`` does a strict version match and the Godot client's
``CLIENT_SCHEMA_VERSION`` must move in lockstep. The minor version is
named ``0.10.0-m7h`` (M7-η) rather than ``0.10.0-m9`` to keep the M7
chronology readable; the M9 namespace is reserved for the LoRA work.
See ``.steering/20260428-event-boundary-observability/design-final.md``
and the Codex review log (``codex-review.md``) for the rationale.

M7ζ bump (0.8.0-m7e → 0.9.0-m7z): two additive fields tied to the Slice ζ
"Live Resonance" panel-context work. :class:`ReasoningTrace` gains
``persona_id: str | None`` so the Godot ``ReasoningPanel`` can render the
persona identity (display_name + 1-line summary) alongside the per-tick
trace without joining to ``AgentState`` at the client. :class:`RelationshipBond`
gains ``latest_belief_kind: Literal[...] | None`` (same value domain as
:attr:`SemanticMemoryRecord.belief_kind`) so the panel can surface the most
recent belief classification (trust / clash / wary / curious / ambivalent)
that was promoted from the dyad's affinity loop, rendered as an icon prefix
next to the bond row. Both default to ``None`` so older M7ε producers remain
wire-compatible. The ``relational_memory`` SQLite table is unaffected
(``RelationshipBond`` is in-memory on :class:`AgentState`). See
``.steering/20260426-m7-slice-zeta-live-resonance/`` and the
``eager-churning-hartmanis`` plan file for the rationale.

Compatibility with M6 payloads:

* Additive and wire-compatible for consumers: no existing ``event_type`` /
  ``kind`` / ``reason`` discriminator gains or loses a value.
* Producers that construct :class:`~erre_sandbox.world.tick.WorldRuntime`
  directly need no change — ``RunLifecycleState`` defaults to
  :attr:`EpochPhase.AUTONOMOUS` so the existing run() behaviour is preserved.

See ``.steering/20260425-m8-session-phase-model/`` for the rationale.
"""


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


# =============================================================================
# §2 Enums
# =============================================================================


class Zone(StrEnum):
    """Five spatial zones of the world (see ``docs/glossary.md``)."""

    STUDY = "study"
    PERIPATOS = "peripatos"
    CHASHITSU = "chashitsu"
    AGORA = "agora"
    GARDEN = "garden"


class ERREModeName(StrEnum):
    """Eight ERRE cognitive modes (see ``persona-erre`` skill for semantics)."""

    PERIPATETIC = "peripatetic"
    CHASHITSU = "chashitsu"
    ZAZEN = "zazen"
    SHU_KATA = "shu_kata"
    HA_DEVIATE = "ha_deviate"
    RI_CREATE = "ri_create"
    DEEP_WORK = "deep_work"
    SHALLOW = "shallow"


class MemoryKind(StrEnum):
    """Four memory faculties of the agent (CoALA-inspired)."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    RELATIONAL = "relational"


class TimeOfDay(StrEnum):
    """Six simulated time-of-day periods used by :class:`TemporalEvent` (M6).

    The world clock quantises wall-clock into these buckets so the FSM and
    LLM can reason about circadian context without float comparisons. The
    mapping from hour to period is owned by ``world/tick.py``; this enum
    only freezes the vocabulary on the wire.
    """

    DAWN = "dawn"
    MORNING = "morning"
    NOON = "noon"
    AFTERNOON = "afternoon"
    DUSK = "dusk"
    NIGHT = "night"


class HabitFlag(StrEnum):
    """Epistemic status of a cognitive habit attributed to a historical figure."""

    FACT = "fact"
    LEGEND = "legend"
    SPECULATIVE = "speculative"


class ShuhariStage(StrEnum):
    """Three stages of skill acquisition in Japanese arts (shu-ha-ri)."""

    SHU = "shu"
    HA = "ha"
    RI = "ri"


class PlutchikDimension(StrEnum):
    """Plutchik's eight primary emotions."""

    JOY = "joy"
    TRUST = "trust"
    FEAR = "fear"
    SURPRISE = "surprise"
    SADNESS = "sadness"
    DISGUST = "disgust"
    ANGER = "anger"
    ANTICIPATION = "anticipation"


class EpochPhase(StrEnum):
    """Three research epochs of a run (M8, L6 ADR D3 ``two-phase methodology``).

    A ``WorldRuntime`` progresses ``autonomous → q_and_a → evaluation`` with
    no reverse. The goal is to protect the autonomous-emergence claim: the
    ``autonomous`` epoch has no researcher intervention, and any user dialogue
    (``speaker_id="researcher"``) belongs to ``q_and_a``. Offline scoring in

 succeeded in 0ms:
# M5/M6 natural runtime gating bug — design (P3a-decide Task 1)

> Plan-mode 等価ドキュメント。auto-mode 内の "Plan + /reimagine + Codex review"
> CLAUDE.md 制約を満たすため、本ファイルで初期案 + reimagine 代案 + 採用案 +
> Codex review 反映を一元化する。

## 1. 観測症状 (G-GEAR PR #129 採取)

| cell | wall | dialogs | focal | utterances 内訳 |
|---|---|---|---|---|
| kant_natural | 13 min (kill) | 2 | 6 | kant=6 / nietzsche=3 / rikyu=3 |
| nietzsche_natural | 13 min (kill, starved) | 0 | 0 | — |
| rikyu_natural | 13 min (kill) | 3 | 6 | kant=6 / nietzsche=6 / rikyu=6 |

**stimulus side は 3 cell とも focal=198 / dialogs=168 で完走**、natural 専用の
gating 挙動が発火している。

## 2. 仮説 4 件と裏取り

| ID | 仮説 | 裏取り | 採否 |
|---|---|---|---|
| A | RNG seed が初動後に false 一辺倒に偏る | `random.Random(seed_root)` は MT19937 で 2^19937 周期、burst 後だけ false 連続にはならない | × 棄却 |
| B | COOLDOWN_TICKS 30 × cognition_period 7-18s で実効 cooldown 30 min+ | 確かに wall は長いが、cognition tick は最終的に進む。kant_natural 13 min wall で nietzsche cognition_period=7s + WorldRuntime DEFAULT_COGNITION_PERIOD_S=10s → world_tick は 50+ 進むはず → cooldown 単独では説明不可 | △ 補助 |
| C | `_close_timed_out` が in-flight dialog を premature close | 既存 dialog の transcript が 6 turn (= dialog_turn_budget default) で揃っており、exhausted close で正常終了している。timeout race 未発生 | × 棄却 |
| D (revised) | LLM-driven `destination_zone` で agents が AGORA から散る → `_iter_colocated_pairs` が 0 pair 返却 | `personas/{nietzsche,rikyu}.yaml` の `preferred_zones` に **AGORA が含まれない** (Nietzsche=[peripatos,study,garden] / Rikyu=[chashitsu,garden,study])。`cognition/cycle.py:_resample_destination_to_persona_zone` で AGORA 以外に強制リサンプリング → 初動 1-3 tick 後に必然的に scatter | ◎ **採用** |

### Hypothesis D の精緻なメカニズム

1. `cli/eval_run_golden.py:_initial_state_for_natural` は 3 persona を
   `Zone.AGORA` の non-overlapping seat に配置 (boot-time)。
2. `cognition/prompting.py` の system prompt が `destination_zone` を 6 値
   (`study|peripatos|chashitsu|agora|garden|null`) のうち 1 つ選ばせるため、
   LLM は約 5/6 の確率で非 null を返す。
3. 非 null 値が persona の `preferred_zones` 外なら
   `_resample_destination_to_persona_zone` で **preferred の中から決定的に再選択**
   される (Nietzsche なら peripatos / Rikyu なら chashitsu 等)。
4. `WorldRuntime._consume_result` が MoveMsg を `apply_move_command` し、
   同時に `rt.state.position.zone = res.agent_state.position.zone` で更新
   (cycle.py:686-692 で `new_state.position.model_copy(update={"zone": ...})`)。
5. 次の `_run_dialog_tick` で `_iter_colocated_pairs` が `a.zone == b.zone` を
   要求 → Nietzsche (PERIPATOS) / Rikyu (CHASHITSU) / Kant (STUDY|AGORA) は
   ほぼ常に bare → 0 pair。
6. 既に open な dialog は **budget exhaustion** (6 turn) まで継続するので、
   "初動 burst 2-3 dialogs × 6 turns = 12-18 utterance" で総量が固定。

「Nietzsche starved」は zone scatter が初動 1 tick で起きて Nietzsche 関与 pair
が一切 admit できなかった subset。

## 3. 初回案 (Claude single-shot)

`integration/dialog.py` の `InMemoryDialogScheduler` に
**`eval_natural_mode: bool = False`** flag を追加。`True` のとき:

- `tick()` 内で `_iter_colocated_pairs(agents)` を呼ばず、`agents` の **全 distinct pair**
  を反復する pure イテレータ `_iter_all_pairs` を使う。
- pair の `zone` は両 agent の zone の **どちらでもよい**ので `a.zone` を採用
  (logging / envelope 用、admission に zone 制約は無し)。
- `_REFLECTIVE_ZONES` 制約も bypass (3 persona は事実上 AGORA で対話している
  「論理的同居」状態として扱う)。
- `COOLDOWN_TICKS` / `AUTO_FIRE_PROB_PER_TICK` / `TIMEOUT_TICKS` はすべて
  default 通り **active のまま** (natural cadence を保つ)。

CLI 側は `eval_run_golden.py:935-941` で `InMemoryDialogScheduler(...,
eval_natural_mode=True)` を渡す **1 行追加** のみ。

## 4. /reimagine 代案 (zero-from-scratch alternative)

代案 A: **`pin_zone` パラメタを WorldRuntime に追加**して MoveMsg を破棄

- `world/tick.py` に `eval_pin_zone: Zone | None = None` を入れて、
  `_consume_result` で MoveMsg を全部 drop (zone 移動禁止)。
- 利点: 「物理的同居」が真になる。LLM 出力は無害化されるだけで scheduler は
  純朴なまま。
- 欠点: world/ 層に eval-specific な knob を入れる (planning purity 違反、
  M5/M6/M7ζ の dwell/phase wheel と相互作用するリスク)。

代案 B: **persona の `preferred_zones` を eval 起動時に [AGORA] のみに上書き**

- `eval_run_golden.py:capture_natural` 内で `PersonaSpec` を model_copy し、
  preferred_zones を `[Zone.AGORA]` に強制。
- 利点: scheduler/world に変更不要、概念的にも「eval 用に AGORA 固定」と明快。
- 欠点: PersonaSpec が deeply frozen の場合 `model_copy` で
  preferred_zones が反映されない可能性。検証必要。LLM が
  `destination_zone=null` を返すと AGORA に止まるが、`destination_zone=garden`
  を返すと resample で AGORA 強制 — 一見動くが `_resample_destination_to_persona_zone`
  の実装が `random.choice(list(persona.preferred_zones))` (cycle.py:894 周辺)
  で 1 要素 list なら必ず AGORA に解決される、確認要。CLI 側 1 ファイルで完結。

代案 C: **dialog scheduler が "registered agent set" を持ち、initial-zone-anchor**
で pair を構築

- 起動時に `register_pair_set(frozenset[frozenset[str]])` で eval pair set を
  与え、`tick()` はその pair を直接反復。
- 利点: 明示的、既存ロジックを壊さない。
- 欠点: API 増、CLI 経由で frozenset 構築が必要、boolean flag より重い。

## 5. 比較と採用判断

### 5.0 critical insight: `ERRE_ZONE_BIAS_P` の default = 0.2

`cognition/cycle.py:275` で
`self._zone_bias_p = float(os.environ.get("ERRE_ZONE_BIAS_P", "0.2"))`。
すなわち non-preferred zone への移動が LLM 出力で発生したとき、
**20% でしか preferred への bias resample が発火しない**。残り 80% は LLM の
zone choice を honor。

prompt が `destination_zone` に 6 値 (`study|peripatos|chashitsu|agora|garden|null`)
を提示する事実と組み合わせると、natural condition の per-tick zone change rate は
おおよそ:

- LLM null 比率 ~ 1/6 (no move)
- LLM picks AGORA (preferred 内なら no resample) ~ 1/6 (stay)
- LLM picks non-preferred ~ 4/6 → bias_p=0.2 で 20% は AGORA resample / 80% は
  そのまま移動

→ 移動率 ≈ 4/6 × 0.8 ≈ **53%**
→ 3 tick 後に少なくとも 1 名が AGORA を離れる確率 = 1 − (1 − 0.53)^3 ≈ **89%**

これが「初動 2-3 dialog → admission 停止」と一致する。

### 5.1 代案再評価

| 軸 | 初回案 (flag) | 代案 A (pin) | 代案 B (preferred_zones) | 代案 B+ (preferred + bias_p=1.0) | 代案 C (pair set) |
|---|---|---|---|---|---|
| 変更ファイル数 | 2 (dialog.py + CLI) | 2-3 (tick.py + CLI) | 1 (CLI) | 1 (CLI) | 2 (dialog.py + CLI) |
| 変更行数 (推定) | ~25 | ~15 | ~6 | ~10 | ~40 |
| **修正の完全性** | **完全** | 完全 (但し world/ 層介入) | **不完全** (bias_p=0.2 で 53% drift 残存) | 完全 (env var 強制) | 完全 |
| planning purity 違反 | 1-line CLI (許容) | world/ 層 (NG) | CLI のみ | CLI のみ + env var mutation | 1-line CLI |
| 既存テスト regression リスク | 低 (default False) | 中 | 低 | 低 (env var 範囲限定) | 低 |
| 概念的明快さ | **高** ("logical co-location for eval") | 中 ("freeze movement") | 中 (不完全) | 低 (env var hack) | 中 |

**結論: 代案 B 単独では 5.0 の bias_p=0.2 計算により 53% drift が残るため不採用**。

### 5.2 採用案: **初回案 (scheduler flag `eval_natural_mode`)** 単独

理由:
1. **完全性**: zone 制約 自体を bypass するので、agent が wander してもしなくても
   pair admit に影響しない。bias_p / preferred_zones / LLM 出力に依存しない。
2. **副作用最小**: integration/ 層内で完結、cognition/ や world/ には触れない。
   既存 1221 PASS は default False (= 既存挙動) で維持。
3. **概念的に正しい**: eval natural は「3 persona を論理的に同居させる」ための
   評価 setup であり、proximity-based 自然発火セマンティクスとは別の関心事。
4. CLI 1 行追加 (`InMemoryDialogScheduler(..., eval_natural_mode=True)`) は
   planning purity の "CLI 不変" 制約をわずかに違反するが、これは
   **「eval scheduler 構築時の opt-in」** であって CLI ロジック変更ではない。
   許容範囲とする (decisions.md ME-8 で justify)。

代案 B+ (env var mutation) は機能はするが env-driven hack で diagnosability が
低く、scheduler-side flag より監査性で劣る → 不採用。

## 6. 修正範囲 (採用案 = 初回案 scheduler flag)

### 6.1 修正ファイル

- `src/erre_sandbox/integration/dialog.py`:
  - `InMemoryDialogScheduler.__init__` に `eval_natural_mode: bool = False` 追加
    (keyword-only)
  - `tick()` 内で `eval_natural_mode=True` のとき
    `_iter_colocated_pairs` を呼ばず、`agents` の全 distinct pair を反復する
    新ヘルパ `_iter_all_distinct_pairs` を使用
  - `_REFLECTIVE_ZONES` 制約と `a.zone == b.zone` 制約を bypass
  - **Cooldown / probability / timeout は active のまま** (natural cadence 保持)
  - `schedule_initiate` の zone 制約 (line 156) は `eval_natural_mode=True` でも
    bypass する (eval では agent zone が自由に変わるため)
  - public attribute (driver から動的に切替可能) — `golden_baseline_mode`
    と同じパターン

- `src/erre_sandbox/cli/eval_run_golden.py`:
  - line 935-941 の `InMemoryDialogScheduler(...)` 呼び出しに
    `eval_natural_mode=True` を 1 引数追加 (`golden_baseline_mode=False` の隣)
  - これは構築時 opt-in のみで CLI ロジックは不変

- `tests/test_integration/test_dialog_eval_natural_mode.py` (新規):
  1. **Red → Green 転換確認**:
     - eval_natural_mode=False (既存挙動) で、3 agent が異なる zone に分散すると
       admission が停止することを assert (バグの document 化)
     - eval_natural_mode=True で、同じ scenario でも admission が継続することを assert
  2. **invariant 保持**:
     - cooldown は active (close 後 30 tick 待つ)
     - probability gate は active (rng > 0.25 → admit しない)
     - timeout は active (last_activity_tick + 6 で close)
     - `initiator_id == target_id` reject は active
     - 既に open な pair の二重 open reject は active
  3. **golden_baseline_mode との独立性**:
     - 両 flag を True にしても矛盾しない (golden_baseline が優先で zone bypass)
     - default 両方 False で M4-frozen Protocol 挙動
  4. **scheduler 単体テスト**: ManualClock 不要、`tick()` を直接呼んで
     AgentView 渡し、scheduler 内部状態 (`_open` / `_pair_to_id` /
     `_last_close_tick`) を inspect

### 6.2 既存 1221 テスト互換性

`eval_natural_mode: bool = False` default のため、既存挙動は完全に維持。
- `tests/test_integration/test_dialog.py` (既存 70 件): default False で全 PASS
- `tests/test_integration/test_dialog_golden_baseline_mode.py` (既存 10 件):
  golden_baseline_mode は eval_natural_mode と直交、両 default False / True で
  既存と同じ動作

### 6.3 schemas.py の Protocol 整合

`DialogScheduler` Protocol は `__init__` 引数を規定していない (M4 §7.5 frozen)
ので keyword-only flag 追加は Protocol 違反にあたらない。`tick()` /
`schedule_initiate()` / `record_turn()` / `close_dialog()` の signature は
完全に不変。

## 7. 受け入れ条件

- [ ] 新規 test_dialog_eval_natural_mode.py の Red→Green 転換テストが PASS
  - default False で zone drift の admission stop を再現
  - True で admission が継続
- [ ] cooldown / probability / timeout / 自己 dialog reject / 二重 open reject
      の invariant が True/False 両方で維持される
- [ ] 既存 1221 PASS 維持 (default False を確認)
- [ ] G-GEAR 再採取で focal 30 / total 90 / dialogs ~15 を 30-60 min wall
      で完走 (本セッションでは Mac で実機検証不可、次 G-GEAR セッションで確認)
- [ ] decisions.md に新規 ADR (ME-8) 追加: "eval natural condition は
      InMemoryDialogScheduler.eval_natural_mode=True で zone 制約を bypass"
- [ ] tasklist.md §P3a-decide にチェック項目追加

## 8. リスクと反証

exec
/bin/zsh -lc "sed -n '1308,1368p' src/erre_sandbox/schemas.py && sed -n '1084,1120p' src/erre_sandbox/world/tick.py && sed -n '1128,1198p' src/erre_sandbox/world/tick.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
    | WorldLayoutMsg,
    Field(discriminator="kind"),
]
"""Discriminated union of all WebSocket envelope kinds."""


# =============================================================================
# §7.5 DialogScheduler (interface only, M4 foundation)
# =============================================================================


class DialogScheduler(Protocol):
    """Interface for agent-to-agent dialog orchestration (M4 foundation).

    Contract-only: the concrete turn-taking policy, backpressure, and timeout
    handling is the responsibility of ``m4-multi-agent-orchestrator``. This
    Protocol is frozen here so that ``cognition`` and ``world`` can type-hint
    against it in parallel tasks without waiting for the implementation.

    Methods return envelope messages (or ``None``) so the gateway can
    broadcast them over WebSocket without an additional marshalling layer.
    """

    def schedule_initiate(
        self,
        initiator_id: str,
        target_id: str,
        zone: Zone,
        tick: int,
    ) -> DialogInitiateMsg | None:
        """Decide whether to admit a new dialog and emit the initiate envelope.

        ``None`` means the scheduler rejected the request (e.g. existing
        dialog, cooldown, zone mismatch). Non-``None`` is the envelope to
        broadcast.
        """
        ...

    def record_turn(self, turn: DialogTurnMsg) -> None:
        """Record a turn in the dialog's transcript for later close/replay."""
        ...

    def close_dialog(
        self,
        dialog_id: str,
        reason: Literal["completed", "interrupted", "timeout", "exhausted"],
        *,
        tick: int | None = None,
    ) -> DialogCloseMsg:
        """Close an open dialog and emit the close envelope.

        ``tick`` is a non-breaking optional keyword-only extension added
        2026-04-28 (codex review F1) so callers that know the current world
        tick (timeout sweep, exhausted budget) can record the actual close
        tick instead of falling back to ``last_activity_tick``. Implementations
        that ignore ``tick`` keep the M4 frozen behaviour, so the wire
        contract is unchanged.
        """
        ...

    def transcript_of(self, dialog_id: str) -> list[DialogTurnMsg]:
    def _run_dialog_tick(self) -> None:
        """Evaluate the dialog scheduler after all per-agent cognition ran.

        The scheduler consumes a narrow projection (:class:`AgentView`) of
        each runtime so it cannot reach into kinematics or the pending
        observation buffer. Dialog envelopes are delivered through the
        scheduler's injected sink, which :func:`bootstrap` wires back to
        :meth:`inject_envelope`.
        """
        if self._dialog_scheduler is None:
            return
        views = self._agent_views()
        # The scheduler type is a Protocol frozen in schemas.py §7.5 —
        # ``tick`` is the concrete extension exposed by the default
        # :class:`InMemoryDialogScheduler`. Callers supplying a custom
        # scheduler should either subclass that class or accept that the
        # proximity auto-fire logic is skipped.
        tick_fn = getattr(self._dialog_scheduler, "tick", None)
        if tick_fn is None:
            return
        try:
            tick_fn(self._current_world_tick(), views)
        except Exception:
            # A misbehaving scheduler must not crash the cognition loop.
            logger.exception("dialog scheduler tick raised")

    def _current_world_tick(self) -> int:
        """Return the highest per-agent tick, or 0 when no agents are registered.

        Shared by ``_run_dialog_tick``, ``_drive_dialog_turns``, and
        ``_on_heartbeat_tick`` so the three consumers of "current world
        tick" always see the same value. Cheap enough to recompute each
        call (M4 target N ≤ 10 agents); if agent counts grow we could
        cache and invalidate inside ``_consume_result``.
        """
        return max((rt.state.tick for rt in self._agents.values()), default=0)

            for rt in self._agents.values()
        ]

    async def _drive_dialog_turns(self, world_tick: int) -> None:
        """Walk every open dialog and either generate a turn or close at budget.

        Called only when both :attr:`_dialog_scheduler` and
        :attr:`_dialog_generator` are set. For each open dialog the method
        consults :meth:`InMemoryDialogScheduler.iter_open_dialogs` and:

        1. Picks the next speaker by strict alternation:
           ``turn_index % 2 == 0`` => initiator, else target. Derived from
           ``len(transcript)`` rather than a tracked counter so the scheduler
           remains the single source of truth.
        2. Closes the dialog with ``reason="exhausted"`` when
           ``len(transcript) >= speaker.cognitive.dialog_turn_budget``.
        3. Otherwise dispatches the generator concurrently via
           :func:`asyncio.gather` with ``return_exceptions=True`` so one
           misbehaving pair cannot cancel the siblings. ``None`` return is a
           soft close — the existing timeout path will reap it later. An
           exception logs at ``WARNING`` and leaves the dialog untouched.
        4. On a fresh ``DialogTurnMsg`` it calls
           :meth:`InMemoryDialogScheduler.record_turn` (updates transcript and
           ``last_activity_tick``) and :meth:`inject_envelope` (fan-out to
           the WebSocket consumers). Scheduler ``record_turn`` does not emit
           on its own, so the explicit inject here is load-bearing.

        If a referenced speaker agent is not registered with this runtime
        the dialog is skipped and a warning logged — it means the runtime
        and scheduler have drifted, which is a bug in higher-layer wiring.
        """
        scheduler = self._dialog_scheduler
        generator = self._dialog_generator
        if scheduler is None or generator is None:
            return
        open_dialogs: list[tuple[str, str, str, Zone]] = list(
            scheduler.iter_open_dialogs(),
        )
        if not open_dialogs:
            return

        pending = self._stage_dialog_turns(
            scheduler=scheduler,
            generator=generator,
            open_dialogs=open_dialogs,
            world_tick=world_tick,
        )
        if not pending:
            return
        results = await asyncio.gather(
            *(p.coro for p in pending),
            return_exceptions=True,
        )
        for p, res in zip(pending, results, strict=True):
            if isinstance(res, BaseException):
                logger.warning(
                    "dialog turn generation failed for dialog %s speaker %s: %s",
                    p.dialog_id,
                    p.speaker_id,
                    res,
                )
                continue
            if res is None:
                # Soft close — leave for timeout reaper.
                continue
            if not isinstance(res, DialogTurnMsg):
                logger.warning(
                    "dialog turn generator returned unexpected type %s "
                    "for dialog %s — dropping",
                    type(res).__name__,
                    p.dialog_id,

codex
The implementation matches the excerpt. One behavior I’m checking closely now is whether opening all three pairs at once interacts with the existing turn driver and per-agent focal budget, because the zone bug fix can change throughput as well as eligibility.
exec
/bin/zsh -lc "sed -n '1198,1268p' src/erre_sandbox/world/tick.py" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1040,1090p' src/erre_sandbox/world/tick.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
                    p.dialog_id,
                )
                continue
            try:
                scheduler.record_turn(res)
            except KeyError:
                # Dialog closed mid-gather (timeout / exhausted / external).
                logger.debug(
                    "dialog %s closed before turn %d could be recorded",
                    p.dialog_id,
                    p.turn_index,
                )
                continue
            self.inject_envelope(res)

    def _stage_dialog_turns(
        self,
        *,
        scheduler: DialogScheduler,
        generator: DialogTurnGenerator,
        open_dialogs: Sequence[tuple[str, str, str, Zone]],
        world_tick: int,
    ) -> list[_PendingTurn]:
        """Decide per-dialog what to do this tick: close, skip, or enqueue.

        Synchronous because every decision (budget / unknown agent / close)
        is local state. Returned pending turns are staged coroutines that
        :meth:`_drive_dialog_turns` then runs under ``asyncio.gather``.
        """
        pending: list[_PendingTurn] = []
        for did, init_id, target_id, _zone in open_dialogs:
            transcript = scheduler.transcript_of(did)
            turn_index = len(transcript)
            speaker_id = init_id if turn_index % 2 == 0 else target_id
            addressee_id = target_id if speaker_id == init_id else init_id
            speaker_rt = self._agents.get(speaker_id)
            addressee_rt = self._agents.get(addressee_id)
            if speaker_rt is None or addressee_rt is None:
                logger.warning(
                    "dialog %s references unregistered agent(s) "
                    "speaker=%s addressee=%s — skipping",
                    did,
                    speaker_id,
                    addressee_id,
                )
                continue
            budget = speaker_rt.state.cognitive.dialog_turn_budget
            if turn_index >= budget:
                try:
                    scheduler.close_dialog(did, reason="exhausted", tick=world_tick)
                except KeyError:
                    # Racy concurrent close (timeout already ran) — ignore.
                    logger.debug("dialog %s already closed before exhaust", did)
                continue
            pending.append(
                _PendingTurn(
                    dialog_id=did,
                    speaker_id=speaker_id,
                    addressee_id=addressee_id,
                    turn_index=turn_index,
                    coro=generator.generate_turn(
                        dialog_id=did,
                        speaker_state=speaker_rt.state,
                        speaker_persona=speaker_rt.persona,
                        addressee_state=addressee_rt.state,
                        transcript=transcript,
                        world_tick=world_tick,
                    ),
                ),
            )
        return pending

 succeeded in 0ms:
            return
        # M7ζ-3 phase wheel: the global cognition heap event still fires at
        # ``_cognition_period`` cadence, but only agents whose
        # ``next_cognition_due`` has elapsed (and which are not in
        # post-MoveMsg dwell) actually step this tick. The 1e-6 tolerance
        # absorbs floating-point drift between the global heap due time and
        # the per-agent due time computed from ``cognition_period_s``.
        now = self._clock.monotonic()
        # Evaluate agents list once so that dict mutation during gather
        # (register_agent from inside a handler, if anyone ever does that)
        # cannot desynchronise the result / runtime pairing below.
        runtimes = list(self._agents.values())
        due: list[AgentRuntime] = []
        for rt in runtimes:
            if now < rt.dwell_until:
                continue  # in seiza dwell, skip this cognition tick
            if rt.next_cognition_due <= now + 1e-6:
                due.append(rt)
        if due:
            results = await asyncio.gather(
                *(self._step_one(rt) for rt in due),
                return_exceptions=True,
            )
            for rt, res in zip(due, results, strict=True):
                self._consume_result(rt, res)
                # ``cognition_period_s`` is the *minimum* gap between this
                # agent's cognition steps. ``dwell_until`` (set inside
                # ``_consume_result`` when a MoveMsg fires) layers an
                # *upper* override on top: when ``dwell_time_s >
                # cognition_period_s`` (e.g. Rikyū's 90 s dwell vs 18 s
                # period) dwell wins, when ``dwell_time_s <
                # cognition_period_s`` (e.g. Nietzsche's 5 s dwell vs 7 s
                # period) period still bounds the next step. This is the
                # intended semantics — dwell never speeds an agent up.
                rt.next_cognition_due = (
                    now + rt.persona.behavior_profile.cognition_period_s
                )
        # Dialog scheduler runs every global tick regardless of which agents
        # were due, so persona-driven cognition cadence does not starve
        # proximity-driven dialog initiations.
        self._run_dialog_tick()
        if self._dialog_generator is not None and self._dialog_scheduler is not None:
            await self._drive_dialog_turns(self._current_world_tick())

    def _run_dialog_tick(self) -> None:
        """Evaluate the dialog scheduler after all per-agent cognition ran.

        The scheduler consumes a narrow projection (:class:`AgentView`) of
        each runtime so it cannot reach into kinematics or the pending
        observation buffer. Dialog envelopes are delivered through the
        scheduler's injected sink, which :func:`bootstrap` wires back to

exec
/bin/zsh -lc "sed -n '680,745p' src/erre_sandbox/cli/eval_run_golden.py" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '730,820p' src/erre_sandbox/cli/eval_run_golden.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
    run_id = f"{persona}_stimulus_run{run_idx}"
    state = _SinkState()

    con = duckdb.connect(str(temp_path), read_only=False)
    bootstrap_schema(con)

    def _zone_resolver(speaker_id: str, dialog_id: str) -> str:
        # The driver opens dialogs in stimulus-declared zones; we mirror the
        # last-stamped zone via the sink-state cache so the per-row write
        # has a definite value even on multi-turn stimuli.
        del speaker_id
        return state.last_zone_by_speaker.get(dialog_id, "")

    def _stimulus_persona_resolver(agent_id: str) -> str | None:
        # The driver uses the persona_id literal as the focal speaker's
        # ``speaker_id`` and DEFAULT_INTERLOCUTOR_ID for the partner. Map
        # both back to the persona namespace so HIGH-2 focal counting
        # (``speaker_persona_id == persona``) is faithful even on
        # multi-turn stimuli where the partner speaks turn_index=1.
        if agent_id == persona:
            return persona
        if agent_id == DEFAULT_INTERLOCUTOR_ID:
            return DEFAULT_INTERLOCUTOR_ID
        return None

    sink = _make_duckdb_sink(
        con=con,
        run_id=run_id,
        focal_persona_id=persona,
        persona_resolver=_stimulus_persona_resolver,
        fallback_speaker_persona=persona,
        fallback_addressee_persona=DEFAULT_INTERLOCUTOR_ID,
        zone_resolver=_zone_resolver,
        state=state,
    )

    scheduler = InMemoryDialogScheduler(
        envelope_sink=lambda _e: None,
        turn_sink=sink,
        golden_baseline_mode=True,
    )

    if inference_fn is None:
        if client is None:
            msg = "capture_stimulus: provide either inference_fn or client"
            raise ValueError(msg)
        loop = asyncio.get_running_loop()
        inference_fn = _make_stimulus_inference_fn(
            client=client,
            persona_spec=persona_spec,
            sink_state=state,
            loop=loop,
        )
    driver = GoldenBaselineDriver(
        scheduler=scheduler,
        inference_fn=inference_fn,
        seed_root=seed_root,
        cycle_count=cycle_count,
    )

    # Warmup is a pre-condition only when we own the client.
    if client is not None:
        await _warm_up_ollama(client, persona_spec)

    # Populate the zone cache as the driver opens dialogs by hooking the
    # envelope sink. We receive a DialogInitiateMsg per open with its

 succeeded in 0ms:
            sink_state=state,
            loop=loop,
        )
    driver = GoldenBaselineDriver(
        scheduler=scheduler,
        inference_fn=inference_fn,
        seed_root=seed_root,
        cycle_count=cycle_count,
    )

    # Warmup is a pre-condition only when we own the client.
    if client is not None:
        await _warm_up_ollama(client, persona_spec)

    # Populate the zone cache as the driver opens dialogs by hooking the
    # envelope sink. We receive a DialogInitiateMsg per open with its
    # ``zone``; feed it into ``state.last_zone_by_speaker`` keyed on
    # dialog_id (not speaker_id, because both pair members share it).
    initiate_log: dict[str, str] = {}

    def _envelope_sink(env: Any) -> None:
        zone = getattr(env, "zone", None)
        dialog_id = getattr(env, "dialog_id", None)
        if zone is not None and dialog_id is None:
            # DialogInitiateMsg carries zone but no dialog_id at this layer;
            # we resolve through scheduler.get_dialog_id below.
            initiator = getattr(env, "initiator_agent_id", None)
            target = getattr(env, "target_agent_id", None)
            if initiator and target:
                did = scheduler.get_dialog_id(initiator, target)
                if did is not None:
                    initiate_log[did] = str(zone)
        if zone is None and dialog_id is not None:
            # DialogCloseMsg — strip from cache (best-effort)
            initiate_log.pop(str(dialog_id), None)

    # Wire envelope sink in-place (scheduler's internal _sink is private).
    scheduler._sink = _envelope_sink  # noqa: SLF001 — local-only sink swap

    # Make the cache visible to the DuckDB sink before run_persona starts
    # firing. The driver calls schedule_initiate first, the envelope sink
    # populates initiate_log[dialog_id], then record_turn fires record_turn
    # which calls our DuckDB sink — at that point the lookup hits.
    state.last_zone_by_speaker = initiate_log  # alias

    # Drive the battery — synchronous loop since the driver itself is sync.
    # If the inference_fn raises CaptureFatalError (HIGH-3 propagation) it tears
    # down the run before any rename.
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(
            None, lambda: driver.run_persona(persona, stimuli=sliced)
        )
    except CaptureFatalError:
        # Already recorded in state.fatal_error; fall through to closing.
        logger.exception("stimulus capture aborted by fatal sink error")

    write_with_checkpoint(con)

    return CaptureResult(
        run_id=run_id,
        output_path=temp_path,
        total_rows=state.total,
        focal_rows=state.focal,
        fatal_error=state.fatal_error,
        selected_stimulus_ids=selected_ids,
    )


# ---------------------------------------------------------------------------
# Natural capture (full bootstrap stack, headless)
# ---------------------------------------------------------------------------


async def capture_natural(  # noqa: C901, PLR0915 — composition root mirrors bootstrap.py
    *,
    persona: str,
    run_idx: int,
    turn_count: int,
    temp_path: Path,
    ollama_host: str,
    chat_model: str,
    embed_model: str,
    memory_db_path: Path | None,
    wall_timeout_min: float,
    personas_dir: Path = _PERSONAS_DIR_DEFAULT,
    seeds_path: Path | None = None,
    runtime_factory: Callable[..., WorldRuntime] | None = None,
) -> CaptureResult:
    """Capture one natural-condition cell using a headless WorldRuntime stack.


codex
So far I do not see a live-run regression path with the default left false. I’m running the focused new test file now to confirm the mechanics in this workspace, then I’ll write the severity-ordered review.
exec
/bin/zsh -lc 'uv run pytest tests/test_integration/test_dialog_eval_natural_mode.py' in /Users/johnd/ERRE-Sand Box
 succeeded in 610ms:
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/johnd/ERRE-Sand Box
configfile: pyproject.toml
plugins: asyncio-0.26.0, anyio-4.13.0
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 11 items

tests/test_integration/test_dialog_eval_natural_mode.py ...........      [100%]

============================== 11 passed in 0.01s ==============================

exec
/bin/zsh -lc pwd in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
/Users/johnd/ERRE-Sand Box

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/cli/eval_run_golden.py | sed -n '934,950p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba src/erre_sandbox/integration/dialog.py | sed -n '406,422p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba src/erre_sandbox/integration/dialog.py | sed -n '100,190p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba src/erre_sandbox/integration/dialog.py | sed -n '292,330p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
   934	
   935	    scheduler_rng = random.Random(seed_root)  # noqa: S311 — non-crypto, eval seed
   936	    scheduler = InMemoryDialogScheduler(
   937	        envelope_sink=runtime.inject_envelope,
   938	        rng=scheduler_rng,
   939	        turn_sink=duckdb_sink,
   940	        golden_baseline_mode=False,
   941	        # P3a-decide gating fix: bypass zone-equality so the 3 personas can
   942	        # sustain dialog after LLM destination_zone scatters them out of
   943	        # AGORA. See .steering/20260430-m9-eval-system/design-natural-gating-fix.md
   944	        # for root-cause analysis.
   945	        eval_natural_mode=True,
   946	    )
   947	    runtime.attach_dialog_scheduler(scheduler)
   948	
   949	    dialog_generator = OllamaDialogTurnGenerator(llm=inference, personas=persona_specs)
   950	    runtime.attach_dialog_generator(dialog_generator)

 succeeded in 0ms:
   406	                yield a, b
   407	
   408	
   409	def _iter_all_distinct_pairs(
   410	    agents: Iterable[AgentView],
   411	) -> Iterator[tuple[AgentView, AgentView]]:
   412	    """Yield every distinct ordered pair regardless of zone.
   413	
   414	    m9-eval-system P3a-decide: used by ``tick()`` when
   415	    ``eval_natural_mode=True``. The zone field on the leading element is
   416	    still meaningful (it becomes the dialog's recorded zone via the
   417	    ``schedule_initiate`` envelope), but pair eligibility itself does not
   418	    depend on zone equality.
   419	    """
   420	    sorted_agents = sorted(agents, key=lambda v: v.agent_id)
   421	    for i, a in enumerate(sorted_agents):
   422	        for b in sorted_agents[i + 1 :]:

 succeeded in 0ms:
   100	    probability to 1.0 or 0.0 deterministically.
   101	    """
   102	
   103	    def __init__(
   104	        self,
   105	        *,
   106	        envelope_sink: Callable[[ControlEnvelope], None],
   107	        rng: Random | None = None,
   108	        turn_sink: Callable[[DialogTurnMsg], None] | None = None,
   109	        golden_baseline_mode: bool = False,
   110	        eval_natural_mode: bool = False,
   111	    ) -> None:
   112	        self._sink = envelope_sink
   113	        self._rng = rng if rng is not None else Random()  # noqa: S311 — non-crypto
   114	        # M8 L6-D1: optional per-turn sink. When bootstrap wires it to a
   115	        # ``MemoryStore.add_dialog_turn_sync`` closure (with agent_id →
   116	        # persona_id resolution baked in), every recorded turn lands in
   117	        # sqlite for later LoRA-training export. Left None for unit tests
   118	        # and the existing lightweight fixtures that have no store.
   119	        self._turn_sink = turn_sink
   120	        # m9-eval-system P2b (design-final.md §Orchestrator): when True the
   121	        # external golden baseline driver bypasses cooldown / timeout / zone
   122	        # restriction so that 70-stimulus battery × 3 cycles can drive the
   123	        # same agent pair without the natural-dialog admission rules. Public
   124	        # attribute so the driver can flip it between stimulus phase
   125	        # (200 turn, mode=True) and natural-dialog phase (300 turn,
   126	        # mode=False) within the same scheduler instance / MemoryStore.
   127	        self.golden_baseline_mode: bool = golden_baseline_mode
   128	        # m9-eval-system P3a-decide (design-natural-gating-fix.md): when True
   129	        # the eval natural-condition pilot bypasses zone-equality and
   130	        # reflective-zone gates inside ``tick()`` and ``schedule_initiate()``
   131	        # so 3 personas can sustain dialog after LLM-driven destination_zone
   132	        # scatters them across study/peripatos/chashitsu. Cooldown / probability
   133	        # / timeout / self-dialog reject / double-open reject all remain active
   134	        # so admission cadence is still natural — only the spatial constraint
   135	        # is dropped. Orthogonal to ``golden_baseline_mode``: stimulus phase
   136	        # uses ``golden_baseline_mode=True`` (driver controls everything),
   137	        # natural phase uses ``eval_natural_mode=True`` (proximity-free
   138	        # logical co-location). Default False keeps M4-frozen Protocol
   139	        # behaviour for live multi-agent runs.
   140	        self.eval_natural_mode: bool = eval_natural_mode
   141	        self._open: dict[str, _OpenDialog] = {}
   142	        self._pair_to_id: dict[frozenset[str], str] = {}
   143	        # Bounded by C(N, 2) for N agents — M4 targets N≤3 so this cannot
   144	        # grow beyond a few entries. If a future milestone scales to N>100
   145	        # agents, cap this to an LRU dict or prune by stale age from
   146	        # ``tick()``; for now the memory footprint is irrelevant.
   147	        self._last_close_tick: dict[frozenset[str], int] = {}
   148	
   149	    # ------------------------------------------------------------------
   150	    # Protocol methods (frozen in schemas.py §7.5)
   151	    # ------------------------------------------------------------------
   152	
   153	    def schedule_initiate(
   154	        self,
   155	        initiator_id: str,
   156	        target_id: str,
   157	        zone: Zone,
   158	        tick: int,
   159	    ) -> DialogInitiateMsg | None:
   160	        """Admit or reject a new dialog.
   161	
   162	        Returns the :class:`DialogInitiateMsg` on admission for callers that
   163	        rely on the Protocol signature, BUT the envelope is already on the
   164	        way to consumers via the injected sink at the moment this method
   165	        returns. Callers must not forward the return value onto the same
   166	        envelope queue — see module docstring.
   167	        """
   168	        if initiator_id == target_id:
   169	            return None
   170	        if (
   171	            zone not in _REFLECTIVE_ZONES
   172	            and not self.golden_baseline_mode
   173	            and not self.eval_natural_mode
   174	        ):
   175	            # m9-eval-system P2b: golden baseline stimulus battery includes
   176	            # ``Zone.STUDY`` (Kant Wachsmuth/RoleEval, Nietzsche aphoristic
   177	            # bursts) — bypass the natural-dialog cultural restriction.
   178	            # m9-eval-system P3a-decide: eval natural condition lets agents
   179	            # wander out of reflective zones (LLM-driven destination_zone)
   180	            # and we still want them to dialog — bypass zone gate too.
   181	            return None
   182	        key = _pair_key(initiator_id, target_id)
   183	        if key in self._pair_to_id:
   184	            return None
   185	        last_close = self._last_close_tick.get(key)
   186	        if (
   187	            last_close is not None
   188	            and tick - last_close < self.COOLDOWN_TICKS
   189	            and not self.golden_baseline_mode
   190	        ):

 succeeded in 0ms:
   292	
   293	    def tick(self, world_tick: int, agents: Sequence[AgentView]) -> None:
   294	        """Drive proximity-based admission + timeout close in one step.
   295	
   296	        Called by ``WorldRuntime._on_cognition_tick`` after per-agent
   297	        cognition has run. Order:
   298	
   299	        1. close any dialogs whose last_activity_tick is older than TIMEOUT
   300	        2. for each co-located pair in reflective zones, probabilistically
   301	           admit (if not already open and past cooldown)
   302	
   303	        m9-eval-system P3a-decide: when ``eval_natural_mode`` is True the
   304	        spatial gates are dropped. ``_iter_all_distinct_pairs`` enumerates
   305	        every distinct agent pair regardless of zone, and the reflective-zone
   306	        skip below is bypassed. Cooldown / probability / timeout invariants
   307	        remain active so admission cadence is still natural — only proximity
   308	        is removed.
   309	        """
   310	        self._close_timed_out(world_tick)
   311	        if self.eval_natural_mode:
   312	            pair_iter = _iter_all_distinct_pairs(agents)
   313	        else:
   314	            pair_iter = _iter_colocated_pairs(agents)
   315	        for a, b in pair_iter:
   316	            if not self.eval_natural_mode and a.zone not in _REFLECTIVE_ZONES:
   317	                continue
   318	            key = _pair_key(a.agent_id, b.agent_id)
   319	            if key in self._pair_to_id:
   320	                continue
   321	            last_close = self._last_close_tick.get(key)
   322	            if last_close is not None and world_tick - last_close < self.COOLDOWN_TICKS:
   323	                continue
   324	            if self._rng.random() > self.AUTO_FIRE_PROB_PER_TICK:
   325	                continue
   326	            self.schedule_initiate(a.agent_id, b.agent_id, a.zone, world_tick)
   327	
   328	    def get_dialog_id(self, agent_a: str, agent_b: str) -> str | None:
   329	        """Return the open dialog id for the (a, b) pair if any, else None."""
   330	        return self._pair_to_id.get(_pair_key(agent_a, agent_b))

codex
**HIGH**

None.

**MEDIUM**

None.

**LOW**

LOW-1: The two-mode boolean surface is now slightly easy to misread. In [dialog.py](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/integration/dialog.py:128), the comment says `eval_natural_mode` preserves cooldown / probability / timeout, which is true for the CLI path because [eval_run_golden.py](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/cli/eval_run_golden.py:940) sets `golden_baseline_mode=False`. If a future caller sets both booleans true, `golden_baseline_mode` still bypasses cooldown and timeout. I would either document that the invariant claim assumes `golden_baseline_mode=False`, or assert/reject both true if that combination is not meaningful.

LOW-2: `_iter_all_distinct_pairs()` says “ordered pair” in [dialog.py](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/integration/dialog.py:412), but the implementation yields each unordered distinct pair once in stable order. Pure doc nit; behavior is correct.

Correctness: yes, this fixes the observed natural gating bug. With `eval_natural_mode=True`, [tick()](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/integration/dialog.py:310) no longer depends on `a.zone == b.zone`, and [schedule_initiate()](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/integration/dialog.py:170) no longer rejects non-reflective zones. Remaining 0-admission cases are expected: fewer than two agents, all pairs already open, all pairs in cooldown, RNG suppression, or scheduler/tick not wired.

Invariant preservation: for the shipped CLI mode, yes. Self-reject, double-open reject, cooldown, probability gate, and timeout all remain active. The only caveat is the LOW-1 combined-flag case.

Protocol contract: clean. The frozen `DialogScheduler` Protocol does not constrain `__init__`, and the protocol method signatures are unchanged.

Risk to live M5/M6: low. Default `eval_natural_mode=False` preserves the old path.

Re-capture confidence: good. I would expect the focal-30 natural cells to complete barring LLM throughput/runtime failures. This removes the structural “0 colocated pairs forever” plateau; cooldown and RNG can still create pauses, but not permanent starvation.

Verification: `uv run pytest tests/test_integration/test_dialog_eval_natural_mode.py` passed, 11/11. I did not rerun the full 1232-test suite.

**Verdict: ship**
hook: Stop
hook: Stop Completed
2026-05-01T04:09:01.484614Z ERROR codex_core::session: failed to record rollout items: thread 019de1b8-46a1-7a12-a1ff-0d8667efebf5 not found
tokens used
76,961
**HIGH**

None.

**MEDIUM**

None.

**LOW**

LOW-1: The two-mode boolean surface is now slightly easy to misread. In [dialog.py](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/integration/dialog.py:128), the comment says `eval_natural_mode` preserves cooldown / probability / timeout, which is true for the CLI path because [eval_run_golden.py](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/cli/eval_run_golden.py:940) sets `golden_baseline_mode=False`. If a future caller sets both booleans true, `golden_baseline_mode` still bypasses cooldown and timeout. I would either document that the invariant claim assumes `golden_baseline_mode=False`, or assert/reject both true if that combination is not meaningful.

LOW-2: `_iter_all_distinct_pairs()` says “ordered pair” in [dialog.py](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/integration/dialog.py:412), but the implementation yields each unordered distinct pair once in stable order. Pure doc nit; behavior is correct.

Correctness: yes, this fixes the observed natural gating bug. With `eval_natural_mode=True`, [tick()](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/integration/dialog.py:310) no longer depends on `a.zone == b.zone`, and [schedule_initiate()](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/integration/dialog.py:170) no longer rejects non-reflective zones. Remaining 0-admission cases are expected: fewer than two agents, all pairs already open, all pairs in cooldown, RNG suppression, or scheduler/tick not wired.

Invariant preservation: for the shipped CLI mode, yes. Self-reject, double-open reject, cooldown, probability gate, and timeout all remain active. The only caveat is the LOW-1 combined-flag case.

Protocol contract: clean. The frozen `DialogScheduler` Protocol does not constrain `__init__`, and the protocol method signatures are unchanged.

Risk to live M5/M6: low. Default `eval_natural_mode=False` preserves the old path.

Re-capture confidence: good. I would expect the focal-30 natural cells to complete barring LLM throughput/runtime failures. This removes the structural “0 colocated pairs forever” plateau; cooldown and RNG can still create pauses, but not permanent starvation.

Verification: `uv run pytest tests/test_integration/test_dialog_eval_natural_mode.py` passed, 11/11. I did not rerun the full 1232-test suite.

**Verdict: ship**

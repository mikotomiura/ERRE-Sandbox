"""``erre-sandbox cache-benchmark`` — WP6 prompt cache benchmark (M10-0 A5).

Builds the **real** prompt strings from ``cognition.prompting`` for a fixed,
deterministic agent state, measures the prompt-ordering contract
(``docs/m10-0/prompt-ordering-contract.md``) along four axes — prefix hash,
system/user token split, KV-hit proxy, TTFT p50/p95 — and emits a
deterministic baseline JSON plus a trace DuckDB row per persona.

This module is the **only** part of the cache-benchmark feature that imports
``cognition.prompting``: the evidence package core stays string-only. The
baseline is deterministic (TTFT comes from a fixed synthetic sample vector,
``computed_at`` is excluded), so ``--check`` recomputes in memory and
byte-compares against the committed artefact, exiting non-zero on drift —
the regression gate the prompt-ordering contract §2-4 calls for.

The TTFT values are **synthetic** (``live_ttft_verified: false``): a
deterministic placeholder vector, not a measured server latency. A live
measurement is the optional ``runner.run_live_probe`` path, never a CI gate.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final

from erre_sandbox.cognition.prompting import (
    _COMMON_PREFIX,
    build_system_prompt,
    build_user_prompt,
)
from erre_sandbox.cognition.world_model import synthesize_world_model
from erre_sandbox.evidence.cache_benchmark import (
    CACHE_BENCHMARK_SCHEMA_VERSION,
    KV_HIT_PROXY_BASIS,
    BenchCase,
    TokenCountSource,
    TtftSource,
    connect_cache_benchmark_db,
    run_cases_synthetic,
    write_bench_rows,
)
from erre_sandbox.evidence.source_navigator.compiler import load_persona_spec
from erre_sandbox.schemas import (
    AgentState,
    ERREMode,
    ERREModeName,
    Position,
    RelationshipBond,
    SemanticMemoryRecord,
    Zone,
)

if TYPE_CHECKING:
    from erre_sandbox.contracts.cognition_layers import WorldModelEntry
    from erre_sandbox.evidence.cache_benchmark import BenchResult

_SWM_CASE_SUFFIX: Final[str] = "+swm"
"""Suffix marking a flag-on (SWM-injected) benchmark case (DA-M10B-4)."""

_PERSONA_ID_RE: Final[re.Pattern[str]] = re.compile(r"\A[a-z][a-z0-9_-]{0,63}\Z")

_DEFAULT_PERSONAS: Final[str] = "kant,nietzsche,rikyu"
_DEFAULT_BASELINE_PATH: Final[str] = "data/bench/cache_benchmark_baseline.json"
_DEFAULT_TRACE_DB: Final[str] = "data/bench/cache_benchmark.duckdb"
_BASELINE_RUN_ID: Final[str] = "baseline"

# Fixed synthetic TTFT samples (milliseconds). Deterministic placeholder, NOT a
# measured latency — see module docstring. p50=12.0, p95=19.0 for this vector.
_SYNTHETIC_TTFT_SAMPLES_MS: Final[tuple[float, ...]] = (10.0, 12.0, 15.0, 11.0, 20.0)

_GENERATED_BY: Final[str] = "erre_sandbox.cli.cache_benchmark"


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Attach the ``cache-benchmark`` sub-command to the root argparse tree."""
    parser = subparsers.add_parser(
        "cache-benchmark",
        help="Benchmark the prompt cache contract (M10-0 A5).",
        description=(
            "Measure the prompt cache benchmark (M10-0 A5) for one or more "
            "personas and write a deterministic baseline JSON plus a trace "
            "DuckDB row per persona. TTFT is synthetic (a fixed deterministic "
            "vector); live measurement is out of scope for this command."
        ),
    )
    parser.add_argument(
        "--personas",
        default=_DEFAULT_PERSONAS,
        help=f"Comma-separated persona_ids (default: {_DEFAULT_PERSONAS}).",
    )
    parser.add_argument(
        "--personas-dir",
        dest="personas_dir",
        default="personas",
        help="Directory containing <persona>.yaml files (default: personas/).",
    )
    parser.add_argument(
        "--baseline-path",
        dest="baseline_path",
        default=_DEFAULT_BASELINE_PATH,
        help=f"Committed baseline JSON path (default: {_DEFAULT_BASELINE_PATH}).",
    )
    parser.add_argument(
        "--trace-db",
        dest="trace_db",
        default=_DEFAULT_TRACE_DB,
        help=f"Benchmark trace DuckDB path (default: {_DEFAULT_TRACE_DB}).",
    )
    parser.add_argument(
        "--no-trace",
        dest="write_trace",
        action="store_false",
        default=True,
        help="Skip the DuckDB trace write (baseline JSON only).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        default=False,
        help=(
            "Do not write. Recompute the baseline in memory and byte-compare "
            "against --baseline-path; exit non-zero on drift or absence."
        ),
    )


def _fixed_agent_state(persona_id: str) -> AgentState:
    """A fully deterministic agent state for the baseline (tick 0, fixed zone/mode).

    Only the tick-variable state tail of the system prompt depends on this; the
    shared prefix (``_COMMON_PREFIX``) and persona block do not. Kept fixed so
    the baseline changes only when the prompt template changes.
    """
    return AgentState(
        agent_id=persona_id,
        persona_id=persona_id,
        tick=0,
        position=Position(x=0.0, y=0.0, z=0.0, zone=Zone.STUDY),
        erre=ERREMode(name=ERREModeName.DEEP_WORK, entered_at_tick=0),
    )


def _build_case(personas_dir: Path, persona_id: str) -> BenchCase:
    persona = load_persona_spec(personas_dir, persona_id)
    agent = _fixed_agent_state(persona_id)
    system_prompt = build_system_prompt(persona, agent)
    # Empty observations + memories → a deterministic, persona-independent user
    # prompt (the schema-hint tail is the invariant we care about here).
    user_prompt = build_user_prompt(observations=[], memories=[])
    return BenchCase(
        case_id=persona_id,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        shared_prefix=_COMMON_PREFIX,
    )


# Deterministic synthetic evidence (5 promoted dyads across the 5 zones, mixed
# affinity signs) for the flag-on benchmark fixture. ``agent_id`` is fixed to
# "kant"; the *rendered* entries are persona-independent, so the same SWM is
# injected into every ``<persona>+swm`` case.
_SWM_FIXTURE_AGENT_ID: Final[str] = "kant"
_SWM_FIXTURE_TICK: Final[int] = 130
_SWM_FIXTURE_BONDS: Final[tuple[RelationshipBond, ...]] = (
    RelationshipBond(
        other_agent_id="nietzsche",
        affinity=-0.72,
        familiarity=0.61,
        ichigo_ichie_count=9,
        last_interaction_tick=120,
        last_interaction_zone=Zone.AGORA,
    ),
    RelationshipBond(
        other_agent_id="rikyu",
        affinity=0.66,
        familiarity=0.58,
        ichigo_ichie_count=8,
        last_interaction_tick=124,
        last_interaction_zone=Zone.CHASHITSU,
    ),
    RelationshipBond(
        other_agent_id="socrates",
        affinity=0.41,
        familiarity=0.40,
        ichigo_ichie_count=7,
        last_interaction_tick=118,
        last_interaction_zone=Zone.PERIPATOS,
    ),
    RelationshipBond(
        other_agent_id="hume",
        affinity=0.33,
        familiarity=0.50,
        ichigo_ichie_count=6,
        last_interaction_tick=110,
        last_interaction_zone=Zone.STUDY,
    ),
    RelationshipBond(
        other_agent_id="basho",
        affinity=0.58,
        familiarity=0.45,
        ichigo_ichie_count=7,
        last_interaction_tick=122,
        last_interaction_zone=Zone.GARDEN,
    ),
)


def _swm_fixture_entries() -> tuple[WorldModelEntry, ...]:
    """Deterministic representative SWM via the **real** synthesis path.

    Driving :func:`synthesize_world_model` (rather than hand-typing a
    ``WorldModelEntry`` list) keeps the flag-on token measurement honest: the
    rendered ``Held world-model entries`` section is exactly what the runtime
    produces, so the benchmark cannot false-green if the format drifts
    (DA-M10B-4). Yields 5 ``env`` + 1 ``self`` entries; the rendered case shows
    only the top 4 because :func:`build_user_prompt` →
    :func:`format_world_model_entries` caps at ``max_items=4``. The committed
    baseline therefore couples to that cap — changing it requires regenerating
    ``cache_benchmark_baseline.json`` (the ``--check`` gate enforces this).
    """
    records = tuple(
        SemanticMemoryRecord(
            id=f"belief_{_SWM_FIXTURE_AGENT_ID}__{bond.other_agent_id}",
            agent_id=_SWM_FIXTURE_AGENT_ID,
            summary=f"belief about {bond.other_agent_id}",
            belief_kind="clash" if bond.affinity < 0 else "trust",
            confidence=0.80,
        )
        for bond in _SWM_FIXTURE_BONDS
    )
    swm = synthesize_world_model(
        records,
        _SWM_FIXTURE_BONDS,
        agent_id=_SWM_FIXTURE_AGENT_ID,
        current_tick=_SWM_FIXTURE_TICK,
    )
    return tuple(swm.entries)


def _build_swm_case(
    personas_dir: Path,
    persona_id: str,
    entries: tuple[WorldModelEntry, ...],
) -> BenchCase:
    """Flag-on case: identical SYSTEM prompt, USER prompt with injected SWM.

    The system prompt is byte-identical to the persona's base case (Individual
    state lives only in the USER prompt), so the test can assert SYSTEM byte
    equality + prefix_hash equality + bounded user-token delta (DA-M10B-4).
    """
    persona = load_persona_spec(personas_dir, persona_id)
    agent = _fixed_agent_state(persona_id)
    system_prompt = build_system_prompt(persona, agent)
    # M10-C: the flag-on runtime path always opens the write-back channel
    # (Held-entry belief citations + the extended response schema), so the
    # benchmark case mirrors it. The SYSTEM prompt is still byte-identical to the
    # base case — the citations and schema-hint growth live entirely on the USER
    # side — so SYSTEM byte / prefix_hash equality holds and only the bounded
    # user-token delta moves (DA-M10C-3, acceptance: <= +200 vs base case).
    user_prompt = build_user_prompt(
        observations=[],
        memories=[],
        world_model_entries=entries,
        world_model_update_enabled=True,
    )
    return BenchCase(
        case_id=f"{persona_id}{_SWM_CASE_SUFFIX}",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        shared_prefix=_COMMON_PREFIX,
    )


def _result_to_baseline_case(result: BenchResult) -> dict[str, object]:
    """Deterministic per-case fields (no computed_at). Synthetic TTFT included."""
    return {
        "case_id": result.case_id,
        "prefix_hash": result.prefix_hash,
        "system_token_count": result.system_token_count,
        "user_token_count": result.user_token_count,
        "kv_hit_proxy": result.kv_hit_proxy,
        "ttft_p50": result.ttft_p50,
        "ttft_p95": result.ttft_p95,
    }


def _render_baseline(results: list[BenchResult]) -> str:
    """Deterministic baseline JSON text (sorted, no timestamp)."""
    payload: dict[str, object] = {
        "schema_version": CACHE_BENCHMARK_SCHEMA_VERSION,
        "generated_by": _GENERATED_BY,
        "run_id": _BASELINE_RUN_ID,
        "kv_hit_proxy_basis": KV_HIT_PROXY_BASIS,
        "token_count_source": TokenCountSource.PROXY_WHITESPACE_RE.value,
        "ttft_source": TtftSource.SYNTHETIC.value,
        "live_ttft_verified": False,
        "synthetic_ttft_samples_ms": list(_SYNTHETIC_TTFT_SAMPLES_MS),
        "cases": [
            _result_to_baseline_case(r)
            for r in sorted(results, key=lambda r: r.case_id)
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _resolve_persona_ids(personas_arg: str) -> list[str] | None:
    ids = [tok.strip() for tok in personas_arg.split(",") if tok.strip()]
    if not ids:
        print("cache-benchmark: --personas resolved to empty list", file=sys.stderr)
        return None
    for pid in ids:
        if not _PERSONA_ID_RE.fullmatch(pid):
            print(
                f"cache-benchmark: --personas {pid!r} rejected; must match"
                f" {_PERSONA_ID_RE.pattern} (lowercase alnum + _ -, <=64 chars)",
                file=sys.stderr,
            )
            return None
    return ids


def run(args: argparse.Namespace) -> int:
    """Execute the ``cache-benchmark`` sub-command (POSIX exit code)."""
    ids = _resolve_persona_ids(args.personas)
    if ids is None:
        return 2

    personas_dir = Path(args.personas_dir)
    # Base (flag-off) cases + flag-on (SWM-injected) cases. Base cases are
    # byte-identical to the M10-0 baseline (build_user_prompt with no
    # world_model_entries); the +swm cases are new and measure the bounded
    # USER-side injection cost with the SYSTEM prompt unchanged (DA-M10B-4).
    swm_entries = _swm_fixture_entries()
    cases = [_build_case(personas_dir, pid) for pid in ids]
    cases += [_build_swm_case(personas_dir, pid, swm_entries) for pid in ids]
    # computed_at is excluded from the deterministic baseline; the trace row
    # below carries the real timestamp.
    computed_at = datetime.now(UTC)
    results = run_cases_synthetic(
        cases,
        samples_ms=_SYNTHETIC_TTFT_SAMPLES_MS,
        run_id=_BASELINE_RUN_ID,
        computed_at=computed_at,
    )
    baseline_text = _render_baseline(results)
    baseline_path = Path(args.baseline_path)

    if args.check:
        return _check(baseline_path, baseline_text)

    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(baseline_text, encoding="utf-8", newline="\n")
    print(f"cache-benchmark: wrote baseline {baseline_path}", file=sys.stderr)

    if args.write_trace:
        trace_db = Path(args.trace_db)
        trace_db.parent.mkdir(parents=True, exist_ok=True)
        con = connect_cache_benchmark_db(trace_db)
        try:
            n = write_bench_rows(con, results)
        finally:
            con.close()
        print(f"cache-benchmark: wrote {n} trace row(s) to {trace_db}", file=sys.stderr)

    for r in sorted(results, key=lambda r: r.case_id):
        print(
            f"{r.case_id}: prefix_hash={r.prefix_hash[:12]}..."
            f" sys_tok={r.system_token_count} usr_tok={r.user_token_count}"
            f" kv_hit_proxy={r.kv_hit_proxy:.4f}"
            f" ttft_p50={r.ttft_p50:.1f}ms ttft_p95={r.ttft_p95:.1f}ms"
            f" ({r.ttft_source.value})"
        )
    return 0


def _check(baseline_path: Path, expected: str) -> int:
    if not baseline_path.is_file():
        print(
            f"cache-benchmark --check: missing {baseline_path};"
            " regenerate with `python -m erre_sandbox cache-benchmark`",
            file=sys.stderr,
        )
        return 1
    actual = baseline_path.read_text(encoding="utf-8")
    if actual != expected:
        print(
            f"cache-benchmark --check: {baseline_path} is out of date;"
            " regenerate with `python -m erre_sandbox cache-benchmark`",
            file=sys.stderr,
        )
        return 1
    print(f"cache-benchmark --check: {baseline_path} is current", file=sys.stderr)
    return 0


__all__ = ["register", "run"]

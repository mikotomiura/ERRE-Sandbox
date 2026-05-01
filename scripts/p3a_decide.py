"""Compute Tier A metrics + bootstrap CI on the P3a stimulus pilot cells.

m9-eval-system P3a-decide Task 2 (`.steering/20260430-m9-eval-system/
design-natural-gating-fix.md` §Task 2): with the natural side gated by
the M5/M6 zone-drift bug (fixed in PR #128 follow-up), compute CI widths
on the **stimulus 3 cells** alone so the ME-4 ratio ADR can be partially
closed pending re-capture.

The script:

1. Discovers ``data/eval/pilot/<persona>_stimulus_run<idx>.duckdb``.
2. Reads each file read-only (DB6: never write) and pulls the
   ``utterance`` column for the focal speaker rows
   (``speaker_persona_id == persona``).
3. Computes the lightweight Tier A metrics per persona (Burrows Delta
   per-utterance against the persona's own reference, MATTR over the
   concatenated utterance stream). The heavy ML metrics (NLI / novelty
   / Empath) require ``[eval]`` extras; if the imports fail the script
   logs a clear "skipped — install eval extras" line per metric and
   continues with the lightweight set.
4. Bootstraps a 95% CI per (persona, metric) via
   :mod:`erre_sandbox.evidence.bootstrap_ci`.
5. Writes ``data/eval/pilot/_p3a_decide.json``.

Pre-condition: the operator must rsync the G-GEAR DuckDB files into
``data/eval/pilot/`` first. The script exits non-zero with an explicit
error if any expected file is missing — see ``_rsync_receipt.txt`` for
the manual rsync protocol (ME-2).

Usage::

    uv run python scripts/p3a_decide.py
    # → writes data/eval/pilot/_p3a_decide.json
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Callable

import duckdb

from erre_sandbox.evidence.bootstrap_ci import bootstrap_ci
from erre_sandbox.evidence.tier_a import (
    BurrowsLanguageMismatchError,
    compute_burrows_delta,
    compute_mattr,
)

_PILOT_DIR: Final[Path] = Path("data/eval/pilot")
_OUT_PATH: Final[Path] = _PILOT_DIR / "_p3a_decide.json"
_PERSONAS: Final[tuple[str, ...]] = ("kant", "nietzsche", "rikyu")
_RUN_IDX: Final[int] = 0

_PERSONA_LANGUAGE: Final[dict[str, str]] = {
    "kant": "de",
    "nietzsche": "de",
    "rikyu": "ja",
}


def _open_pilot(persona: str) -> duckdb.DuckDBPyConnection:
    path = _PILOT_DIR / f"{persona}_stimulus_run{_RUN_IDX}.duckdb"
    if not path.is_file():
        msg = (
            f"missing pilot file: {path} — rsync from G-GEAR first "
            f"(see {_PILOT_DIR}/_rsync_receipt.txt)"
        )
        raise FileNotFoundError(msg)
    return duckdb.connect(str(path), read_only=True)


def _focal_utterances(con: duckdb.DuckDBPyConnection, persona: str) -> list[str]:
    rows = con.execute(
        "SELECT utterance FROM raw_dialog.dialog "
        "WHERE speaker_persona_id = ? AND utterance IS NOT NULL "
        "ORDER BY tick, dialog_id, turn_index",
        [persona],
    ).fetchall()
    return [str(r[0]) for r in rows if r[0]]


def _per_utterance_burrows(persona: str, utterances: list[str]) -> list[float | None]:
    """Compute Burrows Delta for each utterance against the persona reference.

    Returns a list of floats; entries that raise BurrowsLanguageMismatchError
    or are too short to score (NaN return) are mapped to ``None``.
    """
    from erre_sandbox.evidence.reference_corpus.loader import (  # noqa: PLC0415 — optional path
        load_reference,
    )

    language = _PERSONA_LANGUAGE[persona]
    try:
        reference = load_reference(persona_id=persona, language=language)
    except Exception as exc:  # noqa: BLE001 — broad on purpose: we degrade gracefully
        print(  # noqa: T201
            f"[skip] burrows reference unavailable for {persona}/{language}: {exc!r}",
            file=sys.stderr,
        )
        return []
    out: list[float | None] = []
    for utt in utterances:
        try:
            value = compute_burrows_delta(utt, reference, language=language)
        except BurrowsLanguageMismatchError:
            out.append(None)
            continue
        if math.isnan(value):
            out.append(None)
        else:
            out.append(float(value))
    return out


def _try_optional_metric(
    name: str,
    fn: Callable[[], dict[str, Any]],
) -> dict[str, Any] | None:
    """Call ``fn()`` and surface a clean skip line on any ImportError."""
    try:
        return fn()
    except ImportError as exc:
        print(  # noqa: T201
            f"[skip] tier_a {name}: {exc.name} not installed "
            f"(install with `uv sync --extra eval`)",
            file=sys.stderr,
        )
        return None


def _persona_block(persona: str) -> dict[str, Any]:
    con = _open_pilot(persona)
    try:
        utterances = _focal_utterances(con, persona)
    finally:
        con.close()

    block: dict[str, Any] = {
        "persona_id": persona,
        "n_utterances": len(utterances),
        "metrics": {},
    }

    if not utterances:
        block["note"] = "no focal utterances after rsync — pilot DB empty?"
        return block

    # Burrows Delta — per-utterance values, bootstrap on the per-utterance vector.
    burrows_values = _per_utterance_burrows(persona, utterances)
    finite = [v for v in burrows_values if v is not None]
    if finite:
        result = bootstrap_ci(burrows_values, n_resamples=2000, seed=0)
        block["metrics"]["burrows_delta_per_utterance"] = {
            "point": result.point,
            "lo": result.lo,
            "hi": result.hi,
            "width": result.width,
            "n": result.n,
            "n_resamples": result.n_resamples,
            "method": result.method,
        }
    else:
        block["metrics"]["burrows_delta_per_utterance"] = {
            "skipped": "no finite burrows values — reference corpus or language gap",
        }

    # MATTR — single value over the concatenated utterance stream. CI via
    # bootstrap on per-utterance MATTR (so we have a distribution to resample).
    per_utterance_mattr: list[float | None] = []
    for utt in utterances:
        value = compute_mattr(utt)
        per_utterance_mattr.append(None if value is None else float(value))
    finite_mattr = [v for v in per_utterance_mattr if v is not None]
    if finite_mattr:
        result = bootstrap_ci(per_utterance_mattr, n_resamples=2000, seed=0)
        block["metrics"]["mattr_per_utterance"] = {
            "point": result.point,
            "lo": result.lo,
            "hi": result.hi,
            "width": result.width,
            "n": result.n,
            "n_resamples": result.n_resamples,
            "method": result.method,
        }
    else:
        block["metrics"]["mattr_per_utterance"] = {"skipped": "no MATTR values"}

    # NLI / novelty / Empath — heavy ML metrics. We attempt the import and
    # skip gracefully if [eval] extras are absent (Mac default is no extras).
    nli_block = _try_optional_metric(
        "nli_contradiction",
        lambda: _nli_block(utterances),
    )
    if nli_block is not None:
        block["metrics"]["nli_contradiction"] = nli_block

    novelty_block = _try_optional_metric(
        "semantic_novelty",
        lambda: _novelty_block(utterances),
    )
    if novelty_block is not None:
        block["metrics"]["semantic_novelty"] = novelty_block

    empath_block = _try_optional_metric(
        "empath_proxy",
        lambda: _empath_block(utterances),
    )
    if empath_block is not None:
        block["metrics"]["empath_proxy"] = empath_block

    return block


def _nli_block(utterances: list[str]) -> dict[str, Any]:
    from erre_sandbox.evidence.tier_a import (  # noqa: PLC0415 — optional dep
        compute_nli_contradiction,
    )

    pairs = [(utterances[i], utterances[i + 1]) for i in range(len(utterances) - 1)]
    if not pairs:
        return {"skipped": "fewer than 2 utterances"}
    point = compute_nli_contradiction(pairs)
    if point is None:
        return {"skipped": "NLI scorer returned no result"}
    # Per-pair scores are not exposed by the public API; for a CI we treat
    # the mean as a single point estimate and flag the "no per-sample CI"
    # status. P5 will refactor to return per-pair vectors for proper CI.
    return {
        "point": float(point),
        "ci_status": (
            "point_estimate_only — per-pair vector not exposed by tier_a.nli yet"
        ),
    }


def _novelty_block(utterances: list[str]) -> dict[str, Any]:
    from erre_sandbox.evidence.tier_a import (  # noqa: PLC0415 — optional dep
        compute_semantic_novelty,
    )

    point = compute_semantic_novelty(utterances)
    if point is None:
        return {"skipped": "fewer than 2 utterances"}
    return {
        "point": float(point),
        "ci_status": (
            "point_estimate_only — per-step vector not exposed by tier_a.novelty yet"
        ),
    }


def _empath_block(utterances: list[str]) -> dict[str, Any]:
    from erre_sandbox.evidence.tier_a import (  # noqa: PLC0415 — optional dep
        compute_empath_proxy,
    )

    scores = compute_empath_proxy(utterances)
    if not scores:
        return {"skipped": "empath returned empty dict"}
    # Surface a coarse summary (top-5 categories by score). CI on individual
    # categories is P4-territory because the IPIP-NEO loop produces the
    # primary persona-style signal; here we just expose the vector.
    top = sorted(scores.items(), key=lambda kv: -kv[1])[:5]
    return {
        "top_categories": [{"name": k, "score": float(v)} for k, v in top],
        "ci_status": "vector_only — bootstrap CI deferred to P4 IPIP-NEO loop",
    }


def main() -> int:
    if not _PILOT_DIR.is_dir():
        print(f"pilot directory not found: {_PILOT_DIR}", file=sys.stderr)  # noqa: T201
        return 1
    missing: list[str] = []
    for persona in _PERSONAS:
        candidate = _PILOT_DIR / f"{persona}_stimulus_run{_RUN_IDX}.duckdb"
        if not candidate.is_file():
            missing.append(str(candidate))
    if missing:
        print(  # noqa: T201
            "missing pilot DuckDB files — rsync from G-GEAR first:",
            file=sys.stderr,
        )
        for missing_path in missing:
            print(f"  {missing_path}", file=sys.stderr)  # noqa: T201
        print(  # noqa: T201
            f"\nsee {_PILOT_DIR}/_rsync_receipt.txt for the ME-2 protocol",
            file=sys.stderr,
        )
        return 2

    blocks: list[dict[str, Any]] = []
    for persona in _PERSONAS:
        try:
            blocks.append(_persona_block(persona))
        except Exception as exc:  # noqa: BLE001
            blocks.append(
                {"persona_id": persona, "error": f"{type(exc).__name__}: {exc!s}"}
            )

    payload: dict[str, Any] = {
        "schema": "p3a_decide/v1",
        "scope": "stimulus_only",
        "note": (
            "Natural side intentionally omitted — gated by the M5/M6 zone-drift "
            "bug (fixed via InMemoryDialogScheduler.eval_natural_mode in this "
            "session). Re-run after G-GEAR re-capture per "
            "g-gear-p3a-rerun-prompt.md."
        ),
        "personas": blocks,
    }
    _OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {_OUT_PATH} ({len(blocks)} persona blocks)")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Compute Tier A metrics + bootstrap CI on the P3a pilot cells (both conditions).

m9-eval-system P3a-decide finalization session: the natural-side gating bug
was fixed via ``InMemoryDialogScheduler.eval_natural_mode`` (ME-8) and the
COOLDOWN_TICKS_EVAL re-cooldown amendment, and G-GEAR re-captured 6 cells
(stimulus + natural × 3 personas). This script reads both conditions and
emits CI widths so the ME-4 ratio ADR can be edited with empirical data.

The script:

1. Discovers ``data/eval/pilot/<persona>_<condition>_run<idx>.duckdb`` for
   ``condition in ("stimulus", "natural")`` and 3 personas (6 cells total).
2. Reads each file read-only (DB6: never write) and pulls the
   ``utterance`` column for the focal speaker rows
   (``speaker_persona_id == persona``).
3. Computes the lightweight Tier A metrics per (persona, condition):
   Burrows Delta per-utterance against the persona's own reference, MATTR
   over the concatenated utterance stream. The heavy ML metrics
   (NLI / novelty / Empath) require ``[eval]`` extras; if the imports fail
   the script logs a clear "skipped — install eval extras" line per metric
   and continues with the lightweight set.
4. Bootstraps a 95% CI per (persona, condition, metric) via
   :mod:`erre_sandbox.evidence.bootstrap_ci`.
5. Validates that all 6 expected (persona × condition) cells are present,
   error-free, meet a focal-row floor (stimulus>=150, natural>=25), and
   carry both lightweight metrics with finite ``width`` fields. Any
   validation error suppresses the verdict and the script exits with code
   3. (Codex P3a-finalize HIGH-3 — partial / error / under-sampled cells
   must not feed an ME-4 ADR Edit.)
6. Aggregates per-cell widths into three views per (condition, metric):
   raw mean, per-sample variability (``width * sqrt(n)``), and
   target-extrapolated width (``width * sqrt(n / n_target)``) where
   ``n_target_stimulus = 200`` and ``n_target_natural = 300`` are the
   ME-4 default golden-baseline turn budgets. The ratio verdict is
   computed on target-extrapolated widths so the comparison reflects
   projected variability at deployed scale rather than pilot N
   asymmetry. Raw widths are kept as ``raw_descriptive_only`` for audit.
   (Codex P3a-finalize HIGH-1.)
7. Writes ``data/eval/pilot/_p3a_decide.json`` with schema ``p3a_decide/v3``.

Pre-condition: the operator must rsync the G-GEAR DuckDB files into
``data/eval/pilot/`` first. The script exits non-zero with an explicit
error if any expected file is missing — see ``_rsync_receipt.txt`` for
the manual rsync protocol (ME-2).

Vendi Score and Big5 ICC (the other two metrics ME-4's verdict references)
are P4 territory; this script lists them under ``deferred_metrics`` rather
than computing them, so the ME-4 Edit must remain a partial-update until P4.

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
from erre_sandbox.evidence.tier_a.burrows import BurrowsTokenizationUnsupportedError

_PILOT_DIR: Final[Path] = Path("data/eval/pilot")
_OUT_PATH: Final[Path] = _PILOT_DIR / "_p3a_decide.json"
_PERSONAS: Final[tuple[str, ...]] = ("kant", "nietzsche", "rikyu")
_CONDITIONS: Final[tuple[str, ...]] = ("stimulus", "natural")
_RUN_IDX: Final[int] = 0
_DEFERRED_METRICS: Final[tuple[str, ...]] = ("vendi_score", "big5_icc")
_REQUIRED_METRICS: Final[tuple[str, ...]] = (
    "burrows_delta_per_utterance",
    "mattr_per_utterance",
)
_RATIO_TOLERANCE_PCT: Final[float] = 10.0
# ME-4 default golden-baseline turn counts (the "200/300 default" in ADR text).
# Used as `n_target` for extrapolating CI widths from the asymmetric pilot
# (stimulus focal ≈ 198, natural focal ≈ 30) to the planned baseline turn
# budgets, so the verdict reflects projected variability at the deployed
# scale rather than raw pilot widths confounded with sample-size effects.
_N_TARGET_BY_CONDITION: Final[dict[str, int]] = {
    "stimulus": 200,
    "natural": 300,
}

_PERSONA_LANGUAGE: Final[dict[str, str]] = {
    "kant": "de",
    "nietzsche": "de",
    "rikyu": "ja",
}

# Known (persona, metric) pairs that the validation gate accepts as
# **warnings** rather than errors because they reflect a documented
# library limitation, not a data-quality problem. The first entry
# captures the Burrows Delta Japanese tokenizer gap: ``compute_burrows_delta``
# raises ``BurrowsTokenizationUnsupportedError`` for any rikyu utterance
# (see ``erre_sandbox.evidence.tier_a.burrows`` line ~127). Pre-tokenizing
# Japanese is m9-eval-corpus expansion work; this Mac session ships a
# lightweight partial update of ME-4 with Burrows scoped to (kant,
# nietzsche) and MATTR scoped to all three personas.
_KNOWN_LIMITATIONS: Final[dict[tuple[str, str], str]] = {
    ("rikyu", "burrows_delta_per_utterance"): (
        "BurrowsTokenizationUnsupportedError — Japanese tokenizer not "
        "implemented in tier_a.burrows; pre-tokenizing 青空文庫/国文大観 "
        "deferred to m9-eval-corpus expansion. ratio for this metric is "
        "computed on (kant, nietzsche) only; rikyu contribution comes "
        "from MATTR alone. ME-4 must remain re-openable on tokenizer "
        "delivery."
    ),
}


def _pilot_path(persona: str, condition: str) -> Path:
    return _PILOT_DIR / f"{persona}_{condition}_run{_RUN_IDX}.duckdb"


def _open_pilot(persona: str, condition: str) -> duckdb.DuckDBPyConnection:
    path = _pilot_path(persona, condition)
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
        except (BurrowsLanguageMismatchError, BurrowsTokenizationUnsupportedError):
            # Codex HIGH-2: Japanese tokenization (rikyu) raises
            # BurrowsTokenizationUnsupportedError; previously only
            # BurrowsLanguageMismatchError was caught, so the exception
            # propagated and aborted the whole rikyu cell — losing MATTR
            # too. We map both to a per-utterance None so MATTR survives
            # and the validation gate can still see the cell as "burrows
            # skipped, mattr present" rather than "cell errored".
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
    """Call ``fn()`` and surface a clean skip line on optional metric failure.

    Codex MEDIUM-4: previously caught only ``ImportError`` so that any
    downstream failure (model load timeout, runtime error inside the eval
    extras) propagated to ``main()`` and erased the entire cell — Burrows
    + MATTR included. We now catch ``Exception`` here so optional
    diagnostics can never invalidate the decision-critical lightweight
    metrics. The cell still surfaces the skip reason for transparency.
    """
    try:
        return fn()
    except ImportError as exc:
        print(  # noqa: T201
            f"[skip] tier_a {name}: {exc.name} not installed "
            f"(install with `uv sync --extra eval`)",
            file=sys.stderr,
        )
        return None
    except Exception as exc:  # noqa: BLE001 — see docstring: lightweight metrics must survive
        print(  # noqa: T201
            f"[skip] tier_a {name}: {type(exc).__name__}: {exc!s}",
            file=sys.stderr,
        )
        return {"skipped": f"{type(exc).__name__}: {exc!s}"}


def _persona_block(persona: str, condition: str) -> dict[str, Any]:
    con = _open_pilot(persona, condition)
    try:
        utterances = _focal_utterances(con, persona)
    finally:
        con.close()

    block: dict[str, Any] = {
        "persona_id": persona,
        "condition": condition,
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


def _normalize_width(raw_width: float, n: int, n_target: int) -> float:
    """Project a raw bootstrap CI width from sample size ``n`` to ``n_target``.

    Codex HIGH-1: with stimulus n≈198 and natural n=30, equal per-sample
    variability would still produce raw natural widths ≈ sqrt(198/30) ≈ 2.57x
    the stimulus widths. The ME-4 verdict must use a width that has been
    extrapolated to the planned baseline turn budget so the comparison
    reflects projected variability at deployed scale, not pilot N asymmetry.

    Uses the standard ``CI_width ∝ 1/sqrt(n)`` scaling — exact for sample-
    mean bootstrap CIs on iid data, an approximation otherwise but the best
    closed-form available without per-utterance vectors.
    """
    if n <= 0 or n_target <= 0:
        return float("nan")
    return float(raw_width) * math.sqrt(n / n_target)


def _per_sample_variability(raw_width: float, n: int) -> float:
    """Return ``raw_width * sqrt(n)`` as a per-sample variability proxy.

    Codex HIGH-1 also asks for an ``n``-invariant variability measure so a
    reader can see whether one condition is intrinsically more variable
    per utterance, separate from the target-extrapolated comparison.
    """
    if n <= 0:
        return float("nan")
    return float(raw_width) * math.sqrt(n)


def _mean_widths_by_condition(
    blocks: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Aggregate per-cell widths into per-condition mean widths.

    Emits three views per metric per condition:

    - ``mean_width`` — raw mean of per-cell bootstrap CI widths.
    - ``mean_per_sample_variability`` — mean of ``width * sqrt(n)``, an
      ``n``-invariant per-sample variability proxy (Codex HIGH-1).
    - ``mean_extrapolated_width`` — mean of ``width * sqrt(n / n_target)``,
      projecting each pilot CI to the ME-4 default golden-baseline turn
      budget (stimulus 200, natural 300). The ME-4 verdict must use this
      view, not the raw widths.

    Only the lightweight Tier A metrics (Burrows Delta + MATTR) are
    aggregated here — Vendi Score and Big5 ICC are P4 deliverables and are
    listed under ``deferred_metrics`` in the payload.
    """
    summary: dict[str, dict[str, Any]] = {}
    for condition in _CONDITIONS:
        n_target = _N_TARGET_BY_CONDITION[condition]
        per_metric: dict[str, dict[str, Any]] = {}
        for metric in _REQUIRED_METRICS:
            widths: list[float] = []
            ns: list[int] = []
            per_sample: list[float] = []
            extrapolated: list[float] = []
            for block in blocks:
                if block.get("condition") != condition:
                    continue
                metrics = block.get("metrics", {})
                entry = metrics.get(metric)
                if not isinstance(entry, dict) or "width" not in entry:
                    continue
                width = float(entry["width"])
                n = int(entry.get("n", 0))
                widths.append(width)
                ns.append(n)
                per_sample.append(_per_sample_variability(width, n))
                extrapolated.append(_normalize_width(width, n, n_target))
            if widths:
                per_metric[metric] = {
                    "mean_width": sum(widths) / len(widths),
                    "mean_per_sample_variability": (sum(per_sample) / len(per_sample)),
                    "mean_extrapolated_width": (sum(extrapolated) / len(extrapolated)),
                    "n_target": n_target,
                    "n_cells": len(widths),
                    "per_cell_widths": widths,
                    "per_cell_n": ns,
                    "per_cell_per_sample_variability": per_sample,
                    "per_cell_extrapolated_widths": extrapolated,
                }
            else:
                per_metric[metric] = {"skipped": "no finite widths in this condition"}
        for view in (
            "mean_width",
            "mean_per_sample_variability",
            "mean_extrapolated_width",
        ):
            finite = [
                entry[view]
                for entry in per_metric.values()
                if isinstance(entry, dict) and view in entry
            ]
            combined_key = f"combined_{view}"
            per_metric[combined_key] = (
                {"value": sum(finite) / len(finite), "n_metrics": len(finite)}
                if finite
                else {"skipped": f"no finite {view} values"}
            )
        per_metric["n_target"] = n_target
        summary[condition] = per_metric
    return summary


def _validate_cells_for_ratio(
    blocks: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """Validate that the 6 expected cells are fit to feed the ratio verdict.

    Returns ``{"errors": [...], "warnings": [...]}``:

    - **errors** block the verdict (Codex P3a-finalize HIGH-3): missing
      cell, errored cell, under-sampled cell, or a missing required
      metric whose absence is **not** documented in
      ``_KNOWN_LIMITATIONS``.
    - **warnings** are documented library/data limitations that the
      script accepts as a known partial-coverage trade-off (e.g., rikyu
      Burrows is known-skipped because the Japanese tokenizer is not
      implemented). Aggregation already drops warned cells per metric
      via the ``"width" in entry`` check, so the per-metric mean simply
      reports a smaller ``n_cells``. The ME-4 Edit must surface the
      warning so a future tokenizer delivery can re-open the ADR.
    """
    errors: list[str] = []
    warnings: list[str] = []
    expected_pairs = {(p, c) for p in _PERSONAS for c in _CONDITIONS}
    seen_pairs: set[tuple[str, str]] = set()
    # Phase A floor used during G-GEAR re-capture (PR #131 + PR #133):
    # natural focal>=25, stimulus focal>=150 (allowing buffer below the
    # 200-turn target).
    min_focal_by_condition = {"stimulus": 150, "natural": 25}
    for block in blocks:
        persona = block.get("persona_id")
        condition = block.get("condition")
        if persona not in _PERSONAS or condition not in _CONDITIONS:
            errors.append(f"unexpected cell tag: {block!r}")
            continue
        seen_pairs.add((persona, condition))
        if "error" in block:
            errors.append(f"cell ({persona}, {condition}) errored: {block['error']}")
            continue
        n_utt = int(block.get("n_utterances", 0))
        floor = min_focal_by_condition[condition]
        if n_utt < floor:
            errors.append(
                f"cell ({persona}, {condition}) under-sampled: "
                f"n_utterances={n_utt} < floor={floor}"
            )
        metrics = block.get("metrics", {})
        for metric in _REQUIRED_METRICS:
            entry = metrics.get(metric)
            if not isinstance(entry, dict) or "width" not in entry:
                limitation = _KNOWN_LIMITATIONS.get((persona, metric))
                msg_loc = f"cell ({persona}, {condition}) metric '{metric}'"
                if limitation is not None:
                    warnings.append(f"{msg_loc} known limitation: {limitation}")
                else:
                    errors.append(
                        f"{msg_loc} missing required metric (or width field absent)"
                    )
    missing_pairs = expected_pairs - seen_pairs
    for missing_persona, missing_condition in sorted(missing_pairs):
        errors.append(f"cell ({missing_persona}, {missing_condition}) absent")
    return {"errors": errors, "warnings": warnings}


def _ratio_summary(
    by_condition: dict[str, dict[str, Any]],
    *,
    validation_errors: list[str] | None = None,
    validation_warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Compute the ME-4 ratio verdict on **target-extrapolated** widths.

    Codex HIGH-1 requires the verdict to use widths normalized to the
    ME-4 default golden-baseline budget (stimulus 200, natural 300). Raw
    pilot widths are retained as ``raw_descriptive_only`` for audit but
    are explicitly **not** the basis of the verdict.

    Codex HIGH-3 requires that any validation **error** suppresses the
    verdict — the JSON instead carries ``ratio_summary.skipped`` plus
    the list of errors so the ADR Edit can refuse to advance. Validation
    **warnings** (documented library limitations such as rikyu Burrows
    Japanese tokenizer absence) are surfaced inline so the ADR Edit can
    note partial coverage but do not block the verdict.
    """
    warnings_list = list(validation_warnings or [])
    if validation_errors:
        return {
            "skipped": (
                "validation gate failed; refusing to emit ratio verdict — "
                "see validation_errors"
            ),
            "validation_errors": validation_errors,
            "validation_warnings": warnings_list,
            "deferred_metrics": list(_DEFERRED_METRICS),
            "verdict_threshold_pct": _RATIO_TOLERANCE_PCT,
        }
    stim = by_condition.get("stimulus", {})
    nat = by_condition.get("natural", {})
    stim_extrap = stim.get("combined_mean_extrapolated_width", {})
    nat_extrap = nat.get("combined_mean_extrapolated_width", {})
    if "value" not in stim_extrap or "value" not in nat_extrap:
        return {
            "skipped": "one or both conditions missing combined extrapolated width",
            "deferred_metrics": list(_DEFERRED_METRICS),
            "verdict_threshold_pct": _RATIO_TOLERANCE_PCT,
        }
    stim_extrap_w = float(stim_extrap["value"])
    nat_extrap_w = float(nat_extrap["value"])
    extrap_ratio = nat_extrap_w / stim_extrap_w if stim_extrap_w > 0 else float("inf")
    diff_pct = abs(extrap_ratio - 1.0) * 100.0
    if diff_pct < _RATIO_TOLERANCE_PCT:
        verdict = "within_tolerance_default_200_300_maintainable"
    elif extrap_ratio > 1.0:
        verdict = "natural_wider_at_target_alternative_recommended"
    else:
        verdict = "stimulus_wider_at_target_alternative_recommended"

    stim_raw = stim.get("combined_mean_width", {}).get("value")
    nat_raw = nat.get("combined_mean_width", {}).get("value")
    raw_ratio = (
        (float(nat_raw) / float(stim_raw))
        if isinstance(stim_raw, (int, float))
        and stim_raw > 0
        and isinstance(nat_raw, (int, float))
        else None
    )
    stim_var = stim.get("combined_mean_per_sample_variability", {}).get("value")
    nat_var = nat.get("combined_mean_per_sample_variability", {}).get("value")
    variability_ratio = (
        (float(nat_var) / float(stim_var))
        if isinstance(stim_var, (int, float))
        and stim_var > 0
        and isinstance(nat_var, (int, float))
        else None
    )

    return {
        "verdict_method": "target_extrapolated_width_ratio",
        "verdict": verdict,
        "verdict_threshold_pct": _RATIO_TOLERANCE_PCT,
        "validation_warnings": warnings_list,
        "n_target_by_condition": dict(_N_TARGET_BY_CONDITION),
        "target_extrapolated": {
            "stimulus_combined_width": stim_extrap_w,
            "natural_combined_width": nat_extrap_w,
            "ratio_natural_over_stimulus": extrap_ratio,
            "abs_diff_from_unity_pct": diff_pct,
        },
        "per_sample_variability_descriptive": {
            "stimulus_combined": stim_var,
            "natural_combined": nat_var,
            "ratio_natural_over_stimulus": variability_ratio,
        },
        "raw_descriptive_only": {
            "stimulus_combined_width": stim_raw,
            "natural_combined_width": nat_raw,
            "ratio_natural_over_stimulus": raw_ratio,
            "warning": (
                "raw ratio is sample-size-confounded (stimulus n≈198, natural "
                "n=30); not a decision input — see target_extrapolated."
            ),
        },
        "deferred_metrics": list(_DEFERRED_METRICS),
        "caveats": [
            (
                "Verdict is computed on widths normalized to ME-4 default "
                "n_target (stimulus=200, natural=300). The raw width ratio "
                "is sample-size-confounded and is exposed only for audit."
            ),
            (
                "Vendi Score and Big5 ICC are deferred to P4. This Mac "
                "session can therefore only deliver a **lightweight partial "
                "update** of ME-4 (Burrows Delta + MATTR), not a final close."
            ),
            (
                "MATTR is a P3a-decide proxy for the lightweight metric set; "
                "the ADR-named metrics (Vendi + Big5 ICC) may yield a "
                "different ratio when computed in P4. ME-4 must remain "
                "re-openable on P4 disagreement (>=10% extrapolated ratio "
                "diff or sign reversal)."
            ),
            (
                "NLI / novelty / Empath are point estimates only in this "
                "lightweight script; per-pair / per-step CI is P5 work."
            ),
        ],
    }


def _check_pilot_files_present() -> list[str]:
    missing: list[str] = []
    for persona in _PERSONAS:
        for condition in _CONDITIONS:
            candidate = _pilot_path(persona, condition)
            if not candidate.is_file():
                missing.append(str(candidate))
    return missing


def _collect_blocks() -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for persona in _PERSONAS:
        for condition in _CONDITIONS:
            try:
                blocks.append(_persona_block(persona, condition))
            except Exception as exc:  # noqa: BLE001
                blocks.append(
                    {
                        "persona_id": persona,
                        "condition": condition,
                        "error": f"{type(exc).__name__}: {exc!s}",
                    }
                )
    return blocks


def main() -> int:
    if not _PILOT_DIR.is_dir():
        print(f"pilot directory not found: {_PILOT_DIR}", file=sys.stderr)  # noqa: T201
        return 1
    missing = _check_pilot_files_present()
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

    blocks = _collect_blocks()
    by_condition = _mean_widths_by_condition(blocks)
    validation = _validate_cells_for_ratio(blocks)
    validation_errors = validation["errors"]
    validation_warnings = validation["warnings"]
    ratio_summary = _ratio_summary(
        by_condition,
        validation_errors=validation_errors,
        validation_warnings=validation_warnings,
    )

    payload: dict[str, Any] = {
        "schema": "p3a_decide/v3",
        "scope": "stimulus_and_natural",
        "note": (
            "Both conditions present: natural side re-captured after the M5/M6 "
            "zone-drift bug fix (eval_natural_mode flag, ME-8 ADR) and the "
            "COOLDOWN_TICKS_EVAL=5 + wall default 120 amendment. CI widths are "
            "surfaced per (persona, condition); the verdict in ratio_summary "
            "is computed on target-extrapolated widths (ME-4 default budgets, "
            "stimulus=200, natural=300) per Codex P3a-finalize HIGH-1. The "
            "ME-4 ADR Edit is the authority for the final ratio decision; "
            "this script provides the empirical inputs. Documented library "
            "limitations (e.g. rikyu Burrows Japanese tokenizer absence) "
            "surface under validation_warnings rather than blocking the "
            "verdict — ME-4 must remain re-openable on m9-eval-corpus "
            "tokenizer delivery."
        ),
        "proxy_metrics": {
            "computed_lightweight": list(_REQUIRED_METRICS),
            "deferred_to_p4": list(_DEFERRED_METRICS),
            "warning": (
                "lightweight_ratio_is_not_final_me4_ratio: ME-4 references "
                "Vendi + Big5 ICC; this Mac session computes Burrows Delta + "
                "MATTR as a lightweight proxy. P4 must re-run the verdict "
                "with the ADR-named metrics before ME-4 can be fully closed."
            ),
        },
        "validation_errors": validation_errors,
        "validation_warnings": validation_warnings,
        "cells": blocks,
        "by_condition": by_condition,
        "ratio_summary": ratio_summary,
    }
    _OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(  # noqa: T201
        f"wrote {_OUT_PATH} ({len(blocks)} cells; "
        f"{len(_PERSONAS)} personas × {len(_CONDITIONS)} conditions)"
    )
    if validation_errors:
        print(  # noqa: T201
            f"validation gate failed ({len(validation_errors)} errors); "
            f"ratio verdict suppressed — see {_OUT_PATH}.validation_errors",
            file=sys.stderr,
        )
        for err in validation_errors:
            print(f"  - {err}", file=sys.stderr)  # noqa: T201
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

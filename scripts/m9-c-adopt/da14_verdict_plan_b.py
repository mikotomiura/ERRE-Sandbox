r"""DA-14 Plan B verdict aggregator — kant ADOPT / Phase E A-6 (rank=16).

Reads the 4 rescore artefacts (MPNet + E5-large + lexical-5gram primary,
BGE-M3 exploratory) plus the kernel-independent Burrows / ICC / throughput
JSONs, applies the **encoder agreement axis** (3-of-4 primary with 2+
required, see ``.steering/20260517-m9-c-adopt-plan-b-design/
d2-encoder-allowlist-plan-b.json``), and writes the final verdict JSON +
markdown.

Plan B differs from DA-15 Plan A in two key ways:

1. **Encoder agreement axis** replaces the per-encoder eligibility +
   quorum logic. Plan B ADOPT requires at least 2 of the 3 *primary*
   encoders (MPNet / E5-large / lexical-5gram) to clear ALL of:

   * ``natural_d <= -0.5`` AND ``natural_diff_hi < 0``
   * ``language_balanced_d <= -0.5``
   * ``length_balanced_d <= -0.5``

   AND all 3 primaries must share the *same* (negative) sign on natural d
   — the BGE-M3 sign-flip lesson generalised to "majority direction
   discipline" (allowlist note ``rationale``).

2. **Burrows / ICC / throughput** axes are evaluated independently
   (kernel-agnostic) and *each* must clear:

   * Burrows reduction% >= 5 point AND CI lower > 0
   * ICC(A,1) >= 0.55
   * throughput pct of baseline >= 70%

Plan B kant ADOPT requires **all four** axis verdicts to PASS. A single
axis fail routes the persona to **Phase E A-6** (rank=16 spike, DA-16
ADR candidate — see ``.steering/20260516-m9-c-adopt-plan-b-eval-gen/
blockers.md`` if recorded).

Usage::

    python scripts/m9-c-adopt/da14_verdict_plan_b.py \
        --rescore .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-mpnet-plan-b-kant.json \
        --rescore .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-e5large-plan-b-kant.json \
        --rescore .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-lex5-plan-b-kant.json \
        --rescore .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-bgem3-plan-b-kant.json \
        --burrows .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-burrows-plan-b-kant.json \
        --icc .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-icc-plan-b-kant.json \
        --throughput .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-throughput-plan-b-kant.json \
        --allowlist .steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json \
        --output-json .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-verdict-plan-b-kant.json \
        --output-md .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-verdict-plan-b-kant.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_VENDI_D_GATE: float = -0.5
_BURROWS_REDUCTION_GATE_PCT: float = 5.0
_ICC_GATE: float = 0.55
_THROUGHPUT_GATE_PCT: float = 70.0


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _bootstrap_clears(payload: dict[str, Any] | None) -> bool:
    """Return True if a balanced bootstrap dict clears the DA-14 gates."""
    if not payload:
        return False
    return (
        payload.get("cohens_d") is not None
        and payload["cohens_d"] <= _VENDI_D_GATE
        and payload.get("diff_hi") is not None
        and payload["diff_hi"] < 0
    )


def _natural_clears(rescore: dict[str, Any]) -> tuple[bool, float | None, float | None]:
    """Natural-window gate: d <= -0.5 AND diff CI upper < 0."""
    sb = rescore.get("standard_bootstrap") or {}
    d = sb.get("cohens_d")
    hi = sb.get("diff_hi")
    pass_ = (
        d is not None
        and d <= _VENDI_D_GATE
        and hi is not None
        and hi < 0
    )
    return pass_, d, hi


def _per_encoder_summary(
    rescore: dict[str, Any],
    allowlist: dict[str, Any],
) -> dict[str, Any]:
    """Collect axis verdicts + role for a single encoder."""
    encoder = rescore["encoder"]
    d2_entry = allowlist["encoders"].get(encoder, {})
    role = d2_entry.get("role")
    pinned_sha = d2_entry.get("revision_sha")
    revision_match = rescore.get("encoder_revision_sha") == pinned_sha
    library_match = rescore.get("library_versions_match_d2", False)

    natural_pass, natural_d, natural_hi = _natural_clears(rescore)
    lang_pass = _bootstrap_clears(rescore.get("language_balanced_bootstrap"))
    length_pass = _bootstrap_clears(rescore.get("length_balanced_bootstrap"))

    lang_d = (
        rescore.get("language_balanced_bootstrap", {}).get("cohens_d")
        if rescore.get("language_balanced_bootstrap")
        else None
    )
    length_d = (
        rescore.get("length_balanced_bootstrap", {}).get("cohens_d")
        if rescore.get("length_balanced_bootstrap")
        else None
    )

    all_axes_pass = natural_pass and lang_pass and length_pass
    return {
        "encoder": encoder,
        "encoder_revision_sha": rescore.get("encoder_revision_sha"),
        "encoder_role_d2": role,
        "kernel_type": rescore.get("kernel_type", "semantic"),
        "d2_revision_match": revision_match,
        "d2_library_match": library_match,
        "natural_cohens_d": natural_d,
        "natural_diff_hi": natural_hi,
        "natural_pass": natural_pass,
        "language_balanced_d": lang_d,
        "language_balanced_pass": lang_pass,
        "length_balanced_d": length_d,
        "length_balanced_pass": length_pass,
        "all_three_axes_pass": all_axes_pass,
        "within_language_d": {
            lang: (entry.get("cohens_d") if isinstance(entry, dict) else None)
            for lang, entry in rescore.get("within_language", {}).items()
        },
    }


def _encoder_agreement_axis(per_encoder: list[dict[str, Any]]) -> dict[str, Any]:
    """3-primary-of-which-2-required encoder agreement gate.

    Returns the per-axis verdict + which encoders cleared. Primary list
    comes from allowlist role markers; exploratory (BGE-M3) is reported
    but cannot contribute to the quorum.
    """
    primaries = [e for e in per_encoder if e["encoder_role_d2"] == "primary"]
    exploratories = [
        e for e in per_encoder if e["encoder_role_d2"] == "exploratory"
    ]
    n_primary = len(primaries)
    n_primary_pass = sum(1 for e in primaries if e["all_three_axes_pass"])

    # Direction discipline: all primaries must share the same (negative)
    # natural d sign when the gate passes (BGE-M3 sign-flip generalisation).
    natural_ds = [
        e.get("natural_cohens_d") for e in primaries
        if e.get("natural_cohens_d") is not None
    ]
    all_negative = bool(natural_ds) and all(d < 0 for d in natural_ds)
    direction_pass = all_negative

    primary_pass = n_primary_pass >= 2 and direction_pass

    return {
        "primary_count_total": n_primary,
        "primary_count_passed_all_axes": n_primary_pass,
        "primary_count_required": 2,
        "direction_all_negative": all_negative,
        "axis_pass": primary_pass,
        "primary_encoders_passing": [
            e["encoder"] for e in primaries if e["all_three_axes_pass"]
        ],
        "exploratory_encoders_reported": [e["encoder"] for e in exploratories],
    }


def _burrows_axis(burrows: dict[str, Any]) -> dict[str, Any]:
    """Burrows reduction% gate (kernel-independent)."""
    reduction = burrows.get("reduction_pct")
    ci_lo = burrows.get("ci_lower")
    pass_ = (
        reduction is not None
        and reduction >= _BURROWS_REDUCTION_GATE_PCT
        and ci_lo is not None
        and ci_lo > 0
    )
    return {
        "reduction_pct": reduction,
        "ci_lower": ci_lo,
        "ci_upper": burrows.get("ci_upper"),
        "gate_pct": _BURROWS_REDUCTION_GATE_PCT,
        "axis_pass": pass_,
    }


def _icc_axis(icc: dict[str, Any]) -> dict[str, Any]:
    """ICC(A,1) gate (kernel-independent)."""
    point = icc.get("v2_point") or icc.get("point")
    pass_ = point is not None and point >= _ICC_GATE
    return {
        "icc_point": point,
        "gate": _ICC_GATE,
        "axis_pass": pass_,
    }


def _throughput_axis(throughput: dict[str, Any]) -> dict[str, Any]:
    """Throughput pct of baseline gate (kernel-independent)."""
    pct = throughput.get("throughput_pct_of_baseline") or throughput.get(
        "throughput_pct",
    )
    pass_ = pct is not None and pct >= _THROUGHPUT_GATE_PCT
    return {
        "throughput_pct_of_baseline": pct,
        "gate_pct": _THROUGHPUT_GATE_PCT,
        "axis_pass": pass_,
    }


def _aggregate_verdict(
    encoder_axis: dict[str, Any],
    burrows_axis: dict[str, Any],
    icc_axis: dict[str, Any],
    throughput_axis: dict[str, Any],
) -> str:
    """ADOPT if all four axes PASS, else PHASE_E_A6 (rank=16 spike)."""
    if (
        encoder_axis["axis_pass"]
        and burrows_axis["axis_pass"]
        and icc_axis["axis_pass"]
        and throughput_axis["axis_pass"]
    ):
        return "ADOPT"
    return "PHASE_E_A6"


def _fmt_or_dash(value: Any, fmt: str = ".4f") -> str:
    if isinstance(value, (int, float)) and value == value:
        return f"{value:{fmt}}"
    return "—"


def _write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines: list[str] = []
    lines.append("# DA-14 Plan B verdict — kant (encoder agreement axis)")
    lines.append("")
    lines.append(f"**verdict**: `{payload['verdict']}`")
    lines.append("")
    lines.append("## Thresholds (DA-14 / Plan B, unchanged)")
    lines.append("")
    th = payload["thresholds"]
    lines.append(f"- Vendi natural d ≤ `{th['vendi_d_le']}` AND natural CI upper < 0")
    lines.append(f"- Lang-balanced d ≤ `{th['vendi_d_le']}`")
    lines.append(f"- Length-balanced d ≤ `{th['vendi_d_le']}`")
    lines.append(
        f"- Burrows reduction% ≥ `{th['burrows_pct_ge']}` AND CI lower > 0",
    )
    lines.append(f"- ICC(A,1) ≥ `{th['icc_ge']}`")
    lines.append(f"- Throughput pct of baseline ≥ `{th['throughput_pct_ge']}%`")
    lines.append("")
    lines.append("## Per-encoder rescore (Plan B 4-encoder panel)")
    lines.append("")
    lines.append(
        "| encoder | role | natural d | lang-bal d | length-bal d | "
        "natural | lang-bal | length-bal | all-3 |",
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for enc in payload["per_encoder"]:
        nat_d = _fmt_or_dash(enc.get("natural_cohens_d"))
        lang_d = _fmt_or_dash(enc.get("language_balanced_d"))
        length_d = _fmt_or_dash(enc.get("length_balanced_d"))
        lines.append(
            f"| `{enc['encoder']}` | {enc.get('encoder_role_d2', '—')} | "
            f"{nat_d} | {lang_d} | {length_d} | "
            f"{'PASS' if enc['natural_pass'] else 'FAIL'} | "
            f"{'PASS' if enc['language_balanced_pass'] else 'FAIL'} | "
            f"{'PASS' if enc['length_balanced_pass'] else 'FAIL'} | "
            f"{'**YES**' if enc['all_three_axes_pass'] else 'no'} |",
        )
    lines.append("")
    lines.append("## Encoder agreement axis (3-of-4 primary, 2+ required)")
    lines.append("")
    ea = payload["axes"]["encoder_agreement"]
    lines.append(
        f"- Primaries clearing all 3 axes: **{ea['primary_count_passed_all_axes']}"
        f" of {ea['primary_count_total']}** "
        f"(required ≥ {ea['primary_count_required']})",
    )
    lines.append(
        f"- All primary natural d share negative sign: "
        f"**{ea['direction_all_negative']}**",
    )
    lines.append(
        f"- Primary encoders passing: `{ea['primary_encoders_passing']}`",
    )
    lines.append(
        f"- Exploratory (reported, non-quorum): "
        f"`{ea['exploratory_encoders_reported']}`",
    )
    lines.append(f"- Axis verdict: `{'PASS' if ea['axis_pass'] else 'FAIL'}`")
    lines.append("")
    lines.append("## Kernel-independent axes")
    lines.append("")
    ba = payload["axes"]["burrows"]
    ia = payload["axes"]["icc"]
    ta = payload["axes"]["throughput"]
    lines.append(
        f"- Burrows reduction% = `{_fmt_or_dash(ba['reduction_pct'])}` "
        f"(CI lo=`{_fmt_or_dash(ba['ci_lower'])}` "
        f"hi=`{_fmt_or_dash(ba['ci_upper'])}`) → "
        f"`{'PASS' if ba['axis_pass'] else 'FAIL'}`",
    )
    lines.append(
        f"- ICC(A,1) = `{_fmt_or_dash(ia['icc_point'])}` → "
        f"`{'PASS' if ia['axis_pass'] else 'FAIL'}`",
    )
    lines.append(
        f"- Throughput pct = `{_fmt_or_dash(ta['throughput_pct_of_baseline'], '.2f')}%` → "
        f"`{'PASS' if ta['axis_pass'] else 'FAIL'}`",
    )
    lines.append("")
    if payload["verdict"] == "ADOPT":
        lines.append("## kant ADOPT — next step")
        lines.append("")
        lines.append(
            "All four axes PASS. Next session expands Plan B to nietzsche /"
            " rikyu by retraining each persona with the Plan B corpus +"
            " WeightedTrainer + DR-5/DR-6 patches, then recomputes this"
            " verdict per persona.",
        )
    else:
        lines.append("## Phase E A-6 (rank=16 spike) — next step")
        lines.append("")
        lines.append(
            "At least one axis failed. Plan B kant is routed to Phase E A-6"
            " (rank=16 spike) as the next investment. Open a new ADR DA-16"
            " for the rank=16 hypothesis, recording which axes failed and"
            " the within-language d patterns that motivate rank capacity"
            " expansion vs further corpus tuning.",
        )
    lines.append("")
    lines.append("## Pre-registration anchor")
    lines.append("")
    lines.append(
        "Encoder + revision SHA + library versions + kernel_type are pinned"
        " in `.steering/20260517-m9-c-adopt-plan-b-design/"
        "d2-encoder-allowlist-plan-b.json`. Rescore + verdict outputs"
        " embed the runtime-detected SHA so the audit chain is self-"
        "contained.",
    )
    lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="m9-c-adopt-da14-verdict-plan-b")
    p.add_argument("--rescore", action="append", required=True, type=Path)
    p.add_argument("--burrows", required=True, type=Path)
    p.add_argument("--icc", required=True, type=Path)
    p.add_argument("--throughput", required=True, type=Path)
    p.add_argument("--allowlist", required=True, type=Path)
    p.add_argument("--output-json", required=True, type=Path)
    p.add_argument("--output-md", required=True, type=Path)
    args = p.parse_args(argv)

    allowlist = _load_json(args.allowlist)
    rescores = [_load_json(p) for p in args.rescore]
    burrows = _load_json(args.burrows)
    icc = _load_json(args.icc)
    throughput = _load_json(args.throughput)

    per_encoder = [_per_encoder_summary(r, allowlist) for r in rescores]
    encoder_axis = _encoder_agreement_axis(per_encoder)
    burrows_axis = _burrows_axis(burrows)
    icc_axis = _icc_axis(icc)
    throughput_axis = _throughput_axis(throughput)

    verdict = _aggregate_verdict(
        encoder_axis, burrows_axis, icc_axis, throughput_axis,
    )

    payload: dict[str, Any] = {
        "persona": "kant",
        "plan": "B",
        "verdict": verdict,
        "thresholds": {
            "vendi_d_le": _VENDI_D_GATE,
            "burrows_pct_ge": _BURROWS_REDUCTION_GATE_PCT,
            "icc_ge": _ICC_GATE,
            "throughput_pct_ge": _THROUGHPUT_GATE_PCT,
            "note": "DA-14 thresholds unchanged. Plan B applies them under"
            " the encoder agreement axis (3-of-4 primary, 2+ required) +"
            " kernel-independent Burrows/ICC/throughput.",
        },
        "per_encoder": per_encoder,
        "axes": {
            "encoder_agreement": encoder_axis,
            "burrows": burrows_axis,
            "icc": icc_axis,
            "throughput": throughput_axis,
        },
        "preregistration_anchor": (
            ".steering/20260517-m9-c-adopt-plan-b-design/"
            "d2-encoder-allowlist-plan-b.json (D-2 Plan B allowlist) +"
            " DA-14 thresholds unchanged. Encoder agreement axis from"
            " ``encoder_agreement_axis`` block of the allowlist."
        ),
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_markdown(payload, args.output_md)
    print(
        f"verdict={verdict} "
        f"encoder_agreement={encoder_axis['axis_pass']} "
        f"burrows={burrows_axis['axis_pass']} "
        f"icc={icc_axis['axis_pass']} "
        f"throughput={throughput_axis['axis_pass']}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

r"""DA-15 verdict aggregator — kant ADOPT/REJECT under Plan A.

Reads the per-encoder calibration and rescore artefacts, applies the
pre-registered DA-14 thresholds (unchanged) under the DA-15 amended metric
``vendi_semantic_v2_encoder_swap``, and writes the final verdict JSON + MD.

The verdict considers an encoder eligible for ADOPT contribution only if it
clears BOTH:

* calibration gate (overall AUC ≥ 0.75 AND every within-language slice with
  enough class mass also ≥ 0.75) — Codex HIGH-2
* rescore gate under balanced conditions: cohens_d ≤ -0.5 with diff CI
  upper < 0, under BOTH language-balanced and length-balanced bootstraps —
  Codex HIGH-2's "balancing 後に effect が消える encoder は Plan A FAIL"

A kant ADOPT verdict is reached when at least one primary candidate
encoder clears both gates AND ICC(A,1) PASS (from DA-14, kernel-independent
axis). Burrows axis remains FAIL — the markdown verdict pins this as a
named limitation per Codex LOW-1.

Usage::

    python scripts/m9-c-adopt/da15_verdict.py \
        --rescore .steering/20260516-m9-c-adopt-da15-impl/da15-rescore-e5-kant.json \
        --rescore .steering/20260516-m9-c-adopt-da15-impl/da15-rescore-bge-m3-kant.json \
        --calibration .steering/20260516-m9-c-adopt-da15-impl/da15-calibration-e5.json \
        --calibration .steering/20260516-m9-c-adopt-da15-impl/da15-calibration-bge-m3.json \
        --da14-verdict .steering/20260515-m9-c-adopt-retrain-v2-verdict/da14-verdict-v2-kant.json \
        --output-json .steering/20260516-m9-c-adopt-da15-impl/da15-verdict-kant.json \
        --output-md .steering/20260516-m9-c-adopt-da15-impl/da15-verdict-kant.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_VENDI_D_GATE: float = -0.5
_VENDI_AUC_GATE: float = 0.75


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _calibration_pass(calib: dict[str, Any]) -> bool:
    if calib.get("verdict") != "PASS":
        return False
    if calib.get("overall_auc", 0) < _VENDI_AUC_GATE:
        return False
    return all(
        v.get("auc") is None or v["auc"] >= _VENDI_AUC_GATE
        for v in calib.get("within_language_auc", {}).values()
    )


def _bootstrap_clears(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    return (
        payload.get("cohens_d") is not None
        and payload["cohens_d"] <= _VENDI_D_GATE
        and payload.get("diff_hi") is not None
        and payload["diff_hi"] < 0
    )


def _encoder_eligible(rescore: dict[str, Any], calib: dict[str, Any]) -> dict[str, Any]:
    cal_pass = _calibration_pass(calib)
    natural_d = rescore["natural_windows"]["cohens_d"]
    natural_pass = (
        natural_d is not None
        and natural_d <= _VENDI_D_GATE
        and rescore["standard_bootstrap"].get("hi") is not None
        and rescore["standard_bootstrap"]["hi"] < 0
    )
    lang_pass = _bootstrap_clears(rescore.get("language_balanced_bootstrap"))
    length_pass = _bootstrap_clears(rescore.get("length_balanced_bootstrap"))
    overall_eligible = cal_pass and natural_pass and lang_pass and length_pass
    return {
        "encoder": rescore["encoder"],
        "encoder_revision_sha": rescore.get("encoder_revision_sha"),
        "calibration_pass": cal_pass,
        "calibration_overall_auc": calib.get("overall_auc"),
        "calibration_within_lang_auc": calib.get("within_language_auc"),
        "natural_cohens_d": natural_d,
        "natural_diff_lo": rescore["standard_bootstrap"].get("lo"),
        "natural_diff_hi": rescore["standard_bootstrap"].get("hi"),
        "natural_pass": natural_pass,
        "language_balanced_d": (
            rescore.get("language_balanced_bootstrap", {}).get("cohens_d")
            if rescore.get("language_balanced_bootstrap")
            else None
        ),
        "language_balanced_pass": lang_pass,
        "length_balanced_d": (
            rescore.get("length_balanced_bootstrap", {}).get("cohens_d")
            if rescore.get("length_balanced_bootstrap")
            else None
        ),
        "length_balanced_pass": length_pass,
        "within_language_d": {
            lang: (entry.get("cohens_d") if isinstance(entry, dict) else None)
            for lang, entry in rescore.get("within_language", {}).items()
        },
        "eligible_for_adopt": overall_eligible,
    }


def _write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines: list[str] = []
    lines.append("# DA-15 Phase 1 verdict — kant (Plan A = Vendi kernel swap)")
    lines.append("")
    lines.append(f"**verdict**: `{payload['verdict']}`")
    lines.append("")
    lines.append("## Metric definition (Codex HIGH-1)")
    lines.append("")
    lines.append(
        "DA-15 introduces a *versioned amended* Vendi metric"
        " `vendi_semantic_v2_encoder_swap` so that swapping the encoder"
        " cannot retroactively rescue a DA-14 axis. The DA-14 MPNet"
        " instrument (`vendi_semantic`) is always reported alongside as"
        " the regression baseline."
    )
    lines.append("")
    lines.append("| | DA-14 MPNet (regression record) | DA-15 amended metric |")
    lines.append("|---|---|---|")
    da14 = payload["da14_record"]
    lines.append(
        f"| Vendi axis | `vendi_semantic` cohens_d="
        f"{da14['vendi_d']:.4f} (CI hi={da14['vendi_ci_hi']:.4f}) → "
        f"`{da14['vendi_pass']}` |"
        f" `vendi_semantic_v2_encoder_swap` — see below |"
    )
    lines.append(
        f"| Burrows axis | `burrows_reduction` "
        f"point={da14['burrows_point']:.4f} → `FAIL` (5% target unmet)"
        f" | not in scope (Plan A is Vendi-only) |"
    )
    lines.append(
        f"| ICC axis | ICC(A,1) point={da14['icc_point']:.4f} → "
        f"`{da14['icc_pass']}` | kernel-independent → `{da14['icc_pass']}` |"
    )
    lines.append(
        f"| Throughput | rate_focal_per_s={da14['throughput_pct']:.2f}%"
        f" → `{da14['throughput_pass']}` | not affected → "
        f"`{da14['throughput_pass']}` |"
    )
    lines.append("")
    lines.append("## DA-15 per-encoder rescore")
    lines.append("")
    lines.append(
        "| encoder | calibration AUC | natural d | lang-bal d | "
        "length-bal d | calibration | natural | lang-bal | length-bal | eligible |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|---|---|---|"
    )
    for enc in payload["per_encoder"]:
        cal_auc = enc.get("calibration_overall_auc")
        cal_auc_s = f"{cal_auc:.4f}" if cal_auc is not None else "—"
        nat_d = enc.get("natural_cohens_d")
        nat_s = f"{nat_d:.4f}" if nat_d is not None else "—"
        lang_d = enc.get("language_balanced_d")
        lang_s = f"{lang_d:.4f}" if lang_d is not None else "—"
        length_d = enc.get("length_balanced_d")
        length_s = f"{length_d:.4f}" if length_d is not None else "—"
        lines.append(
            f"| `{enc['encoder']}` | {cal_auc_s} | {nat_s} | {lang_s} | "
            f"{length_s} | "
            f"{'PASS' if enc['calibration_pass'] else 'FAIL'} | "
            f"{'PASS' if enc['natural_pass'] else 'FAIL'} | "
            f"{'PASS' if enc['language_balanced_pass'] else 'FAIL'} | "
            f"{'PASS' if enc['length_balanced_pass'] else 'FAIL'} | "
            f"{'**YES**' if enc['eligible_for_adopt'] else 'no'} |"
        )
    lines.append("")
    lines.append("## Per-encoder within-language d (encoder eligibility audit)")
    lines.append("")
    lines.append("| encoder | d_de | d_en | d_ja |")
    lines.append("|---|---|---|---|")
    for enc in payload["per_encoder"]:
        wl = enc.get("within_language_d", {})
        def _fmt(v: Any) -> str:
            return f"{v:.4f}" if isinstance(v, (int, float)) and v == v else "—"
        lines.append(
            f"| `{enc['encoder']}` | {_fmt(wl.get('de'))} | {_fmt(wl.get('en'))} | "
            f"{_fmt(wl.get('ja'))} (insufficient mass) |"
        )
    lines.append("")
    lines.append("## kant ADOPT quorum")
    lines.append("")
    q = payload["quorum"]
    lines.append(f"- Plan A primary axes passed: **{q['primary_axes_passed']} of 3**")
    lines.append(f"- Plan A quorum threshold: **{q['quorum_threshold']}**")
    lines.append(f"- ICC(A,1) PASS (kernel-independent, from DA-14)")
    lines.append(
        f"- Vendi (DA-15 amended) PASS: **{q['vendi_swapped_pass']}** "
        f"(eligible encoders: {q['eligible_encoders']})"
    )
    lines.append(f"- Burrows reduction PASS: **{q['burrows_pass']}**")
    lines.append("")
    if payload["verdict"] == "ADOPT":
        lines.append("## Named limitations (Codex LOW-1 mandate)")
        lines.append("")
        lines.append(
            "**Burrows reduction remains FAIL** (v2 reduction = "
            f"{da14['burrows_reduction_pct']:.4f}% vs 5% target). Plan A is a"
            " measurement-side swap on the Vendi axis and does not improve"
            " German function-word stylometry. Plan A ADOPT therefore rests"
            " only on the DA-15 amended `vendi_semantic_v2_encoder_swap` axis"
            " plus the kernel-independent ICC(A,1) axis (2 of 3 quorum);"
            " Burrows axis remains open for Plan B (retrain) or reference-"
            "corpus work."
        )
        lines.append("")
    elif payload["verdict"] == "REJECT":
        lines.append("## Rejection rationale")
        lines.append("")
        lines.append(
            "No candidate encoder cleared both the calibration gate"
            f" (AUC ≥ {_VENDI_AUC_GATE}) and the DA-14 thresholds (cohens_d ≤"
            f" {_VENDI_D_GATE}, CI upper < 0) under standard + balanced"
            " bootstrap. Plan A is therefore unable to reach the kant 2-of-3"
            " quorum even with ICC(A,1) PASS. Phase 2 (Plan B = Candidate C"
            " targeted hybrid retrain) is the documented next step."
        )
        lines.append("")
    lines.append("## Pre-registration anchor")
    lines.append("")
    lines.append(
        "Encoder + HF revision SHA + library versions are pinned in"
        " `.steering/20260516-m9-c-adopt-da15-impl/decisions.md` D-2."
        " Output files (`da15-calibration-*.json`, `da15-rescore-*.json`)"
        " embed the runtime-detected revision SHA so the audit chain is"
        " self-contained."
    )
    lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="m9-c-adopt-da15-verdict")
    p.add_argument("--rescore", action="append", required=True, type=Path)
    p.add_argument("--calibration", action="append", required=True, type=Path)
    p.add_argument("--da14-verdict", required=True, type=Path)
    p.add_argument("--output-json", required=True, type=Path)
    p.add_argument("--output-md", required=True, type=Path)
    args = p.parse_args(argv)

    da14 = _load_json(args.da14_verdict)
    da14_axes = da14["axes"]
    da14_record = {
        "vendi_d": da14_axes["vendi_semantic"]["cohens_d"],
        "vendi_ci_hi": da14_axes["vendi_semantic"]["diff_ci_95"][1],
        "vendi_pass": "PASS" if da14_axes["vendi_semantic"]["pass"] else "FAIL",
        "burrows_point": da14_axes["burrows_reduction"]["v2_mean"],
        "burrows_reduction_pct": da14_axes["burrows_reduction"]["reduction_pct"],
        "icc_point": da14_axes["icc_a1"]["v2_point"],
        "icc_pass": "PASS" if da14_axes["icc_a1"]["pass"] else "FAIL",
        "throughput_pct": da14_axes["throughput"]["throughput_pct_of_baseline"],
        "throughput_pass": "PASS" if da14_axes["throughput"]["pass"] else "FAIL",
    }

    # Pair each rescore with its calibration by encoder name.
    rescores = {r["encoder"]: r for r in (_load_json(p) for p in args.rescore)}
    calibrations = {
        c["encoder"]: c for c in (_load_json(p) for p in args.calibration)
    }
    common = sorted(set(rescores) & set(calibrations))
    if not common:
        msg = "no encoder appears in both --rescore and --calibration"
        raise RuntimeError(msg)

    per_encoder = [_encoder_eligible(rescores[e], calibrations[e]) for e in common]
    eligible = [e for e in per_encoder if e["eligible_for_adopt"]]
    eligible_names = [e["encoder"] for e in eligible]

    vendi_swapped_pass = bool(eligible)
    icc_pass = da14_axes["icc_a1"]["pass"]
    burrows_pass = da14_axes["burrows_reduction"]["pass"]
    primary_axes_passed = sum(
        [vendi_swapped_pass, icc_pass, burrows_pass],
    )

    verdict = "ADOPT" if primary_axes_passed >= 2 else "REJECT"

    payload: dict[str, Any] = {
        "persona": "kant",
        "metric_amended": "vendi_semantic_v2_encoder_swap",
        "metric_historical": "vendi_semantic (DA-14 MPNet instrument)",
        "thresholds": {
            "vendi_cohens_d_le": _VENDI_D_GATE,
            "vendi_ci_upper_lt": 0.0,
            "vendi_calibration_auc_ge": _VENDI_AUC_GATE,
            "burrows_reduction_pct_ge": 5.0,
            "icc_point_ge": 0.55,
            "throughput_pct_ge": 70.0,
            "note": "DA-14 thresholds, unchanged. DA-15 swaps the encoder and renames the metric.",
        },
        "da14_record": da14_record,
        "per_encoder": per_encoder,
        "quorum": {
            "primary_axes_passed": primary_axes_passed,
            "quorum_threshold": "2_of_3",
            "vendi_swapped_pass": vendi_swapped_pass,
            "burrows_pass": burrows_pass,
            "icc_pass": icc_pass,
            "eligible_encoders": eligible_names,
        },
        "verdict": verdict,
        "named_limitations": {
            "burrows": (
                "Burrows reduction remains FAIL; German function-word"
                " stylometry is not improved by Plan A. Plan A ADOPT rests"
                " only on the DA-15 amended Vendi axis + ICC(A,1)."
            ),
        },
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    _write_markdown(payload, args.output_md)
    print(
        f"verdict={verdict} eligible_encoders={eligible_names} "
        f"primary_axes_passed={primary_axes_passed}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

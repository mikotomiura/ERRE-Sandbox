"""CLI: score a same-base C3b pilot into a ``*.c3b_verdict.json`` sidecar.

A thin entry over :func:`run_c3b_verdict_pipeline` with its **own** argparse so
the golden-capture CLI (:mod:`erre_sandbox.cli.eval_run_golden`) stays
byte-invariant. Invoked as ``python -m erre_sandbox.cli.c3b_verdict`` (the repo
convention; only ``erre-sandbox`` lives in ``[project.scripts]``).

The production encoder panel (mpnet + e5-large primary, bge-m3 exploratory, ADR
§5.1) is built via :func:`build_embedding_provider`, whose heavy
``sentence-transformers`` import is deferred to call time, so importing this
module does not pull the ML stack into the graph.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from erre_sandbox.evidence.individuation.c3b_pipeline import run_c3b_verdict_pipeline
from erre_sandbox.evidence.individuation.c3b_verdict import (
    EXPLORATORY_ENCODER_IDS,
    PRIMARY_ENCODER_IDS,
)
from erre_sandbox.evidence.individuation.c3b_verdict_report import (
    c3b_verdict_sidecar_path_for,
    write_c3b_verdict_sidecar_atomic,
)

logger = logging.getLogger(__name__)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="erre-c3b-verdict",
        description=(
            "Score a same-base C3b pilot (3-rikyu x flag-on/off x seed) into a "
            "frozen-ADR GO/REJECT/inconclusive/invalid verdict sidecar."
        ),
    )
    parser.add_argument(
        "--capture",
        action="append",
        required=True,
        metavar="DUCKDB",
        help=(
            "Path to one published capture .duckdb (with sibling .capture.json + "
            ".individuation.json). Repeat for every (seed, condition) cell."
        ),
    )
    parser.add_argument(
        "--run-id",
        required=True,
        help="Pilot run id stamped into the verdict sidecar.",
    )
    parser.add_argument(
        "--out",
        default=None,
        metavar="PATH",
        help=(
            "Verdict sidecar output path. Default: <first --capture>.c3b_verdict.json."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_arg_parser().parse_args(argv)

    # Heavy ML dep deferred (ADR §5.1 panel = mpnet + e5-large + bge-m3).
    from erre_sandbox.evidence.individuation.layer1 import (  # noqa: PLC0415
        build_embedding_provider,
    )

    encoders = [
        build_embedding_provider(model_id)
        for model_id in (*PRIMARY_ENCODER_IDS, *EXPLORATORY_ENCODER_IDS)
    ]
    capture_paths = [Path(c) for c in args.capture]
    out_path = (
        Path(args.out)
        if args.out is not None
        else c3b_verdict_sidecar_path_for(capture_paths[0])
    )

    report = run_c3b_verdict_pipeline(
        capture_paths,
        encoders=encoders,
        run_id=args.run_id,
        computed_at=datetime.now(UTC),
    )
    write_c3b_verdict_sidecar_atomic(out_path, report)
    logger.info(
        "c3b verdict run_id=%s verdict=%s out=%s",
        report.run_id,
        report.verdict,
        out_path,
    )
    logger.info("reason: %s", report.reason)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

#!/usr/bin/env python
"""Skill lever pilot — 実走記録から verdict を計算する (prereg v2 §5)。

入力 = 1 行 1 sample の JSONL (``skill_lever_scorer.Sample`` の欄) と、run が送った要求条件の JSON
(``skill_lever_scorer.request_meta`` と一致しなければ INVALID_SCORER)。certification =
``scripts/skill_lever_mutation_check.py`` の出力。判定は ``skill_lever_scorer.evaluate`` だけが行う。

実行 (repo root から)::

    uv run python scripts/skill_lever_evaluate.py --records <samples.jsonl> \\
        --meta <meta.json> --cert <v2_mutation.json> --out <results.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import skill_lever_scorer as sc  # noqa: E402

_PREREG = _REPO_ROOT / "experiments" / "20260926-skill-lever-pilot" / "prereg.md"


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", type=pathlib.Path, required=True)
    ap.add_argument("--meta", type=pathlib.Path, required=True)
    ap.add_argument("--cert", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    args = ap.parse_args(argv)

    lines = args.records.read_text(encoding="utf-8").splitlines()
    meta_text = args.meta.read_text(encoding="utf-8")
    report = sc.evaluate_records(lines, meta_text, args.cert)
    report["inputs"] = {
        "records_sha256": _sha256(args.records),
        "meta_sha256": _sha256(args.meta),
        "cert_sha256": _sha256(args.cert),
        "prereg_sha256": _sha256(_PREREG) if _PREREG.exists() else None,
        "n_lines": sum(bool(line.strip()) for line in lines),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"status={report['status']} verdict={report['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

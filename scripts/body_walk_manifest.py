#!/usr/bin/env python
"""探索を身体側へ (b) — 較正 pilot の凍結 manifest の書き出しと照合 (pilot prereg §8).

凍結時に、写像に関わる全ファイルの sha256 を ``manifest.json`` に書く。対象:
* prereg・run.sh・SEED・certification・見取り図
* 本登録のコード (battery・pilot scorer・模擬・写像・manifest 検査・変異 harness) と test
* import する凍結物 (v5 の battery / scorer / 模擬 / 写像、v4 の battery / 模擬、v2 / 旧 Stage B の scorer / battery)

pilot の実走後の写像 (``run.sh``) は、v2・v4・v5 manifest の照合に続けてこれを照合し、1 つでも違えば写像を計算しない。
照合は 2 つに分かれる:

* 結び付き (``binding_violations``):
  - certification (``results/pilot_mutation.json``): 変異の明細が登録変異の集合 (label と期待 test) と一致し、全て KILLED。
    記録 sha256 が現在の 14 ファイル・test・変異 harness と一致
  - 見取り図 (``results/decision_table.json``): 記録 sha256 が現在の 14 ファイルと一致し、登録した行 (s = 0 / 0.5 / 0.9) が
    全て computed で写像された
* 凍結条件 (``freeze_violations``): 見取り図の s = 0 の行が door-close でない (写像が恒真の door-close でない)。
  2026-09-30 の見取り図はこれを満たさず、user 裁定 DU-4 で door-close を確定した (写像は凍結しない)。
  ``--verify`` は ``MANIFEST BOUND, NOT FROZEN (door-close)`` を出して非 0 で終わるので、run.sh は止まる。
  ``--write`` は結び付きだけを要求し、証拠の記録として sha256 を書く

ERRE の sampling の凍結値 (``src/erre_sandbox/``) は manifest に入れない。凍結後の値の変化は battery の
``FROZEN_WALK`` の封印が検出する (値が変われば battery 違反 → pilot は invalid)。

実行 (repo root から)::

    uv run python scripts/body_walk_manifest.py --write    # 証拠の記録を書くときのみ
    uv run python scripts/body_walk_manifest.py --verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import body_walk_mutation_check as mut  # noqa: E402
from scripts import body_walk_pilot_scorer as ps  # noqa: E402
from scripts import body_walk_select as sel  # noqa: E402

EXP = "experiments/20260930-body-walk-calibration-pilot"
MANIFEST = f"{EXP}/manifest.json"
CERT = f"{EXP}/results/pilot_mutation.json"
TABLE = f"{EXP}/results/decision_table.json"
_TESTS = "tests/test_body_walk"
FROZEN_FILES: tuple[str, ...] = (
    f"{EXP}/prereg.md",
    f"{EXP}/run.sh",
    f"{EXP}/SEED",
    CERT,
    TABLE,
    "scripts/body_walk_battery.py",
    "scripts/body_walk_pilot_scorer.py",
    "scripts/body_walk_sim.py",
    "scripts/body_walk_select.py",
    "scripts/body_walk_manifest.py",
    "scripts/body_walk_mutation_check.py",
    "scripts/closed_loop_v5_battery.py",
    "scripts/closed_loop_v5_pilot_scorer.py",
    "scripts/closed_loop_v5_sim.py",
    "scripts/closed_loop_v5_select.py",
    "scripts/closed_loop_battery.py",
    "scripts/closed_loop_sim.py",
    "scripts/skill_lever_scorer.py",
    "scripts/skill_lever_battery.py",
    "scripts/stage_b_scorer.py",
    "scripts/stage_b_battery.py",
    f"{_TESTS}/__init__.py",
    f"{_TESTS}/conftest.py",
    f"{_TESTS}/test_battery.py",
    f"{_TESTS}/test_scorer.py",
    f"{_TESTS}/test_sim.py",
    f"{_TESTS}/test_select.py",
    f"{_TESTS}/test_manifest.py",
)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(
    root: pathlib.Path, files: tuple[str, ...] = FROZEN_FILES
) -> dict[str, str]:
    return {f: sha256(root / f) for f in files}


def manifest_violations(manifest: dict[str, str], root: pathlib.Path) -> list[str]:
    out: list[str] = []
    for f, want in manifest.items():
        p = root / f
        if not p.is_file():
            out.append(f"{f}: missing")
        elif sha256(p) != want:
            out.append(f"{f}: sha256 differs from the frozen manifest")
    return out


def certification_violations(cert: dict[str, Any], root: pathlib.Path) -> list[str]:
    """Certification: 自己申告でなく、明細・登録変異の集合・sha256 を照合する (Codex 2 回目 HIGH)."""
    out: list[str] = []
    if cert.get("all_killed") is not True:
        out.append("certification: not all mutants KILLED")
    if cert.get("target_sha256") != sel.certified_sha256(root):
        out.append("certification: recorded sha256 differs from current code")
    if cert.get("tests_sha256") != sel.tests_sha256(root):
        out.append("certification: recorded test sha256 differs from current tests")
    if cert.get("harness_sha256") != sel.harness_sha256(root):
        out.append(
            "certification: recorded harness sha256 differs from current harness"
        )
    rows = cert.get("mutants")
    if not isinstance(rows, list):
        return [*out, "certification: no mutant rows"]
    want = {m.label: sorted(m.expect) for m in mut.MUTANTS}
    got = {
        x.get("label"): x.get("expected_any_of") for x in rows if isinstance(x, dict)
    }
    if len(rows) != len(want) or got != want:
        out.append("certification: mutant rows differ from the registered mutants")
    if any(not isinstance(x, dict) or x.get("status") != "KILLED" for x in rows):
        out.append("certification: a mutant row is not KILLED")
    return out


TRIVIAL_DOOR_CLOSE: str = (
    "decision table: the s = 0 row is door-close (trivially door-close)"
)


def table_violations(table: dict[str, Any], root: pathlib.Path) -> list[str]:
    """見取り図の結び付き: 記録 sha256 が現在のコードと一致し、登録した行が全てあり、computed で写像された."""
    out: list[str] = []
    if table.get("target_sha256") != sel.certified_sha256(root):
        out.append("decision table: recorded sha256 differs from current code")
    rows = table.get("rows")
    if not isinstance(rows, list) or [
        x.get("s") for x in rows if isinstance(x, dict)
    ] != list(sel.TABLE_ROWS):
        return [*out, "decision table: rows differ from TABLE_ROWS"]
    mapped = (sel.STATUS_CHOSEN, sel.STATUS_DOOR_CLOSE)
    for x in rows:
        pilot = x.get("pilot") or {}
        mapping = x.get("mapping") or {}
        if pilot.get("status") != ps.STATUS_COMPUTED or mapping.get("status") not in (
            mapped
        ):
            out.append(
                f"decision table: row s={x.get('s')} was not computed and mapped"
            )
    return out


def freeze_violations(table: dict[str, Any]) -> list[str]:
    """凍結条件: 見取り図の s = 0 の行が door-close でない.

    s = 0 (前回を全く反復しない仮想の挙動) でも door-close なら、写像は pilot の結果に依らず door-close になる
    (恒真の選定、v5 DP-6 の型)。2026-09-30 の見取り図はこれに当たり、user 裁定 DU-4 で door-close を確定した
    (本登録の写像は凍結しない)。したがって本 manifest の ``--verify`` は ``MANIFEST OK`` を出さず、run.sh は止まる。
    """
    rows = table.get("rows")
    if (
        not isinstance(rows, list)
        or not rows
        or not isinstance(rows[0], dict)
        or (rows[0].get("mapping") or {}).get("status") != sel.STATUS_CHOSEN
    ):
        return [TRIVIAL_DOOR_CLOSE]
    return []


def _load_artifacts(
    root: pathlib.Path,
) -> tuple[dict[str, Any], dict[str, Any]] | str:
    try:
        cert: dict[str, Any] = json.loads((root / CERT).read_text(encoding="utf-8"))
        table: dict[str, Any] = json.loads((root / TABLE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"cannot read certification / decision table: {exc}"
    return cert, table


def binding_violations(root: pathlib.Path) -> list[str]:
    """Certification と見取り図が現在のコード・test・harness に結び付き、中身が揃っているか (凍結条件は別)."""
    loaded = _load_artifacts(root)
    if isinstance(loaded, str):
        return [loaded]
    cert, table = loaded
    return certification_violations(cert, root) + table_violations(table, root)


def consistency_violations(root: pathlib.Path) -> list[str]:
    """結び付き + 凍結条件 (写像を凍結できるか)."""
    loaded = _load_artifacts(root)
    if isinstance(loaded, str):
        return [loaded]
    return binding_violations(root) + freeze_violations(loaded[1])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--write",
        action="store_true",
        help="証拠の記録として sha256 を書く (結び付きだけを要求する。凍結条件は --verify が照合する)",
    )
    mode.add_argument("--verify", action="store_true")
    args = ap.parse_args(argv)

    binding = binding_violations(_REPO_ROOT)
    if args.write:
        if binding:
            print("\n".join(f"ERROR: {p}" for p in binding))
            return 1
        path = _REPO_ROOT / MANIFEST
        path.write_text(
            json.dumps(build_manifest(_REPO_ROOT), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"wrote {MANIFEST} ({len(FROZEN_FILES)} files)")
        return 0
    manifest = json.loads((_REPO_ROOT / MANIFEST).read_text(encoding="utf-8"))
    problems = manifest_violations(manifest, _REPO_ROOT) + binding
    if set(manifest) != set(FROZEN_FILES):
        problems.append("manifest file list differs from FROZEN_FILES")
    for p in problems:
        print(f"MISMATCH: {p}")
    loaded = _load_artifacts(_REPO_ROOT)
    freeze = [] if isinstance(loaded, str) else freeze_violations(loaded[1])
    for p in freeze:
        print(f"NOT FROZEN: {p} (door-close, user 裁定 DU-4)")
    if problems:
        print(f"MANIFEST MISMATCH ({len(problems)})")
    elif freeze:
        print("MANIFEST BOUND, NOT FROZEN (door-close)")
    else:
        print("MANIFEST OK")
    return 0 if not problems and not freeze else 1


if __name__ == "__main__":
    sys.exit(main())

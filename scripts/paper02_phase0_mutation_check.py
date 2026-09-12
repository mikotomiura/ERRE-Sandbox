#!/usr/bin/env python
"""Phase 0 guards の mutation check — 判定を壊すと test が本当に落ちるか。

``scripts/paper02_phase0_pilot.py`` の各判定を 1 つずつ壊し、
``tests/test_integration/test_paper02_phase0_pilot.py`` が **exit code 非 0**
で落ちることを実測する。落ちなかった (= SURVIVED) 改変があれば、その判定は
どの test にも pin されておらず、緑は恒真だったということになる。

なぜ要るか: negative fixture を「置いた」だけでは、それが判定関数を通って
いない限り何も検査していない (``feedback_witness_needs_mutation_testing``、
2026-09-07 に実際に踏んだ穴)。Phase 0 の禁止 P-1〜P-4 は *装置で* 強制すると
上位 ADR が定めているので、その装置が効いていることを exit code で示す必要がある。

実行 (repo root から)::

    uv run python scripts/paper02_phase0_mutation_check.py

対象ファイルは実行中だけ書き換わり、**必ず原状復帰する** (finally + sha256 照合)。
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_TARGET = _REPO_ROOT / "scripts" / "paper02_phase0_pilot.py"
_TEST = "tests/test_integration/test_paper02_phase0_pilot.py"

#: ``(ラベル, 置換前, 置換後)``。置換前は対象ファイルに 1 回だけ現れること。
MUTATIONS: tuple[tuple[str, str, str], ...] = (
    (
        "M1  G1: drop the meta_path finder registration",
        "    finder = _ScorerBlockingFinder()\n    sys.meta_path.insert(0, finder)\n",
        "    finder = _ScorerBlockingFinder()\n",
    ),
    (
        "M2  G1: drop the already-imported check",
        "    already = [name for name in sys.modules if SCORER_NEEDLE in name]\n"
        "    if already:\n"
        "        raise ScorerImportError(\n"
        '            f"P-1 violation: scorer already imported before the guard: '
        '{already!r}"\n'
        "        )\n",
        "    already = []\n",
    ),
    (
        "M3  G2: drop the plain-import branch",
        "        if isinstance(node, ast.Import):\n"
        "            hits.extend(a.name for a in node.names if SCORER_NEEDLE in a.name)",
        "        if False:\n            pass",
    ),
    (
        "M4  G2: drop the from-import branch",
        "        elif (\n"
        "            isinstance(node, ast.ImportFrom)\n"
        "            and node.module\n"
        "            and SCORER_NEEDLE in node.module\n"
        "        ):\n"
        "            hits.append(node.module)",
        "        elif False:\n            pass",
    ),
    (
        "M5  G2b: drop the dynamic-import scan",
        "            hits.extend(\n"
        "                a.name\n"
        "                for a in node.names\n"
        '                if a.name.split(".")[0] in _DYNAMIC_IMPORT_NAMES\n'
        "            )",
        "            pass",
    ),
    (
        "M6  G3: always report 'not imported'",
        '    return completed.stdout.strip() == "True"',
        "    return False",
    ),
    (
        "M7  G4: drop the flatness check",
        "        if isinstance(value, Mapping):\n"
        '            raise VerdictBlindError(f"nested mapping under {key!r} '
        '— breaks flatness")\n',
        "",
    ),
    (
        "M8  G4: drop the scalar check",
        "        if not isinstance(value, (str, int, float, bool, type(None))):\n"
        "            raise VerdictBlindError(\n"
        '                f"non-scalar value under {key!r} ({type(value).__name__}) — "\n'
        '                "breakdowns must be unrepresentable"\n'
        "            )\n",
        "",
    ),
    (
        "M9  G4: drop the finiteness check",
        "        if isinstance(value, float) and not math.isfinite(value):\n"
        '            raise VerdictBlindError(f"non-finite float under {key!r}: '
        '{value!r}")\n',
        "",
    ),
    (
        "M10 G4: drop the key-set check",
        "    actual = set(payload)\n    if actual != set(allowed):\n",
        "    actual = set(payload)\n    if False:\n",
    ),
    (
        "M11 G4: drop the forbidden-token check",
        "        hits = forbidden_token_hits(key)\n"
        "        if hits:\n"
        '            raise VerdictBlindError(f"forbidden token(s) {hits} in key '
        '{key!r}")\n'
        "        if isinstance(value, str):\n"
        "            hits = forbidden_token_hits(value)\n"
        "            if hits:\n"
        "                raise VerdictBlindError(\n"
        '                    f"forbidden token(s) {hits} in the value of {key!r}"\n'
        "                )\n",
        "        pass\n",
    ),
    (
        "M12 G5: add a condition field to PilotDraw",
        "    plan_parsed: bool\n    zone_present: bool\n",
        '    plan_parsed: bool\n    zone_present: bool\n    condition: str = ""\n',
    ),
    (
        "M13 I-1: stop scrubbing, return the real response",
        "        return ChatResponse(\n"
        "            content=_SCRUBBED_RESPONSE,\n"
        "            model=_SCRUBBED_MODEL_TAG,\n"
        "            eval_count=0,\n"
        "            total_duration_ms=0.0,\n"
        "        )",
        "        return response",
    ),
    (
        "M14 HIGH-3: collect parse metrics for every role",
        "        if self._collect_parse:\n"
        "            self._draws.append(project_response(response.content))",
        "        self._draws.append(project_response(response.content))",
    ),
    (
        "M15 bands: move a boundary onto the R4 threshold",
        "BAND_LOW: Final[float] = 0.2",
        "BAND_LOW: Final[float] = 0.5",
    ),
    (
        "M16 tokens: drop 'study' from ARTIFACT_LEAK_TOKENS",
        'ARTIFACT_LEAK_TOKENS: Final[tuple[str, ...]] = (\n    "study",\n',
        "ARTIFACT_LEAK_TOKENS: Final[tuple[str, ...]] = (\n",
    ),
    (
        "M17 tokens: drop 'mc_index' from ARTIFACT_LEAK_TOKENS",
        '    "mc_index",\n)',
        ")",
    ),
    (
        "M18 tokens: drop 'permutation' from FORBIDDEN_TOKENS",
        '    "permutation",\n    "entropy",',
        '    "entropy",',
    ),
    (
        "M19 tokens: drop 'garden' from FORBIDDEN_TOKENS",
        '    "agora",\n    "garden",\n)',
        '    "agora",\n)',
    ),
    (
        "M20 scanner: forbidden_token_hits always empty",
        "    lowered = text.lower()\n"
        "    return tuple(token for token in tokens if token in lowered)",
        "    return ()",
    ),
    (
        "M21 scanner: artifact_tree_leak_hits always empty",
        '        hits.extend(\n            f"{rel}: {token}"\n'
        "            for token in forbidden_token_hits(text, ARTIFACT_LEAK_TOKENS)\n"
        "        )",
        "        pass",
    ),
)


def main() -> int:
    original = _TARGET.read_text(encoding="utf-8")
    sha_before = hashlib.sha256(original.encode("utf-8")).hexdigest()
    env = dict(os.environ, PYTHONUTF8="1")
    results: list[tuple[str, str, int]] = []
    try:
        for label, old, new in MUTATIONS:
            if original.count(old) != 1:
                results.append((label, f"ANCHOR x{original.count(old)}", -1))
                continue
            _TARGET.write_text(original.replace(old, new, 1), encoding="utf-8")
            proc = subprocess.run(  # noqa: S603
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    _TEST,
                ],
                cwd=str(_REPO_ROOT),
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                check=False,
            )
            summary = [
                line
                for line in (proc.stdout or "").splitlines()
                if "passed" in line or "failed" in line or "error" in line
            ]
            results.append(
                (
                    label,
                    summary[-1].strip() if summary else "(no summary)",
                    proc.returncode,
                )
            )
    finally:
        _TARGET.write_text(original, encoding="utf-8")

    sha_after = hashlib.sha256(
        _TARGET.read_text(encoding="utf-8").encode("utf-8")
    ).hexdigest()
    survived = [label for label, _, code in results if code == 0]
    # アンカーが 0 個 / 複数だと改変自体が起きていない。緑に見せずに失敗させる。
    unanchored = [label for label, _, code in results if code < 0]

    print(f"{'mutation':52s} exit  pytest summary")
    print("-" * 100)
    for label, summary, code in results:
        marker = "SURVIVED!! " if code == 0 else ""
        print(f"{label:52s} {code:>4}  {marker}{summary}")
    print("-" * 100)
    print(f"source restored (sha256 match): {sha_before == sha_after}")
    print(f"SURVIVED (bad): {len(survived)} / {len(results)}")
    if unanchored:
        print(f"ERROR: アンカーが一意でない改変: {unanchored}")
    if sha_before != sha_after:
        print("ERROR: 対象ファイルが原状復帰していない")
        return 2
    return 1 if (survived or unanchored) else 0


if __name__ == "__main__":
    sys.exit(main())

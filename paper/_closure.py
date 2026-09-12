"""論文リポジトリへ持ち出す `erre_sandbox` モジュールの推移閉包を出す。

`gather.ps1` から呼ばれる。エントリ点のモジュールが import しているものを AST で辿り、
**実際に要るファイルだけ**を列挙する。手で列挙すると import が増えたときに黙って
取りこぼし、移送先で `repro.sh` が落ちる — それを避けるための機械化。

出力は 1 行 1 件の TSV: `<src からの相対パス>\t<パッケージ相対パス>`
  例: `erre_sandbox/evidence/es4_actuator/battery.py\terre_sandbox/evidence/es4_actuator/battery.py`

`data/` などの非 .py 添付物も一緒に出す (battery.py は
`Path(__file__).parent / "data"` で yaml を探すので、パッケージと同じ場所に無いと落ちる)。

使い方:
    python paper/_closure.py 01
    python paper/_closure.py 02
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"

# 論文ごとのエントリ点。ここに「その論文の解析が直接触るモジュール」だけを書く。
# 間接依存は AST が自動で拾うので書かない。
ENTRIES: dict[str, tuple[str, ...]] = {
    "01": (
        "erre_sandbox.evidence.es4_actuator.battery",
        "erre_sandbox.evidence.es4_actuator.constants",
        "erre_sandbox.evidence.es4_actuator.controls",
        "erre_sandbox.evidence.es4_actuator.reference",
        "erre_sandbox.evidence.es4_actuator.scoring",
        "erre_sandbox.evidence.tier_b.vendi",
    ),
    "02": (
        "erre_sandbox.evidence.es3_locomotion.controls",
        "erre_sandbox.evidence.es3_locomotion.decomposition",
        "erre_sandbox.evidence.es3_locomotion.scenario",
        "erre_sandbox.evidence.es3_locomotion.verdict_report",
        "erre_sandbox.evidence.spdm.probe",
        "erre_sandbox.evidence.spdm.scenario",
        "erre_sandbox.evidence.spdm.verdict_report",
        "erre_sandbox.integration.embodied.bank_power",
        # C-proper の verdict を産んだ scorer。data/raw/cproper-verdict.json が
        # scorer_schema_version="ecl-cproper-scorer-1" を宣言しているのに閉包から
        # 漏れており、中核 verdict が論文 repo 単体で再導出できなかった
        # (2026-09-12、code-reviewer HIGH-3)。_MOVE-IN.done.md §3 の
        # 「C-proper scorer ... 所在を特定してから移す」がこれで閉じる。
        "erre_sandbox.integration.embodied.bank_scorer",
    ),
}

# パッケージに同梱された非コード資産 (module prefix -> 相対ディレクトリ)。
# battery.py が `Path(__file__).parent / "data"` を読むので、これが無いと import は
# 通っても実行時に落ちる。
DATA_DIRS: dict[str, str] = {
    "erre_sandbox.evidence.es4_actuator": "data",
}


def module_to_path(mod: str) -> Path | None:
    p = SRC / (mod.replace(".", "/") + ".py")
    if p.exists():
        return p
    p = SRC / mod.replace(".", "/") / "__init__.py"
    return p if p.exists() else None


def transitive_closure(entries: tuple[str, ...]) -> set[str]:
    """`entries` から到達可能な erre_sandbox モジュール名の集合。

    `from x import y` の `y` がサブモジュールのこともあるので、`x.y` も候補に入れる
    (存在しなければ `module_to_path` が None を返して落ちるだけ)。
    """
    seen: set[str] = set()
    stack = list(entries)
    while stack:
        mod = stack.pop()
        if mod in seen:
            continue
        path = module_to_path(mod)
        if path is None:
            continue
        seen.add(mod)
        # 親パッケージの __init__.py も要る
        parts = mod.split(".")
        for i in range(1, len(parts)):
            stack.append(".".join(parts[:i]))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("erre_sandbox"):
                    stack.append(node.module)
                    for alias in node.names:
                        stack.append(f"{node.module}.{alias.name}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("erre_sandbox"):
                        stack.append(alias.name)
    return seen


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ENTRIES:
        print(f"usage: {sys.argv[0]} {{{'|'.join(ENTRIES)}}}", file=sys.stderr)
        return 2
    paper = sys.argv[1]
    mods = transitive_closure(ENTRIES[paper])

    out: list[str] = []
    for mod in sorted(mods):
        path = module_to_path(mod)
        if path is None:
            continue
        rel = path.relative_to(SRC).as_posix()
        out.append(rel)
        data_dir = DATA_DIRS.get(mod)
        if data_dir:
            for f in sorted((path.parent / data_dir).glob("*")):
                if f.is_file():
                    out.append(f.relative_to(SRC).as_posix())

    for rel in out:
        print(rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

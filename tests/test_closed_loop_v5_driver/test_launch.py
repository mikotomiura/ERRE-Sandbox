"""閉ループ v5 driver の起動の前提・import 制限・certification (実走はしない)."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest
from scripts import closed_loop_v5_driver as drv
from scripts import closed_loop_v5_driver_mutation_check as mutation


def test_driver_does_not_import_other_drivers() -> None:
    """判定に関わる行を本ファイルに置く (v4 driver を import しない).

    import 先は凍結物だけ。
    """
    tree = ast.parse(Path(drv.__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    harness = "scripts.closed_loop_v5_driver_mutation_check"
    assert not any("_driver" in n for n in names - {harness})
    local = {n for n in names if n.startswith(("scripts", "erre_sandbox"))}
    assert local == {
        "scripts",
        harness,  # certification が登録変異の集合を照合する
        "scripts.closed_loop_battery",
        "scripts.closed_loop_v5_battery",
        "scripts.closed_loop_v5_pilot_scorer",
        "scripts.skill_lever_battery",
        "scripts.skill_lever_scorer",
        "scripts.skill_lever_scorer.messages_sha256",
        "scripts.skill_lever_scorer.parse_choice",
        "scripts.skill_lever_scorer.request_meta",
        "erre_sandbox.inference.ollama_adapter",
        "erre_sandbox.inference.ollama_adapter.ChatMessage",
        "erre_sandbox.inference.ollama_adapter.ChatResponse",
        "erre_sandbox.inference.ollama_adapter.OllamaChatClient",
        "erre_sandbox.inference.ollama_adapter.OllamaUnavailableError",
        "erre_sandbox.inference.sampling",
        "erre_sandbox.inference.sampling.ResolvedSampling",
    }


def _script(tmp_path: Path, name: str, body: str) -> str:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_manifest_problems_require_manifest_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ok = _script(tmp_path, "ok.py", "print('checking')\nprint('MANIFEST OK')\n")
    bad = _script(
        tmp_path, "bad.py", "print('MANIFEST MISMATCH (1)')\nraise SystemExit(1)\n"
    )
    silent = _script(tmp_path, "silent.py", "print('MANIFEST OK')\nprint('x')\n")
    crash = _script(tmp_path, "crash.py", "print('MANIFEST OK')\nraise SystemExit(2)\n")
    monkeypatch.setattr(drv, "MANIFEST_CHECKS", (ok,))
    assert drv.manifest_problems() == []
    for script in (bad, silent, crash):
        monkeypatch.setattr(drv, "MANIFEST_CHECKS", (ok, script))
        assert len(drv.manifest_problems()) == 1
    monkeypatch.setattr(drv, "MANIFEST_CHECKS", (str(tmp_path / "missing.py"),))
    assert len(drv.manifest_problems()) == 1


def test_committed_manifests_pass_the_launch_check() -> None:
    """run.sh と同じ凍結 manifest (v2 → v4 → v5) を、同じ順に照合する.

    凍結物に触れていないことの確認を兼ねる。
    """
    assert drv.MANIFEST_CHECKS == (
        "scripts/skill_lever_manifest.py",
        "scripts/closed_loop_manifest.py",
        "scripts/closed_loop_v5_manifest.py",
    )
    run_sh = (drv._EXP_DIR / "run.sh").read_text(encoding="utf-8")
    order = [run_sh.index(f'"$PYTHON" {s} --verify') for s in drv.MANIFEST_CHECKS]
    assert order == sorted(order)
    assert sys.executable
    assert drv.manifest_problems() == []


def test_run_sh_gates_on_the_published_name() -> None:
    """凍結 run.sh は写像の前に公開名 (records.jsonl) の存在を検査する (DV-1 の前提)."""
    run_sh = (drv._EXP_DIR / "run.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in run_sh
    gate = run_sh.index(f'test -f "$RUN_DIR/{drv.RECORDS_NAME}"')
    assert gate < run_sh.index("closed_loop_v5_select")
    assert drv.DEFAULT_RUN_DIR == drv._EXP_DIR / "results" / "run"
    assert 'RUN_DIR="$EXP_DIR/results/run"' in run_sh
    assert drv.PARTIAL_NAME != drv.RECORDS_NAME


def test_launch_problems_include_manifest_and_certification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(drv, "manifest_problems", lambda: ["manifest boom"])
    monkeypatch.setattr(drv, "DRIVER_CERT", tmp_path / "missing.json")
    problems = drv.launch_problems()
    assert "manifest boom" in problems
    assert any("driver certification unreadable" in p for p in problems)


def test_main_refuses_to_launch_without_touching_the_run_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[object] = []

    async def must_not_run(*args: object, **_kwargs: object) -> str:
        called.append(args)  # 実 endpoint には繋がない (変異で起動拒否が外れても安全)
        return drv.REASON_ABORTED

    monkeypatch.setattr(drv, "launch_problems", lambda: ["nope"])
    monkeypatch.setattr(drv, "run", must_not_run)
    monkeypatch.setattr(drv, "DEFAULT_RUN_DIR", tmp_path / "run")
    code = drv.main([])
    assert code == drv.EXIT_CODES[drv.REASON_ABORTED]
    assert called == []
    assert not (tmp_path / "run").exists()


def test_main_takes_no_run_dir_or_endpoint() -> None:
    """登録外の実走経路を閉じる: run dir と endpoint は固定."""
    for extra in (["--run-dir", "x"], ["--endpoint", "http://example"]):
        with pytest.raises(SystemExit):
            drv.main(extra)


def test_driver_certification_detects_stale_or_failing(tmp_path: Path) -> None:
    rows = [{"label": m.label, "status": "KILLED"} for m in mutation.MUTANTS]
    good = {
        "target_sha256": drv.certified_files(),
        "all_killed": True,
        "mutants": rows,
    }
    cert = tmp_path / "cert.json"
    cert.write_text(json.dumps(good), encoding="utf-8")
    assert drv.driver_certification_problems(cert) == []
    cert.write_text(json.dumps({**good, "all_killed": False}), encoding="utf-8")
    assert drv.driver_certification_problems(cert) == [
        "driver certification: not all KILLED"
    ]
    cert.write_text(json.dumps({**good, "all_killed": "true"}), encoding="utf-8")
    assert drv.driver_certification_problems(cert) == [
        "driver certification: not all KILLED"
    ]
    stale = {**good["target_sha256"], "closed_loop_v5_driver.py": "0" * 64}
    cert.write_text(json.dumps({**good, "target_sha256": stale}), encoding="utf-8")
    assert len(drv.driver_certification_problems(cert)) == 1
    assert drv.driver_certification_problems(tmp_path / "missing.json")
    # 変異の集合・各行の status (all_killed だけを信じない)
    survived = [*rows[:-1], {**rows[-1], "status": "SURVIVED"}]
    for bad in ([], rows[:-1], [*rows, rows[0]], rows[::-1], survived):
        cert.write_text(json.dumps({**good, "mutants": bad}), encoding="utf-8")
        assert drv.driver_certification_problems(cert) == [
            "driver certification: mutants differ from the registered set "
            "or are not all KILLED"
        ]
    for broken in (None, [1], [{"label": "x"}]):
        cert.write_text(json.dumps({**good, "mutants": broken}), encoding="utf-8")
        assert drv.driver_certification_problems(cert) == [
            f"driver certification unreadable: {cert}"
        ]
    assert set(good["target_sha256"]) == {
        "closed_loop_v5_driver.py",
        "closed_loop_v5_driver_mutation_check.py",
        "tests/__init__.py",
        "tests/_mock.py",
        "tests/conftest.py",
        "tests/test_driver.py",
        "tests/test_launch.py",
    }
    assert None not in good["target_sha256"].values()


def test_launch_problems_check_git_tracking_and_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(drv, "manifest_problems", list)
    monkeypatch.setattr(drv, "driver_certification_problems", lambda _p: [])
    monkeypatch.setattr(drv, "_git", lambda *_a: "")
    assert drv.launch_problems() == []
    monkeypatch.setattr(drv, "_git", lambda *_a: None)
    problems = drv.launch_problems()
    assert sum(p.startswith("not tracked by git") for p in problems) == len(drv.PINNED)
    assert any("differ from HEAD" in p for p in problems)

    def untracked_only(*args: str) -> str | None:
        return None if args[0] == "ls-files" else ""

    monkeypatch.setattr(drv, "_git", untracked_only)
    assert not any("HEAD" in p for p in drv.launch_problems())

    def diff_only(*args: str) -> str | None:
        return None if args[0] == "diff" else ""

    monkeypatch.setattr(drv, "_git", diff_only)
    assert drv.launch_problems() == [
        "pinned files differ from HEAD (or git unavailable)"
    ]


def test_pinned_covers_the_judgement_path() -> None:
    exp = "experiments/20260928-closed-loop-v5-calibration-pilot"
    must = {
        "scripts/closed_loop_v5_driver.py",
        "scripts/closed_loop_v5_driver_mutation_check.py",
        "scripts/closed_loop_v5_battery.py",
        "scripts/closed_loop_v5_pilot_scorer.py",
        "scripts/closed_loop_v5_select.py",
        "scripts/closed_loop_v5_manifest.py",
        "scripts/closed_loop_battery.py",
        "scripts/skill_lever_scorer.py",
        "src/erre_sandbox/inference/ollama_adapter.py",
        f"{exp}/run.sh",
        f"{exp}/prereg.md",
        f"{exp}/manifest.json",
        f"{exp}/SEED",
        f"{exp}/results/pilot_mutation.json",
        f"{exp}/results/driver_mutation.json",
    }
    assert must <= set(drv.PINNED)
    assert {f"scripts/{s}" for s in drv.CERTIFIED_SCRIPTS} <= set(drv.PINNED)
    root = Path(drv.__file__).resolve().parents[1]
    missing = [
        p for p in drv.PINNED if not (root / p).exists() and "driver_mutation" not in p
    ]
    assert missing == []


def test_committed_driver_certification_is_current() -> None:
    """commit 済み driver_mutation.json が現在の driver・harness・test と一致.

    変異試験の実行中は外す。
    """
    assert drv.driver_certification_problems(drv.DRIVER_CERT) == []

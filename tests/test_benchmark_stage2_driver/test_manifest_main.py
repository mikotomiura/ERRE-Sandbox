"""判別性 gate 段 2 — 第 2 段の封印 ``manifest_main.json`` の照合と本走の入口 (H2).

一時の root (``main_tree.build_tree``、合成の証明書) で、検査 1〜9 の正例と、
1 項目ずつ崩した負例を見る。driver は送信前 (``plan_for`` の本走の枝)、
scorer は判定前 (``compute_verdict``) に照合する。書き手
``scripts/benchmark_stage2_freeze.py`` の排他的作成と拒否も見る
(見取り図の再計算は実 repo の照合で)。
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
from typing import TYPE_CHECKING, Any

import pytest
from scripts import benchmark_stage2_driver as dr
from scripts import benchmark_stage2_freeze as fz
from scripts import benchmark_stage2_manifest as man
from scripts import benchmark_stage2_manifest_main as mm
from scripts import benchmark_stage2_plan as pl
from scripts import benchmark_stage2_scorer as sc

from tests.test_benchmark_stage2_driver.main_tree import build_tree, write_json
from tests.test_benchmark_stage2_driver.test_driver import MODELS_SHA, _min_gate

if TYPE_CHECKING:
    from collections.abc import Callable

GATE = _min_gate({"O_time": 6})


@pytest.fixture(scope="module")
def base(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    return build_tree(
        tmp_path_factory.mktemp("base") / "root",
        gate_bytes=json.dumps(GATE).encode("utf-8"),
        models_bytes=dr.MODELS_JSON.read_bytes(),
    )


@pytest.fixture
def root(base: pathlib.Path, tmp_path: pathlib.Path) -> pathlib.Path:
    dst = tmp_path / "root"
    shutil.copytree(base, dst)
    return dst


def _gate_bytes(root: pathlib.Path) -> bytes:
    return (root / mm.GATE).read_bytes()


def found(root: pathlib.Path, **kw: Any) -> list[str]:
    args: dict[str, Any] = {"gate_bytes": _gate_bytes(root), "models_sha": MODELS_SHA}
    args.update(kw)
    return mm.violations(root, **args)


def _sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def edit_rec(root: pathlib.Path, f: Callable[[dict[str, Any]], None]) -> None:
    rec = json.loads((root / mm.MANIFEST_MAIN).read_text(encoding="utf-8"))
    f(rec)
    write_json(root / mm.MANIFEST_MAIN, rec)


def edit_bound_json(
    root: pathlib.Path, rel: str, key: str, f: Callable[[dict[str, Any]], None]
) -> None:
    """記録が sha で束ねる JSON を書き換え、記録の sha も合わせる.

    中の検査だけを崩す。
    """
    obj = json.loads((root / rel).read_text(encoding="utf-8"))
    f(obj)
    write_json(root / rel, obj)
    sha = _sha(root / rel)
    edit_rec(root, lambda r: r.__setitem__(key, sha))


def append(root: pathlib.Path, rel: str) -> None:
    with (root / rel).open("ab") as fh:
        fh.write(b"\n# changed\n")


# ------------------------------------------------------------ 正例


def test_tree_passes(root: pathlib.Path) -> None:
    assert found(root) == []
    rec = mm.require(root, gate_bytes=_gate_bytes(root), models_sha=MODELS_SHA)
    assert rec["stage"] == "main"
    assert rec["battery_checks"]["O_time"]["R"] == 6
    assert rec["battery_checks"]["O_time"]["checks"]
    assert set(rec["battery_checks"]) == {"O_time"}


def test_missing_manifest_is_refused(root: pathlib.Path) -> None:
    (root / mm.MANIFEST_MAIN).unlink()
    assert found(root) == ["manifest_main.json: missing"]
    with pytest.raises(mm.ManifestError, match="missing"):
        mm.require(root, gate_bytes=_gate_bytes(root), models_sha=MODELS_SHA)


# ------------------------------------------------------------ 1. stage・status・prereg


def test_1_stage_must_be_main(root: pathlib.Path) -> None:
    edit_rec(root, lambda r: r.__setitem__("stage", "pilot"))
    assert found(root) == ["manifest_main: stage is not main"]


def test_1_prereg_status_must_be_frozen(root: pathlib.Path) -> None:
    p = root / man.PREREG
    p.write_bytes(
        p.read_bytes().replace(
            mm.STATUS_MAIN.encode("utf-8"), man.STATUS_PILOT.encode("utf-8"), 1
        )
    )
    sha = _sha(p)
    edit_rec(root, lambda r: r.__setitem__("prereg_sha256", sha))
    assert found(root) == ["prereg: status is not FROZEN"]


def test_1_prereg_sha_is_bound(root: pathlib.Path) -> None:
    edit_rec(root, lambda r: r.__setitem__("prereg_sha256", "0" * 64))
    assert found(root) == ["prereg: sha256 differs from the record"]


# ------------------------------------------------------------ 2. 第 1 段の封印


def test_2_prereg_body_must_match_stage1(root: pathlib.Path) -> None:
    append(root, man.PREREG)
    sha = _sha(root / man.PREREG)
    edit_rec(root, lambda r: r.__setitem__("prereg_sha256", sha))
    assert found(root) == [
        "prereg: body differs from manifest.json (only the status line may change)"
    ]


def test_2_stage1_manifest_sha_is_bound(root: pathlib.Path) -> None:
    append(root, man.MANIFEST)
    assert found(root) == ["manifest.json: sha256 differs from the record"]


def test_2_stage1_files_are_checked(root: pathlib.Path) -> None:
    append(root, f"{man.EXP}/run.sh")
    assert found(root) == [f"{man.EXP}/run.sh: sha256 differs from manifest.json"]


def test_2_stage1_file_set_is_checked(root: pathlib.Path) -> None:
    edit_bound_json(
        root,
        man.MANIFEST,
        "manifest_pilot_sha256",
        lambda m: m["files"].pop(f"{man.EXP}/run.sh"),
    )
    assert found(root) == [
        "manifest.json: the frozen file set differs",
        f"{man.EXP}/run.sh: sha256 differs from manifest.json",
    ]


def test_2_stage1_sketch_conclusion_is_checked(root: pathlib.Path) -> None:
    fx = json.loads((root / man.FIXTURE_DIFFS).read_text(encoding="utf-8"))
    src = fx["batteries"]["G"]["source"]["path"]
    append(root, src)
    assert found(root) == ["fixture_diffs: G source differs from the frozen table"]


# ------------------------------------------------------------ 3. 証明書


def test_3_certificate_sha_is_bound(root: pathlib.Path) -> None:
    append(root, mm.CERT)
    assert found(root) == ["certificate: sha256 differs from the record"]


def test_3_certificate_missing(root: pathlib.Path) -> None:
    (root / mm.CERT).unlink()
    assert found(root) == ["certificate: missing"]


@pytest.mark.parametrize(
    ("change", "want"),
    [
        (
            lambda c: c.__setitem__("version", "pre_pilot"),
            "certificate: version is not pre_main",
        ),
        (
            lambda c: c.update(all_killed=False),
            "certificate: not all killed",
        ),
        (lambda c: c.__setitem__("all_killed", 1), "certificate: not all killed"),
        (
            lambda c: c["targets"].pop("manifest_main"),
            "certificate: targets differ (manifest_main must be a target)",
        ),
        (
            lambda c: c["target_sha256"].pop("tests/test_driver.py"),
            "certificate: target_sha256 covers a different file set",
        ),
        (
            lambda c: c["witness_tests_sha256"].pop(mm.CERT_WITNESS_EXTRA[0]),
            "certificate: witness_tests_sha256 covers a different file set",
        ),
        (
            lambda c: c.__setitem__("inputs_sha256", {}),
            "certificate: inputs_sha256 covers a different file set",
        ),
        (lambda c: c.__setitem__("mutants", []), "certificate: no mutant rows"),
        (
            lambda c: c["mutants"][0].__setitem__("status", "SURVIVED"),
            "certificate: a mutant row is not KILLED",
        ),
        (
            lambda c: c["mutants"].pop(),
            "certificate: a target has no mutant",
        ),
        (
            lambda c: c.__setitem__("meta_test", []),
            "certificate: the meta-test did not hold",
        ),
        (
            lambda c: c["meta_test"][0].__setitem__("status", "SURVIVED"),
            "certificate: the meta-test did not hold",
        ),
    ],
    ids=[
        "version",
        "killed",
        "killed_truthy",
        "targets",
        "tests",
        "witness",
        "inputs",
        "no_rows",
        "survived_row",
        "uncovered_target",
        "no_meta",
        "failed_meta",
    ],
)
def test_3_certificate_fields(
    root: pathlib.Path, change: Callable[[dict[str, Any]], None], want: str
) -> None:
    edit_bound_json(root, mm.CERT, "certificate_sha256", change)
    assert found(root) == [want]


@pytest.mark.parametrize(
    ("rel", "want"),
    [
        (
            "scripts/benchmark_stage2_units.py",
            "certificate: benchmark_stage2_units.py differs from the current file",
        ),
        (
            "scripts/benchmark_stage2_manifest_main.py",
            "certificate: benchmark_stage2_manifest_main.py differs"
            " from the current file",
        ),
        (
            f"{mm.CERT_TEST_DIR}/test_scorer.py",
            "certificate: tests/test_scorer.py differs from the current file",
        ),
        (
            mm.CERT_WITNESS_EXTRA[1],
            f"certificate: {mm.CERT_WITNESS_EXTRA[1]} differs from the current file",
        ),
    ],
    ids=["target", "manifest_main", "test", "witness"],
)
def test_3_certificate_binds_current_files(
    root: pathlib.Path, rel: str, want: str
) -> None:
    append(root, rel)
    assert found(root) == [want]


def test_3_a_new_test_file_is_outside_the_certificate(root: pathlib.Path) -> None:
    (root / mm.CERT_TEST_DIR / "test_new.py").write_text("", encoding="utf-8")
    assert found(root) == ["certificate: target_sha256 covers a different file set"]


# ------------------------------------------------------------ 4〜7. 入力


def test_4_gate_bytes_are_bound(root: pathlib.Path) -> None:
    other = json.dumps(GATE, indent=1).encode("utf-8")
    assert found(root, gate_bytes=other) == [
        "gate.json: the passed gate differs from the certified gate",
        "gate.json: sha256 differs from the record",
    ]


def test_4_passed_gate_must_be_the_certified_gate(root: pathlib.Path) -> None:
    """Codex r1 H1: root・証明書は gate A、記録と渡す gate は B (JSON の値は同じ)."""
    other = _gate_bytes(root) + b"\n"
    sha = hashlib.sha256(other).hexdigest()
    edit_rec(root, lambda r: r.__setitem__("gate_sha256", sha))
    assert found(root, gate_bytes=other) == [
        "gate.json: the passed gate differs from the certified gate"
    ]


def test_4_gate_must_be_the_certified_input(root: pathlib.Path) -> None:
    """記録と証明書の gate が root の gate と違う (root の gate を差し替えた)."""
    other = json.dumps(GATE, indent=1).encode("utf-8")
    (root / mm.GATE).write_bytes(other)
    sha = _sha(root / mm.GATE)
    edit_rec(root, lambda r: r.__setitem__("gate_sha256", sha))
    assert found(root, gate_bytes=other) == [
        "certificate: inputs_sha256 differs from the current gate.json"
    ]


def test_5_models_sha_is_bound(root: pathlib.Path) -> None:
    assert found(root, models_sha="0" * 64) == [
        "models.json: sha256 differs from manifest.json",
        "models.json: sha256 differs from the record",
    ]


def test_5_models_must_be_the_stage1_models(root: pathlib.Path) -> None:
    """Codex r1 H4: 記録と渡す sha が一致しても第 1 段の models.json と違えば拒む."""
    edit_rec(root, lambda r: r.__setitem__("models_json_sha256", "0" * 64))
    assert found(root, models_sha="0" * 64) == [
        "models.json: sha256 differs from manifest.json"
    ]


def test_6_fixture_bytes_are_bound(root: pathlib.Path) -> None:
    good = (root / mm.FIXTURE_MAIN).read_bytes()
    assert found(root, fixture_bytes=good) == []
    assert found(root, fixture_bytes=good + b" ") == [
        "fixture_diffs_main.json: sha256 differs from the record"
    ]
    append(root, mm.FIXTURE_MAIN)
    assert found(root) == ["fixture_diffs_main.json: sha256 differs from the record"]
    (root / mm.FIXTURE_MAIN).unlink()
    assert found(root) == ["fixture_diffs_main.json: missing"]


def test_7_sketch_must_be_the_recomputed_one(root: pathlib.Path) -> None:
    edit_rec(root, lambda r: r.__setitem__("sketch_sha256", "0" * 64))
    assert found(root) == ["sketch.json: sha256 differs from the recomputed sketch"]


# ------------------------------------------------------------ 8. battery_checks


@pytest.mark.parametrize(
    ("change", "want"),
    [
        (
            lambda bc: bc["O_time"].__setitem__("R", 7),
            "battery_checks: R differs from the GO batteries of the gate",
        ),
        (
            lambda bc: bc.__setitem__(
                "v2", {"R": 6, "checks": {k: [] for k in mm.check_keys("v2")}}
            ),
            "battery_checks: R differs from the GO batteries of the gate",
        ),
        (
            lambda bc: bc.pop("O_time"),
            "battery_checks: R differs from the GO batteries of the gate",
        ),
        (
            lambda bc: next(iter(bc["O_time"]["checks"].values())).append("x"),
            "battery_checks: O_time has a failed check",
        ),
        (
            lambda bc: bc["O_time"].__setitem__("checks", None),
            "battery_checks: O_time has no checks",
        ),
        (
            lambda bc: bc["O_time"].__setitem__("checks", {}),
            "battery_checks: O_time check names differ from the registration",
        ),
    ],
    ids=["R", "extra", "dropped", "failed", "none", "empty"],
)
def test_8_battery_checks(
    root: pathlib.Path, change: Callable[[dict[str, Any]], None], want: str
) -> None:
    edit_rec(root, lambda r: change(r["battery_checks"]))
    assert found(root) == [want]


def test_8_battery_checks_missing(root: pathlib.Path) -> None:
    edit_rec(root, lambda r: r.pop("battery_checks"))
    assert found(root) == ["battery_checks: missing or malformed"]


# ------------------------------------------------------------ driver (送信前)


def _gate_path(root: pathlib.Path) -> pathlib.Path:
    return root / mm.GATE


def test_driver_plan_for_requires_the_manifest(
    root: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert dr.plan_for(pl.STAGE_MAIN, _gate_path(root), root=root)

    def no_plan(*_a: object, **_k: object) -> tuple[pl.Segment, ...]:
        msg = "main_plan is called before the manifest check"
        raise AssertionError(msg)

    monkeypatch.setattr(pl, "main_plan", no_plan)
    append(root, "scripts/benchmark_stage2_units.py")
    with pytest.raises(dr.PreflightError, match=r"^manifest_main: certificate"):
        dr.plan_for(pl.STAGE_MAIN, _gate_path(root), root=root)
    (root / mm.MANIFEST_MAIN).unlink()
    with pytest.raises(dr.PreflightError, match=r"manifest_main\.json: missing"):
        dr.plan_for(pl.STAGE_MAIN, _gate_path(root), root=root)


def test_driver_recomputes_battery_checks(
    root: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = pl.battery_checks

    def failing(b: str, r: int | None = None) -> dict[str, list[str]]:
        out = real(b, r)
        out[next(iter(out))] = ["recomputed failure"]
        return out

    monkeypatch.setattr(pl, "battery_checks", failing)
    with pytest.raises(dr.PreflightError, match="battery_checks differ"):
        dr.plan_for(pl.STAGE_MAIN, _gate_path(root), root=root)


def test_driver_checks_the_gate_before_the_manifest(root: pathlib.Path) -> None:
    """壊れた gate は封印の照合の前に gate の読み手が拒む (理由が gate の契約になる)."""
    bad = dict(GATE, schema="x")
    _gate_path(root).write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(dr.PreflightError) as info:
        dr.plan_for(pl.STAGE_MAIN, _gate_path(root), root=root)
    assert "manifest_main" not in str(info.value)


# ------------------------------------------------------------ scorer (判定前)


def test_scorer_refuses_without_the_manifest(
    root: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_read(*_a: object, **_k: object) -> object:
        msg = "records are read before the manifest check"
        raise AssertionError(msg)

    monkeypatch.setattr(sc.rd, "read_run", no_read)
    monkeypatch.setattr(sc, "_REPO_ROOT", root)  # CLI の照合の root
    (root / mm.MANIFEST_MAIN).unlink()
    args = [
        root / "run",
        _gate_path(root),
        dr.MODELS_JSON,
        root / mm.FIXTURE_MAIN,
    ]
    with pytest.raises(mm.ManifestError, match="missing"):
        sc.compute_verdict(*args, root=root)
    out = tmp_path / "v.json"
    rc = sc.main(
        [
            "--run-dir",
            str(args[0]),
            "--out",
            str(out),
            "--gate",
            str(args[1]),
            "--models-json",
            str(args[2]),
            "--fixtures",
            str(args[3]),
        ]
    )
    assert rc == 2
    assert not out.exists()


def test_scorer_checks_the_fixture_it_read(
    root: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    other = tmp_path / "fixture_diffs_main.json"
    other.write_bytes((root / mm.FIXTURE_MAIN).read_bytes() + b" ")
    with pytest.raises(mm.ManifestError, match=r"fixture_diffs_main\.json: sha256"):
        sc.compute_verdict(
            root / "run", _gate_path(root), dr.MODELS_JSON, other, root=root
        )


# ------------------------------------------------------------ 書き手


@pytest.fixture
def frozen_write(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[pathlib.Path], list[str]]:
    """書き手を一時の root で呼ぶ (見取り図の再計算 約 10 分は現在の版を返す差し替え).

    第 1 段の manifest の sha は写した版から作り直したもの。
    """

    def recompute(root: pathlib.Path) -> tuple[list[str], str | None]:
        return [], _sha(root / man.SKETCH)

    monkeypatch.setattr(fz, "recompute_sketch", recompute)

    def write(root: pathlib.Path) -> list[str]:
        return fz.write(root, pilot_manifest_sha=_sha(root / man.MANIFEST))

    return write


def test_freeze_writes_once_and_verifies(
    root: pathlib.Path,
    frozen_write: Callable[[pathlib.Path], list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    want = (root / mm.MANIFEST_MAIN).read_bytes()
    (root / mm.MANIFEST_MAIN).unlink()
    assert fz.verify(root) == ["manifest_main.json: missing"]
    assert frozen_write(root) == []
    assert (root / mm.MANIFEST_MAIN).read_bytes() == want
    assert fz.verify(root) == []
    assert frozen_write(root) == [
        "manifest_main.json: already exists (refusing to overwrite)"
    ]
    monkeypatch.setattr(fz, "_REPO_ROOT", root)
    assert fz.main(["--verify"]) == 0


@pytest.mark.parametrize(
    ("change", "want"),
    [
        (
            lambda root: append(root, mm.FIXTURE_MAIN),
            "fixture_diffs_main.json: differs from the recomputation",
        ),
        (
            lambda root: (root / mm.FIXTURE_MAIN).unlink(),
            "fixture_diffs_main.json: missing",
        ),
        (
            lambda root: (root / man.PREREG).write_text(
                (root / man.PREREG)
                .read_text(encoding="utf-8")
                .replace(mm.STATUS_MAIN, man.STATUS_PILOT, 1),
                encoding="utf-8",
            ),
            "prereg: status is not FROZEN",
        ),
    ],
    ids=["fixture", "fixture_missing", "status"],
)
def test_freeze_refuses_to_write(
    root: pathlib.Path,
    change: Callable[[pathlib.Path], None],
    want: str,
    frozen_write: Callable[[pathlib.Path], list[str]],
) -> None:
    (root / mm.MANIFEST_MAIN).unlink()
    change(root)
    assert want in frozen_write(root)
    assert not (root / mm.MANIFEST_MAIN).exists()


def test_freeze_refuses_a_failed_battery_check(
    root: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    frozen_write: Callable[[pathlib.Path], list[str]],
) -> None:
    (root / mm.MANIFEST_MAIN).unlink()
    real = pl.battery_checks

    def failing(b: str, r: int | None = None) -> dict[str, list[str]]:
        out = real(b, r)
        out["main:r_range"] = ["x"]
        return out

    monkeypatch.setattr(pl, "battery_checks", failing)
    assert frozen_write(root) == ["battery_checks: O_time main:r_range: ['x']"]
    assert not (root / mm.MANIFEST_MAIN).exists()


def test_freeze_verify_recomputes_battery_checks(
    root: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = pl.battery_checks
    monkeypatch.setattr(
        pl, "battery_checks", lambda b, r=None: {**real(b, r), "extra": []}
    )
    assert fz.verify(root) == [
        "battery_checks: the recomputation differs from the record"
    ]


def test_freeze_refuses_a_stage1_manifest_other_than_the_pilot_commit(
    root: pathlib.Path,
    frozen_write: Callable[[pathlib.Path], list[str]],  # noqa: ARG001 — 再計算の差し替えだけ使う
) -> None:
    """Codex r1 H5: 作り直された第 1 段の manifest を採らない (実の sha は定数)."""
    (root / mm.MANIFEST_MAIN).unlink()
    assert "manifest.json: differs from the pilot freeze commit" in fz.write(root)
    assert not (root / mm.MANIFEST_MAIN).exists()


def test_freeze_records_the_recomputed_sketch(
    root: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    frozen_write: Callable[[pathlib.Path], list[str]],
) -> None:
    """Codex r1 H7: 記録の sketch の sha は再計算の出力 (違えば書かない)."""
    (root / mm.MANIFEST_MAIN).unlink()
    differs = "sketch: sketch.json differs from the recomputation"
    monkeypatch.setattr(fz, "recompute_sketch", lambda _root: ([differs], "0" * 64))
    assert frozen_write(root) == [differs]
    assert not (root / mm.MANIFEST_MAIN).exists()
    monkeypatch.setattr(fz, "recompute_sketch", lambda _root: ([], "0" * 64))
    assert frozen_write(root) == [
        "sketch.json: sha256 differs from the recomputed sketch"
    ]
    assert not (root / mm.MANIFEST_MAIN).exists()


def test_freeze_checks_external_modules_against_their_chain_seals(
    root: pathlib.Path, frozen_write: Callable[[pathlib.Path], list[str]]
) -> None:
    (root / mm.MANIFEST_MAIN).unlink()
    rel = "scripts/skill_lever_battery.py"
    append(root, rel)
    errs = frozen_write(root)
    assert errs
    head = f"external modules: {rel} differs from the seal "
    assert all(e.startswith(head) for e in errs)
    assert not (root / mm.MANIFEST_MAIN).exists()


# ------------------------------------------------------------ 8・9 の追加と壊れた記録


def test_8_check_names_are_registered(root: pathlib.Path) -> None:
    """Codex r1 H6: 本走の項目が欠けた記録を scorer の照合が拒む (再計算しない側)."""
    edit_rec(
        root,
        lambda r: r["battery_checks"]["O_time"].__setitem__(
            "checks", {"pilot:r_range": []}
        ),
    )
    assert found(root) == [
        "battery_checks: O_time check names differ from the registration"
    ]


def test_9_external_modules_are_bound(root: pathlib.Path) -> None:
    rel = "scripts/o_time_probe_scorer.py"
    assert rel in mm.external_modules(root)
    append(root, rel)
    assert found(root) == [f"external modules: {rel} differs from the record"]


def test_9_external_set_follows_the_import_closure(root: pathlib.Path) -> None:
    edit_rec(root, lambda r: r["external_sha256"].pop("scripts/stage_b_scorer.py"))
    assert found(root) == ["external modules: the set differs from the import closure"]


@pytest.mark.parametrize(
    ("body", "want"),
    [
        (b"{", "manifest_main.json: unreadable (JSONDecodeError)"),
        (b"[]", "manifest_main.json: not an object"),
    ],
    ids=["truncated", "not_object"],
)
def test_broken_manifest_is_a_violation(
    root: pathlib.Path, body: bytes, want: str
) -> None:
    (root / mm.MANIFEST_MAIN).write_bytes(body)
    assert found(root) == [want]
    with pytest.raises(mm.ManifestError, match=r"manifest_main\.json"):
        mm.require(root, gate_bytes=_gate_bytes(root), models_sha=MODELS_SHA)


def test_malformed_battery_entry_is_a_violation(root: pathlib.Path) -> None:
    edit_rec(root, lambda r: r["battery_checks"].__setitem__("O_time", None))
    assert found(root) == ["battery_checks: missing or malformed"]


def test_plan_for_uses_the_bytes_it_checked(root: pathlib.Path) -> None:
    """Codex r1 H4: 渡した models の bytes を照合し、path を読まない."""
    segs = dr.plan_for(
        pl.STAGE_MAIN,
        _gate_path(root),
        root / "no_such_models.json",
        root=root,
        models_bytes=dr.MODELS_JSON.read_bytes(),
    )
    assert segs


def test_none_is_never_a_match(root: pathlib.Path) -> None:
    """片方が無い (None・null) 比較は一致に数えない (消えた対象と null の証明書の値)."""
    rel = "scripts/benchmark_stage2_units.py"
    (root / rel).unlink()
    edit_bound_json(
        root,
        mm.CERT,
        "certificate_sha256",
        lambda c: c["target_sha256"].__setitem__(pathlib.PurePath(rel).name, None),
    )
    assert found(root) == [
        "certificate: benchmark_stage2_units.py differs from the current file"
    ]


def test_malformed_stage1_manifest_is_a_violation(root: pathlib.Path) -> None:
    """壊れた第 1 段の manifest は traceback でなく違反の文になる."""
    (root / man.MANIFEST).write_bytes(b"{")
    sha = _sha(root / man.MANIFEST)
    edit_rec(root, lambda r: r.__setitem__("manifest_pilot_sha256", sha))
    errs = found(root)
    assert len(errs) == 1
    assert errs[0].startswith("manifest_main: malformed input (JSONDecodeError")
    with pytest.raises(mm.ManifestError, match="malformed input"):
        mm.require(root, gate_bytes=_gate_bytes(root), models_sha=MODELS_SHA)


def test_freeze_refuses_an_external_module_without_a_seal(
    root: pathlib.Path, frozen_write: Callable[[pathlib.Path], list[str]]
) -> None:
    """閉包に新しく入り、どの chain の封印にも無い module は書かない."""
    (root / mm.MANIFEST_MAIN).unlink()
    (root / "scripts/zz_new.py").write_text("X = 1\n", encoding="utf-8")
    append(root, "scripts/benchmark_stage2_units.py")
    with (root / "scripts/benchmark_stage2_units.py").open("a", encoding="utf-8") as fh:
        fh.write("from scripts import zz_new  # noqa: F401\n")
    assert "scripts/zz_new.py" in mm.external_modules(root)
    errs = frozen_write(root)
    assert "external modules: scripts/zz_new.py is not in any chain seal" in errs
    assert not (root / mm.MANIFEST_MAIN).exists()


def test_driver_main_checks_and_sends_with_the_same_models_bytes(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex r1 H4: CLI は models.json を 1 回読み、照合と送信に同じ bytes を使う."""
    seen: dict[str, Any] = {}

    def plan(_stage: str, _gate: object, **k: Any) -> tuple[pl.Segment, ...]:
        seen["models_bytes"] = k.get("models_bytes")
        return ()

    async def run(*_a: object, **k: Any) -> dict[str, Any]:
        seen["reference"] = k.get("reference")
        return {"segments": {}}

    monkeypatch.setattr(dr, "plan_for", plan)
    monkeypatch.setattr(dr, "run_stage", run)
    assert dr.main(["--stage", pl.STAGE_PILOT, "--run-dir", str(tmp_path)]) == 0
    want = dr.MODELS_JSON.read_bytes()
    assert seen["models_bytes"] == want
    assert seen["reference"] == json.loads(want.decode("utf-8"))
    monkeypatch.setattr(dr, "MODELS_JSON", tmp_path / "missing.json")
    assert dr.main(["--stage", pl.STAGE_PILOT, "--run-dir", str(tmp_path)]) == (
        dr.EXIT_REFUSED
    )

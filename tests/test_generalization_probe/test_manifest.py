"""凍結 manifest (prereg §9・§10).

改変の検出、certification・見取り図・fixture 表・key 選定とコードの結び付き、
2 段の凍結条件 (第 1 段の封印の保存・pilot の再計算・driver の certification の契約)。
"""

from __future__ import annotations

import functools
import hashlib
import json
import tempfile
import types
from pathlib import Path
from typing import Any

import pytest
from scripts import generalization_probe_battery as bat
from scripts import generalization_probe_manifest as man
from scripts import generalization_probe_mutation_check as mut
from scripts import generalization_probe_scorer as sc
from scripts import generalization_probe_sim as sim

from tests.test_generalization_probe.test_pilot_gate import META, make_pilot

_ROOT = Path(__file__).resolve().parents[2]
PILOT_FROZEN = "# x\n\n- status: **PILOT-FROZEN** (2026-10-02)\n"
FROZEN = "# x\n\n- status: **FROZEN** (2026-10-02)\n"
DRAFT = "# x\n\n- status: DRAFT\n"
PASS = sc.VERDICT_PASS
ABSENT = sc.VERDICT_ABSENT
UNDER = sc.VERDICT_UNDERPOWERED
INVALID = sc.VERDICT_INVALID_BATTERY


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_manifest_detects_changed_and_missing_files(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "b.txt").write_text("y", encoding="utf-8")
    files = {"a.txt": _sha_text("x"), "b.txt": _sha_text("y")}
    assert man.manifest_violations(files, tmp_path) == []
    (tmp_path / "a.txt").write_text("x2", encoding="utf-8")
    (tmp_path / "b.txt").unlink()
    assert man.manifest_violations(files, tmp_path) == [
        "a.txt: sha256 differs from the frozen manifest",
        "b.txt: missing",
    ]


def test_frozen_files_cover_the_code_and_tests() -> None:
    listed = set(man.FROZEN_FILES) | set(man.MAIN_EVIDENCE)
    for path in (_ROOT / man._TESTS).glob("*.py"):
        assert f"{man._TESTS}/{path.name}" in listed
    for path in (_ROOT / "scripts").glob("generalization_probe_*.py"):
        assert f"scripts/{path.name}" in listed
    assert "scripts/stage_b_scorer.py" in listed
    assert man.MANIFEST in man.MAIN_EVIDENCE


def _cert() -> dict[str, Any]:
    return {
        "all_killed": True,
        "target_sha256": man.certified_sha256(_ROOT),
        "tests_sha256": man.tests_sha256(_ROOT),
        "harness_sha256": man.harness_sha256(_ROOT),
        "manifest_sha256": man.sha256(_ROOT / man.SELF),
        "meta_test": [
            {
                "label": c[0],
                "status": "FAILED_AS_EXPECTED",
                "expected_all_of": sorted(c[4]),
                "failed": [*sorted(c[4]), "test_other"],
            }
            for c in mut.META_CASES
        ],
        "mutants": [
            {
                "label": m.label,
                "status": "KILLED",
                "expected_any_of": sorted(m.expect),
                "failed": [sorted(m.expect)[0], "test_other"],
            }
            for m in mut.MUTANTS
        ],
    }


def test_certification_binding() -> None:
    assert man.certification_violations(_cert(), _ROOT) == []
    bad = _cert()
    bad["mutants"] = bad["mutants"][:-1]
    assert "certification: mutant rows differ from the registered mutants" in (
        man.certification_violations(bad, _ROOT)
    )
    stale = _cert()
    stale["target_sha256"] = {}
    assert "certification: recorded sha256 differs from current code" in (
        man.certification_violations(stale, _ROOT)
    )
    no_self = _cert()
    no_self["manifest_sha256"] = "0" * 64
    assert man.certification_violations(no_self, _ROOT) == [
        "certification: recorded manifest-check sha256 differs from current file"
    ]
    survived = _cert()
    survived["mutants"][0]["status"] = "SURVIVED"
    assert "certification: a mutant row is not KILLED" in man.certification_violations(
        survived, _ROOT
    )


def test_certification_requires_the_expected_failure() -> None:
    """KILLED の行は、期待した test のどれかで実際に落ちていること.

    Codex 3 回目 HIGH-1。
    """
    unrelated = _cert()
    unrelated["mutants"][0]["failed"] = ["test_unrelated"]
    assert man.certification_violations(unrelated, _ROOT) == [
        "certification: a mutant row did not fail for an expected reason"
    ]
    missing = _cert()
    del missing["mutants"][0]["failed"]
    assert man.certification_violations(missing, _ROOT) == [
        "certification: a mutant row did not fail for an expected reason"
    ]


META_MSG = (
    "certification: the meta-test differs from the registered cases"
    " or did not fail as expected"
)


def test_meta_test_must_match_the_registered_cases() -> None:
    """meta-test は登録ケースと一対一で、期待集合をすべて実際に落とした.

    Codex MEDIUM-8、3 回目 HIGH-1。
    """
    no_meta = _cert()
    no_meta["meta_test"] = []
    assert man.certification_violations(no_meta, _ROOT) == [META_MSG]
    renamed = _cert()
    renamed["meta_test"][0]["label"] = "other"
    assert man.certification_violations(renamed, _ROOT) == [META_MSG]
    not_failed = _cert()
    not_failed["meta_test"][0]["status"] = "NOT_AS_EXPECTED"
    assert man.certification_violations(not_failed, _ROOT) == [META_MSG]
    duplicated = _cert()
    duplicated["meta_test"] = [*duplicated["meta_test"], duplicated["meta_test"][0]]
    assert man.certification_violations(duplicated, _ROOT) == [META_MSG]
    short = _cert()
    short["meta_test"][0]["failed"] = short["meta_test"][0]["expected_all_of"][1:]
    assert man.certification_violations(short, _ROOT) == [META_MSG]
    other_expect = _cert()
    other_expect["meta_test"][0]["expected_all_of"] = ["test_other"]
    assert man.certification_violations(other_expect, _ROOT) == [META_MSG]


# ------------------------------------------------------------- 見取り図


def _fake_simulate(
    form: str, target: float, r_count: int, nu: object, n_sims: int, seed: int
) -> dict[str, float]:
    """模擬の代わり: 目標 E[C] だけで決まる、格子の上の率."""
    del form, r_count, nu, n_sims, seed
    if target == 0.0:
        pas, absent = 0.0, 0.9
    elif target >= 0.5:
        pas, absent = 0.9, 0.0
    else:
        pas, absent = 0.0, 0.0
    return {
        PASS: pas,
        ABSENT: absent,
        UNDER: round(1.0 - pas - absent, 10),
        INVALID: 0.0,
        "realized_C": target,
    }


@functools.cache
def _sketch_json() -> str:
    """見取り図の fixture.

    検査器の点集合からでなく、本番の ``sim.main`` を模擬だけ差し替えて走らせて作る。
    """
    with tempfile.TemporaryDirectory() as tmp, pytest.MonkeyPatch.context() as mp:
        mp.setattr(sim, "simulate", _fake_simulate)
        mp.setattr(sim, "pure_extremal_size", lambda *_a, **_k: 0.0)
        mp.setattr("builtins.print", lambda *_a, **_k: None)
        out = Path(tmp) / "sketch.json"
        assert sim.main(["--out", str(out)]) == 0
        return out.read_text(encoding="utf-8")


def _sketch() -> dict[str, Any]:
    sketch: dict[str, Any] = json.loads(_sketch_json())
    return sketch


def test_sketch_recheck_accepts_a_consistent_sketch() -> None:
    sk = _sketch()
    assert sk["selection"] == {"selected_R": sim.R_MAIN, "door_close": False}
    assert sk["most_favorable_reaches"] is True
    assert man.sketch_violations(sk, _ROOT) == []


def test_sketch_recheck_detects_missing_points() -> None:
    sk = _sketch()
    sk["per_R"][2]["rows"] = sk["per_R"][2]["rows"][:-1]
    assert "sketch R18: rows differ from the points the rule requires" in (
        man.sketch_violations(sk, _ROOT)
    )
    empty = _sketch()
    empty["per_R"][2]["rows"] = []
    assert man.sketch_violations(empty, _ROOT) != []


def test_sketch_recheck_recomputes_flags_and_values() -> None:
    sk = _sketch()
    sk["per_R"][2]["size_ok"] = False
    out = man.sketch_violations(sk, _ROOT)
    assert "sketch R18: size_ok differs from a recomputation from the rows" in out
    bad_value = _sketch()
    bad_value["per_R"][0]["rows"][0]["value"] = 0.1
    assert "sketch R6: a row value differs from its per-seed results" in (
        man.sketch_violations(bad_value, _ROOT)
    )
    over = _sketch()
    over_rates = {PASS: 0.07, ABSENT: 0.07, UNDER: 0.86, INVALID: 0.0}
    for row in over["per_R"][2]["rows"]:
        if row["kind"].startswith("size"):
            row["per_seed"] = [{**p, **over_rates} for p in row["per_seed"]]
            row["value"] = 0.07
    over["per_R"][2]["worst_size"] = 0.07
    assert man.sketch_violations(over, _ROOT) == [
        "sketch R18: size_ok differs from a recomputation from the rows"
    ]
    worst = _sketch()
    worst["per_R"][2]["worst_size"] = 0.5
    assert man.sketch_violations(worst, _ROOT) == [
        "sketch R18: worst_size differs from a recomputation"
    ]


RATES_MSG = (
    "sketch R18: a row's per-seed results are not one valid set of rates per seed"
)


def _seed0(update: dict[str, float]) -> list[str]:
    sk = _sketch()
    row = sk["per_R"][2]["rows"][0]
    row["per_seed"][0] = {**row["per_seed"][0], **update}
    return man.sketch_violations(sk, _ROOT)


def test_sketch_recheck_rejects_invalid_rates_and_row_r() -> None:
    """per_seed の率の妥当性と、行の R を照合する (Codex 3 回目 MEDIUM-3)."""
    # 範囲だけが破れる (合計 1・格子の上)
    assert RATES_MSG in _seed0({PASS: 1.5, ABSENT: 0.0, UNDER: -0.5, INVALID: 0.0})
    # 合計だけが破れる
    assert RATES_MSG in _seed0({PASS: 0.9, ABSENT: 0.0, UNDER: 0.9, INVALID: 0.0})
    # 格子だけが破れる (2,000 回の率にならない)
    assert RATES_MSG in _seed0({PASS: 0.90005, ABSENT: 0.0, UNDER: 0.09995})
    assert RATES_MSG in _seed0({"realized_C": float("nan")})
    one_seed = _sketch()
    row = one_seed["per_R"][2]["rows"][0]
    row["per_seed"] = row["per_seed"][:1]
    assert RATES_MSG in man.sketch_violations(one_seed, _ROOT)
    relabeled = _sketch()
    relabeled["per_R"][2]["rows"][0]["R"] = 6
    assert man.sketch_violations(relabeled, _ROOT) == [
        "sketch R18: a row's R differs from its block"
    ]


def test_sketch_recheck_rejects_booleans() -> None:
    """JSON の真偽値を数値として受け入れない (Codex 4 回目 LOW-2)."""
    # 率の 0.0 を false に
    assert RATES_MSG in _seed0({INVALID: False})
    # 攪乱点の ⊥ 0.0 を false に
    point = _sketch()
    row = point["per_R"][2]["rows"][0]
    assert row["bot"] == 0.0
    row["bot"] = False
    assert man.sketch_violations(point, _ROOT) == [
        "sketch R18: rows are missing or malformed"
    ]
    # 凍結した設定の 1.0 を true に
    params = _sketch()
    assert params["params"]["lambda_fractions"][-1] == 1.0
    params["params"]["lambda_fractions"][-1] = True
    assert man.sketch_violations(params, _ROOT) == [
        "sketch: params differ from the frozen settings"
    ]


def test_sketch_recheck_checks_the_params() -> None:
    for key, value in (("n_sim_power", 1), ("grid", []), ("tau", 0.25)):
        sk = _sketch()
        sk["params"][key] = value
        assert man.sketch_violations(sk, _ROOT) == [
            "sketch: params differ from the frozen settings"
        ]


def _favourable_2tau(sweeps: list[dict[str, Any]]) -> int:
    hits = [
        i
        for i, x in enumerate(sweeps)
        if x["R"] == sim.R_CANDIDATES[0]
        and x["form"] == "homog_sd005"
        and (x["base"], x["bot"], x["coupling"])
        == (sim.FAVORABLE.base, sim.FAVORABLE.bot, sim.FAVORABLE.coupling)
        and x["target_C"] == sc.DELTA_PLANT
    ]
    assert len(hits) == 1
    return hits[0]


def test_sketch_recheck_checks_the_sweeps() -> None:
    """sweep の完全性・pass と per_seed の整合・到達上限・境目.

    Codex 3 回目 MEDIUM-3。
    """
    sk = _sketch()
    i = _favourable_2tau(sk["sweeps"])
    zero = {PASS: 0.0, ABSENT: 0.0, UNDER: 1.0, INVALID: 0.0}
    forged = {
        **sk["sweeps"][i],
        "pass": 1.0,
        "per_seed": [{**p, **zero} for p in sk["sweeps"][i]["per_seed"]],
    }
    # Codex 3 回目の例: 最有利の 2τ 点の 1 行だけにし、
    # per_seed の PASS は 0、集計の pass は 1
    truncated = {**sk, "sweeps": [forged]}
    out = man.sketch_violations(truncated, _ROOT)
    assert "sketch: sweep rows differ from the points the rule requires" in out
    assert "sketch: a sweep row's pass differs from its per-seed results" in out
    inconsistent = _sketch()
    inconsistent["sweeps"][i] = forged
    assert man.sketch_violations(inconsistent, _ROOT) == [
        "sketch: a sweep row's pass differs from its per-seed results"
    ]
    duplicated = _sketch()
    duplicated["sweeps"].append(duplicated["sweeps"][0])
    assert man.sketch_violations(duplicated, _ROOT) == [
        "sketch: sweep rows differ from the points the rule requires"
    ]
    reach = _sketch()
    reach["sweeps"][0]["reachable"] = 0.5
    assert man.sketch_violations(reach, _ROOT) == [
        "sketch: a sweep row's reachable differs from a recomputation"
    ]
    rates = _sketch()
    rates["sweeps"][0]["per_seed"][0][PASS] = 1.5
    assert man.sketch_violations(rates, _ROOT) == [
        "sketch: a sweep row's per-seed results are not valid rates"
    ]
    bounds = _sketch()
    bounds["boundaries"]["R18"]["homog_sd005"]["favorable"] = 0.3
    assert man.sketch_violations(bounds, _ROOT) == [
        "sketch: boundaries differ from a recomputation from the sweeps"
    ]


def test_sketch_recheck_recomputes_selection_and_reach() -> None:
    sk = _sketch()
    sk["selection"] = {"selected_R": 6, "door_close": False}
    assert "sketch: the selection differs from a recomputation of the rule" in (
        man.sketch_violations(sk, _ROOT)
    )
    unreached = _sketch()
    unreached["sweeps"] = []
    assert (
        "sketch: most_favorable_reaches differs from a recomputation from the sweeps"
        in man.sketch_violations(unreached, _ROOT)
    )
    flipped = _sketch()
    flipped["most_favorable_reaches"] = False
    assert man.sketch_violations(flipped, _ROOT) == [
        "sketch: most_favorable_reaches differs from a recomputation from the sweeps"
    ]


def test_freeze_violations_stage_pilot() -> None:
    sk = _sketch()
    assert man.freeze_violations(sk, PILOT_FROZEN) == []
    assert man.freeze_violations(sk, FROZEN) == []
    assert man.freeze_violations(sk, DRAFT) == [man.DRAFT]
    closed = {**sk, "selection": {"selected_R": None, "door_close": True}}
    assert man.freeze_violations(closed, PILOT_FROZEN) == [man.DOOR_CLOSE]
    other = {**sk, "selection": {"selected_R": 12, "door_close": False}}
    assert man.freeze_violations(other, PILOT_FROZEN) == [man.DOOR_CLOSE]
    unreached = {**sk, "most_favorable_reaches": False}
    assert man.freeze_violations(unreached, PILOT_FROZEN) == [man.NOT_REACHED]


# ------------------------------------------------------------- 第 2 段


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def test_stage1_seal_allows_only_the_status_line(tmp_path: Path) -> None:
    """第 2 段: 第 1 段の封印は prereg の status 行以外を変えさせない.

    Codex 2 回目 HIGH-2。
    """
    for rel in man.FROZEN_FILES:
        _write(tmp_path, rel, f"content of {rel}\n")
    _write(tmp_path, man.PREREG, "# p\n\n- status: **PILOT-FROZEN** (a)\n\nbody\n")
    _write(tmp_path, man.MANIFEST, json.dumps(man.build_manifest(tmp_path)))
    assert man.stage1_seal_violations(tmp_path) == []
    _write(tmp_path, man.PREREG, "# p\n\n- status: **FROZEN** (b)\n\nbody\n")
    assert man.stage1_seal_violations(tmp_path) == []
    _write(tmp_path, man.PREREG, "# p\n\n- status: **FROZEN** (b)\n\nbody changed\n")
    assert man.stage1_seal_violations(tmp_path) == [
        "stage 1: prereg changed beyond its status line since the pilot seal"
    ]
    _write(tmp_path, man.PREREG, "# p\n\n- status: **FROZEN** (b)\n\nbody\n")
    _write(tmp_path, man.SKETCH, "regenerated\n")
    assert man.stage1_seal_violations(tmp_path) == [
        f"stage 1: {man.SKETCH}: sha256 differs from the frozen manifest"
    ]
    (tmp_path / man.MANIFEST).unlink()
    assert man.stage1_seal_violations(tmp_path) == [
        "stage 1: manifest.json is missing or unreadable"
    ]


def _driver_root(tmp_path: Path) -> Path:
    for rel in (man.DRIVER, man.DRIVER_TEST, man.DRIVER_HARNESS):
        _write(tmp_path, rel, f"{rel}\n")
    return tmp_path


def _driver_cert(root: Path) -> dict[str, Any]:
    return {
        "all_killed": True,
        "mutants": [
            {
                "label": "d1",
                "status": "KILLED",
                "expected_any_of": ["test_x"],
                "failed": ["test_x", "test_y"],
            }
        ],
        "meta_test": [
            {
                "label": "m",
                "status": "FAILED_AS_EXPECTED",
                "expected_all_of": ["test_m"],
                "failed": ["test_m"],
            }
        ],
        "target_sha256": {man.DRIVER: man.sha256(root / man.DRIVER)},
        "tests_sha256": {man.DRIVER_TEST: man.sha256(root / man.DRIVER_TEST)},
        "harness_sha256": {man.DRIVER_HARNESS: man.sha256(root / man.DRIVER_HARNESS)},
    }


def _fake_harness(monkeypatch: pytest.MonkeyPatch, **attrs: object) -> None:
    fake = types.SimpleNamespace(**attrs)
    real = man.importlib.import_module

    def loader(name: str) -> object:
        return fake if name == man.DRIVER_HARNESS_MODULE else real(name)

    monkeypatch.setattr(man.importlib, "import_module", loader)


@pytest.fixture
def fake_driver_harness(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_harness(
        monkeypatch,
        MUTANTS=[types.SimpleNamespace(label="d1", expect=frozenset({"test_x"}))],
        META_CASES=(("m", "driver.py", "old", "new", ("test_m",)),),
    )


DRIVER_META_MSG = (
    "driver: the meta-test differs from the registered driver cases"
    " or did not fail as expected"
)


def test_driver_certification_contract(
    tmp_path: Path, fake_driver_harness: None
) -> None:
    """driver の certification の契約.

    各行 KILLED・登録変異・meta-test・sha256 (Codex 2 回目 HIGH-3)。
    """
    del fake_driver_harness
    root = _driver_root(tmp_path)
    assert man.driver_certification_violations(_driver_cert(root), root) == []
    survived = _driver_cert(root)
    survived["mutants"][0]["status"] = "SURVIVED"
    assert man.driver_certification_violations(survived, root) == [
        "driver: a mutant row is not KILLED"
    ]
    not_list = {**_driver_cert(root), "mutants": "not-a-list"}
    assert man.driver_certification_violations(not_list, root) == [
        "driver: certification has no mutant rows"
    ]
    other = _driver_cert(root)
    other["mutants"][0]["label"] = "d2"
    assert man.driver_certification_violations(other, root) == [
        "driver: mutant rows differ from the registered driver mutants"
    ]
    no_meta = {**_driver_cert(root), "meta_test": []}
    assert man.driver_certification_violations(no_meta, root) == [DRIVER_META_MSG]
    _write(root, man.DRIVER, "edited\n")
    assert "driver: recorded target_sha256 differs from the current file" in (
        man.driver_certification_violations(
            _driver_cert(tmp_path) | {"target_sha256": {}}, root
        )
    )


def test_driver_certification_requires_the_expected_failures(
    tmp_path: Path, fake_driver_harness: None
) -> None:
    """driver の変異は期待した test で落ち、meta-test は登録ケースと一対一.

    Codex 3 回目 HIGH-1。
    """
    del fake_driver_harness
    root = _driver_root(tmp_path)
    # Codex 3 回目の例: 期待と無関係な test だけが落ちた KILLED
    unrelated = _driver_cert(root)
    unrelated["mutants"][0]["failed"] = ["test_unrelated"]
    assert man.driver_certification_violations(unrelated, root) == [
        "driver: a mutant row did not fail for an expected reason"
    ]
    for meta in (
        [{"status": "FAILED_AS_EXPECTED"}],
        [_driver_cert(root)["meta_test"][0]] * 2,
        [{**_driver_cert(root)["meta_test"][0], "failed": ["test_other"]}],
        [{**_driver_cert(root)["meta_test"][0], "expected_all_of": ["test_other"]}],
        [{**_driver_cert(root)["meta_test"][0], "label": "other"}],
    ):
        cert = {**_driver_cert(root), "meta_test": meta}
        assert man.driver_certification_violations(cert, root) == [DRIVER_META_MSG]


def test_registries_must_be_well_formed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """登録 (MUTANTS・META_CASES) の形を、照合の表を作る前に検証する.

    Codex 4 回目 HIGH-1。
    """
    ns = types.SimpleNamespace
    case = ("m", "driver.py", "old", "new", ("test_m",))
    assert man.meta_want((case,)) == {"m": ["test_m"]}
    for bad_cases in (
        (),
        (("m", "f", "o", "n", ()),),  # 期待集合が空
        (("m", "f", "o", "n", ("test_a",)), ("m", "f", "o", "n", ("test_b",))),
        ((1, "f", "o", "n", ("test_a",)),),  # label が文字列でない
        (("m", "f", "o", "n", (1,)),),  # test 名が文字列でない
        (("m",),),
        None,
    ):
        assert man.meta_want(bad_cases) is None
    good = ns(label="d1", expect=frozenset({"test_x"}))
    assert man.mutant_want([good]) == {"d1": ["test_x"]}
    for bad_mutants in (
        [],
        [ns(label="d1", expect=frozenset())],
        [good, good],
        [ns(label="d1")],
        None,
    ):
        assert man.mutant_want(bad_mutants) is None
    root = _driver_root(tmp_path)
    # Codex 4 回目の反例: 期待集合が空の登録と、失敗 0 の meta-test
    _fake_harness(monkeypatch, MUTANTS=[good], META_CASES=(("m", "d", "o", "n", ()),))
    empty = _driver_cert(root)
    empty["meta_test"] = [
        {
            "label": "m",
            "status": "FAILED_AS_EXPECTED",
            "expected_all_of": [],
            "failed": [],
        }
    ]
    assert man.driver_certification_violations(empty, root) == [DRIVER_META_MSG]
    # Codex 4 回目の反例: label の重複した登録と、後のケースだけを実行した証明書
    _fake_harness(
        monkeypatch,
        MUTANTS=[good],
        META_CASES=(
            ("m", "d", "o", "n", ("test_a",)),
            ("m", "d", "o", "n", ("test_b",)),
        ),
    )
    later = _driver_cert(root)
    later["meta_test"] = [
        {
            "label": "m",
            "status": "FAILED_AS_EXPECTED",
            "expected_all_of": ["test_b"],
            "failed": ["test_b"],
        }
    ]
    assert man.driver_certification_violations(later, root) == [DRIVER_META_MSG]
    # 登録変異の label の重複
    _fake_harness(monkeypatch, MUTANTS=[good, good], META_CASES=(case,))
    assert man.driver_certification_violations(_driver_cert(root), root) == [
        "driver: mutant rows differ from the registered driver mutants"
    ]


def test_driver_certification_requires_the_harness_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _driver_root(tmp_path)
    out = man.driver_certification_violations(_driver_cert(root), root)
    assert "driver: mutant rows differ from the registered driver mutants" in out
    assert DRIVER_META_MSG in out
    _fake_harness(
        monkeypatch,
        MUTANTS=[types.SimpleNamespace(label="d1", expect=frozenset({"test_x"}))],
    )
    assert DRIVER_META_MSG in man.driver_certification_violations(
        _driver_cert(root), root
    )


def _pilot_root(tmp_path: Path, selected_r: int) -> dict[str, Any]:
    samples = make_pilot()
    _write(
        tmp_path,
        man.PILOT_RECORDS,
        "\n".join(json.dumps(vars(s)) for s in samples) + "\n",
    )
    _write(tmp_path, man.PILOT_META, json.dumps(META))
    cert = {
        "mutants": [{"label": "m", "status": "KILLED"}],
        "target_sha256": {
            k: hashlib.sha256(v.read_bytes()).hexdigest()
            for k, v in sc.certified_targets().items()
        },
    }
    _write(tmp_path, man.CERT, json.dumps(cert))
    _write(tmp_path, man.SKETCH, "{}")
    _write(tmp_path, man.DRIVER, "driver\n")
    _write(
        tmp_path,
        man.PILOT_PROVENANCE,
        json.dumps(
            {
                "driver_sha256": _sha_text("driver\n"),
                "records_sha256": man.sha256(tmp_path / man.PILOT_RECORDS),
                "meta_sha256": man.sha256(tmp_path / man.PILOT_META),
            }
        ),
    )
    fresh = man.pg.decide_pilot(samples, META, certified=True, selected_r=selected_r)
    fresh["inputs_sha256"] = {
        name: man.sha256(tmp_path / rel)
        for name, rel in (
            ("records", man.PILOT_RECORDS),
            ("meta", man.PILOT_META),
            ("cert", man.CERT),
            ("sketch", man.SKETCH),
        )
    }
    return fresh


def test_pilot_gate_is_recomputed_from_its_inputs(tmp_path: Path) -> None:
    """第 2 段: pilot の機械判定を入力から再計算して照合する (Codex 2 回目 MEDIUM-5)."""
    gate = _pilot_root(tmp_path, 6)
    prov = json.loads((tmp_path / man.PILOT_PROVENANCE).read_text(encoding="utf-8"))
    assert gate["decision"] == "GO"
    assert man.pilot_gate_violations(gate, prov, 6, tmp_path) == []
    forged = {**gate, "masked_max_bottom": 0.15}
    assert (
        "pilot gate: masked_max_bottom differs from a recomputation from the inputs"
        in (man.pilot_gate_violations(forged, prov, 6, tmp_path))
    )
    assert (
        "pilot gate: R differs from the sketch selection"
        in man.pilot_gate_violations(gate, prov, 18, tmp_path)
    )
    _write(tmp_path, man.PILOT_META, json.dumps({**META, "extra": 1}))
    assert man.pilot_gate_violations(gate, prov, 6, tmp_path) != []


def test_pilot_provenance_binds_driver_records_and_meta(tmp_path: Path) -> None:
    """provenance は driver と、それが書いた records・meta を同時に結ぶ.

    Codex 3 回目 HIGH-2。
    """
    gate = _pilot_root(tmp_path, 6)
    prov = json.loads((tmp_path / man.PILOT_PROVENANCE).read_text(encoding="utf-8"))
    assert man.pilot_gate_violations(gate, prov, 6, tmp_path) == []
    for key, rel in (
        ("driver_sha256", man.DRIVER),
        ("records_sha256", man.PILOT_RECORDS),
        ("meta_sha256", man.PILOT_META),
    ):
        want = [f"pilot: provenance {key} does not bind the current {rel}"]
        # 別の実行の provenance (その項目が今の対象と違う)
        mixed = {**prov, key: "0" * 64}
        assert man.pilot_gate_violations(gate, mixed, 6, tmp_path) == want
        missing = {k: v for k, v in prov.items() if k != key}
        assert man.pilot_gate_violations(gate, missing, 6, tmp_path) == want


def test_key_violations() -> None:
    want = {c: list(v) for c, v in bat.PROBE_KEYS.items()}
    assert man.key_violations({"assignment": want}) == []
    other = {**want, "bird": ["vulture", *want["bird"][1:]]}
    assert man.key_violations({"assignment": other}) != []


def test_committed_artifacts_are_bound() -> None:
    """commit した成果物が現在のコードに結び付いている.

    certification・見取り図・fixture 表・key 選定と、コード・test・harness。
    """
    assert man.binding_violations(_ROOT) == []
    sketch = json.loads((_ROOT / man.SKETCH).read_text(encoding="utf-8"))
    assert sketch["selection"] == {"selected_R": sim.R_MAIN, "door_close": False}


def test_freeze_violations_stage_main_checks_the_seal(tmp_path: Path) -> None:
    """第 2 段の凍結条件は、第 1 段の封印・pilot・driver の証拠を照合する."""
    out = man.freeze_violations(_sketch(), FROZEN, "main", tmp_path)
    assert "stage 1: manifest.json is missing or unreadable" in out
    assert "pilot gate: missing" in out
    assert "driver: certification missing" in out
    assert man.NOT_MAIN_FROZEN in man.freeze_violations(
        _sketch(), PILOT_FROZEN, "main", tmp_path
    )

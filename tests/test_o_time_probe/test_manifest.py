"""凍結 manifest (prereg §9・§10).

改変の検出、certification・見取り図・fixture 表とコードの結び付き、
2 段の凍結条件 (第 1 段の封印の保存・pilot の再計算・driver の certification の契約)。
"""

from __future__ import annotations

import functools
import hashlib
import json
import math
import tempfile
import types
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from scripts import o_time_probe_manifest as man
from scripts import o_time_probe_mutation_check as mut
from scripts import o_time_probe_scorer as sc
from scripts import o_time_probe_sim as sim

from tests.test_o_time_probe.test_pilot_gate import META, make_pilot

_ROOT = Path(__file__).resolve().parents[2]
PILOT_FROZEN = "# x\n\n- status: **PILOT-FROZEN** (2026-10-08)\n"
FROZEN = "# x\n\n- status: **FROZEN** (2026-10-08)\n"
DRAFT = "# x\n\n- status: DRAFT\n"
PASS = sc.VERDICT_PASS
ABSENT = sc.VERDICT_ABSENT
UNDER = sc.VERDICT_UNDERPOWERED
INVALID = sc.VERDICT_INVALID_BATTERY
LAST = 2  # per_R の最後 (R = 288)


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
    for path in (_ROOT / "scripts").glob("o_time_probe_*.py"):
        assert f"scripts/{path.name}" in listed
    assert "scripts/stage_b_scorer.py" in listed
    assert man.MANIFEST in man.MAIN_EVIDENCE
    assert man.PREREG in man.FROZEN_FILES


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
                "expected_all_of": sorted(c[-1]),
                "failed": [*sorted(c[-1]), "test_other"],
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
    not_all = {**_cert(), "all_killed": False}
    assert man.certification_violations(not_all, _ROOT) == [
        "certification: not all mutants KILLED"
    ]
    tests = {**_cert(), "tests_sha256": {}}
    assert man.certification_violations(tests, _ROOT) == [
        "certification: recorded test sha256 differs from current tests"
    ]
    harness = {**_cert(), "harness_sha256": "0" * 64}
    assert man.certification_violations(harness, _ROOT) == [
        "certification: recorded harness sha256 differs from current harness"
    ]


def test_certification_requires_the_expected_failure() -> None:
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
    elif target == 0.35:
        pas, absent = 0.85, 0.0
    elif target == 0.25:
        pas, absent = 0.0, 0.85
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
    assert sk["selection"] == {"selected_R": 288, "door_close": False}
    assert sk["most_favorable_reaches"] is True
    assert man.sketch_violations(sk, _ROOT) == []


def test_sketch_written_with_lf() -> None:
    assert "\r\n" not in _sketch_json()


def test_sketch_recheck_detects_missing_points() -> None:
    sk = _sketch()
    sk["per_R"][LAST]["rows"] = sk["per_R"][LAST]["rows"][:-1]
    assert "sketch R288: rows differ from the points the rule requires" in (
        man.sketch_violations(sk, _ROOT)
    )
    empty = _sketch()
    empty["per_R"][LAST]["rows"] = []
    assert man.sketch_violations(empty, _ROOT) != []


def test_expected_points_match_the_sim_plan() -> None:
    """manifest が独立に列挙した点と、sim の計画の点が一致する.

    一方だけを変えると落ちる。
    """
    plan = {
        (kind, form, target, nu.base, nu.bot, nu.coupling)
        for kind, form, target, nu, _ in sim.plan_r(24)
    }
    assert plan == man.expected_points()
    assert len(sim.plan_r(24)) == len(plan)


def test_sketch_recheck_recomputes_flags_and_values() -> None:
    sk = _sketch()
    sk["per_R"][LAST]["size_ok"] = False
    out = man.sketch_violations(sk, _ROOT)
    assert "sketch R288: size_ok differs from a recomputation from the rows" in out
    bad_value = _sketch()
    bad_value["per_R"][0]["rows"][0]["value"] = 0.1
    assert "sketch R96: a row value differs from its per-seed results" in (
        man.sketch_violations(bad_value, _ROOT)
    )
    worst = _sketch()
    worst["per_R"][LAST]["worst_size"] = 0.5
    assert man.sketch_violations(worst, _ROOT) == [
        "sketch R288: worst_size differs from a recomputation"
    ]
    counts = _sketch()
    counts["per_R"][LAST]["calls"] = 1
    assert man.sketch_violations(counts, _ROOT) == [
        "sketch R288: the unit and call counts differ from the design"
    ]
    thr = _sketch()
    thr["per_R"][LAST]["size_count_threshold"] += 1
    assert man.sketch_violations(thr, _ROOT) == [
        "sketch R288: the size threshold differs from a recomputation"
    ]


def test_sketch_recheck_size_threshold_boundary() -> None:
    """size の行が閾値ちょうどなら合格、1 つ超えれば不合格."""
    sk = _sketch()
    res = sk["per_R"][LAST]
    x = res["size_count_threshold"]
    for value, ok in ((x, True), (x + 1, False)):
        s2 = json.loads(json.dumps(sk))
        row = next(r for r in s2["per_R"][LAST]["rows"] if r["kind"] == "size_pass")
        rate = value / sim.N_SIM_SIZE
        row["per_seed"][0] = {
            **row["per_seed"][0],
            PASS: rate,
            UNDER: round(1.0 - rate, 10),
        }
        row["value"] = rate
        s2["per_R"][LAST]["worst_size"] = rate
        out = man.sketch_violations(s2, _ROOT)
        if ok:
            assert out == []
        else:
            assert (
                "sketch R288: size_ok differs from a recomputation from the rows" in out
            )


def test_sketch_recheck_band() -> None:
    """決着しない確率の帯 (条件 4) を per_seed から再計算する."""
    sk = _sketch()
    row = next(r for r in sk["per_R"][LAST]["rows"] if r["kind"] == "band")
    row["per_seed"] = [
        {**p, PASS: 0.0, ABSENT: 0.0, UNDER: 1.0} for p in row["per_seed"]
    ]
    row["value"] = 1.0
    out = man.sketch_violations(sk, _ROOT)
    assert "sketch R288: band_ok differs from a recomputation from the rows" in out
    sk["per_R"][LAST]["band_ok"] = False
    out2 = man.sketch_violations(sk, _ROOT)
    assert "sketch: the selection differs from a recomputation of the rule" in out2


RATES_MSG = (
    "sketch R288: a row's per-seed results are not one valid set of rates per seed"
)


def _seed0(update: dict[str, float]) -> list[str]:
    sk = _sketch()
    row = sk["per_R"][LAST]["rows"][0]
    row["per_seed"][0] = {**row["per_seed"][0], **update}
    return man.sketch_violations(sk, _ROOT)


def test_sketch_recheck_rejects_invalid_rates_and_row_r() -> None:
    assert RATES_MSG in _seed0({PASS: 1.5, ABSENT: 0.0, UNDER: -0.5, INVALID: 0.0})
    assert RATES_MSG in _seed0({PASS: 0.9, ABSENT: 0.0, UNDER: 0.9, INVALID: 0.0})
    assert RATES_MSG in _seed0({PASS: 0.90005, ABSENT: 0.0, UNDER: 0.09995})
    assert RATES_MSG in _seed0({"realized_C": float("nan")})
    one_seed = _sketch()
    row = one_seed["per_R"][LAST]["rows"][0]
    row["per_seed"] = row["per_seed"][:1]
    assert RATES_MSG in man.sketch_violations(one_seed, _ROOT)
    relabeled = _sketch()
    relabeled["per_R"][LAST]["rows"][0]["R"] = 96
    assert man.sketch_violations(relabeled, _ROOT) == [
        "sketch R288: a row's R differs from its block"
    ]


def test_sketch_recheck_rejects_booleans() -> None:
    assert RATES_MSG in _seed0({INVALID: False})
    point = _sketch()
    row = point["per_R"][LAST]["rows"][0]
    assert row["bot"] == 0.0
    row["bot"] = False
    assert man.sketch_violations(point, _ROOT) == [
        "sketch R288: rows are missing or malformed"
    ]
    params = _sketch()
    assert params["params"]["lambda_fractions"][-1] == 1.0
    params["params"]["lambda_fractions"][-1] = True
    assert man.sketch_violations(params, _ROOT) == [
        "sketch: params differ from the frozen settings"
    ]
    r_bool = _sketch()
    r_bool["per_R"][0]["R"] = True
    assert "sketch: per_R does not cover the R candidates" in man.sketch_violations(
        r_bool, _ROOT
    )


def test_sketch_recheck_checks_the_params() -> None:
    for key, value in (
        ("n_sim_power", 1),
        ("grid", []),
        ("tau", 0.25),
        ("undecided_max", 0.3),
        ("band_delta", 0.1),
        ("R_candidates", [96, 192]),
    ):
        sk = _sketch()
        sk["params"][key] = value
        assert man.sketch_violations(sk, _ROOT) == [
            "sketch: params differ from the frozen settings"
        ]


def test_expected_params_match_the_sim() -> None:
    assert man._same_json(man.expected_params(), json.loads(json.dumps(sim.params())))


def test_sketch_recheck_checks_r_run() -> None:
    sk = _sketch()
    sk["R_run"] = [24]
    assert man.sketch_violations(sk, _ROOT) == [
        "sketch: R_run does not cover the R candidates"
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
    sk = _sketch()
    i = _favourable_2tau(sk["sweeps"])
    zero = {PASS: 0.0, ABSENT: 0.0, UNDER: 1.0, INVALID: 0.0}
    forged = {
        **sk["sweeps"][i],
        "pass": 0.9,
        "per_seed": [{**p, **zero} for p in sk["sweeps"][i]["per_seed"]],
    }
    truncated = {**sk, "sweeps": [forged]}
    out = man.sketch_violations(truncated, _ROOT)
    assert "sketch: sweep rows differ from the points the rule requires" in out
    assert "sketch: a sweep row's pass differs from its per-seed results" in out
    inconsistent = _sketch()
    inconsistent["sweeps"][i] = forged
    assert man.sketch_violations(inconsistent, _ROOT) == [
        "sketch: a sweep row's pass differs from its per-seed results"
    ]
    no_go = _sketch()
    no_go["sweeps"][0]["no_go"] = 0.5
    # no_go は境目の再計算にも使うので、境目の照合も落ちる
    assert man.sketch_violations(no_go, _ROOT) == [
        "sketch: a sweep row's no_go differs from its per-seed results",
        "sketch: boundaries differ from a recomputation from the sweeps",
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
    bounds["boundaries"]["R288"]["homog_sd005"]["favorable"]["pass_08"] = 0.3
    assert man.sketch_violations(bounds, _ROOT) == [
        "sketch: boundaries differ from a recomputation from the sweeps"
    ]


def test_sketch_recheck_recomputes_selection_and_reach() -> None:
    sk = _sketch()
    sk["selection"] = {"selected_R": 96, "door_close": False}
    assert "sketch: the selection differs from a recomputation of the rule" in (
        man.sketch_violations(sk, _ROOT)
    )
    unreached = _sketch()
    unreached["sweeps"] = []
    assert (
        "sketch: most_favorable_reaches differs from a recomputation from the sweeps"
        in (man.sketch_violations(unreached, _ROOT))
    )
    flipped = _sketch()
    flipped["most_favorable_reaches"] = False
    assert man.sketch_violations(flipped, _ROOT) == [
        "sketch: most_favorable_reaches differs from a recomputation from the sweeps"
    ]


def test_recompute_selection() -> None:
    ok = {
        "power_ok": True,
        "no_go_ok": True,
        "size_ok": True,
        "band_ok": True,
        "calibrated": True,
    }
    rows = [{"R": r, **ok} for r in (24, 48, 72, 96)]
    assert man.recompute_selection(rows) == {"selected_R": 96, "door_close": False}
    rows[3]["band_ok"] = False
    assert man.recompute_selection(rows) == {"selected_R": 72, "door_close": False}
    for flag in ok:
        bad = [{"R": r, **ok, flag: False} for r in (24, 48, 72, 96)]
        assert man.recompute_selection(bad) == {"selected_R": None, "door_close": True}
    truthy = [{"R": 24, **ok, "band_ok": 1}]
    assert man.recompute_selection(truthy) == {"selected_R": None, "door_close": True}


def test_freeze_violations_stage_pilot() -> None:
    sk = _sketch()
    assert man.freeze_violations(sk, PILOT_FROZEN) == []
    assert man.freeze_violations(sk, FROZEN) == []
    assert man.freeze_violations(sk, DRAFT) == [man.DRAFT]
    closed = {**sk, "selection": {"selected_R": None, "door_close": True}}
    assert man.freeze_violations(closed, PILOT_FROZEN) == [man.DOOR_CLOSE]
    other = {**sk, "selection": {"selected_R": 12, "door_close": False}}
    assert man.freeze_violations(other, PILOT_FROZEN) == [man.DOOR_CLOSE]
    smaller = {**sk, "selection": {"selected_R": 192, "door_close": False}}
    assert man.freeze_violations(smaller, PILOT_FROZEN) == []
    unreached = {**sk, "most_favorable_reaches": False}
    assert man.freeze_violations(unreached, PILOT_FROZEN) == [man.NOT_REACHED]


# ------------------------------------------------------------- 第 2 段


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def test_stage1_seal_allows_only_the_status_line(tmp_path: Path) -> None:
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
    not_all = {**_driver_cert(root), "all_killed": False}
    assert man.driver_certification_violations(not_all, root) == [
        "driver: certification is not all KILLED"
    ]
    _write(root, man.DRIVER, "edited\n")
    assert "driver: recorded target_sha256 differs from the current file" in (
        man.driver_certification_violations(
            _driver_cert(tmp_path) | {"target_sha256": {}}, root
        )
    )
    assert man.driver_certification_violations(None, root) == [
        "driver: certification missing"
    ]


def test_driver_certification_requires_the_expected_failures(
    tmp_path: Path, fake_driver_harness: None
) -> None:
    del fake_driver_harness
    root = _driver_root(tmp_path)
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
    ns = types.SimpleNamespace
    case = ("m", "driver.py", "old", "new", ("test_m",))
    assert man.meta_want((case,)) == {"m": ["test_m"]}
    for bad_cases in (
        (),
        (("m", "f", "o", "n", ()),),
        (("m", "f", "o", "n", ("test_a",)), ("m", "f", "o", "n", ("test_b",))),
        ((1, "f", "o", "n", ("test_a",)),),
        (("m", "f", "o", "n", (1,)),),
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
    _fake_harness(monkeypatch, MUTANTS=[good, good], META_CASES=(case,))
    assert man.driver_certification_violations(_driver_cert(root), root) == [
        "driver: mutant rows differ from the registered driver mutants"
    ]


def test_driver_certification_requires_the_harness_module(tmp_path: Path) -> None:
    root = _driver_root(tmp_path)
    out = man.driver_certification_violations(_driver_cert(root), root)
    assert "driver: mutant rows differ from the registered driver mutants" in out
    assert DRIVER_META_MSG in out


@pytest.fixture(autouse=True)
def _cheap_oc(monkeypatch: pytest.MonkeyPatch) -> None:
    """pilot の再計算の照合だけを見るので、spike-in の OC は偽物にする.

    OC の中身は test_pilot_gate で見る。
    """
    monkeypatch.setattr(man.pg, "oc_for_r", lambda _x, _nb, r: {"R": r, "ok": True})


def _pilot_root(tmp_path: Path, selected_r: int) -> dict[str, Any]:
    samples = make_pilot()
    _write(
        tmp_path,
        man.PILOT_RECORDS,
        "\n".join(json.dumps(vars(s), ensure_ascii=False) for s in samples) + "\n",
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
    gate = _pilot_root(tmp_path, 24)
    prov = json.loads((tmp_path / man.PILOT_PROVENANCE).read_text(encoding="utf-8"))
    assert gate["decision"] == "GO"
    assert man.pilot_gate_violations(gate, prov, 24, tmp_path) == []
    forged = {**gate, "masked_max_bottom": 0.15}
    assert (
        "pilot gate: masked_max_bottom differs from a recomputation from the inputs"
        in (man.pilot_gate_violations(forged, prov, 24, tmp_path))
    )
    assert (
        "pilot gate: R differs from the sketch selection"
        in man.pilot_gate_violations(gate, prov, 96, tmp_path)
    )
    stop = {**gate, "decision": "STOP"}
    assert "pilot gate: not GO" in man.pilot_gate_violations(stop, prov, 24, tmp_path)
    unbound = {**gate, "inputs_sha256": {}}
    assert "pilot gate: input records is not bound to the current file" in (
        man.pilot_gate_violations(unbound, prov, 24, tmp_path)
    )
    _write(tmp_path, man.PILOT_META, json.dumps({**META, "extra": 1}))
    assert man.pilot_gate_violations(gate, prov, 24, tmp_path) != []
    assert man.pilot_gate_violations(None, prov, 24, tmp_path) == [
        "pilot gate: missing"
    ]


def test_pilot_provenance_binds_driver_records_and_meta(tmp_path: Path) -> None:
    gate = _pilot_root(tmp_path, 24)
    prov = json.loads((tmp_path / man.PILOT_PROVENANCE).read_text(encoding="utf-8"))
    assert man.pilot_gate_violations(gate, prov, 24, tmp_path) == []
    for key, rel in (
        ("driver_sha256", man.DRIVER),
        ("records_sha256", man.PILOT_RECORDS),
        ("meta_sha256", man.PILOT_META),
    ):
        want = [f"pilot: provenance {key} does not bind the current {rel}"]
        mixed = {**prov, key: "0" * 64}
        assert man.pilot_gate_violations(gate, mixed, 24, tmp_path) == want
        missing = {k: v for k, v in prov.items() if k != key}
        assert man.pilot_gate_violations(gate, missing, 24, tmp_path) == want


def test_committed_artifacts_are_bound() -> None:
    """commit した成果物が現在のコードに結び付いている.

    certification・見取り図・fixture 表と、コード・test・harness。
    """
    assert man.binding_violations(_ROOT) == []
    sketch = json.loads((_ROOT / man.SKETCH).read_text(encoding="utf-8"))
    assert sketch["selection"]["door_close"] is False


def test_freeze_violations_stage_main_checks_the_seal(tmp_path: Path) -> None:
    out = man.freeze_violations(_sketch(), FROZEN, "main", tmp_path)
    assert "stage 1: manifest.json is missing or unreadable" in out
    assert "pilot gate: missing" in out
    assert "driver: certification missing" in out
    assert man.NOT_MAIN_FROZEN in man.freeze_violations(
        _sketch(), PILOT_FROZEN, "main", tmp_path
    )


def test_prereg_body_sha256_ignores_only_the_status_line() -> None:
    a = man.prereg_body_sha256("# p\n- status: **PILOT-FROZEN**\nbody\n")
    b = man.prereg_body_sha256("# p\n- status: **FROZEN** (x)\nbody\n")
    c = man.prereg_body_sha256("# p\n- status: **FROZEN** (x)\nbody2\n")
    assert a == b
    assert a != c


def test_stage1_seal_file_set(tmp_path: Path) -> None:
    for rel in man.FROZEN_FILES:
        _write(tmp_path, rel, f"content of {rel}\n")
    manifest = man.build_manifest(tmp_path)
    manifest["files"].pop(man.SKETCH)
    _write(tmp_path, man.MANIFEST, json.dumps(manifest))
    assert man.stage1_seal_violations(tmp_path) == [
        "stage 1: sealed file set differs from FROZEN_FILES"
    ]


def _set_row(sk: dict[str, Any], kind: str, rates: dict[str, float]) -> None:
    row = next(r for r in sk["per_R"][LAST]["rows"] if r["kind"] == kind)
    row["per_seed"] = [{**p, **rates} for p in row["per_seed"]]
    row["value"] = rates[PASS if kind == "power_pass" else ABSENT]


def test_sketch_recheck_power_flags() -> None:
    low = {PASS: 0.5, ABSENT: 0.0, UNDER: 0.5, INVALID: 0.0}
    sk = _sketch()
    _set_row(sk, "power_pass", low)
    assert "sketch R288: power_ok differs from a recomputation from the rows" in (
        man.sketch_violations(sk, _ROOT)
    )
    sk2 = _sketch()
    _set_row(sk2, "power_no_go", {PASS: 0.0, ABSENT: 0.5, UNDER: 0.5, INVALID: 0.0})
    assert "sketch R288: no_go_ok differs from a recomputation from the rows" in (
        man.sketch_violations(sk2, _ROOT)
    )


def test_fixture_table_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    """表の照合だけを見るので、fixture 表の計算は偽物にする.

    計算そのものは test_fixtures で見る。
    """
    monkeypatch.setattr(man.fx, "fixture_table", lambda r: {"R": r})
    fresh = {f"R{r}": {"R": r} for r in sim.R_CANDIDATES}
    assert man.fixture_violations({"tables": fresh, "passed": True}) == []
    assert man.fixture_violations({"tables": {}, "passed": True}) == [
        "fixture table: differs from a recomputation with the current code"
    ]
    assert man.fixture_violations({"tables": fresh, "passed": False}) == [
        "fixture table: the τ/4 gate failed"
    ]


def _sketch_with(mp_attrs: dict[str, object]) -> dict[str, Any]:
    """sim の登録を差し替えて (形の削除など) 作った見取り図."""
    with tempfile.TemporaryDirectory() as tmp, pytest.MonkeyPatch.context() as mp:
        mp.setattr(sim, "simulate", _fake_simulate)
        mp.setattr(sim, "pure_extremal_size", lambda *_a, **_k: 0.0)
        mp.setattr("builtins.print", lambda *_a, **_k: None)
        for name, value in mp_attrs.items():
            mp.setattr(sim, name, value)
        out = Path(tmp) / "sketch.json"
        assert sim.main(["--out", str(out)]) == 0
        sketch: dict[str, Any] = json.loads(out.read_text(encoding="utf-8"))
        return sketch


def test_registry_catches_a_dropped_form() -> None:
    """sim の FORMS から形を削ると、manifest の登録との不一致で落ちる.

    登録は sim から導かない (Codex HIGH-4)。
    """
    forms = tuple(f for f in sim.FORMS if f != "asc_only")
    out = man.sketch_violations(_sketch_with({"FORMS": forms}), _ROOT)
    assert "sketch R288: rows differ from the points the rule requires" in out
    assert "sketch: sweep rows differ from the points the rule requires" in out


def test_registry_catches_a_dropped_nuisance() -> None:
    grid = tuple(nu for nu in sim.nuisance_grid() if nu.coupling != "anti")
    out = man.sketch_violations(_sketch_with({"nuisance_grid": lambda: grid}), _ROOT)
    assert "sketch R288: rows differ from the points the rule requires" in out


def test_registered_reach_matches_the_sim() -> None:
    """manifest が独立に計算した到達上限は sim と一致する (時系列の形の係数を含む)."""
    for r in man.REGISTERED_R:
        for form in man.REGISTERED_FORMS:
            for _, nu in man._sweep_nuisances(form):
                want = man.registered_reach(form, nu.base, nu.bot, r)
                assert sim.reachable(form, nu, r) == pytest.approx(want, abs=1e-12)
    assert man.REGISTERED_FORMS == sim.FORMS
    assert [(n.base, n.bot, n.coupling) for n in sim.nuisance_grid()] == list(
        man.REGISTERED_NUISANCES
    )


def test_sketch_recheck_calibration() -> None:
    sk = _sketch()
    row = sk["per_R"][LAST]["rows"][0]
    row["per_seed"][0] = {**row["per_seed"][0], "realized_C": row["target_C"] + 0.05}
    out = man.sketch_violations(sk, _ROOT)
    assert "sketch R288: calibrated differs from a recomputation from the rows" in out
    sw = _sketch()
    sw["sweeps"][0]["per_seed"][0] = {
        **sw["sweeps"][0]["per_seed"][0],
        "realized_C": sw["sweeps"][0]["target_C"] + 0.05,
    }
    assert man.sketch_violations(sw, _ROOT) == [
        "sketch: a sweep row is not calibrated to its target"
    ]


def test_registry_rejects_empty_names() -> None:
    """空の label・test 名を登録として受け入れない (Codex LOW-6)."""
    assert man._registry([("", ["test_x"])]) is None
    assert man._registry([("m", [" "])]) is None
    assert man._registry([("m", ["test_x"])]) == {"m": ["test_x"]}
    assert not man.failed_for_expected({"failed": [""], "expected_any_of": [""]})


def test_registered_size_threshold_matches_its_definition() -> None:
    """manifest の size の閾値は、定義を有理数で数えた値と一致する.

    定義 = P(X > x) ≤ 0.01 / G を満たす最小の x。
    """
    for n_sims, g in ((20, 1), (40, 3), (60, 2)):
        tail = [
            sum(
                Fraction(math.comb(n_sims, k))
                * Fraction(1, 20) ** k
                * Fraction(19, 20) ** (n_sims - k)
                for k in range(x + 1, n_sims + 1)
            )
            for x in range(n_sims + 1)
        ]
        want = min(x for x in range(n_sims + 1) if tail[x] <= Fraction(1, 100 * g))
        assert man.registered_size_threshold(g, n_sims) == want
    # 本走の size の点の数 (G = 1140) では 596 (Codex 2 周目が別方式で確かめた値)
    assert man.registered_size_threshold(1140) == 596
    for g in (1, 996, 1140):
        assert man.registered_size_threshold(g) == sim.size_count_threshold(g)


def test_size_threshold_is_independent_of_the_sim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """sim の閾値の計算が誤っていても、manifest の再計算は誤りを共有しない.

    Codex 2 周目 MEDIUM-1。
    """
    monkeypatch.setattr(sim, "size_count_threshold", lambda *_a, **_k: 700)
    sk = _sketch_with({})
    assert sk["per_R"][LAST]["size_count_threshold"] == 700
    out = man.sketch_violations(sk, _ROOT)
    assert "sketch R288: the size threshold differs from a recomputation" in out


def test_registered_boundary_matches_its_definition() -> None:
    rising = [(0.0, 0.1), (0.1, 0.5), (0.2, 0.9), (0.3, 1.0)]
    assert man.registered_boundary(rising) == pytest.approx(0.175)
    falling = [(0.0, 1.0), (0.1, 0.9), (0.2, 0.5), (0.3, 0.1)]
    assert man.registered_boundary(falling, rising=False) == pytest.approx(0.125)
    # 上昇の向きで最初から 0.8 以上なら、最初の点を境目とする
    assert man.registered_boundary(falling) == 0.0
    assert man.registered_boundary(rising, rising=False) is None
    assert man.registered_boundary([(0.1, 0.85), (0.2, 0.9)]) == 0.1
    assert man.registered_boundary([(0.1, 0.8), (0.2, 0.7)], rising=False) == 0.1
    assert man.registered_boundary([]) is None
    for pts in (rising, falling, list(reversed(rising))):
        for up in (True, False):
            assert man.registered_boundary(pts, rising=up) == sim.boundary(
                pts, rising=up
            )


@pytest.mark.parametrize("direction", ["rising", "falling"])
def test_boundaries_are_independent_of_the_sim(
    monkeypatch: pytest.MonkeyPatch, direction: str
) -> None:
    """sim の境目の補間が片方の向きで誤っていても、manifest の再計算は誤りを共有しない.

    Codex 2 周目 MEDIUM-1。
    """
    broken_rising = direction == "rising"
    original = sim.boundary

    def broken(
        points: list[tuple[float, float]], *, rising: bool = True
    ) -> float | None:
        if rising == broken_rising:
            return 0.123
        return original(points, rising=rising)

    monkeypatch.setattr(sim, "boundary", broken)
    sk = _sketch_with({})
    assert "sketch: boundaries differ from a recomputation from the sweeps" in (
        man.sketch_violations(sk, _ROOT)
    )

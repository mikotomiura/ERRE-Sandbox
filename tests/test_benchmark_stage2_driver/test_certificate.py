"""判別性 gate 段 2 の本走前の certification の証明書の読み手 (Codex r1 H7、DD-11).

証明書 = ``experiments/20261126-benchmark-stage2-driver/results/driver_mutation.json``
(``scripts/benchmark_stage2_driver_mutation_check.py --out`` が、全 KILLED・meta-test
成立・原状復帰のときだけ書く。pilot 前の版 pre_pilot を本走前の版 pre_main で
上書きした、DD-11)。8 対象・test・harness・原本の test・pilot の gate.json の sha、
全変異の label・期待 test・witness・判定、meta-test を、現在のファイルと harness の
登録に照合する。

本 file は変異の run では回さない (証明書と現在のファイルの一致は、変異中は必ず崩れて
生き残りを覆う)。harness の判定器の負例 (``test_judge_*``) も本 file が pin する。
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

import pytest
from scripts import benchmark_stage2_driver as dr
from scripts import benchmark_stage2_driver_mutation_check as mc
from scripts import benchmark_stage2_fixtures as fxm
from scripts import benchmark_stage2_freeze as fz
from scripts import benchmark_stage2_manifest as man
from scripts import benchmark_stage2_manifest_main as mm
from scripts import benchmark_stage2_plan as pl
from scripts import benchmark_stage2_scorer as sc

REPO = pathlib.Path(__file__).resolve().parents[2]
CERT = (
    REPO / "experiments/20261126-benchmark-stage2-driver/results/driver_mutation.json"
)


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def cert() -> dict[str, Any]:
    return json.loads(CERT.read_text(encoding="utf-8"))


def test_certificate_is_the_pre_main_version(cert: dict[str, Any]) -> None:
    assert cert["version"] == "pre_main"
    assert set(mc._TARGETS) >= {"fixtures", "scorer"}
    assert cert["targets"] == mc._TARGETS
    assert cert["all_killed"] is True


def test_certificate_binds_the_current_files(cert: dict[str, Any]) -> None:
    want = {
        pathlib.PurePath(rel).name: _sha(rel)
        for rel in [*mc._TARGETS.values(), mc._HARNESS_REL]
    }
    for path in sorted((REPO / mc._TEST_DIR).glob("*.py")):
        want["tests/" + path.name] = _sha(path.relative_to(REPO).as_posix())
    assert cert["target_sha256"] == want
    assert cert["witness_tests_sha256"] == {rel: _sha(rel) for rel in mc._WITNESS_EXTRA}
    gate = f"{mc._EXP_REL}/{mc._PILOT_GATE_REL}"
    assert cert["inputs_sha256"] == {gate: _sha(gate)}


def evidence_problems(row: dict[str, Any], mut: mc.Mutant) -> list[str]:  # noqa: C901
    """証明書の 1 行の証拠が KILLED と登録に整合しない点.

    DD-12 H4: 判定器の判定を読み手が検査し直す。
    """
    out: list[str] = []
    w = mut.witness
    if row.get("status") != "KILLED":
        out.append("status is not KILLED")
    seen = row.get("witnessed_by")
    if not isinstance(seen, dict):
        return [*out, "no witnessed_by"]
    if seen.get("function") not in mut.expect:
        out.append("witness function is not an expected test")
    if seen.get("function") not in (row.get("failed") or []):
        out.append("witness function is not in failed")
    if seen.get("when") != w.when:
        out.append("when differs")
    if w.item is not None and seen.get("param") != w.item:
        out.append("param differs from the registered item")
    if w.item is None and not w.assert_stmt and seen.get("param") is not None:
        out.append("a parametrized record for a witness without item")
    kind = str(seen.get("type", "")).split(".")[-1]
    if w.assert_stmt and (
        seen.get("assert_stmt") is not True or kind != "AssertionError"
    ):
        out.append("not an assert statement of the test")
    if w.exc is not None and kind != w.exc:
        out.append("exception type differs")
    # 要約の文は先頭 300 字 (登録の文はどれも先頭にある)
    if w.text is not None and w.text not in str(seen.get("text", "")):
        out.append("text differs")
    frames = seen.get("frames")
    if not isinstance(frames, list):
        out.append("no frames")
    elif w.via is not None and not any(
        isinstance(f, list) and f[:1] and f[0] in mc._TARGET_FILES and f[1:2] == [w.via]
        for f in frames
    ):
        out.append("no frame of the registered via")
    return out


def test_certificate_lists_every_registered_mutant_as_killed(
    cert: dict[str, Any],
) -> None:
    rows = cert["mutants"]
    assert [r["label"] for r in rows] == [m.label for m in mc.MUTANTS]
    for row, mut in zip(rows, mc.MUTANTS, strict=True):
        assert row["target"] == mc._TARGETS[mut.target]
        assert row["expected_any_of"] == sorted(mut.expect)
        assert row["expected_witness"] == mut.witness.as_dict()
        assert row["why"] == mut.why
        assert evidence_problems(row, mut) == [], row["label"]


def test_evidence_reader_rejects_contradicting_rows(cert: dict[str, Any]) -> None:
    """KILLED の行の証拠を崩すと読み手が拒む.

    Codex r2 H4 の例: g24 の failed を空・型を ValueError に。
    """
    by_label = {m.label.split()[0]: m for m in mc.MUTANTS}
    rows = {r["label"].split()[0]: r for r in cert["mutants"]}

    def broken(label: str, **kw: Any) -> list[str]:
        row = json.loads(json.dumps(rows[label]))
        for k, v in kw.items():
            if k == "failed":
                row["failed"] = v
            else:
                row["witnessed_by"][k] = v
        return evidence_problems(row, by_label[label])

    assert broken("g24", failed=[]) == ["witness function is not in failed"]
    assert broken("g24", type="builtins.ValueError") == [
        "not an assert statement of the test"
    ]
    assert broken("g24", assert_stmt=False) == ["not an assert statement of the test"]
    assert broken("f14", frames=[]) == ["no frame of the registered via"]
    assert broken("c46", param="<lambda>18") == [
        "param differs from the registered item"
    ]


def test_certificate_controls_cover_every_file_set(cert: dict[str, Any]) -> None:
    index = mc.index_tests()
    want = sorted({tuple(mc._files_for(m.expect, index)) for m in mc.MUTANTS})
    assert cert["control_file_sets"] == [list(f) for f in want]


def test_certificate_meta_tests_failed_as_expected(cert: dict[str, Any]) -> None:
    meta = cert["meta_test"]
    assert [m["label"] for m in meta] == [c[0] for c in mc.META_CASES]
    for row, case in zip(meta, mc.META_CASES, strict=True):
        assert row["status"] == "FAILED_AS_EXPECTED"
        assert row["target"] == mc._TARGETS[case[1]]
        assert set(case[4]) <= set(row["failed"])


def test_anchors_are_unique_and_compile() -> None:
    assert mc.anchor_problems(mc._sources()) == []


def test_pinned_files_are_lf() -> None:
    """証明書の sha は LF の checkout の bytes (作業ツリーの CRLF は CI と食い違う)."""
    assert mc.crlf_files() == []


def test_every_target_has_mutants() -> None:
    assert {m.target for m in mc.MUTANTS} == set(mc._TARGETS)


# ------------------------------------------------------------ 第 2 段の封印 (実 repo)


def test_manifest_main_mirrors_the_harness() -> None:
    """封印の照合が写した証明書の範囲は harness の登録と同じ.

    照合の module は harness を import しない (scorer が import するため)。
    """
    assert mm.CERT_TARGETS == mc._TARGETS
    assert mm.CERT_HARNESS == mc._HARNESS_REL
    assert mm.CERT_TEST_DIR == mc._TEST_DIR
    assert mm.CERT_WITNESS_EXTRA == mc._WITNESS_EXTRA
    assert f"{mc._EXP_REL}/{mc._PILOT_GATE_REL}" == mm.GATE
    assert mm.CERT_VERSION == mc._VERSION
    assert REPO / mm.CERT == CERT


def test_real_manifest_main_verifies() -> None:
    """``--verify`` (封印の照合 + battery_checks の再計算) が実 repo で通る."""
    assert fz.verify(REPO) == []
    assert fz.main(["--verify"]) == 0


def test_real_main_plan_passes_the_entry_check() -> None:
    """driver の本走の入口 (送信前の照合) が実の gate で通る (送信はしない)."""
    segs = dr.plan_for(pl.STAGE_MAIN, REPO / mm.GATE)
    assert {s.battery for s in segs} == set(mm.go_r((REPO / mm.GATE).read_bytes()))


def test_real_fixture_diffs_main_is_the_recomputation() -> None:
    body = fxm.compute_text(REPO / mm.GATE).encode("utf-8")
    assert (REPO / mm.FIXTURE_MAIN).read_bytes() == body


@pytest.mark.parametrize("battery", ["v2", "v3", "G", "O_time"])
def test_check_names_mirror_the_plan(battery: str) -> None:
    """照合が写した battery_checks の項目の名前は plan の出力と同じ (R に依らない)."""
    rs = {"v2": (8, 32), "v3": (8, 80), "G": (6, 36), "O_time": (6, 138)}[battery]
    for r in rs:
        assert set(pl.battery_checks(battery, r)) == mm.check_keys(battery)


def test_pilot_manifest_constant_is_the_current_stage1_manifest() -> None:
    """書き手の定数 (pilot の凍結の commit b626962 の版) = 現在の manifest.json."""
    assert _sha(man.MANIFEST) == fz.MANIFEST_PILOT_SHA256


def test_real_external_modules_match_their_chain_seals() -> None:
    assert mm.external_modules(REPO)
    assert fz.external_seal_problems(REPO) == []


def test_real_scorer_passes_the_entry_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """scorer の入口 (判定前の照合) が実 repo で通り、記録の読みに届く."""

    class Reached(Exception):  # noqa: N818 — 届いた印
        pass

    def reached(*_a: object, **_k: object) -> object:
        raise Reached

    monkeypatch.setattr(sc.rd, "read_run", reached)
    with pytest.raises(Reached):
        sc.compute_verdict(
            tmp_path, REPO / mm.GATE, REPO / mm.MODELS, REPO / mm.FIXTURE_MAIN
        )


def test_stage1_verify_fails_only_on_the_status_after_the_freeze() -> None:
    """第 1 段の ``--verify --stage pilot`` は FROZEN の後は status で落ちる.

    設計どおり (prereg は status 行だけが変わる。全体の sha は変わる)。
    """
    stage1 = json.loads((REPO / man.MANIFEST).read_text(encoding="utf-8"))
    assert man.violations(REPO, stage1) == [
        "prereg: status is not PILOT-FROZEN",
        "prereg: sha256 differs",
    ]


# ------------------------------------------------------------ 判定器の負例


def _finish(**kw: Any) -> dict[str, Any]:
    row = {"when": "sessionfinish", "exitstatus": 1, "items": 3, "ran": 3}
    row["stopped"] = False
    row.update(kw)
    return row


def _fail(
    function: str, *, param: str | None = None, assert_stmt: bool = True, **link: Any
) -> dict[str, Any]:
    head = {"type": "builtins.AssertionError", "text": "", "frames": []}
    head.update(link)
    return {
        "function": function,
        "param": param,
        "when": "call",
        "assert_stmt": assert_stmt,
        "chain": [head],
    }


_MUT = mc.Mutant("x", "driver", "a", "b", frozenset({"test_a"}), "why")


def test_judge_kills_only_with_the_witness_of_an_expected_test() -> None:
    def status(records: list[dict[str, Any]], code: int = 1) -> str:
        return mc.status_of(_MUT, code, {"test_a"}, records, collect=False)

    assert status([_fail("test_a"), _finish()]) == "KILLED"
    assert status([_fail("test_b"), _finish()]) == "WRONG_REASON"
    assert status([_fail("test_a", assert_stmt=False), _finish()]) == "WRONG_REASON"
    assert status([_fail("test_a"), _finish(stopped=True)]) == "ABNORMAL_EXIT"
    assert status([_fail("test_a"), _finish(ran=2)]) == "ABNORMAL_EXIT"
    assert status([_fail("test_a")]) == "ABNORMAL_EXIT"
    assert status([_fail("test_a"), _finish()], code=2) == "ABNORMAL_EXIT"
    assert status([], code=0) == "SURVIVED"
    assert status([], code=-1) == "TIMEOUT"
    assert mc.status_of(_MUT, 1, set(), [_finish()], collect=False) == (
        "NO_FAILURE_RECORD"
    )
    assert mc.status_of(_MUT, 1, {"test_a"}, [_finish()], collect=True) == (
        "COLLECTION_ERROR"
    )


def test_judge_matches_item_type_and_text_on_one_exception() -> None:
    w = mc.Witness(item="p1", exc="Failed", text="DID NOT RAISE")
    expect = frozenset({"test_a"})
    failed = _fail(
        "test_a",
        param="p1",
        assert_stmt=False,
        type="_pytest.outcomes.Failed",
        text="DID NOT RAISE <class 'X'>",
    )
    assert mc.witnessed(w, expect, [failed]) is not None
    assert mc.witnessed(w, expect, [{**failed, "param": "p2"}]) is None
    other = {**failed, "chain": [{**failed["chain"][0], "text": "other"}]}
    assert mc.witnessed(w, expect, [other]) is None
    # 理由の文のある証拠で item を名指さないものは、parametrize の記録に一致しない
    bare = mc.Witness(exc="Failed", text="DID NOT RAISE")
    assert mc.witnessed(bare, expect, [failed]) is None
    assert mc.witnessed(bare, expect, [{**failed, "param": None}]) is not None
    # fixture の setup の ERROR は段を名指した登録だけが数える
    setup = {**failed, "when": "setup", "param": None}
    assert mc.witnessed(bare, expect, [setup]) is None


def test_judge_setup_type_error_needs_the_registered_frame() -> None:
    """DD-12 H3: f14 は R = None が main_r_list に届いた TypeError だけを数える."""
    mut = next(m for m in mc.MUTANTS if m.label.startswith("f14 "))
    fn = next(iter(mut.expect))

    def setup(text: str, frames: list[list[str]]) -> dict[str, Any]:
        return {
            "function": fn,
            "param": None,
            "when": "setup",
            "assert_stmt": False,
            "chain": [{"type": "builtins.TypeError", "text": text, "frames": frames}],
        }

    right = setup(
        "unsupported operand type(s) for +: 'int' and 'NoneType'",
        [
            ["test_fixtures.py", "real_diffs"],
            ["benchmark_stage2_fixtures.py", "main_r_list"],
        ],
    )
    assert mc.witnessed(mut.witness, mut.expect, [right]) is not None
    # 別の setup の TypeError (方策の計算の中) は WRONG_REASON
    other = setup(
        "'NoneType' object is not subscriptable",
        [
            ["test_fixtures.py", "real_diffs"],
            ["benchmark_stage2_fixtures.py", "battery_table"],
        ],
    )
    assert mc.witnessed(mut.witness, mut.expect, [other]) is None
    rec = [other, _finish()]
    assert mc.status_of(mut, 1, {fn}, rec, collect=False) == "WRONG_REASON"


def test_judge_assert_statement_must_come_from_a_witness_test_file(
    tmp_path: pathlib.Path,
) -> None:
    def raise_from(name: str, line: str) -> AssertionError:
        # traceback は行の文を disk の file から読むので、実の file を書いて実行する
        (tmp_path / name).write_text(line + "\n", encoding="utf-8")
        code = compile(line + "\n", str(tmp_path / name), "exec")
        try:
            exec(code, {})  # noqa: S102 — 判定器の負例 (固定の文)
        except AssertionError as exc:
            return exc
        raise AssertionError  # pragma: no cover

    top = "<module>"  # exec した文の最後のフレームの関数名
    assert mc._assert_stmt(raise_from("test_driver.py", "assert 1 == 2"), top)
    assert not mc._assert_stmt(raise_from("other.py", "assert 1 == 2"), top)
    assert not mc._assert_stmt(raise_from("test_units.py", "raise AssertionError"), top)
    assert not mc._assert_stmt(ValueError("x"), top)
    # B-2: 期待 test でない関数 (test の helper) の assert は数えない
    assert not mc._assert_stmt(
        raise_from("test_driver.py", "assert 1 == 2"), "test_something"
    )


def test_redact_removes_local_paths_and_addresses() -> None:
    text = r"C:\Users\someone\AppData\x.py at 0x00000195CF8963E0"
    out = mc.redact(text)
    assert "someone" not in out
    assert "0x00000195CF8963E0" not in out

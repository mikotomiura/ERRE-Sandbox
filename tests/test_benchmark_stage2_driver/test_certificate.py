"""判別性 gate 段 2 の pilot 前の certification の証明書の読み手 (Codex r1 H7、DD-6).

証明書 = ``experiments/20261126-benchmark-stage2-driver/results/driver_mutation.json``
(``scripts/benchmark_stage2_driver_mutation_check.py --out`` が、全 KILLED・meta-test
成立・原状復帰のときだけ書く)。対象・test・harness の sha、全変異の label・期待 test・
witness・判定、meta-test を、現在のファイルと harness の登録に照合する。

本 file は変異の run では回さない (証明書と現在のファイルの一致は、変異中は必ず崩れて
生き残りを覆う)。harness の判定器の負例 (``test_judge_*``) も本 file が pin する。
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

import pytest
from scripts import benchmark_stage2_driver_mutation_check as mc

REPO = pathlib.Path(__file__).resolve().parents[2]
CERT = (
    REPO / "experiments/20261126-benchmark-stage2-driver/results/driver_mutation.json"
)


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def cert() -> dict[str, Any]:
    return json.loads(CERT.read_text(encoding="utf-8"))


def test_certificate_is_the_pre_pilot_version(cert: dict[str, Any]) -> None:
    assert cert["version"] == "pre_pilot"
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
    assert cert["witness_tests_sha256"] == {mc._STATS_TEST: _sha(mc._STATS_TEST)}


def test_certificate_lists_every_registered_mutant_as_killed(
    cert: dict[str, Any],
) -> None:
    rows = cert["mutants"]
    assert [r["label"] for r in rows] == [m.label for m in mc.MUTANTS]
    for row, mut in zip(rows, mc.MUTANTS, strict=True):
        assert row["status"] == "KILLED", row["label"]
        assert row["target"] == mc._TARGETS[mut.target]
        assert row["expected_any_of"] == sorted(mut.expect)
        assert row["expected_witness"] == mut.witness.as_dict()
        assert row["why"] == mut.why
        seen = row["witnessed_by"]
        assert seen is not None, row["label"]
        assert seen["function"] in mut.expect
        assert seen["when"] == mut.witness.when
        if mut.witness.item is not None:
            assert seen["param"] == mut.witness.item
        # 照合した例外の型・文も登録を満たす (要約の文は先頭 300 字)
        if mut.witness.exc is not None:
            assert str(seen["type"]).split(".")[-1] == mut.witness.exc
        if mut.witness.text is not None:
            assert mut.witness.text in str(seen["text"])


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

    assert mc._assert_stmt(raise_from("test_driver.py", "assert 1 == 2"))
    assert not mc._assert_stmt(raise_from("other.py", "assert 1 == 2"))
    assert not mc._assert_stmt(raise_from("test_units.py", "raise AssertionError"))
    assert not mc._assert_stmt(ValueError("x"))


def test_redact_removes_local_paths_and_addresses() -> None:
    text = r"C:\Users\someone\AppData\x.py at 0x00000195CF8963E0"
    out = mc.redact(text)
    assert "someone" not in out
    assert "0x00000195CF8963E0" not in out

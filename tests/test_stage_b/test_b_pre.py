"""B-pre rule (prereg §7) の合成 test。実 bank は読まない (計算は run.sh で 1 回)."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scripts import stage_b_pre as mod

CTXS = [f"ctx-{n}" for n in range(8)]
Zone = Callable[[str, str, int], str]


def rows(zone: Zone) -> list[dict[str, Any]]:
    return [
        {
            "condition": cond,
            "frozen_ctx_id": ctx,
            "mc_index": i,
            "pre_bias_destination_zone": zone(cond, ctx, i),
            "resolved_from": "pre_bias_direct_parse",
        }
        for cond in ("on", "off")
        for ctx in CTXS
        for i in range(300)
    ]


def write_bank(tmp_path: Path, data: list[dict[str, Any]]) -> Path:
    path = tmp_path / "bank.jsonl"
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in data), encoding="utf-8", newline="\n"
    )
    return path


def run_synthetic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, data: list[dict[str, Any]]
) -> dict[str, Any]:
    bank = write_bank(tmp_path, data)
    prereg = tmp_path / "prereg.md"
    prereg.write_bytes(b"frozen\n")
    monkeypatch.setattr(
        mod, "BANK_SHA256_PREREG", hashlib.sha256(bank.read_bytes()).hexdigest()
    )
    return mod.run(bank, prereg)


def test_split_is_one_fixed_permutation() -> None:
    h1, h2 = mod.split_halves()
    perm = np.random.default_rng(20260926).permutation(300)
    assert h1 == frozenset(perm[:150].tolist())
    assert h2 == frozenset(perm[150:].tolist())
    assert len(h1) == len(h2) == 150
    assert not h1 & h2


def test_tv_plugin_unsmoothed() -> None:
    assert mod.tv(Counter(a=2, b=2), Counter(a=4)) == pytest.approx(0.5)
    assert mod.tv(Counter(a=3), Counter(b=1)) == pytest.approx(1.0)
    assert mod.tv(Counter(a=1, b=3), Counter(a=1, b=3)) == 0.0


def test_context_specific_choice_is_established(tmp_path, monkeypatch) -> None:
    out = run_synthetic(tmp_path, monkeypatch, rows(lambda _c, ctx, _i: f"z{ctx}"))
    for cond in ("on", "off"):
        res = out["conditions"][cond]
        assert res["floor"] == 0.0
        assert res["between_median"] == 1.0
        assert res["n_pairs"] == 28
    assert out["b_pre_established"] is True
    assert out["status"] == "computed"
    assert out["verdict"] is None


def test_context_free_choice_is_not_established(tmp_path, monkeypatch) -> None:
    """文脈に依らない選択: between = 0、within = 半分間の差 → 不成立."""
    h1, _ = mod.split_halves()
    out = run_synthetic(
        tmp_path, monkeypatch, rows(lambda _c, _x, i: "za" if i in h1 else "zb")
    )
    res = out["conditions"]["on"]
    assert res["floor"] == 1.0
    assert res["between_median"] == 0.0
    assert out["b_pre_established"] is False
    assert out["verdict"] == "INVALID_TASK_BATTERY"


def test_equal_median_and_floor_is_not_established(tmp_path, monkeypatch) -> None:
    """成立は between 中央値 > 床 (strict)。全て同一分布 → 0 > 0 は不成立."""
    out = run_synthetic(tmp_path, monkeypatch, rows(lambda _c, _x, _i: "za"))
    assert out["conditions"]["off"]["floor"] == 0.0
    assert out["conditions"]["off"]["between_median"] == 0.0
    assert out["b_pre_established"] is False


def test_between_uses_half1_only(tmp_path, monkeypatch) -> None:
    """between は半分 1 同士の TV。半分 2 だけが文脈で違っても動かない."""
    h1, _ = mod.split_halves()
    out = run_synthetic(
        tmp_path,
        monkeypatch,
        rows(lambda _c, ctx, i: "za" if i in h1 else f"z{ctx}"),
    )
    res = out["conditions"]["on"]
    assert res["between_median"] == 0.0
    assert res["floor"] == 1.0


def test_floor_is_max_within(tmp_path, monkeypatch) -> None:
    """床は within の最大値 (平均でない)。1 context だけ半分間で割れる."""
    h1, _ = mod.split_halves()

    def zone(_c: str, ctx: str, i: int) -> str:
        if ctx == "ctx-0":
            return "za" if i in h1 else "zb"
        return f"z{ctx}"

    out = run_synthetic(tmp_path, monkeypatch, rows(zone))
    res = out["conditions"]["on"]
    assert res["within"]["ctx-0"] == 1.0
    assert res["floor"] == 1.0
    assert res["between_median"] == 1.0
    assert out["b_pre_established"] is False


def test_both_conditions_required(tmp_path, monkeypatch) -> None:
    out = run_synthetic(
        tmp_path,
        monkeypatch,
        rows(lambda cond, ctx, _i: f"z{ctx}" if cond == "on" else "za"),
    )
    assert out["conditions"]["on"]["established"] is True
    assert out["conditions"]["off"]["established"] is False
    assert out["b_pre_established"] is False


def test_hash_mismatch_is_not_computed(tmp_path: Path) -> None:
    bank = write_bank(tmp_path, rows(lambda _c, ctx, _i: f"z{ctx}"))
    out = mod.run(bank, tmp_path / "prereg.md")
    assert out["status"] == "not_computed"
    assert out["b_pre_established"] is False
    assert "conditions" not in out
    assert out["verdict"] is None


def test_missing_bank_is_not_computed(tmp_path: Path) -> None:
    out = mod.run(tmp_path / "absent.jsonl", tmp_path / "absent.md")
    assert out["inputs"]["bank"]["sha256"] is None
    assert out["prereg_sha256"] is None
    assert out["b_pre_established"] is False


def test_structure_problem_is_not_established(tmp_path, monkeypatch) -> None:
    data = [r for r in rows(lambda _c, ctx, _i: f"z{ctx}") if r["mc_index"] != 7]
    out = run_synthetic(tmp_path, monkeypatch, data)
    assert out["status"] == "not_computed"
    assert out["verdict"] is None
    assert out["reason"].startswith("input_structure")


def test_none_zone_is_counted_as_bottom_category(tmp_path, monkeypatch) -> None:
    """DB-3: None は 1 カテゴリ ⊥。半分 1 の None だけが文脈で違う → between が動く."""
    h1, _ = mod.split_halves()

    def zone(_c: str, ctx: str, i: int) -> str | None:
        if ctx in ("ctx-0", "ctx-1", "ctx-2", "ctx-3", "ctx-4") and i in h1:
            return None
        return "za"

    out = run_synthetic(tmp_path, monkeypatch, rows(zone))
    res = out["conditions"]["on"]
    assert out["status"] == "computed"
    assert res["bottom_rate"]["ctx-0"] == 0.5
    assert res["bottom_rate"]["ctx-7"] == 0.0
    assert res["within"]["ctx-0"] == 1.0
    assert res["floor"] == 1.0
    # 5 context が ⊥、3 context が za → 28 対中 15 対が TV 1、13 対が 0 → 中央値 1.0
    assert res["between_median"] == 1.0


def test_non_string_zone_is_not_computed(tmp_path, monkeypatch) -> None:
    out = run_synthetic(tmp_path, monkeypatch, rows(lambda _c, _x, _i: 3))
    assert out["status"] == "not_computed"


def test_prereg_hash_is_observed(tmp_path, monkeypatch) -> None:
    out = run_synthetic(tmp_path, monkeypatch, rows(lambda _c, ctx, _i: f"z{ctx}"))
    assert out["prereg_sha256"] == hashlib.sha256(b"frozen\n").hexdigest()


def test_bank_hash_constant_is_in_prereg_text() -> None:
    """照合相手の bank sha256 は凍結 prereg §7 の本文に書かれた値 (実ファイルを読む)."""
    root = Path(__file__).resolve().parents[2]
    text = (root / mod.PREREG_REL).read_text(encoding="utf-8")
    section7 = text[text.index("## 7.") : text.index("## 8.")]
    assert f"`{mod.BANK_SHA256_PREREG}`" in section7

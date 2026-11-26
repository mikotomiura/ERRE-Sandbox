"""記録 → 単位の値 (``benchmark_stage2_units``) の test.

- 凍結の集計関数 (r を [0, R) に付け替え) と、単位の値が一致する
  (G・O_time は単位ごと、v2・v3 は replicate ごと)。
- Codex r1 H2: 単位は明示 key で整列する。非対称な合成記録で、
  key ごとの (t, f, n)・単位の位置・
  ``stats.strata`` の項目・``stats.half_labels`` の半分を確かめる。
"""

from __future__ import annotations

import random

import numpy as np
import pytest
from scripts import benchmark_stage2_plan as pl
from scripts import benchmark_stage2_stats as st
from scripts import benchmark_stage2_units as un
from scripts import generalization_probe_battery as gbat
from scripts import generalization_probe_scorer as gsc
from scripts import o_time_probe_battery as obat
from scripts import o_time_probe_scorer as osc
from scripts import skill_experience_battery as v3bat
from scripts import skill_experience_scorer as v3sc
from scripts import skill_lever_battery as v2bat
from scripts import skill_lever_scorer as v2sc


def _vocab(battery: str) -> list[str | None]:
    if battery in ("v2", "v3"):
        return [*v2bat.ACTIONS, None]
    if battery == "G":
        return [*gbat.ACTIONS, None]
    return [*obat.ACTIONS, None]


def _random_choices(battery: str, calls: list[pl.CallSpec], seed: int) -> dict:  # type: ignore[type-arg]
    rng = random.Random(seed)
    vocab = _vocab(battery)
    out = {}
    for c in calls:
        key = (
            (c.arm, c.encoding, c.replicate, c.probe_id, c.k)
            if battery == "O_time"
            else (c.arm, c.replicate, c.probe_id, c.k)
        )
        out[key] = rng.choice(vocab)
    return out


def _remap(choices: dict, r0: int, battery: str) -> dict:  # type: ignore[type-arg]
    """集計用の写し: r を [0, R) に付け替え (添字だけ)."""
    out = {}
    for key, v in choices.items():
        if battery == "O_time":
            arm, enc, r, pid, k = key
            out[(arm, enc, r - r0, pid, k)] = v
        else:
            arm, r, pid, k = key
            out[(arm, r - r0, pid, k)] = v
    return out


def _lever(battery: str) -> list[pl.CallSpec]:
    return [c for c in pl.pilot_calls(battery) if c.purpose == pl.P_LEVER]


# ------------------------------------------------------------ 凍結の集計との一致


def test_v2_units_match_frozen_per_replicate() -> None:
    rs = pl.pilot_lever_r("v2")
    ch = _random_choices("v2", _lever("v2"), 1)
    vals = un.unit_values(un.unit_counts("v2", ch, rs))
    grouped: dict[tuple[str, int, str], list[str | None]] = {}
    for (arm, r, pid, _k), v in sorted(
        _remap(ch, rs[0], "v2").items(), key=lambda x: x[0][3]
    ):
        grouped.setdefault((arm, r, pid), []).append(v)
    s = v2sc.component_scores(grouped, len(rs))
    d = v2sc.family_units(s)  # (2R,): 族 A の r、族 B の r
    per_rep = (d[: len(rs)] + d[len(rs) :]) / 2.0
    np.testing.assert_allclose(
        vals.reshape(len(rs), -1).mean(axis=1), per_rep, atol=1e-12
    )
    assert vals.mean() == pytest.approx(d.mean(), abs=1e-12)


def test_v3_units_match_frozen_per_replicate() -> None:
    rs = pl.pilot_lever_r("v3")
    ch = _random_choices("v3", _lever("v3"), 2)
    vals = un.unit_values(un.unit_counts("v3", ch, rs))
    grouped: dict[tuple[str, int, str], list[str | None]] = {}
    for (arm, r, pid, _k), v in sorted(
        _remap(ch, rs[0], "v3").items(), key=lambda x: x[0][3]
    ):
        grouped.setdefault((arm, r, pid), []).append(v)
    s = v3sc.component_scores(grouped, v3bat.JUDGE_ARMS, len(rs))
    d = v2sc.family_units(s)
    per_rep = (d[: len(rs)] + d[len(rs) :]) / 2.0
    np.testing.assert_allclose(
        vals.reshape(len(rs), -1).mean(axis=1), per_rep, atol=1e-12
    )


def test_g_units_match_frozen_unit_by_unit() -> None:
    rs = pl.pilot_lever_r("G")
    ch = _random_choices("G", _lever("G"), 3)
    vals = un.unit_values(un.unit_counts("G", ch, rs))
    grouped = {
        (arm, r, pid): [v] for (arm, r, pid, _), v in _remap(ch, rs[0], "G").items()
    }
    frozen = gsc.unit_scores(gsc.arm_unit_scores(grouped, len(rs)), len(rs))
    np.testing.assert_allclose(vals, frozen, atol=1e-12)


def test_o_time_units_match_frozen_unit_by_unit() -> None:
    rs = pl.pilot_lever_r("O_time")
    ch = _random_choices("O_time", _lever("O_time"), 4)
    vals = un.unit_values(un.unit_counts("O_time", ch, rs))
    grouped = {
        (arm, enc, osc.room_index(pid), r): [v]
        for (arm, enc, r, pid, _), v in _remap(ch, rs[0], "O_time").items()
    }
    frozen = osc.unit_scores(osc.cell_scores(grouped, len(rs)), len(rs))
    np.testing.assert_allclose(vals, frozen, atol=1e-12)


# ------------------------------------------------------------ 明示 key (Codex r1 H2)


def _all_foil_or_other(battery: str, calls: list[pl.CallSpec]) -> dict:  # type: ignore[type-arg]
    """全セルを ⊥ にした記録."""
    return {
        (c.arm, c.encoding, c.replicate, c.probe_id, c.k)
        if battery == "O_time"
        else (c.arm, c.replicate, c.probe_id, c.k): None
        for c in calls
    }


def _target_of(battery: str, cell: un.Cell) -> str:
    """そのセルの target の label (凍結の category が w を返す選択)."""
    for lab in _vocab(battery):
        if lab is not None and un.category(battery, cell.key, lab) == "w":
            return lab
    raise AssertionError(cell)


@pytest.mark.parametrize("battery", st.BATTERIES)
def test_single_cell_lands_at_its_explicit_position(battery: str) -> None:
    """1 つの単位の 1 セルだけ target にすると、その単位の位置だけ (1, 0, n).

    順の取り違えを検出する。
    """
    rs = pl.pilot_lever_r(battery)
    ids = un.unit_ids(battery, rs)
    rng = random.Random(7)
    for _ in range(5):
        pos = rng.randrange(len(ids))
        uid = ids[pos]
        cell = un.unit_cells(battery, uid)[rng.randrange(un.CELLS_PER_UNIT[battery])]
        ch = _all_foil_or_other(battery, _lever(battery))
        ch[cell.key] = _target_of(battery, cell)
        counts = un.unit_counts(battery, ch, rs)
        hit = np.flatnonzero(counts[:, 0])
        assert hit.tolist() == [pos]
        assert counts[pos].tolist() == [1, 0, un.CELLS_PER_UNIT[battery]]
        # 位置 → (r, 項目) の写像は stats の層・半分と同じ
        upr = un.UNITS_PER_REP[battery]
        r, a, b = uid
        assert pos // upr == r - rs[0]
        item = st.strata(st.SPECS[battery], rs)[pos] // st.SPECS[battery].cycle
        if battery in ("v2", "v3"):
            assert item == a  # probe
        elif battery == "G":
            assert item == a * gbat.N_TRIPLES + b
        else:
            assert item == a * obat.N_ROOMS + b


def test_units_share_seed_within_unit_and_differ_across() -> None:
    """単位 = seed を共有する呼び出しの組 (同じ seed の arm を別単位に割らない)."""
    for battery in st.BATTERIES:
        rs = pl.pilot_lever_r(battery)
        seed_of = {
            (c.arm, c.encoding, c.replicate, c.probe_id, c.k)
            if battery == "O_time"
            else (c.arm, c.replicate, c.probe_id, c.k): c.seed
            for c in _lever(battery)
        }
        seen: dict[int, int] = {}
        for n, uid in enumerate(un.unit_ids(battery, rs)):
            seeds = {seed_of[c.key] for c in un.unit_cells(battery, uid)}
            assert len(seeds) == 1, (battery, uid)
            s = seeds.pop()
            if battery != "G":
                assert s not in seen, (battery, uid)
            seen.setdefault(s, n)
        # G はつ組の 3 probe が seed を共有する (単位の中)。単位の数 = seed の数
        assert len(seen) == len(un.unit_ids(battery, rs))


def test_half_labels_follow_explicit_r() -> None:
    rs = pl.main_r("v2", 16)
    halves = st.half_labels(st.SPECS["v2"], rs)
    ids = un.unit_ids("v2", rs)
    for h, (r, _, _) in zip(halves, ids, strict=True):
        assert h == ((r - rs[0]) // 4) % 2


def test_missing_cell_is_not_bottom() -> None:
    rs = pl.pilot_lever_r("O_time")
    ch = _random_choices("O_time", _lever("O_time"), 5)
    ch.pop(next(iter(ch)))
    with pytest.raises(un.MissingCellError):
        un.unit_counts("O_time", ch, rs)


# ------------------------------------------------------------ ⊥ の数・6 分類・q と r


def test_bot_counts_shapes_and_values() -> None:
    ch = _random_choices("v2", list(pl.pilot_calls("v2")), 6)
    counts, n = un.bot_counts("v2", ch, pl.pilot_lever_r("v2"))
    assert len(counts) == 5
    assert n == 720
    want = [
        sum(v is None for (a, *_), v in ch.items() if a == arm)
        for arm in v2bat.ALL_ARMS
    ]
    assert list(counts) == want
    g = _random_choices("G", list(pl.pilot_calls("G")), 7)
    gc, gn = un.bot_counts("G", g, pl.pilot_lever_r("G"))
    assert len(gc) == 4
    assert gn == 288
    o = _random_choices("O_time", list(pl.pilot_calls("O_time")), 8)
    oc, on = un.bot_counts("O_time", o, pl.pilot_lever_r("O_time"))
    assert len(oc) == 4
    assert on == 144
    v3 = _random_choices("v3", list(pl.pilot_calls("v3")), 9)
    cc, cn = un.bot_counts("v3", v3, pl.pilot_lever_r("v3"), v3bat.CONTROL_ARMS)
    assert len(cc) == 4
    assert cn == 360


def test_six_classes_and_q_r() -> None:
    rs = pl.pilot_lever_r("G")
    ch = _random_choices("G", _lever("G"), 10)
    missing = frozenset([next(iter(ch))])
    six = un.six_classes("G", ch, rs, missing)
    assert sum(sum(row.values()) for row in six.values()) == len(_lever("G"))
    assert sum(row["missing"] for row in six.values()) == 1
    counts = un.unit_counts("G", ch, rs)
    q, r = un.q_and_r(counts)
    c = un.unit_values(counts).mean()
    assert r is not None
    assert c == pytest.approx(q * (2 * r - 1), abs=1e-12)

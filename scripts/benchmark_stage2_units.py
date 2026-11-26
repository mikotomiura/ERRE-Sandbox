"""判別性 gate 段 2 — 記録 (照合済みの parse 結果) → 独立な単位の値・(target, foil, 全セル)・⊥ の数・6 分類.

規則の SSOT は ``experiments/20261126-benchmark-stage2-discriminability/prereg.md`` §B・§D。

* セルの得点は各 battery の凍結の ``category`` で決める (target = +1、foil = −1、それ以外 = 0)。
* 独立な単位 (§D、DU-12) と単位の中のセル (Codex r1 H2: 明示 key で整列する):
  - v2・v3: (実 r, probe, k)。セル = 判定の 4 arm (v2 = lever、v3 = judge)。n = 4。
  - G: (実 r, 族, つ組)。セル = 族内の 2 arm × つ組の 3 probe。n = 6。
  - O_time: (実 r, 族, 部屋)。セル = 族内の 2 arm × 2 書き方。n = 4。
* 単位の順 = r が外側、1 replicate の中は ``benchmark_stage2_stats.strata`` の順
  (v2・v3 = probe 外・k 内、G = 族 × 8 + つ組、O_time = 族 × 6 + 部屋)。
* 単位の値 = (t − f) / n。各 battery の凍結の集計 (``component_scores``・``family_units`` ほか) の平均と一致する
  (等しい重み。test で r を [0, R) に付け替えた凍結の関数と結ぶ)。
* 入力は ``Choices`` = key → parse 結果 (None = ⊥)。key は v2・v3・G = (arm, r, probe_id, k)、
  O_time = (arm, encoding, r, probe_id, k)。欠けた key は ``MissingCellError`` (⊥ に畳まない)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from scripts import generalization_probe_battery as gbat
from scripts import generalization_probe_scorer as gsc
from scripts import o_time_probe_battery as obat
from scripts import o_time_probe_scorer as osc
from scripts import skill_experience_battery as v3bat
from scripts import skill_experience_scorer as v3sc
from scripts import skill_lever_battery as v2bat
from scripts import skill_lever_scorer as v2sc

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

Key = tuple[Any, ...]
Choices = dict[Key, str | None]

V2_K: Final[int] = 10  # 凍結の skill_lever_scorer.FROZEN_K
CELLS_PER_UNIT: Final[dict[str, int]] = {"v2": 4, "v3": 4, "G": 6, "O_time": 4}
UNITS_PER_REP: Final[dict[str, int]] = {"v2": 60, "v3": 30, "G": 16, "O_time": 12}
# 6 分類 (§B): target / foil / Ω 内の残り / Ω 外 / ⊥ / 通信の欠測
CLASSES: Final[tuple[str, ...]] = ("target", "foil", "other", "oov", "bot", "missing")
_CAT_TO_CLASS: Final[dict[str, str]] = {
    "w": "target",
    "foil": "foil",
    "other": "other",
    "oov": "oov",
    "bot": "bot",
}


class MissingCellError(KeyError):
    """単位を作るのに要る記録が無い (not_computed。⊥ に畳まない)."""


@dataclass(frozen=True)
class Cell:
    """単位の中の 1 セル: 記録の key と、採点に使う (凍結の) 引数."""

    key: Key
    arm: str  # 記録の腕名


def _k_count(battery: str) -> int:
    return V2_K if battery == "v2" else v3sc.FROZEN_K if battery == "v3" else 1


def unit_ids(battery: str, r_list: Sequence[int]) -> list[tuple[int, int, int]]:
    """単位の明示 id の列 (順 = §D の単位の順)。v2・v3 = (r, probe 番号, k)、G = (r, 族, つ組)、O_time = (r, 族, 部屋)."""
    if battery in ("v2", "v3"):
        return [
            (r, qi, k)
            for r in r_list
            for qi in range(len(v2bat.lever_probes()))
            for k in range(_k_count(battery))
        ]
    if battery == "G":
        return [
            (r, fi, j)
            for r in r_list
            for fi in range(len(gbat.FAMILIES))
            for j in range(gbat.N_TRIPLES)
        ]
    if battery == "O_time":
        return [
            (r, fi, i)
            for r in r_list
            for fi in range(len(obat.FAMILIES))
            for i in range(obat.N_ROOMS)
        ]
    msg = f"unknown battery {battery!r}"
    raise ValueError(msg)


def unit_cells(battery: str, uid: tuple[int, int, int]) -> list[Cell]:
    """単位の中のセル (seed を共有する呼び出し)."""
    r, a, b = uid
    if battery in ("v2", "v3"):
        pid = v2bat.lever_probes()[a].probe_id
        arms = v2bat.LEVER_ARMS if battery == "v2" else v3bat.JUDGE_ARMS
        return [Cell((arm, r, pid, b), arm) for arm in arms]
    if battery == "G":
        return [
            Cell((arm, r, p.probe_id, 0), arm)
            for p in gbat.triple_probes(b)
            for arm in gbat.FAMILIES[a]
        ]
    if battery == "O_time":
        unit = obat.Unit(a, b, r)
        pid = osc.probe_id(b)
        return [Cell((arm, enc, r, pid, 0), arm) for arm, enc in obat.unit_calls(unit)]
    msg = f"unknown battery {battery!r}"
    raise ValueError(msg)


_G_PROBES: Final[dict[str, gbat.Probe]] = {p.probe_id: p for p in gbat.probes()}
_V2_PROBES: Final[dict[str, v2bat.LeverProbe]] = {
    p.probe_id: p for p in v2bat.lever_probes()
}


def category(battery: str, cell_key: Key, choice: str | None) -> str:
    """凍結の ``category`` (w / foil / other / oov / bot)。腕名は lever (v3 は POINTS_AS) で."""
    if battery == "v2":
        arm, _, pid, _ = cell_key
        return v2sc.category(choice, _V2_PROBES[pid], arm)
    if battery == "v3":
        arm, _, pid, _ = cell_key
        return v2sc.category(choice, _V2_PROBES[pid], v3bat.POINTS_AS[arm])
    if battery == "G":
        arm, _, pid, _ = cell_key
        return gsc.category(choice, _G_PROBES[pid], arm)
    if battery == "O_time":
        arm, _, _, pid, _ = cell_key
        return osc.category(choice, arm, osc.room_index(pid))
    msg = f"unknown battery {battery!r}"
    raise ValueError(msg)


def _get(choices: Mapping[Key, str | None], key: Key) -> str | None:
    if key not in choices:
        raise MissingCellError(key)
    return choices[key]


def unit_counts(
    battery: str,
    choices: Mapping[Key, str | None],
    r_list: Sequence[int],
) -> np.ndarray:
    """(n_units, 3) の (target, foil, 全セル) の数。順 = ``unit_ids``."""
    out = []
    for uid in unit_ids(battery, r_list):
        t = f = n = 0
        for cell in unit_cells(battery, uid):
            cat = category(battery, cell.key, _get(choices, cell.key))
            t += cat == "w"
            f += cat == "foil"
            n += 1
        out.append((t, f, n))
    arr = np.array(out, dtype=int).reshape(-1, 3)
    if arr.size and not np.all(arr[:, 2] == CELLS_PER_UNIT[battery]):
        msg = "unit cell count differs from the registered value"
        raise ValueError(msg)
    return arr


def unit_values(counts: np.ndarray) -> np.ndarray:
    """(t − f) / n ∈ [−1, 1]."""
    c = np.asarray(counts, dtype=float)
    return (c[:, 0] - c[:, 1]) / c[:, 2]


# ------------------------------------------------------------ ⊥ の数 (資格・envelope)

# 判定と資格に使う arm の並び (stats.N_ARMS の順: v2 = ALL_ARMS (C0 が 5 本目)、v3・G = lever、O_time = LEVER_ARMS)
BOT_ARMS: Final[dict[str, tuple[str, ...]]] = {
    "v2": v2bat.ALL_ARMS,
    "v3": v3bat.JUDGE_ARMS,
    "G": gbat.LEVER_ARMS,
    "O_time": obat.LEVER_ARMS,
}


def arm_keys(battery: str, arm: str, r_list: Sequence[int]) -> list[Key]:
    """arm の全呼び出しの key (C0・L arm・masked・M0 の腕名でも同じ形)。G の masked は M_* を渡す."""
    if battery in ("v2", "v3"):
        return [
            (arm, r, p.probe_id, k)
            for r in r_list
            for p in v2bat.lever_probes()
            for k in range(_k_count(battery))
        ]
    if battery == "G":
        return [(arm, r, p.probe_id, 0) for r in r_list for p in gbat.probes()]
    if battery == "O_time":
        return [
            (arm, enc, r, osc.probe_id(i), 0)
            for r in r_list
            for i in range(obat.N_ROOMS)
            for enc in obat.ENCODINGS
        ]
    msg = f"unknown battery {battery!r}"
    raise ValueError(msg)


def bot_counts(
    battery: str,
    choices: Mapping[Key, str | None],
    r_list: Sequence[int],
    arms: Sequence[str] | None = None,
) -> tuple[tuple[int, ...], int]:
    """arm 別の ⊥ の数と arm あたりの呼び出しの数 (整数、``stats.parse_rule`` に渡す)."""
    arms = BOT_ARMS[battery] if arms is None else tuple(arms)
    counts = []
    n = None
    for arm in arms:
        keys = arm_keys(battery, arm, r_list)
        counts.append(sum(_get(choices, k) is None for k in keys))
        if n is None:
            n = len(keys)
        elif n != len(keys):
            msg = "arms differ in call count"
            raise ValueError(msg)
    return tuple(counts), int(n or 0)


# ------------------------------------------------------------ 6 分類・q・r (記述)


def lever_cells(battery: str, r_list: Sequence[int]) -> list[Cell]:
    return [c for uid in unit_ids(battery, r_list) for c in unit_cells(battery, uid)]


def six_classes(
    battery: str,
    choices: Mapping[Key, str | None],
    r_list: Sequence[int],
    transport_missing: frozenset[Key] = frozenset(),
) -> dict[str, dict[str, int]]:
    """arm ごとの 6 分類の数。``transport_missing`` の key は通信の欠測 (choices に無くてよい)."""
    out: dict[str, dict[str, int]] = {}
    for cell in lever_cells(battery, r_list):
        row = out.setdefault(cell.arm, dict.fromkeys(CLASSES, 0))
        if cell.key in transport_missing:
            row["missing"] += 1
            continue
        cat = category(battery, cell.key, _get(choices, cell.key))
        row[_CAT_TO_CLASS[cat]] += 1
    return out


def q_and_r(counts: np.ndarray) -> tuple[float, float | None]:
    """q = target か foil を選んだ率、r = その中の target の率 (C = q(2r − 1))。t + f = 0 なら r は None."""
    c = np.asarray(counts, dtype=int)
    t, f, n = int(c[:, 0].sum()), int(c[:, 1].sum()), int(c[:, 2].sum())
    q = (t + f) / n
    return q, (t / (t + f) if t + f else None)

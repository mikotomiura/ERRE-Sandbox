"""Fixtures for tests/test_body_walk.

探索を身体側へ (b) 歩行 → decode 条件の較正 pilot prereg。

scripts を import できるよう repository root を ``sys.path`` に置く
(``tests/test_closed_loop_v5`` と同じ型)。

合成 run は ``body_walk_sim.synthetic_records``
(凍結 plan を上から呼び、状態を R1 で描いて方策に渡し、parse した
行動で状態を更新する) を使う。実モデルは使わない。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts import body_walk_battery as bat  # noqa: E402
from scripts import body_walk_pilot_scorer as ps  # noqa: E402
from scripts import body_walk_sim as sim  # noqa: E402
from scripts import closed_loop_v5_select as v5sel  # noqa: E402

if TYPE_CHECKING:
    from scripts import closed_loop_battery as v4


def behaviour(**kw: Any) -> sim.Behaviour:
    base: dict[str, Any] = {
        "lam_dev": 0.4,
        "base": sim.base_table(v5sel.V4_LOOP_BASE),
        "bot": 0.0,
        "oov": 0.0,
        "s_same": 0.5,
        "s_changed": 0.5,
    }
    base.update(kw)
    return sim.Behaviour(**base)


def first_option(
    _key: bat.PilotKey, _st: v4.State, opts: tuple[str, ...]
) -> str | None:
    """表示先頭を選ぶ (状態を読まない)."""
    return opts[0]


def synth(**kw: Any) -> list[ps.Record]:
    beh = kw.pop("beh", None) or behaviour()
    return [ps.record_from_json(x) for x in sim.synthetic_records(beh, **kw)]


def to_lines(records: list[ps.Record]) -> list[str]:
    return [json.dumps(r.__dict__, ensure_ascii=True, sort_keys=True) for r in records]


def meta_text() -> str:
    return json.dumps(bat.request_meta_walk())

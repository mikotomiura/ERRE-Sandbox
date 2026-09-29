"""Fixtures for tests/test_closed_loop_v5 (閉ループ v5 較正 pilot prereg).

scripts を import できるよう repository root を ``sys.path`` に置く
(``tests/test_closed_loop`` と同じ型)。

``synth`` は pilot の driver 仕様 (prereg §2) を写した合成記録の生成器:
凍結 plan の順に呼び、状態を軸の renderer で描いて方針に渡し、
parse した行動で状態を更新する。実モデルは使わない。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts import closed_loop_battery as v4  # noqa: E402
from scripts import closed_loop_v5_battery as bat  # noqa: E402
from scripts import closed_loop_v5_pilot_scorer as ps  # noqa: E402
from scripts.skill_lever_scorer import (  # noqa: E402
    messages_sha256,
    parse_choice,
    request_meta,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    Policy = Callable[[bat.PilotKey, v4.State, tuple[str, ...], str], str | None]


def synth(policy: Policy, *, stop_after: int | None = None) -> list[ps.Record]:
    """凍結 plan を上から呼ぶ合成 run.

    policy(key, 状態, 表示中の選択肢, user 文) → raw。
    """
    states: dict[tuple[str, str, int], v4.State] = {}
    out: list[ps.Record] = []
    for i, key in enumerate(bat.pilot_plan()):
        if stop_after is not None and i >= stop_after:
            break
        ck = (key.axis, key.world, key.replicate)
        st = states.get(ck, v4.EMPTY_STATE)
        msgs = bat.loop_messages(st, key.world, key.replicate, key.step, key.axis)
        opts = bat.dev_options(key.axis, key.replicate, key.step)
        raw = policy(key, st, opts, msgs[1]["content"])
        parsed = None if raw is None else parse_choice(raw)
        out.append(
            ps.Record(
                call_index=i,
                axis=key.axis,
                world=key.world,
                replicate=key.replicate,
                step=key.step,
                seed=bat.pilot_seed(key.replicate, key.step),
                prompt_sha256=messages_sha256(msgs),
                raw=raw,
                parsed=parsed,
            )
        )
        states[ck] = v4.update(
            st, key.world, v4.loop_signature(key.replicate, key.step), parsed
        )
    return out


def to_lines(records: list[ps.Record]) -> list[str]:
    return [json.dumps(r.__dict__, ensure_ascii=True, sort_keys=True) for r in records]


def meta_text() -> str:
    return json.dumps(request_meta())


def first_option(
    _key: bat.PilotKey, _st: v4.State, opts: tuple[str, ...], _text: str
) -> str:
    """表示先頭を選ぶ (状態を読まない)."""
    return opts[0]

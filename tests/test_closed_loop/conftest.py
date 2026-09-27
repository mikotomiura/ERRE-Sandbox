"""Fixtures for tests/test_closed_loop (prereg v4).

The closed-loop pilot scorer / battery / sim live in ``scripts/closed_loop_*.py``; put
the
repository root on ``sys.path`` so they are importable as
``scripts.closed_loop_scorer`` etc.
(same pattern as ``tests/test_skill_experience/conftest.py``).

``synth`` は driver の仕様 (prereg v4 §2.4 / §4) を写した合成記録の生成器: 凍結 plan
の順に呼び、
ループ段は状態を renderer で描いて方針に渡し、parse した行動で状態を更新する。
実モデルは使わない。
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts import closed_loop_battery as bat  # noqa: E402
from scripts import closed_loop_scorer as sc  # noqa: E402
from scripts import skill_lever_battery as v2  # noqa: E402
from scripts.skill_lever_scorer import messages_sha256, parse_choice  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Callable

    Policy = Callable[[bat.PlanKey, bat.State, tuple[str, ...]], str | None]


def options_for(key: bat.PlanKey) -> tuple[str, ...]:
    if key.step is not None:
        return bat.dev_options(key.replicate, key.step)
    assert key.probe_id is not None
    return v2.layout(key.replicate).option_order[key.probe_id]


def qidx(probe_id: str) -> int:
    return [p.probe_id for p in v2.lever_probes()].index(probe_id)


def synth(
    policy: Policy,
    *,
    renderer: str = sc.FROZEN_RENDERER,
    stop_after: int | None = None,
) -> list[sc.Record]:
    """凍結 plan を上から呼ぶ合成 run。stop_after 件で打ち切る (接頭辞)."""
    states: dict[tuple[str, int], bat.State] = {}
    raws: dict[bat.PlanKey, str | None] = {}
    out: list[sc.Record] = []
    for i, key in enumerate(sc.frozen_plan()):
        if stop_after is not None and i >= stop_after:
            break
        st = states.get((key.world, key.replicate), bat.EMPTY_STATE)
        if key.phase == bat.PHASE_C0:
            assert key.probe_id is not None
            msgs = bat.c0_messages(key.replicate, qidx(key.probe_id))
            raw = policy(key, bat.EMPTY_STATE, options_for(key))
        elif key.phase == bat.PHASE_LOOP:
            assert key.step is not None
            msgs = bat.loop_messages(st, key.world, key.replicate, key.step, renderer)
            raw = policy(key, st, options_for(key))
        elif key.phase == bat.PHASE_PROBE:
            assert key.probe_id is not None
            msgs = bat.probe_messages(
                st, key.world, key.replicate, qidx(key.probe_id), renderer
            )
            raw = policy(key, st, options_for(key))
        else:
            assert key.of is not None
            target = next(
                r for r in out if r.key() == dataclasses.replace(key.of, of=None)
            )
            out.append(
                sc.Record(
                    i,
                    key.phase,
                    key.world,
                    key.replicate,
                    key.step,
                    key.probe_id,
                    key.k,
                    target.seed,
                    target.prompt_sha256,
                    raws[key.of],
                    target.parsed,
                )
            )
            continue
        parsed = None if raw is None else parse_choice(raw)
        raws[dataclasses.replace(key, of=None)] = raw
        out.append(
            sc.Record(
                i,
                key.phase,
                key.world,
                key.replicate,
                key.step,
                key.probe_id,
                key.k,
                sc.expected_seed(key),
                messages_sha256(msgs),
                raw,
                parsed,
            )
        )
        if key.phase == bat.PHASE_LOOP:
            assert key.step is not None
            states[(key.world, key.replicate)] = bat.update(
                st, key.world, bat.loop_signature(key.replicate, key.step), parsed
            )
    return out


def to_lines(records: list[sc.Record]) -> list[str]:
    return [json.dumps(dataclasses.asdict(r), ensure_ascii=False) for r in records]


@pytest.fixture
def cert(tmp_path: Path) -> Path:
    path = tmp_path / "cert.json"
    shas = {
        name: hashlib.sha256(p.read_bytes()).hexdigest()
        for name, p in sc.certified_targets().items()
    }
    path.write_text(
        json.dumps({"target_sha256": shas, "all_killed": True}), encoding="utf-8"
    )
    return path

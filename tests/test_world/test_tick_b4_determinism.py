"""§B4 Plane1 侵入経路 sorted 化の determinism 回帰 (M13-M2 Layer1, Issue I1).

FROZEN ADR `.steering/20260711-m13-m2-impl-design/design-final.md` §M4.3 /
DA-M2IMPL-4 が flag した ``world/tick.py`` の非 sorted 反復 (separation /
proximity の ``combinations(self._agents.values(), 2)`` + mutation loop /
temporal / affordance の裸 ``values()``) を sorted 化した construction-quality
の determinism 硬化を検証する。**checksum は再現性であって metric/floor/
verdict ではない** (loop.py docstring の scope guard 継承、measurement 非再入)。

Tests (AC↔test, issue 001):
* ``test_tick_n1_byte_invariant`` (I1-G1) — N=1 では ``combinations`` が空
  集合になり、単一 agent の物理積分は反復戦略 (``dict.values()`` vs
  ``sorted(self._agents)``) に依存しない純関数のはずなので、
  ``WorldRuntime`` 経由の trace と、同じ ``step_kinematics`` primitive を
  直接呼んだ独立導出 trace の ``ecl_trace_checksum`` が完全一致する。
* ``test_tick_separation_registration_order_invariant`` (I1-G2) — N=3 の
  chain-push シナリオで agent 登録順を permutation しても、separation 適用後
  の全 position が同一。
* ``test_tick_proximity_pair_canonical`` (I1-G3) — sorted-pair 反復
  (``combinations(_sorted_runtimes(), 2)``) は常に
  ``rt_a.agent_id < rt_b.agent_id`` (sorted_pair=(min_id,max_id)) を満たし、
  登録順に非依存。
* ``test_tick_no_bare_values_iteration_on_checksum_path`` (I1-G4) — §B4 が
  flag した 5 メソッド (``_on_physics_tick`` / ``_apply_separation_force`` /
  ``_fire_proximity_events`` / ``_fire_affordance_events`` /
  ``_fire_temporal_events``) の AST に裸の ``self._agents.values()`` 呼び出し
  が無いことを機械保証する (discovery guard, §M4.3 / §M8 継承)。
  ``_on_cognition_tick`` (live wall-clock ``asyncio.gather``) は issue 001
  Scope Out により対象外 — record-mode 逐次化は society.py 側 (I2) の責務。
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import TYPE_CHECKING, Any

from erre_sandbox.integration.embodied.loop import EclTraceRow, ecl_trace_checksum
from erre_sandbox.world import ManualClock, WorldRuntime
from erre_sandbox.world import tick as tick_module
from erre_sandbox.world.physics import Kinematics, step_kinematics

if TYPE_CHECKING:
    from collections.abc import Callable

_PHYSICS_DT = 1.0 / 30.0


def _empty_trace_row(**overrides: Any) -> EclTraceRow:
    base: dict[str, Any] = {
        "run_id": "b4-pin",
        "agent_id": "solo",
        "physics_tick_index": 0,
        "agent_tick": 0,
        "order_slot": 0,
        "x": 0.0,
        "y": 0.0,
        "z": 0.0,
        "yaw": 0.0,
        "pitch": 0.0,
        "zone": "study",
        "resolved_from": None,
        "move_centroid": None,
        "move_provenance": None,
        "move_jitter": None,
        "move_pre_clamp": None,
        "move_post_clamp": None,
        "move_clamp_fired": None,
    }
    base.update(overrides)
    return EclTraceRow(**base)


async def test_tick_n1_byte_invariant(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    """I1-G1: N=1 の ecl_trace_checksum は sorted 化の前後で不変。

    ``combinations`` は N=1 で常に空集合 (separation/proximity は一切走ら
    ない)。残る唯一の反復は ``_on_physics_tick`` の mutation loop で、これも
    per-agent 独立な純関数 (``step_kinematics``) なので、``dict.values()``
    と ``sorted(self._agents)`` のどちらで反復しても単一 agent の出力は
    数学的に同一になるはずである。本 test はこの主張を「実装からの独立導出」
    (同じ公開 primitive ``step_kinematics`` を ``WorldRuntime`` の外で直接
    呼ぶ) と比較することで検証する。
    """
    captured: list[EclTraceRow] = []

    def sink(
        agent_id: str,
        idx: int,
        x: float,
        y: float,
        z: float,
        yaw: float,
        pitch: float,
        zone: Any,
    ) -> None:
        captured.append(
            _empty_trace_row(
                agent_id=agent_id,
                physics_tick_index=idx,
                x=x,
                y=y,
                z=z,
                yaw=yaw,
                pitch=pitch,
                zone=zone,
            ),
        )

    clock = ManualClock(start=0.0)
    runtime = WorldRuntime(
        cycle=object(),  # type: ignore[arg-type]
        clock=clock,
        physics_hz=30.0,
        ecl_trace_sink=sink,
    )
    state = make_agent_state(
        agent_id="solo",
        position={"x": 1.0, "y": 0.0, "z": 2.0, "zone": "study"},
    )
    runtime.register_agent(state, make_persona_spec())

    for _ in range(5):
        await runtime._on_physics_tick()

    actual_checksum = ecl_trace_checksum(captured)

    # Independent re-derivation: no WorldRuntime, no dict iteration at all —
    # just the same public step_kinematics primitive called directly. The
    # solo agent has no MoveMsg destination (register_agent seeds
    # Kinematics(destination=None)), so position never advances; the
    # trace is a constant row repeated at each physics_tick_index.
    kin = Kinematics(position=state.position)
    expected_rows: list[EclTraceRow] = []
    for idx in range(5):
        new_pos, _zone_changed = step_kinematics(kin, _PHYSICS_DT)
        expected_rows.append(
            _empty_trace_row(
                agent_id="solo",
                physics_tick_index=idx,
                x=new_pos.x,
                y=new_pos.y,
                z=new_pos.z,
                yaw=new_pos.yaw,
                pitch=new_pos.pitch,
                zone=new_pos.zone,
            ),
        )
    expected_checksum = ecl_trace_checksum(expected_rows)

    assert actual_checksum == expected_checksum


def _register_three_agent_chain(
    runtime: WorldRuntime,
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    order: list[str],
) -> None:
    """Register a 3-agent chain-push fixture in the given registration order.

    All three positions (x=0.0/0.5/1.0) sit within the default 1.5 m
    ``separation_radius_m`` of every neighbour, so every pair fires the
    separation nudge — the exact 3+-agent chain-push scenario §M4.3 flags
    as registration-order-dependent under the old non-sorted
    ``combinations(self._agents.values(), 2)``.
    """
    specs = {
        "a": (
            make_agent_state(agent_id="a", position={"x": 0.0, "z": 0.0}),
            make_persona_spec(),
        ),
        "b": (
            make_agent_state(
                agent_id="b",
                persona_id="nietzsche",
                position={"x": 0.5, "z": 0.0},
            ),
            make_persona_spec(persona_id="nietzsche"),
        ),
        "c": (
            make_agent_state(
                agent_id="c",
                persona_id="rikyu",
                position={"x": 1.0, "z": 0.0},
            ),
            make_persona_spec(persona_id="rikyu"),
        ),
    }
    for agent_id in order:
        state, persona = specs[agent_id]
        runtime.register_agent(state, persona)


def test_tick_separation_registration_order_invariant(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    """I1-G2: chain-push の結果 position は agent 登録順に非依存 (§M4.3 point 1)."""
    orders = [
        ["a", "b", "c"],
        ["c", "b", "a"],
        ["b", "a", "c"],
        ["c", "a", "b"],
    ]
    results: list[dict[str, tuple[float, float]]] = []
    for order in orders:
        runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
        _register_three_agent_chain(runtime, make_agent_state, make_persona_spec, order)
        runtime._apply_separation_force()
        results.append(
            {
                agent_id: (rt.state.position.x, rt.state.position.z)
                for agent_id, rt in sorted(runtime._agents.items())
            },
        )

    first = results[0]
    for other in results[1:]:
        assert other == first


def test_tick_proximity_pair_canonical(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    """I1-G3: sorted-pair 反復は常に rt_a.agent_id < rt_b.agent_id (Codex HIGH-3).

    ``combinations`` over a list pre-sorted by ``agent_id`` yields every pair
    with the smaller id first — this *is* the ``sorted_pair=(min_id,max_id)``
    canonical form (registration/dict-insertion order never leaks into which
    runtime plays "a" vs "b"). Verified for both separation's and proximity's
    shared ``_sorted_runtimes()`` source, and shown independent of
    registration order.
    """
    from itertools import combinations

    def build(order: list[str]) -> WorldRuntime:
        runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
        specs = {
            "z": make_agent_state(agent_id="z", position={"x": 0.0, "z": 0.0}),
            "a": make_agent_state(
                agent_id="a",
                persona_id="nietzsche",
                position={"x": 1.0, "z": 0.0},
            ),
            "m": make_agent_state(
                agent_id="m",
                persona_id="rikyu",
                position={"x": 2.0, "z": 0.0},
            ),
        }
        personas = {
            "z": make_persona_spec(),
            "a": make_persona_spec(persona_id="nietzsche"),
            "m": make_persona_spec(persona_id="rikyu"),
        }
        for agent_id in order:
            runtime.register_agent(specs[agent_id], personas[agent_id])
        return runtime

    forward = build(["z", "a", "m"])
    reversed_order = build(["m", "a", "z"])

    for runtime in (forward, reversed_order):
        pairs = list(combinations(runtime._sorted_runtimes(), 2))
        pair_ids = [(rt_a.agent_id, rt_b.agent_id) for rt_a, rt_b in pairs]
        assert pair_ids == [("a", "m"), ("a", "z"), ("m", "z")]
        for rt_a, rt_b in pairs:
            assert rt_a.agent_id < rt_b.agent_id


_CHECKSUM_PATH_METHODS = (
    "_on_physics_tick",
    "_apply_separation_force",
    "_fire_proximity_events",
    "_fire_affordance_events",
    "_fire_temporal_events",
)


def _is_bare_agents_values_call(node: ast.AST) -> bool:
    """True when ``node`` is exactly ``self._agents.values()`` (bare, non-sorted)."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr == "values"):
        return False
    target = func.value
    return (
        isinstance(target, ast.Attribute)
        and target.attr == "_agents"
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
    )


def test_tick_no_bare_values_iteration_on_checksum_path() -> None:
    """I1-G4: §B4 の checksum 影響経路に裸の非 sorted values() が無い (discovery guard).

    Scope is the exact five methods issue 001 names as the §B4 Plane1
    intrusion points. ``_on_cognition_tick`` (the live wall-clock
    ``asyncio.gather`` fan-out at L1432 in the impl-design ADR's line
    numbering) is explicitly out of scope for this issue — it is inherently
    non-deterministic and untouched; record-mode sequential scheduling is
    society.py's responsibility (Issue I2). Canonicalisation via
    ``sorted(self._agents)`` (dict-key iteration, no ``.values()`` at all) is
    the replacement pattern and is allowed by construction — this guard only
    forbids the literal ``self._agents.values()`` call shape.
    """
    source_path = inspect.getsourcefile(tick_module)
    assert source_path is not None
    source = Path(source_path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=source_path)

    class_node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "WorldRuntime"
    )

    checked = set()
    for method_node in ast.walk(class_node):
        if (
            isinstance(method_node, ast.AsyncFunctionDef | ast.FunctionDef)
            and method_node.name in _CHECKSUM_PATH_METHODS
        ):
            checked.add(method_node.name)
            offenders = [
                n for n in ast.walk(method_node) if _is_bare_agents_values_call(n)
            ]
            assert not offenders, (
                f"{method_node.name} contains a bare self._agents.values() call "
                "— must go through sorted(self._agents) / _sorted_runtimes()"
            )

    assert checked == set(_CHECKSUM_PATH_METHODS), (
        f"expected to find all of {_CHECKSUM_PATH_METHODS} on WorldRuntime, "
        f"found {checked}"
    )

# Tasklist — M7 Slice γ (v2 — adopted 2026-04-25 after /reimagine)

> Plan file: `C:\Users\johnd\.claude\plans\zany-gathering-teapot.md`
> Repo-resident copy: `design-final.md` (本ディレクトリ内)
> v1 scaffold は意図的に放棄、v2 を /reimagine + 比較で採用。

## Commit 1: schemas 拡張 + WorldLayoutMsg + version bump (1.5h)  ✅

- [x] `src/erre_sandbox/schemas.py` §7 に `ZoneLayout`, `PropLayout`, `WorldLayoutMsg` 追加
- [x] `ReasoningTrace` に `observed_objects: list[str]` / `nearby_agents: list[str]` /
      `retrieved_memories: list[str]` を追加 (default_factory)
- [x] `SCHEMA_VERSION` を **`0.6.0-m7g`** に bump
- [x] `__all__` に新規型を追加
- [x] `ControlEnvelope` discriminated union に `WorldLayoutMsg` を追加
- [x] `fixtures/control_envelope/world_layout.json` golden 追加 (+ 既存 12 件の version bump)
- [x] `tests/test_schemas_m7g.py` 新設 (WorldLayoutMsg / 拡張 ReasoningTrace / fixture round-trip)
      `tests/test_schemas.py::test_schema_version_is_current_milestone` を 0.6.0-m7g に更新
- [x] `tests/test_envelope_kind_sync.py::_EXPECTED_KINDS` に `world_layout` 追加
- [x] `tests/test_envelope_fixtures.py` の shared invariant に world_layout (tick=0) 例外
- [x] `personas/{kant,nietzsche,rikyu}.yaml` の schema_version bump
- [x] `tests/schema_golden/*.schema.json` 再生成
- [x] `godot_project/scripts/EnvelopeRouter.gd` に `world_layout` match arm 最小追加
      (full BoundaryLayer consumer は Commit 4)
- [x] `.steering/20260425-m7-slice-gamma/evidence/_stream_probe_m7g.py` 新設
      (β probe は frozen evidence のまま温存)
- [x] `uv run pytest tests/` 全パス + `ruff check/format` 私の変更分 clean
- [x] commit: `feat(schemas): m7-γ ReasoningTrace+WorldLayoutMsg, bump 0.6.0-m7g`

## Commit 2: cognition (relational + reflection + trace) (3h)  ✅

- [x] `src/erre_sandbox/cognition/relational.py` 新設
      `compute_affinity_delta(turn, recent_transcript, persona) -> float` 純関数
      (γ 初期実装は constant `+0.02`、clamp [-1.0, 1.0]) +
      `apply_affinity` / `clamp_affinity_delta` ヘルパ
- [x] `tests/test_cognition/test_relational.py` 追加 (境界値 / clamp / signature
      / 6-step dialog budget の確認、計 15 件)
- [x] `src/erre_sandbox/bootstrap.py` の `turn_sink` を chain 化、
      `_make_relational_sink` factory で複雑度を抑制、
      relational_memory INSERT + 双方向 `RelationshipBond.affinity` 更新
- [x] `WorldRuntime.apply_affinity_delta(agent_id, other_agent_id, delta, *, tick)`
      新設 — bond mutation を model_copy 経由で実施、未登録 agent は no-op
- [x] `src/erre_sandbox/cognition/reflection.py::build_reflection_messages` に
      `recent_dialog_turns: Sequence[DialogTurnMsg] = ()` 引数追加、
      Reflector.maybe_reflect / _execute も同引数を伝搬
- [x] `src/erre_sandbox/cognition/cycle.py::_fetch_recent_peer_turns` 新設、
      reflection 呼び出し直前に他 persona の dialog_turn 上限 3 件を取得して渡す
- [x] ReasoningTrace 生成位置 (`_build_envelopes`) を拡張:
      observed_objects ← AffordanceEvent salience top-3、
      nearby_agents ← ProximityEvent.crossing="enter" max 2、
      retrieved_memories ← memories[:3].entry.id、
      `decision` に `f"affinity={bond.affinity:+.2f} with {other_agent_id}"` を suffix
- [x] `tests/test_cognition/test_reflection_envelope.py::_StubReflector` の
      signature を新引数対応 (バックワード互換テストの修正)
- [x] `uv run pytest tests/` 全パス (855) + `ruff check/format` 私の変更分 clean
- [x] commit: `feat(cognition): m7-γ affinity hook + reflection peer turns + trace`

## Commit 3: gateway WorldLayoutMsg on-connect (1h)  ✅

- [x] `WorldRuntime.layout_snapshot()` (Commit 2 で先行実装、γ 用 zones+props 構築)
- [x] `_RuntimeLike` Protocol に `layout_snapshot` を追加
- [x] `_NullRuntime` に空 layout を返す stub を追加
- [x] `_SERVER_CAPABILITIES` に `world_layout` (および欠けていた M6 の
      `reasoning_trace` / `reflection_event`) を追加
- [x] `gateway.ws_observe` の `registry.add(...)` 直前で
      `await _send(ws, runtime.layout_snapshot())` を実行
- [x] `tests/test_integration/test_world_layout_msg.py` 新設 (5 tests)
      — connect → world_layout 受信 / capabilities / null runtime / golden fixture /
      WorldRuntime.layout_snapshot 内容
- [x] `tests/test_integration/conftest.py::MockRuntime` に `layout_snapshot` stub 追加
- [x] `tests/test_integration/_ws_helpers.py::promote_to_active` 新設 + 既存
      gateway / multi_agent_stream / scenario tests を `_promote_to_active` 経由化
- [x] `test_every_advertised_kind_has_explicit_routing` の expected_global を更新
- [x] `uv run pytest tests/` 全パス (860) + ruff clean
- [x] commit: `feat(gateway): m7-γ WorldLayoutMsg single-shot on-connect`

## Commit 4: Godot Relationships UI + layout consumer + scene 補修 (3.5h)

- [ ] `godot_project/scripts/EnvelopeRouter.gd` に `world_layout_received` signal +
      match arm
- [ ] `godot_project/scripts/BoundaryLayer.gd` の `zone_rects` / `prop_coords` を
      `_on_world_layout_received` で置換 (hardcode は default fallback、
      `# TODO(slice-γ)` 解消)
- [ ] `godot_project/scripts/ReasoningPanel.gd` に Foldout「Relationships」追加。
      `agent_update` 受信時に `agent_state.relationships` を引いて
      `<persona> affinity ±0.NN (N turns, last in <zone>)` 形式で 2 行描画
- [ ] `godot_project/scenes/zones/Chashitsu.tscn` の root Z=15 → -33.33 修正
      (子 mesh は相対座標保持)
- [ ] `godot_project/scenes/zones/Zazen.tscn` に石灯籠 primitive
      (CylinderMesh + BoxMesh、Garden.tscn の lantern を参考)
- [ ] `uv run pytest tests/test_godot_project.py` headless boot 緑 (該当 test 存在時)
- [ ] commit: `feat(godot): m7-γ Relationships UI + WorldLayoutMsg consumer + scenes`

## Commit 5: γ 受入 + C3 判定 (2h)

- [ ] `tests/test_integration/test_slice_gamma_e2e.py` 追加 (3-agent fixture、
      relational_memory ≥3、ReasoningTrace.decision に "affinity" 含有)
- [ ] `uv run pytest tests/` 全パス + `ruff check/format --check` clean
- [ ] G-GEAR live 90-120s run (ERRE_ZONE_BIAS_P=0.1, kant/nietzsche/rikyu)
      - dialog_turn ≥3 / world_layout = 1 / relational_memory ≥3
      - Godot ReasoningPanel で affinity 表示確認 (MacBook 側)
- [ ] `.steering/20260425-m7-slice-gamma/decisions.md` に
      D1-D5 (v2 採用根拠) + C3 判定 (3 観点: 観察容易性 / affinity 体現 / 論文化価値、
      2/3 で必要、初期スタンス defer to δ) を記録
- [ ] commit: `feat(acceptance): m7-γ slice e2e + C3 deferral judgement`

## Verification + PR

- [ ] `/review-changes` で code-reviewer 起動、HIGH 全対応 (security skip 可)
- [ ] `git push -u origin feat/m7-slice-gamma`
- [ ] `gh pr create` with 受入チェック
- [ ] PR URL を decisions.md に記録
- [ ] `/finish-task` 実行

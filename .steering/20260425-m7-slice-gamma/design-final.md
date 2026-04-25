# M7 Slice γ — Final Design (after /reimagine, approved 2026-04-25)

> **次セッションで本ファイル + plan file を最初に Read してから実装に入る。**
> Plan file 本体: `C:\Users\johnd\.claude\plans\zany-gathering-teapot.md`
> このファイルは plan file の repo-resident コピーで内容は同一。

## Plan vs. design.md scaffold (v1) の差分要約

`.steering/20260425-m7-slice-gamma/design.md` の v1 scaffold は意図的に放棄、
独立 Plan agent (v2) を `/reimagine` で立て、両案比較で v2 を採用。差分の核:

| 軸 | v1 (scaffold) | v2 (採用) |
|---|---|---|
| 1. affinity hook | sink 直後に 1 行追加 | `cognition/relational.py::compute_affinity_delta` を pure function 化 + chain sink (`bootstrap.py`) |
| 2. ReasoningTrace 粒度 | 未確定 | observed_objects ← AffordanceEvent salience top-3 / nearby_agents ← ProximityEvent.crossing="enter" max 2 / retrieved_memories ← recall_*.id top-3 |
| 3. WorldLayoutMsg 送信 | 曖昧 | `WorldRuntime.layout_snapshot()` property、`registry.add()` 直前に per-session 1 回 push |
| 4. Relationships UI | hybrid | Foldout 1 つに `<persona> affinity ±0.NN (N turns, last in <zone>)` 縦並び (SelectionPanel と重複回避) |
| 5. C3 (anatomy) 判定 | 「実装後に判断」 | 観察容易性 / affinity 体現 / 論文化価値の 3 観点を明文化、2/3 で必要判定、初期スタンス defer to δ |

### v2 からの minor adjust: affinity_delta 算出規則
v2 の lexical heuristic + persona prior は γ MVP 範囲外。**γ では `compute_affinity_delta`
を pure function として切り出す構造**を採用しつつ、**初期実装は constant `+0.02`**
で固定 (clamp [-1.0, 1.0])。lexical heuristic は signature 互換のまま δ で
差し替え可能。

## 5 commit (~11h) tasklist (granular, 30 min 粒度)

### Commit 1: schemas — ReasoningTrace 拡張 + WorldLayoutMsg + version bump (1.5h)
- 0:30 `WorldLayoutMsg` + `ZoneLayout` + `PropLayout` を `src/erre_sandbox/schemas.py` §7 末尾に追加 (`kind="world_layout"`、`zones: list[ZoneLayout]`、`props: list[PropLayout]`、tick=0)
- 0:30 `ReasoningTrace` に `observed_objects: list[str]` / `nearby_agents: list[str]` / `retrieved_memories: list[str]` を追加 (default_factory)
- 0:30 `SCHEMA_VERSION` を **`0.6.0-m7g`** に bump、`__all__` 更新、`fixtures/control_envelope/world_layout.json` golden 追加、`tests/test_schemas.py` 期待値更新

### Commit 2: cognition — relational + reflection + trace (3.0h)
- 0:30 `src/erre_sandbox/cognition/relational.py` 新設、`compute_affinity_delta` 純関数 (constant +0.02 clamp) + unit test
- 0:30 `src/erre_sandbox/bootstrap.py` の `turn_sink` を chain 化、`_persist_relational_event` (relational_memory に MemoryEntry(kind=RELATIONAL, content, tags=[zone, dialog_id]) INSERT + `RelationshipBond.affinity` mutation) を追加
- 1:00 `src/erre_sandbox/cognition/reflection.py::build_reflection_messages` に `recent_dialog_turns` 引数追加 (D1)、system prompt 末尾に「直近の他 agent 発話 (最大 3)」 section を append
- 0:30 `src/erre_sandbox/cognition/cycle.py` で reflection 呼び出し時に `store.iter_dialog_turns(persona=other_personas, since=now-300s)` から 3 件取得して渡す
- 0:30 ReasoningTrace 生成位置で観測 event filter + recall_* id 集計 + `decision` に `f"... affinity={bond.affinity:+.2f} ..."` 文字列を埋め込み (D3 + D4)

### Commit 3: gateway — WorldLayoutMsg on-connect (1.0h)
- 0:30 `WorldRuntime` に `layout_snapshot() -> WorldLayoutMsg` property 追加 (`world/zones.py::ZONE_CENTERS` + `ZONE_PROPS` から構築)
- 0:30 `src/erre_sandbox/integration/gateway.py:558` の `registry.add(...)` 直前に `await _send(ws, runtime.layout_snapshot())` 挿入。`tests/test_integration/test_world_layout_msg.py` で connect → world_layout 受信を assert (golden JSON snapshot)

### Commit 4: Godot — Relationships UI + WorldLayoutMsg consumer + scene 補修 (3.5h)
- 0:30 `godot_project/scripts/EnvelopeRouter.gd` に `world_layout_received` signal + match arm
- 0:45 `godot_project/scripts/BoundaryLayer.gd` の `zone_rects` / `prop_coords` を `_on_world_layout_received` で置換 (hardcode は default fallback、`# TODO(slice-γ)` 解消)
- 1:00 `godot_project/scripts/ReasoningPanel.gd` に Foldout「Relationships」追加 (`agent_state.relationships` を 2 行描画)
- 0:30 `godot_project/scenes/zones/Chashitsu.tscn` の root Z=15 → -33.33 に修正
- 0:45 `godot_project/scenes/zones/Zazen.tscn` に石灯籠 primitive (CylinderMesh + BoxMesh、Garden.tscn の lantern 参考)

### Commit 5: γ acceptance + C3 判定 (2.0h)
- 0:30 `tests/test_integration/test_slice_gamma_e2e.py` 追加 (3-agent fixture、relational_memory ≥3、ReasoningTrace.decision に "affinity" 含有)
- 0:30 `uv run pytest tests/` 全パス + `uv run ruff check src/ tests/ && --format --check` clean
- 0:30 G-GEAR live 90-120s run、`dialog_turn` ≥3 / Godot ReasoningPanel 確認
- 0:30 `decisions.md` に v2 採用根拠 (D1-D5)、C3 判定 (3 観点) を記録

## Critical Files

- `src/erre_sandbox/schemas.py` (Commit 1)
- `src/erre_sandbox/cognition/relational.py` (Commit 2、新規)
- `src/erre_sandbox/cognition/reflection.py` (Commit 2)
- `src/erre_sandbox/cognition/cycle.py` (Commit 2)
- `src/erre_sandbox/bootstrap.py` (Commit 2)
- `src/erre_sandbox/world/tick.py` (Commit 3、`layout_snapshot` property)
- `src/erre_sandbox/integration/gateway.py` (Commit 3)
- `godot_project/scripts/EnvelopeRouter.gd` (Commit 4)
- `godot_project/scripts/BoundaryLayer.gd` (Commit 4)
- `godot_project/scripts/ReasoningPanel.gd` (Commit 4)
- `godot_project/scenes/zones/Chashitsu.tscn` (Commit 4)
- `godot_project/scenes/zones/Zazen.tscn` (Commit 4)
- `tests/test_integration/test_slice_gamma_e2e.py` (Commit 5、新規)
- `fixtures/control_envelope/world_layout.json` (Commit 1、新規)

## 既存 utility の再利用

- `MemoryStore.iter_dialog_turns(persona, since)` (`memory/store.py:836-873`)
- `world/zones.py::ZONE_CENTERS` / `ZONE_PROPS`
- `RelationshipBond.affinity` (`schemas.py`)
- `cognition/reflection.py::build_reflection_messages` の既存 episodic memory 経路
- Garden.tscn の lantern primitive (Zazen 石灯籠の参考)

## Verification

### Unit / integration
- `uv run pytest tests/` 全パス
- `uv run ruff check src/ tests/` + `--format --check` clean
- `tests/test_schemas.py::test_schema_version` が `0.6.0-m7g` を expect
- `tests/test_integration/test_world_layout_msg.py`
- `tests/test_integration/test_slice_gamma_e2e.py`
- `tests/cognition/test_relational.py` で `compute_affinity_delta` 境界値

### Live G-GEAR
- `feat/m7-slice-gamma` branch で `ERRE_ZONE_BIAS_P=0.1 uv run erre-sandbox --personas kant,nietzsche,rikyu --db var/run-gamma.db`
- `_stream_probe_m8.py` を 0.6.0-m7g に bump (Commit 1 同梱)
- 90-120s run、`evidence/<run>.summary.json` で `dialog_turn ≥ 3` / `world_layout = 1`
- `relational_memory` table (`SELECT COUNT(*) FROM episodic_memory WHERE kind='relational'`) で ≥3 行

### Review + PR
- `/review-changes` (code-reviewer + security-checker、γ では security skip 可)
- `gh pr create` で受入チェック付きで作成

## Plan → Clear → Execute (CLAUDE.md L69-71)

本 plan 承認後、context が 30% を超えていたら `/clear` で切り、次セッションで:
1. `C:\Users\johnd\.claude\plans\zany-gathering-teapot.md` を Read
2. 本 `design-final.md` を Read
3. 既存 `tasklist.md` (v1 scaffold) を v2 tasklist に書き換え (実装着手前に)
4. Commit 1 から開始

context 30% 超で `/clear` 推奨は本タスクで Plan agent + 3 Explore agent を回したため。

## 採用しなかった v2 の細部 (M9+ で再検討)

- lexical heuristic affinity_delta (signature 互換で差し替え可能)
- observation event ベースの delta

# m4-contracts-freeze

## 背景

M4 planning (`/20260420-m4-planning/`) で、M4 マイルストーン (3 体対話・反省・関係形成)
を **3 軸 (Multiplicity / Temporality / Sociality)** に分解し、Contract-First で
foundation を先に凍結してから並列実装する方針を採用した (v2 + hybrid)。

本タスクは M4 の **最初の foundation タスク**。他 5 本
(`m4-personas-nietzsche-rikyu-yaml` / `m4-memory-semantic-layer` /
`m4-gateway-multi-agent-stream` / `m4-cognition-reflection` /
`m4-multi-agent-orchestrator`) はすべて本タスクの contract 凍結に依存するため、
これが merge されないと並列実装を開始できない。

M2 Contract-First が MVP 10 日完了の最大成功要因だったという実績
(memory `project_implementation_plan.md`) を M4 に再適用する。

## ゴール

M4 個別タスクが並列実装を開始するために必須な最小 primitive を
`src/erre_sandbox/schemas.py` に凍結し、新 fixture
(`tests/fixtures/m4/`) を生成して互換検証を通す。`schema_version` を
`0.1.0-m2` → `0.2.0-m4` に bump する。

## スコープ

### 含むもの

- `src/erre_sandbox/schemas.py` に M4 primitive 追加:
  - `AgentSpec` (persona_id + initial_zone の最小 fields)
  - `BootConfig.agents: list[AgentSpec]` (既存 `BootConfig` への field 追加、別 API は作らない)
  - `ReflectionEvent` (agent_id, tick, summary_text, src_episodic_ids)
  - `SemanticMemoryRecord` (id, agent_id, embedding, summary, origin_reflection_id)
  - `DialogInitiateMsg` / `DialogTurnMsg` / `DialogCloseMsg` (ControlEnvelope variant 3 種)
  - `DialogScheduler` (**Protocol interface only**、具体実装は `m4-multi-agent-orchestrator` で)
- `SCHEMA_VERSION` 定数 (もしくは同等の参照点) を `0.2.0-m4` に bump
- `tests/fixtures/m4/` 配下に新 fixture (ControlEnvelope 各 variant + BootConfig 3-agent 例)
- `tests/test_schemas.py` に新 primitive の validation / round-trip / variant discrimination test を追加
- `godot_project/scripts/WebSocketClient.gd` の ControlEnvelope parser に
  `dialog_initiate` / `dialog_turn` / `dialog_close` の dispatch を追加 (hard-error しないこと)
- `.steering/20260420-m4-planning/tasklist.md` の MASTER-PLAN 追記系
  checkbox を `[x]` に更新する fixup を初回 commit に含める

### 含まないもの (個別タスクに委譲)

- reflection 発火条件の実装 (N tick? importance 閾値? zone トリガー?) → `m4-cognition-reflection`
- `semantic_memory` の sqlite schema 詳細 (index 構成、embedding dim、CRUD 実装) → `m4-memory-semantic-layer`
- `DialogScheduler` 本体実装 (turn-taking policy) → `m4-multi-agent-orchestrator`
- per-agent gateway routing 方式 (broadcast filter vs explicit subscription) → `m4-gateway-multi-agent-stream`
- `personas/nietzsche.yaml` / `personas/rikyu.yaml` の content → `m4-personas-nietzsche-rikyu-yaml`
- bootstrap の N-agent 拡張 / `__main__.py` の `--personas` flag → `m4-multi-agent-orchestrator`

## 受け入れ条件

- [ ] `src/erre_sandbox/schemas.py` に上記 6 primitive + `DialogScheduler` Protocol が存在する
- [ ] `BootConfig.agents: list[AgentSpec]` が既存 `BootConfig` 上に field 追加されている
      (新しい register API は作らない)
- [ ] `schema_version` (定数 or `ControlEnvelope.schema_version` default 等) が
      `0.2.0-m4` を返す
- [ ] `tests/fixtures/m4/` 配下に新 fixture が生成され、Pydantic round-trip が通る
- [ ] `tests/test_schemas.py` に M4 primitive 向け assertion が追加されている
- [ ] 既存 346 テストが継続 PASS (regression なし)
- [ ] `godot_project/scripts/WebSocketClient.gd` が
      `dialog_initiate` / `dialog_turn` / `dialog_close` を hard-error なく受け取れる
      (少なくとも print もしくは no-op dispatch が存在)
- [ ] `ruff` (format + lint) クリーン
- [ ] `.steering/20260420-m4-planning/tasklist.md` の MASTER-PLAN 追記 /
      `decisions.md` 作成の checkbox を `[x]` に更新する fixup を初回 commit に含める
- [ ] `feature/m4-contracts-freeze` branch で PR 準備まで到達
      (main 直接 push 禁止、CLAUDE.md 準拠)

## 関連ドキュメント

- `.steering/20260420-m4-planning/design.md` — 採用案 (v2 + hybrid)、Contract 凍結対象
- `.steering/20260420-m4-planning/decisions.md` — D3 (foundation 小型化の粒度) が本タスクの境界定義
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §5.1 — M4 詳細計画
- `docs/architecture.md` §Schemas — schemas.py の責務
- `.steering/20260418-schemas-freeze/` — M2 で同等の foundation 凍結を実施した先例
- memory `project_implementation_plan.md` — Contract-First 成功記録

## 運用メモ

- 破壊と構築 (`/reimagine`) 適用: **No**
- 理由: 設計判断は `/20260420-m4-planning/` で `/reimagine` 済み。本タスクは
  その採用案 (v2 + hybrid) を mechanically に具体化する実装タスクであり、
  凍結対象・粒度・schema_version bump 方針はすでに確定済み。複数案が考えられる
  領域は残っていないため、初回案を破壊する合理的理由がない。
  実装中に当初想定外の設計選択肢が浮上した場合のみ、その時点で `/reimagine` を検討する。

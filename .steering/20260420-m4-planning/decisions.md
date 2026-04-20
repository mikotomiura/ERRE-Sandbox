# Decisions — m4-planning

本ドキュメントは M4 全体の planning 段階で行った設計判断と根拠を記録する。
個別サブタスクでの詳細判断は各 `.steering/YYYYMMDD-m4-*/decisions.md` で扱う。

---

## D1. `/reimagine` 適用の判断

### 判断
**適用する**。M4 planning は設計タスクの中核 (arch + API + scope) であり、
memory `feedback_reimagine_trigger.md` (「設計タスクでは必ず /reimagine 適用」) と
`feedback_reimagine_scope.md` の規定対象そのもの。

### 履歴
1. requirement.md 記入後に v1 (素直な時系列積み上げ案、MASTER-PLAN §5 直訳) を design.md に記入
2. `design-v1.md` に退避
3. 意図的リセット宣言: 「v1 の層切り分解・時系列順序を踏襲しない」
4. requirement.md のみを立脚点に v2 を生成
5. `design-comparison.md` で両案比較
6. ユーザー選択: **v2 + hybrid** (選択肢 3)

---

## D2. 採用案: **v2 + hybrid (foundation 小型化)**

### 選択肢
- v1: 層切り直列積み上げ (4 タスク)
- v2: Contract-First + 3 軸 (Multiplicity/Temporality/Sociality) 並列 (6 タスク)
- v2 + hybrid (採用): v2 を base とし、foundation の凍結粒度を最小 primitive のみに絞る

### 採用理由
1. **M2 Contract-First の実証済み成功** — MVP を 10 日で完了できた最大要因は T05-T08 で
   schemas.py と ControlEnvelope fixture を先に凍結したこと。memory
   `project_implementation_plan.md` の "Why" に記録されている。
2. **Dialog (Axis C) の cross-cutting 性** — v1 は dialog を gateway-multi-agent-stream
   に内包していたが、実際は schemas + world (turn-taking) + cognition (生成) + gateway
   (broadcast) の全層に跨る cross-cutting concern。v2 で foundation 凍結時に明示化。
3. **2 拠点構成 (MacBook / G-GEAR) の活用** — v1 は直列前提で両機構成が
   1 機相当に縮退。v2 は contracts-freeze 後に 3 並列タスク (persona / memory-semantic /
   gateway-multi-agent) を両機で分担可能。
4. **手戻りコストの非対称性** — schema を後から変えるコストは前倒しコストの 3-5 倍。
   M2 の T19 live で Godot parser と Python schemas の整合で実体験済 (GAP-5 に帰結)。
5. **Hybrid 要素 (foundation 小型化) で v2 短所を緩和** — 凍結対象を並列実行に
   必須な最小 primitive に絞り、実装詳細 (reflection 発火条件、sqlite index、
   turn-taking policy 等) は個別タスクへ委譲。foundation 過負荷を避ける。

### 不採用 (v1) の理由
- dialog の cross-cutting 性が隠蔽され後半の scope creep リスクが高い
- Contract-First の恩恵を放棄し並列実行の機会を逃す
- multi-agent orchestrator 拡張が step 4 の末尾に押し込まれ責務が不明確

---

## D3. Foundation 小型化の粒度

### 凍結する (struct 完成形 or interface)
- `AgentSpec` (persona_id + initial_zone の最小 fields)
- `BootConfig.agents: list[AgentSpec]` (既存 struct への field 追加)
- `ReflectionEvent` (agent_id, tick, summary_text, src_episodic_ids)
- `SemanticMemoryRecord` (id, agent_id, embedding, summary, origin_reflection_id)
- `DialogInitiateMsg` / `DialogTurnMsg` / `DialogCloseMsg` (ControlEnvelope variant)
- `DialogScheduler` (**Protocol interface only**、本体は orchestrator タスクで)

### 凍結しない (個別タスクで決定)
- reflection 発火条件 (N tick / importance 閾値 / zone トリガー)
  → `m4-cognition-reflection` で決定
- `semantic_memory` の sqlite schema 詳細 (index 構成、embedding dim)
  → `m4-memory-semantic-layer` で決定
- DialogScheduler 本体実装 (turn-taking policy)
  → `m4-multi-agent-orchestrator` で決定
- per-agent gateway routing 方式 (broadcast filter / explicit subscription)
  → `m4-gateway-multi-agent-stream` で決定

### 根拠
Foundation が重くなると個別タスクで "schema 追加待ち" 遅延が発生。最小 primitive
のみ凍結し、実装詳細は個別タスク内で柔軟に決定させる。これは YAGNI 原則と
M2 成功パターンの折衷。

---

## D4. `schema_version` の bump 方針

### 判断
`0.1.0-m2` → `0.2.0-m4` に bump (minor bump、breaking changes を伴うため)

### 理由
- `AgentSpec` 追加、`DialogTurnMsg` 等の新 variant、ControlEnvelope 既存 structure
  に影響しうる → 厳密には additive-only だが、foundation 凍結の節目として明示的な
  bump を行う
- M2 → M4 (M3 は MASTER-PLAN で意図的に skip されている) の飛びを
  version 命名で反映 (semantic clarity)
- M4 fixture と M2 fixture を `tests/fixtures/m2/` `tests/fixtures/m4/` で併存期間を作る。
  M4 merge 完了時に M2 fixture を削除。

---

## D5. M4 サブタスク数: 4 → 6 への拡張

### 変更
MASTER-PLAN §5 の M4 代表タスク 4 本に対して、以下 2 本を追加:
- `m4-contracts-freeze` (Foundation)
- `m4-multi-agent-orchestrator` (Integration)

### 理由
- Contracts 凍結を独立タスク化しないと、並列実行の entry point が不明瞭
- multi-agent orchestrator は v1 で step 4 (gateway) の末尾に埋もれていたが、
  本来は bootstrap + DialogScheduler + live 検証を含む integration 責務のタスク

### How to apply (M4 以降)
- 本追加は memory `project_implementation_plan.md` の補足として記録する
- MASTER-PLAN §5 の表に M4 詳細セクション (本 PR で追記予定) を設けて反映

---

## D6. docs 更新方針: 各サブタスクに委譲

### 判断
`docs/architecture.md` / `docs/functional-design.md` の M4 関連更新は本 planning タスクでは
**見出しの追加予告のみ** を行い、本体の更新は個別サブタスクで実施する。

### 理由
- planning 段階で docs 本体を書くと、個別タスクで細部が変わった時に二重メンテになる
- 個別サブタスクの設計判断 (D3 の「凍結しない」項目) が確定してから書いた方が正確
- 各サブタスクの検収条件に「該当 docs セクション追記」を含めることで漏れを防ぐ

---

## 参照
- `requirement.md` (本タスクの前提)
- `design.md` (v2 + hybrid 採用案)
- `design-v1.md` (v1 初回案の退避)
- `design-comparison.md` (2 案の詳細比較)
- `.steering/20260419-m2-functional-closure/decisions.md` (M2 closeout 継承点)
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §5 (追記先)
- memory `project_implementation_plan.md` (Contract-First 成功記録)
- memory `feedback_reimagine_trigger.md` / `feedback_reimagine_scope.md` (適用根拠)

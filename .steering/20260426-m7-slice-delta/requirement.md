# M7 — Slice δ (CSDG 半数式 + negative affinity + 2 層 Memory bridge)

## 背景

Slice γ (PR #92) で関係性ループの **signature** は完成した:

- `cognition/relational.py::compute_affinity_delta(turn, recent_transcript, persona)`
  が pure function で実装され、δ で body 差し替え可能
- `WorldRuntime.apply_affinity_delta` が双方向 bond mutation
- `MemoryEntry(kind=RELATIONAL)` が dialog turn ごとに INSERT
- `ReasoningTrace` が observed_objects / nearby_agents / retrieved_memories を含む
- Godot `ReasoningPanel.Relationships` block が affinity を表示

しかし `compute_affinity_delta` は **constant +0.02** で固定されており、γ MVP の判断
として decisions.md D2 で明示的に δ 送りされた。

**MacBook post-merge review (R3、2026-04-25)** で CSDG (前身プロジェクト) との
4 軸 (半数式 / 3 層 Critic / 2 層 Memory / 多様性強制) 整合性をチェックし、δ で
着手すべき HIGH 3 件 + MEDIUM 5 件 + LOW 4 件を抽出した。本 Slice δ はその R3
HIGH/MEDIUM の主要部分 + γ で defer された C3 anatomy 残り 2/3 を消化する。

加えて γ で送り負債になった項目 (decisions.md C3、`.steering/20260425-m7-slice-gamma/`):

- C3 anatomy: 1/3 criteria 達成 (Relationships UI のみ)、残り 2/3 (visual avatar
  primitive + persona-distinct silhouette) を δ で判定
- D5 で `last in <zone>` を defer (RelationshipBond が zone field を持たない)、
  bond schema 拡張 + Godot 表示拡張

## ゴール

1 PR (~12-15h 工数想定) で以下を同時達成し、live G-GEAR で「3 agent が
**実体ある関係性** (正/負 affinity + decay + belief 化) を持って振る舞う」を
観察可能にする:

1. **CSDG 半数式の adoption** (R3 H1): `compute_affinity_delta` body を
   `prev*(1-decay) + event_impact*event_weight` に置換
2. **Negative affinity path の実装** (R3 M4): persona-trait antagonism または
   lexical contradiction で negative delta を生成、`Physical.emotional_conflict`
   との連動
3. **2 層 Memory bridge** (R3 M1 + R3 H1 後段): `|affinity| > belief_threshold`
   かつ N interactions 後に SemanticMemoryRecord に格上げ ("I trust Rikyu" /
   "I clash with Nietzsche")
4. **観測ホットパス scaling 修正** (R3 H3): `iter_dialog_turns` に `since_tick` /
   `limit` パラメータ追加、または専用 query `recent_peer_turns(exclude_persona_id, limit)`
5. **Live UX 修正** (R3 M2 + M3): `_decision_with_affinity` ranking key を
   `(|affinity|, last_interaction_tick)` desc / reflection peer-turn injection に
   persona display_name resolver を渡す
6. **C3 anatomy 残り 2/3 判定**: visual avatar primitive (capsule + color) と
   persona-distinct silhouette の 2 軸を Plan mode + /reimagine で 3 案比較、
   採用するか δ-2 / m9-lora に送るか判定
7. **bond schema `last_in_zone` 拡張** (γ D5 defer): `RelationshipBond` に
   `last_interaction_zone: Zone | None` 追加、Godot `ReasoningPanel` で
   "<persona> affinity ±0.NN (N turns, last in <zone> @ tick T)" 表示

## スコープ

### 含むもの (本 PR)

- R3 HIGH 3 件 (H1 半数式 / H2 single-writer comment + Lock 検討 / H3 SQL push)
- R3 MEDIUM 5 件 (M1 importance / M2 sort key / M3 persona resolver / M4 negative /
  M5 layout_snapshot timeout)
- C3 anatomy 残り 2/3 判定 (採用 or 別 slice 送り)
- bond schema `last_interaction_zone` 拡張
- 受入 live G-GEAR run (negative delta 1 件以上 / belief promotion 1 件以上 /
  decay による saturation 観察)

### 含まないもの (Slice ε / m8-affinity-dynamics 以降)

- R3 LOW 4 件 (L1 zone size warn / L2 GDScript split bug / L3 public accessor /
  L4 add_sync 公開) — 別 chore PR
- 3 層 Critic (Statistical / LLM-Judge) → m8-affinity-dynamics or M10-11
- 多様性強制の残り (opening 6 種・余韻 9 種) → M10-11
- LoRA / persona 分化 → L6 / m9-lora
- 4 agent 目以降 → L6 user-dialogue IF

## 受け入れ条件

### Unit / integration

- [ ] `uv run pytest tests/` 全パス (target: 880+ tests、現在 862)
- [ ] `uv run ruff check src/ tests/` pass
- [ ] **R3 H1 unit test**: `compute_affinity_delta` の半数式が `prev` と
  `event_impact` で挙動を変える (constant でない) ことを境界値 4 ケース以上で確認
- [ ] **R3 M4 unit test**: negative delta が persona antagonism または lexical
  contradiction で発生する 2 ケース以上
- [ ] **R3 H3 unit test**: `recent_peer_turns(exclude_persona_id, limit=5)` が
  SQLite 側で filter + LIMIT を発行 (cursor.execute の SQL を mock で確認)
- [ ] **C3 belief promotion test**: `|affinity| > 0.5` after 5+ interactions で
  SemanticMemoryRecord が生成
- [ ] **bond.last_interaction_zone schema test**: `RelationshipBond` round-trip
  + 既存 fixtures binary compat
- [ ] Godot `ReasoningPanel` rendering: `last in <zone>` 表示 (GUT で fixture)

### Live G-GEAR

- [ ] 3 agent 90-120s run で affinity delta が正/負両方発生 (run summary に記録)
- [ ] decay により affinity の saturation が観察される (CSDG 半数式の挙動確認)
- [ ] 1 件以上の belief promotion が SemanticMemoryRecord に出現
- [ ] `recent_peer_turns` SQL push 後の latency が現状 (γ Run-1) より低下
- [ ] `ReasoningPanel` で "last in <zone>" 表示が読める

### 評価記録

- [ ] `observation.md` に CSDG 半数式の挙動 (decay rate / event_impact 範囲) を記録
- [ ] `decisions.md` に C3 判定 (anatomy 採用 / defer) と根拠を記録
- [ ] M9 LoRA 比較 reference として γ Run-1 と δ Run-1 の baseline metrics 並記

## 関連ドキュメント

- Plan 本体: 次セッションで Plan mode (`Shift+Tab`×2) + Opus + **`/reimagine` 必須**
  - 半数式 (decay_rate / event_impact_fn / event_weight_fn の 3 自由度) は複数案ありうる
  - belief promotion 閾値 (`|affinity| > X` after Y interactions) も複数案ありうる
  - C3 anatomy は 3 案 (capsule / silhouette billboard / billboard + animation) で
    /reimagine
- 前提となる review 結果: `.steering/20260425-m7-slice-gamma/decisions.md` の **R3**
- γ design-final: `.steering/20260425-m7-slice-gamma/design-final.md`
- γ run-01 baseline: `.steering/20260425-m7-slice-gamma/run-01-gamma/`
- CSDG memory: `~/.claude/projects/-Users-johnd-ERRE-Sand-Box/memory/reference_csdg_source_project.md`
- MASTER-PLAN: `.steering/20260418-implementation-plan/MASTER-PLAN.md`

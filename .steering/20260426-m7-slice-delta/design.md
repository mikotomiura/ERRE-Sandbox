# Slice δ — Design (Plan mode で書く)

> **このファイルは Plan mode + Opus + /reimagine で書く**。
> 着手前に必ず以下を Read:
>
> 1. `requirement.md` (本 dir)
> 2. `.steering/20260425-m7-slice-gamma/decisions.md` の **R3** (CSDG 比較 review)
> 3. `.steering/20260425-m7-slice-gamma/design-final.md` (γ design 全文)
> 4. `~/.claude/projects/-Users-johnd-ERRE-Sand-Box/memory/reference_csdg_source_project.md`

## 設計対象 (5 軸 + 1 判定)

Plan mode で各軸の **2-3 案を出して /reimagine で再生成案と比較、採用案を確定**する。
γ design-final の構造を参考に、以下の表形式でまとめる:

### 軸 1: CSDG 半数式の具現化 (R3 H1)

- `prev*(1-decay) + event_impact*event_weight` の 3 自由度を埋める
- Question 1: `decay_rate` は固定値 or persona ごと or zone ごと?
- Question 2: `event_impact` は utterance sentiment / lexical overlap /
  persona-trait match のどれ? 複合?
- Question 3: `event_weight` は `PersonaSpec.personality` のどの field に
  どうマップする?

### 軸 2: Negative affinity path (R3 M4)

- Question 1: lexical contradiction (NLI 系) は overkill か? heuristic で十分?
- Question 2: persona-trait antagonism のルール (e.g., kant.rationalism vs
  nietzsche.dionysian の対立軸) は YAML で定義 or hardcode?
- Question 3: `Physical.emotional_conflict` field (CSDG 由来、現在 unused) を
  delta 算出に使うか?

### 軸 3: 2 層 Memory bridge (R3 M1 + 長期 belief)

- Question 1: `belief_threshold` の値 (0.3? 0.5? 0.7?)
- Question 2: 必要 interactions 数 (3? 5? N と書ける?)
- Question 3: SemanticMemoryRecord の content 自動生成 (LLM 呼ぶ? template?)
- Question 4: belief を decay させるか? (永続? 一定期間後に再評価?)

### 軸 4: SQL push 修正 (R3 H3)

- Question 1: `iter_dialog_turns(since_tick, limit)` 拡張 vs 専用 query 新設
- Question 2: index 追加が必要か? `(persona_id, tick desc)` index?

### 軸 5: bond schema 拡張 (γ D5 defer)

- Question 1: `last_interaction_zone: Zone | None` で済む? それとも
  `interaction_zones: dict[Zone, int]` (zone ごとの count)?
- Question 2: 既存 fixtures の binary compat 保持方法

### 判定: C3 anatomy 残り 2/3

- 案 A: capsule mesh + persona-color material (γ default の billboard 改良)
- 案 B: billboard sprite (2D 立ち絵 / Stable Diffusion 生成 PNG)
- 案 C: billboard + idle animation (sprite atlas + AnimationPlayer)
- 案 D: defer to ε / m9-lora (LoRA 出力で自動分化を待つ)
- /reimagine で 3 案出して比較、採用案を確定

## Commit 構成 (案、Plan mode で確定)

γ の 7 commit (~11h) を踏襲:

1. **schemas** — `RelationshipBond.last_interaction_zone` + version bump
   `0.6.0-m7g → 0.7.0-m7d`
2. **cognition (formula)** — `compute_affinity_delta` body + decay + negative path
3. **cognition (memory bridge)** — belief promotion + SemanticMemoryRecord 生成
4. **memory/store** — `recent_peer_turns(exclude_persona_id, limit)` SQL push
5. **gateway / world** — H2 single-writer comment + M5 layout_snapshot timeout
6. **Godot** — `last in <zone>` 表示 + (C3 採用なら) anatomy primitive
7. **acceptance + live G-GEAR run** — δ MVP の zone-residency / affinity dist /
   belief promotion 観察

## テスト戦略

- δ Commit ごとに対応 unit test 1-3 個 (γ で確立した pattern)
- live G-GEAR run は MacBook Godot で screenshot を含めて完結 (γ 流儀)
- belief promotion test は `MemoryStore` mock で fast、live run は 120s

## リスク

- **半数式の calibration 不足**: 適切な `decay_rate` を 1 run で見つけるのは難しい。
  Plan で「最初は decay=0.05/tick で start、live run で観察 → δ-2 で再 calibrate」
  と明示する
- **C3 採用するか defer か**: Plan mode で 3 案比較しても結論が出ない場合、
  時間を切って defer する判断を decisions.md に記録
- **SQL push の migration**: 既存 `dialog_turns` に index 追加だけなら無痛、
  schema 変更なら migration script 必要 → Plan で確認

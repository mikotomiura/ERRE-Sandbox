# M6 Design Decisions

## Decision 1: Hybrid Track 構造を採用 (reimagine 結果)

### Context
M5 完了後、user 違和感 3 点 (イベント抽象性 / xAI 欠落 / 建築乏しさ) は相互依存する。単純な線形実装も、単純な垂直スライスも不適切。

### Options 比較
- **Alt-1 純線形 (A→B→C)**: 安全だが、B (xAI) は A (発火イベント) が無いと見せるものが無く、C (境界付き建物) は B (境界可視化) と関係する。相互依存を見逃す。
- **Alt-2 純垂直スライス (chashitsu だけ極める)**: 深度は出るが、FSM policy は全 5 ゾーン対象で既に動いており、共通骨格改善が長期停滞するのは不合理。
- **採用: Hybrid (3 並列 × chashitsu 垂直統合)**: 共通骨格 (event / xAI 基盤 / Blender パイプ) を 3 軸で進めつつ、統合 demo は chashitsu 1 点に集中。残 4 ゾーン (study/agora/garden + 残り) は M7 で pattern コピー。

### 根拠
- M5 でも /reimagine hybrid 採用の実績あり (project memory: M5 plan)
- 研究プラットフォームとして「機能する pipeline → 観察可能な研究装置」へ転換するには 3 軸同時改善が必要
- chashitsu は FSM で既に special mode を持ち、深掘りの価値が高い (persona-erre skill)

---

## Decision 2: ReasoningTrace を末行 JSON で回収

### Context
LLM 推論過程を構造化データで取りたい。structured output API (function calling 等) はモデル/バックエンド依存が強い。

### Options
- **Alt-A structured output (Ollama の response_format=json)**: バックエンド依存、モデル互換性問題
- **Alt-B 末行 JSON (prompt で指示し regex で抽出)**: バックエンド非依存、fallback しやすい
- **採用 B**: M5 LLM spike でも類似アプローチ採用 (`.steering/20260420-m5-llm-spike/decisions.md`)。malformed 時は fallback empty trace で動作継続。

### 抽出率目標
- Stable Ollama live で ≥ 80%。80% 未満なら prompt 例示強化 / sampling temp 微調整で回復を図る。

---

## Decision 3: `_maybe_apply_erre_fsm` の返り値を tuple に変更 (署名変更)

### Context
現在 `cycle.py:351` の docstring L382-387 に「if a future milestone requires an explicit shift event, emit it from here」と明記されている。M6-A-1 で実現する。

### 選択肢
- **Alt-A: 引数 `observations` を mutate**: 副作用あり、test 困難
- **Alt-B: instance 属性に stash**: thread safety 問題、debug 困難
- **採用 C: 返り値を `tuple[AgentState, ERREModeShiftEvent | None]`**: 署名変更は許容、明示的、test 容易

### 破壊的変更範囲
- 呼び出し元は `cycle.py:216` のみ (Grep 確認済)
- テストコードへの波及: 既存 test_cognition の `_maybe_apply_erre_fsm` 直接呼び出しを 1 箇所更新 (新規 test_erre_mode_events が主検証)
- Schema 契約への影響なし (内部 API のみ)

---

## Decision 4: Chashitsu First, 他 4 ゾーンは M7 繰越

### Context
Blender 制作コストは 1 ゾーン数時間〜1 日。5 ゾーン全部を M6 で作ると 1 週間消費、他トラックが停滞。

### 採用根拠
- chashitsu は FSM で専用 mode (`chashitsu`) を持ち、ERRE 理論 (身体的回帰・侘び寂び) の中核
- パイプラインを 1 ゾーンで定着させれば、M7 で残 4 ゾーン pattern コピーで高速実装可能
- acceptance gate に「茶室がリアルに見えるか」を据え、user 体感の違和感を直接解消

### M7 繰越項目 (明示)
- study / agora / garden / base_terrain の .blend 建築
- NavMesh-based pathing
- 屋内照明・パーティクル環境

---

## Decision 5: Scene 再作成しない (地盤 PlaneMesh 温存)

### Context
現 zone scene (Chashitsu.tscn 等) は 30×30 PlaneMesh + material。.blend を scene に置換する誘惑あるが、既存 zone contract (座標・material・CollisionShape) が依存されている。

### 採用
- PlaneMesh を「地盤」として残し、.glb を子ノード `add_child` する方式
- 既存 `WorldManager.gd` のゾーン参照・LOD・tinter 契約を破らない
- Rollback 容易 (子ノード削除のみ)

---

## Decision 6: Synapse Graph は簡素静的のみ

### Context
force-directed layout (d3 相当) は Godot では自前実装が重い。

### 採用
- 3 列固定レイアウト (左=入力 Observation / 中央=persona trait + FSM rule / 右=decision) を Label + Line2D で描画
- インタラクション: ホバーで詳細表示程度、drag layout は M7+
- 拡張性: 列方向を増やせる構造 (例: 将来 memory 層を追加) にしておく

---

## 参照

- 承認済みプラン: `~/.claude/plans/jiggly-rolling-hare.md`
- M5 schemas 先例: `.steering/20260420-m5-contracts-freeze/decisions.md`
- M5 JSON 出力先例: `.steering/20260420-m5-llm-spike/decisions.md`

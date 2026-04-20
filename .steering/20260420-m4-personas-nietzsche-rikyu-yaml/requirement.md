# m4-personas-nietzsche-rikyu-yaml

## 背景

M4 planning (`.steering/20260420-m4-planning/`) で確定した 6 サブタスクのうち、
Axis A (Multiplicity) 側の content curation タスク。
`m4-contracts-freeze` (PR #43 merged) で `PersonaSpec` / `AgentSpec` の schema
は 0.2.0-m4 として凍結済み。本タスクは `personas/kant.yaml` に続く 2 体目・
3 体目のペルソナ YAML を生成する。

3 体 (Kant / Nietzsche / Rikyu) が選ばれている理由:
- **Kant**: 規則性・理性の極 (DMN 抑制 + 散歩による分散的思考のハイブリッド)
- **Nietzsche**: 破壊的創造の極 (慢性的身体苦痛 + 山岳環境 + 孤独の中での破格の散文)
- **Rikyu**: 沈黙・間・実在的緊張の極 (茶室 = chashitsu で主君に死を命じられる非対称関係の精緻化)

この 3 体の ERRE mode / sampling パラメータが明確に差別化されることで、
M4 acceptance #4 (DialogInitiateMsg → DialogTurnMsg 往復) が観察する
「認知的多様性からの相互作用」の材料になる。

## ゴール

`personas/nietzsche.yaml` と `personas/rikyu.yaml` を
`PersonaSpec` schema に validate でき、`persona-erre` skill の ERRE mode 体系を
反映し、kant.yaml と十分差別化された形で完成させる。

## スコープ

### 含むもの

- `personas/nietzsche.yaml` — Nietzsche のペルソナ YAML 新規作成
- `personas/rikyu.yaml` — Rikyu のペルソナ YAML 新規作成
- 両 YAML は以下を含む:
  - `schema_version: "0.2.0-m4"` (foundation で bump 済み)
  - `persona_id` / `display_name` / `era` / `primary_corpus_refs`
  - `personality` (Big Five + wabi + ma_sense)
  - `cognitive_habits` (fact / legend / speculative フラグ付き、4-6 項目)
  - `preferred_zones` (5 zone から差別化された選択)
  - `default_sampling` (kant と数値が異なる)
- `tests/test_personas/test_load_all.py` — `personas/*.yaml` を
  parametrize で全件 `PersonaSpec.model_validate()` に通す
- 既存 `tests/test_personas.py` はそのまま維持 (Kant 専用)
- 本タスクの設計判断 (`/reimagine` の v1→v2 遷移とその根拠) を
  `.steering/20260420-m4-personas-nietzsche-rikyu-yaml/decisions.md` に記録

### 含まないもの (個別タスク / 後続)

- ペルソナからのプロンプト組み立て (`cognition/prompt_assembly.py` 等)
  → 既存の T11 経路をそのまま再利用、本タスクでは変更しない
- `AgentSpec` を使った bootstrap の N-agent 起動フロー → `m4-multi-agent-orchestrator`
- ERRE mode 切替ロジックの実装 → M5 以降 (既に M2 で最小実装あり)
- LoRA per persona → M9
- 新しい cognitive_habit `mechanism` の実験的検証 → ERRE-Sandbox v0.3 research
- 4 体目以降のペルソナ (Russell / Einstein etc.) → M5 以降

## 受け入れ条件

- [ ] `personas/nietzsche.yaml` が `PersonaSpec.model_validate()` に通る
- [ ] `personas/rikyu.yaml` が `PersonaSpec.model_validate()` に通る
- [ ] 両 YAML が `schema_version: "0.2.0-m4"` を持つ
- [ ] `cognitive_habits` の各項目が `flag` (fact / legend / speculative) 付き
- [ ] `mechanism` フィールドが 1 文以上の具体的な cognitive-neuroscience 根拠を含む
- [ ] `default_sampling` の数値が kant の (`temperature=0.60`, `top_p=0.85`,
      `repeat_penalty=1.12`) と異なる (ERRE mode の baseline 差異を反映)
- [ ] `preferred_zones` が kant と少なくとも 1 zone 異なる (Rikyu は特に chashitsu
      偏重、Nietzsche は peripatos + garden 偏重を期待)
- [ ] `tests/test_personas/test_load_all.py` を追加し、
      `personas/*.yaml` を parametrize で validate
- [ ] `/reimagine` を適用し、v1 (初回案) と v2 (再生成案) を比較の上、
      採用案 (v1 / v2 / hybrid) を `decisions.md` に記録
- [ ] 既存 378 テスト継続 PASS (regression なし、380+ に増える見込み)
- [ ] `ruff check` + `ruff format --check` クリーン
- [ ] code-reviewer subagent で HIGH 指摘ゼロ

## 関連ドキュメント

- `.steering/20260420-m4-planning/design.md` §「m4-personas-nietzsche-rikyu-yaml」
- `.steering/20260420-m4-contracts-freeze/` — PersonaSpec bump の前提
- `.steering/20260418-persona-kant-yaml/design.md` — Kant YAML の先例、
  構造とコメント方針を踏襲
- `.claude/skills/persona-erre/SKILL.md` — ERRE mode / サンプリングオーバーライド
  の canonical reference
- `personas/kant.yaml` — 構造・コメント・flag 方針のテンプレート
- memory `feedback_reimagine_scope.md` — content curation にも reimagine 適用

## 運用メモ

- 破壊と構築 (`/reimagine`) 適用: **Yes**
- 理由: memory `feedback_reimagine_scope.md` の明示的な適用範囲。
  偉人ペルソナは「どの cognitive_habit を選ぶか / mechanism の粒度 /
  sampling fingerprint / zone mapping」すべてが設計選択で、既存 tropes
  (Nietzsche = 力への意志 / Rikyu = 茶の湯美学) に引きずられると
  後続 2 体目 merge 後に差別化不足が露呈する確率が高い。初回案を
  意図的に破棄し、身体的・神経生理的側面から再構築して比較する。

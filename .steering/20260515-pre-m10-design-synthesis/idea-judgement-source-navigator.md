# Corpus2Skill 導入判断メモ

Last reviewed: 2026-05-12  
Status: M9 完了後の設計候補。現時点では実装しない。

## 結論

Corpus2Skill の考え方は、ERRE-Sandbox に **かなり有効**。ただし有効なのは
「エージェントが毎 tick 使う検索機構」としてではなく、史料・評価 corpus・persona 根拠を
**階層的に見える化する evidence/source navigator** として採用する場合に限る。

判定:

- 公式 `dukesun99/Corpus2Skill` を直接 dependency として取り込む: **2/10、不採用**
- 論文の compile-then-navigate pattern を ERRE 向けにローカル再実装する: **8/10、強い採用候補**
- M9 進行中タスクへ割り込ませる: **3/10、後回し**
- M9 完了後の M10-0 preflight として設計する: **最適**

## 参照した外部情報

- Paper: https://arxiv.org/abs/2604.14572
- Code: https://github.com/dukesun99/Corpus2Skill

Paper の主張:

- RAG は検索結果だけを LLM に渡すため、corpus 全体の構造や未探索領域を LLM が見られない。
- Corpus2Skill は document corpus をオフラインで階層 skill tree に変換し、serve 時に agent が
  `SKILL.md` / `INDEX.md` / document id をたどって探索する。
- 強い領域は single-domain / atomic-document corpora。
- 弱い領域は open-domain / extractive pools / 長大文書中心の検索。

公式実装の特徴:

- Anthropic Skills API / Anthropic API key 前提。
- `.claude/skills/` 形式を出力。
- compile phase で embedding + clustering + LLM summarization + labeling。
- serve phase で code execution + `get_document(doc_id)` tool を使う。
- README 上で early release / rough edges remain と明記。
- 現時点では root に LICENSE が見当たらないため、コード取り込みは不可扱いから始めるべき。

## ERRE-Sandbox との適合点

### 強く合う点

1. ERRE の Extract/Reverify と同型である

ERRE は一次史料・批判的伝記から `cognitive_habits` を抽出し、fact / legend /
speculative を明示する。Corpus2Skill 型の navigator は、この根拠 corpus を
「どこに何があり、どの persona habit に接続するか」という探索木にできる。

2. M10 の cited evidence 方針に合う

M10+ 設計では `WorldModelUpdateHint` / `SubjectiveWorldModel` / `cited_memory_ids` により、
LLM 自己宣言ではなく引用済み evidence で状態を動かす方針になっている。
Corpus2Skill 型の document id navigation は、この citation discipline と相性が良い。

3. M9-eval / LoRA 汚染防止と接続できる

M9 は raw_dialog と metrics を分離し、training data に評価情報や個体層情報を混ぜない方針。
Corpus navigator は training data generator ではなく、source/evidence inspection として
隔離すれば汚染を避けられる。

4. 人文学研究ツールとして価値がある

「カントのこの認知習慣はどの一次史料・伝記記述・神経科学根拠に由来するか」を
手で追える状態にできる。これは ERRE の学術的説明責任をかなり強める。

### 合わない点

1. 公式実装はクラウド API 前提

ERRE はクラウド LLM API を必須依存にしない。Anthropic API 前提の compile / serve は
そのまま採用不可。

2. `.claude/skills` は Codex/ERRE の canonical 入口ではない

ERRE では Codex 実運用入口は `.agents/skills/`。ただし生成物をそこへ直接入れるのも危険。
generated corpus tree は agent instruction ではなく、まず data/evidence artifact として扱う。

3. ランタイム tick に入れるには重い

ERRE の cognition cycle は 10 秒単位で動く。毎回階層 navigation を multi-turn で行うと、
latency、token、GPU throughput、prompt cache を壊す。

4. 現行 memory retriever と役割が違う

`memory/retrieval.py` は episodic / semantic memory を decay + importance + recall_count +
semantic similarity で引く runtime memory。Corpus2Skill は static corpus navigation。
ここを混ぜると memory の意味が濁る。

## 採用すべき設計方針

名称案:

- `source_navigator`
- `corpus_navigator`
- `evidence_navigator`

推奨は `source_navigator`。理由は、ERRE では「検索」より「根拠追跡」の意味が強いから。

配置案:

```text
src/erre_sandbox/evidence/source_navigator/
  __init__.py
  compile.py
  models.py
  builder.py
  local_summarizer.py
  document_store.py

data/corpus_index/
  kant/
    INDEX.md
    documents.json
    provenance.yaml
    clusters.json
```

または M10-0 ではまずコード化せず、`tools/` 側の experimental compiler として始めてもよい。

## 具体アイディア

### Idea 1: Persona Source Navigator

目的:

`personas/*.yaml` の `primary_corpus_refs` / `cognitive_habits` と、`corpora/` /
`evidence/reference_corpus/raw/` を結び、後から「この habit の根拠は何か」をたどれる
階層 index を作る。

入力:

- `personas/kant.yaml`
- `personas/nietzsche.yaml`
- `personas/rikyu.yaml`
- `corpora/`
- `src/erre_sandbox/evidence/reference_corpus/raw/`
- `_provenance.yaml`

出力:

- persona ごとの `INDEX.md`
- habit ごとの source cluster
- document id
- provenance
- fact / legend / speculative の対応表

採用価値:

- 高い。M10 前に実装しても runtime へ影響しない。
- persona YAML の根拠監査が強くなる。

注意:

- summary は証拠ではない。証拠は必ず raw document id と provenance。
- 著作権保護テキストを repo に含めない。

### Idea 2: M10 WorldModel Citation Navigator

目的:

M10-C の `WorldModelUpdateHint.cited_memory_ids` と同じ思想で、static source 側にも
`cited_document_ids` を持たせる。

使い方:

- LLM が「カントは歩行で発散思考が増える」と主張したら、navigator が
  該当 habit / source / neuroscience note を提示する。
- Python 側が document id と provenance を検証してから採用する。

採用価値:

- 非常に高い。ただし M10-C 以降。
- LLM 自己申告で内部状態を動かさない方針に合う。

注意:

- LLM に navigator summary を根拠として使わせない。
- 原文 document id を取得できない主張は採用しない。

### Idea 3: Evaluation Corpus QA Harness

目的:

M9-eval / M10-eval の golden stimulus や reference corpus に対して、
「どの corpus 領域が評価に使われているか」を階層化し、評価セットの偏りを見つける。

採用価値:

- 中程度から高い。
- `golden/` や `data/eval/` が増えるほど価値が上がる。

注意:

- training view には接続しない。
- metrics table や evaluation-only data が LoRA training に漏れないよう、
  `contracts/eval_paths.py` の分離原則を維持する。

### Idea 4: Developer / Researcher Navigation Skill

目的:

Codex や人間が「ERRE の docs / steering / decisions を後からたどる」ための
repository knowledge navigator を作る。

採用価値:

- 便利だが優先度は低い。
- 既存 `.agents/skills/` と混ざると危ないため、generated skill と handwritten skill を
  厳密に分ける必要がある。

注意:

- `.agents/skills/` へ自動書き込みしない。
- generated artifacts は `data/` か `docs/generated/` へ置く。

## 非採用ライン

以下はやらない。

- 公式 Corpus2Skill を core dependency に追加する。
- Anthropic API key を ERRE の必須依存にする。
- `.claude/skills/` を ERRE/Codex の実行入口として使う。
- generated corpus skill を `.agents/skills/` に直接配置する。
- runtime cognition tick ごとに multi-turn source navigation を走らせる。
- Corpus2Skill summary を factual evidence として扱う。
- M9-eval / LoRA training data に evaluation-only navigator output を混ぜる。
- license 未確認の外部コードを `src/erre_sandbox/` に取り込む。

## M9 完了後の推奨設計タスク

タスク名案:

```text
2026xxxx-source-navigator-m10-0
```

設計フェーズで決めること:

1. 生成物の置き場所
2. source document id の形式
3. provenance schema
4. summary を evidence と誤用しないための contract
5. local summarizer backend
6. embedding backend
7. incremental update の有無
8. M10 `cited_memory_ids` との接続境界
9. M9-eval / training contamination 防止
10. CI でどこまで検証するか

最初の MVP:

- Kant のみ。
- 既存 `personas/kant.yaml` と committed public-domain reference corpus のみ。
- 階層 depth は 2 まで。
- 出力は markdown + JSON。
- runtime には接続しない。
- acceptance は「habit 6 件が document/provenance にたどれること」。

MVP acceptance:

- `kant` の全 `cognitive_habits` について `source`, `flag`, `trigger_zone`,
  `document_ids`, `provenance` を引ける。
- provenance missing は loud failure。
- generated summary だけを根拠にした assertion が schema 上不可能。
- default install に重い ML dependency を追加しない。
- `uv run pytest tests/test_evidence` が既存の contamination contract を壊さない。

## 最終判断

Corpus2Skill は ERRE の「認知習慣を再実装する」本体ではない。
しかし、ERRE の弱点になりやすい **根拠追跡・史料監査・評価 corpus の見通し**を補強する
道具としては非常に強い。

したがって、M9 完了後に以下の姿勢で設計する:

> Corpus2Skill を導入するのではなく、ERRE の evidence discipline に合わせて
> **Corpus2Skill 型 source navigation をローカル・検証可能・非クラウド依存で再設計する**。

これが最も安全で、かつ研究プラットフォームとしての ERRE の説得力を上げる道筋。

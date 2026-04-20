# Decisions — m5-contracts-freeze

`.steering/20260420-m5-planning/` と `.steering/20260420-m5-llm-spike/` で合意した
仕様の機械的反映に加え、本タスク実施中に下した非自明な設計判断を記録する。

## 判断 1: design を /reimagine で再生成し v2 (TDD + script 化) を採用

- **判断日時**: 2026-04-20
- **背景**: 初回 design-v1 は "M4 手順を機械的に踏襲" とした。ユーザー指摘により
  「contract 凍結は公開 API を定義する判断なので /reimagine 推奨条件に該当」と再認識
- **選択肢**:
  - A (v1): M4 手順踏襲 (schemas 編集 → fixtures 手編集 → golden 手動再生成 → test 後追い)
  - B (v2): TDD 順 + `scripts/regen_schema_artifacts.py` 新設 +
    `tests/test_schemas_m5.py` milestone grouping ← **採用**
- **理由**: contract 凍結の本質は「契約を実行可能仕様で明示する」こと。TDD 順序にする
  と schemas.py の diff が単独で意図を運ばなくてもよくなり、test が first-class の
  contract として残る。fixture / golden の手編集は M4 でも神経質な作業だったため
  script 化で M6/M7 の再利用資産を作る
- **トレードオフ**: planning + reimagine フローに +1 ターン分の往復、および新規ファイル
  (`scripts/regen_schema_artifacts.py`、`tests/test_schemas_m5.py`) 2 件の追加
- **影響範囲**: design.md, design-v1.md, design-comparison.md の 3 ファイル構成;
  以降のタスク (M6 以降の schema bump) は本 script を再利用できる
- **見直しタイミング**: script の維持コストが投資を上回った場合 (未発生想定)

## 判断 2: `turn_index` は required (no default) で freeze、M4 互換の例外として docstring に明記

- **判断日時**: 2026-04-20
- **背景**: code-reviewer が MEDIUM 指摘として「`Field(...)` は additive でなく M4 破壊」
  を挙げた。「全て additive」という schemas.py docstring の文言と不整合
- **選択肢**:
  - A: `turn_index: int = Field(default=0, ge=0)` に softening
  - B: required を維持し、SCHEMA_VERSION docstring で breaking であることを明記 ← **採用**
- **理由**: spike 判断 4 で turn_index は exhaustion close の load-bearing 値。default=0
  にすると producer が turn_index を払い出さない事故を schema が捕捉できない。M4 の
  sole producer (`InMemoryDialogScheduler`) は同 PR で upgrade 済で live 互換問題なし
- **トレードオフ**: wire-level の "fully additive" 主張が崩れるので docstring で明示
  義務化 (怠ると将来の誤解を招く)
- **影響範囲**: `src/erre_sandbox/schemas.py::SCHEMA_VERSION` docstring を 2 段構成に
  (additive / breaking-for-producers) 変更。`DialogTurnMsg.turn_index` の field doc は
  unchanged
- **見直しタイミング**: 本 repo 外に M4 compat が必要な producer が生まれた場合
  (現状想定なし)

## 判断 3: `scripts/regen_schema_artifacts.py` に adapter validation を追加

- **判断日時**: 2026-04-20
- **背景**: code-reviewer が MEDIUM 指摘として「`_FIXTURE_ADDITIVE_PATCHES` が top-level
  のみしかカバーせず、nested 変更の将来拡張で silent fail する恐れ」を挙げた
- **選択肢**:
  - A: 警告コメントを追加するだけ
  - B: 再生成後に `TypeAdapter(ControlEnvelope).validate_python(data)` で
    fail-fast する防衛線を追加 ← **採用**
- **理由**: silent fail は regen → commit → pytest まで検出が遅れる。adapter 検証は
  O(n) でコスト無視可、idempotent 性も保てる
- **トレードオフ**: スクリプトに pydantic への依存が明示化 (既存 golden 再生成ですでに
  TypeAdapter を使っているので追加依存なし)
- **影響範囲**: `scripts/regen_schema_artifacts.py::_regen_fixtures` の末尾 1 行
  + docstring 拡張
- **見直しタイミング**: 将来 nested patch が必要になった場合、helper を再設計する

## 判断 4: tick.py:477 PLW2901 は noqa で対応 (refactor しない)

- **判断日時**: 2026-04-20
- **背景**: `ruff check src tests scripts` 実行で PLW2901 がヒット。`git stash`
  検証で本タスク開始前から main 上に存在する pre-existing と確認
- **選択肢**:
  - A: noqa で明示的に許容 ← **採用**
  - B: `_resolve_zone_target(env)` helper 関数に抽出して refactor
  - C: 放置 (ruff gate を通過できない)
- **理由**: 再バインドはゾーン解決済 target を apply と queue の 2 先にフォワードする
  intentional な pattern。helper 抽出は本タスクのスコープ (contracts-freeze) 外。
  noqa は 1 行のコメント追加で意図を明示でき、code-reviewer も "defensible" と評価
- **トレードオフ**: tick.py が更に成長した時点で B に切替える必要あり
  (code-reviewer の LOW 指摘として記録)
- **影響範囲**: `src/erre_sandbox/world/tick.py:477` の 1 行コメント
- **見直しタイミング**: 該当 for-loop 本体が 20 行超過した時点で refactor 検討

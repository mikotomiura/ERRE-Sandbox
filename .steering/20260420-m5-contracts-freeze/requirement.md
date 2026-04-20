# m5-contracts-freeze — M5 schema 0.3.0-m5 凍結

## 背景

M5 は ERRE mode FSM + dialog_turn LLM 生成 の両輪。`.steering/20260420-m5-planning/`
の採用 hybrid 案は **Contract-First 先行 + LLM Spike 先行** で、spike が
`.steering/20260420-m5-llm-spike/decisions.md` 判断 1-7 で完走済み。spike 結果は
contract 側に **追加 field を要求しない** ことを確認した (判断 4: `dialog_turn_budget=6`
維持、判断 7: C 案退避不要)。

したがって本タスクは planning と spike の合意に従い、M5 並列 4 本 (erre-mode-fsm /
erre-sampling-override-live / dialog-turn-generator / godot-zone-visuals) が型制約に
依拠して並走できるよう、schema 0.3.0-m5 を **直列で先行凍結** する。

## ゴール

`src/erre_sandbox/schemas.py` を 0.3.0-m5 に bump し、新 field と 2 Protocol を
additive に追加、fixture / golden / conftest を再生成し、既存 525 test + 本タスク
で追加する最小 test が PASS する状態で merge 可能にする。以降の sub-task は本 contract
に依存して並列実装できる。

## スコープ

### 含むもの

- `schemas.py` の変更:
  - `SCHEMA_VERSION = "0.3.0-m5"`
  - `Cognitive.dialog_turn_budget: int = Field(default=6, ge=0)` 追加
  - `DialogTurnMsg.turn_index: int = Field(..., ge=0)` 追加
  - `DialogCloseMsg.reason` literal に `"exhausted"` 追加
  - `ERREModeTransitionPolicy` Protocol 追加 (interface のみ)
  - `DialogTurnGenerator` Protocol 追加 (interface のみ)
  - `__all__` 更新
- `fixtures/control_envelope/*.json` の `schema_version` を 0.3.0-m5 に更新、
  `dialog_turn.json` に `turn_index` 追加
- `tests/schema_golden/*.schema.json` を再生成
- `tests/conftest.py` の `_build_dialog_turn` に `turn_index` default 追加
- 新 field の最小 test (turn_index の境界、reason="exhausted" の受理、Protocol の
  runtime_checkable 非要求の確認など)
- docs の `schema_version` 言及を 0.3.0-m5 に更新 (repository-structure.md 等)

### 含まないもの

- FSM / TurnGenerator の **実装** (Protocol interface のみ)
- `erre/` パッケージの実体、`integration/dialog_turn.py` の実体
- `bootstrap.py` の wiring 変更
- Godot 側の consumer 実装
- Feature flag 3 種の `__main__.py` 追加
- persona YAML / zone シーンの追加

## 受け入れ条件

- [ ] `SCHEMA_VERSION == "0.3.0-m5"` (schemas.py §1)
- [ ] `Cognitive.dialog_turn_budget` の default=6, ge=0 が型チェック / validation
      で確認できる
- [ ] `DialogTurnMsg.turn_index` が required int (ge=0) として追加され、欠損時は
      ValidationError になる
- [ ] `DialogCloseMsg.reason` が `"exhausted"` を受理し、未知 literal は reject
- [ ] `ERREModeTransitionPolicy` と `DialogTurnGenerator` が Protocol として import
      可能、`__all__` にも含まれる
- [ ] `uv run pytest -q` が既存 525 test + 新 test 全て PASS (0 failures, 0 errors)
- [ ] `uv run ruff check src tests` および `uv run ruff format --check` が PASS
- [ ] `uv run mypy src/erre_sandbox` が PASS (本 task に関係する箇所で 0 new errors)
- [ ] fixture JSON の `schema_version` が 0.3.0-m5、`dialog_turn.json` に
      `turn_index` が含まれる
- [ ] golden schema 3 ファイルが新 field を反映して regenerate されている
- [ ] `test_schema_contract.py::test_json_schema_matches_golden` が PASS

## 関連ドキュメント

- `.steering/20260420-m5-planning/design.md` §Schema 0.3.0-m5 追加内容 (設計根源)
- `.steering/20260420-m5-planning/decisions.md` 判断 2 (schema bump 根拠)
- `.steering/20260420-m5-llm-spike/decisions.md` 判断 4-7 (spike が値を validate)
- `.steering/20260420-m4-contracts-freeze/decisions.md` (M4 の踏襲元パターン)
- `docs/repository-structure.md` §4 (schemas 層の import 禁則)
- `.claude/skills/persona-erre/SKILL.md` §ルール 2 (Protocol が将来使う delta 表)

## 運用メモ

- **タスク種別**: その他 (contracts freeze 専用、実装は後続 sub-task)
- **破壊と構築 (/reimagine) 適用**: **Yes**
  - 理由: 公開 API (wire schema) を凍結する判断で、本来 /reimagine 推奨条件に該当。
    planning 段階で追加 field の **洗い出し** は済むが、配置・命名・Protocol の置き場
    (schemas.py vs contracts.py 分離)・fixture 更新戦略 (手編集 vs 再生成スクリプト)・
    test 順序 (TDD vs 後追い) などには代案余地がある。memory `feedback_reimagine_scope.md`
    「迷ったら適用」ルールにも合致。

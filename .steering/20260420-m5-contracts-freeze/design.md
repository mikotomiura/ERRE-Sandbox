# 設計 — m5-contracts-freeze (v2, reimagine 再生成案)

## 実装アプローチ

**Test-First (TDD) + milestone-grouped test file + scripted artifact regeneration**
の 3 原則で contract freeze を実行する。

### 原則 1: TDD で "何が凍結されるか" を実行可能仕様にする

schemas.py の **編集より先** に、新しい契約を記述する pytest を書く:

- 新 field の validation 境界 (`dialog_turn_budget` の ge=0、`turn_index` の required/ge=0)
- literal 拡張 (`reason="exhausted"` 受理、未知 literal の reject)
- Protocol の import 可能性と signature 形状 (`get_type_hints` で最低限の shape 検証)
- version 文字列 (`SCHEMA_VERSION == "0.3.0-m5"`)

これを最初に書くことで、スキーマ変更の意図が pytest で "読める" 形に残り、後から
誰かが schemas.py を触るときの "契約破壊の監視網" になる。実装後に後追いで test を
書くと、"通った状態" を基準に test を書く確証バイアスが入る。

### 原則 2: 新規 test は milestone-grouped ファイルに集約

M4 と M5 の schema 変更を 1 つの肥大化した `test_schemas.py` に混ぜると、履歴が
読みにくい。M5 由来の新 test は `tests/test_schemas_m5.py` として独立させ、
docstring に "M5 (0.3.0-m5) で凍結された契約" の旨を明記する。M6 以降も同パターンで
追加する。

### 原則 3: fixture / golden は一度きりのスクリプトで再生成

手編集だと `schema_version` 置換漏れや `turn_index` 追加忘れが起きやすい。本 task で
以下のスクリプトを **コード同梱で commit** する:

```
scripts/regen_schema_artifacts.py
```

このスクリプトは:
1. `schemas.py::SCHEMA_VERSION` を読み取り
2. `fixtures/control_envelope/*.json` の `schema_version` を置換
3. `dialog_turn.json` が `turn_index` を含まなければ `turn_index=0` を追加 (idempotent)
4. `tests/schema_golden/*.schema.json` を `TypeAdapter.json_schema()` で再生成

今回以降の schema bump でも同スクリプトが再利用できる。将来の PR レビューでは
"schemas.py + 再生成コミット" の 2 段構造になり、diff の意図が明瞭になる。

## 変更対象

### 新規作成するファイル

- `scripts/regen_schema_artifacts.py` — 上記の fixture + golden 再生成 (idempotent)
- `tests/test_schemas_m5.py` — M5 由来の新契約を記述する pytest

### 修正するファイル

- `src/erre_sandbox/schemas.py` — 以下を additive で追加:
  - `SCHEMA_VERSION = "0.3.0-m5"`
  - `Cognitive.dialog_turn_budget: int = Field(default=6, ge=0, ...)`
  - `DialogTurnMsg.turn_index: int = Field(..., ge=0, ...)`
  - `DialogCloseMsg.reason: Literal[..., "exhausted"]`
  - `ERREModeTransitionPolicy` Protocol (interface only)
  - `DialogTurnGenerator` Protocol (async, interface only)
  - `__all__` 更新
- `tests/conftest.py::_build_dialog_turn` — `turn_index=0` の default pop を追加
- `fixtures/control_envelope/*.json` — regen script で自動更新
- `tests/schema_golden/*.schema.json` — regen script で自動更新
- `docs/repository-structure.md` — 本文中に `0.2.0-m4` の言及があれば `0.3.0-m5` へ

### 削除するファイル

- なし

## 影響範囲

- **wire 互換**: additive only。`turn_index` が DialogTurnMsg の required field として
  追加されるが、現状 producer は本 task 実装を挟まないと emit されない。Godot consumer
  は未知 field を無視する既定動作、`turn_index` のみ parse 後に読む設計 (次タスクで)。
- **既存 test**: `DialogTurnMsg(...)` を **直接** 構築する箇所があれば
  `turn_index` 未指定で FAIL する。conftest の factory 経由は default で吸収される。
  Grep で該当箇所を列挙し、明示 `turn_index=0` を付与する (通例 2-3 箇所以内)。
- **scripts/** ディレクトリが既存でなければ新規作成 (repo 初)。README.md は付けず、
  スクリプト冒頭の docstring に使い方を書く (過剰な分割を避ける)。
- **sub-task の並列実装**: merge 後、erre-mode-fsm / erre-sampling-override-live /
  dialog-turn-generator / godot-zone-visuals の 4 本が `schemas.py` の新しい
  symbol (Protocol + Cognitive.dialog_turn_budget 等) を import 可能になる。

## 既存パターンとの整合性

- **Protocol の置き場**: 既存 §7.5 `DialogScheduler` と同じく schemas.py に置く。
  behavioral Protocol を schemas.py から追い出す代案もあるが、repo 内で唯一の
  precedent (`DialogScheduler`) が schemas.py にある以上、2 本追加は既存パターン踏襲
  が妥当。Protocol 分離は将来 3 つ以上に増えた時点で検討。
- **`__all__` アルファベット順**: 既存の並びを維持 (新規 2 つも該当位置に挿入)。
- **docstring の密度**: 各 field に "なぜこの値か/なぜこの制約か" を 2-3 行で記述
  (spike decisions への参照を含む)。既存 `DialogScheduler` の docstring 密度と同等。
- **ReflectionEvent / SemanticMemoryRecord (M4 追加)** の docstring 末尾が
  "決定 task へのポインタ (.steering/...)" を含むパターンを踏襲。
- **fixture 命名 / layout**: 既存通り `fixtures/control_envelope/<kind>.json`。

## テスト戦略

### TDD サイクル (本 task 内で実行)

1. `tests/test_schemas_m5.py` を新規作成し、以下を赤 (fail) 状態で書く:
   - `test_schema_version_is_m5`
   - `test_cognitive_dialog_turn_budget_default_and_bounds`
   - `test_dialog_turn_has_turn_index_and_is_required`
   - `test_dialog_close_accepts_exhausted_reason`
   - `test_erre_mode_transition_policy_protocol_importable`
   - `test_dialog_turn_generator_protocol_importable`
   - `test_protocol_signatures_shape` (get_type_hints で最低限の shape 確認、
     runtime_checkable は要求しない)
2. schemas.py を編集し、赤 → 緑
3. `python scripts/regen_schema_artifacts.py` を実行し、fixture + golden を更新
4. `conftest.py::_build_dialog_turn` の default 追加
5. 直接 `DialogTurnMsg(...)` を構築する既存 test を grep → 明示 `turn_index=0` 付与
6. `uv run pytest -q` で既存 525 + 新 test が全 PASS
7. `uv run ruff check src tests scripts` / `ruff format --check` / `mypy src/erre_sandbox`

### 統合 test

本 task は interface-only。FSM / TurnGenerator の統合 test は後続 sub-task で追加。

### 回帰

- `test_schema_contract.py::test_json_schema_matches_golden` が新 golden と一致
- 既存 M4 fixture は `schema_version` 置換と `dialog_turn.turn_index` 追加だけで
  引き続き parse 可能

## ロールバック計画

- 単一 PR `feature/m5-contracts-freeze` → review → merge
- 問題時は `git revert` で M4 contract に戻る。`scripts/regen_schema_artifacts.py` は
  version 文字列を読み込むので、revert 後に再実行すれば fixture/golden も自動で
  M4 版に戻る (script が残っても idempotent で副作用なし)。
- 緊急時に "scripts だけ先に merge して schemas は後回し" は不可 (script は最新
  SCHEMA_VERSION を前提に書かれるため)。同一 commit で整合を取る。

## この案の狙い (v2 固有の価値)

1. **TDD 順序**: contract の "凍結" を pytest で文字通り凍結する。test が後回しだと
   version bump の意図が schemas.py diff 単独からしか読めない。
2. **milestone-grouped test ファイル**: 今後 M6/M7 で schema が更に変わる際に、
   過去の契約変更の意図を読みたい人が `test_schemas_m{N}.py` を開けば分かる。
3. **scripted artifact regen**: fixture / golden の手編集は 1 回でも事故ると
   CI で気づくまでに時間がかかる。コード化すれば PR の diff が "script 実行の
   決定論的結果" として機械的に説明できる。
4. **scope 拡張 (docs 更新を含む)**: 後続 sub-task で docs 更新を忘れるリスクを排除。

## 設計判断の履歴

- 初回案 (`design-v1.md`) と再生成案 (v2) を `design-comparison.md` で比較
- **採用: v2 (再生成案)**
- 根拠: contract 凍結の本質が「契約を実行可能仕様で明示する」ことなので TDD 順序が
  筋。`scripts/regen_schema_artifacts.py` は M6/M7 でも再利用でき、既存
  `tests/schema_golden/README.md` の手動コマンド手順を自動化する一度限りの投資として
  妥当。milestone-grouped test ファイルは将来の契約変更の履歴可読性を向上させる。
  v1 は M4 手順の安全策だが、M4 のプロセス自体の改善機会を見逃しており、reimagine
  の主旨 (先行案の暗黙前提を問い直す) と整合しない。

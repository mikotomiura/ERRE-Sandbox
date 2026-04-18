# T05 schemas-freeze タスクリスト

## 準備
- [x] 関連 docs / skills を読む (glossary, architecture, repository-structure, python-standards, persona-erre, architecture-rules)
- [x] 影響範囲確認 (schemas.py は現状スケルトン、他モジュールからの import なし)
- [x] `/reimagine` で v1 → v2 比較 → v2 採用

## 実装 (§順に schemas.py を書き下ろす)
- [x] §1 Protocol constants (`SCHEMA_VERSION`)
- [x] §2 Enum 群 (Zone, ERREModeName, MemoryKind, HabitFlag, ShuhariStage, PlutchikDimension)
- [x] §3 Persona (CognitiveHabit, PersonalityTraits, SamplingBase, PersonaSpec)
- [x] §4 AgentState (Position, Physical, Cognitive, ERREMode, RelationshipBond, AgentState)
- [x] §5 Observation (5 event + Annotated Union)
- [x] §6 MemoryEntry
- [x] §7 ControlEnvelope (7 msg + Annotated Union)
- [x] §8 `__all__` 定義
- [x] `src/erre_sandbox/__init__.py` の再 export を検討 (必要なら更新)

## 静的解析
- [x] `uv run ruff check src/erre_sandbox/schemas.py` が警告ゼロ
- [x] `uv run ruff format --check src/erre_sandbox/schemas.py` がパス
- [x] `uv run mypy src/erre_sandbox/schemas.py` が strict でパス

## テスト
- [x] `tests/test_schemas.py` に smoke テスト 6 種を追加
  - [x] 各モデルのデフォルト値インスタンス化
  - [x] `extra="forbid"` で未知フィールドを reject
  - [x] StrEnum の JSON 往復
  - [x] Observation discriminated union (success + failure)
  - [x] ControlEnvelope discriminated union (success + failure)
  - [x] `SCHEMA_VERSION` の整合
- [x] `uv run pytest` 全体がパス (既存 test_smoke.py が壊れない)

## レビュー
- [x] code-reviewer によるレビュー
- [x] HIGH 指摘への対応

## ドキュメント
- [x] `decisions.md` に CSDG 参考箇所 + v2 採用根拠を明記
- [x] 用語追加 (必要なら glossary)

## 完了処理
- [x] design.md の最終化 (実装との差分を追記)
- [x] Conventional Commits でコミット (c81b5fb)
- [x] `feature/schemas-freeze` を push し、main への PR #5 を作成
- [x] `.steering/20260418-implementation-plan/tasklist.md` の T05 チェックを入れる

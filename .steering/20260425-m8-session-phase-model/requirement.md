# M8 Spike — Session Phase Model

## 背景

L6 ADR D3 (`two-phase methodology`) の M8 precondition。現状 ControlEnvelope 11
variants に user→agent channel が無く、user 介入は「autonomous 観察を汚染する」
方法論的緊張を抱えている (L6 design.md §4)。D3 採用は "session を autonomous /
q_and_a / evaluation の 3 相に分け、時間分離で autonomous claim を保護" する
方針。本 spike は schema に `SessionPhase` enum と `session_phase` フィールドを
追加し、epoch 遷移 API の契約を確定、Q&A epoch 中の user 発話記録仕様を
decisions.md に固定する。

## ゴール

- `schemas.py` に `SessionPhase` enum (autonomous / q_and_a / evaluation) を追加
- `AgentState` か `BootConfig` のどちらに `session_phase` を載せるかを決定し実装
- epoch 遷移 API (`transition_to_q_and_a()` 等) の契約を Pydantic Protocol で確定
- Q&A epoch 中の user 発話は **既存 DialogTurnMsg を再利用** する仕様を decisions に
- schema_version を bump、architecture-rules Skill と整合

## スコープ

### 含むもの
- `SessionPhase` enum の導入
- session_phase の置き場所決定と schema 追加 (1 フィールド)
- epoch 遷移 API の Protocol と test
- Q&A epoch 中の user 発話記録仕様 (DialogTurnMsg.speaker_id に "researcher" 等)
- schema_version bump と migration note

### 含まないもの
- Godot UI 実装 (text input box、別 spike)
- LLM への user 発話 injection 実装 (DialogScheduler 改修、別 spike)
- evaluation phase の中身 (M10-11 evaluation layer task)
- user persona YAML の具体設計 (persona-erre Skill 別 doc)

## 受け入れ条件

- [ ] `SessionPhase` enum が `schemas.py` に定義、Literal 型で 3 phase
- [ ] `session_phase` フィールドの所在 (AgentState vs BootConfig) が decisions で確定
- [ ] 遷移 API の Protocol が定義され、test が全 phase 遷移パスをカバー
- [ ] Q&A epoch 中の user 発話仕様が decisions.md に記録 (DialogTurnMsg.speaker_id
      の規約、autonomous log から除外する rule)
- [ ] schema_version bump (現 `0.2.0-m4` → `0.3.0-m8` 等)、migration note 記載
- [ ] `architecture-rules` Skill の schemas.py 追記ルール違反なし

## 関連ドキュメント

- 親 ADR: `.steering/20260424-steering-scaling-lora/decisions.md` D3
- 関連 L6 design §4 (方法論的緊張 autonomy vs intervention)
- 関連 Skill: `architecture-rules` (schemas 追記ルール)、
  `persona-erre` (researcher persona を扱う場合の YAML 雛形)
- 下流 (別 spike で扱う): Godot text input UI、user 発話 LLM injection、
  evaluation phase 本体、user persona YAML

## メモ: MacBook 完走可能

本 spike は schema + Protocol + unit test で構成、live LLM 推論不要。
MacBook 単独で完走可能、G-GEAR 不在中の優先候補。

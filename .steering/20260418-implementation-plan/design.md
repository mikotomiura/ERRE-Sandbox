# 設計 — 計画のアーキテクチャと実装順序

## 実装アプローチ

**契約駆動 (Contract-First)** を採用。素直な時系列積み上げ (初回案) では 2 拠点
が直列化して MacBook がアイドル化し、`ControlEnvelope` 仕様未凍結で両機が独立
実装する致命リスクがあるため、`/reimagine` で破棄して再生成した。

### 3 段 Phase

| Phase | 内容 | 並列性 |
|---|---|---|
| **Phase C** (Contract Freeze) | `schemas.py` と ControlEnvelope JSON fixture を凍結 | MacBook 単独、G-GEAR はモデル pull のバックグラウンド |
| **Phase P** (Parallel Build) | G-GEAR: memory→inference→cognition→world→gateway / MacBook: godot_project→WS client→peripatos scene | 両機並列 |
| **Phase I** (Integration) | 両機を WS で結線、M2 検収 | 両機同時 |

## 変更対象

### 新規作成するファイル (MVP = M2 まで)

#### `src/erre_sandbox/` — Python コードスケルトン
- `schemas.py` — Contract の核 (AgentState / Memory / ControlEnvelope)
- `memory/store.py`, `memory/embedding.py`, `memory/retrieval.py`
- `inference/ollama_adapter.py`, `inference/server.py`
- `cognition/cycle.py`
- `world/tick.py`, `world/zones.py`
- `ui/` (M2 では最小、T18 optional で Streamlit)

#### `godot_project/` — Godot 4.4 シーン
- `project.godot`, `scenes/MainScene.tscn`
- `scripts/AgentController.gd`, `scripts/WebSocketClient.gd`

#### その他
- `pyproject.toml`, `uv.lock`, `.python-version`
- `personas/kant.yaml`
- `tests/conftest.py`, `tests/test_schemas.py`
- `tests/fixtures/control_envelope_samples.json` — Godot と Python の両方が読む
- `docs/_pdf_derived/erre-sandbox-v0.2.txt` (gitignore 対象)

## 影響範囲

- 既存ファイルへの変更なし。すべて新規作成。
- `.gitignore` には `docs/_pdf_derived/`, `.godot/` を追加予定。

## 既存パターンとの整合性

- `docs/repository-structure.md` §4 の依存方向に完全準拠
  (`world/ → cognition/ → inference/, memory/` / `schemas.py` は他モジュール非参照)
- `docs/development-guidelines.md` の Conventional Commits + 作業ブランチ運用
- `.claude/skills/` の Skill 群を各タスクに割り当て (MASTER-PLAN.md 付録 A 参照)

## テスト戦略

| レベル | 対象 | 適用タスク |
|---|---|---|
| 単体 | `schemas.py` (Pydantic バリデーション) | T08 |
| 単体 | `memory/store.py` (sqlite-vec 挿入/検索) | T10 |
| 統合 | `cognition/cycle.py` (Ollama モックで 1 周回) | T12 |
| E2E | `world/tick.py` + gateway + WS 受信 | T19 |
| 契約テスト | `tests/fixtures/control_envelope_samples.json` を Python と Godot 両方でパース | T07, T15 |

## ロールバック計画

- 各タスクは作業ブランチで実施 (`feature/[task-name]`)
- 問題時は PR をクローズ、main は常にクリーン
- モデル重みは Ollama キャッシュにある限り再 pull 不要
- `.steering/[task]/` は失敗しても削除せず記録を保持、教訓を `decisions.md` や
  `blockers.md` に残す

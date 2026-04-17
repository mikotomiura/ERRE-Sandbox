---
name: test-standards
description: >
  pytest + pytest-asyncio を使ったテスト設計と実装の基準。
  tests/test_*.py ファイルを書く・修正する・追加する時に必須参照。
  test_schemas.py / test_memory/ / test_cognition/ / test_inference/ /
  test_world/ にテストを追加する時、conftest.py を変更する時、
  CI (uv sync --frozen → ruff → pytest) を設定する時に自動召喚される。
  @pytest.mark.asyncio の使い方、AgentState ファクトリフィクスチャ、
  sqlite-vec 一時 DB、LLM モック戦略、埋め込みプレフィックス検証テスト、
  TDD 適用範囲 (スキーマ検証・記憶検索・ERRE 状態遷移が対象) を定義する。
  ファイル命名: test_schemas.py, test_reflection.py など test_ prefix の .py ファイル全般。
allowed-tools: Read, Edit, Glob, Grep, Bash(pytest *), Bash(uv run pytest *)
---

# Test Standards

## このスキルの目的

ERRE-Sandbox のテストは「非決定論的な LLM 出力に依存しないロジックを確実に検証する」ことが目的。
特に、記憶検索スコアリング・Pydantic スキーマバリデーション・ERRE モード状態遷移・
埋め込みプレフィックス正確性は回帰リスクが高く、テストなしの変更は禁止。

## 適用範囲

### 適用するもの
- `tests/` 配下のすべての `test_*.py`
- `tests/conftest.py` のフィクスチャ定義

### 適用しないもの
- LLM 推論の出力内容 (非決定論的) — 統合テストでのみ実際の Ollama を使用可
- Godot シーンの描画テスト
- 探索的プロトタイピング段階のコード

## 主要なルール

### ルール 1: ディレクトリ構造は src/ のミラー

```
src/erre_sandbox/memory/retrieval.py  →  tests/test_memory/test_retrieval.py
src/erre_sandbox/cognition/cycle.py   →  tests/test_cognition/test_cycle.py
src/erre_sandbox/schemas.py           →  tests/test_schemas.py
```

新しいモジュールを追加したら、同時に対応テストファイルを作る。

### ルール 2: 非同期テストは @pytest.mark.asyncio

```python
# ✅ 良い例
import pytest
from erre_sandbox.memory.retrieval import retrieve

@pytest.mark.asyncio
async def test_retrieve_returns_top_k() -> None:
    results = await retrieve(query="散歩", k=3)
    assert len(results) <= 3
```

```python
# ❌ 悪い例
def test_retrieve_returns_top_k() -> None:
    import asyncio
    results = asyncio.run(retrieve(query="散歩", k=3))  # asyncio.run は nest できない
    assert len(results) <= 3
```

`pyproject.toml` に以下を追加して全テストを asyncio モードにする:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### ルール 3: conftest.py に共通フィクスチャを集約

```python
# tests/conftest.py
import pytest
import sqlite3
from erre_sandbox.schemas import AgentState, Biography, Physical

@pytest.fixture
def agent_state_kant() -> AgentState:
    """Factory: Kant persona in default state."""
    return AgentState(
        bio=Biography(
            name="Immanuel Kant",
            era="1724-1804",
            primary_corpus_refs=["kuehn2001"],
            cognitive_habits=["15:30±5min walk", "nasal breathing only"],
        )
    )

@pytest.fixture
def tmp_sqlite_db(tmp_path):
    """Temporary sqlite-vec DB for memory tests."""
    db_path = tmp_path / "test_erre.db"
    conn = sqlite3.connect(str(db_path))
    # sqlite-vec 拡張をロード
    conn.enable_load_extension(True)
    conn.execute("SELECT load_extension('sqlite_vec')")
    yield conn
    conn.close()
```

### ルール 4: TDD 適用範囲

**必ず TDD で書くもの (テストを先に書く)**:
- `schemas.py` のバリデーション制約
- `memory/retrieval.py` の検索スコアリングロジック
- ERRE モード状態遷移 (peripatos → DMN bias 変化など)
- 埋め込みプレフィックス検証

**TDD を適用しないもの**:
- LLM 出力に依存するテスト (非決定論的)
- Godot シーンの描画
- 探索的プロトタイピング段階

### ルール 5: LLM 推論を伴うテストはモック分離

単体テストでは LLM を呼ばない。統合テストでのみ実際の Ollama を使用。

```python
# ✅ 良い例 — 単体テストでモック
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_cognition_cycle_calls_llm(agent_state_kant) -> None:
    mock_response = {"action": "walk", "speech": "Gut morgen."}
    with patch("erre_sandbox.inference.ollama_adapter.generate",
               AsyncMock(return_value=mock_response)):
        result = await run_cognition_cycle(agent_state_kant)
    assert result.action == "walk"
```

```python
# ✅ 良い例 — 統合テスト (Ollama 必要、CI では @pytest.mark.integration でスキップ可)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_cycle_with_ollama(agent_state_kant) -> None:
    result = await run_cognition_cycle(agent_state_kant)
    assert result.action is not None
```

### ルール 6: 埋め込みプレフィックス検証テスト（CI 必須）

プレフィックスのミスマッチは 5〜15 ポイントの recall 劣化を招く。
**このテストを削除・無効化してはならない**。

```python
# tests/test_memory/test_embedding_prefix.py
import pytest
from erre_sandbox.memory.embedding import embed_query, embed_document
from erre_sandbox.memory.embedding import QUERY_PREFIX, DOC_PREFIX
import numpy as np

def cosine_sim(a: list[float], b: list[float]) -> float:
    a_, b_ = np.array(a), np.array(b)
    return float(np.dot(a_, b_) / (np.linalg.norm(a_) * np.linalg.norm(b_)))

def test_query_and_doc_prefix_are_different() -> None:
    """Query and document prefixes must be distinct."""
    assert QUERY_PREFIX != DOC_PREFIX

def test_semantic_similarity_with_correct_prefix() -> None:
    """Relevant doc must score higher than irrelevant doc."""
    q = embed_query("アリストテレスの歩行習慣について")
    d_relevant = embed_document("ペリパトス学派は歩きながら議論した")
    d_irrelevant = embed_document("量子コンピューターの計算速度")
    assert cosine_sim(q, d_relevant) > cosine_sim(q, d_irrelevant) + 0.3
```

### ルール 7: memory_strength の単体テスト

```python
# tests/test_memory/test_retrieval.py
from erre_sandbox.memory.retrieval import compute_memory_strength

def test_memory_decays_over_time() -> None:
    """Strength must decrease as days increase."""
    s_fresh = compute_memory_strength(importance=8.0, days_since=0.0, recall_count=0)
    s_old   = compute_memory_strength(importance=8.0, days_since=30.0, recall_count=0)
    assert s_fresh > s_old

def test_recall_increases_strength() -> None:
    """Recall count bonus must increase strength."""
    s_no_recall  = compute_memory_strength(importance=5.0, days_since=1.0, recall_count=0)
    s_recalled   = compute_memory_strength(importance=5.0, days_since=1.0, recall_count=5)
    assert s_recalled > s_no_recall
```

## チェックリスト

- [ ] テストファイルが `tests/test_[module]/test_[file].py` の構造を守っているか
- [ ] 非同期テストに `@pytest.mark.asyncio` が付いているか
- [ ] 共通フィクスチャが `conftest.py` に集約されているか
- [ ] LLM 推論を単体テストでモックしているか
- [ ] 埋め込みプレフィックステストが `tests/test_memory/test_embedding_prefix.py` にあるか
- [ ] `pytest` が通るか (`uv run pytest`)
- [ ] `ruff check tests/` が通るか

## 補足資料

- `examples.md` — conftest.py の全フィクスチャ例と統合テストの書き方

## 関連する他の Skill

- `python-standards` — テストコードでも同じ Python 規約が適用される
- `implementation-workflow` — Step F (テストと検証) でこの Skill を参照

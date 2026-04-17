# Test Standards — 実装例集

---

## 例 1: conftest.py の全フィクスチャ

```python
# tests/conftest.py
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from erre_sandbox.schemas import (
    AgentState,
    Biography,
    Emotion,
    ERREMode,
    Physical,
    Traits,
)


# ── AgentState ファクトリ ──────────────────────────────────────────────

@pytest.fixture
def agent_state_kant() -> AgentState:
    """Immanuel Kant persona in default state."""
    return AgentState(
        bio=Biography(
            name="Immanuel Kant",
            era="1724-1804",
            primary_corpus_refs=["kuehn2001", "kant_kritik_1781"],
            cognitive_habits=[
                "15:30±5min walk 60-75min",
                "nasal breathing only during walk",
                "no conversation on return",
            ],
        ),
        traits=Traits(conscientiousness=0.9, openness=0.8),
        physical=Physical(fatigue=20, focus=70, location="study"),
        erre=ERREMode(mode="deep_work", dmn_bias=-0.2),
    )


@pytest.fixture
def agent_state_nietzsche() -> AgentState:
    """Friedrich Nietzsche persona in peripatetic mode."""
    return AgentState(
        bio=Biography(
            name="Friedrich Nietzsche",
            era="1844-1900",
            primary_corpus_refs=["nietzsche_gotzendammerung_1889"],
            cognitive_habits=[
                "long mountain walks 6-8h",
                "short aphorism generation during walk",
                "alternating high arousal / complete rest",
            ],
        ),
        traits=Traits(openness=0.95, neuroticism=0.7),
        physical=Physical(fatigue=30, focus=80, location="peripatos"),
        erre=ERREMode(mode="peripatetic", dmn_bias=0.4,
                      sampling_overrides={"temperature": 0.3, "top_p": 0.05}),
    )


@pytest.fixture
def agent_state_rikyu() -> AgentState:
    """Sen no Rikyu persona in chashitsu mode."""
    return AgentState(
        bio=Biography(
            name="Sen no Rikyu",
            era="1522-1591",
            primary_corpus_refs=["ii_chanoyu_c1858"],
            cognitive_habits=[
                "ichigo ichie — each meeting unrepeatable",
                "silence as primary communication",
                "wabi-sabi aesthetic in all choices",
            ],
        ),
        traits=Traits(agreeableness=0.8, openness=0.9),
        physical=Physical(fatigue=10, focus=90, location="chashitsu"),
        emotion=Emotion(valence=0.2, arousal=-0.3, plutchik="trust"),
        erre=ERREMode(mode="chashitsu", dmn_bias=-0.4,
                      sampling_overrides={"temperature": -0.2, "top_p": -0.05}),
    )


# ── データベース ──────────────────────────────────────────────────────

@pytest.fixture
def tmp_sqlite_db(tmp_path: Path):
    """Temporary sqlite-vec DB. Yields open connection, closes after test."""
    db_path = tmp_path / "test_erre.db"
    conn = sqlite3.connect(str(db_path))
    conn.enable_load_extension(True)
    conn.execute("SELECT load_extension('sqlite_vec')")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY,
            agent_id TEXT NOT NULL,
            content TEXT NOT NULL,
            importance REAL NOT NULL,
            tick INTEGER NOT NULL,
            embedding BLOB
        )
    """)
    conn.commit()
    yield conn
    conn.close()


# ── LLM モック ────────────────────────────────────────────────────────

@pytest.fixture
def mock_llm_response():
    """Default mock LLM response for cognition tests."""
    return {
        "action": "walk",
        "speech": None,
        "reflection": None,
        "importance_self_score": 5,
    }
```

---

## 例 2: スキーマ検証テスト (TDD 先書き)

```python
# tests/test_schemas.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from erre_sandbox.schemas import Physical, Traits, ERREMode


class TestPhysical:
    def test_fatigue_clamps_to_100(self) -> None:
        with pytest.raises(ValidationError):
            Physical(fatigue=101)

    def test_fatigue_clamps_to_0(self) -> None:
        with pytest.raises(ValidationError):
            Physical(fatigue=-1)

    def test_location_must_be_valid_zone(self) -> None:
        with pytest.raises(ValidationError):
            Physical(location="office")  # 許可されていないゾーン


class TestERREMode:
    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValidationError):
            ERREMode(mode="invalid_mode")

    def test_dmn_bias_range(self) -> None:
        with pytest.raises(ValidationError):
            ERREMode(dmn_bias=1.5)    # -1.0〜1.0 の範囲外

    def test_sampling_overrides_default_empty(self) -> None:
        mode = ERREMode()
        assert mode.sampling_overrides == {}


class TestTraits:
    def test_shuhari_stage_default_is_shu(self) -> None:
        traits = Traits()
        assert traits.shuhari_stage == "shu"

    def test_wabi_must_be_unit_range(self) -> None:
        with pytest.raises(ValidationError):
            Traits(wabi=2.0)
```

---

## 例 3: 統合テスト (Ollama 使用、CI ではスキップ)

```python
# tests/test_cognition/test_integration.py
from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_cognition_cycle_completes(agent_state_kant) -> None:
    """Full cycle: observe → retrieve → prompt → act. Requires Ollama."""
    from erre_sandbox.cognition.cycle import run_cycle
    result = await run_cycle(agent_state_kant)
    assert result is not None
    assert result.action in {"walk", "sit", "speak", "reflect", "idle"}
```

`pytest.ini` または `pyproject.toml` で integration マークを登録:

```toml
[tool.pytest.ini_options]
markers = [
    "integration: requires external services (Ollama, SGLang)",
    "slow: tests taking > 5 seconds",
]
```

CI では `pytest -m "not integration"` で統合テストをスキップ。

---

## 例 4: 記憶検索の統合テスト (sqlite-vec 使用)

```python
# tests/test_memory/test_store.py
from __future__ import annotations

import pytest

from erre_sandbox.memory.store import MemoryStore
from erre_sandbox.memory.embedding import embed_document


@pytest.mark.asyncio
async def test_add_and_retrieve_memory(tmp_sqlite_db) -> None:
    store = MemoryStore(conn=tmp_sqlite_db)
    await store.add(
        agent_id="kant",
        content="今日の散歩で三批判書の構成が定まった",
        importance=9.0,
        tick=100,
    )
    results = await store.retrieve(
        agent_id="kant",
        query="散歩と思考",
        k=3,
    )
    assert len(results) >= 1
    assert "散歩" in results[0].content or "批判" in results[0].content
```

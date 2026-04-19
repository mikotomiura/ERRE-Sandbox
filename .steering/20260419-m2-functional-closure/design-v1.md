# 設計 — m2-functional-closure

## 0. 現状インベントリ (Explore 結果、`/reimagine` 前の前提条件)

本タスク着手前に Explore agent で `src/erre_sandbox/` 配下を網羅調査。
結果を設計判断の ground truth として記録。

### 0.1 `_RuntimeLike` Protocol (差替対象の interface)

```python
# src/erre_sandbox/integration/gateway.py:91-99
class _RuntimeLike(Protocol):
    async def recv_envelope(self) -> ControlEnvelope: ...
```

- `_NullRuntime` (L444-458) が placeholder 実装
- `make_app(runtime: _RuntimeLike | None = None)` で DI
- `_broadcaster()` lifespan が `await runtime.recv_envelope()` を無限 loop

**判断**: DI 方向 (gateway が runtime を受け取る) は確定。reimagine でこの軸は議論不要。

### 0.2 既存モジュールの public API

| モジュール | 主要クラス / 関数 | 役割 |
|---|---|---|
| `world/` | `WorldRuntime` (async scheduler) | tick 駆動。physics_hz=30.0 / cognition_period_s=10.0 設定済。MVP 検収条件と完全整合 |
| `world/` | `WorldRuntime.register_agent(state, persona)` | Agent 登録 |
| `world/` | `AgentRuntime` (dataclass) / `Kinematics` | Agent 状態 (position, destination, speed_mps=1.3) |
| `memory/` | `MemoryStore(db_path, embed_dim=768)` | sqlite-vec backed. `async add(entry, embedding)` / `async close()` |
| `inference/` | `OllamaChatClient(model="qwen3:8b", endpoint=":11434")` | `async chat(messages, sampling)` |
| `cognition/` | `CognitionCycle.step(agent_state, persona, observations)` | 1 サイクル full pipeline |
| `schemas.py` | `WorldTickMsg` / `MoveMsg` / `AgentUpdateMsg` / ControlEnvelope union | `0.1.0-m2` |
| `integration/gateway.py` | `make_app(runtime)` / `_main()` (uvicorn factory) | WS gateway |

### 0.3 欠落しているピース

本タスクで埋めるのは以下 3 点のみ:

1. **`src/erre_sandbox/__main__.py` が存在しない** → orchestrator entry point 欠落
2. **`pyproject.toml` の `[project.scripts]` が未設定** → `python -m erre_sandbox` で起動できるが `erre-sandbox` コマンドは未提供
3. **WorldRuntime と make_app を wire up する glue が無い** (既存 `_main()` は `_NullRuntime` を使う factory mode のみ)

### 0.4 既存 wire-up の参考実装

`tests/test_integration/conftest.py` の `MockRuntime` が唯一の wire-up 例:

```python
class MockRuntime:
    async def recv_envelope(self) -> ControlEnvelope:
        return await self._queue.get()
```

統合テストは `make_app(runtime=mock_runtime)` fixture を使用。本タスクは
**MockRuntime の位置に real WorldRuntime を差し込む**のが本質。

### 0.5 Reimagine で議論すべき真の軸 (DI 以外)

| 軸 | A 案 | B 案 |
|---|---|---|
| Orchestrator 配置 | `__main__.py` 1 ファイル | `runtime.py` + 薄い `__main__.py` |
| Wire-up 責務 | WorldRuntime ctor に依存を注入 | runtime.py が明示的に wire |
| MVP §4.4 #1「inference server listen」の解釈 | gateway 8000 = inference 配信元 (pragmatic) | 別 server 立ち (literal) |
| Persona 読込 | `__main__` が YAML を読んで WorldRuntime に渡す | WorldRuntime factory 内部で YAML ロード |
| 推論 connect 戦略 | 起動時 fail-fast (Ollama 未起動 → crash) | lazy connect (初回 cognition で retry) |

---

## 1. 実装アプローチ (v1 — 素直な単一ファイル orchestrator)

**一言で言うと**: 新規コードは `__main__.py` 1 ファイルのみ。WorldRuntime を constructor
injection で組み立て、既存 `_main()` と同じ uvicorn factory mode で起動する。変更量を
最小化し、MVP 完了だけを目的として動かす。

### 1.1 採用軸 (A 列)

| 軸 | v1 採択 |
|---|---|
| Orchestrator 配置 | `__main__.py` 1 ファイルのみ |
| Wire-up 責務 | `WorldRuntime(memory=..., inference=..., cognition=..., personas=[...])` constructor injection |
| MVP §4.4 #1 解釈 | gateway 8000 が inference 配信元 (pragmatic)。`inference/server.py` は新設せず |
| Persona 読込 | `__main__.py` が `personas/kant.yaml` を直接 `yaml.safe_load()` して `PersonaSpec` を組立、`WorldRuntime` に渡す |
| 推論 connect 戦略 | 起動時 fail-fast。`OllamaChatClient.health_check()` を追加し最初に叩く。失敗 → SystemExit(2) |
| Server 起動 | 既存 `gateway._main()` と同じ `uvicorn.run(app, host, port)` を `__main__.py` から呼ぶ |
| Lifecycle | `try/finally` + `await memory.close()` のシンプルな手書き |

### 1.2 骨格擬似コード

```python
# src/erre_sandbox/__main__.py
import asyncio, sys, uvicorn, yaml
from pathlib import Path
from erre_sandbox.memory import MemoryStore
from erre_sandbox.inference import OllamaChatClient
from erre_sandbox.cognition import CognitionCycle
from erre_sandbox.world import WorldRuntime
from erre_sandbox.integration.gateway import make_app
from erre_sandbox.schemas import PersonaSpec, AgentState, Zone

async def amain(host: str, port: int) -> None:
    persona = PersonaSpec.model_validate(
        yaml.safe_load(Path("personas/kant.yaml").read_text())
    )
    memory = MemoryStore(db_path="var/kant.db")
    inference = OllamaChatClient()  # default qwen3:8b
    await inference.health_check()  # fail-fast
    cognition = CognitionCycle(memory=memory, inference=inference)
    runtime = WorldRuntime(
        memory=memory, inference=inference, cognition=cognition,
    )
    agent_state = AgentState(agent_id="kant", zone=Zone.PERIPATOS, ...)
    runtime.register_agent(agent_state, persona)
    try:
        app = make_app(runtime=runtime)
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        runtime_task = asyncio.create_task(runtime.run())
        try:
            await server.serve()
        finally:
            runtime_task.cancel()
    finally:
        await memory.close()

def cli() -> None:
    asyncio.run(amain(host="0.0.0.0", port=8000))

if __name__ == "__main__":
    cli()
```

### 1.3 長所 / 短所

**長所**
- 新規ファイル 1 つ。レビュー量最小。git revert が容易
- MVP 要件との対応が一目瞭然 (1 ファイルだけ追えばいい)
- 既存 `_main()` pattern と対称的で学習コスト低

**短所**
- Lifecycle が手書き (AsyncExitStack を使わない) のため、failure path で
  resource leak のリスクが残る (e.g. inference 生成後に runtime 組立で例外 → inference 未 close)
- orchestrator 関数が約 40-50 行になり、設計責務 (YAML 読込 / DI 組立 /
  server 起動 / teardown) が 1 関数に圧縮される
- テスト時に `amain()` 全体 mock は辛い。unit test は限定的
- M4 (3-agent + multi-persona YAML) 拡張時に `__main__.py` が肥大化しやすい
- `inference/server.py` 未設置のため MVP 検収条件 #1 の literal 読みには
  「gateway が兼務」の説明責任が生じる

## 2. 変更対象

*(/reimagine 後に確定)*

### 2.1 修正するファイル

- `src/erre_sandbox/integration/gateway.py` — `_NullRuntime` 定義は残すが
  `_main()` に real WorldRuntime 組み立てルートを追加するか否かは要決定
- `pyproject.toml` — `[project.scripts]` に entry point 追加候補
- `docs/architecture.md` — `_NullRuntime` 注意書きは MVP 完了で文言トーン変更
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` — §4.4 4 項目を `[x]`

### 2.2 新規作成するファイル

*(/reimagine 後に確定。最低限 `__main__.py`、可能性あり `runtime.py` / `main.py`)*

### 2.3 削除するファイル

なし。`_NullRuntime` は uvicorn factory mode のために保持。

## 3. 影響範囲

- **既存テスト**: `tests/test_integration/*` は MockRuntime を継続使用。本タスク
  で real WorldRuntime が入っても既存テストは変更不要
- **Godot 側**: 変更なし (schema_version 0.1.0-m2 据置)
- **G-GEAR 運用**: `ollama serve` + `python -m erre_sandbox` の 2 プロセス起動
  が最小構成として確定する

## 4. 既存パターンとの整合性

- `make_app(runtime=...)` constructor injection をそのまま活用
- 既存の async context manager / lifespan パターンを踏襲
- `OllamaChatClient` / `MemoryStore` / `CognitionCycle` は `async with` or 明示
  `close()` で lifecycle 管理 — orchestrator でも同パターン

## 5. テスト戦略

- **単体テスト**: orchestrator の boot/shutdown が例外なく完了すること (mock
  ollama / in-memory db で)
- **統合テスト**: WorldTickMsg が 30Hz で queue に enqueue されることを 1s
  サンプリングで確認 (ollama は mock で OK)
- **E2E テスト (手動 evidence)**: G-GEAR + MacBook Godot live 視認。MVP §4.4 4 項目
  全 PASS の evidence を `evidence/` に格納
- `uv run pytest` 全緑を boot gate とする

## 6. ロールバック計画

- `__main__.py` 新規追加なので git revert で即時ロールバック可能
- `_NullRuntime` を残すため uvicorn factory mode は無傷で継続利用可能
- `v0.1.1-m2` tag も revert 可 (ただし GitHub Release を作った場合はそちらも
  削除要)

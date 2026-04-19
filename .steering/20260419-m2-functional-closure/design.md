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

## 1. 実装アプローチ (採用 — ハイブリッド: v2 lifecycle safety + v1 最小ファイル数)

**一言で言うと**: Composition root を `bootstrap.py` に分離し、`__main__.py` は
argparse CLI shell に徹する **2 ファイル構成**。`contextlib.AsyncExitStack` +
`asyncio.TaskGroup` + SIGINT/SIGTERM handler で構造的 lifecycle safety を確保。
ただし BootConfig dataclass と persona loader は `bootstrap.py` 内に private
関数として内蔵し (M4 拡張時に切り出し)、**YAGNI を抑える**。

### 1.1 モジュール配置

```
src/erre_sandbox/
├─ __main__.py      # 新規: ~20 行。argparse + asyncio.run(bootstrap(cfg))
└─ bootstrap.py     # 新規: ~100 行。composition root + private helpers
                    #   ├─ @dataclass(frozen=True) BootConfig (inline)
                    #   ├─ _load_kant_persona() -> PersonaSpec (inline private)
                    #   ├─ _build_kant_agent_state() -> AgentState (inline private)
                    #   └─ async def bootstrap(cfg: BootConfig) -> None
```

既存モジュール (`world/`, `memory/`, `inference/`, `cognition/`, `integration/`) には
**touch しない**。

### 1.2 Composition root (bootstrap.py 骨格)

```python
# src/erre_sandbox/bootstrap.py
from __future__ import annotations
import asyncio, signal, yaml
from contextlib import AsyncExitStack, suppress
from dataclasses import dataclass, field
from pathlib import Path
import uvicorn

from .memory import MemoryStore
from .inference import OllamaChatClient
from .cognition import CognitionCycle
from .world import WorldRuntime
from .integration.gateway import make_app
from .schemas import AgentState, PersonaSpec, Zone


@dataclass(frozen=True)
class BootConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    db_path: str = "var/kant.db"
    model: str = "qwen3:8b"
    ollama_url: str = "http://127.0.0.1:11434"
    check_ollama: bool = True
    log_level: str = "info"
    personas_dir: Path = field(default_factory=lambda: Path("personas"))


def _load_kant_persona(cfg: BootConfig) -> PersonaSpec:
    data = yaml.safe_load((cfg.personas_dir / "kant.yaml").read_text())
    return PersonaSpec.model_validate(data)


def _build_kant_agent_state() -> AgentState:
    return AgentState(agent_id="kant", zone=Zone.PERIPATOS, ...)


async def bootstrap(cfg: BootConfig) -> None:
    async with AsyncExitStack() as stack:
        memory = MemoryStore(db_path=cfg.db_path)
        stack.push_async_callback(memory.close)

        inference = OllamaChatClient(model=cfg.model, endpoint=cfg.ollama_url)
        if cfg.check_ollama:
            await inference.health_check()  # fail-fast

        cognition = CognitionCycle(memory=memory, inference=inference)
        runtime = WorldRuntime(
            memory=memory, inference=inference, cognition=cognition,
            physics_hz=30.0, cognition_period_s=10.0,
        )
        runtime.register_agent(_build_kant_agent_state(), _load_kant_persona(cfg))

        app = make_app(runtime=runtime)
        server = uvicorn.Server(uvicorn.Config(
            app, host=cfg.host, port=cfg.port,
            log_level=cfg.log_level, lifespan="on",
        ))

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        async with asyncio.TaskGroup() as tg:
            runtime_task = tg.create_task(runtime.run(), name="world-runtime")
            server_task = tg.create_task(server.serve(), name="uvicorn")
            stop_waiter = tg.create_task(stop.wait(), name="signal-wait")
            done, _ = await asyncio.wait(
                {runtime_task, server_task, stop_waiter},
                return_when=asyncio.FIRST_COMPLETED,
            )
            server.should_exit = True
            runtime_task.cancel()
            for t in (runtime_task, server_task):
                with suppress(asyncio.CancelledError, Exception):
                    await t
```

### 1.3 CLI shell (`__main__.py`) 骨格

```python
# src/erre_sandbox/__main__.py
from __future__ import annotations
import argparse, asyncio, sys
from .bootstrap import bootstrap, BootConfig


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="erre-sandbox")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", dest="db_path", default="var/kant.db")
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--skip-health-check", dest="check_ollama",
                        action="store_false", default=True)
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args(argv)
    cfg = BootConfig(
        host=args.host, port=args.port, db_path=args.db_path,
        model=args.model, ollama_url=args.ollama_url,
        check_ollama=args.check_ollama, log_level=args.log_level,
    )
    asyncio.run(bootstrap(cfg))
    return 0


if __name__ == "__main__":
    sys.exit(cli())
```

### 1.4 採用軸 (ハイブリッド決着)

| 軸 | 採択 | 根拠 |
|---|---|---|
| Orchestrator 配置 | `bootstrap.py` + 薄い `__main__.py` の **2 分割** | v2 の testability を採用、config.py/_loader.py への過剰分離は M4 まで保留 |
| Wire-up 責務 | `AsyncExitStack.push_async_callback()` でリソース登録 | 例外経路でも必ず close() される。try/finally 手書き (v1) は T19 silent failure 教訓から回避 |
| MVP §4.4 #1 解釈 | gateway 8000 = inference 配信元 (pragmatic)。`docs/architecture.md` §Inference を補足 | 別 server は M7 SGLang 移行時に再検討 |
| Persona 読込 | `bootstrap.py` 内の private fn `_load_kant_persona(cfg)` | 1 persona MVP では module 切り出し過剰。M4 で `personas/_loader.py` として切り出し |
| 推論 connect 戦略 | **デフォルト fail-fast**、CLI `--skip-health-check` で offline テスト可能 | オペレータが早期に気付ける / CI は offline |
| Supervision | `asyncio.TaskGroup` で runtime + uvicorn + stop-waiter 3 task を対等 wait | どれかが終了 → 全体終了。T19 ghost session 再発防止 |
| Shutdown | SIGINT/SIGTERM → `asyncio.Event.set()` → `server.should_exit=True` + runtime cancel | Docker/systemd で graceful。ghost session 残留なし |
| Config | `@dataclass(frozen=True) BootConfig` を `bootstrap.py` 内定義 | イミュータブル設定。argparse から直接コンストラクト |

### 1.5 長所 / 短所 (ハイブリッド)

**長所**
- bootstrap() が `BootConfig` 引数だけで完結 → pytest で mock 注入が自然
- AsyncExitStack により resource leak が構造的に防げる
- TaskGroup で runtime 死亡時も uvicorn が落ちる (T19 silent failure 再発防止)
- SIGTERM 対応で systemd / Docker 運用時の挙動が予測可能
- M4 (3-agent) 拡張時は `bootstrap.py` 内の `register_agent()` をループ化するだけ
- 新規ファイル 2 本のみ。PR レビュー量は v2 より 50% 少ない

**短所 / 残存リスク**
- `asyncio.TaskGroup` + signal handler + AsyncExitStack の合成は Python 3.11 固定 (既存と同等、許容)
- bootstrap.py 内に BootConfig / persona loader / agent state builder を抱え込むため、
  M4 時点で config.py / personas/_loader.py に切り出す再リファクタが発生
  (small, 1 PR で完結する想定)
- FastAPI lifespan を使わず自前 supervision のため、将来 FastAPI startup event を
  併用する際は二重管理 (bootstrap と app.lifespan) を意識する必要あり

## 2. 変更対象

### 2.1 修正するファイル

- `pyproject.toml` — `[project.scripts]` に `erre-sandbox = "erre_sandbox.__main__:cli"` 追加
- `src/erre_sandbox/inference/ollama_adapter.py` — `async def health_check()` を追加
  (既存 method が無ければ。`POST /api/tags` 1 発)
- `docs/architecture.md` §Gateway — `_NullRuntime` 注意書きのトーン調整 (MVP 完了で
  real runtime が標準ルート、`_NullRuntime` は uvicorn factory mode の test 時のみに)
- `docs/architecture.md` §Inference — MVP phase での "inference は gateway WS 経由"
  stance を明文化 (M7 SGLang 移行で別 server 化する計画を参照付き)
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §4.4 — 4 checkbox `[x]` + T21
  closeout note

### 2.2 新規作成するファイル

- `src/erre_sandbox/__main__.py` (~20 行) — argparse CLI shell + `asyncio.run(bootstrap(cfg))`
- `src/erre_sandbox/bootstrap.py` (~100 行) — `BootConfig` dataclass + `_load_kant_persona()`
  + `_build_kant_agent_state()` + `bootstrap(cfg)` composition root
- `tests/test_bootstrap.py` (~80 行) — bootstrap unit/integration テスト (mock ollama 使用)
- `personas/kant.yaml` — 既存なら変更なし、無ければ最小仕様で新設
- `var/` — runtime DB 格納ディレクトリ (gitignore 済確認)

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

### 5.1 単体テスト

- `tests/test_bootstrap.py::test_bootstrap_boots_and_shutdowns_cleanly`:
  `--skip-health-check` + `:memory:` DB + mock OllamaChatClient で `bootstrap()`
  を 200ms だけ走らせ、SIGTERM 相当 (`stop_event.set()`) で graceful 終了すること
- `tests/test_bootstrap.py::test_bootstrap_fails_fast_on_ollama_down`:
  health_check が raise → `bootstrap()` が SystemExit or specific exception
- `tests/test_bootstrap.py::test_load_kant_persona_from_fixture`:
  `personas/kant.yaml` (fixture コピー) を読み `PersonaSpec` が返る

### 5.2 統合テスト

- `tests/test_integration/test_scenario_kant_walker.py` (新規):
  bootstrap 起動後 WS client を疑似接続し **HandshakeMsg → WorldTickMsg 受信
  (30 tick/s)** を 3s 観測
- 既存 `tests/test_integration/test_scenario_*.py` は MockRuntime 継続使用 (変更なし)

### 5.3 E2E (手動 evidence)

- G-GEAR + MacBook Godot live 視認。MVP §4.4 4 項目全 PASS の evidence を
  `.steering/20260419-m2-functional-closure/evidence/` に格納:
  - `godot-walking-YYYYMMDD-HHMMSS.mp4` or `.gif` (avatar 30Hz 周回)
  - `gateway-log-cognition-YYYYMMDD-HHMMSS.log` (10s ごと `[cognition]` 1 行 × 6 以上)
  - `sqlite-vec-dump-YYYYMMDD-HHMMSS.txt` (episodic_memory >= 5 rows)
  - `ollama-listen-YYYYMMDD-HHMMSS.log` (`ollama serve` + gateway listen 確認)

### 5.4 Gate

`uv run pytest` 緑 → G-GEAR 側 `uv run python -m erre_sandbox` 正常起動 →
Godot live 接続で 30Hz avatar 視認 → 60s 以上動かして evidence 収集 →
commit → PR → main merge → `v0.1.1-m2` tag。

## 6. ロールバック計画

- 新規ファイル 2 本 (`__main__.py`, `bootstrap.py`) のみなので git revert で即時戻せる
- `_NullRuntime` は残るため uvicorn factory mode は無傷で継続
- `pyproject.toml` の entry point 追加も revert 可
- `v0.1.1-m2` tag も revert 可 (GitHub Release を作った場合はそちらも削除要)
- 既存 T10-T14 モジュールに touch しないので回帰リスク極小

## 7. 設計判断の履歴

- 初回案 (design-v1.md, "素直な単一ファイル orchestrator") と再生成案 (design.md §1,
  "Composition Root + Lifecycle-First") を `/reimagine` で比較
- 比較詳細: `design-comparison.md`
- **採用: ハイブリッド** (v2 の lifecycle safety を採り、config/loader の module 分離は M4 へ保留)
- 根拠:
  1. T19 で経験した silent failure (ghost session) と同種の問題を MVP 段階で
     構造的に防ぐ価値 (AsyncExitStack + TaskGroup + SIGTERM) > "ファイル数最小" の
     bragging right
  2. 一方で `config.py` / `personas/_loader.py` の分離は 1-Kant-walker MVP には
     過剰 (YAGNI)。M4 の multi-agent 化で初めて切り出し動機が明確になる
  3. ハイブリッドは **safety の享受** と **ファイル数の最小化** を両立し、
     M4 移行時の追加コストも最小

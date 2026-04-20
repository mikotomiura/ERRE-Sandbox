# 設計 — m4-multi-agent-orchestrator (v1 草案)

> **status**: v1 (/reimagine で破棄予定)

## 実装アプローチ

### 1. bootstrap の multi-agent 化
- `_load_kant_persona` → `_load_persona(cfg, persona_id)` に generalise
- `_build_kant_initial_state` → `_build_initial_state(spec, persona)` に generalise
- `bootstrap()` の中で `cfg.agents` が非空なら loop で register、空なら従来 Kant 1 体

### 2. CLI `--personas kant,nietzsche,rikyu`
`__main__.py` に option 追加、`persona.preferred_zones[0]` を default initial_zone とする
AgentSpec を組み立てる。agent_id は `f"a_{persona_id}_001"`。

### 3. InMemoryDialogScheduler
`src/erre_sandbox/world/dialog.py` (新規) に COOLDOWN_TICKS=30、TIMEOUT_TICKS=6 の
in-memory scheduler を置く。state = `_open: dict[str, _OpenDialog]` +
`_pair_to_id: dict[frozenset[str], str]` + `_last_close_tick`。

### 4. WorldRuntime 配線 (保守的)
`WorldRuntime.__init__(dialog_scheduler: DialogScheduler | None = None)` で inject
可能にするが、**自動 firing は行わない**。テストと後続タスクが外から explicit に呼ぶ。

### 5. テスト
- `tests/test_world/test_dialog_scheduler.py`: unit 10 本
- `tests/test_bootstrap.py` に 3-agent smoke test 追加 (Ollama mock)

### 6. ドキュメント
- docs/architecture.md §Simulation Layer / §ControlEnvelope
- docs/functional-design.md §4 M4

## 変更対象

### 修正
- `src/erre_sandbox/bootstrap.py`
- `src/erre_sandbox/__main__.py`
- `src/erre_sandbox/world/tick.py` (optional inject)
- `src/erre_sandbox/world/__init__.py`
- `docs/architecture.md`
- `docs/functional-design.md`

### 新規
- `src/erre_sandbox/world/dialog.py`
- `tests/test_world/test_dialog_scheduler.py`
- `tests/test_bootstrap.py` (既存か新規要確認)

## 影響範囲

- BootConfig.agents が初めて使われる (M2 back-compat は empty tuple)
- WorldRuntime の optional param 追加 (既存テスト影響なし)

## テスト戦略

Ollama / embedding mock で完結。live は G-GEAR で別タスク。

## ロールバック計画

PR revert。schema / DB 無変更。

## 未解決の論点 (/reimagine で検討)

1. **DialogScheduler の所属層**: `world/` / `cognition/` / `integration/` どこ所属?
2. **dialog_id 生成の責任**: scheduler / caller / gateway?
3. **DialogInitiateMsg に dialog_id を足す foundation 破壊**: 要検討
4. **dialog 発火 trigger の実装場所**: WorldRuntime hook / 独立 scheduler loop / explicit
5. **Persona loading のキャッシュ**: 同 persona を複数 agent が使う場合
6. **agent_id 命名**: `a_{persona_id}_001` 固定 / CLI で指定可能
7. **dialog transcript の永続化**: in-memory only / sqlite
8. **live 検証用 smoke スクリプト**: `scripts/run_m4_acceptance.py` を作るか

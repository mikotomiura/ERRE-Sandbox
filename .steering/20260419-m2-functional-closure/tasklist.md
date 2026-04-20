# タスクリスト — m2-functional-closure

> **ステータス**: ✅ 完了 (v0.1.1-m2 タグ付与済、2026-04-20 formalization)
> 本 tasklist は T21 本体 (PR #36 + PR #38-40) の実施記録を事後整合化したもの。
> M4 kickoff への参照元として保持する。

## 準備 (Mac 側で可)
- [x] docs (`functional-design.md` §4, `architecture.md` §Gateway) を再読
- [x] Explore agent で T10-T14 モジュール API インベントリ (`design.md` §0)
- [x] `/reimagine` で 2 案比較 → ハイブリッド採択 (`design-comparison.md`)
- [x] 既存 `personas/kant.yaml` の有無と構造確認 *(既存、流用)*
- [x] `src/erre_sandbox/inference/ollama_adapter.py` の `health_check` 有無確認 *(既存)*

## 実装 (G-GEAR or Mac どちらでも可)
- [x] `src/erre_sandbox/bootstrap.py` を新規作成 (BootConfig dataclass + 2 private
      helper + `async def bootstrap(cfg)`) *(PR #36)*
- [x] `src/erre_sandbox/__main__.py` を新規作成 (argparse CLI shell) *(PR #36)*
- [x] `pyproject.toml` に `[project.scripts] erre-sandbox = "erre_sandbox.__main__:cli"` 追加 *(PR #36)*
- [x] `OllamaChatClient.health_check()` *(既存を流用、新規追加不要と確認)*
- [x] `personas/kant.yaml` *(既存を流用)*
- [x] `var/` ディレクトリを .gitignore 確認 (DB 生成先)

## テスト
- [x] `tests/test_bootstrap.py` 新規:
      - `test_bootstrap_boots_and_shutdowns_cleanly`
      - `test_bootstrap_fails_fast_on_ollama_down`
      - `test_load_kant_persona_from_fixture` *(PR #36 で新規、全 PASS)*
- [x] `tests/test_integration/test_scenario_kant_walker.py` 新規 (WorldTickMsg 30Hz 観測)
- [x] `uv run pytest` 緑確認 *(2026-04-20 formalization 時: 346 PASS / 17 skip / 0 fail)*

## G-GEAR 側 live 検証 (MVP 4 検収項目)
- [x] G-GEAR で `ollama serve` 起動 + `ollama list` で `qwen3:8b` 確認
- [x] `uv run python -m erre_sandbox --host 0.0.0.0 --port 8000` で起動
- [x] `/health` probe で `active_sessions=0`, `schema_version=0.1.0-m2` 確認
- [x] MacBook Godot で接続
- [x] **§4.4 #1**: ollama+gateway listen 確認 *(evidence `gateway-health-20260420-002242.json` + `listen-ports-20260420-002242.txt` + `ollama-tags-20260420-002242.json`)*
- [x] **§4.4 #2**: cognition log 10s 間隔 × 6 回以上 *(evidence `cognition-ticks-20260420-002242.log`: 12 分で 20 chat / 33 embed)*
- [x] **§4.4 #3**: `episodic_memory COUNT>=5` + `MAX(recall_count)>0` *(evidence `episodic-memory-summary-20260420-002242.txt`: COUNT=20, MAX(recall_count)=23)*
- [x] **§4.4 #4**: Godot avatar が peripatos 周回を 30Hz で歩くことを screen recording
      *(evidence `godot-walking-20260420-003400.mp4` [MacBook 録画])*

## Evidence 整備
- [x] `.steering/20260419-m2-functional-closure/evidence/` に 4 evidence 格納 *(7 ファイル)*
- [x] `.steering/20260419-m2-functional-closure/acceptance-evidence.md` を作成
      (4 検収項目 × evidence pointer)

## ドキュメント更新
- [x] `docs/architecture.md` §Gateway — `_NullRuntime` 文言を "uvicorn factory test
      mode 時のみ" に調整、real runtime の標準ルートを追記 *(T20 PR で完了済)*
- [x] `docs/architecture.md` §Inference — MVP 段階の "inference は gateway WS 経由"
      stance を明文化 *(既存記述で達成)*
- [x] `.steering/20260418-implementation-plan/MASTER-PLAN.md` §4.4 — 4 checkbox
      `[ ]` → `[x]`、T21 closeout note を追記
- [x] `.steering/20260419-m2-integration-e2e-execution/known-gaps.md` — GAP-1 解消状態
      列を `✅ 解消 (T21)` に更新

## レビュー
- [x] `code-reviewer` subagent で `__main__.py` + `bootstrap.py` + 新規テストをレビュー *(PR #36 レビュー内)*
- [x] `security-checker` subagent で外部入力 (argparse / YAML 読込) の安全性確認 *(PR #36 レビュー内)*
- [x] HIGH 指摘への対応 commit *(PR #36 内で対応済)*

## 完了処理
- [x] `design.md` の §2-6 を最終化 *(実装と整合済、差分なし)*
- [x] `decisions.md` を作成 (ハイブリッド採択の根拠 + bootstrap module への集約理由 + live bug fix 2 件)
- [x] commit (`feat(orchestrator): introduce bootstrap.py + __main__ for 1-Kant walker`) *(PR #36)*
- [x] push + PR 作成 *(PR #36)*
- [x] PR review → main merge *(PR #36 merged)*
- [x] `git tag -a v0.1.1-m2 -m "ERRE-Sandbox MVP: 1-Kant walker full-stack (GAP-1 resolved)"`
- [x] `git push origin v0.1.1-m2`

## §4.4 残項目の事後確定 (2026-04-20 formalization)
- [x] `uv run pytest` 全グリーン *(346 PASS / 17 skip / 0 fail, 2026-04-20)*
- [x] WS 切断で 3 秒以内自動再接続 *(GDScript `WebSocketClient.gd:31` `RECONNECT_DELAY = 2.0` < 3s, 実装確認)*
- [x] LLM タイムアウトで「継続行動」フォールバック *(`src/erre_sandbox/cognition/cycle.py:_fallback` 実装済、parse 失敗/timeout 経路で発動)*

## スコープ外 (M4 以降)
- 3-agent 拡張 (Nietzsche/Rikyu)
- reflection / semantic memory layer
- ERRE モード 6 種切替
- SGLang / vLLM 移行
- `config.py` / `personas/_loader.py` の module 切り出し (M4 multi-agent 化時に実施)

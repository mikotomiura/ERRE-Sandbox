# タスクリスト — m2-functional-closure

## 準備 (Mac 側で可)
- [x] docs (`functional-design.md` §4, `architecture.md` §Gateway) を再読
- [x] Explore agent で T10-T14 モジュール API インベントリ (`design.md` §0)
- [x] `/reimagine` で 2 案比較 → ハイブリッド採択 (`design-comparison.md`)
- [ ] 既存 `personas/kant.yaml` の有無と構造確認 (存在しなければ新設要件に変更)
- [ ] `src/erre_sandbox/inference/ollama_adapter.py` の `health_check` 有無確認

## 実装 (G-GEAR or Mac どちらでも可)
- [ ] `src/erre_sandbox/bootstrap.py` を新規作成 (BootConfig dataclass + 2 private
      helper + `async def bootstrap(cfg)`)
- [ ] `src/erre_sandbox/__main__.py` を新規作成 (argparse CLI shell)
- [ ] `pyproject.toml` に `[project.scripts] erre-sandbox = "erre_sandbox.__main__:cli"` 追加
- [ ] `OllamaChatClient.health_check()` を追加 (無ければ)
- [ ] `personas/kant.yaml` を整備 (存在しなければ最小仕様で新設)
- [ ] `var/` ディレクトリを .gitignore 確認 (DB 生成先)

## テスト
- [ ] `tests/test_bootstrap.py` 新規:
      - `test_bootstrap_boots_and_shutdowns_cleanly` (mock ollama, stop_event.set() で終了)
      - `test_bootstrap_fails_fast_on_ollama_down` (health_check raise で bootstrap 失敗)
      - `test_load_kant_persona_from_fixture`
- [ ] `tests/test_integration/test_scenario_kant_walker.py` 新規 (WorldTickMsg 30Hz 観測)
- [ ] `uv run pytest` 緑確認

## G-GEAR 側 live 検証 (MVP 4 検収項目)
- [ ] G-GEAR で `ollama serve` 起動 + `ollama list` で `qwen3:8b` 確認
- [ ] `uv run python -m erre_sandbox --host 0.0.0.0 --port 8000` で起動
- [ ] `/health` probe で `active_sessions=0`, `schema_version=0.1.0-m2` 確認
- [ ] MacBook Godot で接続
- [ ] **§4.4 #1**: ollama+gateway listen 確認 → evidence `ollama-listen-*.log`
- [ ] **§4.4 #2**: cognition log 10s 間隔 × 6 回以上 → evidence `gateway-log-cognition-*.log`
- [ ] **§4.4 #3**: `sqlite3 var/kant.db "SELECT COUNT(*) FROM episodic_memory;" >= 5`
      + `SELECT MAX(recall_count) FROM episodic_memory; > 0` → evidence `sqlite-vec-dump-*.txt`
- [ ] **§4.4 #4**: Godot avatar が peripatos 周回を 30Hz で歩くことを screen recording
      → evidence `godot-walking-*.mp4|gif`

## Evidence 整備
- [ ] `.steering/20260419-m2-functional-closure/evidence/` に 4 evidence 格納
- [ ] `.steering/20260419-m2-functional-closure/acceptance-evidence.md` を作成
      (4 検収項目 × evidence pointer)

## ドキュメント更新
- [ ] `docs/architecture.md` §Gateway — `_NullRuntime` 文言を "uvicorn factory test
      mode 時のみ" に調整、real runtime の標準ルートを追記
- [ ] `docs/architecture.md` §Inference — MVP 段階の "inference は gateway WS 経由"
      stance を明文化、M7 SGLang 移行計画へのリンク
- [ ] `.steering/20260418-implementation-plan/MASTER-PLAN.md` §4.4 — 4 checkbox
      `[ ]` → `[x]`、T21 closeout note を追記
- [ ] `.steering/20260419-m2-integration-e2e-execution/known-gaps.md` — GAP-1 解消状態
      列を `✅ 解消 (T21)` に更新

## レビュー
- [ ] `code-reviewer` subagent で `__main__.py` + `bootstrap.py` + 新規テストをレビュー
- [ ] `security-checker` subagent で外部入力 (argparse / YAML 読込) の安全性確認
- [ ] HIGH 指摘への対応 commit

## 完了処理
- [ ] `design.md` の §2-6 を最終化 (実装結果との整合性確認)
- [ ] `decisions.md` を作成 (ハイブリッド採択の根拠 + bootstrap module への集約理由)
- [ ] commit (`feat(orchestrator): introduce bootstrap.py + __main__ for 1-Kant walker`)
- [ ] push + PR 作成
- [ ] PR review → main merge
- [ ] `git tag -a v0.1.1-m2 -m "ERRE-Sandbox MVP: 1-Kant walker full-stack (GAP-1 resolved)"`
- [ ] `git push origin v0.1.1-m2`

## スコープ外 (M4 以降)
- 3-agent 拡張 (Nietzsche/Rikyu)
- reflection / semantic memory layer
- ERRE モード 6 種切替
- SGLang / vLLM 移行
- `config.py` / `personas/_loader.py` の module 切り出し (M4 multi-agent 化時に実施)

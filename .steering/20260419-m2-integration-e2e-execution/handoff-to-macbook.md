# MacBook 側セッションへの引き継ぎ — T19 実行フェーズ完了後

本 PR (T19 実行フェーズ, G-GEAR 側) で完了した範囲と、
MacBook 側で継続すべき項目を明示する。次セッションの起点として読む。

## G-GEAR 側で完了済 (本 PR)

- [x] `tests/test_integration/test_scenario_{walking,memory_write,tick_robustness}.py`
      11 件の `@pytest.mark.skip` を解除、Layer B 実装で全 PASS
- [x] `tests/test_integration/conftest.py` — `FakeEmbedder` /
      `memory_store_with_fake_embedder` / `M2Logger` / `m2_logger` fixture 追加
- [x] `tests/test_integration/_ws_helpers.py` — `client_handshake()` /
      `recv_envelope()` 共有ヘルパ新規
- [x] Layer C smoke run 1 回完了 (decisions.md D2 に記録)
  - Ollama `qwen3:8b` / `nomic-embed-text:latest` 存在確認
  - Gateway `python -m erre_sandbox.integration.gateway --port 8765` 起動確認
  - `/health` HTTP 200 + `schema_version: 0.1.0-m2` 確認
- [x] `uv run pytest` 329 passed / 23 skipped (全体)
- [x] `uv run ruff check` / `ruff format --check` / `mypy src` 全緑
- [x] `.gitignore` に `logs/` 追加

## MacBook 側で実施すべき項目

### 1. Godot 実機統合 (T20 ACC-SCENARIO-WALKING Live)

- [ ] MacBook で `git pull` して本ブランチをローカルに反映
- [ ] G-GEAR 側で gateway を起動 (`--host 0.0.0.0 --port 8000`)
- [ ] MacBook で Godot 4.6 を起動し `godot_project/scenes/MainScene.tscn` を Play
- [ ] `ws://g-gear.local:8000/ws/observe` (または IP 直指定) に接続成功を確認
- [ ] Avatar が Peripatos シーンで Tween 移動することを視認
- [ ] 30Hz 描画が安定 (WorldTickMsg を 1 Hz 受信できている) ことを確認
- [ ] disconnect/reconnect 実験: gateway を再起動して Godot の再接続を確認
- [ ] 結果を `.steering/20260419-m2-acceptance/` (次タスク) に screenshot + ログで記録

### 2. ACC-DOCS-UPDATED (T20)

- [ ] `docs/architecture.md` の §1 全体図 / §3 Gateway セクションを
      T14 完成版に更新 (WebSocket 契約の `SessionPhase` / `HANDSHAKE_TIMEOUT_S` 等
      の新定数を反映)
- [ ] `docs/glossary.md` に用語追加: `SessionPhase`, `MAX_ENVELOPE_BACKLOG`,
      `SCHEMA_VERSION_HEADER` (T14 PR #24 で導入)

### 3. ACC-TAG-READY (T20)

- [ ] `pyproject.toml` の `version = "0.0.1"` (現在) を `"0.1.0"` に更新
- [ ] `CITATION.cff` に `version: 0.1.0` / `date-released: 2026-04-XX` を記入
- [ ] `uv.lock` を再生成してコミット

### 4. M2 MVP タグ付与 (T20 本番作業)

- [ ] `/start-task m2-acceptance` で `.steering/20260419-m2-acceptance/`
      (または作業日) を作成
- [ ] `.steering/20260419-m2-integration-e2e/t20-acceptance-checklist.md` の
      15 項目を 1 件ずつ実行、結果を acceptance 記録に転記
- [ ] `git checkout main && git pull`
- [ ] `git tag -a v0.1.0-m2 -m "ERRE-Sandbox M2 MVP: 1 agent × 1 zone integration"`
- [ ] `git push origin v0.1.0-m2`
- [ ] `gh release create v0.1.0-m2 --title "v0.1.0-m2" --notes-file docs/release-notes/v0.1.0-m2.md`

### 5. 将来対応 (T20 スコープ外)

- [ ] `M2_LOG_PATH` env 付き `pytest tests/test_integration/` を 2 回実行し、
      出力 jsonl の diff が空であることを確認 (ACC-REPRO-SEED の相当動作、
      本 PR の Layer B では latency_ms が時刻依存で非決定論のため、
      本項は M7 observability で強化予定)

## 既知の制約・注意事項

- **Layer C 自動化は M7 以降**: 実 Ollama + 実 sqlite-vec の連続 CI テストは
  本 PR のスコープ外。本タスクでは smoke run 1 回のみ (decisions.md D2)
- **p50/p95 レイテンシ測定は手動**: `M2_LOG_PATH=logs/m2-acceptance-run.jsonl
  uv run pytest tests/test_integration/test_scenario_walking.py --count=20`
  を走らせて `jq` で集計する運用
- **Godot 側のテストは本 PR では未検証**: MacBook セッションで最初に着手すべき

## 参照

- 本タスク設計: `.steering/20260419-m2-integration-e2e-execution/design.md`
- 本タスク判断: `.steering/20260419-m2-integration-e2e-execution/decisions.md`
- T19 設計フェーズ (PR #23): `.steering/20260419-m2-integration-e2e/`
- T14 gateway 実装 (PR #24): `.steering/20260419-gateway-fastapi-ws/`
- T20 acceptance checklist: `.steering/20260419-m2-integration-e2e/t20-acceptance-checklist.md`
- M2 検収条件: `.steering/20260418-implementation-plan/MASTER-PLAN.md` §4.4

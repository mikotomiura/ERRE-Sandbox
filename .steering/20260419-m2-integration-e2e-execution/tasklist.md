# タスクリスト — T19 実行フェーズ

design.md の v1 採用 (reimagine 不適用) に基づき、以下の順で実施した。
G-GEAR 側作業は PR #27 で完了。MacBook 側 (Godot / docs / タグ) は
`handoff-to-macbook.md` に引き継ぎ。

## Phase A: 準備・設計記録

- [x] A1. `requirement.md` 記入 (ユーザー承認済)
- [x] A2. `design.md` 記入 (ユーザー承認済)
- [x] A3. `decisions.md` 作成 (D1-D5)
- [x] A4. `.gitignore` に `logs/` を追加
- [x] A5. `git checkout -b feature/m2-integration-e2e-execution`

## Phase B: conftest.py 拡張

- [x] B1. `FakeEmbedder` クラスを `tests/test_integration/conftest.py` に追加
      (SHA-256 ベース deterministic 768-d、`DOC_PREFIX` / `QUERY_PREFIX` 強制)
- [x] B2. `memory_store_with_fake_embedder` async fixture 追加
      (in-memory sqlite-vec + teardown close)
- [x] B3. `m2_logger` fixture 追加
      (`M2_LOG_PATH` env 未設定なら no-op、設定時は `<project>/logs/` 配下のみ許可する
      traversal-safe jsonl 書出し)
- [x] B4. `uv run pytest tests/test_integration/test_gateway.py` 回帰緑 (43 件)

## Phase C: test_scenario_walking.py 点灯

- [x] C1. `pytestmark = pytest.mark.skip(...)` 行を削除
- [x] C2. `_ws_helpers.py` 新規、`client_handshake()` / `recv_envelope()` を公開
- [x] C3. `test_s_walking_step0_world_registers_kant_in_peripatos` 実装
- [x] C4. `test_s_walking_step1_gateway_heartbeat` 実装
- [x] C5. `test_s_walking_step2_cognition_emits_move` 実装
- [x] C6. `test_s_walking_step3_godot_avatar_moves` 実装
- [x] C7. `uv run pytest tests/test_integration/test_scenario_walking.py -v` で 4 件 PASS

## Phase D: test_scenario_memory_write.py 点灯

- [x] D1. `pytestmark = pytest.mark.skip(...)` 行を削除
- [x] D2. `test_s_memory_write_steps_are_three` 実装
- [x] D3. `test_s_memory_write_writes_four_episodic_one_semantic` 実装
- [x] D4. `test_s_memory_write_embedding_prefix_applied` 実装
      (code-reviewer MED 6 対応: `fake_embedder` のみ依存に簡素化)
- [x] D5. `uv run pytest tests/test_integration/test_scenario_memory_write.py -v` で 3 件 PASS

## Phase E: test_scenario_tick_robustness.py 点灯

- [x] E1. `pytestmark = pytest.mark.skip(...)` 行を削除
- [x] E2. `test_s_tick_robustness_initial_agent_update` 実装
- [x] E3. `test_s_tick_robustness_tolerates_missed_heartbeat` 実装
      (code-reviewer MED 5 対応: 冗長 `not isinstance(ErrorMsg)` を削除)
- [x] E4. `test_s_tick_robustness_survives_reconnect` 実装
- [x] E5. `test_s_tick_robustness_memory_continuity` 実装
- [x] E6. `uv run pytest tests/test_integration/test_scenario_tick_robustness.py -v` で 4 件 PASS

## Phase F: CI 検証・Layer C smoke run

- [x] F1. `uv run pytest tests/test_integration/` 54 passed
- [x] F2. `uv run pytest` 全体 329 passed / 23 skipped
- [x] F3. `uv run ruff check` 緑
- [x] F4. `uv run ruff format --check` 緑
- [x] F5. `uv run mypy src` 緑
- [x] F6. Ollama list: qwen3:8b (5.2 GB) / nomic-embed-text (274 MB) 確認
- [x] F7. Gateway 起動 `--port 8765`、`/health` HTTP 200 確認、shutdown 確認
- [x] F8. decisions.md D2 に smoke run 結果追記、ログ `logs/m2-smoke-run-gateway-20260419.txt`

## Phase G: handoff 文書 + MASTER-PLAN sync

- [x] G1. `handoff-to-macbook.md` 作成 (Godot 実機検証 / ACC-DOCS-UPDATED /
      ACC-TAG-READY / v0.1.0-m2 タグの順序と参照先を列挙)
- [x] G2. `.steering/20260418-implementation-plan/tasklist.md` T19 行を
      `[x]` + 実行フェーズ完了サマリに更新 (commit 9cf373e で分離)

## Phase H: レビュー

- [x] H1. self-review (design / decisions / handoff の整合確認)
- [x] H2. code-reviewer subagent 起動 → HIGH 1 + MEDIUM 5 + LOW 3 を抽出
- [x] H3. HIGH 1 (M2Logger パストラバーサル) 対応: `_ALLOWED_LOG_ROOT` ガード + `M2LogPathError`
- [x] H4. MEDIUM 2/4/5/6 対応 (ユーザー承認済)、MEDIUM 3 TODO(T20) 記録、LOW defer

## Phase I: コミット・PR

- [x] I1. `git add` 実施 (tests/ / .gitignore / .steering/)
- [x] I2. commit df00a1e: `feat(integration): T19 execution — unskip scenario tests + Layer B/C smoke`
- [x] I3. commit 9cf373e: `chore(steering): sync MASTER-PLAN tasklist with T19 execution completion`
- [x] I4. `git push -u origin feature/m2-integration-e2e-execution`
- [x] I5. PR #27 作成 (https://github.com/mikotomiura/ERRE-Sandbox/pull/27)
- [x] I6. `/finish-task` 実行中 (本ファイル更新はその一部)

## ロールバック

```bash
git checkout main
git branch -D feature/m2-integration-e2e-execution
# tests/test_integration/ の skip マーカーが復活するのみ、src/ への影響はゼロ
```

## 未完了スコープ (MacBook 側、T19 本質完了条件)

本 PR (G-GEAR 側) では以下は **未実施**。詳細は `handoff-to-macbook.md` を参照:

- [ ] Godot 実機 `ws://g-gear.local:8000/ws/observe` 接続 + Avatar Tween 移動 + 30Hz 描画検証
- [ ] `docs/architecture.md` の §3 Gateway 節を T14 完成版に更新 (ACC-DOCS-UPDATED)
- [ ] `pyproject.toml` / `CITATION.cff` を `0.1.0` に bump (ACC-TAG-READY)
- [ ] T20 m2-acceptance タスク発動 → `v0.1.0-m2` タグ付与

これらが完了するまで T19 は「G-GEAR 側実行フェーズ完了」状態であり、
MASTER-PLAN 直下の T19 行の `[x]` は G-GEAR 作業分を指す。
MacBook 合流後に T19 全体を再確認し、T20 へ遷移する。

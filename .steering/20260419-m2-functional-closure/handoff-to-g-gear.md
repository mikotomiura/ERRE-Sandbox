# G-GEAR 側セッションへの引き継ぎ — T21 m2-functional-closure live 検証

本タスク (T21) は MASTER-PLAN §4.4 の残 4 検収項目 (GAP-1 依存) を PASS させ、
MVP 機能的完了を宣言するためのもの。Mac 側で **orchestrator コード + 設計
ドキュメント + ユニットテスト** は完了済。G-GEAR 側で **live 検証 (Ollama 実
推論込み) の 4 検収項目 evidence 取得** をお願いしたい。

## Mac 側で完了済 (PR #36, branch `feature/t21-m2-functional-closure`)

- [x] `.steering/20260419-m2-functional-closure/{requirement,design,design-v1,design-comparison,tasklist}.md`
- [x] `/reimagine` 適用: v1 (素直な単一 __main__) と v2 (Composition Root + Lifecycle-First) を比較し **ハイブリッド** 採択
- [x] `src/erre_sandbox/bootstrap.py` — `BootConfig` + `_load_kant_persona` +
      `_build_kant_initial_state` + `bootstrap` + `_supervise` (AsyncExitStack +
      asyncio.wait(FIRST_COMPLETED) + SIGINT/SIGTERM handler)
- [x] `src/erre_sandbox/__main__.py` — argparse CLI shell
- [x] `src/erre_sandbox/inference/ollama_adapter.py` — `health_check()` 追加
- [x] `pyproject.toml` — `[project.scripts] erre-sandbox = "erre_sandbox.__main__:cli"` 追加
- [x] `docs/architecture.md` §Gateway / §Inference 文言更新
- [x] `tests/test_bootstrap.py` — **11 件 PASS** (_load_kant_persona x 2 /
      _build_kant_initial_state x 2 / health_check x 3 / BootConfig x 2 / _supervise x 2)
- [x] 既存 346 テストに regression なし (ruff / mypy クリア)
- [x] `code-reviewer` + `security-checker` subagent review: HIGH/MEDIUM なし
- [x] commit + push + PR #36 作成
- [x] 本 `handoff-to-g-gear.md` 作成

## G-GEAR 側で実施すべき項目

### 1. ブランチ同期

```powershell
cd ~/ERRE-Sand\ Box  # 実パス
git fetch origin
git checkout feature/t21-m2-functional-closure
git pull
```

- [ ] HEAD が `feat(orchestrator): introduce bootstrap.py + __main__ for 1-Kant walker` commit になっていることを確認
- [ ] `.steering/20260419-m2-functional-closure/` 配下が取得済

### 2. 依存同期 + ヘルスチェック

```powershell
uv sync --frozen
uv run erre-sandbox --help
```

- [ ] `--help` が表示されること (`[project.scripts]` の entry point が効いている)
- [ ] ollama 未起動時は `uv run erre-sandbox` が即座に `OllamaUnavailableError` で落ちることを一度試す (fail-fast 確認)

### 3. Ollama 起動 + モデル確認

```powershell
# 別ターミナル
ollama serve
# 起動確認
curl http://127.0.0.1:11434/api/tags
# 必要モデル確認
ollama list  # qwen3:8b と nomic-embed-text が含まれていること
# 無ければ
ollama pull qwen3:8b
ollama pull nomic-embed-text
```

- [ ] `qwen3:8b` が downloaded であること
- [ ] `nomic-embed-text` が downloaded であること (cognition の埋め込みに使う)

### 4. Orchestrator 起動

```powershell
# Windows Firewall: port 8000 inbound が許可されていること
mkdir -p var
uv run erre-sandbox --host 0.0.0.0 --port 8000 --log-level info 2>&1 | tee logs/orchestrator.log
```

- [ ] 起動時 log に `[bootstrap] health_check http://127.0.0.1:11434 (model=qwen3:8b)` が出る
- [ ] 続いて `[bootstrap] starting (host=0.0.0.0 port=8000 db=var/kant.db)` が出る
- [ ] uvicorn の `Uvicorn running on http://0.0.0.0:8000` が出る

### 5. MacBook Godot live 接続 (両機協調)

G-GEAR orchestrator が稼働中の状態で、MacBook 側で:

```
cd /Users/johnd/ERRE-Sand\ Box
git checkout feature/t21-m2-functional-closure
git pull
godot --path godot_project --editor
# Godot Editor の Play (F5) で MainScene.tscn 起動
```

**MacBook 側担当**:
- [ ] Godot Output に `[WS] connected` + `[WS] client HandshakeMsg sent` が出ること
- [ ] Kant avatar が peripatos シーンに visible
- [ ] 10s ごとに avatar が移動を開始 (cognition が destination を返した後)
- [ ] **screen recording で 30s 以上** 撮る (MVP §4.4 #4 evidence)

### 6. MVP §4.4 4 検収項目の evidence 取得

G-GEAR 側で収集。`.steering/20260419-m2-functional-closure/evidence/` に格納。

#### 6.1 `#1`: ollama + gateway listen
```powershell
# Orchestrator 起動中に
curl -s http://127.0.0.1:8000/health | jq > evidence/gateway-health-$(Get-Date -Format "yyyyMMdd-HHmmss").json
curl -s http://127.0.0.1:11434/api/tags | jq > evidence/ollama-tags-$(Get-Date -Format "yyyyMMdd-HHmmss").json
ss -tulpn | grep -E "8000|11434" > evidence/listen-ports-$(Get-Date -Format "yyyyMMdd-HHmmss").txt
```

- [ ] `gateway-health-*.json` に `schema_version=0.1.0-m2` / `status=ok` / `active_sessions`
- [ ] `ollama-tags-*.json` に `qwen3:8b` と `nomic-embed-text` が含まれる
- [ ] `listen-ports-*.txt` に 8000 / 11434 の LISTEN 行あり

#### 6.2 `#2`: cognition 10s ごと
```powershell
# orchestrator 起動から 60s 以上経ったら
grep -E "\[cognition\]|CognitionCycle|cycle" logs/orchestrator.log \
  | head -n 20 \
  > evidence/cognition-ticks-$(Get-Date -Format "yyyyMMdd-HHmmss").log
```

- [ ] 10s 間隔で cognition 実行 log が 6 行以上 (60s 観測)
- [ ] エラー無し (OllamaUnavailableError / CognitionError が無い)

#### 6.3 `#3`: episodic_memory 書込
```powershell
# orchestrator 起動から 60s 以上経ったら (複数 cognition tick 済み)
sqlite3 var/kant.db \
  "SELECT COUNT(*), MAX(recall_count), MIN(wall_clock), MAX(wall_clock) FROM episodic_memory;" \
  > evidence/episodic-memory-summary-$(Get-Date -Format "yyyyMMdd-HHmmss").txt
sqlite3 var/kant.db \
  "SELECT memory_id, kind, importance, recall_count, substr(content, 1, 60) FROM episodic_memory ORDER BY created_at DESC LIMIT 10;" \
  > evidence/episodic-memory-sample-$(Get-Date -Format "yyyyMMdd-HHmmss").txt
```

- [ ] COUNT >= 5
- [ ] MAX(recall_count) > 0 (retrieval が発生し recall_count が増えている)

#### 6.4 `#4`: Godot avatar 30Hz 歩行 (MacBook 側で取得、G-GEAR evidence ディレクトリへ push)

- [ ] MacBook で `godot-walking-YYYYMMDD-HHMMSS.mp4` or `.gif` を 30s 以上収録
- [ ] evidence/ に push (git-lfs 不要な size に圧縮、~5MB 目安)
- [ ] Kant avatar が peripatos を周回移動し、位置が滑らかに更新されることが確認できる

### 7. acceptance-evidence.md 作成

`.steering/20260419-m2-functional-closure/acceptance-evidence.md` を新規作成:

```markdown
# T21 MVP §4.4 受け入れ evidence

| # | 検収条件 | 結果 | Evidence |
|---|---|---|---|
| 1 | ollama + gateway listen | ✅ PASS | evidence/gateway-health-*.json, evidence/ollama-tags-*.json, evidence/listen-ports-*.txt |
| 2 | Kant 10s ごと LLM 応答 | ✅ PASS | evidence/cognition-ticks-*.log (N 行観測) |
| 3 | episodic_memory >= 5 + recall_count>0 | ✅ PASS | evidence/episodic-memory-summary-*.txt (COUNT=M, MAX(recall_count)=K) |
| 4 | Godot avatar 30Hz 歩行 | ✅ PASS | evidence/godot-walking-*.mp4 |

## 実施環境
- 実施日: 2026-04-20
- G-GEAR: RTX 5060 Ti 16GB + Windows WSL2
- MacBook: MacBook Air M4, Godot 4.6.2.stable.official
- branch: `feature/t21-m2-functional-closure`
- schema_version: `0.1.0-m2`
```

### 8. MASTER-PLAN §4.4 の 4 checkbox を `[x]` に更新

`.steering/20260418-implementation-plan/MASTER-PLAN.md` §4.4 の該当 4 行を
`[ ]` → `[x]` にし、末尾 notation の `(GAP-1 → M4 待ち)` を削除して
`(T21 完了)` に置換する。T21 closeout note を追加する。

### 9. known-gaps.md の GAP-1 更新

`.steering/20260419-m2-integration-e2e-execution/known-gaps.md` の GAP-1 行を
`⏳ 未解消` → `✅ 解消 (T21)` に更新、解消先 notation に T21 PR を明示。

### 10. commit + push + PR main merge + tag

```powershell
git add .steering/20260419-m2-functional-closure/evidence/ \
        .steering/20260419-m2-functional-closure/acceptance-evidence.md \
        .steering/20260418-implementation-plan/MASTER-PLAN.md \
        .steering/20260419-m2-integration-e2e-execution/known-gaps.md
git commit -m "docs(steering): T21 MVP 4 検収項目 evidence + MASTER-PLAN [x] 更新"
git push origin feature/t21-m2-functional-closure
```

その後 PR #36 を main merge:

```powershell
gh pr merge 36 --merge --delete-branch
git checkout main
git pull
git tag -a v0.1.1-m2 -m "ERRE-Sandbox MVP: 1-Kant walker full-stack (GAP-1 resolved)"
git push origin v0.1.1-m2
```

- [ ] PR #36 main merge
- [ ] tag `v0.1.1-m2` push

### 11. MVP 機能的完了宣言

tag push 後、**MVP 機能的完了** を正式宣言。次マイルストンは M4
`gateway-multi-agent-stream` (3-agent 拡張 + reflection + semantic memory)。

## 失敗時のトラブルシュート

| 症状 | 疑い | 対処 |
|---|---|---|
| `uv run erre-sandbox: command not found` | entry point 未反映 | `uv sync --frozen` を再実行。無理なら `uv run python -m erre_sandbox --host ...` |
| `OllamaUnavailableError: /api/tags unreachable` | ollama serve 未起動 | `ollama serve` を別ターミナルで起動、`curl http://127.0.0.1:11434/api/tags` で確認 |
| Godot `[WS] connected` は出るが avatar 動かず | cognition が destination を返していない | orchestrator log の `[cognition]` 行を確認、`CognitionError` / `OllamaUnavailableError` を grep |
| `episodic_memory` に行なし | embedding client が失敗 | `nomic-embed-text` model が pulled か確認。ollama log で `/api/embed` の 200 応答を確認 |
| 30Hz 見えず (遅い / 途切れる) | WS broadcast 過負荷 | `active_sessions` が 1 で安定しているか、gateway log に `WebSocket error` が無いか確認 |
| orchestrator 起動後に即 exit | port 8000 衝突 | `ss -tulpn | grep 8000` で既存 process を kill、または `--port 8001` で起動 |

## 参照

- T21 設計: `.steering/20260419-m2-functional-closure/design.md`
- 設計判断比較: `.steering/20260419-m2-functional-closure/design-comparison.md`
- タスクリスト: `.steering/20260419-m2-functional-closure/tasklist.md`
- T20 handoff (参考、session counter runbook): `.steering/20260419-m2-acceptance/handoff-to-g-gear.md`
- T20 session counter runbook: `.steering/20260419-m2-acceptance/session-counter-runbook.md`
- MASTER-PLAN §4.4: `.steering/20260418-implementation-plan/MASTER-PLAN.md`
- known-gaps (GAP-1): `.steering/20260419-m2-integration-e2e-execution/known-gaps.md#gap-1`
- PR #36: https://github.com/mikotomiura/ERRE-Sandbox/pull/36

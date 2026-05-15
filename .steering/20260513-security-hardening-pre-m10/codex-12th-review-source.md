# Codex Review Issues

作成日: 2026-05-12

前回レビューで見つかった「即時修正候補」と「運用上の注意点」を、実装タスク化しやすい粒度に整理する。
現時点でランタイム本体に即時悪用できる HIGH は見つかっていないが、Codex 運用ガードと LAN 境界には強めの改善余地がある。

## 1. HIGH: Codex edit policy hook が shell 経由の編集を検査しない

### 根拠

- `.codex/hooks.json` の `PreToolUse` matcher は `apply_patch|Edit|Write` のみ。
- `.codex/hooks/pre_tool_use_policy.py` は patch/direct write の target 解析だけを行う。
- `exec_command` 経由の `sed -i` / `tee` / `python -c` / redirect 書き込みは、`.steering` 必須チェックや banned import チェックを通らない。

### リスク

- `src/erre_sandbox/` に `.steering` 記録なしで実装変更できる。
- `import openai` / `from anthropic` / `import bpy` など、プロジェクト禁止事項が shell 編集で混入しうる。
- hook が「強制機構」に見える一方で、実際には主要な編集経路を取り逃がす。

### 推奨対応

1. `.codex/hooks.json` の `PreToolUse` matcher に `exec_command` 相当の shell 実行ツールを含める。
2. shell コマンド内の明白な書き込みパターンを deny する。
   - `>`
   - `>>`
   - `sed -i`
   - `perl -pi`
   - `tee`
   - `python -c` / `python - <<`
   - `cat >`
3. Stop hook または pre-commit で「実ファイル差分」を再スキャンする。
   - `src/erre_sandbox/**/*.py` に cloud LLM / `bpy` import がないか。
   - `src/erre_sandbox/**/*.py` に `print(` がないか。
   - `src/erre_sandbox/` 差分があるのに recent `.steering/YYYYMMDD-*` が不完全でないか。
4. CI に同等の grep gate を追加する。ローカル hook は補助、CI を最終防衛線にする。

### 検証

```bash
uv run ruff check src tests
uv run mypy src
git diff -- src/erre_sandbox .codex/hooks .codex/hooks.json
```

## 2. MEDIUM: WebSocket gateway が既定で `0.0.0.0` + 認証なし

### 根拠

- `src/erre_sandbox/__main__.py` と `src/erre_sandbox/bootstrap.py` の既定 host は `0.0.0.0`。
- `src/erre_sandbox/integration/gateway.py` は `/ws/observe` を認証なしで `accept()` する。
- `docs/functional-design.md` と `docs/architecture.md` には「LAN 内前提、認証なし」と明記されている。

### リスク

- 共有 Wi-Fi や誤公開環境では、agent state / reasoning trace / dialog envelope が LAN 内の任意クライアントに見える。
- 不正クライアントが多数接続して session / queue / handshake 資源を消費できる。

### 推奨対応

1. 既定 host を `127.0.0.1` に変更する。
2. LAN 公開が必要な場合だけ `--host 0.0.0.0 --unsafe-lan` のような明示フラグを要求する。
3. MVP でも軽量な shared token を入れる。
   - HTTP header: `X-Erre-Token`
   - query parameter はログに残りやすいので避ける。
4. `Origin` チェックまたは許可 client subnet の設定を追加する。
5. `Registry` に最大 active session 数を設け、超過時は handshake 前後で close する。

### 検証

```bash
uv run pytest tests/test_integration/test_gateway.py tests/test_integration/test_multi_agent_stream.py -q
```

## 3. MEDIUM: repo-local Codex 設定が network access を広く許可している

### 根拠

- `.codex/config.toml` に `web_search = "live"`。
- `.codex/config.toml` の `[sandbox_workspace_write]` に `network_access = true`。
- プロジェクト方針は「クラウド送信なし」「ローカル推論で完結」。

### リスク

- prompt injection や誤操作により、repo 内容・評価データ・研究メモが外部へ送信される余地が増える。
- 「クラウド LLM API を必須依存にしない」制約と、Codex 作業環境のネットワーク許可が混同されやすい。

### 推奨対応

1. 既定は network off にする。
2. web search は必要時のみ明示許可にする。
3. `.codex/config.toml` にコメントで、network を有効化してよい条件を書く。
4. 外部送信を伴うコマンドやブラウズ前に、ユーザー承認を必須にする運用を AGENTS.md に追記する。

### 検証

```bash
git diff -- .codex/config.toml AGENTS.md
```

## 4. MEDIUM/LOW: eval CLI の `--memory-db` が既存ファイルを無条件削除する

### 根拠

- `src/erre_sandbox/cli/eval_run_golden.py` は `--memory-db` に任意 `Path` を受ける。
- natural capture で `memory_db_path.exists()` の場合に `memory_db_path.unlink()` する。

### リスク

- ローカル CLI 前提なので攻撃面は小さい。
- ただし誤指定で任意ファイルを消せる。特に絶対パスや重要な sqlite ファイルを指定した場合に危険。

### 推奨対応

1. 既存 `--memory-db` を削除するには `--overwrite-memory-db` を必須にする。
2. 既定では run 専用の一意 temp path を作る。
3. 許可ディレクトリを `var/eval/` や `/tmp/erre-sandbox/` に制限する。
4. symlink を拒否する。
5. tests に「既存ファイルは flag なしで消えない」ケースを追加する。

### 検証

```bash
uv run pytest tests/test_cli/test_eval_run_golden.py -q
```

## 5. LOW: WorldRuntime の envelope queue が unbounded

### 根拠

- `src/erre_sandbox/world/tick.py` の `_envelopes` は `asyncio.Queue()` で `maxsize` なし。
- gateway 側 per-client queue は bounded だが、runtime と broadcaster の間は無制限。

### リスク

- broadcaster 停止・遅延・例外時に runtime 側 queue が伸び続ける。
- 長時間実行時のメモリ増加が見えにくい。

### 推奨対応

1. runtime queue に `maxsize` を設定する。
2. heartbeat / agent_update は最新値 coalesce を検討する。
3. dialog / error / reasoning trace は欠落させない方針なら別 queue に分ける。
4. overflow 時の warning envelope または metrics counter を追加する。

### 検証

```bash
uv run pytest tests/test_world tests/test_integration/test_gateway.py -q
```

## 6. LOW: `_audit_stimulus.json` が CRLF 化して `git diff --check` に失敗

### 根拠

- `data/eval/golden/_audit_stimulus.json` は内容差分ではなく改行コード差分に見える。
- `git diff --check` が trailing whitespace として失敗する。

### リスク

- レビューで実質差分が読みにくい。
- CI や pre-commit に `diff --check` を入れた場合に失敗する。

### 推奨対応

1. `_audit_stimulus.json` を LF に正規化する。
2. `.gitattributes` に JSON の LF 固定を追加する。
3. Windows 由来の評価成果物について、rsync / copy 後の改行コード確認を手順化する。

### 検証

```bash
git diff --check
```

## 確認済みチェック

前回レビュー時点では以下を確認済み。

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
```

結果:

- `ruff check`: pass
- `ruff format --check`: pass
- `mypy src`: pass
- `pytest -q`: `1386 passed, 33 skipped`
- `git diff --check`: fail (`data/eval/golden/_audit_stimulus.json` の CRLF 起因)

## 推奨着手順

1. Hook / CI の編集ガード強化。
2. WebSocket gateway の localhost default + explicit LAN opt-in。
3. `.codex/config.toml` の network default 見直し。
4. `--memory-db` の削除保護。
5. runtime queue bound。
6. 評価 JSON の LF 正規化。

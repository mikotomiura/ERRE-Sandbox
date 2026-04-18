# 設計

## 1. 実装アプローチ

Ollama のモデル pull は `ollama pull <tag>` の発行だけで完結する。設計上の論点は以下の 3 点のみ:

- **A. 環境変数の反映タイミング**: User env vars は `setx` 済みだが、既存 Ollama プロセスには未反映 → pull 前に再起動する
- **B. モデル tag の解決**: MASTER-PLAN の tag (`qwen2.5:7b-instruct-q5_K_M` / `multilingual-e5-small`) が Ollama registry に存在するか不明 → 候補優先順位で段階的に試す
- **C. ネットワーク障害対策**: `ollama pull` は再開可能だが、GB 単位 DL の中断リスクあり (MASTER-PLAN R1) → run_in_background で開始、ログ監視で完了検知

## 2. プロセス再起動 (A)

```bash
# 1. 既存 Ollama を停止 (tray + server)
taskkill //F //IM "ollama app.exe" //IM "ollama.exe"

# 2. User env vars が有効な新 PowerShell から ollama app.exe を起動
#    (Explorer/tray 経由の起動は env を確実に継承しないケースがあるため、Start-Process 明示)
powershell.exe -NoProfile -Command 'Start-Process -FilePath "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe"'

# 3. 3-5 秒待機、ヘルスチェック
curl -s http://localhost:11434/api/version
tail -30 "$LOCALAPPDATA/Ollama/server.log" | grep -i "OLLAMA_"
```

`server.log` 先頭付近に環境変数がダンプされる仕様を利用して、反映を客観検証する。

## 3. モデル選定 (B)

### 3.1 推論 LLM

| 候補 | サイズ (Q5_K_M) | 根拠 | 優先度 |
|---|---|---|---|
| `qwen3:8b-q5_K_M` | ~5.5 GB | llm-inference Skill §ルール 3 の推奨 | **1** |
| `qwen2.5:7b-instruct-q5_K_M` | ~4.8 GB | MASTER-PLAN §6.3 明示、Qwen3 未登録時の fallback | 2 |
| `llama-3.1-swallow:8b-q5_K_M` | ~5.5 GB | 和文特化、Skill §ルール 3 の ALTERNATIVE | 3 |

試行順序: 1 → 2 → 3。いずれも失敗した場合は `blockers.md` に記録して `/reimagine`。

### 3.2 埋め込みモデル

| 候補 | 次元 | 根拠 | 優先度 |
|---|---|---|---|
| `multilingual-e5-small` | 384 | MASTER-PLAN §6.3 指定 | **1** |
| `nomic-embed-text` | 768 | Ollama 公式ライブラリ、多言語対応 | 2 |
| `mxbai-embed-large` | 1024 | Ollama 公式ライブラリ、英語強 | 3 |
| `snowflake-arctic-embed:22m` | 384 | Ollama 公式、小型 (~0.04GB)、EN 中心 | 4 |

試行順序: 1 → 2 → 3 → 4。埋め込み次元は `src/erre_sandbox/memory/embedding.py` (T10) で動的に参照する設計とするため、どの候補でも影響最小。

## 4. バックグラウンド pull 実行 (C)

- `ollama pull <tag>` を Bash の `run_in_background: true` で起動
- 並列 pull は Ollama サーバの IO 帯域を分割してしまうため **LLM → embedding の順次** 実行
- 進捗監視は `ollama list` の polling、完了検知は出力 tail の grep (success / error)

## 5. 変更対象

### 5.1 修正するファイル

- `.steering/_setup-progress.md` — Phase 8 に T09 の `[x]` エントリ追加
- `.steering/20260418-model-pull-g-gear/tasklist.md` — チェック進捗

### 5.2 新規作成するファイル

- `.steering/20260418-model-pull-g-gear/decisions.md` — モデル採用判断 (どの候補が勝ったか、VRAM 実測)
- `.steering/20260418-model-pull-g-gear/blockers.md` — pull 失敗時のみ作成

### 5.3 削除するファイル

なし。

## 6. 影響範囲

- Ollama 再起動中 (~5 秒) は `:11434` のサービスが一時停止。G-GEAR は単機運用なので業務影響なし。
- VRAM は pull 自体では消費されず、`ollama run` 実行時に初めて確保される。T09 スコープ内のスモークテストは 1 回のみで十分。
- ディスク: `%USERPROFILE%\.ollama\models\` に合計 ~6 GB が書き込まれる。空き容量要確認。

## 7. 既存パターンとの整合性

- `.steering/20260418-setup-g-gear/` と同じ 4 ファイル構成 (requirement / design / tasklist / decisions)
- llm-inference Skill のルール 1-5 をすべて遵守
- Conventional Commits: `chore(models): T09 model-pull-g-gear — pull Qwen3-8B Q5_K_M + e5-small`

## 8. テスト戦略

- **スモーク**: `ollama run <LLM> "1+1="` で数字応答を確認
- **embedding 動作**: `curl` で `/api/embed` を叩き、配列長が期待次元と一致
- **VRAM 確認**: `nvidia-smi` で使用量を記録、decisions.md に実測値を残す
- **回帰テスト**: 既存 `uv run pytest` は未影響だが念のため実行 → 96 passed / 16 skipped が維持されること

## 9. ロールバック計画

- pull 済みモデル削除: `ollama rm <tag>`
- Ollama 自体のアンインストール: T01 design.md §7 (本タスクとは別スコープ)
- ブランチ破棄: `git checkout main && git branch -D feature/model-pull-g-gear`

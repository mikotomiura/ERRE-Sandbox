# Decisions

> **2026-04-18 追記 (pull 完了後)**: D1 / D2 の採用を確定。実測値と応答サンプルは各節の「実測補足」に追加。

## D1 実測補足

- pull 完了: 24 分、平均 3.5 MB/s、中断なし
- `ollama list`: ID `500a1f067a9f`、ディスク 5.2 GB
- VRAM 実測 (context 4096 / num_parallel 4 / KV q8_0): **6.2 GB delta** (未 load 1307 MiB → load 後 7493 MiB)
- 応答品質: 日本語挨拶を正しく返却 (`こんにちは`)。thinking phase が観察されたため Qwen3 は reasoning ON がデフォルト → T11 inference-ollama-adapter で必要なら `think: false` オプション (または `/no_think` 指示) を検討
- 判断: 採用継続。VRAM 予算の半分以下で済むため、context を 8K / num_parallel を 8 に上げる余地が大きい (M4 multi-persona 時に再評価)

## D2 実測補足

- pull 完了: 7 分、qwen3 との帯域共有で ~500 KB/s
- `ollama list`: ID `0a109f422b47`、ディスク 274 MB
- 動作検証: `/api/embed` に `"search_query: 偉人の認知習慣"` を投げて **768 次元** `list[float]` 取得、first5 = `[-0.003, 0.008, -0.176, -0.003, 0.063]`
- 判断: 採用継続。768 次元が T10 design の `DEFAULT_DIM = 768` と一致。プレフィックス `"search_query: "` / `"search_document: "` は T10 D5 で API 化済み

## D1. 推論 LLM は `qwen3:8b` (default quantization ~5.2 GB) を採用

- **日付**: 2026-04-18
- **判断**: 推論 LLM は Ollama registry の `qwen3:8b` (default tag、5.2 GB、pull 中) を採用。
- **背景**: design.md §3.1 の優先順位 1 `qwen3:8b-q5_K_M` は **registry に存在しない** (API `/api/pull` が `{"error":"pull model manifest: file does not exist"}` を返却)。`qwen3:8b` (修飾子なし) はマニフェストが存在し、5.2 GB のダウンロードを開始。
- **採用理由**:
  1. Qwen3 系 8B クラスが RTX 5060 Ti 16GB の VRAM 予算 (llm-inference Skill §ルール 3 の 13GB 目安) に適合
  2. Ollama の default tag は通常 Q5_K_M 近傍の中量子化 (5.2 GB は Q5 系と整合)
  3. 実測量子化は pull 完了後 `ollama show qwen3:8b --modelfile` で事後確認する
- **代替と fallback 順序** (将来 tag が消滅した場合):
  1. `qwen3:8b` (今回採用) ✅ registry 存在確認済
  2. `qwen2.5:7b-instruct-q5_K_M` (MASTER-PLAN §6.3 明示)
  3. `llama-3.1-swallow:8b-q5_K_M` (和文特化)
- **トレードオフ**: 実際の量子化種別が事前に固定されないため、M7 SGLang 移行時に GGUF を手動指定する際の整合が少しずれる可能性がある。M7 着手前に `.ollama/models` から GGUF をコピーするか、Hugging Face から Q5_K_M を直接取得する方針で吸収。
- **ロールバックトリガー**: `ollama run qwen3:8b` の応答が 30 秒以上かかる、または VRAM が 13GB を超過する場合は fallback 2 (qwen2.5:7b) を評価。

## D2. 埋め込みモデルは `nomic-embed-text` (768 次元, ~274 MB) を採用

- **日付**: 2026-04-18
- **判断**: 埋め込みモデルは `nomic-embed-text` (274 MB、768 次元、pull 中) を採用。
- **背景**: design.md §3.2 の優先順位 1 `multilingual-e5-small` は Ollama registry に **存在しない** (API manifest check で 404)。優先順位 2 の `nomic-embed-text` はマニフェスト取得に成功、pull を開始した。
- **採用理由**:
  1. Ollama 公式ライブラリで入手確実
  2. 多言語対応 (日本語含む)、ERRE-Sandbox が扱う日本語哲学テキストに対応可能
  3. 274 MB と軽量で SSD を圧迫しない
  4. 768 次元は sqlite-vec の `vec0` virtual table で標準的なサイズ
- **代替と fallback 順序**:
  1. `multilingual-e5-small` (MASTER-PLAN 指定、registry 未登録のため不採用)
  2. `nomic-embed-text` (今回採用) ✅
  3. `mxbai-embed-large` (1024 次元、サイズ ~670 MB)
  4. `snowflake-arctic-embed:22m` (超軽量)
- **トレードオフ**: `multilingual-e5-small` (384 次元) と比べて次元数が倍 (768) → sqlite-vec のインデックスサイズも倍。10 万件レコード時点で差分は ~150 MB 程度、M7 で本番運用時に再評価。
- **反映先**: T10 memory-store の `embedding.py` で `EMBED_DIM = 768` 定数、または `ollama show` から動的取得。

## D3. Ollama 再起動は `ollama serve` を直接起動する方式を採用

- **日付**: 2026-04-18
- **判断**: User 環境変数を反映させるため、`ollama app.exe` (tray) 経由ではなく `ollama.exe serve` を Git Bash から直接 `export` + `nohup &` で起動する方式を採用した。
- **背景**: Start-Process 経由で tray を再起動したが、内部の server プロセスが "timeout waiting for Ollama server to be ready" で起動失敗。app.log のみ更新され、server.log は空のまま。明確な原因は不明 (既存 tray インスタンスの mutex 競合の可能性)。
- **採用理由**:
  1. `ollama.exe serve` をシェル変数でオーバーライドした env vars 付きで起動することで、User 環境変数の伝搬不整合を完全に bypass できる
  2. server.log で env vars が反映されていること (`OLLAMA_NUM_PARALLEL:4` / `OLLAMA_FLASH_ATTENTION:true` / `OLLAMA_KV_CACHE_TYPE:q8_0`) を客観確認できた
- **トレードオフ**: 本セッションの Bash を閉じると Ollama serve が終了する。ユーザー再起動時は通常の tray app から起動し、その時点で User env vars が新規プロセスに継承される (setx 済みのため)。
- **反映先**: tasklist.md の「Ollama 再起動」項目、および T11 実装時の `OllamaAdapter` の接続先は `127.0.0.1:11434` を維持。

## D4. 本タスクの commit 戦略: pull 進行中でも中間 commit を行う

- **日付**: 2026-04-18
- **判断**: qwen3:8b (5.2 GB) の pull は ~20 分かかるため、pull 完了を待たずに decisions.md / tasklist.md の現時点状態を commit し、push する。pull 完了後のスモークテスト結果は追加 commit (または amend) で反映する。
- **採用理由**:
  1. T10 memory-store の設計作業と並列稼働するため、pull 完了を block 条件にしない
  2. チェックポイント commit により、万一セッションが中断しても進捗が失われない
  3. push して origin に残すことで、MacBook 側からも途中状態を観察できる
- **反映先**: tasklist.md の「完了処理」セクションで 2 段階 commit を許容。

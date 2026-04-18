# T09 model-pull-g-gear

## 背景

T01 setup-g-gear 完了後、G-GEAR (Windows 11 / RTX 5060 Ti 16GB) に uv 0.11.7 と Ollama 0.21.0 は導入済みだが、推論に使用するモデル重みがまだ pull されていない (`ollama list` が空)。MASTER-PLAN.md §13 では「T05 着手と同時に G-GEAR で T09 (モデル pull) をバックグラウンド実行」と規定されていたが、並列稼働されなかったため Contract Freeze (T08) 完了時点でモデル未保有の状態にある。

T11 inference-ollama-adapter 実装以降は `ollama run <model>` の即応性が前提となるため、T10 memory-store の設計と並行してモデル pull を早急に走らせる必要がある。

また、T01 で設定した `OLLAMA_NUM_PARALLEL=4` / `OLLAMA_FLASH_ATTENTION=1` / `OLLAMA_KV_CACHE_TYPE=q8_0` は User 環境変数として永続化されているが、**既に起動していた Ollama プロセスには反映されていない**。モデル pull と同時に Ollama を再起動して、新環境変数が有効な状態で KV キャッシュが確保されることを確認する必要がある。

## ゴール

G-GEAR で以下が可能な状態を作る:

1. Ollama プロセスが `OLLAMA_NUM_PARALLEL=4` / `OLLAMA_FLASH_ATTENTION=1` / `OLLAMA_KV_CACHE_TYPE=q8_0` を有効にして起動している
2. 推論用 LLM (Qwen3-8B 相当の Q5_K_M 量子化、~5.5 GB) が `ollama list` に現れ、`ollama run <tag>` が応答を返す
3. 埋め込み用モデル (multilingual-e5-small 相当、~0.5 GB) が `ollama list` に現れ、REST API 経由で ベクトルを返す (T10 memory-store が使用)
4. `nvidia-smi` でモデル推論時に GPU メモリが 5-8 GB 割り当てられる (context 4K × 4 parallel ≈ 5-8 GB 見込み、llm-inference Skill §ルール 4 に準拠)
5. 次タスク T10 memory-store / T11 inference-ollama-adapter が即着手可能

## スコープ

### 含むもの

- Ollama プロセスの再起動 (新 User env vars の反映)
- 推論 LLM の pull (第一候補: `qwen3:8b-q5_K_M`、llm-inference Skill §ルール 3 準拠。失敗時は MASTER-PLAN §6.3 の fallback `qwen2.5:7b-instruct-q5_K_M`)
- 埋め込みモデルの pull (第一候補: MASTER-PLAN 指定の `multilingual-e5-small`、Ollama registry 未登録の場合は `nomic-embed-text` または `mxbai-embed-large` に fallback)
- `ollama run` / `curl /api/embed` での軽量スモークテスト
- `.steering/_setup-progress.md` の T09 を `[x]` に更新、実測 pull サイズと VRAM を記載
- `feature/model-pull-g-gear` ブランチでの記録 commit・push

### 含まないもの

- `OllamaAdapter` クラスの実装 → T11
- 記憶層 (sqlite-vec) の実装 → T10
- LoRA / vLLM の導入 → M9
- SGLang への切替 → M7

## 受け入れ条件

- [ ] Ollama サーバーログ (`%LOCALAPPDATA%\Ollama\server.log`) に `OLLAMA_NUM_PARALLEL=4` / `OLLAMA_FLASH_ATTENTION=1` / `OLLAMA_KV_CACHE_TYPE=q8_0` が記録されている
- [ ] `ollama list` に推論 LLM 1 件と埋め込みモデル 1 件がリストされる
- [ ] `ollama run <LLM> "日本語で一言挨拶"` が 15 秒以内に応答を返す (寒冷 start は除く)
- [ ] `curl http://localhost:11434/api/embed -d '{"model":"<embed>","input":"hello"}'` がベクトルを返す
- [ ] `nvidia-smi` で Ollama プロセスに VRAM が割当てられており、Total 16 GB を超えない
- [ ] `.steering/_setup-progress.md` の Phase 8 で T09 が `[x]` に更新され、pull 済みモデル ID・サイズ・所要時間が併記される
- [ ] `.steering/20260418-model-pull-g-gear/tasklist.md` が全チェック済み
- [ ] 作業ブランチ `feature/model-pull-g-gear` を push (PR 作成可)

## 関連ドキュメント

- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §6.3 (モデル重み指示), §10 R1 / R2 (pull 中断リスク / VRAM 超過リスク)
- `.claude/skills/llm-inference/SKILL.md` ルール 1 (環境変数), ルール 3 (モデル選定), ルール 4 (context × parallel)
- `docs/architecture.md` §推論層
- `.steering/20260418-setup-g-gear/decisions.md` D2 (OLLAMA_* User scope 判断)

## 運用メモ

- 破壊と構築 (`/reimagine`) 適用: **No**
- 理由: モデル選定は llm-inference Skill のルールに完全に従い、代替は fallback 優先順位で一意に決定できる。アーキテクチャ判断は伴わない。
- タスク種類: その他 (環境構築 / モデルセットアップ、Phase 8 実装の前提条件)

# タスクリスト

## 準備
- [x] MASTER-PLAN.md §6.3 と llm-inference Skill §ルール 1 / 3 を読む
- [x] T01 decisions.md D2 で User scope env が確定していることを確認
- [x] `git checkout -b feature/model-pull-g-gear`

## Ollama 再起動 (新 env 反映)
- [x] `taskkill //F //IM "ollama app.exe" //IM "ollama.exe"` — 既存プロセス停止
- [ ] ~~`Start-Process "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"` 経由~~ (tray 経由は server 起動失敗、decisions.md D3 参照)
- [x] `export OLLAMA_NUM_PARALLEL=4 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 && nohup ollama.exe serve &` で直接起動
- [x] `curl -s http://localhost:11434/api/version` → `{"version":"0.21.0"}` 取得
- [x] server.log で `OLLAMA_NUM_PARALLEL:4` / `OLLAMA_FLASH_ATTENTION:true` / `OLLAMA_KV_CACHE_TYPE:q8_0` を確認

## 推論 LLM の pull
- [x] ~~`ollama pull qwen3:8b-q5_K_M`~~ → manifest 404、**fallback `qwen3:8b` (5.2 GB, ID 500a1f067a9f) を採用 (decisions.md D1)**
- [x] BG pull 完了 (実測 ~24 分、平均 ~3.5 MB/s、中断なし)
- [x] `ollama list` に `qwen3:8b  500a1f067a9f  5.2 GB` が現れる
- [x] `ollama run qwen3:8b "こんにちは、..."` → 応答 `こんにちは` (35.2s wall time, cold start 含む; 2 回目以降は model keep-alive 5 min で高速)

## 埋め込みモデルの pull
- [x] ~~`ollama pull multilingual-e5-small`~~ → manifest 404、**fallback `nomic-embed-text` (274 MB, 768 次元, ID 0a109f422b47) を採用 (decisions.md D2)**
- [x] BG pull 完了 (~7 分、平均 ~500 KB/s、qwen3 との帯域共有)
- [x] `curl /api/embed -d '{"model":"nomic-embed-text","input":"search_query: 偉人の認知習慣"}'` → 768 次元の float 列を返す (first5 = [-0.003, 0.008, -0.176, -0.003, 0.063])

## VRAM / ディスク実測
- [x] `nvidia-smi`: 未 load 時 1307 MiB → qwen3:8b load 後 7493 MiB (**VRAM delta 6.2 GB**, 総使用 ~46%, 残 8.5 GB)
- [x] `ollama ps`: `qwen3:8b  6.7 GB  100% GPU  context 4096  4 min` (KV 込み 6.7 GB、Skill 予算 13 GB に対して余裕)
- [x] `%USERPROFILE%\.ollama\models\`: 5.2 GB (LLM blob + embed blob + manifests)
- [x] `decisions.md` に D1 / D2 / D3 / D4 を既に記録済み (WIP 段階で先行記録、実測値で更新)

## 回帰テスト
- [x] `uv run pytest` で 96 passed / 16 skipped を維持 (LLM/embedding は test スコープ外のため未変更)

## ドキュメント
- [x] `.steering/_setup-progress.md` の Phase 8 に T09 を `[x]` で追記 (採用モデル ID / サイズ / pull 時間 / VRAM delta)
- [x] `decisions.md` の D1/D2 に pull 後の実測値を補足
- [ ] `blockers.md` は不要 (manifest 404 の fallback は decisions で解決済み)

## 完了処理
- [x] `git add .steering/` → WIP commit 06cf007 に続き finalize commit を追加 (2 段階 commit 戦略 D4)
- [ ] ~~`git push -u origin feature/model-pull-g-gear`~~ (本セッションでは push 保留、ユーザー指示により local のみ)
- [ ] PR 作成は push 実施後に延期

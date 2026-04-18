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
- [x] ~~`ollama pull qwen3:8b-q5_K_M`~~ → manifest 404、**fallback `qwen3:8b` (5.2 GB) を採用 (decisions.md D1)**
- [ ] ⏳ BG pull 進行中 (~4 MB/s, 残 ~20 分予想)
- [ ] `ollama list` に `qwen3:8b` が現れる
- [ ] `ollama run qwen3:8b "こんにちは、一言で挨拶を返してください"` が 15 秒以内に応答

## 埋め込みモデルの pull
- [x] ~~`ollama pull multilingual-e5-small`~~ → manifest 404、**fallback `nomic-embed-text` (274 MB, 768 次元) を採用 (decisions.md D2)**
- [ ] ⏳ BG pull 進行中 (`nomic-embed-text`, 274 MB)
- [ ] `curl http://localhost:11434/api/embed -d '{"model":"nomic-embed-text","input":"test"}'` で埋め込み取得、次元 768 を確認

## VRAM / ディスク実測
- [ ] `nvidia-smi --query-gpu=memory.used --format=csv` で LLM 未 load 時と load 後の差分を記録
- [ ] `%USERPROFILE%\.ollama\models\` のディスク使用量を記録
- [ ] `decisions.md` に採用モデル / 実測値を記録

## 回帰テスト
- [ ] `uv run pytest` が依然 96 passed / 16 skipped を返すこと

## ドキュメント
- [ ] `.steering/_setup-progress.md` の T09 を `[x]` に更新、採用モデル ID / サイズ / 所要時間を記載
- [ ] `decisions.md` 記入
- [ ] (必要なら) `blockers.md` 記入

## 完了処理
- [ ] `git add .steering/` → `git commit -m "chore(models): T09 model-pull-g-gear — <LLM> + <embed> (T09)"`
- [ ] `git push -u origin feature/model-pull-g-gear`
- [ ] PR 作成 (GitHub Web UI)

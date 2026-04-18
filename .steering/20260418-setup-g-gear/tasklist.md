# タスクリスト

## 準備
- [x] MASTER-PLAN.md §6 (G-GEAR 側アクション) / §10 R3-R4 を読む
- [x] setup-macbook/requirement.md を雛形として比較参照
- [x] 現環境のプロービング (python / git / curl / nvidia-smi / wsl / ollama / uv)
- [x] 破壊と構築 (/reimagine) 適用判定: Yes
- [x] OS path 判断 (WSL2 vs 素 Windows): **素 Windows 採用**

## Git ブランチ
- [x] `git checkout -b feature/setup-g-gear`

## 実装: uv
- [x] `python -m pip install --user --upgrade uv` (PowerShell `irm | iex` はエージェント制約で非採用、pip で代替)
- [x] 新規シェルで `uv --version` が 0.11.7 でヒット
- [x] `uv python install 3.11` を実行 → CPython 3.11.15 導入
- [x] `uv python list --only-installed` で 3.11.15 を確認
- [x] User PATH に `%APPDATA%\Python\Python311\Scripts` と `%USERPROFILE%\.local\bin` を追記

## 実装: Ollama
- [x] `winget install --id Ollama.Ollama --silent` を実行 → 0.21.0 導入
- [x] `ollama --version` が `ollama version is 0.21.0` を返す
- [x] Ollama デーモンが常駐 (`ollama app.exe` と `ollama.exe` が tasklist に存在)

## 実装: 環境変数 (llm-inference Skill 準拠)
- [x] `[Environment]::SetEnvironmentVariable('OLLAMA_NUM_PARALLEL','4','User')`
- [x] `[Environment]::SetEnvironmentVariable('OLLAMA_FLASH_ATTENTION','1','User')`
- [x] `[Environment]::SetEnvironmentVariable('OLLAMA_KV_CACHE_TYPE','q8_0','User')`
- [x] 新規 PowerShell で 3 変数が `4 / 1 / q8_0` を返す
- [ ] Ollama サービスの再起動による反映 → **T09 (model-pull-g-gear) の直前に実施** (本タスクでは新規起動プロセスが env を継承するため後回しで可)

## 検証: プロジェクト整合
- [x] `cd C:\ERRE-Sand_Box && uv sync` がエラーなく完走 (84 パッケージ解決)
- [x] `uv run ruff check` → All checks passed!
- [x] `uv run ruff format --check` → 16 files already formatted
- [x] `uv run mypy src` → Success: no issues found in 8 source files
- [x] `uv run pytest` → **96 passed, 16 skipped** (MacBook が T05-T08 を先行した影響で smoke の 2 件を超え、schemas/fixtures テスト一式を追認)
- [x] `nvidia-smi -L` で RTX 5060 Ti 16GB が継続認識

## レビュー
- [x] self-review: 受け入れ条件 10 項目のうち 9 項目を達成、残 1 項目 (`ollama run` での GPU メモリ割当確認) は T09 モデル pull 後に自然検証される
- [x] (skip) security-checker: 設定した OLLAMA_* は非機密 → skip 判断

## ドキュメント
- [x] `.steering/_setup-progress.md` の T01 を `[x]` に更新、導入バージョン・GPU・検証結果を記載
- [x] `decisions.md` に D1 (素 Windows 採用) / D2 (OLLAMA_* を User scope) を記録
- [x] `blockers.md` 不要 (ブロッカーなし)
- [x] MASTER-PLAN.md §6 への「素 Windows の場合」追記は後続タスクに繰り越し (`blockers.md` に記載不要、PR 説明で触れる)

## 完了処理
- [ ] `git add` 対象確認 → `.steering/_setup-progress.md` と `.steering/20260418-setup-g-gear/`
- [ ] `git commit -m "chore(setup): configure G-GEAR with uv 0.11.7 and Ollama 0.21.0 (T01)"` (Conventional Commits)
- [ ] `git push -u origin feature/setup-g-gear`
- [ ] (任意) GitHub Web UI から PR 作成

# T01 setup-g-gear

## 背景

Claude Code 環境 (Phase 0-7) と MacBook 側の T02-T04 (setup-macbook / pdf-extract-baseline / pyproject-scaffold) は既に完了し、`uv.lock` を含む Python プロジェクト骨格が `main` に存在する。G-GEAR (Windows 11 Home / RTX 5060 Ti 16GB) は、推論・記憶・認知層 (T09-T14) を担当する「実行機」として MASTER-PLAN.md §3 に位置づけられているが、実装に必要なツールチェイン (uv / Ollama / CUDA 経由 GPU 推論) が未整備。

実環境のプロービング結果 (2026-04-18, G-GEAR):

- ✅ Git (`/mingw64/bin/git` 2.53.0.windows.2)
- ✅ curl (`/mingw64/bin/curl`)
- ✅ Python 3.11.9 (python.org 版, `/c/Users/johnd/AppData/Local/Programs/Python/Python311`)
- ✅ Node.js (`/c/Program Files/nodejs`)
- ✅ NVIDIA GeForce RTX 5060 Ti (16GB, `nvidia-smi -L` で認識)
- ❌ uv — 未インストール
- ❌ Ollama — 未インストール
- ❌ WSL2 — 未インストール (`wsl.exe --install` で導入可能な状態)
- ❌ `OLLAMA_*` 環境変数 — 未設定

## ゴール

G-GEAR で以下が可能な状態を作る:

1. `uv` と uv 管理下の Python 3.11 が PATH から利用できる
2. Ollama が常駐起動し、`ollama list` / `ollama pull` が動作する
3. `OLLAMA_NUM_PARALLEL=4` / `OLLAMA_FLASH_ATTENTION=1` / `OLLAMA_KV_CACHE_TYPE=q8_0` が恒久的に設定される (llm-inference Skill 準拠)
4. `cd C:\ERRE-Sand_Box && uv sync` が成功し、`uv run pytest` が MacBook と同じ緑を示す
5. 次タスク T09 (model-pull-g-gear) と T10 (memory-store) が即着手可能

## スコープ

### 含むもの

- uv のインストール (Windows 版 PowerShell or WSL2 Ubuntu、どちらか採用側)
- `uv python install 3.11` で uv 管理 Python 3.11 を導入
- Ollama のインストール (採用 OS に合わせた公式インストーラ)
- `OLLAMA_*` 環境変数の恒久化
- 既存 `pyproject.toml` に対する `uv sync` / `uv run ruff check` / `uv run pytest` のグリーン確認
- `.steering/_setup-progress.md` の T01 を `[x]` に更新
- `feature/setup-g-gear` ブランチで commit → push (main 直 push は禁止)

### 含まないもの

- モデル重みの `ollama pull` → T09 (model-pull-g-gear) で実施
- `sglang[all]` / `vllm` の導入 → M7 / M9 で別タスク
- Godot のインストール (G-GEAR は描画側ではない)
- VS Code / Cursor の導入 (任意、本タスクのスコープ外)
- ペルソナ / schemas / inference 実装 → T05 以降

## 受け入れ条件

- [ ] `which uv` がヒットし `uv --version` が 0.4 以上
- [ ] `uv python list --only-installed` に 3.11.x が含まれる
- [ ] `which ollama` がヒットし `ollama --version` がヒット
- [ ] 新規シェルで `echo $OLLAMA_NUM_PARALLEL $OLLAMA_FLASH_ATTENTION $OLLAMA_KV_CACHE_TYPE` が `4 1 q8_0` を返す
- [ ] `cd C:\ERRE-Sand_Box && uv sync` がエラーなく完走
- [ ] `uv run pytest` が MacBook と同じ 2 件 pass 相当でグリーン
- [ ] `nvidia-smi` から Ollama プロセスに GPU メモリが割り当てられる (`ollama run <small-model>` で確認可能な状態)
- [ ] `.steering/_setup-progress.md` の「Phase 8: MVP 実装フェーズ」で T01 が `[x]` に更新されている
- [ ] `.steering/20260418-setup-g-gear/tasklist.md` が全チェック済み
- [ ] 作業ブランチ `feature/setup-g-gear` を push (PR 作成可)

## 関連ドキュメント

- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §6 (G-GEAR 側アクション), §10 R3 / R4 (WSL2 固有リスク)
- `.steering/20260418-setup-macbook/requirement.md` (対称タスク T02 の雛形)
- `docs/architecture.md` §2 (2 拠点構成)
- `docs/development-guidelines.md` §Git ワークフロー
- `.claude/skills/llm-inference/` (OLLAMA_* 環境変数の根拠)

## 運用メモ

- 破壊と構築 (`/reimagine`) 適用: **Yes (設計段階で 2 案比較済み、design.md §2 を参照)**
- 理由: OS パス選択 (WSL2 vs 素の Windows) はアーキテクチャ判断を伴うため、初回案 (WSL2) を意図的に壊し、素 Windows 案と比較して採用側を確定する。
- タスク種類: その他 (環境構築 / セットアップ)

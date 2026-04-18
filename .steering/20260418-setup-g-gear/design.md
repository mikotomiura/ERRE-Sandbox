# 設計

## 1. 実装アプローチ

採用: **素の Windows (native Windows, PowerShell + Git Bash)**。

- uv 公式 Windows installer (`powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`) で導入
- `uv python install 3.11` で uv 管理下の CPython 3.11 を入れる (既存の python.org 版 3.11.9 は残すが、`pyproject.toml` 経由の `.venv` は uv 管理側を使用)
- Ollama は `OllamaSetup.exe` (公式 Windows installer) をユーザー権限で導入
- `OLLAMA_*` 環境変数は **ユーザー環境変数** に設定 (`setx` 経由)。Ollama サービスの再起動で反映
- GPU アクセラレーションは Ollama が CUDA ランタイムを同梱する (WSL より単純)
- ネットワーク: 本タスクでは listener 起動までは行わない (T14 gateway-fastapi-ws)。`netsh portproxy` は素 Windows では不要 (R3 消滅)

## 2. 破壊と構築 (Reimagine)

### 2.1 初回案: WSL2 + Ubuntu 24.04

MASTER-PLAN.md §6 記載。Linux で MacBook と実行環境を揃える利点は明確だが、以下の弱点:

- W1: admin 権限 + 再起動が必要 (本セッションで完結しない)
- W2: `netsh portproxy` の追加運用 (R3) と `g-gear.local` mDNS (R4) が増える
- W3: WSL2 から物理ホストの NIC に届くまでのネットワークホップが 1 段増える
- W4: Ollama VRAM が WSL2 側から見ると仮想割当てで、M7 SGLang 移行時に再構築リスク
- W5: `uv` / `python3.11` を Windows と WSL 両側に二重導入 (保守コスト)

### 2.2 再生成案: 素の Windows

- Ollama 公式 Windows installer が CUDA ランタイム同梱 → GPU 利用は自動
- `uv` は Windows PowerShell installer でネイティブ導入 → PATH/PowerShell/Git Bash 全てで動く
- `setx OLLAMA_NUM_PARALLEL 4` でユーザー環境変数を恒久化
- `netsh portproxy` 不要、ファイアウォール設定も `listenaddress=0.0.0.0` の FastAPI を許可するだけで足りる (T14)
- Linux 固有挙動は M7 SGLang 移行時 (Linux 必須) に WSL2 で再構築すれば良い。その頃には SGLang のための Linux 環境が別途必要になるため、「今は WSL を入れない」は一貫する

### 2.3 判定

素の Windows 案を採用。決定根拠は `decisions.md` D1 を参照。

## 3. 変更対象

### 3.1 修正するファイル

- `.steering/_setup-progress.md` — Phase 8 の T01 を `[x]` に更新、完了日時と導入バージョンを追記
- (任意) `.steering/20260418-implementation-plan/MASTER-PLAN.md` §6 — 「WSL2 の場合」節に「素の Windows の場合」追記 (本タスクのスコープ外、後続で別コミット)

### 3.2 新規作成するファイル

- `.steering/20260418-setup-g-gear/decisions.md` — OS 採用判断 D1、環境変数スコープ判断 D2 の記録

### 3.3 削除するファイル

なし。

## 4. 影響範囲

- `.steering/_setup-progress.md` の編集は MacBook 側と競合しうる (CLAUDE.md 運用メモで「MacBook 単独編集」推奨) が、T01 は G-GEAR 側だけが持つ情報のため、本ブランチ経由の PR でマージする
- Ollama / uv の PATH 追加は PowerShell / Git Bash の PATH 優先順位に影響するが、python.org の Python 3.11.9 とは衝突しない (uv は独自 `.python-installations/` に入れる)

## 5. 既存パターンとの整合性

- `.steering/20260418-setup-macbook/` の構造 (requirement / design / tasklist) をそのまま踏襲
- CLAUDE.md §作業記録ルール: 環境構築タスクも `.steering/` 記録必須 → 本ディレクトリで満たす
- docs/development-guidelines.md §Git ワークフロー: `feature/setup-g-gear` ブランチ、Conventional Commits、main 直 push 禁止

## 6. テスト戦略

本タスクはセットアップのため単体テスト追加はなし。以下で代替検証:

- **受け入れ条件の手動検証**: `uv --version` / `ollama --version` / `nvidia-smi` / 環境変数確認
- **回帰テスト**: 既存 `tests/test_smoke.py` (7 レイヤー import 検証) が `uv run pytest` でグリーンになることを確認
- **CUDA 経由 GPU 確認**: `ollama run` での 1 回の推論 (モデル pull は T09 範囲だが、軽量モデルで動作確認してもよい)
- **再現性**: 新規 PowerShell / Git Bash セッションを開いて PATH / 環境変数が生きていることを確認

## 7. ロールバック計画

- uv: `~/.local/bin/uv.exe` を削除、PATH エントリを除去
- Ollama: `Settings > Apps > Ollama > Uninstall`、`%LocalAppData%\Ollama` を削除
- 環境変数: `setx OLLAMA_NUM_PARALLEL ""` (空文字で削除) または `reg delete HKCU\Environment /v OLLAMA_NUM_PARALLEL /f`
- uv 管理 Python: `uv python uninstall 3.11` で uv が管理するインストールのみ削除 (python.org 側には触れない)
- Git ブランチ: `git checkout main && git branch -D feature/setup-g-gear`

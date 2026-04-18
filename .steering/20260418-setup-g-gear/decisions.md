# Decisions

## D1. OS パスは素の Windows を採用 (WSL2 不採用)

- **日付**: 2026-04-18
- **判断**: G-GEAR のセットアップを **素の Windows** (PowerShell + Git Bash) で実施する。WSL2 + Ubuntu 24.04 を採用しない。
- **背景**: MASTER-PLAN.md §6 の初回案は WSL2 想定だったが、admin 権限と再起動が必要、`netsh portproxy` (R3)・`g-gear.local` mDNS (R4)・VRAM 仮想割当て・uv/Python の二重インストールという 4 系統の運用負債が積み上がる。
- **採用理由**:
  1. uv 公式 Windows installer (PowerShell) と Ollama 公式 `OllamaSetup.exe` はいずれも admin 不要のユーザー権限インストール
  2. Ollama Windows 版は CUDA ランタイム同梱で GPU 利用が追加設定なし
  3. `netsh portproxy` が本質的に不要 (FastAPI listener が直接 0.0.0.0 に bind 可能) → R3 消滅
  4. Linux 固有挙動の検証は M7 SGLang 移行時 (Linux 必須) に改めて実施すれば十分
- **トレードオフ**: MacBook (Unix) と G-GEAR (Windows) で OS 差分が残る。差分は Python / Ollama の挙動差異に限定され、`schemas.py` (Pydantic v2) / `memory/store.py` (sqlite-vec) / `inference/ollama_adapter.py` (httpx) は OS 非依存のため影響は最小。
- **ロールバックトリガー**: M4-M5 の段階で「Windows 固有バグが週 1 回以上発生」または「SGLang 移行が M7 より前倒しされた」場合に WSL2 再検討。
- **反映先**: `design.md §2`、`requirement.md` の「運用メモ」、後続で `MASTER-PLAN.md §6` に追記。

## D2. OLLAMA_* 環境変数は User scope に設定

- **日付**: 2026-04-18
- **判断**: `OLLAMA_NUM_PARALLEL=4` / `OLLAMA_FLASH_ATTENTION=1` / `OLLAMA_KV_CACHE_TYPE=q8_0` を **ユーザー環境変数** (HKCU\\Environment) に設定する。System 環境変数 (HKLM) には触れない。
- **採用理由**:
  1. admin 権限不要 (`setx` のデフォルト)
  2. 他ユーザーに影響しない (個人機につき実害はないが clean な分離)
  3. ロールバックが `reg delete HKCU\Environment /v <name> /f` で一撃
- **トレードオフ**: システムサービスとして将来 Ollama を走らせる場合は System scope への昇格が必要。その時点で再設定。

# ERRE-Sandbox 実装プラン (MVP + 本番構築版 / 2 拠点対応)

作成日: 2026-04-18
対象リポジトリ: `/Users/johnd/ERRE-Sand Box`
根拠 PDF: `ERRE-Sandbox_v0.2.pdf` (21p, .gitignore 対象)
参照ドキュメント: `docs/functional-design.md`, `docs/architecture.md`, `docs/repository-structure.md`, `docs/development-guidelines.md`, `docs/glossary.md`

---

## 1. Context (なぜこの計画が必要か)

Claude Code 環境 (Phase 0-7) は完成したが、実装資産 (`src/erre_sandbox/`, `godot_project/`, `personas/`, `tests/`, `pyproject.toml`) はすべて未着手。

本計画は以下の要求に応える:

1. MVP (M2: 1 体歩行 + 記憶 + Godot 描画) と本番構築版 (M4→M10-11) を明確に二段で示す
2. PDF 仕様書 (`ERRE-Sandbox_v0.2.pdf`) の参照方針を運用レベルで確定する
3. G-GEAR (RTX 5060 Ti 16GB) と MacBook Air M4 それぞれが何をインストールし、いつ何を実行するかを列挙する
4. 計画段階で「破壊と構築」(`/reimagine`) を適用し、初回案を意図的に壊して再構築した結果を採用する

---

## 2. 破壊と構築の結果 (Reimagine 適用)

### 2.1 初回案 (素直な時系列積み上げ) の弱点

| # | 弱点 | 深刻度 |
|---|---|---|
| W1 | 2 拠点が直列実行になり MacBook が前半アイドルする | 高 |
| W2 | `ControlEnvelope` 仕様を固めないまま両機が独立実装し、末期に大幅手戻り | 致命 |
| W3 | ペルソナ YAML の構造未確定で `schemas.Biography / Traits` が後から変動 | 中 |
| W4 | `tests/` インフラを「後でやる」扱いにし、TDD 推奨領域のカバレッジが漏れる | 高 |
| W5 | Godot プロジェクトの初期化を後半まで遅延、MacBook のリードタイムを浪費 | 中 |
| W6 | PDF 参照タイミングが曖昧で docs/*.md と版ずれが発生 | 中 |
| W7 | モデル重みダウンロード時間 (~5.5GB) がスケジュール外 | 中 |
| W8 | WSL2 のポート公開 (`netsh portproxy`) を検収日当日に忘れる典型事故 | 高 |

### 2.2 採用した再生成案: **契約駆動 (Contract-First)**

`schemas.py` と `ControlEnvelope` JSON fixture を最初の 3 日で凍結し、それ以降は両機並列稼働。モデル pull は Contract 凍結中にバックグラウンドで走らせる。

---

## 3. 採用アーキテクチャ (docs/architecture.md と完全整合)

```
┌─── G-GEAR (Linux / Win+WSL2, RTX 5060 Ti 16GB) ──────────────┐
│ Inference: Ollama (MVP) / SGLang (M7+) / vLLM+LoRA (M9+)     │
│ Simulation: asyncio tick 30Hz 物理 / 0.1Hz 認知               │
│ Memory: sqlite-vec + multilingual-e5-small                    │
│ Gateway: FastAPI + uvicorn + websockets                       │
│   ws://g-gear.local:8000/stream                               │
└───────────────────────────────────────────────────────────────┘
                  ↕ WebSocket (JSON / msgpack)
┌─── MacBook Air M4 (macOS arm64) ─────────────────────────────┐
│ Orchestrator: Python 3.11 asyncio WS client                  │
│ Viz: Godot 4.4 3D viewer (5 zones)                           │
│ Dashboard: Streamlit or FastAPI+HTMX                          │
│ Research: Jupyter notebooks                                   │
│ Docs / PDF / Claude Code CLI のマスター機                     │
└───────────────────────────────────────────────────────────────┘
```

---

## 4. MVP 版 = M2 詳細プラン

### 4.1 MVP の定義 (docs/functional-design.md §4 より)

「1 体の Kant エージェントが peripatos を歩行し、`Memory Stream` に記憶を書き、Godot 4.4 で 30Hz 描画される」。

### 4.2 タスク分割 (`.steering/[YYYYMMDD]-[task-name]/` 単位)

各タスクは `/start-task` で着手し `/finish-task` で終了する。

| # | タスク名 | 担当機 | 工数 | 依存 | 主な参照 Skill |
|---|---|---|---|---|---|
| T01 | `setup-g-gear` | G-GEAR | 1d | — | (環境構築) |
| T02 | `setup-macbook` | MacBook | 0.5d | — | (環境構築) |
| T03 | `pdf-extract-baseline` | MacBook | 0.5d | T02 | — |
| T04 | `pyproject-scaffold` | MacBook | 0.5d | T02 | python-standards, git-workflow, architecture-rules |
| T05 | `schemas-freeze` | MacBook | 1d | T04 | python-standards, persona-erre, architecture-rules |
| T06 | `persona-kant-yaml` | MacBook | 0.5d | T05 | persona-erre |
| T07 | `control-envelope-fixtures` | MacBook | 0.5d | T05 | test-standards, godot-gdscript |
| T08 | `test-schemas` | MacBook | 0.5d | T05, T07 | test-standards |
| T09 | `model-pull-g-gear` (BG) | G-GEAR | 0.5d (実 2-4h) | T01 | llm-inference |
| T10 | `memory-store` | G-GEAR | 1.5d | T08 | test-standards, error-handling |
| T11 | `inference-ollama-adapter` | G-GEAR | 1d | T08, T09 | llm-inference, error-handling |
| T12 | `cognition-cycle-minimal` | G-GEAR | 1.5d | T10, T11 | persona-erre, error-handling |
| T13 | `world-tick-zones` | G-GEAR | 1d | T12 | python-standards |
| T14 | `gateway-fastapi-ws` | G-GEAR | 1d | T13 | error-handling |
| T15 | `godot-project-init` | MacBook | 0.5d | T07 | godot-gdscript |
| T16 | `godot-ws-client` | MacBook | 1d | T15 | godot-gdscript, error-handling |
| T17 | `godot-peripatos-scene` | MacBook | 1d | T16 | godot-gdscript |
| T18 | `ui-dashboard-minimal` (optional) | MacBook | 0.5d | T14 | python-standards |
| T19 | `m2-integration-e2e` | 両機 | 1d | T14, T17 | implementation-workflow, test-standards |
| T20 | `m2-acceptance` | 両機 | 0.5d | T19 | git-workflow |

**実働**: 約 10 日 (並列化後)。時系列積み上げなら 15-18 日相当。

**CSDG 参照**: T05 / T06 / T10 / T11 / T12 で `github.com/mikotomiura/cognitive-state-diary-generator` の実装を参考にする。具体的な引き継ぎ箇所と式・定数は **付録 B** を参照。

### 4.3 依存グラフ (Critical Path)

```
T01 ───┐
T02 ───┴─ T03
       └─ T04 ─ T05 ─┬─ T06
                     ├─ T07 ─ T08 ─── [CONTRACT FREEZE] ─┬─ T10 ─ T11 ─ T12 ─ T13 ─ T14 ┐
                     │                                    │                                 │
                     │                    T09 (BG) ───────┘                                 │
                     │                                                                       │
                     │                                    └─ T15 ─ T16 ─ T17 ─────────────┐│
                     │                                                                      ↓↓
                     │                                    T18 (opt) ──────────────────── T19 ─ T20 (M2)
```

### 4.4 MVP 検収条件

- [ ] G-GEAR で `ollama serve` 起動、`uv run python -m erre_sandbox.inference.server` が ws://g-gear.local:8000/stream を listen
- [ ] Kant エージェントが peripatos ゾーンを周回移動、認知サイクルが 10 秒ごと 1 回 LLM 応答を返す
- [ ] `sqlite-vec` に `episodic_memory` レコードが追加され、`recall_count>0` で再検索される
- [ ] MacBook 側 Godot でアバターが peripatos シーンを 30Hz 更新で歩く
- [ ] `uv run pytest` が schemas / memory / cognition で全グリーン
- [ ] WS 切断で 3 秒以内自動再接続、LLM タイムアウトで「継続行動」フォールバック
- [ ] `.steering/YYYYMMDD-m2-acceptance/` に検収結果と再現手順を記録
- [ ] 作業ブランチ経由で main に merge 後、`v0.1.0-m2` タグを付与

---

## 5. 本番構築版 = M4 → M10-11 の段階プラン

| マイルストーン | ゴール | 代表 `.steering` タスク | 備考 |
|---|---|---|---|
| **M4** | 3 体対話・反省・関係形成 | `cognition-reflection`, `memory-semantic-layer`, `personas-nietzsche-rikyu-yaml`, `gateway-multi-agent-stream` | 認証なし継続 (LAN 前提) |
| **M5** | ERRE モード 6 種切替 (peripatos/chashitsu/zazen/shu/ha/ri) | `erre-mode-fsm`, `erre-sampling-override`, `world-zone-triggers`, `godot-zone-visuals` | サンプリング切替を persona-erre Skill に従って実装 |
| **M7** | 5-8 体 × 12 時間安定運転 | `memory-decay-compression`, `cognition-piano-parallel`, `inference-sglang-migration`, `observability-logging` | **ここで SGLang へ移行**、Ollama は開発時のみに |
| **M9** | LoRA per persona (vLLM) | `inference-vllm-adapter`, `lora-training-pipeline`, `lora-runtime-swap` | M4-M7 で蓄積した ≥1000 ターン/ペルソナの対話ログで訓練 |
| **M10-11** | 4 層評価 + 統計レポート | `eval-layer1-spatial`, `eval-layer2-semantic`, `eval-layer3-ritual`, `eval-layer4-thirdparty`, `eval-statistics-bh-fdr`, `docs-osf-preregistration` | n≥20 試行、BH-FDR 補正、OSF 事前登録 |

**段階的負債解消**: 認証追加 (v1.0 前後)、MkDocs JA/EN (M10)、Zenodo DOI 発行 (v1.0)。

---

## 6. G-GEAR 側アクション一覧

### 6.1 OS / ドライバ / CUDA

```bash
# WSL2 の場合 (PowerShell 管理者)
wsl --install -d Ubuntu-24.04 && wsl --update
# Ubuntu 内
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential git curl avahi-daemon avahi-utils
sudo apt install -y nvidia-cuda-toolkit  # CUDA 12.x
nvidia-smi   # RTX 5060 Ti 16GB が認識されること
```

### 6.2 Python / uv / Ollama

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.11
curl -fsSL https://ollama.com/install.sh | sh

# ~/.bashrc に以下を追加 (llm-inference Skill 準拠)
export OLLAMA_NUM_PARALLEL=4
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0
```

### 6.3 モデル重み (T09 でバックグラウンド pull)

```bash
ollama pull qwen2.5:7b-instruct-q5_K_M        # Qwen3-8B 相当の Q5_K_M
# 代替候補: Llama-3.1-Swallow-8B-Instruct-v0.3 Q5_K_M (HF GGUF → ollama create)
ollama pull multilingual-e5-small             # 埋め込み (Ruri-v3-30m も可)
```

### 6.4 ネットワーク (WSL2 固有)

```powershell
# PowerShell 管理者、1 回だけ
$wsl_ip = (wsl hostname -I).Trim().Split()[0]
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=$wsl_ip
netsh advfirewall firewall add rule name="WSL2 ERRE ws" dir=in action=allow protocol=TCP localport=8000
```

`g-gear.local` 解決: avahi-daemon (Linux ホスト) か MacBook の `/etc/hosts` に IP 直書き。

### 6.5 M7 以降

```bash
uv pip install "sglang[all]"   # 本番推論、M7 で起動
# M9: uv pip install "vllm"     # LoRA hot-swap
```

---

## 7. MacBook Air M4 側アクション一覧

### 7.1 基盤ツール

```bash
xcode-select --install
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.11

brew install --cask godot       # Godot 4.4
brew install poppler            # pdftotext / PDF 画像化
brew install git gh jq
```

### 7.2 エディタ + 拡張

```bash
brew install --cask visual-studio-code   # または cursor
code --install-extension charliermarsh.ruff
code --install-extension ms-python.python
code --install-extension geequlim.godot-tools
```

### 7.3 Godot プロジェクト初期化 (T15)

1. Godot 4.4 起動 → New Project → 場所 `godot_project/`
2. Renderer: **Compatibility** (M4 統合 GPU 省電力)、後で Forward+ に切替可
3. `.gitignore` に `.godot/` (Godot キャッシュ) を追加
4. `godot_project/project.godot` がコミットされることを確認

### 7.4 pyproject.toml (T04 で確定)

候補依存 (すべて Apache-2.0 / MIT / BSD):

```toml
python = "3.11"
pydantic = "^2.7"
fastapi = "^0.115"
uvicorn = {extras = ["standard"], version = "^0.30"}
websockets = "^13"
httpx = "^0.27"
sqlite-vec = "^0.1"
pyyaml = "^6"
numpy = "^2"

[tool.uv.dev-dependencies]
pytest = "^8"
pytest-asyncio = "^0.24"
ruff = "^0.6"
mypy = "^1.11"
streamlit = "^1.39"   # M2 後半以降 (T18 optional)
```

### 7.5 Claude Code マスター機として

- `/start-task`・`/add-feature`・`/fix-bug`・`/refactor`・`/reimagine`・`/review-changes`・`/smart-compact`・`/finish-task` は原則 MacBook で起動
- `.steering/` の `_setup-progress.md` など共有ファイルは MacBook 側のみが編集

---

## 8. PDF 資料 (`ERRE-Sandbox_v0.2.pdf`) の扱い方

### 8.1 立ち位置

- **参照原典**: docs/ 5 ファイルは PDF の内容を既に分解反映済み
- **日々の実装判断は docs/*.md を正**。PDF は (a) docs/ が曖昧なとき、(b) マイルストーン着手時の章再確認、(c) 定期ドリフト検知 に限定利用

### 8.2 T03 で行う pdftotext 化

```bash
# MacBook 側、1 回のみ
mkdir -p docs/_pdf_derived
pdftotext -layout "ERRE-Sandbox_v0.2.pdf" docs/_pdf_derived/erre-sandbox-v0.2.txt
echo "docs/_pdf_derived/" >> .gitignore
```

以後 Claude Code は `Read docs/_pdf_derived/erre-sandbox-v0.2.txt` で章単位読みが可能。

### 8.3 画像・図表が必要な場合

Claude Code の `Read` ツールは PDF を `pages:"1-5"` で直接読めるため、poppler 無しでも代替ルートがある。21 ページのため 5 ページ刻みで読む。

### 8.4 ドリフト検知タスク

M2 完了後と M5 完了後に `.steering/YYYYMMDD-pdf-docs-sync/` で PDF テキストと docs/*.md を突き合わせる。

---

## 9. 両機間連携ワークフロー

| 項目 | ルール |
|---|---|
| マスター機 | **MacBook Air M4** (Claude Code CLI + Godot + PDF 閲覧の中心) |
| G-GEAR の役割 | 「実行機」。推論・記憶・認知系タスクの `/start-task` はこちらで起動 |
| `/start-task` 起動先 | スキーマ/UI/Godot/ドキュメント系 → MacBook、推論/記憶/認知/ワールド系 → G-GEAR |
| Git 同期頻度 | タスク着手時 `git pull` 必須、完了時は作業ブランチを push → PR → `/review-changes` → main merge |
| ブランチ命名 | `feature/schemas-freeze`, `feature/memory-store` など Conventional Branch |
| WIP コミット | 長時間作業は 30-60 分ごとに `chore: wip [task-name]` |
| main 直接 push | **禁止** (docs/development-guidelines.md §8) |
| Contract 凍結中 (T05-T08) | MacBook 単独作業、G-GEAR は T09 モデル pull のみ |
| 同一ファイル並行編集 | Contract 凍結後は物理分離 (タスク分担で重複させない) |

---

## 10. リスクと対処

| # | リスク | 対処 |
|---|---|---|
| R1 | モデル pull 中のネット切断 | `ollama pull` は再開可能、有線推奨 |
| R2 | Qwen3-8B Q5_K_M の VRAM 実測超過 (理論 ~13GB) | context 4K / 並列 4 → 超過時 context 2K / 並列 2 → 最終手段 Q4_K_M。M1 末に実測値で docs/architecture.md §7 を更新 |
| R3 | WSL2 ポート公開忘れ | T01 に `netsh portproxy` をチェックリスト化、検収前に `curl ws://g-gear.local:8000/health` 事前確認 |
| R4 | `g-gear.local` が解決できない | MacBook の `/etc/hosts` に IP 直書きで fallback |
| R5 | SGLang 起動失敗 (M7) | `.steering/m7-sglang-migration/` で段階移行、Ollama fallback を常時ライブに保つ (error-handling Skill) |
| R6 | M4 Python パッケージの arm64 非対応 | uv + pre-built wheel 優先、必要なら G-GEAR 側で uv.lock 生成 |
| R7 | schemas.py へのフィールド後追加 (Contract 破壊) | T06 で Kant YAML の全フィールドを可視化、Pydantic `extra="forbid"` で早期検知、破れたら `/reimagine` |
| R8 | Godot Skinned Mesh アセット不足 | M2 は立方体 + 色マテリアルで許容。M5 以降に Apache/MIT アセット (Mixamo 等) を追加、GPL の Blender ルートは `erre-sandbox-blender/` に完全分離 |
| R9 | `.steering/` の Git コンフリクト | タスクディレクトリ単位で物理分離、共有ファイル (`_setup-progress.md`) は MacBook 単独編集 |
| R10 | PDF と docs/ のドリフト | M2・M5 完了後にドリフト検知タスクを実行 |
| R11 | Claude Code の Read で PDF 大量ページ読みによる context 消費 | 5 ページ刻み + `/smart-compact` を挟む |
| R12 | LoRA 訓練 (M9) のデータ不足 | M4-M7 で対話ログを常時 SQLite 永続化、ペルソナごと ≥1000 ターン蓄積 |
| R13 | sqlite-vec の 10 万件超でパフォーマンス劣化 | `memory/` のバックエンドを早期抽象化、M7 後半で Qdrant + bge-m3 への切替候補 |

---

## 11. Critical Files (実装時の起点)

### 読む (既存)
- `/Users/johnd/ERRE-Sand Box/CLAUDE.md`
- `/Users/johnd/ERRE-Sand Box/docs/architecture.md`
- `/Users/johnd/ERRE-Sand Box/docs/functional-design.md`
- `/Users/johnd/ERRE-Sand Box/docs/repository-structure.md`
- `/Users/johnd/ERRE-Sand Box/docs/development-guidelines.md`
- `/Users/johnd/ERRE-Sand Box/docs/glossary.md`
- `/Users/johnd/ERRE-Sand Box/.steering/_setup-progress.md`

### 新規作成 (T04-T17)
- `/Users/johnd/ERRE-Sand Box/pyproject.toml`
- `/Users/johnd/ERRE-Sand Box/uv.lock`
- `/Users/johnd/ERRE-Sand Box/.python-version`
- `/Users/johnd/ERRE-Sand Box/src/erre_sandbox/__init__.py`
- `/Users/johnd/ERRE-Sand Box/src/erre_sandbox/schemas.py`  ← **Contract の核**
- `/Users/johnd/ERRE-Sand Box/src/erre_sandbox/memory/store.py`
- `/Users/johnd/ERRE-Sand Box/src/erre_sandbox/memory/embedding.py`
- `/Users/johnd/ERRE-Sand Box/src/erre_sandbox/memory/retrieval.py`
- `/Users/johnd/ERRE-Sand Box/src/erre_sandbox/inference/ollama_adapter.py`
- `/Users/johnd/ERRE-Sand Box/src/erre_sandbox/inference/server.py`
- `/Users/johnd/ERRE-Sand Box/src/erre_sandbox/cognition/cycle.py`
- `/Users/johnd/ERRE-Sand Box/src/erre_sandbox/world/tick.py`
- `/Users/johnd/ERRE-Sand Box/src/erre_sandbox/world/zones.py`
- `/Users/johnd/ERRE-Sand Box/personas/kant.yaml`
- `/Users/johnd/ERRE-Sand Box/tests/conftest.py`
- `/Users/johnd/ERRE-Sand Box/tests/test_schemas.py`
- `/Users/johnd/ERRE-Sand Box/tests/fixtures/control_envelope_samples.json`  ← **Godot と Python 両方から読む**
- `/Users/johnd/ERRE-Sand Box/godot_project/project.godot`
- `/Users/johnd/ERRE-Sand Box/godot_project/scenes/MainScene.tscn`
- `/Users/johnd/ERRE-Sand Box/godot_project/scripts/AgentController.gd`
- `/Users/johnd/ERRE-Sand Box/godot_project/scripts/WebSocketClient.gd`
- `/Users/johnd/ERRE-Sand Box/docs/_pdf_derived/erre-sandbox-v0.2.txt` (T03、gitignore)

### 参照する外部リポジトリ (本プロジェクト外)
- `github.com/mikotomiura/cognitive-state-diary-generator` — CSDG (MIT, 作者: mikotomiura)。schemas / 状態遷移 / 2 層メモリ / 3 層 Critic の参照資産。詳細は付録 B

---

## 12. 検証 (Verification)

### MVP (M2) の E2E 動作確認手順

MacBook 側:

```bash
cd "/Users/johnd/ERRE-Sand Box"
git pull
uv sync
uv run pytest                                     # schemas / memory / cognition テストがグリーン
# Godot を起動 → MainScene を Play → ws://g-gear.local:8000/stream に接続
# peripatos ゾーンをアバターが歩いていることを目視確認
```

G-GEAR 側 (同時稼働):

```bash
cd ~/erre-sandbox
git pull && uv sync
ollama serve &
uv run python -m erre_sandbox.inference.server    # FastAPI + WS 起動
# ログで「10秒ごとの認知サイクル完了」が出力されることを確認
# sqlite-vec の DB に insert / retrieve されていることを確認:
sqlite3 erre.db "SELECT count(*) FROM episodic_memory;"
sqlite3 erre.db "SELECT * FROM episodic_memory ORDER BY created_at DESC LIMIT 5;"
```

### 本番構築版 (M4+) の検収は各マイルストーン達成時に `.steering/YYYYMMDD-mN-acceptance/` で別途定義する

---

## 13. 最初に着手するタスク

1. **MacBook 側**で `/start-task` → `[YYYYMMDD]-setup-macbook` (T02)
2. **G-GEAR 側**で `/start-task` → `[YYYYMMDD]-setup-g-gear` (T01)
3. T02 完了後、MacBook で T03 → T04 → T05 (Contract Freeze へ突入)
4. T05 着手と同時に G-GEAR で T09 (モデル pull) をバックグラウンド実行
5. T08 (Contract 凍結) 完了後に両機並列で Phase P (T10-T18) へ

---

## 付録 A: Skill 割り当て一覧

| Skill | 主な適用タスク |
|---|---|
| architecture-rules | T04, T05, T10-T14 |
| implementation-workflow | T10-T19 (共通骨格) |
| llm-inference | T09, T11, T19, M7 (SGLang), M9 (vLLM LoRA) |
| persona-erre | T05, T06, T12, M5 全般 |
| godot-gdscript | T15-T17, M4 複数エージェント, M5 ゾーン視覚 |
| error-handling | T10, T11, T14, T16 |
| test-standards | T07, T08, T10 以降全般 |
| git-workflow | T01, T02 最終 commit, 各 `/finish-task`, T20 タグ付け |
| python-standards | Python を書くすべてのタスク |
| blender-pipeline | MVP 不要、M5+ のアセット追加時のみ |
| project-status | セッション開始時、Plan Mode 起動時の常用 |

---

## 付録 B: CSDG (Cognitive-State Diary Generator) 参照資産マップ

CSDG は本プロジェクトの作者 (mikotomiura) が先行して作成した単一キャラクター向け
日記生成システムで、ERRE パイプラインと「意図的非効率」を既に実装している。
ERRE-Sandbox はこれを複数ペルソナ + 3D 空間 + ローカル LLM に拡張する後継。

### B.1 CSDG の概要

- **URL**: https://github.com/mikotomiura/cognitive-state-diary-generator
- **ライセンス**: MIT (Apache-2.0 OR MIT 互換)
- **言語・管理**: Python 3.11+ / uv / Pydantic v2
- **LLM**: Anthropic Claude (`claude-sonnet-4-20250514`) または Google Gemini (`gemini-2.0-flash`)、`CSDG_LLM_PROVIDER` 環境変数で切替
- **目的**: 架空キャラ「三浦とこみ」(26 歳・バックエンドエンジニア・元哲学大学院生) の 7 日間の一人称ブログ日記を、3 Phase パイプライン (State Update → Content Gen → Critic Eval) で生成
- **docs/erre-design.md**: ERRE 思想 (Extract-Reverify-Reimplement-Express) と「意図的非効率」を明文化済み

### B.2 タスク別の具体的活用ポイント

| タスク | CSDG 参照ファイル | 具体的な活用内容 | 流用方針 |
|---|---|---|---|
| **T05** schemas-freeze | `csdg/schemas.py` | `HumanCondition` (sleep_quality, physical_energy, mood_baseline, cognitive_load, emotional_conflict) のフィールド・range・デフォルト値を `AgentState.Physical` の骨格に採用。`CharacterState` (fatigue, motivation, stress, memory_buffer≤3, relationships dict) の構造を参考。`DailyEvent` (day, event_type, domain, description, emotional_impact) を `Observation` スキーマに応用 | パターン移植 (複数ペルソナ向けに拡張) |
| **T06** persona-kant-yaml | `prompts/System_Persona.md` | ペルソナ定義の項目階層 (背景・個人ブログ・古典参照・文体特性) をペルソナ YAML に反映。CSDG の単一キャラ定義をテンプレート化して偉人ごとに並列化 | 構造のみ参考、中身はペルソナ固有 |
| **T10** memory-store | `csdg/engine/memory.py`, `csdg/schemas.py` の Memory 系 | 2 層構造 (`ShortTermMemory` window_size=3 + `LongTermMemory` beliefs≤10, recurring_themes≤5, turning_points) を参考に、ERRE-Sandbox の 4 種記憶へマッピング: Episodic ← ShortTerm / Semantic ← long_term.beliefs+recurring_themes / Procedural・Relational は ERRE-Sandbox 独自。2 ビュー設計 (`get_context_for_actor()` / `get_context_for_critic()`) を踏襲 | 構造踏襲、sqlite-vec で永続化 |
| **T11** inference-ollama-adapter | `csdg/llm_client.py` | プロバイダー抽象化パターン (環境変数による切替) のみ参考 | API は Ollama / SGLang 向けに完全書き直し |
| **T12** cognition-cycle-minimal | `csdg/engine/state_transition.py` | **半数式 `base = prev * (1 - decay_rate) + event_impact * event_weight`** を流用。LLM delta 合成 `result = base + clip(llm_delta, ±max) * llm_weight + gauss(0, noise_scale)`。`HumanCondition` 自動導出の 4 要素ロジック: sleep_quality ← 前日疲労+ストレスペナルティ+ドリフト / physical_energy ← sleep_quality+前日疲労 / mood_baseline ← 減衰+ランダムドリフト+微小イベント / cognitive_load ← 未解決課題+ストレス+ネガティブイベント累積。clamp: fatigue=[0, clamp_max] / others=[clamp_min, clamp_max]。physical_energy 低下時の motivation ペナルティ適用 | 式・構造をそのまま流用、`config` 定数は ERRE-Sandbox 向けに調整 |
| **M4** cognition-reflection | `csdg/engine/memory.py` `_llm_extract_beliefs_and_themes()` | evict→LLM extract パターンで直近 N 日の記憶から信念・テーマ・転換点を蒸留。reflection トリガー (importance>150 または peripatos/chashitsu 入室) 時の実装ロジックに転用 | ロジックをそのまま使用可能 |
| **M10-11** eval-layer2-semantic | `csdg/engine/critic.py` Layer 2 (StatisticalChecker) | 文字数レンジ / 平均文長 (CSDG では 25-30 字が最適) / 句読点頻度 / 疑問文比率 / trigram overlap (MAX 0.30) / deviation 分析 / 高インパクト時の感情決壊チェック (短文連打 3 回以上, 口語マーカー, 中断表現) | 指標は日記特有→対話文向けに再パラメータ化 |
| **M10-11** eval-layer3-ritual | `csdg/engine/critic.py` Layer 1 (RuleBasedValidator) の余韻テンプレート反復検出 (`_ENDING_TEMPLATE_MARKERS`) | 同じ場所/時刻/構造の連続使用を「儀式の反復性」指標として検出 | 構造のみ参考 |
| **M10-11** eval-layer4-thirdparty | `csdg/engine/critic.py` Layer 3 (LLMJudge) + 逆推定一致スコア | **3 層 Critic + 重み合成 `L1*0.40 + L2*0.35 + L3*0.25`** / L1-L2 コンセンサス補正 `correction = (L12_mean - L3) * 0.5` / Veto 機構 (`has_critical_failure()`) / Reject 条件 (任意軸 < 3) / revision_instruction の二重注入 | ロジックをほぼそのまま転用 |

### B.3 直接引き継ぐ式・定数

| 項目 | 値 / 式 | 出所 |
|---|---|---|
| 半数式状態遷移 | `base = prev * (1 - decay_rate) + event_impact * event_weight` | `state_transition.py` |
| LLM delta 合成 | `base + clip(llm_delta, ±max_llm_delta) * llm_weight + gauss(0, noise_scale)` | `state_transition.py` |
| Critic スコア合成 | `weighted = L1 * 0.40 + L2 * 0.35 + L3 * 0.25` | `critic.py` |
| L1/L2 コンセンサス補正 | `correction = (L12_mean - L3) * 0.5` | `critic.py` |
| `_MAX_TRIGRAM_OVERLAP` | 0.30 (超過で -1.5 ペナルティ) | `critic.py` |
| `_CRITICAL_TRIGRAM_OVERLAP` | 0.50 (veto 発動) | `critic.py` |
| `_CRITICAL_CHAR_DEVIATION` | 0.5 (±50% 逸脱で全軸 veto) | `critic.py` |
| Reject 条件 | 任意軸 < 3 (1-5 スケール) | `critic.py` |
| 高インパクト判定 | `|emotional_impact| > 0.7` | schemas.py |
| `ShortTermMemory.window_size` | 3 日 → ERRE-Sandbox は 10 秒 tick 単位に再校正 | `memory.py` |
| `LongTermMemory` 上限 | beliefs ≤ 10, recurring_themes ≤ 5 | `memory.py` |
| `HumanCondition` デフォルト | sleep_quality=0.7, physical_energy=0.7, mood_baseline=0.0, cognitive_load=0.2 | `schemas.py` |
| リトライ設計 | max 3 回 + temperature 段階減衰 + 構造違反時 bonus 1 回 (予算外) | `CSDG_MAX_RETRIES=3`, `CSDG_INITIAL_TEMPERATURE=0.7` |

### B.4 取り込まない (再設計する) 部分

- **LLM 呼び出しコード** (`csdg/llm_client.py`): クラウド API 前提 → Ollama / SGLang 用に完全書き直し
- **プロンプトテキスト本体** (`prompts/System_Persona.md` 等): 単一キャラクター (三浦とこみ) 向け → 複数偉人ペルソナ向けに書き直し、ERRE モード別サンプリング指示を追加
- **Express 層 (日記テキスト出力)**: 3D 可視化 (Godot ControlEnvelope 送信) に差し替え
- **時間単位**: CSDG は 1 日 1 更新 (7 日で完結) → ERRE-Sandbox は 10 秒 tick (0.1Hz 認知)。`decay_rate` や `window_size` は tick 単位に再校正
- **`scenario.py`** (7 日分のイベント台本): ERRE-Sandbox はワールド物理と他エージェントから動的にイベントが発生するため不要
- **`quality_report.py` の 8 項目 PASS/FAIL 判定**: 日記特有の多様性指標 (書き出し 6 種・余韻 9 種) → 対話/行動向けに再設計

### B.5 MVP (M2) で優先取り込む 3 点

1. **T05**: `HumanCondition` の 5 フィールドを `AgentState.Physical` の骨格に採用
2. **T12**: 半数式状態遷移と `HumanCondition` 自動導出の 4 要素ロジックを移植
3. **T10**: 2 層メモリの役割分担 (短期=Episodic, 長期=Semantic) を反映

### B.6 本番版 (M4+) で取り込む 3 点

1. **M4**: `_llm_extract_beliefs_and_themes()` の evict→extract パターンを reflection 実装に採用
2. **M10-11 Layer 4**: 3 層 Critic + 逆推定一致スコア + Veto + 重み合成 (0.40/0.35/0.25) を LLM-as-judge 評価の実装ベースにする
3. **M10-11 Layer 2**: 統計的文体検証 (trigram overlap, 平均文長, 疑問文比率) を対話文向けにチューニングして転用

### B.7 ライセンス・帰属

- CSDG は **MIT**。ERRE-Sandbox の **Apache-2.0 OR MIT** と互換
- **コード断片をそのままコピーする場合**: `NOTICE` ファイルに CSDG への帰属表示を追加
- **パターン・式・ロジックを参考にリライトする場合**: `.steering/[task]/decisions.md` に「CSDG の `~~` を参考に `~~` を採用」と明記 (法的帰属義務なし、学術的礼節として推奨)

### B.8 参照優先順位 (同一事項に複数情報源がある場合)

1. ERRE-Sandbox `docs/*.md` (このプロジェクトの正)
2. `ERRE-Sandbox_v0.2.pdf` (docs の出典原典)
3. CSDG `csdg/schemas.py`, `engine/*.py` (実装パターンの実例)
4. CSDG `docs/erre-design.md` (ERRE 思想の先行定義)
5. 学術論文 (Park et al. 2023, Sumers et al. 2023, Oppezzo & Schwartz 2014 等)


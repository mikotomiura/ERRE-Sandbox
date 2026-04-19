# Claude Code 環境構築進捗

> このファイルは構築の進捗を記録する。各 setup-* コマンドが完了するたびに更新される。
> セッションを跨いだ継続のための引き継ぎ情報として機能する。

## プロジェクト概要

- **名称**: ERRE-Sandbox
- **目的**: 歴史的偉人（アリストテレス・カント・ニーチェ・利休・道元など）の認知習慣を、ローカルLLMで駆動される自律エージェント群として3D空間に再実装し、「意図的非効率性」と「身体的回帰」を設計プリミティブとして知的創発を観察する、完全OSS・予算ゼロの研究プラットフォーム
- **技術スタック**: Python / FastAPI / Godot (3D) / Ollama + llama.cpp / sqlite-vec / SGLang
- **チーム規模**: 個人 (1人)
- **重視する品質特性**: 再現可能性, パフォーマンス, 保守性・拡張性, セキュリティ
- **構築開始日**: 2026-04-17
- **仕様書**: ERRE-Sandbox_v0.2.pdf (21ページ, 研究企画書兼技術設計書)

## 構築進捗

- [x] **Phase 0: Bootstrap** (このコマンド)
  - 完了日時: 2026-04-17
  - 備考: 環境チェック完了、git init 実施、ディレクトリ構造作成済み
- [x] **Phase 1: /setup-docs** — 永続ドキュメント
  - 完了日時: 2026-04-17
  - 作成ファイル:
    - docs/functional-design.md
    - docs/architecture.md
    - docs/repository-structure.md
    - docs/development-guidelines.md
    - docs/glossary.md
  - 主要な決定事項:
    - 優先ユースケース: ゲーム開発者向け自律NPC AIミドルウェア
    - ドキュメント言語: 日本語メイン、OSS公開に必要な箇所は英語追加
    - アーキテクチャ: 特定パターンに縛らず、必要に応じて破壊と再構築
    - 全5ドキュメントの横断整合性レビュー完了
- [x] **Phase 2: /setup-claude-md** — CLAUDE.md と .steering
  - 完了日時: 2026-04-17
  - 作成ファイル:
    - CLAUDE.md (87 行)
    - .steering/README.md
    - .steering/_template/ × 5 ファイル (requirement, design, tasklist, blockers, decisions)
  - .gitignore 更新: なし (.steering/ は git 追跡対象)
  - Grill me: 実施済み — 全チェック項目 OK
- [x] **Phase 3: /setup-skills** — Skill 群
  - 完了日時: 2026-04-17
  - 作成 Skill:
    - python-standards (SKILL.md, patterns.md) — Python 3.11 / asyncio / Pydantic v2 / ruff 規約
    - test-standards (SKILL.md, examples.md) — pytest-asyncio / conftest / 埋め込みプレフィックステスト
    - git-workflow (SKILL.md, checklist.md) — Conventional Commits / Refs: / リリースタグ
    - error-handling (SKILL.md, examples.md) — SGLang→Ollama フォールバック / 再接続 / gather
    - architecture-rules (SKILL.md, decision-tree.md) — レイヤー依存 / GPL禁止 / API禁止
    - implementation-workflow (SKILL.md, anti-patterns.md) — 調査→設計→実装→テスト→レビュー骨格
    - project-status (SKILL.md) — 動的 Shell Preprocessing Skill
  - 動的 Skill 数: 1 (project-status)
- [x] **Phase 4: /setup-agents** — サブエージェント群
  - 完了日時: 2026-04-18
  - 作成エージェント:
    - file-finder (sonnet) — ファイル検索・分類専門
    - dependency-checker (sonnet) — 依存関係調査専門
    - impact-analyzer (sonnet) — 変更影響範囲分析専門
    - code-reviewer (opus) — コード品質・可読性レビュー専門
    - test-analyzer (sonnet) — テスト失敗原因分析専門
    - security-checker (opus) — セキュリティリスク監査専門
    - test-runner (haiku) — テスト実行・結果要約専門
    - build-executor (haiku) — ビルド実行・結果要約専門
    - log-analyzer (sonnet) — ログ分析・異常パターン検出専門
- [x] **Phase 5: /setup-commands** — ワークフローコマンド群
  - 完了日時: 2026-04-18
  - 作成コマンド:
    - /start-task
    - /add-feature
    - /fix-bug
    - /refactor
    - /reimagine
    - /review-changes
    - /smart-compact
    - /finish-task
- [x] **Phase 6: /setup-hooks** — Hook 群（3 層構成: Preflight / Guard / Report）
  - 完了日時: 2026-04-18
  - 作成 Hook:
    - SessionStart: .claude/hooks/session-start.sh（動的情報表示）
    - UserPromptSubmit: Preflight 層 / preflight.sh（毎ターン .steering/ 状態・git 状態・reimagine 状態を動的表示、BLOCK せず）
    - PreToolUse: Guard 層 / pre-edit-steering.sh + pre-edit-banned.sh（違反ブロック + パス時 `[guard] PASS` 出力）
    - PostToolUse: Report 層 / post-fmt.sh（Edit/Write 後に ruff format、変更時のみ `[fmt] ruff format applied`）
    - Stop: Report 層 / stop-check.sh（ruff check + mypy、問題時のみ WARN）
  - 出力プレフィックス統一: [preflight] / [guard] / [fmt] / [stop]
  - settings.json: 新規作成（全 hook を `"type": "command"` に統一）
  - 外部スクリプト:
    - .claude/hooks/session-start.sh
    - .claude/hooks/preflight.sh
    - .claude/hooks/pre-edit-steering.sh
    - .claude/hooks/pre-edit-banned.sh
    - .claude/hooks/post-fmt.sh
    - .claude/hooks/stop-check.sh
- [x] **Phase 7: /verify-setup** — 整合性検証
  - 完了日時: 2026-04-18
  - 検証結果: HEALTHY
  - 修正が必要な項目: 3 件 (すべて LOW、運用上問題なし)
  - レポート: .steering/_verify-report-20260418.md

## 次に実行すべきコマンド

`/start-task` で最初の実装タスクを開始

## 各コマンド実行前のチェックリスト

各 setup-* コマンドを実行する前に、以下を必ず確認してください:

1. `/context` で使用率が 30% 以下か
2. 適切なモデルに切り替えてあるか（設計系は Opus、実装系は Sonnet）
3. 前のコマンドが完了し、`/clear` でセッションがリセットされているか
4. このファイル (`.steering/_setup-progress.md`) を Read で読んで進捗を確認したか

## 構築物の相互参照マップ

このセクションは各 setup-* コマンドが完了するたびに更新される。

### Skill リスト
- python-standards
- test-standards
- git-workflow
- error-handling
- architecture-rules
- implementation-workflow
- project-status (動的)
- llm-inference (動的)
- persona-erre
- godot-gdscript
- blender-pipeline

### Skill → Agent 参照
- test-standards → code-reviewer, test-analyzer
- python-standards → code-reviewer
- error-handling → code-reviewer, security-checker, log-analyzer
- architecture-rules → impact-analyzer, code-reviewer, security-checker
- git-workflow → dependency-checker
- llm-inference → code-reviewer, log-analyzer, security-checker
- persona-erre → code-reviewer, impact-analyzer
- godot-gdscript → code-reviewer, impact-analyzer
- blender-pipeline → security-checker, code-reviewer

### Skill → Command 参照
- implementation-workflow → /add-feature, /fix-bug, /refactor（共通骨格）
- test-standards → /add-feature, /fix-bug, /refactor（Step F/tasklist 参照）
- llm-inference → /add-feature, /fix-bug（inference/ 関連タスク時）
- persona-erre → /add-feature（personas/ や schemas.py の ERREMode 関連タスク時）
- godot-gdscript → /add-feature（godot_project/ 関連タスク時）

### Agent → Command 参照
- file-finder → implementation-workflow 経由で /add-feature, /fix-bug, /refactor
- impact-analyzer → implementation-workflow 経由で /add-feature, /fix-bug, /refactor
- code-reviewer → implementation-workflow 経由で全実装系 + /review-changes, /finish-task
- security-checker → /add-feature (Step H), /review-changes
- test-runner → implementation-workflow 経由で全実装系 + /refactor 交互実行 + /finish-task
- test-analyzer → implementation-workflow 経由で /add-feature, /fix-bug
- log-analyzer → /fix-bug (Step 2b)

### Hook → Command 参照
- SessionStart Hook → 全コマンドのセッション開始時に動作
- UserPromptSubmit Hook (Preflight 層) → 全ターンで動作。編集を伴わないターン（調査・質問・計画）でもプロジェクト状態を可視化
- PreToolUse Hook (Guard 層) → /add-feature, /fix-bug, /refactor の実装ステップで動作。パス時は `[guard] PASS` で可視化
- PostToolUse Hook (Report 層) → /add-feature, /fix-bug, /refactor 等の実装系で動作、変更時のみ報告
- Stop Hook (Report 層) → 全コマンドのターン終了時に動作、問題時のみ WARN

---

## Phase 8: MVP 実装フェーズ (2026-04-18〜)

実装プランは `.steering/20260418-implementation-plan/MASTER-PLAN.md` を参照。

- [x] **T02 setup-macbook** (MacBook, 実作業 2026-04-18)
  - Homebrew 5.1.6 / gh 2.90.0 / jq 1.8.1 / poppler 26.04.0 / Godot 4.6.2 / uv Python 3.11.15
  - VS Code 拡張 ruff + godot-tools 追加
  - `~/.zprofile` に brew shellenv を追加、`code` CLI は `~/.local/bin/code` に symlink
  - 記録: `.steering/20260418-setup-macbook/`
  - 設計判断 3 件: Godot 4.6 採用 / code symlink を user ディレクトリ / Python 併存
- [x] **T01 setup-g-gear** (G-GEAR, 実作業 2026-04-18)
  - OS: Windows 11 Home (native, WSL2 不採用) — /reimagine で WSL2 初回案を破棄し素 Windows 案を採用
  - uv 0.11.7 (pip 経由 user install) / CPython 3.11.15 (uv 管理) / Ollama 0.21.0 (winget)
  - User PATH 追加: `%APPDATA%\Python\Python311\Scripts`, `%USERPROFILE%\.local\bin`, Ollama は winget が自動追加
  - User env vars: `OLLAMA_NUM_PARALLEL=4` / `OLLAMA_FLASH_ATTENTION=1` / `OLLAMA_KV_CACHE_TYPE=q8_0`
  - GPU: RTX 5060 Ti 16GB を `nvidia-smi -L` で確認、CUDA は Ollama 同梱ランタイムで利用
  - 検証: `uv sync` 成功、`ruff check` / `ruff format --check` / `mypy src` グリーン、`pytest` 96 passed / 16 skipped
  - 記録: `.steering/20260418-setup-g-gear/` (requirement / design / tasklist / decisions)
  - 設計判断 2 件: 素 Windows 採用 (D1) / OLLAMA_* を User scope (D2)
- [x] **T03 pdf-extract-baseline** (MacBook, 2026-04-18)
  - `docs/_pdf_derived/erre-sandbox-v0.2.txt` を生成 (939 行 / 73 KB)
  - `.gitignore` に `docs/_pdf_derived/` 追加、派生物は Git 管理外
  - 想定キーワード (ERRE-Sandbox / peripatos / chashitsu / 守破離) 48 件ヒット
  - 記録: `.steering/20260418-pdf-extract-baseline/`
- [x] **T04 pyproject-scaffold** (MacBook, 2026-04-18)
  - `pyproject.toml` (uv_build + PEP 735 `[dependency-groups]` + ruff ALL + hybrid strict mypy + pytest-asyncio mode=auto)
  - `.python-version` = 3.11 / `src/erre_sandbox/{schemas.py,inference,memory,cognition,world,ui,erre}` レイヤー骨格
  - `tests/test_smoke.py` で 7 レイヤー import 検証 (2 件 pass)
  - `LICENSE` / `LICENSE-MIT` / `NOTICE` 正式テキスト配置、`README.md` 最小版 (EN/JA)
  - `uv sync` / `ruff check` / `ruff format --check` / `mypy src` / `pytest` の 5 コマンドすべて緑
  - 記録: `.steering/20260418-pyproject-scaffold/` (requirement/design/design-v1/design-comparison/decisions/tasklist)
  - /reimagine 適用: v2 + ハイブリッド調整 3 点を採用
  - 設計判断 8 件: uv_build 採用 / PEP 735 / ruff ALL / hybrid strict mypy / line-length 88 / uv.lock コミット / LICENSE 正式配置 / schemas.py docstring-only
- [x] **T05 schemas-freeze** ★ Contract 凍結の核 (MacBook, 2026-04-18, PR #5/#6)
  - Pydantic v2 で `AgentState` / `Observation` / `ControlEnvelope` を凍結
  - `ControlEnvelope` / `Observation` に discriminated union (Annotated + Field(discriminator="kind")) を採用
  - 静的 `PersonaSpec` と動的 `AgentState` を完全分離 (橋渡しは `persona_id` のみ)
  - `MemoryEntry` に embedding を持たせず、T10 で `StoredMemory` を別定義する方針
  - 記録: `.steering/20260418-schemas-freeze/`
- [x] **T06 persona-kant-yaml** (MacBook, 2026-04-18, PR #7)
  - `personas/kant.yaml` を operational orientation (trigger→behavior→mechanism→consequence) で定義
  - epistemic 3-tier (fact / legend / speculative) 完備、`primary_corpus_refs` は lean (orphan ゼロ)
  - `default_sampling = (temperature=0.60, top_p=0.85, repeat_penalty=1.12)` = 後続ペルソナ温度帯見取り図の基準
  - 記録: `.steering/20260418-persona-kant-yaml/`
- [x] **T07 control-envelope-fixtures** (MacBook, 2026-04-18, PR #8)
  - `fixtures/control_envelope/` を top-level 配置 (Godot developer が Python 依存なしで読める)
  - tick=42 の coherent scenario で 7 fixture (Kant が peripatos で歩行) を束ねる
  - `peripatetic` モード sampling_overrides = (+0.3, +0.05, -0.1) を persona-erre Skill と同期
  - Kant speech は *Kritik der praktischen Vernunft* Beschluss 冒頭の後半句を採用
  - 記録: `.steering/20260418-control-envelope-fixtures/`
- [x] **T08 test-schemas** ★ Contract 凍結の境界 (MacBook, 2026-04-18, PR #9)
  - 3 層契約ガード: Layer 1 (boundary 検証) / Layer 2 (meta-invariant: `extra="forbid"` + `schema_version`) / Layer 3 (JSON Schema golden drift 検知)
  - `tests/schema_golden/` に golden を配置 (fixtures/ と意味を分離)
  - `conftest.py` に callable factory `make_agent_state` / `make_envelope` + convenience fixture の二層構成
  - ルックアップテーブル方式で `make_envelope` をディスパッチ (未消費 overrides は ValueError)
  - 記録: `.steering/20260418-test-schemas/`
- [x] **T15 godot-project-init** (MacBook, 2026-04-18, PR #10)
  - Phase P MacBook 側ラインの scaffold (v2: Scaffolded Handoff を採用、v1 最小ブートを破棄)
  - `godot_project/` に Godot 4.4 互換 + 4.6.2 実機、GL Compatibility renderer
  - MainScene 階層を patterns.md §2 に完全準拠 (ZoneManager / AgentManager / WebSocketClient / UILayer)
  - 各 dir に README.md (`.gitkeep` ではない) で GPL 分離ルール等の文脈を即時提供
  - `tests/test_godot_project.py` で必須ファイル存在 / Python 混入ゼロ / Godot headless boot を機械検証
  - 記録: `.steering/20260418-godot-project-init/`
- [x] **T09 model-pull-g-gear** (G-GEAR, 実作業 2026-04-18)
  - 推論 LLM: `qwen3:8b` (500a1f067a9f, **5.2 GB**, pull 24 分) — MASTER-PLAN §6.3 の `qwen3:8b-q5_K_M` / `qwen2.5:7b-instruct-q5_K_M` は registry 未登録のため fallback 採用 (decisions D1)
  - 埋め込みモデル: `nomic-embed-text` (0a109f422b47, **274 MB, 768 次元**, pull 7 分) — `multilingual-e5-small` も未登録のため fallback 採用 (decisions D2)
  - Ollama 再起動: tray 起動が失敗したため `ollama.exe serve` を env vars 明示 export + `nohup &` で直接起動 (decisions D3)
  - 実測: ollama load 後 VRAM delta 6.2 GB (未 load 1307 MiB → load 後 7493 MiB、総使用 ~46%)、`qwen3:8b` 日本語挨拶 `こんにちは` で応答確認 (cold start 35s, keep-alive 5 min)
  - 記録: `.steering/20260418-model-pull-g-gear/` (requirement / design / tasklist / decisions D1-D4 + 実測補足)
  - 関連 T10 影響: embedding 768 次元と `nomic-embed-text-v1.5` のプレフィックス規約が T10 design の `DEFAULT_DIM` / D5 に反映済み
  - 設計判断 4 件: D1 (LLM fallback) / D2 (embedding fallback) / D3 (tray 迂回して ollama serve 直接) / D4 (2 段階 commit 戦略)
- [ ] T10-T14 は G-GEAR 側 Phase P (MASTER-PLAN.md §4.2 参照)
- [x] **T16 godot-ws-client** (MacBook, 2026-04-18, PR #12)
  - 3 スクリプト完全分離: `WebSocketClient.gd` (auto-reconnect + MAX_FRAME_BYTES)
    / `EnvelopeRouter.gd` (7 専用 signal emit) /
    `AgentManager.gd` (`has_signal` duck typing でログスタブ)
  - Fixture 境界分離: `scripts/dev/FixturePlayer.gd` + `scenes/dev/FixtureHarness.tscn`
    で production path に dev コード不混入
  - Contract ガード新設: `tests/test_envelope_kind_sync.py` で schemas.py §7 ↔
    EnvelopeRouter.gd の kind 集合一致を CI で自動検出
  - Godot headless 回帰: `tests/test_godot_ws_client.py` で 7 kind 順序再生を検証
  - `tests/_godot_helpers.py` に `resolve_godot` 抽出 (test_godot_project.py と共有)
  - MainScene.tscn: 3 script attach + EnvelopeRouter ノード追加 + signal 配線
    (`load_steps=6`, 手動編集 — 次セッションでエディタ canonical 化予定 L5)
  - 設計フロー: v1 素直案 → `/reimagine` で v2 再生成 → 比較 → v2 フル採用
    (V1-W1/W2/W4/W5/W6 を構造で解消、design-comparison.md に比較表)
  - code-reviewer HIGH 1 + MEDIUM 3、security-checker HIGH 1 + MEDIUM 1 対応
  - 全テスト 100 pass / 15 skip、ruff / format / mypy 全緑
  - 記録: `.steering/20260418-godot-ws-client/`
    (requirement / design / design-v1 / design-comparison / decisions / blockers / tasklist)
- [x] **T10 memory-store** (G-GEAR, 設計 PR #15 + 実装 PR #16, 2026-04-18〜19)
  - 設計: `.steering/20260418-memory-store/` (requirement / design / tasklist / decisions D1-D5)
  - /reimagine 適用: v1 (単一テーブル + embedding BLOB + strength カラム) を破棄、**v2 (kind 別テーブル + 共有 `vec0` + 関数 decay)** を採用 (D1)
  - 設計判断 5 件: kind 別テーブル + 共有 vec0 (D1) / decay ハイパラ λ=0.1, β=0.2 (D2) / Procedural / Relational は最小 DDL (D3) / 設計ロック分離 (D4) / 埋め込みプレフィックス強制 (D5)
  - **実装 (PR #16)**:
    - `src/erre_sandbox/memory/store.py` — 4 kind テーブル (episodic / semantic / procedural / relational) + 共有 `vec_embeddings` vec0 virtual table (embed_dim=768)、async API は `asyncio.to_thread` で sqlite3 wrap (`check_same_thread=False`)、`knn_ids` / `evict_episodic_before` / `list_world_scope` 補助 API 公開
    - `src/erre_sandbox/memory/embedding.py` — `QUERY_PREFIX` / `DOC_PREFIX` 定数 + `embed_query` / `embed_document` / 低レベル `embed` の 3 段 API (D5 強制)、httpx.AsyncClient、失敗を `EmbeddingUnavailableError` に正規化
    - `src/erre_sandbox/memory/retrieval.py` — 純粋関数 `score(importance, age, recall, cos)` + `Retriever` クラス、per-agent (k_agent=8) + world-scope (k_world=3) を合成、`mark_recalled` 副作用 (決定論的 now 注入可)
    - `src/erre_sandbox/memory/__init__.py` — public API 14 件 re-export
  - テスト追加 (+38 件、計 134 passed / 16 skipped): test_store.py (14) / test_embedding.py (7) / test_retrieval.py (12) / test_embedding_prefix.py (3, CI 必須・削除禁止) + conftest.py
  - 依存: T09 完了済 (nomic-embed-text 768 次元が `DEFAULT_DIM` と一致) / T08 schemas.MemoryEntry (Contract 凍結済)
- [x] **T17 godot-peripatos-scene** (MacBook, 2026-04-19, PR #17)
  - Phase P MacBook 側ラインの 3 件目、T16 Router signal contract を 3D 表現に接続
  - `scenes/zones/Peripatos.tscn` — 40×4m PlaneMesh + 非対称 post 6 本
    (北 4 / 南 2、Königsberg 散歩道メタファー) + Start/End marker + OmniLight3D
  - `scenes/agents/AgentAvatar.tscn` — Node3D + CapsuleMesh Body + 前方指示
    BoxMesh + Label3D SpeechBubble (patterns.md §3 からは CharacterBody3D →
    Node3D / AnimationPlayer 除去で逸脱、理由は decisions.md 判断 2/3)
  - `scripts/AgentController.gd` (約 120 行) — Tween 駆動移動、envelope の
    `speed` を duration 計算に使用 (Contract-First)、`is_finite()` /
    `MAX_TWEEN_DURATION=30s` / 水平 `look_at` ガード
  - `scripts/AgentManager.gd` 書き換え — T16 print stub を avatar 実操作に置換、
    `preload()` 直接参照で **MainScene.tscn 変更 0 行** (L5 完全解消)
  - `scripts/WorldManager.gd` — ZONE_MAP + `_spawn_initial_zones()` で起動時に
    peripatos を ZoneManager 配下へ add_child
  - `tests/test_godot_peripatos.py` — module-scoped fixture で subprocess 共有、
    6 assertion (zone spawn / avatar spawn / speech / move speed=1.30 /
    animation / no errors)
  - 設計フロー: v1 素直案 (patterns.md 直コピー、V1-W1〜W8 弱点) → `/reimagine`
    で v2 再生成 → v2 フル採用 (V1-W1/W2/W3/W4 を構造で解消)
  - code-reviewer HIGH 1 + MEDIUM 5、security-checker MEDIUM 2 対応
  - 全テスト 106 passed / 15 skipped (T16 100 から +6)、ruff / format / mypy 緑
  - 記録: `.steering/20260419-godot-peripatos-scene/`
    (requirement / design / design-v1 / design-comparison / decisions /
    blockers / tasklist)
- [x] **T11 inference-ollama-adapter** (G-GEAR, 2026-04-19, feature branch)
  - Phase P G-GEAR 側ラインの 2 件目、T10 `EmbeddingClient` と対称な
    Ollama `/api/chat` 薄クライアント
  - `src/erre_sandbox/inference/sampling.py` — 純粋関数
    `compose_sampling(SamplingBase, SamplingDelta) -> ResolvedSampling` +
    `_clamp` で 3 値を `[0.01, 2.0] / [0.01, 1.0] / [0.5, 2.0]` にクランプ
  - `src/erre_sandbox/inference/ollama_adapter.py` — `OllamaChatClient`
    (ClassVar defaults / httpx.AsyncClient DI / async with / is_closed
    idempotent close) + `ChatMessage` / `ChatResponse` (frozen) +
    `OllamaUnavailableError` 1 種に httpx 4 種例外を正規化
  - `inference/__init__.py` — 7 シンボル top-level re-export
    (`OllamaChatClient`, `ChatMessage`, `ChatResponse`,
    `OllamaUnavailableError`, `ResolvedSampling`, `compose_sampling`,
    `DEFAULT_CHAT_MODEL`)
  - `tests/test_inference/` 新規 (23 件): sampling 8 件 (境界値上下完備) /
    adapter 15 件 (MockTransport + `test_close_is_idempotent` +
    `test_injected_client_not_closed_by_adapter`)
  - 設計フロー: v1 素直案 (error-handling examples.md 直移植、10 弱点) →
    `/reimagine` で v2 再生成 → v2 フル採用 (V1-W1/W2/W4/W5/W6/W7/W8/W9 を
    構造で解消)
  - 設計判断 8 件: D1 Contract-First 採用 / D2 `/api/chat` / D3 frozen
    ChatResponse / D4 sampling 分離 / D5 sampling 後勝ち / D6 エラー正規化 /
    D7 `qwen3:8b` default / D8 7 シンボル re-export
  - code-reviewer HIGH 2 + MEDIUM 5 + LOW 4、security-checker MEDIUM 2 + LOW 4
    を総合評価 → 即対応 6 件 + 保留 5 件 (blockers.md BL-1〜BL-5)
  - 全テスト 157 passed / 23 skipped (134 baseline から +23)、ruff / format /
    mypy 全緑
  - 記録: `.steering/20260419-inference-ollama-adapter/`
    (requirement / design / design-v1 / design-comparison / decisions /
    blockers / tasklist)
- [x] **T12 cognition-cycle-minimal** (G-GEAR, 2026-04-19, feature branch)
  - MVP M2 の核となる 1 tick 認知パイプライン (1 エージェント分の CoALA + ERRE
    9 ステップ)
  - `src/erre_sandbox/cognition/state.py` — CSDG 半数式 (MASTER-PLAN B.3 MVP 優先 #2)
    の pure function: `advance_physical(Physical, events) -> Physical`
    (4 要素導出 sleep_quality / physical_energy / mood_baseline / cognitive_load) +
    `apply_llm_delta(Cognitive, LLMPlan) -> Cognitive`
    (valence/arousal/motivation/stress)、`StateUpdateConfig` dataclass で係数調整可、
    `Random` 注入で決定論化
  - `src/erre_sandbox/cognition/parse.py` — `LLMPlan(frozen BaseModel, 8 フィールド)`
    + `parse_llm_plan(text)` JSON 抽出 (code fence 許容、brace balancer で引用内
    ブレース処理) + `MAX_RAW_PLAN_BYTES=64KB` DoS ガード (security M1 対応)
  - `src/erre_sandbox/cognition/prompting.py` — 3-stage system prompt
    (`_COMMON_PREFIX` → persona 固有 → 動的 tail、RadixAttention 最適化) +
    `build_user_prompt` (最新観察 + memories + JSON スキーマヒント)
  - `src/erre_sandbox/cognition/importance.py` — event_type lookup +
    intensity/emotional_impact/importance_hint 補正 → `[0, 1]` clamp
  - `src/erre_sandbox/cognition/cycle.py` — `CognitionCycle.step()` 9-step
    orchestrator + `CycleResult(frozen BaseModel, llm_fell_back flag)` +
    `CognitionError`。LLM/Embed 不通と parse 失敗の 3 経路を単一 fallback に
    畳み込み、それ以外は crash-loud (error-handling Skill §ルール 5)
  - `cognition/__init__.py` — 13 シンボル top-level re-export
  - `tests/test_cognition/` 新規 46 件: importance 7 / parse 11 / state 10 /
    prompting 8 / cycle 10 (happy path + ollama-fail + parse-fail +
    embedding-fail + reflection trigger + sampling override + speech/move 分岐)
  - `pyproject.toml` — `tests/**` per-file-ignores に `S311` 追加 (テスト seed
    用途での Random 許容)
  - 設計フロー: v1 素直案 (1 関数、regex parse、except 握りつぶし、12 弱点) →
    `/reimagine` → v2 (5 モジュール分離 + Pydantic LLMPlan + pure state + RNG DI +
    fallback フラグ) フル採用
  - 設計判断 10 件 (decisions.md): D1 5-module v2 / D2 JSON+Pydantic parse /
    D3 sampling 型強制 / D4 RNG DI 決定論 / D5 種類別 catch / D6 llm_fell_back
    side-channel / D7 3-stage prompt / D8 StateUpdateConfig 係数外出し /
    D9 Reflection トリガーのみ / D10 tests S311 許容
  - code-reviewer HIGH 2 + MEDIUM 5 + LOW 4、security-checker MEDIUM 2 + LOW 4
    → 即対応 9 件 + 保留 9 件 (blockers.md BL-1〜BL-9)
  - 全テスト 203 passed / 23 skipped (157 baseline から +46)、ruff / format /
    mypy 全緑
  - 記録: `.steering/20260419-cognition-cycle-minimal/`
    (requirement / design / design-v1 / design-comparison / decisions /
    blockers / tasklist)
- [x] **T13 world-tick-zones** (G-GEAR, 2026-04-19, feature branch)
  - M2 の Simulation Layer ドライバ: 30Hz 物理 / 0.1Hz 認知 / 1Hz heartbeat を
    単一コルーチン + heapq 絶対時刻スケジューラで駆動 (v1 の TaskGroup 3 タスク案を
    `/reimagine` で破棄して v2 採用)
  - `src/erre_sandbox/world/zones.py` — Voronoi 最近傍ゾーン判定
    (`ZONE_CENTERS` / `ADJACENCY` / `locate_zone` / `default_spawn` /
    `adjacent_zones`)。矩形 AABB + `ZoneNotFoundError` を排し、全座標が
    5 ゾーンに一意分割される (壁・境界ケースの分岐ゼロ)
  - `src/erre_sandbox/world/physics.py` — `Kinematics` (world 内部型、
    schemas.Position を汚さない) + `step_kinematics` 等速直線移動 +
    `apply_move_command`。snap 時も `locate_zone` で zone 再計算 (stale zone 対策)
  - `src/erre_sandbox/world/tick.py` — `Clock` ABC + `RealClock` /
    `ManualClock(advance(dt) で決定論)` + `ScheduledEvent(order=True, seq tie-break)` +
    `AgentRuntime` + `WorldRuntime`。anti-drift 絶対時刻再スケジュール
    (`due_at += period`)、`asyncio.gather(return_exceptions=True)` で N 認知並列、
    unbounded envelope queue + `recv_envelope()` / `drain_envelopes()` 2 面 API
  - `world/__init__.py` — 14 シンボル top-level re-export
  - `tests/test_world/` 新規 45 件: zones 21 / physics 9 / tick 15
    (ManualClock FIFO / stop lifecycle / N エージェント gather / 例外隔離 /
    `llm_fell_back` 継続 / MoveMsg → 物理補間 / ゾーン跨ぎで
    `ZoneTransitionEvent.from_zone=prev` 保証 / heartbeat 周期 / drain FIFO)
  - 設計フロー: v1 (TaskGroup + AABB + Protocol + bounded Queue) → `/reimagine` →
    v2 (単一コルーチン heapq + Voronoi + Clock ABC + unbounded Queue) フル採用
  - code-reviewer HIGH 2 + MEDIUM 2: 即対応完了 (from_zone バグ修正 +
    gather 二重 catch 削除 + snap 時 zone 再計算 + register_agent docstring)
  - 全テスト 248 passed / 23 skipped (203 baseline から +45)、
    ruff / format / mypy --strict 全緑
  - 記録: `.steering/20260419-world-tick-zones/`
    (requirement / design / design-v1 / design-comparison / decisions / tasklist)
- [x] **T14 gateway-fastapi-ws** (G-GEAR, 2026-04-19, feature branch)
  - FastAPI + Starlette WebSocket ゲートウェイ。T13 `WorldRuntime._envelopes` を唯一の
    consumer として複数 Godot peer に fan-out
  - 設計: 関数 = 状態機械 (Session クラス不在)、`asyncio.timeout(HANDSHAKE_TIMEOUT_S/
    IDLE_DISCONNECT_S)` ネストで watchdog タスク排除、単一 `_broadcaster` タスクから
    `Registry.fan_out` で全 per-session bounded queue (256) に push、満杯時 oldest 2 件
    drop + `ErrorMsg(backlog_overflow)` warning + 新 env の 3 step
  - `src/erre_sandbox/integration/gateway.py` — Registry / `ws_observe` / `_recv_loop` /
    `_send_loop` / `_broadcaster` / `_lifespan` / `_health` / `_NullRuntime` / `make_app` /
    `__main__` エントリポイント (`uvicorn.run(..., factory=True)`)
  - `integration/__init__.py` — `Registry` / `make_app` を 2 シンボル追加 re-export
  - 既存 Mac PR #23 の `integration/protocol.py` (SessionPhase, HANDSHAKE_TIMEOUT_S,
    IDLE_DISCONNECT_S, MAX_ENVELOPE_BACKLOG, SCHEMA_VERSION_HEADER) を完全消費
  - `tests/test_integration/conftest.py` — `MockRuntime` / `app` / `client` /
    `fast_timeouts` fixture 追加 (既存 T19 scenario fixture は保持)
  - `tests/test_integration/test_gateway.py` 新規 20 件:
    Layer A 純粋関数 (Registry fan_out 4 件、_parse_envelope 4 件、_make_* 2 件) +
    Layer B TestClient 統合 (/health / handshake success / forward envelope /
    handshake_timeout / schema_mismatch / invalid first frame / invalid during active /
    idle_disconnect / 2-client fan-out / NullRuntime blocks forever)
  - 設計フロー: v1 (Session クラス + TaskGroup + session.py 分離 + watchdog task)
    → `/reimagine` → v2 (関数即セッション + `asyncio.timeout` ネスト + 単一
    gateway.py + Registry 薄ラッパ) フル採用
  - code-reviewer HIGH 2 + MEDIUM 4: 全対応 (internal_error 情報漏洩防止 +
    `maxsize=0` ガード + `_send_loop` の OSError/RuntimeError 包含 +
    `_parse_envelope` の `len(raw)` 前段チェック + conftest docstring 更新)
  - security-checker HIGH 1 + MEDIUM 2: 全対応 (ErrorMsg.detail 固定化 +
    encode コスト削減)、CRITICAL ゼロ
  - 全テスト 294 passed / 34 skipped (274 baseline から +20)、
    ruff / format / mypy --strict 全緑
  - 記録: `.steering/20260419-gateway-fastapi-ws/`
    (requirement / design / design-v1 / design-comparison / decisions / tasklist)
- [x] **T18 ui-dashboard-minimal** (MacBook, 2026-04-19, PR #25)
  - MVP Observability の optional 層: FastAPI mini app + typed `UiMessage` + stub
    エンドポイント。T14 gateway とは独立プロセスで、`ui/godot_bridge.py` (Python 側)
    や Streamlit/HTMX ダッシュボードに差し替え可能なインターフェース雛形
  - 記録: `.steering/20260419-ui-dashboard-minimal/` (requirement / design / design-v1 /
    design-comparison / decisions / tasklist)
  - commit: `a414886 feat(ui): T18 ui-dashboard-minimal — FastAPI mini + typed UiMessage + stub`

- [x] **T19 m2-integration-e2e (design phase)** (両機, 2026-04-19, PR #23)
  - Contract 層の契約凍結と scenario テスト雛形の整備。`src/erre_sandbox/integration/`
    配下に `contract` module を追加、Layer A/B/C 観点の skeleton tests を
    先に書く設計駆動フェーズ
  - `integration-contract.md` / `metrics.md` / `scenarios.md` /
    `t20-acceptance-checklist.md` を同時整備し、T20 検収で参照される ACC 項目を
    事前確定
  - 記録: `.steering/20260419-m2-integration-e2e/` (requirement / design / design-v1 /
    design-comparison / decisions / integration-contract / metrics / scenarios /
    t20-acceptance-checklist / tasklist)
  - commit: `5423b26 feat(integration): T19 m2-integration-e2e — contract module + skeleton tests (design phase)`

- [x] **T19 m2-integration-e2e (execution phase)** (両機, 2026-04-19, PR #27 + PR #28)
  - PR #23 で用意した scenario skeleton tests を `unskip` + Layer B (`TestClient`
    integration) / Layer C (smoke) を稼働。続いて MacBook 側で Godot 4.6 Editor 上に
    live WebSocket 接続を実装、client 側 `HandshakeMsg` 送出を追加して
    gateway `session ACTIVE` まで到達
  - 検証の過程で **GAP-1〜GAP-5** が発覚:
    - GAP-1 `WorldRuntime ↔ Gateway` 配線 (`_NullRuntime` 依存) → M4 繰越
    - GAP-2 Godot live 自動 E2E テスト未整備 → M7 検討
    - GAP-3 session counter 監視運用未策定 → T20 で解消
    - GAP-4 Godot 4.6 diff 削減 (記録のみ)
    - GAP-5 `_NullRuntime` docs 未反映 → T20 で解消
  - 記録: `.steering/20260419-m2-integration-e2e-execution/` (requirement / design /
    decisions / handoff-to-macbook / known-gaps / macbook-verification / tasklist)
  - commits:
    - `df00a1e feat(integration): T19 execution — unskip scenario tests + Layer B/C smoke`
    - `6c6be16 feat(godot): T19 MacBook live integration — client HandshakeMsg + 4.6 upgrades`

- [x] **T20 m2-acceptance** (両機, 2026-04-19, tag `v0.1.0-m2` 付与)
  - MVP M2 検収。**6 ACC 全 PASS** (`ACC-SCENARIO-WALKING` / `ACC-SESSION-COUNTER` /
    `ACC-DOCS-UPDATED` / `ACC-HANDSHAKE` / `ACC-SCHEMA-COMPAT` / `ACC-DISCONNECT-RECONNECT`)
  - GAP 解消: GAP-3 (`session-counter-runbook.md` + 実測 evidence 90s `sessions=0` 定着) /
    GAP-5 (`docs/architecture.md` §Gateway に `_NullRuntime` 注意書き追加)。
    GAP-1 は M4 `gateway-multi-agent-stream` に繰越、GAP-2 は M7、GAP-4 は記録のみ
  - §3 disconnect/reconnect 実機検証: `RECONNECT_DELAY: 5.0 → 2.0` (commit `d52ee8c` +
    `.claude/skills/godot-gdscript/patterns.md §1` 同期更新) により、**reconnect 2.1s**
    (MacBook ms 粒度) + **≤ 1s 観測** (G-GEAR 1Hz 粒度) の 2 系統で MVP 検収条件
    「WS 切断で 3 秒以内自動再接続」(MASTER-PLAN §4.4) を PASS
  - Evidence 3 層構造: ① MacBook ms 粒度 Godot timestamp / ② G-GEAR `localhost:8000/health`
    1Hz probe / ③ uvicorn server-side `WebSocket /ws/observe [accepted]` log
    (Mac IP `192.168.3.118` から ×2 連続 accept を裏取り)
  - 記録: `.steering/20260419-m2-acceptance/` (requirement / design / decisions /
    acceptance-checklist / handoff-to-g-gear / session-counter-runbook / tasklist /
    evidence/README.md + 11 本の probe/restart log)
  - PR 系譜:
    - PR #28 (`6c6be16`): MacBook live integration + 残存課題記録
    - PR #29 (`8167076`): T20 M2 acceptance closeout — GAP-3/5 解消 + checklist 本体作成
    - PR #30 (`16b6d0e`): ACC-SESSION-COUNTER 実測 evidence (`sessions=0` 定着 90s)
    - PR #31 (`2cdbf6e`): G-GEAR 側 localhost cycle evidence (4 auto-reconnect サイクル)
    - PR #32 (`d52ee8c` + `9fa33e9`): `RECONNECT_DELAY` 短縮 + 2.1s reconnect 実測、
      merge 時に `v0.1.0-m2` tag 付与
    - PR #33: フル diff 版を別路線で作成したが PR #32 と conflict のため close、
      PR #34 に最小変更分割
    - PR #34 (`452b28b`): G-GEAR 側 localhost probe 補強 evidence (1Hz 粒度の裏取り)
  - **M2 closeout 宣言**: Contract layer (WS/Handshake/Session FSM/Schema) 完全動作、
    GAP-1 (WorldRuntime↔Gateway 配線) のみ M4 に繰越。次マイルストーンは **M4
    `gateway-multi-agent-stream`** で full-stack orchestrator 実装

- [x] **T21 m2-functional-closure** (両機, 2026-04-20, tag `v0.1.1-m2` 付与)
  - MVP M2 の **機能的完了**。T20 契約層 closeout 後に残っていた GAP-1
    (WorldRuntime↔Gateway 配線欠落) を解消し、MASTER-PLAN §4.4 の 4 検収項目のうち
    **#1-#3 を実機 evidence 付きで PASS**、#4 Godot 30Hz 歩行は Mac 側録画で視覚確認
  - 両機フロー: Mac 側で composition root を設計・実装 → G-GEAR 側で live 検証 →
    検証中に bug を発見・修正 → 実機 evidence 取得 → 相互に records を push
  - Mac 側成果 (PR #36):
    - `src/erre_sandbox/bootstrap.py` (`BootConfig` + `_load_kant_persona` +
      `_build_kant_initial_state` + `bootstrap` + `_supervise` with `AsyncExitStack` +
      `asyncio.wait(FIRST_COMPLETED)` + SIGINT/SIGTERM handler)
    - `src/erre_sandbox/__main__.py` (argparse CLI shell)
    - `src/erre_sandbox/inference/ollama_adapter.py` に `health_check()` 追加
    - `pyproject.toml` の `[project.scripts]` に `erre-sandbox` entry point
    - `docs/architecture.md` §Gateway / §Inference 文言更新
    - `tests/test_bootstrap.py` 11 件 PASS
    - 設計フロー: v1 (素直な単一 `__main__`) と v2 (Composition Root + Lifecycle-First)
      を `/reimagine` で比較し **ハイブリッド採択**
  - G-GEAR 側成果 (PR #37、live 検証で発覚した 2 件の bug を修正):
    - **fix #1** (`src/erre_sandbox/bootstrap.py`): `MemoryStore(...)` 作成直後に
      `create_schema()` を呼ぶ処理が欠けており、初回 cognition tick で
      `sqlite3.OperationalError: no such table: episodic_memory` が発生していた。
      `memory.create_schema()` を追加 (idempotent な `CREATE TABLE IF NOT EXISTS`)
    - **fix #2** (`src/erre_sandbox/world/tick.py`): `cognition/cycle._build_envelopes`
      が MoveMsg の `target` に「現在 x/y/z + zone フィールド差し替え」で作成していたが、
      `step_kinematics` は `locate_zone(dest.x, dest.y, dest.z)` で現在 zone を
      再計算するため、zone 跨ぎが発生せず observation が pending に積まれなかった。
      `_consume_result` で `locate_zone(tgt) ≠ tgt.zone` を検知したら
      `default_spawn(tgt.zone)` に resolve (yaw/pitch 保持、layer 越境を避け
      world 側で完結)
  - 実機 evidence (`.steering/20260419-m2-functional-closure/evidence/`):
    - `gateway-health-20260420-002242.json` — schema 0.1.0-m2 / status ok / active_sessions=2
    - `ollama-tags-20260420-002242.json` — qwen3:8b + nomic-embed-text:latest
    - `listen-ports-20260420-002242.txt` — port 8000 (gateway) + 11434 (ollama) LISTEN
    - `cognition-ticks-20260420-002242.log` — `api/chat` + `api/embed` の ~10s cadence 40 行
    - `episodic-memory-summary-20260420-002242.txt` — **COUNT=20 / MAX(recall_count)=23**
    - `episodic-memory-sample-20260420-002242.txt` — 10 件サンプル (peripatos↔study 10 往復)
  - 記録: `.steering/20260419-m2-functional-closure/` (requirement / design / design-v1 /
    design-comparison / tasklist / handoff-to-g-gear / acceptance-evidence + evidence/)
  - commits:
    - `ac9c16f docs(steering): T21 m2-functional-closure の要件/設計/比較/タスクリストを作成`
    - `19b5e50 feat(orchestrator): introduce bootstrap.py + __main__ for 1-Kant walker`
    - `0dcaf53 docs(steering): T21 G-GEAR 側引き継ぎ手順を追加 — live 検証 4 検収項目 + v0.1.1-m2 tag 運用`
    - `8a2c657 fix(orchestrator): bootstrap schema init + world zone resolution — unlocks MVP §4.4 #3`
    - `8027df2 docs(steering): T21 MVP §4.4 3/4 検収項目 evidence + MASTER-PLAN [x] + known-gaps GAP-1 解消`
  - PR 系譜:
    - PR #36 (Mac): composition root (`bootstrap.py` + `__main__.py` + `erre-sandbox` CLI)
    - PR #37 (G-GEAR): bug fix 2 件 + 実機 evidence + docs 整合、merge 後に `v0.1.1-m2` tag 付与
  - 残: MVP §4.4 #4 Godot 30Hz 歩行の録画 (`evidence/godot-walking-*.mp4`) を
    Mac 側 follow-up commit で追加予定 (tag への影響なし)
  - **MVP 機能的完了宣言**: Contract layer (`v0.1.0-m2`) + functional closure (`v0.1.1-m2`)
    で M2 完了。GAP-1 は T21 で解消、残 GAP (GAP-2 live 自動 E2E / GAP-4 Godot 4.6 diff)
    は後続マイルストンに配置。次マイルストンは **M4 `gateway-multi-agent-stream`**
    (3-agent 拡張 + reflection + semantic memory layer)

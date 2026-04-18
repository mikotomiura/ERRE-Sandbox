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
- [ ] T17 godot-peripatos-scene (次タスク) — MacBook 側 Phase P 3 件目
- [ ] T18-T20 は MASTER-PLAN.md §4.2 参照

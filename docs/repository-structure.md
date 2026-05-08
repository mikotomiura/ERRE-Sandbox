# リポジトリ構造定義書

## 1. ディレクトリ構成

```
> **現状実装スナップショット (last verified 2026-05-08)**: 本ツリーは
> `find src tests godot_project personas fixtures docs .claude .agents` 実態を反映する。
> `[planned]` ラベルは将来追加予定で現存しないファイル/ディレクトリを示す
> (codex addendum D6 + 「現状 snapshot」運用)。

```
erre-sandbox/
├── src/erre_sandbox/           # Python ソースコード
│   ├── __init__.py
│   ├── __main__.py             # `python -m erre_sandbox` エントリポイント (CLI)
│   ├── bootstrap.py            # Composition Root: MemoryStore / CognitionCycle /
│   │                           # WorldRuntime / DialogScheduler の配線
│   ├── schemas.py              # AgentState, Memory, ControlEnvelope (Pydantic v2)
│   ├── contracts/              # 軽量 Pydantic 契約 (PR #111 / codex F5 で導入)
│   │   ├── __init__.py         # M2_THRESHOLDS / Thresholds 再エクスポート
│   │   ├── thresholds.py       # M2 受け入れ閾値 (pydantic + stdlib のみ依存)
│   │   └── eval_paths.py       # M9-eval 4 層 contract (raw_dialog ↔ metrics 境界)
│   ├── erre/                   # ERRE パイプライン DSL (M5 で完成)
│   │   ├── fsm.py              # ERREModeTransitionPolicy / DefaultERREModePolicy
│   │   └── sampling_table.py   # 8 モード x 3 パラメータの SAMPLING_DELTA_BY_MODE
│   ├── inference/              # G-GEAR 側 — LLM 推論
│   │   ├── sglang_adapter.py   # SGLang バックエンド [planned: M7+ 移行]
│   │   ├── ollama_adapter.py   # Ollama バックエンド (現状 default)
│   │   └── sampling.py         # ERRE mode 別 sampling compose
│   ├── memory/                 # 記憶システム (sqlite-vec + semantic layer)
│   │   ├── store.py            # sqlite-vec ラッパー (upsert/recall_semantic 含む)
│   │   └── embedding.py        # 埋め込みモデル管理 (現状: nomic-embed-text 768d)
│   ├── cognition/              # CoALA 認知サイクル
│   │   ├── cycle.py            # Observe → Act ループ
│   │   ├── reflection.py       # Reflector collaborator (M4)
│   │   ├── prompting.py        # system/user prompt ビルダー
│   │   ├── importance.py       # importance scoring
│   │   ├── parse.py            # LLM 出力パース
│   │   └── state.py            # state 更新ヘルパ
│   ├── integration/            # プロセス境界の配線 (M4 で追加)
│   │   ├── gateway.py          # FastAPI + WebSocket (`/ws/observe`, `/health`)
│   │   ├── dialog.py           # InMemoryDialogScheduler + proximity auto-fire
│   │   ├── dialog_turn.py      # OllamaDialogTurnGenerator (M5、inference 層を例外的に import)
│   │   ├── protocol.py         # envelope routing 判定
│   │   ├── metrics.py          # 現在は contracts/thresholds.py への shim (PR #111 で再構成)
│   │   ├── scenarios.py        # 統合テスト用シナリオ
│   │   └── acceptance.py       # acceptance probe ヘルパ
│   ├── evidence/               # post-hoc metric 集計 (M8 で追加、M9-eval で拡張)
│   │   ├── metrics.py          # M8 baseline quality (self_repetition / cross_persona_echo / bias_fired)
│   │   ├── scaling_metrics.py  # M8 scaling profile (pair_info_gain / late_turn_fraction / zone_kl)
│   │   ├── tier_a/             # M9-eval Tier-A pipeline
│   │   │   ├── burrows.py      # Burrows Δ (persona consistency)
│   │   │   ├── mattr.py        # Moving Average Type-Token Ratio (lexical diversity)
│   │   │   ├── nli.py          # NLI claim-conservation (transformers pipeline)
│   │   │   ├── novelty.py      # MPNet sentence-transformer 由来 semantic novelty
│   │   │   └── empath_proxy.py # Empath secondary diagnostic (Big5 主張不可)
│   │   ├── reference_corpus/   # PD reference text (Burrows / NLI baseline)
│   │   ├── eval_store.py       # DuckDB raw_dialog/metrics 単 file ストア
│   │   ├── capture_sidecar.py  # capture status + md5 receipt sidecar JSON
│   │   ├── golden_baseline.py  # GoldenBaselineDriver (stimulus 駆動)
│   │   └── bootstrap_ci.py     # bootstrap 信頼区間 helpers (HIGH-2)
│   ├── cli/                    # subcommand 実装 (M8 で追加、M9-eval で拡張)
│   │   ├── baseline_metrics.py # `erre-sandbox baseline-metrics`
│   │   ├── export_log.py       # `erre-sandbox export-log`
│   │   ├── scaling_metrics.py  # `erre-sandbox scaling-metrics`
│   │   ├── eval_run_golden.py  # `python -m erre_sandbox.cli.eval_run_golden` (M9-eval P3a)
│   │   └── eval_audit.py       # `python -m erre_sandbox.cli.eval_audit` (M9-eval ME-9 gate)
│   ├── world/                  # ワールドシミュレーション
│   │   ├── tick.py             # asyncio tick loop (WorldRuntime)
│   │   └── zones.py            # peripatos/chashitsu/agora/garden/study
│   └── ui/                     # MacBook 側 — 可視化 (依存先: schemas.py + contracts/ のみ)
│       ├── __init__.py
│       └── dashboard/          # サーバサイド集計 + Streamlit/HTMX [planned] フロント
│           ├── __init__.py
│           ├── messages.py     # AlertRecord / MetricsView などの Pydantic
│           └── state.py        # MetricsAggregator / ThresholdEvaluator / DashboardState
├── godot_project/              # MIT ライセンスの Godot 4.6 シーン
│   ├── project.godot           # Godot 4.6 (config_version=5、features=4.6/GL Compatibility)
│   ├── scenes/
│   │   ├── MainScene.tscn      # ルートシーン
│   │   ├── agents/             # 3D アバター
│   │   ├── dev/                # 開発時 viewport / probe
│   │   └── zones/              # 5 ERRE ゾーン + Study + BaseTerrain
│   │       ├── Peripatos.tscn
│   │       ├── Chashitsu.tscn
│   │       ├── Zazen.tscn
│   │       ├── Agora.tscn
│   │       ├── Garden.tscn
│   │       ├── Study.tscn
│   │       └── BaseTerrain.tscn
│   ├── scripts/                # GDScript (.gd) — Agent / World / WebSocket / ReasoningPanel ほか
│   └── assets/                 # モデル・テクスチャ
├── personas/                   # 偉人ペルソナ定義 (現行 3 体、M4 で実装済)
│   ├── kant.yaml               # カント
│   ├── nietzsche.yaml          # ニーチェ
│   └── rikyu.yaml              # 利休
│                               # 将来追加予定 (M9+ scaling trigger 確定後):
│                               # 4th persona (agora 主体仮説) / dogen / aristotle / thoreau 等
├── fixtures/                   # Wire contract specimens (言語中立)
│   └── control_envelope/       # ControlEnvelope 各 kind の JSON + README
├── corpora/                    # PD ソース (青空文庫/Gutenberg/archive.org)
├── data/                       # ランタイム / 評価データ
│   └── eval/                   # M9-eval 出力 (DuckDB + sidecar JSON)
│       ├── pilot/              # Phase 3a pilot 採取
│       └── calibration/        # Phase 2 wall-budget calibration runs (隔離)
├── golden/                     # M9-eval golden battery 入力 (stimulus YAML 等)
├── tests/                      # pytest-asyncio テスト
│   ├── conftest.py
│   ├── test_schemas.py
│   ├── test_architecture/      # 層依存 invariant (PR #111 で導入)
│   ├── test_memory/
│   ├── test_cognition/
│   ├── test_inference/
│   ├── test_integration/
│   ├── test_evidence/
│   ├── test_erre/
│   ├── test_ui/
│   ├── test_world/
│   └── test_godot_project.py
├── examples/
│   └── walking_thinkers_12h/   # 12時間シミュレーション設定
├── docs/                       # 永続ドキュメント (本ファイル群)
│   ├── functional-design.md
│   ├── architecture.md
│   ├── repository-structure.md
│   ├── development-guidelines.md
│   └── glossary.md
├── .claude/                    # Claude Code 設定 (canonical)
│   ├── agents/                 # サブエージェント定義
│   ├── commands/               # スラッシュコマンド
│   ├── skills/                 # スキル定義
│   └── hooks/                  # フック
├── .agents/                    # Codex 向け SKILL mirror (PR で commit)
│   └── skills/                 # `.claude/skills` のサブセット
├── .steering/                  # タスク単位の作業記録
│   ├── _setup-progress.md      # 構築進捗
│   └── _template/              # タスク用テンプレート
├── .github/                    # CI/governance
│   └── workflows/ci.yml        # uv sync --frozen --all-groups → ruff / mypy / pytest を lint/typecheck/test の 3 並列 jobs で実行
├── .pre-commit-config.yaml     # local hook (ruff check + ruff format --check) — uv run で uv.lock 固定版を呼ぶ SSoT 構成
├── pyproject.toml              # uv + ruff + pytest + mypy 設定
├── uv.lock                     # 依存ロックファイル
├── .python-version             # 3.11 pin
├── LICENSE                     # Apache-2.0
├── LICENSE-MIT                 # MIT
├── NOTICE                      # 帰属表示
├── CITATION.cff                # [planned] Zenodo DOI 連携 (現存しない)
├── CODE_OF_CONDUCT.md          # [planned] Contributor Covenant 2.1 (現存しない)
├── CLAUDE.md                   # Claude Code への指示
├── AGENTS.md                   # Codex への指示 (CLAUDE.md と並列、PR で commit)
├── ERRE-Sandbox_v0.2.pdf       # 研究企画書兼技術設計書
└── README.md                   # 英語主体、日本語ジャンプリンク付き
```

## 2. ディレクトリの責務

### `src/erre_sandbox/`
- **目的**: ERRE-Sandbox の全 Python ソースコード
- **置くべきもの**: ビジネスロジック、データスキーマ、推論アダプタ、記憶システム、認知サイクル、UI クライアント
- **置くべきでないもの**: テスト、設定ファイル、ドキュメント、3D アセット

### `tests/`
- **目的**: テストコード
- **構造**: `src/erre_sandbox/` の構造をミラーする (`test_memory/`, `test_cognition/` 等)
- **置くべきでないもの**: テストデータ以外のアセット

### `godot_project/`
- **目的**: Godot 4.6 の 3D シーン・スクリプト・アセット
- **置くべきもの**: `.tscn` シーン、`.gd` スクリプト、3D モデル、テクスチャ
- **置くべきでないもの**: Python コード (Python 側は `src/erre_sandbox/ui/dashboard/` 配下で WebSocket 接続を扱う)

### `personas/`
- **目的**: 偉人ペルソナの YAML 定義と LoRA 設定
- **構造**: 1 偉人 1 YAML ファイル。事実/伝説フラグ付き認知習慣リスト含む

### `fixtures/`
- **目的**: Wire contract の言語中立な specimen (Python + Godot + 将来の他言語クライアントが参照)
- **構造**: `schemas.py` の discriminated union (例: §5 Observation, §7 ControlEnvelope) 1 つにつき 1 サブディレクトリを作り、その配下に `*.json` と README を置く
- **初期メンバ**: `control_envelope/` (T07 で追加)
- **置くべきでないもの**: 単なるテスト用の throwaway データ (→ `tests/` 配下のインライン dict)
- **関連**: `src/erre_sandbox/schemas.py` が唯一の真実。fixture はそこから派生する specimen

### `corpora/`
- **目的**: パブリックドメインの一次史料テキスト
- **置くべきもの**: 青空文庫・Gutenberg・archive.org から取得した PD テキスト
- **置くべきでないもの**: 著作権保護下のテキスト

### `docs/`
- **目的**: 永続的なプロジェクトドキュメント
- **置くべきもの**: 機能設計書、技術設計書、リポジトリ構造、開発ガイドライン、用語集
- **置くべきでないもの**: タスク単位の作業記録 (→ `.steering/`)

### `.claude/`
- **目的**: Claude Code の設定一式
- **詳細**: CLAUDE.md を参照

### `.steering/`
- **目的**: タスク単位の作業記録
- **構造**: `[YYYYMMDD]-[task-name]/` 形式でタスクごとにディレクトリ作成

## 3. ファイル命名規則

| 種類 | 規則 | 例 |
|---|---|---|
| Python モジュール | snake_case | `ollama_adapter.py`, `dashboard/state.py` |
| Python クラス | PascalCase | `AgentState`, `MemoryStream` |
| Python 関数・変数 | snake_case | `dump_for_prompt()`, `tick_count` |
| Python 定数 | UPPER_SNAKE_CASE | `DEFAULT_TEMPERATURE`, `MAX_AGENTS` |
| テストファイル | `test_` prefix + snake_case | `test_schemas.py`, `test_reflection.py` |
| GDScript | PascalCase | `AgentController.gd`, `WorldManager.gd` |
| Godot シーン | PascalCase | `MainScene.tscn`, `Peripatos.tscn` |
| YAML (ペルソナ) | snake_case | `kant.yaml`, `rikyu.yaml` |
| ドキュメント | kebab-case | `functional-design.md`, `repository-structure.md` |
| 設定ファイル | ツール標準に従う | `pyproject.toml`, `.python-version` |

## 4. インポート規則

- **相対パス vs 絶対パス**: `src/erre_sandbox/` 内では絶対パス (`from erre_sandbox.schemas import AgentState`) を使用
- **循環参照**: 禁止。型ヒントのみの参照は `from __future__ import annotations` + `TYPE_CHECKING` で解決
- **レイヤー間の依存方向** (詳細は `.claude/skills/architecture-rules/SKILL.md` のテーブル):
  - `schemas.py` → 他モジュールへの依存なし (最下層)
  - `contracts/` → `schemas.py`, pydantic, stdlib のみ (PR #111 / codex F5 で導入。複数層から参照される軽量 Pydantic 契約。`integration/` の重い `__init__.py` を経由せず `ui/` から直接 import 可)
  - `inference/` → `schemas.py`, `contracts/`
  - `memory/` → `schemas.py`, `contracts/`
  - `cognition/` → `inference/`, `memory/`, `schemas.py`, `contracts/`, `erre/`
  - `world/` → `cognition/`, `schemas.py`, `contracts/`
  - `integration/` → `world/`, `cognition/`, `memory/`, `inference/`, `schemas.py`, `contracts/` (プロセス境界: gateway, dialog scheduler)
  - `ui/` → `schemas.py`, `contracts/` のみ (UI は WebSocket 経由で疎結合、`integration/` には触らない)
  - `bootstrap.py` → 全サブパッケージ (Composition Root のみ横断可)

```
bootstrap.py ──┐  (Composition Root)
               ▼
   integration/ → world/ → cognition/ → inference/
                                      → memory/
                                           ↓
ui/ ────→ schemas.py + contracts/ ← (全モジュールが参照)
```

## 5. 新規ファイル追加時のルール

新しいファイルを追加する際の判断フロー:

1. **このファイルはどのレイヤーに属するか?**
   - LLM 推論関連 → `inference/`
   - 記憶・検索関連 → `memory/`
   - 認知サイクル関連 → `cognition/`
   - ワールド・物理関連 → `world/`
   - プロセス境界 (gateway, scheduler, protocol) → `integration/`
   - 可視化・UI 関連 → `ui/`
   - ERRE パイプライン関連 → `erre/`
   - データスキーマ → `schemas.py` に追記
   - 複数レイヤーから参照される軽量 Pydantic 契約 (閾値定数・config モデル等) → `contracts/`
   - 複数サブパッケージを束ねる起動・配線のみ → `bootstrap.py`
2. **既存のディレクトリに置くべきか、新しいディレクトリを作るべきか?**
   - 既存ディレクトリの責務に含まれるなら既存に追加
   - 新ディレクトリは 3 ファイル以上になる見込みがある場合のみ作成
3. **命名規則に従っているか?** (上記テーブル参照)
4. **対応するテストファイルはどこに置くか?**
   - `src/erre_sandbox/[module]/[file].py` → `tests/test_[module]/test_[file].py`
5. **依存方向は正しいか?**
   - 上のレイヤー図に反する依存を追加していないか確認

## 6. 禁止パターン

- `src/erre_sandbox/` の外にビジネスロジックを置く
- `tests/` の構造を `src/` と乖離させる
- `godot_project/` 内に Python コードを置く (WebSocket で疎結合)
- `schemas.py` から他の `src/erre_sandbox/` モジュールを import する
- `ui/` から `inference/` や `memory/` を直接 import する (Gateway 経由で通信)
- 著作権保護下のテキストを `corpora/` に含める
- GPL 依存ライブラリを `src/erre_sandbox/` で import する (→ 別パッケージに分離)

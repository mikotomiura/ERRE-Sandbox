# リポジトリ構造定義書

## 1. ディレクトリ構成

```
erre-sandbox/
├── src/erre_sandbox/           # Python ソースコード
│   ├── __init__.py
│   ├── __main__.py             # `python -m erre_sandbox` エントリポイント (CLI)
│   ├── bootstrap.py            # Composition Root: MemoryStore / CognitionCycle /
│   │                           # WorldRuntime / DialogScheduler の配線
│   ├── schemas.py              # AgentState, Memory, ControlEnvelope (Pydantic v2)
│   ├── erre/                   # ERRE パイプライン DSL (M5 で完成)
│   │   ├── fsm.py              # ERREModeTransitionPolicy / DefaultERREModePolicy (zone/fatigue/shuhari hook)
│   │   └── sampling_table.py   # 8 モード x 3 パラメータの SAMPLING_DELTA_BY_MODE 単一起源
│   ├── inference/              # G-GEAR 側 — LLM 推論
│   │   ├── sglang_adapter.py   # SGLang バックエンド
│   │   ├── ollama_adapter.py   # Ollama バックエンド (開発用)
│   │   └── sampling.py         # ERRE mode 別 sampling compose
│   ├── memory/                 # 記憶システム (sqlite-vec + semantic layer)
│   │   ├── store.py            # sqlite-vec ラッパー (upsert/recall_semantic 含む)
│   │   └── embedding.py        # 埋め込みモデル管理
│   ├── cognition/              # CoALA 認知サイクル
│   │   ├── cycle.py            # Observe → Act ループ
│   │   ├── reflection.py       # Reflector collaborator (M4)
│   │   ├── prompting.py        # system/user prompt ビルダー
│   │   ├── importance.py       # importance scoring
│   │   ├── parse.py            # LLM 出力パース
│   │   └── state.py            # state 更新ヘルパ
│   ├── integration/            # プロセス境界の配線 (M4 で追加、M5 で dialog_turn 追加)
│   │   ├── gateway.py          # FastAPI + WebSocket (`/stream`, `/ws/observe`, `/health`)
│   │   ├── dialog.py           # InMemoryDialogScheduler + proximity auto-fire
│   │   ├── dialog_turn.py      # OllamaDialogTurnGenerator (M5、inference 層を例外的に import)
│   │   ├── protocol.py         # envelope routing 判定
│   │   ├── metrics.py          # 統合層の観測メトリクス
│   │   ├── scenarios.py        # 統合テスト用シナリオ
│   │   └── acceptance.py       # acceptance probe ヘルパ
│   ├── evidence/               # post-hoc metric 集計 (M8 で追加)
│   │   ├── metrics.py          # baseline quality (self_repetition / cross_persona_echo / bias_fired)
│   │   └── scaling_metrics.py  # scaling profile (pair_info_gain / late_turn_fraction / zone_kl)
│   ├── cli/                    # subcommand 実装 (M8 で追加)
│   │   ├── baseline_metrics.py # `erre-sandbox baseline-metrics`
│   │   ├── export_log.py       # `erre-sandbox export-log`
│   │   └── scaling_metrics.py  # `erre-sandbox scaling-metrics`
│   ├── world/                  # ワールドシミュレーション
│   │   ├── tick.py             # asyncio tick loop (WorldRuntime)
│   │   └── zones.py            # peripatos/chashitsu/agora/garden/study
│   └── ui/                     # MacBook 側 — 可視化
│       ├── ws_client.py        # WebSocket クライアント
│       ├── dashboard.py        # Streamlit / HTMX ダッシュボード
│       └── godot_bridge.py     # Godot 連携
├── godot_project/              # MIT ライセンスの Godot 4.4 シーン
│   ├── project.godot
│   ├── scenes/                 # 3D シーン (.tscn)
│   ├── scripts/                # GDScript (.gd)
│   └── assets/                 # モデル・テクスチャ
├── personas/                   # 偉人ペルソナ定義 (現行 3 体、M4 で実装済)
│   ├── kant.yaml               # カント
│   ├── nietzsche.yaml          # ニーチェ
│   └── rikyu.yaml              # 利休
│                               # 将来追加予定 (M6 以降):
│                               # dogen / aristotle / thoreau /
│                               # kierkegaard / rousseau 等
├── fixtures/                   # Wire contract specimens (言語中立)
│   └── control_envelope/       # ControlEnvelope 各 kind の JSON + README
├── corpora/                    # PD ソース (青空文庫/Gutenberg/archive.org)
├── tests/                      # pytest-asyncio テスト
│   ├── conftest.py
│   ├── test_schemas.py
│   ├── test_memory/
│   ├── test_cognition/
│   ├── test_inference/
│   └── test_world/
├── examples/
│   └── walking_thinkers_12h/   # 12時間シミュレーション設定
├── docs/                       # 永続ドキュメント (本ファイル群)
│   ├── functional-design.md
│   ├── architecture.md
│   ├── repository-structure.md
│   ├── development-guidelines.md
│   └── glossary.md
├── .claude/                    # Claude Code 設定
│   ├── agents/                 # サブエージェント定義
│   ├── commands/               # スラッシュコマンド
│   ├── skills/                 # スキル定義
│   └── hooks/                  # フック
├── .steering/                  # タスク単位の作業記録
│   ├── _setup-progress.md      # 構築進捗
│   └── _template/              # タスク用テンプレート
├── .github/
│   └── workflows/ci.yml        # uv sync --frozen → ruff → pytest
├── pyproject.toml              # uv + ruff + pytest + mypy 設定
├── uv.lock                     # 依存ロックファイル
├── .python-version             # 3.11 pin
├── LICENSE                     # Apache-2.0
├── LICENSE-MIT                 # MIT
├── NOTICE                      # 帰属表示
├── CITATION.cff                # Zenodo DOI 連携
├── CODE_OF_CONDUCT.md          # Contributor Covenant 2.1
├── CLAUDE.md                   # Claude Code への指示
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
- **目的**: Godot 4.4 の 3D シーン・スクリプト・アセット
- **置くべきもの**: `.tscn` シーン、`.gd` スクリプト、3D モデル、テクスチャ
- **置くべきでないもの**: Python コード (Python 側は `src/erre_sandbox/ui/godot_bridge.py` で WebSocket 接続)

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
| Python モジュール | snake_case | `ollama_adapter.py`, `ws_client.py` |
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
- **レイヤー間の依存方向**:
  - `cognition/` → `memory/`, `inference/` (認知が記憶と推論を呼ぶ)
  - `world/` → `cognition/` (ワールドが認知サイクルを駆動)
  - `integration/` → `world/`, `schemas.py` (プロセス境界: gateway, dialog scheduler)
  - `bootstrap.py` → 全サブパッケージ (Composition Root のみ横断可)
  - `ui/` → `schemas.py` のみ (UI はスキーマだけに依存、WebSocket 経由で疎結合)
  - `schemas.py` → 他モジュールへの依存なし (最下層)
  - `inference/` → `schemas.py` のみ
  - `memory/` → `schemas.py` のみ

```
bootstrap.py ──┐  (Composition Root)
               ▼
   integration/ → world/ → cognition/ → inference/
                                      → memory/
                                           ↓
ui/ ─────────────────────→ schemas.py ← (全モジュールが参照)
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

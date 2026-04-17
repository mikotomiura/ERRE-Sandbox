# 開発ガイドライン

## 1. コーディング規約

### 命名規則
- **変数・関数**: snake_case (`agent_state`, `dump_for_prompt()`)
- **クラス**: PascalCase (`AgentState`, `MemoryStream`)
- **定数**: UPPER_SNAKE_CASE (`DEFAULT_TEMPERATURE`, `MAX_AGENTS`)
- **ファイル・モジュール**: snake_case (`ollama_adapter.py`)
- **GDScript**: PascalCase (Godot 標準に従う)

### 型ヒント
- すべての関数に型ヒントを付与する
- Pydantic v2 の `BaseModel` を積極的に活用
- `from __future__ import annotations` を使用し、遅延評価を有効にする

### コメント
- **いつ書くか**: ロジックが自明でない場合、認知科学・論文への参照がある場合、ERRE 独自の設計判断の理由
- **いつ書かないか**: 型ヒントやメソッド名で意図が明確な場合
- **言語**: docstring は英語 (LLM ツール親和性優先)、インラインコメントは日英いずれも可

### Lint / Format
- ruff で lint + format を一元化
- `pyproject.toml` の `[tool.ruff]` セクションで設定
- pre-commit hook で commit 時に自動検証

### Python 固有
- Python 3.11 を使用 (``.python-version`` で pin)
- asyncio を基本とし、同期的な I/O ブロッキングは避ける
- f-string を文字列フォーマットの既定とする

## 2. Git ワークフロー

### ブランチ戦略
- **メインブランチ**: `main` (常にデプロイ可能な状態)
- **作業ブランチ**: `[type]/[task-name]` 形式
  - `feature/agent-cognition-cycle`
  - `fix/memory-retrieval-ranking`
  - `refactor/inference-adapter`
  - `docs/architecture-update`
  - `chore/ci-setup`

### コミットメッセージ
Conventional Commits 形式を採用:

```
[type]([scope]): [短い説明]

- 変更内容 1
- 変更内容 2

Refs: .steering/[YYYYMMDD]-[task-name]/
```

**type**: feat, fix, refactor, docs, test, chore, ci
**scope**: schemas, memory, cognition, inference, world, ui, godot, personas

例:
```
feat(cognition): add DMN-inspired idle reflection window

- peripatos/chashitsu 入室時に温度を上げた自由連想型内省を発火
- importance 閾値未満でもトリガーされる ERRE 独自拡張

Refs: .steering/20260420-reflection-window/
```

### PR
- タイトル: Conventional Commits と同じ形式
- 説明: 変更の背景・目的・テスト方法を記載
- 個人プロジェクトのためレビュアー不要だが、Claude Code の `/review` を活用

### タグ・リリース
- Semantic Versioning: `v0.1.0` (スケルトン) → `v0.5.0` (3体MVP) → `v0.9.0` (RC) → `v1.0.0` (論文併発)
- 各リリースで Zenodo DOI を自動発行
- CITATION.cff で BibTeX を配信

## 3. テスト方針

### テストの種類

| 種類 | 範囲 | フレームワーク | 実行頻度 |
|---|---|---|---|
| 単体テスト | 個々の関数・クラス | pytest | 毎コミット (pre-commit) |
| 統合テスト | モジュール間連携 (memory + cognition 等) | pytest-asyncio | CI (push/PR) |
| E2E テスト | 1体エージェントの認知サイクル完走 | pytest-asyncio | 手動 / CI |
| 埋め込みプレフィックステスト | 検索/文書プレフィックスの正確性 | pytest | CI |

### テストの書き方
- テストファイルは `tests/` 配下に `src/` のミラー構造で配置
- `conftest.py` に共通フィクスチャ (AgentState のファクトリ、sqlite-vec の一時 DB 等)
- 非同期テストは `@pytest.mark.asyncio` を使用
- LLM 推論を伴うテストは mock で分離 (ただし統合テストでは実際の Ollama を使用可)

### TDD の適用
- **適用すべきケース**: schemas.py のバリデーション、memory/ の検索ロジック、ERRE モードの状態遷移
- **適用しないケース**: LLM の出力に依存するテスト (非決定論的)、Godot シーンの描画、探索的プロトタイピング段階

## 4. レビュー基準

### 必須チェック (CI で自動化)
- [ ] `ruff check` が通る
- [ ] `ruff format --check` が通る
- [ ] `pytest` が通る
- [ ] 型ヒントが付与されている

### 手動チェック (セルフレビュー / Claude Code `/review`)
- [ ] テストが追加されている (新機能・バグ修正時)
- [ ] 既存のテストを壊していない
- [ ] 命名規則に従っている
- [ ] 依存方向が正しい (`repository-structure.md` のレイヤー図参照)
- [ ] GPL 依存を持ち込んでいない

### 推奨チェック
- [ ] エッジケースを考慮している
- [ ] asyncio のデッドロック・リソースリークがない
- [ ] VRAM 使用量への影響を考慮している (推論関連の変更時)

## 5. パッケージ管理

### uv の使用
- `uv` を単一のパッケージ・環境・Python 管理ツールとして使用
- `pyproject.toml` に依存を記述、`uv.lock` でロック
- CI では `uv sync --frozen` で再現可能なインストール

### 依存ライブラリの追加基準
新しいライブラリを追加する前に確認:

- [ ] 既存の依存で代替できないか?
- [ ] ライセンスは Apache-2.0 / MIT / BSD と互換か? (GPL は本体に入れない)
- [ ] メンテナンスが活発か? (直近 6 ヶ月以内にリリースがあるか)
- [ ] セキュリティ脆弱性はないか?
- [ ] 予算ゼロに抵触しないか? (有料ライブラリ・有料 API 依存は不可)

## 6. リファクタリング指針

- **いつリファクタリングすべきか**: 同じパターンが 3 箇所以上に現れたとき、モジュールの責務が曖昧になったとき
- **どこまで踏み込むべきか**: 現在のタスクの範囲内。「ついでに直す」は 1 ファイル以内に留める
- **リファクタリング前にやること**: テストの実行、変更前のスナップショット
- **破壊と構築**: 必要なら大胆に壊して再構築する。ただしテストが通る状態を維持

## 7. ドキュメンテーション

### コード内ドキュメント
- docstring は英語、Google スタイル
- 公開 API (関数・クラス) には必ず docstring を付ける
- 内部実装の詳細は docstring に書かず、必要ならインラインコメントで

### プロジェクトドキュメント
- `docs/` の永続ドキュメント: 日本語メイン
- `README.md`: 英語主体、冒頭に「日本語」ジャンプリンク
- MkDocs Material + mkdocstrings で API ドキュメント自動生成
- mkdocs-static-i18n で JA/EN 言語スイッチャ

### 作業記録
- タスク単位の記録は `.steering/[YYYYMMDD]-[task-name]/` に配置
- コミットメッセージで `.steering/` を `Refs:` として参照

## 8. 禁止事項

- GPL 依存ライブラリを `src/erre_sandbox/` に import する
- クラウド LLM API を必須依存にする (予算ゼロ制約)
- 著作権保護下のテキストをリポジトリに含める
- `main` ブランチに直接 push する (作業ブランチ経由のみ)
- テストを書かずに記憶検索ロジック・状態遷移ロジックを変更する
- 埋め込みモデルのプレフィックス (検索クエリ: / 検索文書:) を検証テストなしに変更する

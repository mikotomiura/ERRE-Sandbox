# 設計 (v2 — 再生成案)

## 実装アプローチ

**Single Source of Truth (SSoT) としての uv.lock + 並列ジョブで partial signal**
を最優先する。pre-commit hook は外部 mirror repo を使わず、`uv run` 経由で
プロジェクトの uv.lock 固定 ruff を直接呼ぶ「local hook」のみで構成し、
CI とローカルで「同じバイナリ・同じバージョン」が動くことを保証する。

GitHub Actions は lint / typecheck / test を**並列 3 ジョブ**に分割し、
3 つすべての結果が PR に表示されるようにする (partial signal: mypy が落ちても
pytest 通過は別途見える)。3 ジョブとも `astral-sh/setup-uv@v5` の組み込み
キャッシュ + `uv sync --frozen --all-groups` で同一 .venv を再現。

Godot テストは pytest 標準の **marker による explicit deselection** に切替え、
`pyproject.toml` に `markers = ["godot: ..."]` を登録、対象 2 ファイル
(test_godot_project.py / test_godot_ws_client.py) の関数に
`@pytest.mark.godot` を付与、CI は `pytest -m "not godot"` で実行する。
これにより `--strict-markers` 下でも明示的な除外契約となり、CI 上の skip
理由が「環境依存の偶発的 skip」から「policy 上の意図的 deselection」に格上げされる。

mypy は requirement.md 通り pre-commit には載せず CI 専用ジョブで実行する
(slow という根拠は維持) が、**並列ジョブ**にすることで実時間ボトルネックは
発生しない。

## 採用根拠 (v1 / 慣習との差別化)

- **local hook**: `uv.lock` に固定された ruff だけが正しい ruff。mirror repo の
  rev タグはタイムラグがあり、uv.lock との乖離は将来 codex review で再指摘
  される潜在リスク (PR #112 の D7 が示すように、docs と実態の乖離は本プロジェクト
  の頻発リスク)。SSoT 化でリスクを構造的に閉じる
  - **scope の差**: pre-commit はステージされたファイルのみ (`files:
    ^(src|tests)/.*\.py$`)、CI は `src tests` ディレクトリ全体をチェック。
    ruff バイナリ (= ruff version) は同一だが対象ファイル集合は異なる
- **並列 3 ジョブ**: 直列だと「mypy で詰まったら pytest 結果が見えない」という
  PR レビュー時の盲点が生じる。本プロジェクトは個人開発で `/review` が主レビュー手段
  のため、partial signal が UX に直接効く
- **godot marker**: 現状の `pytest.skip()` は「Godot binary が無い環境」という
  暗黙の契約に依存している。CI が将来 Godot をインストールするように変わった瞬間
  Godot テストが意図せず CI で実行されるリスクがある。marker は CI policy を
  pyproject に明文化する形で、この曖昧さを構造的に排除する

## 変更対象

### 新規作成するファイル

- `.pre-commit-config.yaml`
  ```yaml
  repos:
    - repo: local
      hooks:
        - id: ruff-check
          name: ruff check
          entry: uv run ruff check
          language: system
          types: [python]
          require_serial: true
        - id: ruff-format
          name: ruff format --check
          entry: uv run ruff format --check
          language: system
          types: [python]
          require_serial: true
  ```
- `.github/workflows/ci.yml`
  - 3 並列 jobs: `lint` / `typecheck` / `test`
  - 全 jobs 共通の setup ステップ: checkout → setup-uv@v5 (cache=true) →
    `uv sync --frozen --all-groups`
  - `lint` job: `uv run ruff check src tests` && `uv run ruff format --check src tests`
  - `typecheck` job: `uv run mypy src`
  - `test` job: `uv run pytest -m "not godot"` (godot marker 排除)
  - permissions: `contents: read`
  - concurrency: `group: ci-${{ github.ref }}`, `cancel-in-progress: true`
  - timeout-minutes: 各 job 10 分上限 (受け入れ条件「全体 < 5 分」のために
    各 job が並列で 5 分以内に収まる前提、上限はバッファ)

### 修正するファイル

- `pyproject.toml` `[tool.pytest.ini_options]` (L159-174 範囲) — `markers` キーを
  追加し `godot: requires Godot binary; deselect on CI via -m "not godot"` を登録。
  既存の `--strict-markers` と整合
- `tests/test_godot_project.py` — Godot binary 必須の関数に `@pytest.mark.godot` を付与
  - `test_godot_project_boots_headless` (L53-) のみ対象。
    `test_required_project_files_exist` / `test_godot_project_contains_no_python` は
    binary 不要なので marker なしのまま CI で実行
- `tests/test_godot_ws_client.py` — `resolve_godot()` を呼ぶ全関数に marker
- `README.md` L56-62 (English) + L124-130 (日本語) — 5 コマンド表示の直後に
  注記: "These run automatically via pre-commit hook (commit time) and GitHub
  Actions CI (push/PR). They can also be invoked manually with the commands shown."
- `README.md` (Getting Started 末尾) — `uv tool install pre-commit && pre-commit install`
  を 1 行追記
- `docs/development-guidelines.md` L25-26 — "現状 manual" を「pre-commit hook
  (commit 時) / GitHub Actions CI (push/PR 時) で自動実行」に書換え
- `docs/development-guidelines.md` L90-93 — テスト表「現状実装スナップショット」
  ブロックを CI 化後の表記に書換え (実行頻度を "pre-commit" / "CI (push/PR)" に
  戻す)
- `docs/development-guidelines.md` L107 — 「現状 manual、`.steering/20260428-ci-pipeline-setup/`
  で CI 化予定」を「pre-commit / CI で自動実行」に
- `docs/architecture.md` L86 — `(現状なし) [planned]` を実装済 entry に書換え

### 削除するファイル

- なし

## 影響範囲

- 全コミットで pre-commit hook が走る。初回の `pre-commit install` が必要
- 全 push / PR で 3 並列 jobs が起動。GitHub free tier は十分カバー
- godot marker 導入で CI 上の skip ノイズが消え、`pytest -m "not godot"` で
  collect 段階から対象外化されるため CI ログが clean に
- ローカル `uv run pytest` (marker 指定なし) では従来通り Godot binary が
  あれば実行、無ければ `pytest.skip()` 経路で skip という挙動が維持される

## 既存パターンとの整合性

- `[dependency-groups]` 構成 (lint / typecheck / test / dev) は変更しない。
  CI は `--all-groups` で全 dev 依存を入れる (mypy 単独 job も pytest 単独 job も
  この lock を共有することで再現性確保)
- `--strict-markers` 設定は維持。markers セクション追加で「godot」が strict 下でも
  通る
- README の 5 コマンド (uv run ruff check / ruff format --check / mypy / pytest) は
  そのまま CI step に写し、verbal 注記で自動化を案内 (要件 L53-54)
- L25-26 / L86 / L107 の docs 注記は codex addendum D5 + D6 の "現状 snapshot"
  運用と整合する形で更新 (snapshot date を 2026-04-28 に更新)

## テスト戦略

- **単体テスト追加なし**: CI ファイル自体は YAML 構文 + GitHub Actions runner で
  検証される
- **回帰テスト**: 新設の `markers` を `--strict-markers` 下で書き換えるため、
  ローカルで `uv run pytest tests/test_godot_project.py` が pass することを
  事前検証 (godot binary 在不在の両条件で)
- **CI dry-run**: 可能なら `act` (nektos/act) でローカル GitHub Actions
  シミュレーションを試みる。act が失敗する場合は受け入れを「PR 開いて緑」に
  落とす
- **受け入れ条件 (requirement.md L48-54) の機械検証**: PR で実際に CI を
  走らせ、6 項目すべてを `decisions.md` に時刻付きで記録

## ロールバック計画

- 単一コミットで全部追加するため、`git revert <ci-pipeline-setup commit>` で
  全変更を一括撤回できる構造を維持する (.pre-commit-config.yaml + .github/ +
  pyproject.toml markers + 2 テストファイルへの marker + docs 4 ファイルを
  すべて 1 PR にまとめる)
- 部分破綻時 (例: mypy job だけ落ちる、CI free tier 制限超え) は該当 job だけ
  `if: false` で短時間止め、原因解明後に再有効化。並列 job 構造のため他に
  波及しない

## CI 実時間試算

| Job | 想定時間 |
|---|---|
| lint (ruff check + format) | < 30s |
| typecheck (mypy src) | 1-2 min |
| test (pytest -m "not godot") | 1-2 min |
| **並列実行 wall-clock** | **2-3 min** (uv sync 含め) |

受け入れ条件「< 5 分」を 50% 以上のマージンで満たす。

## 設計判断の履歴

- 初回案 (design-v1.md) と再生成案 (design.md = v2) を比較
  (`design-comparison.md` 参照)
- 採用: **v2**
- 根拠: 本プロジェクトの最大リスク「docs/実装の乖離が codex review で再指摘される」
  (PR #111 F1-F6 + PR #112 D1-D10) を構造的に閉じるため、v2 の SSoT (uv.lock 単独固定)
  + marker policy 明示 + 並列ジョブによる partial signal を採用。v1 は同種の負債
  (ruff version 2 箇所固定、Godot skip 暗黙契約) を新たに生む構造のため不採用。
- 確定日: 2026-04-28

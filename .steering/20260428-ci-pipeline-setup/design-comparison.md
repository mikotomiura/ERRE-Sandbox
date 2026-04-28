# 設計案比較 — ci-pipeline-setup

## v1 (初回案) の要旨

「標準的なパターンに乗る」方針。pre-commit hook は `astral-sh/ruff-pre-commit`
を hosted で使い、GitHub Actions は単一 job で `uv sync --frozen` →
ruff check → ruff format --check → mypy → pytest を**直列実行**する。
Godot テストは既存の `pytest.skip()` 経路に任せ、新規仕組みは追加しない。
最低限の YAML 行数で動く慣習どおりの構成。

## v2 (再生成案) の要旨

**SSoT (uv.lock) + 並列ジョブ + explicit godot marker** の 3 軸で v1 を
構造的にリスク低減した案。

- pre-commit は外部 mirror を排し、`uv run ruff` の **local hook** に統一
  → CI とローカルで同一 ruff バイナリ (uv.lock 固定) が動く
- GitHub Actions を **lint / typecheck / test の並列 3 ジョブ**に分割
  → partial signal: mypy が落ちても pytest 結果が PR に並列で見える
- Godot テストは `markers = ["godot: ..."]` を `pyproject.toml` に登録、対象関数に
  `@pytest.mark.godot` 付与、CI は `pytest -m "not godot"` で意図的 deselection
  → 「環境依存の偶発 skip」を「policy 明示」に格上げ

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| pre-commit hook source | astral-sh/ruff-pre-commit (mirror, `rev:` で固定) | uv run ruff (local hook, uv.lock 固定) |
| ruff バージョン管理 | mirror rev と uv.lock で 2 箇所、乖離リスクあり | uv.lock 単独 (SSoT) |
| GitHub Actions job 構成 | single job, sequential 5 ステップ | 3 並列 jobs (lint / typecheck / test) |
| Failure 時の signal | 直列なので最初の失敗で打ち切り、後続は不明 | 並列 3 jobs それぞれ独立で結果が見える |
| Godot テスト除外 | 既存 `pytest.skip()` 任せ (CI に Godot 入った瞬間意図せず実行されるリスク) | `@pytest.mark.godot` + `pytest -m "not godot"` で policy 明示 |
| pyproject.toml markers | 変更なし | `[tool.pytest.ini_options].markers` に godot 登録 |
| 修正テストファイル | 0 | 2 (test_godot_project.py / test_godot_ws_client.py) |
| README/docs 更新 | 注記追記程度 | 同等 + getting-started に `pre-commit install` 1 行追記 |
| CI 実時間 (受け入れ < 5 分) | 直列で 3-4 分予想 | 並列で 2-3 分予想 (50%+ マージン) |
| 変更行数 (概算) | ~80 行 (YAML 中心) | ~120 行 (YAML + pyproject 1 節 + テスト 2 ファイルに decorator + docs) |
| ロールバック容易性 | revert 1 コマンド | revert 1 コマンド (PR 単一にまとめれば等価) |

## 評価

### v1 の長所

1. 行数最小、レビュー容易
2. mirror repo は GitHub 上で多数事例があり、外部レビュアー (codex 等) の認知コスト低
3. テストファイルへの侵襲なし

### v1 の短所

1. **ruff バージョンが 2 箇所固定**: `.pre-commit-config.yaml` の `rev:` と
   `uv.lock` の ruff version。Renovate/Dependabot 等で片方だけ更新されると
   静かに乖離。本プロジェクトは codex review で「docs/実装の乖離」が頻発
   リスクとして記録されており (PR #112 D5/D6/D7)、構造的に同じ問題を
   再生産する
2. 直列 5 ステップで最初の失敗で打ち切り。「ruff format で 1 文字落ちて
   pytest が走らない」という典型 PR ストレス
3. Godot テストの skip 契約が暗黙 (binary 不在 → skip)。CI policy が
   コードに表現されていない

### v2 の長所

1. **uv.lock SSoT**: ruff のバージョン固定箇所が 1 つになり、`uv sync --frozen`
   の再現性保証範囲に CI と pre-commit の両方が入る
2. **partial signal**: 3 ジョブ並列で PR レビュー時に「どの軸が緑/赤か」が
   一目で見える。個人開発で `/review` が主レビュー手段の本プロジェクトと
   特に相性が良い
3. **godot marker 明示**: CI policy が `pyproject.toml` に文字として表れ、
   将来 CI runner 環境変更 (例: Godot プリインストール) でも意図せぬ実行を
   構造的に防ぐ
4. CI 実時間 2-3 分で受け入れ < 5 分を余裕でクリア

### v2 の短所

1. テストファイル 2 件への侵襲 (`@pytest.mark.godot` 追加)
2. local hook は外部レビュアーには「珍しい構成」に映る可能性。ただし
   `entry: uv run ruff check` は読み下し容易で説明コストは低い
3. 並列 3 ジョブで `uv sync` が 3 回走る。CI minutes 消費は約 3 倍だが
   GitHub free tier (個人 public repo: 無制限) では問題なし
4. YAML 行数が v1 より 30-40 行多い

## リスク評価

| リスク | v1 影響 | v2 影響 |
|---|---|---|
| ruff version drift (mirror vs uv.lock) | **高**: 静かに乖離、codex 再指摘 | 低: SSoT 化で構造的に閉じる |
| CI 実時間が < 5 分超過 | 中: 直列で margin 少 | 低: 並列で 50%+ margin |
| Godot 環境変化で意図せぬ実行 | 中: skip 契約は暗黙 | 低: marker で明示 |
| YAML 構成の複雑さ | 低 | 中: 並列 jobs で要素数増 |
| ローカルで `pre-commit install` 後に uv 不在で hook 失敗 | 低 (mirror が rust binary 自前 download) | 中: uv 必須、ただし本プロジェクトは元々 uv 必須 |

## 推奨案

**v2 採用**を強く推奨する。

### 推奨根拠

本プロジェクトの最大リスクは **「docs / 実装の乖離が時間経過で蓄積し codex review で
再指摘される」** パターンであることが、PR #111 (F1-F6) と PR #112 (D1-D10) の
2 連続レビューで明らかになっている (memory: project_codex_review_cycle 参照)。

v1 の「ruff version が 2 箇所」「Godot skip が暗黙契約」は同じ構造の負債を
新たに生む。一方 v2 は SSoT と marker policy で**構造的に閉じる**設計のため、
今後の codex review で「pre-commit と CI で動く ruff が違う」「CI 上で
Godot テストが意図せず実行されている」という再指摘を未然に防げる。

並列 3 ジョブも個人開発の `/review` ワークフローと相性が良い。

### ハイブリッド余地 (任意)

v2 を基本とし、以下は v1 寄りで簡略化してもよい:

- (A) 並列 3 ジョブを「lint+typecheck の 2 ジョブと test の 1 ジョブ」の
  2 並列に簡略化 (uv sync 回数を 2 回に削減、CI minutes 節約)
- (B) godot marker を導入するが、`pyproject.toml` への登録のみで test 関数への
  `@pytest.mark.godot` は次回 task に分離 (本 task は CI 配線優先、test 改修は別)

(A) は CI minutes が無料で問題ない以上不採用推奨。
(B) は v2 の主旨 (policy 明示) を半減させるため不採用推奨。

両方とも v2 のままで進めるのが筋が良い。

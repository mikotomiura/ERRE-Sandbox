# Blockers / Future Work

本 task で対処せず、将来 task として持ち越す項目。code-reviewer レビュー
(2026-04-28) で MEDIUM/LOW として挙がったもののうち、本 task のスコープを
拡大しない判断をしたもの。

## MEDIUM-5: `pytest-asyncio >= 0.27` リリース時の workaround 撤去

- 場所: `pyproject.toml` `[tool.pytest.ini_options].filterwarnings` 末尾の
  `"default::pytest.PytestUnraisableExceptionWarning"` (および直前のコメントブロック)
- 原因: pytest-asyncio 0.26.x の `_provide_clean_event_loop` が function-scope
  の event loop を close せず、GC タイミング次第で次の test の setup で
  `ResourceWarning` を発火させる (上流既知 issue)。`filterwarnings = ["error"]`
  で hard fail になっていたため `default` 扱いに緩和した
- トリガー: `pyproject.toml` の `pytest-asyncio>=0.24,<1` の lock が 0.27+
  に上がった瞬間
- 撤去手順:
  1. `uv sync` で pytest-asyncio を更新
  2. 上記 1 行とコメントブロックを削除
  3. `uv run pytest -m "not godot"` を 3 回連続で exit=0 確認
  4. PR の commit メッセージで「pytest-asyncio 0.27 アップグレードに伴う
     PytestUnraisableExceptionWarning workaround の撤去」と明記

## MEDIUM-6: GitHub Actions の SHA pinning 移行

- 場所: `.github/workflows/ci.yml` の `actions/checkout@v4` /
  `astral-sh/setup-uv@v5`
- 現状: tag pinning。個人プロジェクトで実用上は十分
- 将来: OSS 化 / 共同開発 / sensitive credentials を扱う段階で SHA pinning へ
  (例: `actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1`)
- ツール: `pinact` / `dependabot` で半自動化可能

## LOW-9: `pytestmark` vs `@pytest.mark.godot` 使い分けの docs 注記

- 現状: `tests/test_godot_peripatos.py` / `test_godot_dialog_bubble.py` /
  `test_godot_mode_tint.py` は module-level `pytestmark = pytest.mark.godot`、
  `test_godot_project.py` / `test_godot_ws_client.py` は関数 decorator
- 使い分けの基準は技術的に正しい (全関数 Godot 必須なら module-level、一部の
  みなら関数単位) が、`docs/development-guidelines.md` のテスト方針に明文化
  されていない
- 対応: 次の docs 整備 task で 1 行追記

## LOW-11: CI 詳細記述の集約

- 現状: `docs/architecture.md:86` と `docs/repository-structure.md:108-110`
  の両方に CI の `--all-groups` / 並列 3 jobs などの詳細が記述されている
- 将来 CI 構成変更時に 2 箇所の同期が必要
- 対応: `repository-structure.md` を「CI 設定の単純な存在」のみに留め、詳細は
  `architecture.md` へクロスリファレンスする整理を次回 docs 整備で実施

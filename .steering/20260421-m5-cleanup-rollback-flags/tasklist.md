# タスクリスト — m5-cleanup-rollback-flags

## 準備

- [x] branch 作成 (`refactor/m5-cleanup-rollback-flags`)
- [x] `v0.3.0-m5` タグが付与済 (commit `691e507`) を確認
- [x] requirement.md + design.md 記入
- [x] baseline pytest 658 passed 確認
- [x] `grep -rnE "enable_*|disable-*|_ZERO_MODE_DELTAS"` で除去箇所 enumerate

## 実装

- [x] `bootstrap.py`: `_ZERO_MODE_DELTAS` 定数除去
- [x] `bootstrap.py`: `bootstrap()` 3 kwargs 除去 + 分岐除去 + docstring 整理
- [x] `bootstrap.py`: `SamplingDelta` + `Mapping` 未使用 import 除去
- [x] `__main__.py`: argparse 3 options 除去
- [x] `__main__.py`: `cli()` → `bootstrap()` kwargs 受け渡し除去
- [x] `cognition/cycle.py`: `erre_sampling_deltas` docstring を testing-only に
- [x] `world/tick.py`: `_dialog_generator` docstring を testing 文脈に
- [x] `integration/dialog_turn.py`: PR #68 E501 2 件 drive-by fix (string-concat)
- [x] `tests/test_main.py`: rollback flag tests 7 件除去、cli smoke 1 件追加
- [x] `tests/test_bootstrap.py`: `_ZERO_MODE_DELTAS` drift 2 件除去
- [x] `tests/test_cognition/test_cycle_erre_fsm.py`: DI test docstring 更新
- [x] `docs/architecture.md`: Composition Root §M5 段落更新

## 検証

- [x] `grep -rnE "enable_*|disable-*|_ZERO_MODE_DELTAS" src/ tests/` → 0 件
- [x] `uv run erre-sandbox --help` に `--disable-*` なし
- [x] `uv run ruff check src tests` → All checks passed
- [x] `uv run ruff format --check src tests` → 全 formatted
- [x] `uv run mypy src/erre_sandbox` → 0 errors
- [x] `uv run pytest -q` → 650 passed, 31 skipped, 0 failed

## レビュー

- [ ] code-reviewer 任意 (本 cleanup は scope 限定、除去のみなので軽量で可)
- [ ] HIGH 指摘あれば対応

## ドキュメント

- [x] `docs/architecture.md` §Composition Root 更新

## 完了処理

- [ ] `git add` 対象ファイル stage
- [ ] `git commit` (Conventional Commits:
      `refactor(bootstrap): remove M5 rollback flags and _ZERO_MODE_DELTAS`)
- [ ] `git push -u origin refactor/m5-cleanup-rollback-flags`
- [ ] `gh pr create` → user review → merge

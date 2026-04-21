# 設計 — m5-cleanup-rollback-flags

## 実装アプローチ

`v0.3.0-m5` タグ付与後の cleanup。`m5-orchestrator-integration` decisions.md
§判断 3 で事前に「acceptance PASS 後に除去」と明示していたので代替案なし、
除去対象を機械的に除去するだけ。

## 変更対象

### 修正するファイル

- `src/erre_sandbox/bootstrap.py` — `_ZERO_MODE_DELTAS` 定数除去 /
  `bootstrap()` の 3 kwargs 除去 / 分岐コード除去 / docstring 整理 /
  `SamplingDelta` + `Mapping` の未使用 import 除去
- `src/erre_sandbox/__main__.py` — `--disable-*` argparse 3 件除去 /
  `cli()` の kwargs 受け渡し除去
- `src/erre_sandbox/cognition/cycle.py` — docstring を "rollback" から
  "testing-only DI slot" に書き換え (`erre_sampling_deltas` DI スロット自体は維持)
- `src/erre_sandbox/world/tick.py` — docstring の `--disable-dialog-turn`
  言及をテスト文脈に書き換え
- `src/erre_sandbox/integration/dialog_turn.py` — PR #68 で merge 後
  ruff E501 violation が残っていた 2 行を string-concat で分割 (drive-by fix)
- `tests/test_main.py` — rollback flag 関連 7 件除去、cli smoke 1 件に集約
- `tests/test_bootstrap.py` — `_ZERO_MODE_DELTAS` drift 2 件除去
  (`_load_persona_registry` の 2 件は維持)
- `tests/test_cognition/test_cycle_erre_fsm.py` — `erre_sampling_deltas` DI
  test 群の docstring を testing-only に書き換え
- `docs/architecture.md` — Composition Root §M5 orchestrator-integration から
  rollback flag 段落を除去し、cleanup 済の旨を追記

### 新規作成するファイル

なし

### 削除するファイル

なし (定数 / kwarg 除去のみ、ファイル単位の削除はなし)

## 影響範囲

- public API 縮小: `bootstrap()` kwargs 3 つ除去、`erre-sandbox --help`
  から 3 flag 消失
- schema 変更なし / Godot 側変更なし / fixtures 変更なし
- tests: 658 passed → 650 passed (net -8: 9 件除去 + 1 件追加)
- lint: PR #68 由来の E501 2 件を drive-by fix してリリース clean に

## 既存パターンとの整合性

- `m5-orchestrator-integration/decisions.md` §判断 3 が予告した
  `m5-cleanup-rollback-flags` そのもの
- 残置した `CognitionCycle.erre_sampling_deltas` DI スロットは
  Reflector の optional collaborator パターンと対称 (本番 default /
  test 注入可)

## テスト戦略

- 単体: 既存 `test_cycle_erre_sampling_deltas_*` 2 件は DI 動作保証として維持
- 統合: `test_cli_invokes_bootstrap_with_parsed_cfg` に集約 (rollback
  propagation の 2 件 smoke は役割終了)
- 回帰: 650 passed + 31 skipped、0 failure 維持
- lint / mypy: 全 clean

## ロールバック計画

- 本 PR が問題を起こした場合、`git revert` で戻せる
- revert で `--disable-*` 機能は復活するが M5 spec 的には不要機能
- 直近 24h 以内に live で問題が出れば revert / そうでなければ
  M6 以降へ進む

## 関連する Skill

- `implementation-workflow` — 共通骨格 (軽量運用)
- `python-standards` — lint / import 整理
- `test-standards` — test 除去時の振る舞い維持

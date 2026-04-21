# m5-cleanup-rollback-flags — M5 過渡期 rollback flag 除去

## 背景

M5 Phase 2 acceptance は **7/7 PASS** で完了、`v0.3.0-m5` タグ付与済
(commit `691e507`)。`m5-orchestrator-integration`
(`.steering/20260421-m5-orchestrator-integration/decisions.md` §判断 3) で
「acceptance PASS 後に削除する transient rollback knob」として明示的に残していた
3 つの feature flag が不要になった:

- `--disable-erre-fsm` (CLI) / `enable_erre_fsm=True` (bootstrap kwarg)
- `--disable-dialog-turn` / `enable_dialog_turn=True`
- `--disable-mode-sampling` / `enable_mode_sampling=True`

これらは M4 挙動への緊急 rollback 経路として用意したが、live で 7/7 PASS 済
のため役割終了。API 表面積を縮小して M6 以降の保守を軽くする。

## ゴール

1. `bootstrap()` から 3 つの `enable_*` kwargs を除去し、常に M5 本番挙動
   (FSM 有効 / 発話生成有効 / sampling override 有効) にする
2. `__main__.py::_build_parser` から 3 つの `--disable-*` argparse option を除去
3. `bootstrap._ZERO_MODE_DELTAS` 定数を除去
4. `CognitionCycle.erre_sampling_deltas` DI スロットは **維持** するが、
   docstring を "testing-only" に変更 (production には不要、但し
   `SAMPLING_DELTA_BY_MODE` 直参照より test 分離性が高いので残す)
5. 関連 test (argparse 5 件 / cli propagation 2 件 / bootstrap drift guard 2 件) を
   削除または "本番は常に DefaultERREModePolicy + OllamaDialogTurnGenerator が
   wire される" の smoke に集約
6. `docs/architecture.md` §Composition Root から transient flag 段落を削除

## スコープ

### 含むもの

- `src/erre_sandbox/bootstrap.py` (kwargs / 定数 / 条件分岐除去)
- `src/erre_sandbox/__main__.py` (argparse + cli)
- `src/erre_sandbox/cognition/cycle.py` (docstring 文言のみ、DI スロット自体は維持)
- `tests/test_main.py` (rollback flag tests 除去)
- `tests/test_bootstrap.py` (ZERO_MODE_DELTAS drift 除去、本番 wire smoke に変更)
- `docs/architecture.md` (transient flag 段落除去)

### 含まないもの

- `CognitionCycle.erre_sampling_deltas` DI スロット自体の除去
  (→ test 分離性のため維持、docstring のみ更新)
- `test_cycle_erre_sampling_deltas_*` tests 2 件
  (→ DI 経路の動作保証は継続、production で使わないだけ)
- Godot / MacBook 側 (そもそも rollback 関係なし)
- 新機能追加 / schema 変更 / reflection / dialog generator 本体の挙動
  (すべて freeze)

## 受け入れ条件

- [ ] `grep -r "enable_erre_fsm\|enable_dialog_turn\|enable_mode_sampling" src/` が 0 件
- [ ] `grep -r "disable-erre-fsm\|disable-dialog-turn\|disable-mode-sampling" src/` が 0 件
- [ ] `grep -r "_ZERO_MODE_DELTAS" src/` が 0 件
- [ ] `uv run erre-sandbox --help` に `--disable-*` が出ない
- [ ] `uv run pytest -q` が全 PASS (rollback flag test を除去した分だけ総数減る)
- [ ] `uv run ruff check src tests` / `ruff format --check` / `mypy src/erre_sandbox` 全 PASS
- [ ] `docs/architecture.md` §Composition Root から 3 flag 段落が消えている

## 関連ドキュメント

- `.steering/20260421-m5-orchestrator-integration/decisions.md` §判断 3
  (「acceptance PASS 後に除去する」明示)
- `.steering/20260421-m5-acceptance-live/acceptance.md` (7/7 PASS 確認)
- `CLAUDE.md` (タスク作業原則)

## 運用メモ

- タスク種別: **リファクタリング**
- 破壊と構築 (`/reimagine`) 適用: **No**
  (除去対象と残置対象が事前確定済、代替案比較の意義なし)
- テスト戦略: 除去 → テスト実行 → 回帰なし確認の逐次方式
  (既存テスト全グリーン状態から始めて振る舞いを維持)

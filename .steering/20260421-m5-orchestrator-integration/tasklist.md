# タスクリスト — m5-orchestrator-integration

## 準備 (完了済)

- [x] `/start-task` で branch 作成 (`feature/m5-orchestrator-integration`)
- [x] requirement.md ドラフト + ユーザー承認
- [x] docs/architecture.md / development-guidelines.md / repository-structure.md 読了
- [x] 既存コード調査 (bootstrap.py / __main__.py / cycle.py / world/tick.py /
      integration/dialog.py / integration/dialog_turn.py / erre/__init__.py)
- [x] impact-analyzer 影響範囲調査
- [x] /reimagine v1 → v2 再生成 → design-comparison.md → **v2 採用確定**

## 0. 先行 chore (m5-world-zone-triggers checkbox 整合)

- [x] `.steering/20260421-m5-world-zone-triggers/tasklist.md` 末尾 3 checkbox
      (commit/push/PR、PR #58 として merge 済) を `[x]` に更新

## 1. TDD (test 先行、赤 → 実装 → 緑)

### Step 1.1: `iter_open_dialogs` テスト先行

- [x] `tests/test_integration/test_dialog.py` に新規 test:
  - `iter_open_dialogs` が open 件数と一致
  - 各 tuple が (dialog_id, initiator, target, zone) であること
  - close 後は列挙されないこと
- [x] `uv run pytest tests/test_integration/test_dialog.py -k iter_open_dialogs`
      で赤確認 (AttributeError)

### Step 1.2: `CognitionCycle.erre_sampling_deltas` テスト先行

- [x] `tests/test_cognition/test_cycle_erre_fsm.py` に新規 test:
  - `erre_sampling_deltas=ZERO_TABLE` 注入時、FSM 遷移 (name 変更) は
    起こるが `agent_state.erre.sampling_overrides` はゼロのまま
  - `erre_sampling_deltas=None` (default) 時は既存挙動 (SAMPLING_DELTA_BY_MODE を参照)
- [x] `uv run pytest tests/test_cognition/test_cycle_erre_fsm.py -k sampling_deltas`
      で赤確認

### Step 1.3: WorldRuntime `_drive_dialog_turns` テスト先行

- [x] `tests/test_integration/test_dialog_orchestration_wiring.py` 新規作成:
  - budget=6、`len(transcript)==5` は turn 生成、`==6` で `reason="exhausted"` close
  - `turn_index % 2 == 0` → initiator speaker、`==1` → target speaker
  - generator が `None` を返す → record も emit も起こらない (timeout 経路に任す)
  - generator が例外を投げても他 dialog の処理を止めない
  - `generator` 未 attach 時は `_drive_dialog_turns` が no-op
- [x] `uv run pytest tests/test_integration/test_dialog_orchestration_wiring.py`
      で赤確認

### Step 1.4: `__main__.py` 3 flag argparse smoke test 先行

- [x] `tests/test_main.py` に新規 test:
  - `parse_args([])` → `enable_erre_fsm=True` / `enable_dialog_turn=True` /
    `enable_mode_sampling=True` (default)
  - `parse_args(["--disable-erre-fsm"])` → `enable_erre_fsm=False` (他 2 つは True)
  - `parse_args(["--disable-dialog-turn"])` → `enable_dialog_turn=False`
  - `parse_args(["--disable-mode-sampling"])` → `enable_mode_sampling=False`
- [x] 赤確認

### Step 1.5: bootstrap smoke test 先行

- [x] `tests/test_bootstrap.py` に 4 smoke case 追加:
  - all ON (baseline M5 wire) — DefaultERREModePolicy が cycle に設定 +
    generator が runtime にアタッチされる
  - `enable_erre_fsm=False` → `cycle._erre_policy is None`
  - `enable_dialog_turn=False` → `runtime._dialog_generator is None`
  - `enable_mode_sampling=False` → `cycle._erre_sampling_deltas == _ZERO_MODE_DELTAS`
- [x] 赤確認

## 2. 実装 (依存順に内側から)

### Step 2.1: `integration/dialog.py` に `iter_open_dialogs` 追加

- [x] `InMemoryDialogScheduler.iter_open_dialogs() -> Iterator[tuple[str, str, str, Zone]]`
      を実装 (docstring 付き)
- [x] `uv run pytest tests/test_integration/test_dialog.py -k iter_open_dialogs` 緑確認

### Step 2.2: `cognition/cycle.py` に `erre_sampling_deltas` DI スロット

- [x] `CognitionCycle.__init__` に
      `erre_sampling_deltas: Mapping[ERREModeName, SamplingDelta] | None = None` kwarg
- [x] `self._erre_sampling_deltas = erre_sampling_deltas or SAMPLING_DELTA_BY_MODE`
- [x] `_maybe_apply_erre_fsm` の `SAMPLING_DELTA_BY_MODE[candidate]` を
      `self._erre_sampling_deltas[candidate]` に置換
- [x] docstring 更新 (理由を簡潔に)
- [x] `uv run pytest tests/test_cognition/test_cycle_erre_fsm.py` 全緑

### Step 2.3: `world/tick.py` に `attach_dialog_generator` + `_drive_dialog_turns`

- [x] `WorldRuntime.__init__` に `self._dialog_generator: DialogTurnGenerator | None = None` 初期化
- [x] `attach_dialog_generator(generator)` method 実装 (`attach_dialog_scheduler` と対称)
- [x] `_on_cognition_tick` 末尾に
      `if self._dialog_generator is not None and self._dialog_scheduler is not None: await self._drive_dialog_turns(current_world_tick)`
- [x] `_drive_dialog_turns(world_tick)` 実装:
  - scheduler.iter_open_dialogs() で列挙
  - speaker 決定 (turn_index % 2)
  - budget 判定で exhausted close
  - `asyncio.gather(*tasks, return_exceptions=True)` で並列生成
  - 結果を record_turn + inject_envelope
  - 例外は個別に log して他を止めない
- [x] `uv run pytest tests/test_integration/test_dialog_orchestration_wiring.py` 全緑
- [x] `tests/test_world/test_tick.py` の `_pump` が動くか確認、flaky なら
      `_pump_until_stable` 方式へ修正

### Step 2.4: `bootstrap.py` に 3 flag kwargs + persona registry + wire

- [x] module top に `_ZERO_MODE_DELTAS: Mapping[ERREModeName, SamplingDelta]` 定数追加
- [x] `_load_persona_registry(cfg) -> dict[str, PersonaSpec]` helper 追加
      (既存の agent 登録ループでの persona load を先取りして dict 構築)
- [x] `bootstrap()` signature に
      `*, enable_erre_fsm: bool = True, enable_dialog_turn: bool = True, enable_mode_sampling: bool = True`
- [x] `CognitionCycle(...)` に `erre_policy=DefaultERREModePolicy() if enable_erre_fsm else None`
      + `erre_sampling_deltas=_ZERO_MODE_DELTAS if not enable_mode_sampling else None` 渡す
- [x] `enable_dialog_turn` True 時に `OllamaDialogTurnGenerator(llm=inference, personas=persona_registry)`
      を instantiate + `runtime.attach_dialog_generator(generator)`
- [x] bootstrap docstring 更新 (3 flag の意図を明示)
- [x] `uv run pytest tests/test_bootstrap.py` 全緑

### Step 2.5: `__main__.py` に argparse 3 flag + cli mapping

- [x] `_build_parser()` に以下 3 つ追加:
  - `--disable-erre-fsm` → `action="store_false"`, `dest="enable_erre_fsm"`, `default=True`
  - `--disable-dialog-turn` → 同様
  - `--disable-mode-sampling` → 同様
- [x] `--help` 文言に "M5 rollback-only flags — leave all ON in production" を明示
- [x] `cli()` の `asyncio.run(bootstrap(cfg))` を
      `asyncio.run(bootstrap(cfg, enable_erre_fsm=args.enable_erre_fsm, ...))` に更新
- [x] `uv run pytest tests/test_main.py` 全緑

## 3. 検証

- [x] `uv run pytest -q` → PR #61 時点 549 passed + 新規テスト分で 0 failures
- [x] `uv run ruff check src tests` PASS
- [x] `uv run ruff format --check src tests` PASS
- [x] `uv run mypy src/erre_sandbox` PASS (0 errors)

## 4. レビュー

- [x] `code-reviewer` サブエージェント起動、差分レビュー
- [x] HIGH 指摘に全対応
- [x] MEDIUM はユーザー判断 (decisions.md に記録)
- [x] LOW は blockers.md or decisions.md で受容

## 5. ドキュメント

- [x] `docs/architecture.md` §フロー 1 / §Composition Root に本 task の wire を反映
      (DefaultERREModePolicy 注入と dialog generator attach の記述を追加)
- [ ] `docs/functional-design.md` への追記: rollback knob は transient なので
      本タスクでは見送り。`m5-acceptance-live` の live 運用ガイドとして合わせて記載
- [x] 新用語がないため `glossary.md` 更新は不要 (既存用語のみ使用)

## 6. 完了処理

- [x] `decisions.md` 作成 (7 判断 + 後続タスク引き継ぎ値)
- [x] 全 steering ファイル最終化 (requirement / design / design-v1 /
      design-comparison / decisions / tasklist)
- [x] `git add` 対象ファイルを個別指定で stage (secret 混入防止)
- [x] `git commit` (Conventional Commits + `Refs:`) — commit 7699a71
- [x] `git push -u origin feature/m5-orchestrator-integration`
- [x] `gh pr create` で PR 作成 → **PR #62**
      (https://github.com/mikotomiura/ERRE-Sandbox/pull/62)
- [ ] PR review → merge (ユーザー判断)

## 制約・リマインダ

- TDD 順序厳守 (赤 → 実装 → 緑)
- `BootConfig` は本 task で一切触らない (v2 判断)
- `InMemoryDialogScheduler` への追加は `iter_open_dialogs` 1 本のみ
- `main` 直 push 禁止、`--no-verify` 禁止
- 549 test に回帰なし
- `_run_dialog_tick` (既存 sync) と `_drive_dialog_turns` (新規 async) を混同しない

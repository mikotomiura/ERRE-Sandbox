# タスクリスト — m5-world-zone-triggers

## 準備

- [x] `.steering/20260420-m5-erre-mode-fsm/decisions.md` §4 を再読 (layer 判断の
      引き継ぎ)
- [x] `src/erre_sandbox/world/tick.py` 読了 (hook 候補を physics / cognition で確認)
- [x] `src/erre_sandbox/erre/` の concrete + Protocol を確認
- [x] `feature/m5-world-zone-triggers` branch を作成

## 設計 (/reimagine)

- [x] `design.md` に v1 初回案を記入 (world hook / `world → erre` allowance)
- [x] `design.md` を `design-v1.md` に退避
- [x] v2 案をゼロから生成 (cognition 層内包 / `cognition → erre` のみ)
- [x] `design-comparison.md` で 2 案を比較
- [x] v2 採用確定 → design.md 最終化 + 採用判断履歴記録

## 実装

### Step A: architecture-rules update

- [x] `.claude/skills/architecture-rules/SKILL.md` の依存テーブル更新:
  - `cognition/` 依存先 += `erre/`
  - `world/` 依存禁止 += `erre/`
  - `erre/` 依存禁止 += `cognition/` (循環防止)

### Step B: TDD (test 先行)

- [x] `tests/test_cognition/test_cycle_erre_fsm.py` 新規 5 test 赤で作成
- [x] `uv run pytest tests/test_cognition/test_cycle_erre_fsm.py` で赤確認
      (TypeError: unexpected kwarg `erre_policy`)

### Step C: CognitionCycle DI 拡張 + Hook 実装

- [x] `cycle.py::CognitionCycle.__init__` に `erre_policy` 引数追加
- [x] `_maybe_apply_erre_fsm` private helper 追加
- [x] `step()` 内の Step 2 と Step 3 の間に hook 挿入
- [x] `cycle.py` docstring 更新 ("ERRE FSM" を Out → In に移動)
- [x] `uv run pytest tests/test_cognition/test_cycle_erre_fsm.py` 全緑

### Step D: defensive guard (code-reviewer MEDIUM 対応)

- [x] `candidate == current` を no-op として扱う guard 追加
- [x] 違反時の regression test 追加

## テスト

- [x] `uv run pytest -q` → 549 passed, 26 skipped, 0 failures
- [x] `uv run ruff check src tests` PASS
- [x] `uv run ruff format --check src tests` PASS
- [x] `uv run mypy src/erre_sandbox` → 0 errors

## レビュー

- [x] `code-reviewer`: HIGH なし / MEDIUM 2 (docstring 追記 + guard) → 対応済
      / LOW 2 件 → 受容 (decisions.md §6)
- [ ] `impact-analyzer`: skip (本 task は limited scope + code-reviewer で十分)

## ドキュメント

- [x] `docs/architecture.md` フロー 1 を M5 FSM step で renumber
- [x] `.claude/skills/architecture-rules/SKILL.md` 依存テーブル更新 (Step A)
- [x] `decisions.md` に 6 件の判断を記録

## 完了処理

- [x] 全 steering ファイルの最終化
- [ ] `git commit` (Conventional Commits:
      `feat(cognition): wire ERREModeTransitionPolicy into cognition cycle step`)
- [ ] `git push -u origin feature/m5-world-zone-triggers`
- [ ] PR 作成 → review → merge

## 制約・リマインダ

- `main` 直 push 禁止
- FSM default None で既存挙動を維持 (boot 時の wire は次タスクの責務)
- 既存 544 test に回帰なし
- architecture-rules 更新は v2 で layer が変わる場合は内容を調整

# タスクリスト — m5-dialog-turn-generator

## 準備
- [x] docs (architecture / development-guidelines / repository-structure) を Read
- [x] requirement.md を作成・承認
- [x] /reimagine で v1/v2 比較 → hybrid 採用、design.md 確定
- [x] impact-analyzer で OllamaChatClient.chat 呼び出しの影響評価 (HIGH なし)

## 実装 (commit 単位)

### commit 1: feat(inference): add think parameter to OllamaChatClient.chat ✅
- [x] `src/erre_sandbox/inference/ollama_adapter.py` に `chat(..., think: bool | None = None)` keyword-only 追加
- [x] `_build_body` で `if think is not None: body["think"] = think` を top-level に (options 外)
- [x] docstring 更新 (qwen3 thinking model, spike 判断 1 参照)
- [x] `tests/test_inference/test_ollama_adapter.py` に 3 ケース追加 + 既存 1 ケースに回帰ガード
- [x] `uv run pytest tests/test_inference/test_ollama_adapter.py -q` 全緑 (17/17)

### commit 2: feat(integration): OllamaDialogTurnGenerator with spike-derived options ✅
- [x] `src/erre_sandbox/integration/dialog_turn.py` 新規作成:
  - [x] module-private 定数 (`_DIALOG_NUM_PREDICT=120` / `_DIALOG_STOP=("\n\n",)` tuple / `_DIALOG_MAX_CHARS=160` / `_DIALOG_LANG_HINT` / `_CONTROL_CHAR_RE`)
  - [x] `_sanitize_utterance` (strip → split → ANSI/C0 scrub → collapse → None/truncate)
  - [x] `_build_dialog_system_prompt` / `_build_dialog_user_prompt` / `_build_dialog_messages`
  - [x] `OllamaDialogTurnGenerator` class (DI: llm + personas)
  - [x] docstring に幻覚 5 パターン対策明記
- [x] `tests/test_integration/test_dialog_turn.py` 新規作成 (16 parametrize ケース = 30 test cases)
- [x] `uv run pytest -q` 全体 627 passed / 31 skipped (既存 612 → +15 new、0 regression)
- [x] `uv run ruff check && uv run ruff format --check` clean

## レビュー
- [x] code-reviewer: HIGH なし、MEDIUM 4 件中 3 件対応 (_DIALOG_STOP tuple / sanitize direct tests / 80 CJK 誤記修正)、1 件 skip (`__init__.py` re-export は gateway.py 先例どおり直接 import)
- [x] security-checker: CRITICAL/HIGH なし、MEDIUM 2 件中 1 件対応 (ANSI/C0 scrub 追加)、1 件ユーザー判断で見送り (schemas.py freeze 維持、decisions.md 判断 6 参照)
- [x] HIGH 指摘: なし

## ドキュメント
- [x] `docs/functional-design.md` M5 セクションに `m5-dialog-turn-generator` 実装メモ追記
- [x] `decisions.md` 新規作成 (判断 1-6 を記録、planning 乖離の整合含む)

## 完了処理
- [x] design.md の「設計判断の履歴」確認
- [ ] 2 commit に分けて commit (Refs: .steering/20260421-m5-dialog-turn-generator/)
- [ ] PR 作成は /finish-task で別途

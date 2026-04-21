# m5-dialog-turn-generator

## 背景

M5 Phase 2 の並列 4 本のうち、LLM 対話生成の**核心タスク**。
`m5-contracts-freeze` (#56) で `DialogTurnGenerator` Protocol / `DialogTurnMsg.turn_index` /
`DialogCloseMsg.reason="exhausted"` / `Cognitive.dialog_turn_budget=6` の
インターフェースは既に凍結済。本タスクはその concrete 実装を
`src/erre_sandbox/integration/dialog_turn.py` に落とし込み、dialog_initiate 後に
LLM で turn を生成して `record_turn` → envelope emit → close 判定まで完走させる。

上位設計と spike 知見は以下に凍結済みで、**本タスクは設計根拠を新規に起こさない**:

- `.steering/20260420-m5-planning/design.md` §Phase 2 / §LLM プロンプト設計方針
- `.steering/20260420-m5-llm-spike/decisions.md` 判断 1-7 (G-GEAR qwen3:8b で 80 turn 実測)

兄弟実装として `Reflector.maybe_reflect` (`cognition/reflection.py:190`) が LLM call +
`OllamaUnavailableError` graceful fallback の手本となる。サンプリング合成は
`compose_sampling()` (`inference/sampling.py`) を流用。

## ゴール

「peripatos / chashitsu / agora / garden で dialog_initiate が admit された後、
同じ dialog に対し 6 turn までの `DialogTurnMsg` が `turn_index=0..5` で単調増加しつつ
LLM から生成され、7 turn 目の要求時点で `DialogCloseMsg(reason='exhausted')` が
emit される」状態を、mock 化された単体テストと既存実装との wiring が可能な段階まで到達させる。

LLM 不通や空応答などの失敗モードでは **例外を bubble させず None を返し**、
scheduler 側が `reason="timeout"` で既存の timeout-close 経路に合流する。

## スコープ

### 含むもの

1. **`src/erre_sandbox/integration/dialog_turn.py` 新規作成**
   - `OllamaDialogTurnGenerator` (仮称) — `DialogTurnGenerator` Protocol 実装
   - `generate_turn(*, dialog_id, speaker_state, speaker_persona, addressee_state, transcript, world_tick) -> DialogTurnMsg | None`
   - 内部で `compose_sampling()` → Ollama chat → utterance 正規化 → `DialogTurnMsg` 構築
   - OllamaUnavailableError / 空応答 / 改行巻き込み / hard-cap 超過の 4 失敗モードを defensive 処理

   - **prompt builder (system / user) と `_DIALOG_LANG_HINT` は同モジュール内に
     module-private で共存** (reflection.py の `build_reflection_messages` 先例。
     cognition/prompting.py は**触らない** — /reimagine hybrid 採用の決定)
   - `turn_index >= 2` 分岐で anti-repeat 指示を末尾に付加 (spike 判断 4)
   - addressee persona 解決のため `__init__(..., personas: Mapping[str, PersonaSpec])`
     で registry を DI

2. **`src/erre_sandbox/inference/ollama_adapter.py` 拡張**
   - `OllamaChatClient.chat(..., think: bool | None = None)` パラメータ追加
   - `_build_body` で `"think"` を top-level payload に配置 (`options` 配下ではない)
   - 既存 API 後方互換 (`think=None` で payload に含めない)

3. **テスト**
   - `tests/test_integration/test_dialog_turn.py` 新規:
     - happy path: 4 turn 連続で `turn_index=0..3` の `DialogTurnMsg` を返す
     - budget 到達時: orchestrator 相当コードが `len(transcript) >= 6` で
       `close_dialog(reason="exhausted")` を emit する assertion
     - mocked LLM で hallucination pattern 1 (言語崩壊) / 2 (完全反復) /
       5 (`\n\n` multi-utterance) の regression guard
     - `OllamaUnavailableError` 発火時に `None` を返し例外を伝播しない
     - turn_index 単調増加、speaker 交互性 (orchestrator 側ロジックも含む)
     - payload に `"think": False` が top-level に含まれる assertion
     - payload `options` に `num_predict=120, stop=["\n\n"]` が含まれる
     - persona_id 毎に `_DIALOG_LANG_HINT` が system prompt 末尾に注入される
     - addressee の `display_name` が DI registry 経由で解決され prompt に含まれる
   - `tests/test_inference/test_ollama_adapter.py` 拡張:
     - `think=True` / `think=False` / `think=None` (default) の body 形 assertion

4. **docstring**
   - `generate_turn` の docstring に decisions.md 判断 6 (幻覚 5 パターンと対策) を明記

### 触らないファイル (hybrid 決定により明示的にスコープ外)

- `src/erre_sandbox/cognition/prompting.py` — dialog prompt builder はここには置かない
- `src/erre_sandbox/integration/dialog.py` — `InMemoryDialogScheduler` は無改変
  (既存 `transcript_of(did)` の `len()` で turn_index を取得)
- `src/erre_sandbox/schemas.py` — freeze 済

### 含まないもの

- **wiring (feature flag / orchestrator 連携)** — `m5-orchestrator-integration` に委ねる。本タスクは
  単体テスト可能な Generator + Scheduler helper までで留める
- **cognition cycle への注入** — 同上、orchestrator で `scheduler.tick` と結合する段で実装
- **ERRE mode FSM** — 完了済 (#57/#58/#60)
- **sampling delta 表の変更** — spike 判断 3 で「変更不要」が確定
- **schema bump** — `m5-contracts-freeze` で確定済、追加フィールドなし
- **Godot 側 DialogBubble** — 完了済 (#59)
- **live acceptance run** — `m5-acceptance-live` の 7 項目で別途評価
- **SGLang への置き換え** — M7 以降

## 受け入れ条件

- [ ] `DialogTurnGenerator` Protocol に準拠する concrete 実装が `integration/dialog_turn.py` に存在する
- [ ] `OllamaChatClient.chat(think=False)` が payload 先頭レベルに `"think": false` を送る (unit test で HTTP body 検証)
- [ ] dialog 用 prompt builder (system / user) が `integration/dialog_turn.py` 内に module-private で存在
- [ ] `_DIALOG_LANG_HINT` dict が system prompt 末尾に persona_id 毎に注入される
- [ ] user prompt builder が `turn_index >= 2` でのみ anti-repeat 指示を付加する
- [ ] addressee の `display_name` が DI registry (`personas: Mapping[str, PersonaSpec]`) から解決される
- [ ] `cognition/prompting.py` と `integration/dialog.py` は無改変 (git diff で確認)
- [ ] mocked LLM を使った integration test で:
  - 4 回連続で `turn_index=0..3` の `DialogTurnMsg` が返る
  - `len(transcript) >= budget` で orchestrator が `close_dialog(reason="exhausted")` を emit する挙動
  - OllamaUnavailableError で generator が `None` を返し、scheduler は既存 timeout 経路に合流
- [ ] hallucination regression guard として pattern 1 / 2 / 5 の LLM 出力 fixture で utterance サニタイズ動作を検証
- [ ] `uv run pytest -q` で既存 test 全件 + 新規 test が 0 failures
- [ ] `uv run ruff check && uv run ruff format --check` が pass
- [ ] live evidence は**本タスクでは不要** (acceptance タスクで実施)

## 非機能要件

- **遅延**: spike 実測 2.3-2.7s / turn。60s window (scheduler TIMEOUT_TICKS=6, 1 tick=10s) 以内に 6 turn が
  実用的に完走できること (本タスクでは unit test のみ、実時間要件は acceptance で検証)
- **メモリ**: transcript は既存 `_OpenDialog.turns` list (上限 `dialog_turn_budget=6`) のみ、新規 DB なし
- **安全**: hard cap 160 Latin / 80 CJK chars で utterance を `[:160] + "…"` truncate (reflection.py の _MAX_SUMMARY_CHARS パターン)
- **後方互換**: `OllamaChatClient.chat` の既存呼び出し (reflection / cognition) は `think=None` default で payload 無改変

## 関連ドキュメント

- `docs/functional-design.md` M5 セクション
- `docs/architecture.md` §inference / §integration 層
- `.claude/skills/persona-erre/SKILL.md` ルール 2 / 3
- `.claude/skills/llm-inference/SKILL.md` ルール 1 / 4
- `.claude/skills/error-handling/SKILL.md` ルール 1 / 5 (generate_with_fallback パターン)
- `.steering/20260420-m5-planning/design.md` §Phase 2 / §LLM プロンプト設計方針 (上位設計)
- `.steering/20260420-m5-llm-spike/decisions.md` 判断 1-7 (実測根拠)
- `src/erre_sandbox/cognition/reflection.py` — 兄弟実装パターン (`Reflector.maybe_reflect`)
- `src/erre_sandbox/inference/sampling.py` — `compose_sampling` 流用点

## 運用メモ

- **破壊と構築 (/reimagine) 適用: Yes** (ユーザー推奨)
  - 理由: 3 軸で複数案が考えられる設計 — (1) `DialogTurnGenerator` 実装形態
    (stateless class / scheduler-aware / DI callable 等)、(2) prompt 構造
    (system の addressee 情報量 / user の transcript 提示順 / lang hint 位置)、
    (3) close 条件正規化 (generator が None を返し scheduler 委任 vs generator が直接 close emit)。
    初回案を退避して再生成案と比較した上で hybrid / どちらかを採用する。
- **タスク種別**: 新機能追加 (`/add-feature`)
- **ブランチ**: `feature/m5-dialog-turn-generator` (main=88aff07 から分岐)
- **想定工数**: 1-1.5 日 (spike と contract が先行済みのため純実装)

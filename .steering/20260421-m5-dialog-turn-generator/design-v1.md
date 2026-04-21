# 設計 — m5-dialog-turn-generator (v1 初回案)

## 実装アプローチ

`Reflector.maybe_reflect` を兄弟パターンとして踏襲する。すなわち:

- `integration/dialog_turn.py` に **stateless な concrete class** `OllamaDialogTurnGenerator`
  を置き、`DialogTurnGenerator` Protocol を実装
- 依存は **DI** (`OllamaChatClient` をコンストラクタ注入)
- `generate_turn` は「prompt builder → `compose_sampling` → `llm.chat` → utterance サニタイズ → `DialogTurnMsg` 構築」の一直線
- 失敗モード (OllamaUnavailableError / 空応答 / hard-cap 超過 / multi-utterance) は全て
  `return None` に収束させる。例外を bubble させない
- Close 条件正規化は **scheduler 側に委任** — generator は turn を生成するか None を返すかだけ
  責任を持ち、`reason="exhausted"` の close emit は scheduler helper (`should_take_turn`) + 呼び出し元
  (orchestrator) の責務

Prompt builder は `cognition/prompting.py` に既存の `build_system_prompt` / `build_user_prompt`
の兄弟として並置する。`_DIALOG_LANG_HINT` は同ファイル内 module-private な dict。

`OllamaChatClient.chat(..., think: bool | None = None)` を追加。`think is None` なら payload 無改変、
非 None なら `body["think"] = think` を top-level に書き込む。これで既存 reflection/cognition 経路は
何も変わらず、dialog_turn から呼ぶ時だけ `think=False` を渡す。

## 変更対象

### 修正するファイル

- `src/erre_sandbox/inference/ollama_adapter.py` — `chat()` に `think: bool | None = None` 追加、
  `_build_body` で top-level 配置。`ChatResponse` は無改変
- `src/erre_sandbox/cognition/prompting.py` — `build_dialog_system_prompt` / `build_dialog_user_prompt` /
  `_DIALOG_LANG_HINT` 追加。既存 `build_system_prompt` / `build_user_prompt` は無改変
- `src/erre_sandbox/integration/dialog.py` — `InMemoryDialogScheduler` に
  `should_take_turn(dialog_id, speaker_id, budget) -> bool` と `turn_index_of(dialog_id) -> int` を追加。
  既存 method は無改変

### 新規作成するファイル

- `src/erre_sandbox/integration/dialog_turn.py` —
  - `OllamaDialogTurnGenerator` class
  - `_sanitize_utterance(raw: str) -> str | None` module-private helper (改行・前後空白・
    hard-cap を一本化)
  - `_DIALOG_MAX_CHARS: Final[int] = 160`
  - `_DIALOG_NUM_PREDICT: Final[int] = 120`
  - `_DIALOG_STOP: Final[tuple[str, ...]] = ("\n\n",)`
- `tests/test_integration/test_dialog_turn.py` — mocked LLM で happy path + 4 失敗モード +
  hallucination pattern 1/2/5 regression guard
- `tests/test_inference/test_ollama_think_param.py` (or `test_ollama_adapter.py` 拡張) —
  `think=False` payload assertion
- `tests/test_cognition/test_prompting_dialog.py` — lang hint 注入 + turn_index 分岐 test
- `tests/test_integration/test_dialog_scheduler_helpers.py` (or existing test 拡張) —
  `should_take_turn` / `turn_index_of` test

### 削除するファイル

- なし

## 影響範囲

- **層**: `inference/` (adapter 拡張、非破壊) + `cognition/` (prompting.py 追加、非破壊) +
  `integration/` (新規 module + scheduler helper 2 本)
- **schema**: 無改変 (`m5-contracts-freeze` で freeze 済み)
- **wire 互換**: 既存 WS consumer (Godot / UI) は影響なし
- **既存テスト**: reflection + cognition cycle の test は `OllamaChatClient.chat` 既存シグネチャを
  そのまま使えるため回帰なし
- **後続タスク**: `m5-orchestrator-integration` が Generator + Scheduler helper を受け取り
  `CognitionCycle.step` / `scheduler.tick` に結合する

## 既存パターンとの整合性

- **`Reflector.maybe_reflect` パターン**: LLM call + OllamaUnavailableError catch → warning log + return None、
  サマリ truncate を `_MAX_SUMMARY_CHARS` でやるのと同じく `_DIALOG_MAX_CHARS` で cap
- **`InMemoryDialogScheduler` Protocol 拡張パターン**: Protocol を触らず実装固有の helper として追加
  (`tick` / `get_dialog_id` / `transcript_of` / `open_count` が先例)
- **`compose_sampling` 単一地点原則**: generator 内で
  `compose_sampling(persona.default_sampling, speaker_state.erre.sampling_overrides)` を 1 回呼ぶ
- **prompting.py の三段構成**: `_COMMON_PREFIX` → persona block → state tail の既存構造を踏襲し、
  dialog 用は persona block の後に「You are now engaged in a dialog with ...」ブロックを挿入、
  state tail の後に lang hint を末尾注入
- **Final[...] 定数配置**: reflection.py の `_MAX_SUMMARY_CHARS` / prompting.py の `_COMMON_PREFIX`
  と同じく module-private `_DIALOG_*` 定数

## テスト戦略

### 単体テスト

- **`test_ollama_think_param.py`** — `httpx.MockTransport` で request body を capture し:
  - `think=False` → `"think": false` が top-level に含まれる
  - `think=True` → `"think": true`
  - `think=None` (default) → `"think"` キー自体が存在しない (既存回帰ガード)
- **`test_prompting_dialog.py`**:
  - `_DIALOG_LANG_HINT["kant"]` が system prompt 末尾に含まれる
  - persona_id が dict 未登録なら lang hint なし (KeyError にならない)
  - `build_dialog_user_prompt(transcript=[], turn_index=0)` に anti-repeat 指示なし
  - `build_dialog_user_prompt(turn_index=2)` 以降で anti-repeat 指示あり
  - transcript が oldest → newest 順で 1 行ずつレンダリング
- **`test_dialog_scheduler_helpers.py`**:
  - `turn_index_of("nonexistent")` → 0 or `KeyError` (挙動を明示的に決める)
  - `should_take_turn` が budget=6, current=5 で True、current=6 で False
  - speaker 交互性 — 同じ speaker が連続するケースで False

### 統合テスト

- **`test_dialog_turn.py`** (mocked LLM):
  - **happy path**: `OllamaDialogTurnGenerator.generate_turn` を 6 回呼ぶと `DialogTurnMsg` が
    `turn_index=0..5` で返る
  - **exhausted close**: scheduler が 7 回目の request 時点で `should_take_turn=False` を返し、
    呼び出し元が `close_dialog(reason="exhausted")` を emit
  - **OllamaUnavailableError**: generator が `None` を返し例外伝播しない
  - **hallucination pattern 1**: モック LLM が日本語を返す場合でも system prompt に lang hint が
    注入されている確認 (prompt side assertion)
  - **hallucination pattern 2**: 同一 utterance の連続ケース → anti-repeat 指示注入の確認
  - **hallucination pattern 5**: `"A.\n\nB."` のような multi-utterance → `_sanitize_utterance` で
    `"A."` のみに切り出す
  - **hard cap**: 200 文字の応答 → `[:160] + "…"` で truncate

### E2E テスト

- 本タスクでは不要。`m5-acceptance-live` の live run で検証

## ロールバック計画

- 各ファイル追加は新規で、既存を破壊しない。`git revert` で commit 単位 rollback 可能
- `OllamaChatClient.chat` への `think` parameter 追加は optional default=None なので既存呼び出し無影響
- `InMemoryDialogScheduler` 拡張は新規メソッド 2 本のみで既存 method 無改変
- 仮に本 PR 後に dialog_turn_generator が実害 (幻覚暴走等) を出した場合、orchestrator 側の
  feature flag `--disable-dialog-turn` で Generator 呼び出しを無効化すれば schedule_initiate +
  timeout close の M4 相当挙動に戻る

## 未解決事項

- `turn_index_of` が存在しない dialog_id で KeyError を投げるか 0 を返すかの挙動
- `OllamaDialogTurnGenerator` が addressee の persona を受け取らないので `speaker` に
  `addressee_state` しか渡せない (Protocol シグネチャが固定済)。addressee の `display_name` は
  agent_id から逆引きできないため、prompt で "another agent" のように抽象化する必要あり
  → v1 では addressee の `agent_id` を system prompt に埋め込む妥協案

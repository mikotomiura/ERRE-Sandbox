# 設計 — m5-dialog-turn-generator (採用: hybrid = v2 ベース + `participants_of` も落とす)

## 実装アプローチ

**「generator の周辺が最小で済む配置を選ぶ」** を軸にする。
Protocol 外の新規 API 追加を極力避け、既存の scheduler / prompting の
責務境界を動かさない。

### 3 つの設計判断

**判断 A: Prompt builder は cognition/prompting.py には置かない**

`cognition/prompting.py` は、cognition cycle の **action-selection 用**
(RESPONSE_SCHEMA_HINT を伴う JSON action を要求する専用プロンプト) に特化した
モジュールである。dialog turn は JSON を返さず、平文 utterance を返す別責務。
先例として `cognition/reflection.py` は `build_reflection_messages` を
prompting.py に置かずに自分自身と共存させている — これは cognition の
汎用 prompting と区別すべき responsibility だからである。

従って dialog 用 prompt builder は **generator 本体と同じ module 内に module-private
で共存させる**。`cognition/prompting.py` は触らない。

**判断 B: Scheduler には新規メソッドを追加しない (または 1 つだけ追加)**

既存 `InMemoryDialogScheduler.transcript_of(dialog_id) -> list[DialogTurnMsg]` が
全 turn を返すので、orchestrator が `len(scheduler.transcript_of(did))` で
turn_index を取れる。`turn_index_of` / `should_take_turn` は既存 API の
二重化に過ぎず不要。

orchestrator が speaker 交互性を判定する際は **`transcript` の最後の話者の
反転** (空 transcript ならその dialog の `initiator` を speaker) で導ける。
`participants_of` も **YAGNI として本タスクでは追加しない** — orchestrator が
`DialogInitiateMsg` を envelope sink 経由で受け取る時点で `initiator` / `target`
を知っているため、そこから state を引けば済む。

**結果: `integration/dialog.py` は一切触らない。**

**判断 C: Close 判定は orchestrator 側に 1 行で**

generator は Protocol 通り `DialogTurnMsg | None` を返す純粋な producer。
`reason="exhausted"` の close emit は `len(transcript) >= budget` を
orchestrator が check して `scheduler.close_dialog(did, reason="exhausted")`
を呼ぶ 1 行ロジックで済む。generator も scheduler helper も拡張不要。

### 帰結

- **generator 実装**: stateless な class、DI で `OllamaChatClient` と
  `personas: Mapping[str, PersonaSpec]` を受け取る (addressee persona の
  display_name 解決のため — Protocol は `addressee_state: AgentState` しか
  渡してこないが、persona_id 経由で registry を引ける)
- **turn_index の導出**: `len(transcript)` を generator 内で計算。Protocol に
  明示パラメータなし
- **think=false**: `OllamaChatClient.chat(..., think: bool | None = None)` に
  keyword-only パラメータ追加。`_build_body` で top-level に配置
- **prompt 3 段構成**: `_common_prefix()` (RadixAttention 共有) → `_persona_block()`
  → `_dialog_context_block()` → `_lang_hint()` を system prompt に並置。
  user prompt は `_transcript_block()` + `_state_tail()` + `_anti_repeat_block()`
  (turn_index >= 2 のみ)

## 変更対象

### 新規作成するファイル

- **`src/erre_sandbox/integration/dialog_turn.py`** — 本タスクの中核モジュール
  - `class OllamaDialogTurnGenerator:` (DialogTurnGenerator Protocol 実装)
    - `__init__(self, *, llm: OllamaChatClient, personas: Mapping[str, PersonaSpec])`
    - `async def generate_turn(...)` — Protocol 通りのシグネチャ
  - module-private:
    - `_DIALOG_NUM_PREDICT: Final[int] = 120` (spike 判断 1)
    - `_DIALOG_STOP: Final[list[str]] = ["\n\n"]` (spike 判断 2)
    - `_DIALOG_MAX_CHARS: Final[int] = 160` (spike 判断 1 の hard cap)
    - `_DIALOG_LANG_HINT: Final[dict[str, str]]` (spike 判断 5)
    - `_build_dialog_messages(...)` → `list[ChatMessage]`
    - `_sanitize_utterance(raw: str) -> str | None`

- **`tests/test_integration/test_dialog_turn.py`** — 主要 integration test。
  `httpx.MockTransport` で `OllamaChatClient` に stub 応答を注入。
  cases:
  1. happy path: 4 turn 連続で `turn_index=0..3` の `DialogTurnMsg` が返る
  2. budget 到達: orchestrator 相当コードが `len(transcript) >= 6` で
     `close_dialog(reason="exhausted")` を emit する assertion
  3. `OllamaUnavailableError` → `None` return
  4. 空応答 → `None` return
  5. `"A.\n\nB."` multi-utterance → utterance が `"A."` に正規化
  6. 200 文字応答 → `[:160] + "…"` に truncate
  7. payload に `"think": false` が top-level に含まれる
  8. payload `options` に `num_predict=120, stop=["\n\n"]` が含まれる
  9. persona_id 毎に `_DIALOG_LANG_HINT` が system prompt 末尾に含まれる
  10. `turn_index=0, 1` の user prompt に anti-repeat 指示なし、`turn_index>=2` で付加
  11. addressee の `display_name` が DI registry 経由で解決されて prompt に含まれる

### 修正するファイル

- **`src/erre_sandbox/inference/ollama_adapter.py`**
  - `OllamaChatClient.chat(messages, *, sampling, model=None, options=None, think: bool | None = None)` — 最後に keyword-only `think` 追加
  - `_build_body` で `think is not None` なら `body["think"] = think` を top-level に追加
  - docstring 更新 (qwen3 系 thinking model への `think=False` 意味を記載)
  - 既存 `stream: False` はそのまま。`model / messages / options / think` の 4 top-level キーが最大

### 削除するファイル

- なし

### テスト (追加)

- **`tests/test_inference/test_ollama_adapter.py` 拡張** (新規ファイル作らない) —
  既存 test file があるかを確認し、あれば拡張、なければ新規作成。
  - `think=True` / `think=False` / `think=None` (default) それぞれの body 形を assert

**`integration/dialog.py` / `cognition/prompting.py` のテストは新規追加しない**
(両 file を本タスクで触らないため回帰リスクなし)。

## 影響範囲

- **層**: `inference/` 1 file 修正 + `integration/` 1 file 新規 (既存 file は無改変)
- **schema**: 無改変 (freeze 済)
- **wire 互換**: 100% — `OllamaChatClient.chat` の既存呼び出し (reflection,
  cognition cycle) は `think=None` default で無改変、reflection の既存テスト
  0 failure 保証
- **cognition 層**: 一切触らない — `prompting.py` / `reflection.py` / `cycle.py` 無改変
- **Godot**: 無影響
- **documents**: `docs/functional-design.md` の M5 セクションに 1 行追記
  ("m5-dialog-turn-generator live" マーカー) を finish-task 時に行う
  (本タスク範囲内だが optional)

## 既存パターンとの整合性

| 参考元 | v2 で踏襲する点 |
|---|---|
| `cognition/reflection.py` (`Reflector`) | LLM call + `OllamaUnavailableError` → None、prompt builder を同ファイル内に共存、hard cap (`_MAX_SUMMARY_CHARS`) truncate |
| `inference/ollama_adapter.py` (`_build_body`) | keyword-only 追加パラメータの後方互換性 (既存呼び出しは `None` で無改変) |
| `integration/dialog.py` (既存 read accessors `get_dialog_id` / `transcript_of` / `open_count`) | orchestrator は既存 `transcript_of(did)` の `len()` で turn_index を取得、`DialogInitiateMsg` 経由で initiator/target を既に保持するため **新規 accessor 不要** |
| `inference/sampling.py` (`compose_sampling`) | 単一地点原則を崩さず、generator 内で 1 回だけ呼ぶ |
| persona-erre Skill §ルール 3 (RadixAttention 最適化) | system prompt の共通 prefix を先頭に配置 |
| persona-erre Skill §ルール 2 (sampling delta) | 既存 `compose_sampling` に `erre.sampling_overrides` を渡すだけ、delta table は変更しない (spike 判断 3) |
| error-handling Skill ルール 1 | `try: ...; except OllamaUnavailableError: logger.warning; return None` |
| error-handling Skill ルール 5 | LLM 出力の defensive 処理 (空応答 / hard-cap / `\n\n` 混入 → None / 切り出し / truncate) |

## テスト戦略

### 単体テスト

**`test_ollama_adapter.py` (拡張)**
- `think=False` / `think=True` / `think=None` の 3 ケースで `_build_body` の
  出力辞書を assert (`httpx.MockTransport` で request body capture)
- `think` が `options` ではなく top-level に入ることを明示

### 統合テスト

**`test_dialog_turn.py` (新規)** — 全 11 ケースを 1 file に集約。LLM は
`httpx.MockTransport` で stub 化し、shared fixture で:
- `personas: dict[str, PersonaSpec]` に 3 persona を入れる (kant / rikyu / nietzsche)
- `transcript` を 0..N turn で parametric に渡して turn_index 分岐を検証
- `httpx.MockTransport` の handler を parametric に切り替え (happy / empty /
  multi-utterance / too-long / http 500 → OllamaUnavailableError)

### E2E テスト

- 本タスクでは不要 — `m5-acceptance-live` の項目 4 (dialog_turn LLM 生成) で
  G-GEAR 実機で検証される

### 回帰テスト

- `uv run pytest tests/test_inference/ tests/test_cognition/ tests/test_integration/`
  で既存 suites が全て緑のまま
- `uv run ruff check && uv run ruff format --check` pass
- `uv run pytest -q` 全体で 0 failures (既存 525 + 新規 ~15)

## ロールバック計画

- **commit 粒度**: 2 commit で分割
  1. `feat(inference): add think parameter to OllamaChatClient.chat`
  2. `feat(integration): OllamaDialogTurnGenerator with spike-derived options`
- 各 commit は独立して revert 可能
- dialog_turn.py は新規作成なので削除のみで rollback 完了
- `OllamaChatClient.chat` の `think` パラメータは optional なので revert 後も
  既存呼び出しは無影響
- **運用時の feature flag** (本タスク範囲外だが明記): `m5-orchestrator-integration`
  で `--disable-dialog-turn` を実装するとき、この flag が OFF なら generator
  自体を import しない / 呼び出さない分岐を orchestrator 側に置く

## 明示的に解決した「未解決事項」

**v1 の `turn_index_of` 存在しない id 挙動の曖昧さ**
→ v2 では `turn_index_of` 自体を追加しない。orchestrator が
`len(scheduler.transcript_of(did))` を呼び、存在しない id なら既存挙動
(empty list) で 0 が返る。挙動が既存 API の自然な延長として自動的に決まる。

**v1 の addressee persona resolution の妥協案**
→ v2 では generator `__init__` に `personas: Mapping[str, PersonaSpec]`
registry を DI する。orchestrator はすでに全 persona を load しているので
`personas={"kant": ..., "rikyu": ..., ...}` を渡すだけ。generator は
`personas[addressee_state.persona_id]` で `display_name` を引ける。妥協なし。

## 設計判断の履歴

- 2026-04-21: `/reimagine` で v1 (初回案) を `design-v1.md` に退避し、v2 を
  ゼロから再生成して比較 (`design-comparison.md`)
- **採用: hybrid (v2 を 95% 採用 + v2 が提案した `participants_of` も YAGNI として落とす)**
- 根拠:
  - cognition 層無改変で既存 525 test の回帰リスクゼロ
  - `transcript_of(did)` と `_OpenDialog` state の二重化を避ける
  - addressee persona resolution を DI registry で正面解決 (v1 の未解決事項を潰す)
  - orchestrator は `DialogInitiateMsg` envelope から initiator/target を既知なので
    scheduler に新規 read accessor を足す理由が薄い
  - 変更ファイル 4 個 (新規 2 + 修正 2) で PR サイズ最小
- 乖離: `.steering/20260420-m5-planning/design.md` が示す
  「`build_dialog_system_prompt` を `cognition/prompting.py` に置く」指示との
  乖離は本タスク完了時に `decisions.md` に根拠を記録して整合を取る

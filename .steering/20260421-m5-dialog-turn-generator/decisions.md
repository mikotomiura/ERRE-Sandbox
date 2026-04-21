# Decisions — m5-dialog-turn-generator

本タスクで採用した設計判断とその根拠。後続タスク (`m5-orchestrator-integration`,
`m5-acceptance-live`) が本文書を単一の判断根拠として参照すること。

---

## 判断 1: prompt builder は `cognition/prompting.py` に置かず、`integration/dialog_turn.py` に co-locate

- **判断日時**: 2026-04-21
- **背景**: `.steering/20260420-m5-planning/design.md` §Phase 2 / §LLM プロンプト設計方針 では
  `build_dialog_system_prompt` / `build_dialog_user_prompt` を `cognition/prompting.py` に
  追加するとされていた (planning 当時の自然な延長案)。
- **本タスクでの再検討** (`/reimagine` v2 再生成案):
  - `cognition/prompting.py` は action-selection 用に特化した module で、`RESPONSE_SCHEMA_HINT`
    による JSON 契約を前提とする。dialog turn は平文 utterance を返す別責務
  - 先例: `cognition/reflection.py` は `build_reflection_messages` を
    `cognition/prompting.py` に置かずに自分自身と共存させている (同じパターン)
  - cognition 層を無改変にすることで既存 525+ test の回帰リスクがゼロ
- **採用**: prompt builder (`_build_dialog_system_prompt` / `_build_dialog_user_prompt` /
  `_DIALOG_LANG_HINT`) を `integration/dialog_turn.py` に module-private で配置する
- **planning 文書との乖離**: `.steering/20260420-m5-planning/design.md` の該当箇所は
  immutable として扱う (planning は時点の判断を残す文書)。本 decisions.md が後続の真実
- **影響範囲**: 本タスクのみ。cognition 層完全無改変

## 判断 2: `InMemoryDialogScheduler` 拡張は行わない (planning の `should_take_turn` / `turn_index_of` / v2 の `participants_of` すべて不採用)

- **判断日時**: 2026-04-21
- **背景**:
  - v1 初回案: `should_take_turn` / `turn_index_of` を scheduler helper として追加
  - v2 再生成案: `participants_of` 1 本に縮小
- **本タスクでの決定**: **いずれも追加しない** (hybrid 採用)
- **根拠**:
  - `turn_index` は generator 内で `len(transcript)` から導出でき、scheduler helper 不要
  - `should_take_turn` の budget 判定も orchestrator 側で `len(scheduler.transcript_of(did))
    >= dialog_turn_budget` の 1 行で書ける
  - `participants_of` は orchestrator が `DialogInitiateMsg` envelope から `initiator_agent_id`
    / `target_agent_id` を既に受け取っているため不要 (envelope sink 経由で orchestrator が
    state を保持する想定)
- **採用**: `InMemoryDialogScheduler` は本タスクで一切変更しない。既存 8 メソッド + 2 property
  で十分
- **影響範囲**: `src/erre_sandbox/integration/dialog.py` 無改変、`tests/test_integration/test_dialog.py`
  回帰リスクゼロ

## 判断 3: `OllamaChatClient.chat(..., think: bool | None = None)` 追加、payload top-level emit

- **判断日時**: 2026-04-21
- **背景**: `.steering/20260420-m5-llm-spike/decisions.md` 判断 1 より、qwen3:8b は thinking
  model で `"think": false` を payload top-level に送らないと response が空になる (`<think>`
  トークンで budget を消費)。
- **実装**:
  - public `chat()` に keyword-only `think: bool | None = None` 追加
  - `_build_body` で `if think is not None: body["think"] = think` を top-level に配置
    (`options` dict ではなく body 直下)
  - 既存 reflection / cognition cycle の呼び出しは `think=None` default で payload 無改変
- **回帰ガード**: `test_chat_sends_sampling_and_messages` に `assert "think" not in body` を追加、
  さらに `test_chat_think_none_omits_key` で明示的に検証
- **後方互換**: 100% (既存 612+ test が無改変で pass)

## 判断 4: addressee persona resolution は DI registry (`personas: Mapping[str, PersonaSpec]`) で正面解決

- **判断日時**: 2026-04-21
- **背景**: `DialogTurnGenerator` Protocol (`schemas.py`) は `addressee_state: AgentState` を
  渡すが `addressee_persona: PersonaSpec` は渡さない (Protocol freeze 済)。しかし prompt で
  addressee を `display_name` で呼びかける必要がある (spike で実証された自然対話条件)。
- **v1 案**: 未解決事項として残置、prompt に `agent_id` を埋める妥協
- **v2 採用案**: `OllamaDialogTurnGenerator.__init__(*, llm, personas)` で persona registry を DI。
  `addressee_persona = self._personas.get(addressee_state.persona_id)` で解決。
  未登録なら `None` に fall back し、prompt builder が `addressee_state.agent_id` に degrade
- **orchestrator 側の配線**: composition root (`bootstrap.py`) はすでに全 persona を load しているため、
  `personas={"kant": ..., "rikyu": ..., "nietzsche": ...}` を渡すだけ
- **テスト**: 登録時に `display_name` (千 利休 等) が prompt に含まれる / 未登録時に `agent_id`
  fallback、の 2 ケースを verify

## 判断 5: `_sanitize_utterance` は ANSI/C0 制御文字除去を追加 (defense-in-depth)

- **判断日時**: 2026-04-21 (security-checker レビュー後)
- **背景**: LLM 出力が `DialogTurnMsg.utterance` として WebSocket 経由で Godot /
  Streamlit dashboard に流れる。qwen3 は ANSI escape や C0 制御文字を出さないが、
  モデル misbehaviour / 将来のバックエンド差し替え時に stray byte が下流 renderer を
  壊す可能性。
- **対策**: `_CONTROL_CHAR_RE` で ANSI CSI (`\x1b\[[0-9;]*[A-Za-z]`) を先に match、次いで
  C0 制御文字 (`\x00-\x08` / `\x0b\x0c` / `\x0e-\x1f` / `\x7f`) を除去。`\t` / `\n` / `\r`
  は既存 `.split()` / `.strip()` 経路で whitespace collapse されるため regex で触らない
- **regex alternation 順序**: ANSI alt を先に置く (C0 class が ESC=0x1b を単独で食うと
  `[31m` が残るため)
- **テスト**: `test_sanitize_utterance_pipeline` の parametrize で 16 ケース (happy / empty
  / boundary 160 char / ANSI / C0 / CJK / tab) を直接検証

## 判断 6: schemas.py への `DialogTurnMsg.utterance: Field(max_length=256)` 追加は**見送り**

- **判断日時**: 2026-04-21 (security-checker SEC-M2 をユーザーが No 判断)
- **security-checker 提案 (MEDIUM)**: defense-in-depth として Pydantic schema 層で 256 char
  上限を設け、`_sanitize_utterance` をバイパスした直接構築経路 (test fixture / 将来の別
  generator) からも validation できるようにする
- **ユーザー判断**: **見送り** (option 2 "No, 現状で十分")
  - `schemas.py` は `m5-contracts-freeze` (#56) で凍結済、freeze 後に触る前例を作らない
  - 現状の runtime sanitize (`_DIALOG_MAX_CHARS=160`) で spike 観測 max=118 に対し 1.4x
    headroom、LOW リスク
  - 本番経路で `DialogTurnMsg` を generator 以外から構築する経路は存在しない
- **後続**: 将来 `m5-schemas-defensive-constraints` 等で検討する選択肢を残す。本文書が
  該当判断の記録

---

## 後続タスク `m5-orchestrator-integration` が本文書から取り出すべき値

1. `OllamaDialogTurnGenerator(llm=..., personas={"kant":..., "rikyu":..., "nietzsche":...})`
   で construct
2. dialog tick 内で:
   - `transcript = scheduler.transcript_of(dialog_id)`
   - `if len(transcript) >= speaker_state.cognitive.dialog_turn_budget: scheduler.close_dialog(did, reason="exhausted"); return`
   - `msg = await generator.generate_turn(...)`
   - `if msg is None: # Ollama unavailable / empty / etc. — soft close via timeout path`
   - `if msg: scheduler.record_turn(msg); gateway.inject_envelope(msg)`
3. speaker 交互性: `initiator / target` を `DialogInitiateMsg` envelope から取得済みの想定。
   `speaker = initiator if len(transcript) % 2 == 0 else target`
4. feature flag `--disable-dialog-turn` を追加する場合は generator 呼び出し自体をスキップ
   (scheduler は既存どおり動いて timeout close に帰着)

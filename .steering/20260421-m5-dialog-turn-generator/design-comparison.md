# 設計案比較 — m5-dialog-turn-generator

`/reimagine` により v1 (初回案) を `design-v1.md` に退避し、v2 (再生成案) を
`design.md` に新規生成。両案を比較して採用を判断する。

## v1 (初回案) の要旨

- `integration/dialog_turn.py` に `OllamaDialogTurnGenerator` (stateless class + DI)
- Prompt builder (`build_dialog_system_prompt` / `build_dialog_user_prompt`) を
  `cognition/prompting.py` に既存 `build_system_prompt` の**兄弟として拡張**
- `InMemoryDialogScheduler` に helper **2 本** (`should_take_turn` /
  `turn_index_of`) を追加し、turn 上限と交互性を scheduler 側で判定
- `OllamaChatClient.chat` に `think: bool | None = None` を追加
- addressee の persona resolution は**未解決事項**として残置、prompt では
  `agent_id` をそのまま埋め込む妥協案
- 新規 test ファイル: `test_dialog_turn.py`, `test_ollama_think_param.py`,
  `test_prompting_dialog.py`, `test_dialog_scheduler_helpers.py` (計 4)

## v2 (再生成案) の要旨

- `integration/dialog_turn.py` に `OllamaDialogTurnGenerator` (stateless class + DI、
  ただし DI に `personas: Mapping[str, PersonaSpec]` registry を追加)
- Prompt builder は **`integration/dialog_turn.py` に module-private で同居**
  (cognition/prompting.py を**一切触らない**)。先例: reflection.py も
  `build_reflection_messages` を cognition/prompting.py に置かず自分自身と同居
- Scheduler は `participants_of` **1 本のみ追加** (`should_take_turn` /
  `turn_index_of` は不要 — 既存 `transcript_of(did)` の `len()` で十分)
- `OllamaChatClient.chat` に `think: bool | None = None` (v1 と同)
- addressee persona resolution は DI registry で**正面から解決** (未解決事項なし)
- `turn_index` は generator 内で `len(transcript)` から導出 — 明示パラメータなし
- 新規 test ファイル: `test_dialog_turn.py` のみ (計 1)。他は既存 file 拡張

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| **prompt builder の配置** | `cognition/prompting.py` 拡張 | `integration/dialog_turn.py` 内 module-private |
| **cognition 層の変更** | あり (prompting.py に 2 関数 + dict 追加) | **なし** (無改変) |
| **scheduler helper** | 2 本追加 (`should_take_turn`, `turn_index_of`) | 1 本追加 (`participants_of`、しかも read-only で最小) |
| **addressee persona 解決** | 未解決 → agent_id を埋める妥協 | DI registry で正面解決 |
| **turn_index の source of truth** | scheduler の `turn_index_of` | 既存 `transcript_of(did)` の `len()` (二重化なし) |
| **close 条件判定の配置** | scheduler helper が返す | orchestrator が `len(transcript) >= budget` で直接判定 |
| **generator DI** | `OllamaChatClient` のみ | `OllamaChatClient` + `personas: Mapping` |
| **新規 test ファイル数** | 4 | 1 |
| **変更ファイル数** | 新規 1 + 修正 3 + test 新規 4 = 8 | 新規 1 + 修正 2 + test 新規 1 + 既存拡張 2 = 6 |
| **Protocol 実装形態** | stateless class + DI | 同じ (収束) |
| **think=false の配置** | `chat(..., think=...)` top-level | 同じ (収束) |
| **失敗モード正規化** | generator が None return | 同じ (収束) |

## 評価

### v1 の長所

- `build_system_prompt` / `build_dialog_system_prompt` が並ぶ対称性は
  一見「美しい」(同じファイル内で "cognition 用" / "dialog 用" と読める)
- `should_take_turn` のような scheduler helper があると orchestrator 側コードが
  1 行短くなる (`scheduler.should_take_turn(...)` の方が `len(scheduler.transcript_of(...)) < budget` より短い)
- spike decisions.md と design.md (planning) で明示的に「build_dialog_system_prompt
  を cognition/prompting.py に置く」と書かれていた → 踏襲が明快

### v1 の短所

- `cognition/prompting.py` は action-selection の JSON 契約 (`RESPONSE_SCHEMA_HINT`)
  に特化した module であり、平文 utterance を返す dialog 用 builder とは
  **責務が異なる**。混在させると「cognition が dialog を知ってる」という
  方向性の依存が生まれる (architecture rules 的には許容範囲だが層境界が曖昧になる)
- scheduler helper 2 本は `transcript_of(did)` + `_OpenDialog` の既存 state を
  **二重化**した API を露出するだけで、新情報を提供しない
- addressee persona resolution を「未解決」として残したまま実装に入ると、
  prompt が `agent_id` (`a_rikyu_001` 等) を埋めて LLM に出ることになり、
  `display_name` を使う既存 reflection / cognition prompt と不整合
- 新規 test ファイル 4 個は維持コストがやや高い (小さい helper に対する
  専用ファイルが多い)

### v2 の長所

- cognition 層無改変 = **既存テスト (reflection / cycle / prompting) の
  回帰リスクがゼロ**。既存 525 test が原理的に影響を受けない
- scheduler helper 1 本のみ追加で API 表面を最小に保つ。`transcript_of` の
  存在感を尊重
- addressee persona resolution を DI registry で正面解決し、prompt 品質が
  spike の前提と一致 (`display_name` で呼びかける)
- 変更ファイル数 6 vs v1 の 8。PR サイズが小さく review しやすい
- `turn_index = len(transcript)` の導出を 1 箇所に閉じ込める。scheduler と
  generator の two-source-of-truth 問題を回避

### v2 の短所

- `cognition/prompting.py` に対称な builder を置かないので、将来「dialog
  prompt builder はどこ?」と探す人が一瞬迷う (ただし `integration/dialog_turn.py`
  で自明、docstring で明記すれば解決)
- `participants_of` は現状 orchestrator が使うかどうか曖昧 (speaker 交互性は
  transcript の末尾から導ける)。**YAGNI の可能性**あり —
  必要になった時に追加する選択肢もある
- design.md (planning) の指示 (`build_dialog_system_prompt` を
  `cognition/prompting.py` に置く) と乖離する。planning 文書の更新が必要

## 推奨案

**hybrid (v2 ベース + v1 から 1 点取り入れ)**

理由:
- **prompt builder の配置は v2 採用** — cognition 層責務の清潔さ、reflection.py
  の先例、既存テストの回帰リスクゼロ という 3 つの利点が v1 の「対称性」より
  重い
- **scheduler helper は v2 採用** (`should_take_turn` / `turn_index_of` を
  追加しない) — 既存 `transcript_of(did)` と二重化するだけで新情報がないため
- **`participants_of` は追加しない (v1 も v2 も明示提案したが YAGNI)** —
  orchestrator が speaker 交互性を実装する段で必要になったら追加する。
  本タスクでは `integration/dialog.py` を**一切触らない**ことにして、
  scope を更に絞る
- **addressee persona resolution は v2 採用** (DI registry)
- **think=false / close 判定の配置 / Protocol 実装形態 は収束しているので
  そのまま**
- **planning 文書の更新**: `.steering/20260420-m5-planning/design.md` の
  `build_dialog_system_prompt` 配置に関する記述は、本タスクの decisions.md に
  「prompting.py ではなく integration/dialog_turn.py に co-locate することにした」と
  判断根拠を記録する形で整合させる (planning 文書自体は immutable として扱う)

この hybrid は v2 を 95% 採用した上で、v2 が提案した `participants_of` だけ
落とすもの。結果として:

| 変更ファイル | 内容 |
|---|---|
| 新規 `src/erre_sandbox/integration/dialog_turn.py` | Generator + prompt builder + sanitize |
| 修正 `src/erre_sandbox/inference/ollama_adapter.py` | `chat(think=...)` 追加 |
| 修正 `tests/test_inference/test_ollama_adapter.py` (既存) | `think` パラメータ test |
| 新規 `tests/test_integration/test_dialog_turn.py` | 11 ケース |

**変更ファイル 4 個、そのうち新規 2 個、修正 2 個** で完結。

## 次のステップ

ユーザーが採用案を確定 (v1 / v2 / 上記 hybrid / その他) したら、その内容を
`design.md` 末尾に追記し、`tasklist.md` の作成 → `/add-feature` へ進む。

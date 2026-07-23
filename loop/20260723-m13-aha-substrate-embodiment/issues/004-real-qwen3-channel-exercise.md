# Issue 004 (I4): real qwen3 + real embedding fully-real record→replay channel exercise（spend ratify ゲート）
verify_level: recheck   # 決定性（record→replay）+ measurement 非再入境界 = 独立再走対象。**実行は user spend ratify 必須**

## Goal
traversal harness を **real qwen3:8b（LLM、think=false）+ real embedding（nomic-embed-text、768d、local Ollama）** で
走らせ、substrate を mock-only でなく **fully-real な real-LLM + real 768d retrieval** で exercise する。ただし
**guard-compliant な「channel exercise」**に留める: real qwen3 が waypoint stimulus に *emergent* に応答した結果を
**record→replay で決定論化**し、二相 knob が（emergent に生じた）λ>0 evaluation tick で発火することを **boolean** で観察。
**traversal（distinct zone を巡ったか）は要求せず honest な count annotation** に留める（gate にしない = toward-tuning
回避）。「real-LLM emergent traversal が効く」「real embedding が multi-zone を生む」とは**主張しない**（Codex HIGH-2 の
defer + embedding ⊥ zone を channel-exercise 枠で最小限に扱うのみ）。

**embedding についての honest 前提（DA-1/DA-7）**: real embedding は **zone routing の梃子ではない**（embedding ⊥ zone、
reflect_clamp 保証）。real embedding を入れるのは「fully-real な substrate（real 768d retrieval が within-zone geometry +
LLM context の両方に効く）」のためであって、collapse を直す・multi-zone を生むためではない。scope (a)「real embedding で
multi-zone」の誤診とは別物（ここでは real 実装を genuine にするだけ）。

## Background
FROZEN ADR + Codex HIGH-2（emergent traversal は defer）。Phase 4b（`project_aha_phase4b_construction_validation_live`）の
real qwen3 sealed run パターン = record→replay + boolean firing + O5 を「hard gate でない count annotation」に留めた前例を
踏襲。`two_phase_live.py` / `aha_phase4b_two_phase_live_capture.py` の real-Ollama 経路（`OllamaChatClient` +
`ThinkOffChatClient` + record/replay + SamplingSpy）を再利用。real qwen3 は **settle 空振りしうる**（Phase 4b run1 =
no_eligible_tick）ゆえ honest 両報告（空振りも成果として記録、stimulus を巡らせるまで調整しない）。

## Scope
### In
- `scripts/aha_traversal_live_capture.py` に **real mode**（`--real` / `--model qwen3:8b` / `--embed-model nomic-embed-text`）追加:
  real `OllamaChatClient`（think=false）+ **real `EmbeddingClient`（nomic-embed-text、既存 `memory/embedding.py`、mock
  差し替え、新規 Python 依存なし）** で traversal harness を走らせ、LLM plan（Plane 2）+ **embedding/retrieval 結果**を
  record → replay 決定論。embedding 結果は Plane 1 決定論のため record するか cross-platform 6桁量子化（float drift 対策、
  `feedback_golden_crossplatform_float_drift`）。
- **real sealed run（実行は spend ratify ゲート、下記 Stop 参照）**: N tick の sealed capture → record→replay-verify
  byte 一致（Plane 1 決定論）。
- channel-exercise witness（boolean/count のみ、verdict=None、side file）:
  - `sign_inversion_fired` を real 記録の（emergent に生じた）λ>0 evaluation tick に適用 = boolean 発火。
  - **traversal count annotation**: 記録 route の distinct zone 数 / move_t=1 tick 数を **honest count で注記**（hard
    gate にしない、`≥K` 要求なし = toward-tuning 回避、Phase 4b O5 と同型）。空振り（settle→λ=0）も honest に記録。
- `experiments/<date>-aha-traversal-real/`（reproducibility-discipline、seed/lockfile 固定、run.sh、capture.log）。
- 実走結果を `docs/research-positioning.md §8` arc-log に honest 追記（空振り含む、over-read しない）。
### Out
- traversal を「効く」と主張・gate 化（emergent traversal の validation は依然 defer）。
- effect/divergence/floor/aha proxy/verdict の算出・emit（measurement 非再入）。
- stimulus の toward-tuning（巡るまで調整）。organ 6ファイル改変。

## Allowed Files
- `scripts/aha_traversal_live_capture.py`（I3 から real-mode 拡張）
- `src/erre_sandbox/integration/embodied/traversal_live.py`（real-client 受け入れの最小拡張、organ 無改変）
- `tests/test_integration/test_traversal_live.py`（real-mode の mock 化 unit + replay 決定論 test。real 実走自体は CI 非対象）
- `experiments/<date>-aha-traversal-real/*`（run.sh / capture.log / manifest、committed artifacts）
- `docs/research-positioning.md`（§8 arc-log、honest 追記）
- **無改変厳守**: organ 6ファイル + two_phase_live.py の firing witness + `memory/embedding.py` の `EmbeddingClient`
  + `inference/ollama_adapter.py`（read-only 再利用、real qwen3 + real embedding は既存クライアントを使うだけ）

## Acceptance Criteria（AC↔test）
- I4-G1（実行ゲート）: **real 実走の前に user spend ratify を得る**（未取得なら本 issue は blocked、code path のみ land）。
- I4-G2 `test_traversal_real_mode_replay_determinism`（mock 化）: real-mode の record→replay が byte 決定論（real
  Ollama をモックした unit）。
- I4-G3（real 実走時）: sealed capture → replay-verify byte 一致（Plane 1 決定論、WSL byte-parity 継承）。
- I4-G4: channel-exercise witness が boolean/count のみ（traversal を gate 化しない、空振りも honest 記録）。
- I4-G5: arc-log に honest 追記（emergent traversal を「効く」と over-read しない）。
- CI parity: `pwsh scripts/dev/pre-push-check.ps1` 4 段全緑（real 実走は CI 非対象、mock unit のみ CI）。

## Test Plan
`pytest -q tests/test_integration/test_traversal_live.py -k real_mode`（mock 化 unit、CI 緑）+ pre-push 4 段。
real 実走（ratify 後）= `python scripts/aha_traversal_live_capture.py --real --capture` → `--verify` byte 一致。

## Stop Conditions
- **user spend ratify 未取得 → real 実走せず code path のみ land（blocked、別 ratify 待ち）**。
- real qwen3 が settle 空振り（λ=0）→ **honest に記録して終了**（stimulus を巡らせるまで調整=禁止）。Phase 4b run1 と同型、
  pre-register 再走は 1 回まで（結果選別しない）。
- real record→replay が byte 不一致 → Plane 1/2 分離漏れを塞ぐ（Phase 4b/ECL 前例）。
- organ 改変を要する → Stop→superseding ADR。budget / ChatGPT usage cap → Stop。

## Dependencies
- I1 + I2 + I3（traversal harness + witnesses + 決定論 golden apparatus）。

## Status
done（**code path のみ。実行は user spend ratify ゲートで BLOCKED**、I4-G1）

## Execution Result

**Status: DONE（code path 全緑）/ real 実走 = BLOCKED（I4-G1 実行ゲート、user spend ratify 未取得）**。

### 変更ファイル
- `src/erre_sandbox/integration/embodied/traversal_live.py`（I1-I3 から拡張、+約230行）:
  `run_traversal_capture` に `inner_chat: Any | None = None`（省略時は既存 `ScriptedTraversalChatClient()`
  で I1-I3 と byte-identical、real client 注入は完全 additive）+ `RecordedEmbeddingCall`（frozen dataclass）
  + `EmbeddingReplayError` + `EmbeddingRecordReplayClient`（`loop.RecordReplayChatClient` を embedding
  channel 用に mirror した新設 record/replay apparatus、record 時 6桁量子化）+
  `traversal_channel_exercise_summary`（非 gate count annotation）。
- `scripts/aha_traversal_live_capture.py`（I3 から real mode 拡張、+約400行）: `--real`/`--model`/
  `--embed-model` CLI flag、`real_capture()`（real `OllamaChatClient` + real `EmbeddingClient` を
  record mode で駆動、実行はしていない）、`real_verify()`（両 Plane1 channel の committed JSONL から
  Ollama-free replay）、`_committed_firing_annotation` を `embedding_factory` 引数化（I3 の default 挙動は
  不変、real mode は committed embedding record を on/off 両 replay で共有）。
- `tests/test_integration/test_traversal_live.py`（I3 の15 testから20 testへ拡張）: 5 新規test
  （`test_traversal_real_mode_replay_determinism` = I4-G2 中核、`EmbeddingRecordReplayClient` 単体2本、
  channel-exercise summary 非gate確認、experiments scaffold 存在確認）。`_SCRIPT_SRC` は既にI3のM1 guardで
  scan対象（I4追加分も継続カバー）。
- `experiments/20260723-aha-traversal-real/`（新規）: `env.md`（BLOCKED状態明記）+ `run.ps1`（real capture、
  未実行）+ `repro.ps1`/`repro.sh`（Ollama-free verify、real実走後にのみ機能）。`artifacts/` は意図的に未作成。
- `docs/research-positioning.md §8`（arc-log 追補、I1-I3 entryの末尾に1段落）。

### real 実走を走らせていないことの確認
本タスク中、`python scripts/aha_traversal_live_capture.py --real --capture`（または `--verify`）は
**一度も実行していない**。`nvidia-smi` 等の GPU/Ollama 確認コマンドも未実行。`OllamaChatClient`/
`EmbeddingClient` の real インスタンスは `real_capture()`/`real_verify()` 関数定義の中でのみ参照され、
これらの関数自体を呼び出すコードは書いたが実行していない（実行したのは全て mock 化 unit test のみ、
`httpx.MockTransport` 経由で real Ollama に一切接続しない）。

### mock 化 replay 決定論 unit の結果
`test_traversal_real_mode_replay_determinism`: `_mock_real_chat_client()`（emergent-likeな非scripted
応答、itineraryに従わない）+ `_mock_real_embedding_client()`（sha256由来のtext-varying vector、
constant-vectorでない）を `run_traversal_capture(inner_chat=...)` の新設注入点で駆動し record run実施。
`embedding_wrapper.inner_invocations > 0`（mock backend実際に呼ばれた）を確認後、両channel
（`RecordReplayChatClient` + `EmbeddingRecordReplayClient`）をreplay modeで再構築し
`run_two_phase_capture` を再実行。**結果: replay 側 `inner_invocations==0`（両channel、real/mock backend
に一切触れず）、checksum/decisions_jsonl/rows 完全一致（byte決定論、I4-G2 満たす）**。

### channel-exercise witnessの非gate性
`traversal_channel_exercise_summary` は `hard_gate=False`/`verdict=None`/`>=K`閾値なし。
`test_traversal_channel_exercise_summary_is_non_gate` で settled run（0 move）とmoved runの両方を
honestに区別して報告することを確認（settled runをfailにしない、fabricateもしない）。firing annotation
も同様に非gate（既存 `two_phase_firing_summary` を real committed decisions + real committed embedding
recordで駆動、I3の`_committed_firing_annotation`を`embedding_factory`引数化して再利用）。

### 新規依存の有無
**なし**。real embedding/chat は既存 `memory/embedding.py::EmbeddingClient` /
`inference/ollama_adapter.py::OllamaChatClient`（共に既存 `httpx` ベース、無改変read-only再利用）のみ。
sentence-transformers/sklearn/torch/peft/sglang等の新規importなし。3点セット（lazy import + mypy ignore
+ importorskip）は不要と確認（新規依存自体が存在しない）。

### test結果
`pytest -v tests/test_integration/test_traversal_live.py -k real_mode`: **1 passed**
（`test_traversal_real_mode_replay_determinism`のみ、他real関連testは`embedding_record`/
`channel_exercise`/`experiments_scaffold`キーワードで別途4件）。`pytest -v test_traversal_live.py`
（全体）: **20 passed**（W1-W4 + I4新規5件、回帰ゼロ）。`pytest -q test_two_phase_live.py`: 20 passed。
**フルpre-push相当**: `ruff format --check src tests`緑（568 files）/ `ruff check src tests`緑 /
`mypy src`緑（244 files）/ `pytest -q --ignore=tests/test_godot`: **3807 passed, 52 skipped**
（既存3802 + I4新規5、skipは環境依存の既存条件のみ）。script自体はT201(print)/PLC0415(lazy import)が
既存script群と同一のpre-existing状態（`scripts/`はpre-push対象外、`mypy scripts/*.py`単独実行のみの
import-untypedも同様）。real_verify()のPLR0912/PLR0915(複雑度)は`_real_replay`/`_check_artifact_bytes`
helperへの抽出でクリアに解消済み。

### organ無改変
`git diff --stat` を organ 6ファイル + `two_phase_live.py` + `live_v1.py` + `live.py` +
`memory/embedding.py` + `inference/ollama_adapter.py`（I4で新規read-only参照）に対し実行、出力なし（空）。

### guard遵守
real Ollama未実行（上記）。construction-only・measurement非再入（effect/divergence/floor/aha proxy/
verdict非emit、`test_traversal_measurement_guard`が`_SCRIPT_SRC`含め継続AST スキャン）。traversal を
「効く」とgate化せず（channel-exercise summaryは非gate、emergent traversal validationは引き続きdefer）。
stimulusのtoward-tuning禁止（`_FAKE_REAL_DESTINATIONS`はitineraryに従わせない設計で、これを模範として
real modeもwaypoint観測を注入するのみで応答を強制しない）。organ6ファイル+`two_phase_live.py`の firing
witness+`memory/embedding.py`+`inference/ollama_adapter.py`はread-only再利用のみ。think=false
（`ThinkOffChatClient`経由、real_capture内で`run_traversal_capture`のThinkOffChatClientラップに従う）。
GPL importなし。既存golden回帰ゼロ。

### blocker
**I4-G1実行ゲートにより real 実走は BLOCKED**（user spend ratify未取得）。code pathは全AC緑
（I4-G2完了、I4-G3/G4/G5は実走発生時に事後検証、G4のnon-gate設計自体は実装済み確認済み）。
organ改変は不要だった。

### 追記（code-review MEDIUM 1 + LOW 2 反映、forward-risk 修正）
- **M-1（重要・完結実装、loud-failでなく）**: `EmbeddingRecordReplayClient.embed_many` を実装。
  `memory.embedding.EmbeddingClient`の公開surface（`embed`/`embed_query`/`embed_document`/`embed_many`）を
  完結（従来欠落=`cognition/cycle.py:1170`のM11-A coherence pathが呼ぶが、traversal経路は
  individual_layer無効ゆえinert・**未テスト**で将来real spend中のAttributeError riskがあった）。
  record modeは**batch全体で1回**inner呼出（実HTTP round-tripと一致、`inner_invocations`は1回のみ増分）
  しつつtext毎に1件`RecordedEmbeddingCall`を記録（replayが同数のstream slotを消費、既存`embed_query`等の
  position-based sequencing と一貫）。**新規test** `test_embedding_record_replay_client_embed_many_record_then_replay`
  を追加（3textのbatch record→replay、`inner_invocations==1`(record)/`==0`(replay)、DOC_PREFIX込みの
  vector一致、exhaustion時`EmbeddingReplayError`を確認）。
- **LOW-1**: `experiments/20260723-aha-traversal-real/run.ps1`に`--seed 0`明示追加。`env.md`実走環境節に
  「seed: 0（`run_traversal_capture`/`real_capture`の既定値と一致・偶然でなくpre-register完全化）」を記載。
- **LOW-2**: `run.ps1`/`repro.ps1`冒頭に`$env:PYTHONUTF8 = "1"`、`repro.sh`冒頭に`export PYTHONUTF8=1`を追加
  （env.mdがWindows native + PYTHONUTF8=1を宣言していたのにscaffold側が未設定だった齟齬を解消）。`env.md`
  にも明記。
- スキップ: LOW-3（replay時のkind/text照合追加）は指示通り未対応（既存`RecordReplayChatClient`と同じ
  純位置ベース作法でprecedent一貫、geometry checksumで最終捕捉）。

**再検証**: `pytest -v tests/test_integration/test_traversal_live.py` = **21 passed**（既存20 +
embed_many test 1件追加）。`pytest -q test_integration -k golden` = 41 passed（既存golden回帰ゼロ、
I1-I3 byte-identity維持）。`ruff format --check src tests`緑（568 files）/ `ruff check src tests`緑 /
`mypy src`緑（244 files）。organ 6ファイル + `two_phase_live.py` + `live_v1.py` + `live.py` +
`memory/embedding.py` + `inference/ollama_adapter.py`の`git diff --stat` = 空。**real Ollama は本ラウンドでも
一度も起動していない**（`--real --capture`/`--verify`実行なし、`nvidia-smi`等も未実行、mock化unit testのみ実行）。

**全4 issue（I1-I4）完了**: I1（traversal driver core）/ I2（W2/W3 firing witness）/ I3（committed golden +
W4 fidelity anchor、WSL byte-parity実測はblocker=byte-parity-ready状態で持ち越し）/ I4（real qwen3 + real
embedding channel exercise、code pathのみland・real実走はI4-G1ゲートでblocked）。organ 6ファイル
（loop.py/cycle.py/handoff.py/two_phase.py/locomotion_sampling.py/embodiment.py/geometry.py）は
4 issue通して一貫して無改変。

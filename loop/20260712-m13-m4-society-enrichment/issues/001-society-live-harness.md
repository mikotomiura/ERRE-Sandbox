# Issue 001 (I1): society_live.py — N-agent live-capture harness（society.py 無改変）
verify_level: recheck   # AC1 record→replay byte-parity + inner_invocations==0 = 再現性契約直結

## Goal
ECL v0 `live.py::run_live_capture`(N=1) を **society scope に 1:1 mirror** した新規
`src/erre_sandbox/integration/embodied/society_live.py` を実装する。各 agent の inner を
`RecordReplayChatClient(inner=ThinkOffChatClient(inner_chats[aid]))` で包み `llms` mapping を構築 →
`run_society_loop`（society.py:861、**無改変**）を駆動。Ollama-free（`_ScriptedInner` mock）で
3 agent を実駆動し record→replay byte-parity + 全 client `inner_invocations==0` を test で証明する。

## Background
FROZEN design-final §A（mirror table）/ §F（determinism）。ECL track が払った determinism 保証
（byte-parity / inner_invocations==0 / WSL parity / Codex HIGH 反映）が 1:1 転移。
`society.py::run_society_loop` は既に `llms: Mapping[str, RecordReplayChatClient]` /
`agent_states` / `personas` / `observation_factories` を受け、seed 固定・sorted 逐次
cognition（no asyncio.gather）・reflection_disabled 済。`ThinkOffChatClient`（live.py:124）は
agent 数非依存 → **import して verbatim 再利用**。

## Scope
### In
- 新規 `src/erre_sandbox/integration/embodied/society_live.py`（`live.py` peer、`integration/embodied/` 同層）:
  - `run_society_live_capture(*, inner_chats: Mapping[str, Any], store, embedding, run_id, agent_states,
    personas, retrieval_now, base_ts, seed=0, n_cognition_ticks=SOCIETY_LIVE_N_COGNITION_TICKS,
    physics_ticks_per_cognition, k_ecl, reflector=None, observation_factories=None) -> SocietyRunResult`:
    各 agent 分 `RecordReplayChatClient(inner=ThinkOffChatClient(inner_chats[aid]))` を dict comprehension で
    構築 → `run_society_loop` を無改変で駆動して返す。
  - **凍結定数** `SOCIETY_LIVE_N_COGNITION_TICKS: Final[int] = 12`（golden の 4 より長い、sealed 前固定）。
  - `build_society_live_env_pins(...)`（model digest / think:false / uv.lock hash / VRAM、
    `build_live_env_pins` 同型を society 版に）。**HIGH-4/M2/M5**: 固定 constructor（agent_states/personas）+
    observation_factory の **canonical JSON fingerprint**、think/sampling/model digest/seed/horizon/run_id を
    env_pins に固定（verify が committed pins を assert できるよう）。
  - `SOCIETY_LIVE_OBSERVABLES`: 単一 agent O5(memory-centroid) を落とし **annotation 型 counter** を追加 =
    `O4_distinct_zones`（trace 全体 distinct zone 数）+ `O_multi_agent_speech`（各 agent ≥1 speech/animation）。
    両方 boolean/count annotation、gate でない、divergence/floor stat でない。**L3**: manifest 上は `annotations`
    配下に置き `verdict`/`passed`/`score`/`floor` key を使わない。`attach_society_live_observables(manifest)`。
  - **固定 agent_states/personas コンストラクタ**（decisions.md 判断2）: kant/nietzsche/rikyu の
    `AgentState`/`PersonaSpec` を import 時定数的に返す helper（`handoff.golden_agent_state`/`golden_persona` 同型）。
    agent_id = `a_kant`/`a_nietzsche`/`a_rikyu`（sorted で order_slot 0/1/2 安定）、初期 zone=study/peripatos/chashitsu。
  - **per-agent observation_factories** helper（各 agent が自分の初期 zone から知覚、`society._default_observation_factory`
    の STUDY ハードコードを per-agent 化。**legitimate nudge**、結果を捏造しない）。
  - scope-guard docstring を `live.py:42-48` から verbatim 複製（construction≠measurement）。
- 新規 `tests/test_integration/test_m4_society_live.py`（Ollama-free、`_ScriptedInner` mock）:
  - `_ScriptedInner`: `chat()` が固定 `ChatResponse`（LLMPlan JSON、think 検証込み）を返す mock。
  - record→replay byte-parity test（`run_society_live_capture` の result から `render_society_golden` →
    `replay_clients()` で replay → checksum/event_log_checksum 一致）。
  - 全 replay client `inner_invocations==0`。
  - **import-lint AST assert**（design §F）: `society_live.py` が `evidence`/`spdm`/`runningness` を import せず
    floor/verdict/scorer/divergence を emit しないことを AST で assert（後続 I2 の script も本 test で cover）。
### Out
- `--capture`/`--verify` CLI（I2）。viewer .tscn / replay test parametrize（I3）。real Ollama 実走（I4）。
  society.py / handoff.py の改変（無改変厳守）。

## Allowed Files
- `src/erre_sandbox/integration/embodied/society_live.py`（新規）
- `tests/test_integration/test_m4_society_live.py`（新規）
- **無改変厳守**: society.py / handoff.py / live.py / loop.py / EclReplayPlayer.gd / MainScene.tscn /
  既存 m2_society_golden / 凍結 evidence

## Acceptance Criteria（AC↔test）
- AC1-G1: `pytest tests/test_integration/test_m4_society_live.py::test_record_replay_byte_parity -q` = passed
  （3 agent record→replay で全成果物 byte 一致 + checksum + event_log_checksum 一致）。
- AC1-G2: `...::test_replay_no_inner_invocations` = passed（全 client `inner_invocations==0`）。
- AC1-G3: `...::test_think_off_forced` = passed（`ThinkOffChatClient` 経由で inner が think=False を受ける）。
- AC1-G4: `...::test_society_live_measurement_guard` = passed（`society_live.py` AST に denylist import/emit 非在）。
- AC1-G5: `...::test_observables_are_annotation` = passed（`SOCIETY_LIVE_OBSERVABLES` が定数文字列、統計計算コード非在）。
  **HIGH-6**: 本 test は observables の **存在・型・canonical rendering のみ** 検証。distinct_zone の値 ≥ N 等
  値ベースの pass/fail/threshold を assert しない（measurement 再入禁止）。
- AC1-G6: `...::test_fixed_constructors_fingerprint` = passed（agent_states/personas/observation_factory の
  canonical JSON fingerprint が決定的・byte 安定、env_pins に載る。HIGH-4/M2）。
- CI parity: `mypy src` 緑 + `ruff check`/`ruff format --check` 緑。

## Test Plan
`_ScriptedInner` mock で 3 agent（kant/nietzsche/rikyu）を `run_society_live_capture` 実駆動。
result → `render_society_golden` → tmp write → 再 replay（`result.replay_clients()` or from-rendered）→ byte 一致。
`inner_invocations` は各 `RecordReplayChatClient` の属性で検証。AST guard は `ast.parse` で import/Call を走査。

## Stop Conditions
- 全 AC 緑（Done）。
- society.py を改変しないと N-agent llms を渡せない → Stop（run_society_loop は既に Mapping を受ける、改変不要）。
- observables に統計計算を書きたくなる → Stop（annotation 厳守、measurement 再入）。
- 固定 persona が zone-pick を駆動する疑い → blockers.md（legitimate nudge の範囲か判定）。
- HOW 越え → Stop → superseding ADR。budget 到達 → Stop。

## Dependencies
- なし（`live.py`/`society.py`/`handoff.py` は committed、read-only 消費）。I2 が本 harness を CLI 化。

## Status
done

## Execution Result
実装完了（2026-07-12）。

- 新規 `src/erre_sandbox/integration/embodied/society_live.py`:
  - `run_society_live_capture`（`inner_chats` mapping → 各 agent
    `RecordReplayChatClient(inner=ThinkOffChatClient(...))` を dict comprehension
    で構築 → `run_society_loop` を無改変で駆動）。
  - `SOCIETY_LIVE_N_COGNITION_TICKS=12`（凍結定数）/ `SOCIETY_LIVE_RUN_ID`。
  - 固定 agent_states/personas コンストラクタ（`society_live_agent_states`/
    `society_live_personas`、kant/nietzsche/rikyu、agent_id
    `a_kant`/`a_nietzsche`/`a_rikyu` で sorted 順が order_slot 0/1/2 と一致、
    初期 zone=study/peripatos/chashitsu）。
  - per-agent observation_factories（`society_live_observation_factory`、
    `society._default_observation_factory` の STUDY ハードコードを per-agent 化、
    legitimate nudge、`plan.destination_zone` は非改変）。
  - `fixed_constructor_fingerprint`（agent_states/personas/observation_factories
    の canonical JSON SHA-256、HIGH-4/M2）+ `build_society_live_env_pins`
    （model digest/think:false/seed/horizon/run_id/fingerprint を env_pins に固定、
    HIGH-4/M2/M5）。
  - `SOCIETY_LIVE_OBSERVABLES`（O1-O3b 継承 + `O4_distinct_zones`/
    `O_multi_agent_speech` annotation、値は凍結文字列リテラルのみ、統計計算コード非在）
    + `attach_society_live_observables`（manifest `annotations` key、
    `verdict`/`passed`/`score`/`floor` 非使用、L3）。
  - scope-guard docstring を `live.py` から verbatim 複製（construction≠measurement）。
- 新規 `tests/test_integration/test_m4_society_live.py`（7 test、全緑）:
  AC1-G1 `test_record_replay_byte_parity` / AC1-G2
  `test_replay_no_inner_invocations` / AC1-G3 `test_think_off_forced` /
  AC1-G4 `test_society_live_measurement_guard` / AC1-G5
  `test_observables_are_annotation` / AC1-G6
  `test_fixed_constructors_fingerprint` + sanity
  `test_society_live_capture_drives_every_agent`。
- Codex HIGH-4/M2/M5/L3 反映済（本 issue スコープ分）。HIGH-1/2/3/5/M1/M3/M4/L1/L2
  は I2/I3/I4 スコープ（本 issue 対象外）。
- society.py / handoff.py / live.py / loop.py / .gd / .tscn / 既存 golden は無改変
  （git diff で確認済）。
- CI parity: `pytest tests/test_integration/test_m4_society_live.py -q` = 7
  passed。`pytest tests/test_integration -q` = 505 passed, 3 skipped(Godot
  未導入、既存)。`mypy src` = no issues (240 files)。`ruff check`/
  `ruff format --check`（対象2ファイル）= 緑。
- Stop 条件は発火せず（society.py 改変不要で駆動できた、observables は annotation
  のまま、固定 persona は zone-pick を駆動しない設計）。

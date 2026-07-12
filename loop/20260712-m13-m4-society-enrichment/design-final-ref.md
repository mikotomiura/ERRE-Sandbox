# design-final — M4 society run enrichment（FROZEN 2026-07-12）

> **status = FROZEN**（Plan mode + /reimagine 独立2案収束 + user 承認済 2026-07-12）。
> HOW はこの文書が SSOT。実装中に HOW を再交渉しない（変更が要れば superseding ADR）。
> plan 原本 = `C:\Users\johnd\.claude\plans\typed-finding-valley.md`（本文書はその committed コピー）。

## Context（なぜ）

M13 建設 pivot の可視化 substrate（M4、PR #75 = MERGED main 6a439a3）は landed したが、可視化が物足りない**根本原因は golden が薄い**こと: 現 `tests/fixtures/m2_society_golden/` は **2 agent・全 tick zone=peripatos・scripted plan(destination_zone 固定)** の最小 fixture で agent が 1 zone でほぼ動かない。M4 viewer(`SocietyReplayViewer.gd`) 本体は既に N-agent/複数 zone 対応済で、壁は golden の中身・scene の avatar ノード数・test の定数だけ。

本タスク = **N agent(3、persona=kant/nietzsche/rikyu)が複数 zone を実際に移動・会話する society run を real qwen3:8b sealed capture(record-mode, think=False)で封印記録** → 新 golden を作り viewer で可視化 + headless placement 検証。**construction であって measurement でない**（verdict/scorer/floor/D_*/family comparison を作らない、R-budget=0、measurement line は CLOSE 済で再入しない）。zone をまたぐ移動は real LLM に **genuine に選ばせ**、起きなければ honest に single-zone 報告（scripted で捏造しない）。

**設計方針の要**: ECL v0 live-capture(N=1)を **society scope に 1:1 mirror**。ECL track が既に払った determinism 保証（byte-parity / `inner_invocations==0` / manifest 再 render witness / WSL parity / Codex HIGH 反映）が無償転移し、read-only driver(`run_society_loop`/`render_society_golden`)が必要な injection seam を既に露出。独立2案（一次案 + Plan エージェント from-scratch 案）が同一アーキテクチャに収束、Plan 案の精緻化を採用。

**user 裁定（2026-07-12）**: (1) PR #75 merge 済（main 6a439a3）。(2) real qwen3:8b 実走承認（実装 spend、honest outcome 受容）。

## 実装対象（ECL live-capture の society peer、mirror table）

| ECL v0（既存・無改変） | Society（新設） |
|---|---|
| `live.py::run_live_capture` | `society_live.py::run_society_live_capture`（新関数） |
| `live.py::ThinkOffChatClient` | **import して verbatim 再利用**（agent 数非依存） |
| `live.py::build_live_env_pins`/`attach_live_observables` | `society_live.py::build_society_live_env_pins`/`attach_society_live_observables` |
| `run_ecl_loop`（driver, read-only） | `run_society_loop`（driver, read-only, society.py:861） |
| `render_golden` | `render_society_golden`（read-only, handoff.py:978） |
| `scripts/ecl_v0_live_capture.py`（`--capture`/`--verify`） | `scripts/m4_society_live_capture.py`（design-copy, not import） |

### A. society-level live-capture harness（新 `src/erre_sandbox/integration/embodied/society_live.py`、society.py 無改変）

- `run_society_live_capture(*, inner_chats: Mapping[str, Any], store, embedding, run_id, agent_states, personas, retrieval_now, base_ts, seed=0, n_cognition_ticks=SOCIETY_LIVE_N_COGNITION_TICKS, physics_ticks_per_cognition, k_ecl, reflector=None, observation_factories=None) -> SocietyRunResult`:
  各 agent の inner を `RecordReplayChatClient(inner=ThinkOffChatClient(inner_chats[aid]))` で包み `llms` mapping を構築 → `run_society_loop` を **無改変で駆動**。`run_ecl_loop`→`run_society_loop`、単一 client→dict comprehension 化するだけ（society.py は既に `llms: Mapping[str, RecordReplayChatClient]` を受ける）。
- observables overlay は society 版に: 単一 agent O5(memory-centroid) を落とし **annotation 型 counter** を追加 = `O4_distinct_zones`（trace 全体 distinct zone 数、既存 `LIVE_OBSERVABLES` O4 踏襲）+ `O_multi_agent_speech`（各 agent ≥1 speech/animation）。**両方 boolean/count annotation、gate でない、divergence/floor stat でない**。
- scope-guard docstring を `live.py:42-48` から verbatim 複製。

### B. bake/verify CLI（新 `scripts/m4_society_live_capture.py`、design-copy）

- `--capture`（G-GEAR, real Ollama）: 各 agent 分 `OllamaChatClient(model="qwen3:8b")` を **遅延 import**（import 副作用なし）+ 共有 constant-vector mock embedding（action-LLM のみ live）→ `run_society_live_capture` → `render_society_golden(result, run_config, env_pins)` + `attach_society_live_observables` → 4 成果物を新 fixture dir へ + `build_expected_placement` で `expected_placement.jsonl` 導出。
- `--verify`（Ollama-free, CI/WSL 可）: committed `decisions.jsonl` から replay、**全 agent client で `inner_invocations==0`**、`replay_checksum` 一致、全成果物 SHA-256、**manifest 自身の再 render byte 一致**（committed env_pins/run block 再利用、fresh capture しない = Codex HIGH-1 anti-vacuous-pass）。
- **R3 既知ギャップ（確認済）**: `handoff.recorded_calls_from_jsonl`(handoff.py:585) は単一 agent 用。**society の from-jsonl per-agent decoder は不在**（`SocietyRunResult.replay_clients()` society.py:792 は in-memory result からのみ）。→ `--verify` 用に **agent_id/order_slot でグルーピングして per-agent recorded call を復元する純 helper を script 内に新設**（`society_decisions_to_jsonl` handoff.py:766 の逆、handoff.py 無改変）。I2 中核。

### C. run 設計（honest な zone 移動、scripted しない）

| agent_id | persona | 初期 zone | observation source_zone |
|---|---|---|---|
| `a_kant` | kant | STUDY | STUDY |
| `a_nietzsche` | nietzsche | PERIPATOS | PERIPATOS |
| `a_rikyu` | rikyu | CHASHITSU | CHASHITSU |

- agent_id は `sorted` で order_slot 0/1/2 が安定かつ人間可読になるよう命名。
- **legitimate nudge（結果を捏造しない）**: (1) 初期 zone 分散、(2) **per-agent `observation_factories`**（各 agent が自分の初期 zone から知覚 → resolver が genuine に agent 固有 memory geometry を読む＝load-bearing、`loop._default_observation_factory` の STUDY ハードコードを per-agent 化）、(3) persona 事前分布（peripatetic Nietzsche / chashitsu Rikyu）、(4) horizon `SOCIETY_LIVE_N_COGNITION_TICKS=12`（golden の 4 より長い、sealed 前に凍結）。
- **禁止**: plan に `destination_zone` を注入（scripted `_PLAN_JSON` 捏造）。`plan.destination_zone`（cycle.py:1394 が読む唯一の駆動源）は完全に LLM authored のまま。
- **honest single-zone fallback = first-class pass**: think=False で 3 agent が初期 zone に留まっても、per-tick `plan.destination_zone` と resolver `resolved_from` を dump し「LLM が別 zone を選ばなかった／選んだが resolver 到達不能」を診断報告。distinct-zone は annotation ゆえ loop は toward-tune できない。

### D. 新 golden fixture

- `tests/fixtures/m4_society_live_golden/`（`run_id="m4-society-live-golden"`, `seed=0`）に manifest/ecl_trace/decisions/envelope_stream + `expected_placement.jsonl`。**既存 m2_society_golden は無改変で共存**。`build_expected_placement(trace,stream)`(test_m4_society_replay.py:85) は fixture 非依存で新 trace/stream に向けるだけ。

### E. viewer 2 箇所の壁（EclReplayPlayer.gd / MainScene.tscn 無改変）

- **headless dump 経路は scene を instantiate しない**（SocietyReplayViewer.gd:103-112）→ 機械 witness(AC4)は N=3 で **.gd/.tscn 無改変で既に成立**。壁は interactive scene と test 定数のみ。
- (a) `godot_project/scenes/dev/SocietyReplayScene.tscn` に **静的 `Avatar2` ノードを 1 個追加**（Avatar0/1 ブロック L40-45 を mirror、`AgentAvatar.tscn` ext_resource `7_avatar` 再利用、`load_steps` 据置）。静的にする根拠 = viewer は `get_node_or_null("Avatar%d" % slot)`(L293) で解決し欠落 slot は skip、scene を committed/inspectable な artifact に保つ、dev-only で byte witness でないため determinism 影響ゼロ。
- (b) `tests/test_integration/test_m4_society_replay.py` を **parametrize**（fork せず）: `_GOLDEN_DIR` + 行数定数(L69 `=40`/L70 `=16`) + slot 集合(L205-208 `[0,1]`) を golden 毎レコード `(golden_dir, n_agents, expected_placement_rows, expected_envelope_rows, expected_slots)` に置換、row 数は `n_agents × physics × cognition` から導出、`slots == list(range(n_agents))`。4 つの `@pytest.mark.godot` test を `[m2(N=2), m4(N=3)]` で parametrize。`canonical_dumps`/`build_expected_placement`/`resolve_godot`/viewer CLI は無改修再利用。

### F. determinism / reproducibility（binding）

- record→replay byte 一致（6桁量子化 `handoff.canonical_dumps` handoff.py:373、WSL byte parity 実測、memory `feedback_golden_crossplatform_float_drift`）。
- env_pins = `build_society_live_env_pins`（model digest / think:false / uv.lock hash / VRAM）。seed 固定・named RNG substream・sorted 逐次 cognition(no asyncio.gather)・reflection_disabled 維持。
- **construction≠measurement**: fp/placement/checksum は再現性 witness であって metric でない。新 .py/.gd/CLI が `evidence`/`spdm`/`runningness` を import せず floor/verdict/scorer/divergence を emit しない（guard `test_m4_viz_measurement_guard.py` が glob 自動追随 + I1/I2 test に import-lint AST assert 追加）。R-budget=0 不変。§D0.2 非反射条項遵守。

## 実行方式 — Loop Engineering（real capture は非 Loop の G-GEAR sealed 一発）

大半（harness/CLI-verify/viewer/test）は Ollama-free & TDD 可能 → worktree `/loop-issue`。real `--capture` のみ VRAM 依存・非再現・一発ゆえ Loop 外（ECL v0 Issue 003 posture）。grill 1 pass = tick budget vs think=False での zone-move 確率（唯一 crisp でない Done/Stop）。

**縦スライス issue（各 = 1 worktree = 1 PR 候補）、DAG `{I1,I2,I3}→I4→I5`**:
- **I1** — `society_live.py`（harness + overlay + `ThinkOffChatClient` 再利用）+ Ollama-free test（`_ScriptedInner` mock で 3 agent を `run_society_loop` 実駆動、record→replay byte-parity + `inner_invocations==0`）。
- **I2** — `scripts/m4_society_live_capture.py`（`--verify` を mock-captured bundle で完全 test、**R3 の per-agent from-jsonl decoder 実装**）。`--capture` の live 分岐は import-lazy・here-untested。
- **I3** — viewer `.tscn` `Avatar2` + `test_m4_society_replay.py` parametrize。**先に既存 m2 golden が新 parametrize 形で全緑**（m4 golden 生成前に回帰ゼロ証明）。
- **I4（非 Loop, human-run）** — G-GEAR Windows-native Ollama で `python scripts/m4_society_live_capture.py --capture --n-cognition-ticks 12 ...`（`& disown` + completion-marker tail）。4 成果物 + `expected_placement.jsonl` commit → `--verify` + parametrized godot test local → multi-zone-or-honest-single-zone 報告。
- **I5** — WSL byte-parity（`--verify` は Ollama-free ゆえ WSL 可）+ pre-push 4段緑。

## acceptance（boolean のみ、verdict なし）

1. 新 golden が record→replay で byte 一致再生。
2. ecl_trace に複数 distinct zone 出現（or honest single-zone 報告 + 機序診断）。
3. envelope_stream に N agent 分 speech/animation。
4. viewer headless dump → placement byte 一致（既存 I6 同型を新 golden に）。
5. pre-push 4段緑 + WSL byte parity。

## リスク（順位付き）

- **R1（最高）think=False で zone 移動が起きない**: single-agent 知見「think=False が load-bearing」。§C 4 nudge で緩和、honest single-zone 報告が first-class pass、distinct-zone は annotation ゆえ toward-tune 不可。scripted 強制禁止。
- **R2 cross-platform byte drift**: 6桁量子化 `canonical_dumps` + WSL 実測で吸収。
- **R3 society from-jsonl replay decoder 不在（確認済）**: script 内に per-agent grouping decoder 新設（handoff.py 無改変）。I2 中核。
- **R4 measurement-guard leakage**: scope-guard docstring 複製 + import-lint AST assert。observables は凍結 annotation 文字列、統計を計算しない。
- **R5 GPL/layer**: bpy 不使用、Godot は GDScript、`society_live.py` は `integration/embodied/` 同層（`live.py` peer、既に `inference.ollama_adapter` import）。新規依存なし。architecture-rules Skill 参照。
- **R6 read-only 違反**: society.py/handoff.py/EclReplayPlayer.gd/MainScene.tscn/既存 m2 golden/凍結 evidence 全て無改変。編集は新 3 ファイル + fixture dir + .tscn に 1 ノード append + test 1 module parametrize のみ。
- **R7 G-GEAR/WSL topology**: `--capture` は Windows-native Ollama（WSL2 不通）、`--verify` は Ollama-free で WSL 可（R2 cross-platform check を executable にする）。

## 検証（end-to-end）

- `--verify`（Ollama-free replay byte 一致）。`pytest tests/test_integration/test_m4_society_replay.py`（新 golden parametrize）+ `test_m4_society_live.py`。
- pre-push CI parity 4段（ruff format --check / ruff check / mypy src / pytest -q）+ WSL byte parity 実測。
- viewer interactive で N agent が複数 zone を歩き会話するのを目視確認。

## 完了後

新 golden landed + viewer 可視化確認 + memory 新規（`project_m4_society_enrichment`、親 `project_m13_m4_code`）+ docs/research-positioning §8 追記。次工程候補 = fidelity Wave 2(CC0 humanoid/HDRI、要 network DL 承認) / M2 Layer2 mirror-sim ADR。

## 事前登録の凍結定数（sealed run 前固定、tune-to-pass 封鎖）

`SOCIETY_LIVE_N_COGNITION_TICKS=12` / `seed=0` / 3 agent(kant/nietzsche/rikyu) / 初期 zone=study/peripatos/chashitsu / `run_id="m4-society-live-golden"` / think=False / model=qwen3:8b。sealed run 後の変更は Stop 条件。

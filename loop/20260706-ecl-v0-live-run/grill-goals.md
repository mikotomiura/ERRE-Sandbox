# grill 成果物 — M13 Phase 1 sealed live run 検証可能ゴール

> grilling skill (`.claude/skills/grilling`) 実起動の出力。main checkout (773d02e) 上・タスクにつき 1 回。
> 入力 = FROZEN ADR (`.steering/20260706-m13-forward-primary/design-final.md`、§FROZEN binding a-e、O1-O5)。
> **設計は Phase 0 で凍結済ゆえ grill の主眼 = 各観測量を named test = exit-code 緑に落とす + sealed run の
> 事前登録定数を tune-to-pass 不能な形で固定する**。

## 終了条件の充足 (軸1 = grill 被覆分岐 = No)

- **ユーザー判断を要する未解決の判断分岐 = 0 件**。FROZEN ADR + Codex Adopt-with-changes が設計分岐を全解消
  (候補 A / ThinkOffChatClient wrapper / embedding mock / experiments 配置 / O1-O5 / Done⇔annotation 分離)。
- 下記 実装レベル残存曖昧点 (RG-1..8) は **全て FROZEN 設計意図内で決定** (D-1..8、ユーザー付託不要)。
- → **軸1 = No (ADR 未被覆 fork なし)** → superseding ADR 不要、issue-slicing 直行。
- 曖昧語: `first-contact` / `minimal reality surface` / `channel-exercise annotation` を本 grill で glossary
  候補として pin (measurement 用語ではないことを明記)。

## 実装レベル残存曖昧点 → FROZEN 設計意図内で決定 (decisions.md D-1..8)

- **RG-1 sealed run の horizon N**: ADR「例 32、pre-register」→ **D-1: N_cognition=32** (golden の 8 より長尺、
  32×20=640 physics row で committed artifact も過大でない、construction「longer horizon 安定完走」観測)。
  sealed run 前に固定、run 後の tune 禁止。
- **RG-2 persona/agent**: golden = kant (`GOLDEN_PERSONA_ID`)。→ **D-2: persona=kant, 単一 agent** (最小、golden
  と同一で差分最小)。
- **RG-3 sampling**: cycle が persona+ERRE mode から compose、`decisions.jsonl` が `ResolvedSampling` を既に記録。
  → **D-3: manual override せず live cycle の resolved sampling を verbatim 記録** (think のみ wrapper で False 強制)。
- **RG-4 embedding**: ADR §DA-FWD-2 = mock 維持。→ **D-4: live capture も `_offline_embedding` 相当の
  constant-vector mock を使用** (live なのは action LLM chat のみ、retrieval は実 memory 蓄積+実 centroid 幾何、
  類似度だけ mock = minimal reality surface)。real nomic-embed-text は使わない。
- **RG-5 O5 threshold**: first-contact の存在証明ゆえ **D-5: O5 = ≥1 tick で `llm_status=="ok"` ∧
  `plan is not None` ∧ MoveMsg `resolved_from=="memory_centroid"` (parsed destination_zone が履歴依存 move を駆動)**。
  実際の成功 tick 数は annotation として honest 記録 (分布は測らない=measurement 非再入)。0 なら construction
  妥当性 branch (軸5)。閾値は sealed run 前に固定 (tune-to-pass 封鎖)。
- **RG-6 O3a/O3b の cross-platform 検証機構**: **D-6**: (a) CI test = committed artifact を replay → committed
  checksum 一致 + inner_invocations==0 (O3a) / raw Plane2 → artifact re-render SHA 一致 (O3b) — platform 非依存
  assertion。(b) cross-platform equality は **I3 実行時に WSL Linux vs Windows で committed artifact の byte 一致を
  手動実測** (feedback_golden_crossplatform_float_drift、env.md に記録)。PR #55 golden と同手順。
- **RG-7 harness = 新規 script**: **D-7**: 新規 `scripts/ecl_v0_live_capture.py` (run_ecl_loop + handoff serializer
  再利用、record mode で ThinkOffChatClient(OllamaChatClient) 注入)。synthetic `ecl_v0_golden.py` は無改変温存。
- **RG-8 committed live artifact の所在**: **D-8**: `experiments/<date>-ecl-v0-live-capture/artifacts/` に committed
  (experiments は CI lint 対象外だが pytest は読める)。I4 の replay-verify test は **tests/ 配下** (CI lint/type
  網羅) が experiments の artifact を読む。

## sequencing の決定的事実 (依存 I1→I3→I4)

- I1 (harness+ThinkOffChatClient) は mock inner で **live 非依存に test 可能** (think=False 転送を request-capture
  test で pin) → autonomous /loop-issue。
- I2 (protocol+env pin) は定数/serialization → autonomous /loop-issue。
- **I3 (sealed run) は I1 harness + I2 protocol の緑後に人手実行** (live qwen3:8b、think=False) → committed
  artifact + WSL byte 一致。loop-watchdog 非対象 (live Ollama 一発)。
- I4 (replay-verify) は **I3 の committed artifact に依存** → I3 後。ただし test logic は既存 synthetic golden を
  テンプレに先行実装可 (I3 後に live artifact へ差替え) → autonomous /loop-issue。

---

## Issue I1 = ThinkOffChatClient + live-capture harness [autonomous]
**verify_level = recheck (公開 API・AC 直結)**。live 非依存 (mock inner)。

| ID | Done = named test 緑 | 失敗モード (fix 前) |
|---|---|---|
| I1-G1 | `test_think_off_chat_client_forces_think_false` — mock inner に `think=False` が渡ることを request-capture で pin (cycle が think 未 pass でも wrapper が上書き、Codex HIGH-1) | wrapper 無 → think=None 転送 → qwen3 `<think>` に budget→空 content→parse 全失敗 |
| I1-G2 | `test_think_off_chat_client_passthrough` — messages/sampling/model/options は inner へ無改変転送、ChatResponse 素通し | wrapper が他引数を壊す |
| I1-G3 | `test_live_capture_harness_records_with_mock_inner` — `RecordReplayChatClient(inner=ThinkOffChatClient(mock))` を record mode で `run_ecl_loop` 駆動 → captured decisions 完全 + trace + checksum 生成 (mock で live 非依存) | harness が record mode で captured Plane2 を組めない |
| I1-G4 | `test_live_capture_replay_roundtrip_mock` — captured decisions のみ replay → checksum byte 一致 + inner_invocations==0 (record→replay 等価を mock で先行実証) | — (回帰固定) |
| I1-G5 | 既存 `test_ecl_flag_off_byte_invariant` + ECL replay test 群 緑維持 (loop.py/cycle.py/world 無改変) | (回帰防止) |

- **Stop**: harness が既存 loop.py/cycle.py/world/tick.py/handoff.py の改変を要する → Stop (ADR binding「既存 seam
  無改変」逸脱、superseding ADR)。
- **Out**: live Ollama 実走 (I3); committed live artifact (I3); measurement 再入。

## Issue I2 = sealed protocol + env pin + manifest 拡張 [autonomous]
**verify_level = parse (config/serialization)**。

| ID | Done = named test 緑 | 失敗モード (fix 前) |
|---|---|---|
| I2-G1 | `test_live_capture_protocol_constants` — N_cognition==32 / persona=="kant" / seed / embedding=mock の pre-registered 定数が固定 (D-1..4) | 定数が run 時可変 = tune-to-pass 穴 |
| I2-G2 | `test_live_manifest_pins_env` — manifest に qwen3:8b digest / Ollama version / VRAM / uv.lock hash / think:false / resolved sampling 記録 (D-3、feedback_pre_push) | env 未 pin = 非再現 |
| I2-G3 | `test_live_manifest_observables_preregistered` — manifest/doc に O1-O5 + Done=O1∧O2∧O3a∧O3b + O5 閾値(≥1) が sealed run 前定数として存在 (D-5) | 観測量が run 後定義 = tune-to-pass |
| I2-G4 | `test_live_capture_measurement_guard` — capture script が evidence/spdm/runningness を import せず floor/landscape/verdict identifier を出さない (holding、既存 guard pattern) | measurement 再入 |

- **Stop**: 観測量/閾値を sealed run 結果に合わせて緩める必要が出た → Stop (tune-to-pass、pre-registration 破り)。
- **Out**: sealed run 実走 (I3); replay-verify test 本体 (I4)。

## Issue I3 = sealed live run + committed artifact [MANUAL sealed gate — loop 外]
**verify = replay-verify gate (I4 test 緑) + WSL cross-platform byte 一致**。autonomous 対象外 (live Ollama 一発)。

| ID | Done | 失敗モード |
|---|---|---|
| I3-G1 | G-GEAR で Ollama 起動 (qwen3:8b, think=False) → I1 harness を live 実走 (N=32) → **例外なく完走 (O1)** | live 実走が crash (α hardening の raised fallback で堅牢のはず) |
| I3-G2 | captured Plane2/trace/manifest を `experiments/20260706-ecl-v0-live-capture/artifacts/` へ committed (6桁量子化) + run.sh/repro.sh/env.md/ollama.log | serialize 漏れ・量子化漏れ (envelope_provenance embedded JSON float) |
| I3-G3 | committed decisions のみ replay → checksum byte 一致 + inner_invocations==0 (**O2**) | replay 非決定 → **Stop→superseding hardening (軸5)** |
| I3-G4 | **WSL Linux (glibc) で committed artifact が Windows (UCRT) と byte 一致** (O3a/O3b cross-platform、D-6) | float drift → **Stop (量子化漏れ特定、軸6)** |
| I3-G5 | **O5 ≥1 tick** で `llm_status=="ok"`∧`plan≠None`∧`resolved_from=="memory_centroid"` (annotation: 成功 tick 数記録) + **O4 非縮退** (distinct zone>1 or move target>1、annotation) | O5==0/O4 縮退 → **construction 妥当性 branch (軸5、think=False 経路 or persona)** |

- **Stop (軸5)**: replay 非決定/crash → superseding hardening ADR (Plan+Codex)。
- **branch (軸5)**: O5==0 (全 unparseable) or O4 縮退 → construction 妥当性 branch (reproducibility Done は満たすが
  organ が channel 未 exercise、measurement 非再入)。
- **Out**: N体化 (B); measurement (C); Godot 可視化 (Milestone 4)。

## Issue I4 = Ollama-free replay-verify + cross-platform O3a/O3b + O5 test [autonomous]
**verify_level = recheck (AC 直結・reproduction 契約)**。I3 committed artifact 依存 (test logic は synthetic golden で先行)。

| ID | Done = named test 緑 | 失敗モード (fix 前) |
|---|---|---|
| I4-G1 | `test_live_golden_replay_checksum_matches` — committed `experiments/.../decisions.jsonl` のみ replay → committed manifest checksum 一致 + inner_invocations==0 (**O3a**、Ollama-free、CI) | replay が committed に一致しない = 非再現 |
| I4-G2 | `test_live_golden_artifact_rerender_sha` — 同一 raw Plane2 → full artifact re-render SHA が committed と一致 (**O3b**、6桁量子化が float drift 吸収) | re-render 非決定 |
| I4-G3 | `test_live_golden_parsed_action_path` — committed decisions に **O5** (≥1 tick で llm_status==ok∧plan≠None∧MoveMsg resolved_from==memory_centroid) が成立 (first-contact 存在証明、D-5) | unparseable-only を見逃す (空洞 claim) |
| I4-G4 | `test_live_golden_measurement_guard` — I4 test が floor/landscape/verdict を計算・出力しない (O4/O5 は boolean/counting annotation のみ、holding) | measurement 再入 |
| I4-G5 | `bash experiments/20260706-ecl-v0-live-capture/repro.sh` exit 0 (1 コマンド Ollama-free 再現、Codex TASK-PRE LOW-1: bash に統一) | repro 契約破れ |

- **Stop**: replay-verify が committed artifact に一致しない (I3 の非決定) → Stop→superseding hardening (軸5)。
- **Out**: measurement 再入; live re-capture の cross-platform byte 一致要求 (Codex HIGH-2: 非要求)。

---

## verify コマンド (全 autonomous slice 共通の CI parity gate)
- `bash scripts/dev/pre-push-check.sh` (WSL) / native は PowerShell 5.1 で `& scripts/dev/pre-push-check.ps1`
  の 4 段 (ruff format --check / ruff check / mypy src / pytest -q) 全 pass = 末尾 `ALL CHECKS PASSED`。
- wall-clock/乱数/dict 順序比較 test は clock/seed pin。experiments/ script 本体は CI 対象外ゆえ検証 logic は tests/。

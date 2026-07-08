# grill 成果物 — M13 B 反復 frozen-context bank 実コード実装 検証可能ゴール

> `grilling` skill (`.claude/skills/grilling`) 実起動の出力。main checkout (ec3979f) 上・タスクにつき 1 回。
> 入力 = FROZEN ADR (`.steering/20260707-m13-b-impl-design/design-final.md` §I0-§I11、PR #63、main=ec3979f)
> + decisions.md (DA-BIMPL-1..9) + Codex review (Verdict=Revise 全 HIGH 反映)。
> **設計は B impl-design ADR で凍結済ゆえ grill の主眼 = §I8 の I1-I6 各契約点を named test = exit-code 緑に
> 落とす + tune-to-pass 不能な pre-registration 定数を forking-paths seal で固定する**。
> **construction であって measurement でない**（floor/landscape/verdict/H/MDE/divergence 非計算、R-budget
> 未消費、holding 不可侵、実 spend の powered run は C-proper AUTHORIZE 後のみ）。

## 終了条件の充足（軸1 = grill 被覆分岐）

- **ユーザー判断を要する未解決の設計分岐 = 1 件のみ**（RG-10 live shakedown scope。ADR §I4 が「任意 sub-step」
  として明示的に開いている唯一の scope 分岐）。他の実装レベル残存曖昧点（RG-1..9）は **全て FROZEN 設計意図内で
  決定**（D-1..9、ユーザー付託不要）。
- → **軸1 = 実質 No**（ADR 未被覆の設計 fork なし、RG-10 は ADR が明示的に user 裁定へ委ねた scope 選択）→
  superseding ADR 不要、RG-10 を user へ確認後 issue-slicing 直行。
- 曖昧語: `bake-out` / `provenance pass` / `pre-bias readout` / `frozen-context bank` / `competing-destination
  cue` / `T3 materiality` を本 grill で `docs/glossary.md` に pin（measurement 用語でないことを明記）。

---

## 実装レベル残存曖昧点 → FROZEN 設計意図内で決定（decisions.md D-1..9）

### RG-1 bank module の配置 と no-organ-change 境界
ADR は「拡張/最小改変で pin、非改変厳守」を binding とするが実ファイル未定。
→ **D-1**: 新規 `src/erre_sandbox/integration/embodied/bank.py`（+ 補助 `bank_fixtures.py`）を追加。既存 organ
（`loop.py`/`cycle.py`/`prompting.py`/`embodiment.py`/`parse.py`/`handoff.py`/`world/tick.py`/`live.py`/
`live_v1.py`/committed golden）は **無改変**（`git diff` empty で test）。provenance pass は既存 `run_ecl_loop`
/`live.run_live_capture` を DI 再利用、record-M は `RecordReplayChatClient` を bank 軸へ wrapper 拡張
（`live_v1.SamplingSpyChatClient` の wrapper 先例に倣う、organ 行 0 変更）。

### RG-2 competing-destination cue の zone 集合・中立第三 zone・persona（forking-paths seal）
ADR §I1.1「Z_comp 2-3 zone に構造同型 observation + 中立 state tail（current=Z_comp 外第三 zone）+ 対称/空
preferred_zones」だが具体値未定。**collapse 観測後に切り直さない = forking-paths seal ゆえ実装時に literal 固定
必須**。
→ **D-2**: 以下を **module literal で pre-register**（result-independent、`test_bank_cue_constants_literal_pin`
が literal + no-`evidence`-import を assert、`ecl_v1.ECL_V1_LOCO_LAM0` の literal-pin 先例に倣う）:
  - `BANK_Z_COMP = (Zone.STUDY, Zone.GARDEN)`（2-zone 対称、3-zone 拡張余地。source-organic = persona が
    organic に選び得る destination 対）。
  - `BANK_NEUTRAL_ZONE = Zone.AGORA`（current/spawn = Z_comp 外第三 zone、erre mode 中立）。
  - fixture persona = 中立（`preferred_zones` 空、`model_validate` fixture 経由、`_bias_target_zone` の
    preferred confound を空で殺す）。
  - 各 z ∈ Z_comp に **構造同型**の affordance/zone_transition observation（同一 salience・同一個数・zone 名のみ
    差替え）+ content 鏡映 memory（`RankedMemory` 静的手構築、kind/strength/content 直接付与、retriever 非呼出）。

### RG-3 凍結 context（prompt, sampling）の生成 = provenance pass
ADR §I3.4(2-1)「enriched substrate → 器官 1 pass で prompt 生成 → 凍結（この 1 pass のみ EclDecisionRecord）」。
λ は prompt 非関与ゆえ prompt は T_on/T_off で byte 同一・sampling のみ 2 値（§I3.3）。
→ **D-3**: provenance pass = enriched substrate を **canonical builder**（`build_system_prompt`/
`build_user_prompt`、materiality criterion 1）で render する 1 full-cycle pass（`run_ecl_loop` 経由）。
capture = `(frozen_ctx_id, system_prompt, user_prompt, sampling_on, sampling_off)`。`sampling_on` =
locomotion `LocomotionState(lam=λ_ctx)` で cycle が compose した resolved sampling / `sampling_off` =
locomotion `None` の resolved sampling（両者で prompt byte 同一を `test_bank_frozen_string` が assert）。
`ERRE_ZONE_BIAS_P=0` を pin し provenance pass の EclDecisionRecord で `bias_fired is None` を assert。
`λ_ctx` は per-context module literal（result-independent）、ES-3 gains（0.3/0.1）は
`erre.locomotion_sampling` の production default を読む（`evidence.es3_locomotion` 非 import）。

### RG-4 bake-out M-loop + BankLlmCallRecord + pre-bias readout
ADR §I1.4/§I5。M-loop は full cycle を通らず凍結 (prompt, sampling) を chat() 直投入。
→ **D-4**: M-loop = 各 (frozen_ctx, condition∈{on,off}) に対し `llm.chat([SystemMsg(frozen_system),
UserMsg(frozen_user)], sampling=frozen_sampling)` を M 回。**readout = `parse_llm_plan(raw_response)
.destination_zone`**（direct parse = 構造的 pre-bias、M-loop は `_bias_target_zone` を呼ばない）。emit =
`BankLlmCallRecord{frozen_ctx_id, condition, mc_index, system_prompt, user_prompt, sampling, raw_response,
pre_bias_destination_zone}`（§I5 閉集合、`EclDecisionRecord` 非流用）。retrieve/store は M-loop 内で一切触れない
（retrieve-count=0 構造的）。`mc_index` = Plane2 record-M の label（新 Python RNG per-draw ゼロ、前件 = zone
bias off）。

### RG-5 bank record/replay + determinism（Plane2 record-M）
ADR §I5「RecordReplayChatClient を bank 軸へ拡張、全順序 tie-break を (order_slot, frozen_ctx_id, condition,
mc_index, seq) へ」。
→ **D-5**: M-loop は (frozen_ctx_id, condition, mc_index) を **sorted 全順序**で反復し `RecordReplayChatClient`
（既存、flat-ordered）へ順に chat()。record mode で `BankLlmCallRecord` 列を捕捉、replay mode で同順に再供給
→ `inner_invocations==0`・bank byte 一致（`test_bank_replay_roundtrip`）。全順序 tie-break key を
serialization に固定（`handoff.py:576` の (order_slot, agent_tick, seq) 超集合）。**N=1 byte 不変**: `run_ecl_loop`
・committed golden は無改変ゆえ既存 checksum byte 不変（bank は別 driver、`test_ecl_flag_off_byte_invariant`
等 緑維持）。

### RG-6 spend ast-guard の scope（§I4、Codex HIGH-4）
既存 `tests/test_integration/_measurement_guard.py`（3-hole AST guard）を **superset 拡張**。
→ **D-6**: bank 専用 guard helper `tests/test_integration/_bank_spend_guard.py`（`_measurement_guard` を再利用
+ 追加 ban）が bank module（`bank.py`/`bank_fixtures.py`/annotation writer/`scripts/ecl_bank_*.py`）を scan:
  - 既存 ban（evidence/spdm/runningness/floor/landscape/verdict/divergence 等）継承。
  - **追加 ban（HIGH-4）**: `math.log` / `collections.Counter` / `set`(over zones) / `itertools.groupby` /
    `numpy`/`pandas`/`scipy`/`statistics` の import + 呼出。
  - call cap（`max_llm_calls ≤ 2·M·K`、超過 fail-fast、`.codex/budget.json` 同型 cost ceiling）。
  - no-adaptive-topup（M/K は凍結 literal、annotation 非依存を AST assert）。
  - **power apparatus は別 module**（`bank.py` measurement path 外、assumed distribution のみで動く、bank driver
    が import しない・annotation side-file を読まない → guard 対象外だが `test_bank_power_isolated_from_annotation`
    が独立を assert）。

### RG-7 power apparatus + power worksheet（§I6、DA-BIMPL-6）
ADR: 数値は非 binding proposal、power worksheet を FROZEN 条件化。
→ **D-7**: power worksheet = doc `experiments/20260708-m13-b-bank/power_worksheet.md`（+ 任意 script
`scripts/bank_power_worksheet.py`、**assumed base distribution のみ**で a-priori MDE 計算 = ES-4 Phase 0 型、
bank annotation を読まない）。worksheet が明記する必須項目: **検定法**（categorical 5-way multinomial power）/
**最悪・代表 base distribution**（H(zone|ctx)≈0 collapse を含む worst-case）/ **K context の pooling 仮定**。
named 閾値（M_min/K/δ_min/H_min/ρ）を proposal（M_min≥300, K≥8, δ_min=0.10 TV, power≥0.8, H_min=0.5bit,
ρ=0.5）から worksheet 出力として確定。**(i) H_min/ρ は empirical gate 目標であって B の保証でない**（未達→
line-close）。**ratification gate**: worksheet 出力 named 値を Codex/user が ratify（DA-BIMPL-6）してから FROZEN。

### RG-8 annotation side-file format + schema version bump
→ **D-8**: side-file = JSONL raw row `{frozen_ctx_id, condition, mc_index, pre_bias_destination_zone,
resolved_from}`（§I4、checksum 外、opaque、独自 `BANK_ANNOTATION_SCHEMA_VERSION`）。**B 側で H/MDE/divergence/
CI/verdict/floor/count/diversity を一切計算・assert しない**（`test_bank_annotation_opaque`）。
`MANIFEST_SCHEMA_VERSION`（`ecl-v0-handoff-2`）は無改変（handoff.py 無改変）、bank manifest overlay が独自
`bank_schema_version="ecl-bank-1"` を付与（`live_v1.attach_live_v1_observables` overlay 先例）。

### RG-9 continuity-gate 4 test + T3 materiality criterion test
ADR §I2/§I6/§I7。
→ **D-9**:
  - **continuity-gate**（4 機械 test、§I2）: (1) import-ban（allowlist 主 = bank module が import してよい閉集合
    列挙 + denylist 補助、`test_bank_import_allowlist`）/ (2) M-loop retrieve-count=0 + provenance pass 別監査
    （retrieve-count=1×K、`test_bank_mloop_retrieve_count_zero` / `test_bank_provenance_pass_uses_canonical_
    builder`）/ (3) arity=1 divergence-free（readout signature = per-context sample-list→scalar、measurement
    path に `*_divergence`/KL/JS/paired-distribution 非在を AST/grep assert、`test_bank_arity_one_divergence_
    free`）/ (4) frozen-string（各 context の chat() prompt が M pass 全体で byte-identical、`test_bank_frozen_
    string`）。
  - **T3 materiality**（§I7）: (a) canonical-inputs-only = fixture は observation/persona/AgentState/memory を
    `model_validate` 経由のみ編集・manual prompt string 非手書き（`test_bank_cue_canonical_inputs_only`）/
    (b) stimulus 判定 gate = **人手 desk-audit gate**（`experiments/.../t3_materiality_desk_audit.md` に
    provenance + criterion 1-3 の証跡 + 「stimulus と判定されたら T3 fail→line-close」の honest teeth を記録、
    user/reviewer sign-off。criterion 4 は機械 test 不能な human gate ゆえ doc 存在 + sign-off を
    `test_bank_t3_desk_audit_present` が確認）。

---

## RG-10（唯一の user 裁定分岐）= construction 検証 run に live shakedown を含めるか
ADR §I4 は「construction 検証 run = mock/schema-test 中心。live shakedown を **行う場合は** tiny M/K cap 凍結 +
sealed + 人手 gate + WSL byte 一致」と **明示的に任意**にしている。powered bank sampling run は C-proper
AUTHORIZE 後のみ（本タスク非対象）ゆえ、ここで問うのは「organ 導通を mock/schema-test だけで締めるか、tiny
non-powered live shakedown（real qwen3:8b、ECL v0/v1 first-contact 同型 sealed 一発）も足すか」。
→ **D-10（user 裁定 2026-07-08 = mock-only）**: construction 検証 run は **mock/schema-test + committed mock
golden replay のみ**で締める。live shakedown は **OUT/defer**（Ollama 不要）。organ 導通は mock record/replay
+ schema test で立証。powered bank sampling run は C-proper AUTHORIZE 後のみ（本タスク非対象）。stats 非計算・
verdict なし・raw row のみ・R-budget 未消費。I5 は Ollama 非依存の autonomous slice になる。

## 実行方式（user 裁定 2026-07-08）
= **subagent-per-issue で本セッション続行**（subagent spawn 明示承認済み、`feedback_subagent_delegation_
explicit_only`）。各 issue を fresh-context subagent (Sonnet) が実装 → test-runner + loop-watchdog で客観検証
（exit code 基準、自己申告を打ち消す）→ 全 issue 緑 + 統合フル CI 緑 → TASK-POST `/cross-review`。

---

## Issue 分解の出発点（§I8 の I1-I6、issue-slicing skill で確定）

| Issue | 契約 | 主 test（Done = named test 緑） | 依存 |
|---|---|---|---|
| I1 | competing cue fixture + 凍結 schema + provenance pass（1 pass full cycle, EclDecisionRecord） | `test_bank_cue_constants_literal_pin` / `test_bank_cue_canonical_inputs_only` / `test_bank_provenance_pass_uses_canonical_builder` / `test_bank_provenance_bias_off` | なし（起点） |
| I2 | bank driver（bake-out M-loop, zone bias off + pre-bias readout）+ `BankLlmCallRecord` + record-M（mc-index, RRCC bank 拡張） | `test_bank_mloop_pre_bias_readout` / `test_bank_llm_call_record_schema` / `test_bank_record_m_mc_index` / `test_bank_replay_roundtrip` | I1 |
| I3 | spend ast-guard（allowlist import + call cap + no-adaptive-topup + raw-row-only + Counter/set/groupby/numpy/scipy/statistics 禁止 + annotation opaque） | `test_bank_no_measurement_computation` / `test_bank_llm_call_cap` / `test_bank_no_adaptive_topup` / `test_bank_annotation_opaque` / `test_bank_import_allowlist` | I2 |
| I4 | power apparatus（categorical multinomial MDE, doc-only pre-run）+ **power worksheet**（検定法・worst/代表分布・pooling 明記、named 閾値確定、ratification gate） | `test_bank_power_isolated_from_annotation` / `test_bank_power_worksheet_present`（worksheet doc + named 閾値存在） | なし（doc-only、並行可） |
| I5 | annotation side-file（opaque）+ construction 検証 run（mock中心 [+ RG-10 で live 可]）+ bank golden replay + cross-platform | `test_bank_annotation_side_file_schema` / `test_bank_golden_replay_checksum` / `test_bank_golden_categorical_byte_stable` | I1, I2 |
| I6 | continuity-gate 4 test + T3 materiality criterion test | `test_bank_import_allowlist` / `test_bank_mloop_retrieve_count_zero` / `test_bank_arity_one_divergence_free` / `test_bank_frozen_string` / `test_bank_t3_desk_audit_present` | I1, I2, I3 |

**sequencing**: I1 → (I2, I4 並行) → (I3, I5, I6 は I1/I2 緑後)。I4 は doc-only ゆえ最も独立。
I3 の guard は I2 の module を対象にするため I2 の後。

---

## verify コマンド（全 autonomous slice 共通の CI parity gate）
- `bash scripts/dev/pre-push-check.sh`（WSL）/ native は `pwsh scripts/dev/pre-push-check.ps1` の 4 段
  （ruff format --check / ruff check / mypy src / pytest -q）全 pass = 末尾 `ALL CHECKS PASSED`。
- categorical（Zone enum）readout ゆえ zone-pick は float 非感応で byte 一致自明。provenance pass の幾何 float
  のみ 6 桁量子化（`_q`/round(x,6)）継承。bank golden = 小規模 committed replay fixture。
- wall-clock/乱数/dict 順序比較 test は clock/seed pin。power worksheet script（もし作る）は assumed dist のみ
  ゆえ CI 対象外可、検証 logic は `tests/` 配下。

## Stop 条件（全 issue 共通、tune-to-narrative 封鎖）
- 実装が organ（loop.py/cycle.py/prompting.py/embodiment.py/parse.py/handoff.py/world）の改変を要する →
  Stop（binding「organ 無改変」逸脱 → superseding ADR）。
- 凍結 context fixture を collapse 観測後に切り直す必要が出た → Stop（forking-paths seal 違反）。
- annotation から H/count/diversity を出す誘惑 → Stop（§I4 spend guard、construction≠measurement 逸脱）。
- power worksheet 閾値を run 結果に合わせて緩める → Stop（tune-to-pass）。
- budget 到達 → Stop。

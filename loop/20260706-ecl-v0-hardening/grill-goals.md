# grill 成果物 — ECL v0 determinism hardening Phase 1 検証可能ゴール

> grilling skill (`.claude/skills/grilling`) 実起動の出力。main checkout 上・タスクにつき 1 回。
> 入力 = FROZEN ADR (`.steering/20260706-m13-ecl-v0-determinism-hardening/design-final.md`、H-0..H-13)。
> **設計は Phase 0 で凍結済ゆえ grill の主眼 = 各漏れの失敗モードを named 回帰 test = exit-code 緑に落とす**。

## 終了条件の充足
- **ユーザー判断を要する未解決の判断分岐 = 0 件**。設計分岐は Phase 0 ADR + Codex Adopt-with-changes で
  全解消済 (P1-a memoize / outcome union / shared `_rank_scope` / checksum inline / version bump / γ last)。
- 曖昧語は glossary 定義済 (`two-plane determinism` / `cross-machine handoff`) + 本 grill で
  **`top-K over candidate pool`** を append 追加 (Codex MEDIUM-3 silent-cap 禁止の pinned 用語)。

## 実装レベル残存曖昧点 → FROZEN 設計意図内で決定 (ユーザー付託不要)
- **RG-1 unparseable タグの record-time 意味**: `RecordReplayChatClient` は parse しないため record 時に
  emit するのは `{ok, raised}` のみ。`unparseable` は **recorded stream 上の値** (response 有・content が
  parse 不能) で replay 時の dispatch は `ok` と同一 (content 返却→cognition 再 parse→None→fallback 再現)。
  `raised` のみ replay で例外再送。∴ union の型は 3 値、client の record-time emit は 2 値、`unparseable` は
  `_build_decision` が `parse_llm_plan()==None` で `llm_status` に立てる (現行踏襲) + hand-built/test 注入で
  stream 値として出現。→ **決定 D-α1**。
- **RG-2 wall_clock/created_at の pin 先**: ADR §3.3「retrieval_now (or tick-derived)」の二択 → **retrieval_now**
  (sent_at pin と同一 clock で一貫、最小差分)。→ **決定 D-α2**。
- **RG-3 2x-bake 決定性 test の形**: `--bake` を 2 回 shell 実行でなく **in-memory** (`run_golden`→`render_golden`
  を 2 回、全 4 artifact 文字列 byte 一致 assert)。CI 内で Ollama 不要・純粋・高速。letter は同一
  (「2 回 bake で全 4 artifact SHA 一致」)。→ **決定 D-α3**。
- **RG-4 γ で AC2 test を強化**: W が decisions.jsonl の wall_clock/created_at を pin する結果、re-bake 後は
  `rendered["decisions.jsonl"] == committed` が真になる。既存 AC2 (`test_ecl_handoff.py:174-186`) の
  「decisions.jsonl は byte 安定を assert しない」注記を **γ で強化** (byte 一致を assert + 注記更新)。
  → **決定 D-γ1**。

## sequencing の決定的事実 (α/β が main を壊さず merge できる根拠)
- 既存 AC2 `test_ecl_v0_handoff_golden_sample_matches` は **decisions.jsonl の byte 安定を意図的に
  assert していない** (trace + envelope_stream のみ byte 比較、`:174-186` に wall_clock/created_at 未 pin を
  既知として文書化)。∴ **α の W fix (fresh render が decisions.jsonl を変える) は既存 test を壊さない** →
  α は re-bake せず main merge 可。
- golden は 8 tick × 1 memory/tick ゆえ retrieval candidates ≤ 8 = k_agent、**truncation 不発**。
  ∴ **β の `_rank_scope` 全順序化は golden の top-k 集合も centroid (順序独立) も MoveMsg target も変えず**、
  ecl_trace_checksum 不変・trace/envelope_stream 不変 → β も re-bake せず main merge 可。retrieved_memories の
  順序変化は decisions.jsonl bytes のみ波及 (AC2 非 assert) → γ re-bake で捕捉。
- ∴ 唯一 golden を変えるのは **γ (P1 jitter sequence 化 = trace 変化 + C canonical = checksum bytes 変化 +
  W = decisions.jsonl 決定化)**。γ で単一 re-bake。cross-issue 順序ハザード構造的不発生。

---

## Slice α = P2(B-2) + W(B-5) — record-mode Plane2/clock hardening
**verify_level = parse (通常、mock 注入)**。golden 不変 (committed 再生成なし)。

| ID | Done = named test 緑 | 失敗モード (fix 前) |
|---|---|---|
| α-G1 | `test_ecl_loop_raised_call_does_not_crash` — record 中 tick k で `OllamaUnavailableError` 注入 → run 完走 (IndexError なし) + `used` tick 整合 (len==n) + 当該 decision `llm_status=="raised"`/`plan is None` | `llm.used[agent_tick]` 位置参照が短くなり IndexError crash |
| α-G2 | `test_ecl_loop_raised_replay_checksum_matches` — raised tick 含む record → decisions のみで replay → `inner_invocations==0` + 同例外再送 + fallback 再現 + checksum byte 一致 | replay で失敗 tick 再現不能 (Plane2 に痕跡なし) |
| α-G3 | `test_ecl_loop_unparseable_replay_checksum_matches` — unparseable content 注入 → fallback → replay で content 返却→同 fallback → checksum 一致 | — (回帰固定) |
| α-G4 | `test_ecl_loop_fallback_envelope_clock_pinned` — fallback tick の AgentUpdateMsg `sent_at == retrieval_now` (record mode)、flag-off は default factory 不変 | cycle `_fallback` が `_pin_envelope_clock` 迂回で sent_at 未 pin |
| α-G5 | `test_ecl_loop_success_then_raised_replay_matches` — ok→raised→ok 列 → replay checksum 一致 (直前 Kinematics.destination 依存で位置前進が決定的、Codex LOW/H-13) | — (回帰固定) |
| α-G6 (W) | `test_ecl_v0_golden_rebake_is_deterministic` — `run_golden`→`render_golden` を 2 回、全 4 artifact 文字列 byte 一致 (wall_clock/created_at pin の letter、D-α3) | `AgentUpdateMsg.agent_state.wall_clock` / `ReasoningTrace.created_at` 未 pin で decisions.jsonl SHA が bake 毎に変わる |
| α-G7 | `test_ecl_flag_off_byte_invariant` (既存) 緑維持 — flag-off (`ecl_mode is None`) 経路完全不変 | (回帰防止) |

- **Stop**: raised 処理が sanctioned 範囲 (`_fallback` pin / record-mode clock pin / `RecordReplayChatClient` /
  `_build_decision` / driver 位置参照廃止) を超えて frozen cycle.py の他所改変を要する → Stop (superseding ADR scope 逸脱)。
  2x-bake が W fix 後も非決定 → Stop (未 pin source 特定)。
- **Out**: γ の committed golden 再生成 (α は再 bake しない); measurement 再入; checksum canonical (γ)。

## Slice β = R(B-3) — retrieval 全順序化 (shared 根治)
**verify_level = recheck (共有層)**。golden ecl_trace_checksum 不変・decisions.jsonl 波及は γ 捕捉。

| ID | Done = named test 緑 | 失敗モード (fix 前) |
|---|---|---|
| β-G1 | `test_rank_scope_total_order_before_truncation` — `k_agent < candidates ≤ 50` の equal-strength 群 (uniform embedding + 同 importance/recall、created_at/id 相異) で `_rank_scope` が truncation **前**に `(-strength, created_at, id)` 全順序化 + 2 回実行 order 一致 | strength のみ sort → `[:k]` truncate で >k tie が非決定/回復不能 |
| β-G2 | `test_rank_scope_candidate_pool_boundary` — `candidates > limit_candidates(50)` の equal-strength で **候補集合 (limit=50) 内**の total order のみ (51 件目以降は拾わない = "top-K over candidate pool")。silent cap でなく境界を test で pin | 境界が暗黙 (silent cap) |
| β-G3 | 全 regression 緑: `pytest -q tests/test_memory/ tests/test_evidence/ tests/test_cognition/ tests/test_integration/` + フル suite 緑 (共有層改変の非回帰) | — |
| β-G4 | `test_ecl_v0_handoff_golden_sample_matches` (既存 AC2) 緑維持 — golden trace/checksum 不変 (candidates≤8 で truncation 不発) | — |

- **Stop**: sort 変更が既存 retrieval-order test (SPDM 集合ベース / production resolver 再ソート) を壊す →
  ADR は LOW risk・resolver は既に同一 key で再ソート済と主張 → 実測で真の衝突なら Stop・escalate。
- **Out**: frozen `running/policy.py` top-1-centroid (計測ライン CLOSED、再走計画外); γ re-bake。
- **付託検査 (Codex MEDIUM-2)**: 過去 committed evidence artifact が retrieval 順序依存で baked されていないか
  Phase 1 で検査 (β issue の Test Plan に含める)。

## Slice γ = P1(B-1) + C(B-4) + 最終単一 re-bake + version bump — **α・β merge 後 (γ last)**
**verify_level = recheck (golden 再生成 + reproduction 契約)**。golden **変わる**。

| ID | Done = named test 緑 | 失敗モード (fix 前) |
|---|---|---|
| γ-G1 (P1) | `test_ecl_record_mode_rng_is_run_sequenced` — `substream(agent,"micro")` 反復呼が同一 `Random` (memoize get-then-assign) → per-tick jitter distinct>1、同 run_id の 2 EclRecordMode で draw 列 byte 一致 | 毎 tick fresh `Random(seed-str)` → 全 tick first-draw 同一 |
| γ-G2 (C) | `test_ecl_trace_checksum_canonical_rules` — `ecl_trace_checksum` が `separators=(",",":")`+`ensure_ascii=False`+`allow_nan=False`、非有限 float は raise + `CANONICAL_JSON_RULES` と同一 canonicalization を pin する drift test | `json.dumps(sort_keys=True)` のみ → 非有限 silently hash + consumer と別値 |
| γ-G3 (version) | `test_manifest_version_and_replay_checksum_fields` — `MANIFEST_SCHEMA_VERSION=="ecl-v0-handoff-2"` + manifest に `replay_checksum_algorithm=="sha256"` + `replay_checksum_json_rules` 出力 | version 未 bump + rule fields なし |
| γ-G4 (re-bake) | `test_ecl_v0_handoff_golden_sample_matches` 強化版緑 — 新 golden で checksum 一致 **かつ `rendered["decisions.jsonl"] == committed`** (W pin 済ゆえ byte 安定、D-γ1) + 2x-bake test (α-G6) 緑 | — |
| γ-G5 (verify) | `python scripts/ecl_v0_golden.py --verify` exit 0 (新 committed golden) | — |

- **Stop**: 2x-bake 非決定 → Stop; checksum canonical 変更が想定外の consumer 契約 test を壊す → 調査。
- **Out**: measurement 再入。
- **順序制約 (binding)**: γ は α・β を main merge した後に着手・**re-bake は γ 内単一回**。

---

## verify コマンド (全 slice 共通の CI parity gate)
- `bash scripts/dev/pre-push-check.sh` (WSL) または `pwsh scripts/dev/pre-push-check.ps1` (G-GEAR native)
  の 4 段 (ruff format --check / ruff check / mypy src / pytest -q) 全 pass = 末尾 `ALL CHECKS PASSED`。
- wall-clock/乱数/dict 順序比較 test は clock/seed pin (G-13)。

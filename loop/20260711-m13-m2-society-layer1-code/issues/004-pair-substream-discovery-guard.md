# Issue 004 (I4): per-pair named RNG substream + pair-interaction determinism + permutation/checklist discovery guard
verify_level: recheck   # Codex MEDIUM-7 (pair_key 衝突封鎖) + MEDIUM-8 (discovery guard) + determinism 契約 直結

## Goal
proximity/separation/dialog の乱数を **per-pair named RNG substream**（pair_key = canonical JSON array）で
seed し、pair-interaction を replay-stable にする。**discovery guard を「既知集合限定」から実装保証へ格上げ**:
登録順 permutation → 同一 checksum の permutation test、checksum 経路に裸の非 sorted `values()`/`set` iteration
が無い AST/grep guard、DB/SQLite read の `ORDER BY`、mutation/event emission の canonical key sort。
**新規 Python 非決定源を作らない**（named 命名規律に沿うのみ）。**construction であって measurement でない**。

## Background
FROZEN ADR §M4.2（per-pair named substream、pair_key = canonical JSON array）/§M4.3（discovery guard 義務化）/
§M9.1（permutation/checklist/pair test）/ DA-M2IMPL 8 / Codex MEDIUM-7（`"-".join(sorted([a,b]))` は agent_id に
`-` を含むと `["a-b","c"]` と `["a","b-c"]` が衝突 → `json.dumps(sorted([a_id,b_id]), separators=(",",":"),
ensure_ascii=True)` で material 化）/ MEDIUM-8（discovery guard = DB ORDER BY / canonical key sort / checksum
入力 = final canonical projection のみ）。§M2 確証: dialog RNG は injected `Random`（dialog.py L126/132）で
seedable。設計 FROZEN。

## Scope
### In
- `integration/embodied/society.py`（+ 必要なら `integration/dialog.py` の injected Random 配線）:
  - **per-pair named substream**: `f"...-{seed}-{pair_key}-{stream}"`、`pair_key =
    json.dumps(sorted([a_id, b_id]), separators=(",", ":"), ensure_ascii=True)`（衝突封鎖）。dialog RNG /
    proximity/separation tie の乱数を per-pair substream で seed。**per-agent** substream
    （`f"...-{seed}-{agent_id}-{stream}"`、embodiment.py `EclRecordMode.substream` 既存規律）と併用。
  - **discovery guard**: (1) 登録順 permutation → 同一 checksum。(2) checksum 経路の裸非 sorted `values()`/`set`
    iteration 非在（canonicalization 用 `sorted(set(...))` は allow）。(3) memory mutation の DB/SQLite read は
    `ORDER BY` 必須。(4) mutation/event emission は canonical key sort。(5) checksum 入力 = final canonical
    projection のみ（中間 order を混ぜない）。
- `tests/test_integration/test_m2_society.py`（本 issue 分を追記）。
### Out
- handoff N体 schema（I5）。spend ast-guard（I6、guard-test 自身は I6）。tick §B4 sorted 化（I1、済）。
  event-log checksum 定義（I3、済、本 issue は permutation/pair 軸で検証）。**measurement 一切**。

## Allowed Files
- `src/erre_sandbox/integration/embodied/society.py`（per-pair substream + discovery guard sort 化）
- `src/erre_sandbox/integration/dialog.py`（injected Random に per-pair named substream を渡す配線のみ、
  既存 `rng if rng is not None else Random()` の seed 供給、乱数使用箇所は無改変）
- `tests/test_integration/test_m2_society.py`（本 issue 分）
- **無改変厳守**: `loop.py` / `handoff.py` / committed golden / `evidence/**` / `bank*.py` / `embodiment.py`
  （substream 命名規律は import 参照のみ）

## Acceptance Criteria（AC↔test）
- I4-G1: `test_m2_pair_interaction_deterministic` — N=2 で proximity/separation/dialog RNG が pair_key
  （canonical JSON array）keyed named substream で replay-stable。pair event が `sorted_pair=(min_id,max_id)` で
  serialize（Codex HIGH-3、I1 と整合）。
- I4-G2: `test_m2_society_determinism_permutation` — N=3 で同一 agent 集合を **異なる登録順**で register →
  **同一 checksum**（order_slot=sorted(agent_id) + I1 sorted 化 + canonical key sort により dict-insertion 順が
  checksum へ漏れない）。
- I4-G3: `test_m2_society_determinism_checklist` — no-wall-clock / per-agent+per-pair named substream /
  deterministic ids を N体拡張検査 + **checksum 経路に裸非 sorted `values()`/`set` iteration が無い**
  （`sorted(set(...))` は allow）+ DB/SQLite read の `ORDER BY` + mutation/event emission の canonical key sort +
  checksum 入力 = final canonical projection のみ（AST/grep discovery guard、Codex MEDIUM-8）。
- I4-G4: `test_m2_pair_key_collision_free` — pair_key = canonical JSON array で agent_id に `-` を含む
  （例 `"a-b"` vs `"c"` と `"a"` vs `"b-c"`）ケースが衝突しない（Codex MEDIUM-7）。
- I4-G5: I1/I2/I3 の test 群 + 既存 legacy byte 不変回帰 緑維持。
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`。

## Test Plan
`pytest -q tests/test_integration/test_m2_society.py` + 回帰 + pre-push 4 段。全て mock LLM + seeded RNG。
permutation は agent 登録順を itertools.permutations で回し checksum 集合が単一要素であることを assert。
discovery guard は AST 走査（ast module）で society.py の checksum 経路を検査。

## Stop Conditions
- 全 AC 緑（Done）。
- permutation で checksum が割れる → Stop（残存非決定源、discovery guard が未閉塞経路を発見 = 本 issue の仕事、
  該当経路を sorted 化して緑にする。閉塞不能なら Stop→調査）。
- pair_key 衝突封鎖に canonical JSON array 以外の hack が必要 → Stop（§M4.2 逸脱）。
- discovery guard を通すために checksum から event 種を除外したくなる → Stop（§M4.4 event-log 全体 checksum 逸脱）。
- 凍結 apparatus 改変を要する → Stop（superseding ADR）。budget 到達 → Stop。

## Dependencies
- I3（event-log 全体 checksum が permutation/checklist の検証対象）。I1（pair sorted 化）。

## Status
DONE（2026-07-11、feat/m13-m2-layer1、commit 749b333）

## Execution Result
subagent（Sonnet）実装 → test-runner(Haiku) 独立再検証（recheck、7/7 exit 0、509 passed）→ verdict=DONE。
- `society.py`: `_pair_key`（canonical JSON array、MEDIUM-7 衝突封鎖）+ `_PairRngCache`（per-pair named
  substream）+ discovery guard（`_CHECKSUM_PATH_FUNCS` AST 検査）。record-mode driver から world の既存 hook
  （`attach_dialog_scheduler`/`_run_dialog_tick`/`_drive_dialog_turns`）を逐次呼出しで dialog 発火（tick.py 無改変）。
  utterance = 決定的テンプレート（LLM call ゼロ）。
- `dialog.py`: `InMemoryDialogScheduler` に `rng_for_pair` 注入（dialog_id を per-pair substream で決定的採番、
  None 時は既存 uuid4 で byte-for-byte 不変）。
- **DG-6 閉**: `test_m2_pair_interaction_deterministic` が実 driver 経由で `dialog_events` **非空**を assert
  （vacuous でない、独立検証で確認）。**決定的発見**: 素朴配線で uuid4 dialog_id が checksum 混入し非決定を
  実測 → 注入経路で閉塞。
- affinity = honest known-empty（唯一の呼出元 bootstrap.py が Allowed 外、docstring 明記）。
- **独立検証**: pytest（test_m2_society 13 / integration 回帰 184 / test_world 158 / dialog 154 passed 3 skip）+
  mypy(239 clean)/ruff/format、7/7 exit 0。cross-review 付託: dialog utterance テンプレの是非、affinity 恒常空。

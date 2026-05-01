# M5/M6 natural runtime gating bug — design (P3a-decide Task 1)

> Plan-mode 等価ドキュメント。auto-mode 内の "Plan + /reimagine + Codex review"
> CLAUDE.md 制約を満たすため、本ファイルで初期案 + reimagine 代案 + 採用案 +
> Codex review 反映を一元化する。

## 1. 観測症状 (G-GEAR PR #129 採取)

| cell | wall | dialogs | focal | utterances 内訳 |
|---|---|---|---|---|
| kant_natural | 13 min (kill) | 2 | 6 | kant=6 / nietzsche=3 / rikyu=3 |
| nietzsche_natural | 13 min (kill, starved) | 0 | 0 | — |
| rikyu_natural | 13 min (kill) | 3 | 6 | kant=6 / nietzsche=6 / rikyu=6 |

**stimulus side は 3 cell とも focal=198 / dialogs=168 で完走**、natural 専用の
gating 挙動が発火している。

## 2. 仮説 4 件と裏取り

| ID | 仮説 | 裏取り | 採否 |
|---|---|---|---|
| A | RNG seed が初動後に false 一辺倒に偏る | `random.Random(seed_root)` は MT19937 で 2^19937 周期、burst 後だけ false 連続にはならない | × 棄却 |
| B | COOLDOWN_TICKS 30 × cognition_period 7-18s で実効 cooldown 30 min+ | 確かに wall は長いが、cognition tick は最終的に進む。kant_natural 13 min wall で nietzsche cognition_period=7s + WorldRuntime DEFAULT_COGNITION_PERIOD_S=10s → world_tick は 50+ 進むはず → cooldown 単独では説明不可 | △ 補助 |
| C | `_close_timed_out` が in-flight dialog を premature close | 既存 dialog の transcript が 6 turn (= dialog_turn_budget default) で揃っており、exhausted close で正常終了している。timeout race 未発生 | × 棄却 |
| D (revised) | LLM-driven `destination_zone` で agents が AGORA から散る → `_iter_colocated_pairs` が 0 pair 返却 | `personas/{nietzsche,rikyu}.yaml` の `preferred_zones` に **AGORA が含まれない** (Nietzsche=[peripatos,study,garden] / Rikyu=[chashitsu,garden,study])。`cognition/cycle.py:_resample_destination_to_persona_zone` で AGORA 以外に強制リサンプリング → 初動 1-3 tick 後に必然的に scatter | ◎ **採用** |

### Hypothesis D の精緻なメカニズム

1. `cli/eval_run_golden.py:_initial_state_for_natural` は 3 persona を
   `Zone.AGORA` の non-overlapping seat に配置 (boot-time)。
2. `cognition/prompting.py` の system prompt が `destination_zone` を 6 値
   (`study|peripatos|chashitsu|agora|garden|null`) のうち 1 つ選ばせるため、
   LLM は約 5/6 の確率で非 null を返す。
3. 非 null 値が persona の `preferred_zones` 外なら
   `_resample_destination_to_persona_zone` で **preferred の中から決定的に再選択**
   される (Nietzsche なら peripatos / Rikyu なら chashitsu 等)。
4. `WorldRuntime._consume_result` が MoveMsg を `apply_move_command` し、
   同時に `rt.state.position.zone = res.agent_state.position.zone` で更新
   (cycle.py:686-692 で `new_state.position.model_copy(update={"zone": ...})`)。
5. 次の `_run_dialog_tick` で `_iter_colocated_pairs` が `a.zone == b.zone` を
   要求 → Nietzsche (PERIPATOS) / Rikyu (CHASHITSU) / Kant (STUDY|AGORA) は
   ほぼ常に bare → 0 pair。
6. 既に open な dialog は **budget exhaustion** (6 turn) まで継続するので、
   "初動 burst 2-3 dialogs × 6 turns = 12-18 utterance" で総量が固定。

「Nietzsche starved」は zone scatter が初動 1 tick で起きて Nietzsche 関与 pair
が一切 admit できなかった subset。

## 3. 初回案 (Claude single-shot)

`integration/dialog.py` の `InMemoryDialogScheduler` に
**`eval_natural_mode: bool = False`** flag を追加。`True` のとき:

- `tick()` 内で `_iter_colocated_pairs(agents)` を呼ばず、`agents` の **全 distinct pair**
  を反復する pure イテレータ `_iter_all_pairs` を使う。
- pair の `zone` は両 agent の zone の **どちらでもよい**ので `a.zone` を採用
  (logging / envelope 用、admission に zone 制約は無し)。
- `_REFLECTIVE_ZONES` 制約も bypass (3 persona は事実上 AGORA で対話している
  「論理的同居」状態として扱う)。
- `COOLDOWN_TICKS` / `AUTO_FIRE_PROB_PER_TICK` / `TIMEOUT_TICKS` はすべて
  default 通り **active のまま** (natural cadence を保つ)。

CLI 側は `eval_run_golden.py:935-941` で `InMemoryDialogScheduler(...,
eval_natural_mode=True)` を渡す **1 行追加** のみ。

## 4. /reimagine 代案 (zero-from-scratch alternative)

代案 A: **`pin_zone` パラメタを WorldRuntime に追加**して MoveMsg を破棄

- `world/tick.py` に `eval_pin_zone: Zone | None = None` を入れて、
  `_consume_result` で MoveMsg を全部 drop (zone 移動禁止)。
- 利点: 「物理的同居」が真になる。LLM 出力は無害化されるだけで scheduler は
  純朴なまま。
- 欠点: world/ 層に eval-specific な knob を入れる (planning purity 違反、
  M5/M6/M7ζ の dwell/phase wheel と相互作用するリスク)。

代案 B: **persona の `preferred_zones` を eval 起動時に [AGORA] のみに上書き**

- `eval_run_golden.py:capture_natural` 内で `PersonaSpec` を model_copy し、
  preferred_zones を `[Zone.AGORA]` に強制。
- 利点: scheduler/world に変更不要、概念的にも「eval 用に AGORA 固定」と明快。
- 欠点: PersonaSpec が deeply frozen の場合 `model_copy` で
  preferred_zones が反映されない可能性。検証必要。LLM が
  `destination_zone=null` を返すと AGORA に止まるが、`destination_zone=garden`
  を返すと resample で AGORA 強制 — 一見動くが `_resample_destination_to_persona_zone`
  の実装が `random.choice(list(persona.preferred_zones))` (cycle.py:894 周辺)
  で 1 要素 list なら必ず AGORA に解決される、確認要。CLI 側 1 ファイルで完結。

代案 C: **dialog scheduler が "registered agent set" を持ち、initial-zone-anchor**
で pair を構築

- 起動時に `register_pair_set(frozenset[frozenset[str]])` で eval pair set を
  与え、`tick()` はその pair を直接反復。
- 利点: 明示的、既存ロジックを壊さない。
- 欠点: API 増、CLI 経由で frozenset 構築が必要、boolean flag より重い。

## 5. 比較と採用判断

### 5.0 critical insight: `ERRE_ZONE_BIAS_P` の default = 0.2

`cognition/cycle.py:275` で
`self._zone_bias_p = float(os.environ.get("ERRE_ZONE_BIAS_P", "0.2"))`。
すなわち non-preferred zone への移動が LLM 出力で発生したとき、
**20% でしか preferred への bias resample が発火しない**。残り 80% は LLM の
zone choice を honor。

prompt が `destination_zone` に 6 値 (`study|peripatos|chashitsu|agora|garden|null`)
を提示する事実と組み合わせると、natural condition の per-tick zone change rate は
おおよそ:

- LLM null 比率 ~ 1/6 (no move)
- LLM picks AGORA (preferred 内なら no resample) ~ 1/6 (stay)
- LLM picks non-preferred ~ 4/6 → bias_p=0.2 で 20% は AGORA resample / 80% は
  そのまま移動

→ 移動率 ≈ 4/6 × 0.8 ≈ **53%**
→ 3 tick 後に少なくとも 1 名が AGORA を離れる確率 = 1 − (1 − 0.53)^3 ≈ **89%**

これが「初動 2-3 dialog → admission 停止」と一致する。

### 5.1 代案再評価

| 軸 | 初回案 (flag) | 代案 A (pin) | 代案 B (preferred_zones) | 代案 B+ (preferred + bias_p=1.0) | 代案 C (pair set) |
|---|---|---|---|---|---|
| 変更ファイル数 | 2 (dialog.py + CLI) | 2-3 (tick.py + CLI) | 1 (CLI) | 1 (CLI) | 2 (dialog.py + CLI) |
| 変更行数 (推定) | ~25 | ~15 | ~6 | ~10 | ~40 |
| **修正の完全性** | **完全** | 完全 (但し world/ 層介入) | **不完全** (bias_p=0.2 で 53% drift 残存) | 完全 (env var 強制) | 完全 |
| planning purity 違反 | 1-line CLI (許容) | world/ 層 (NG) | CLI のみ | CLI のみ + env var mutation | 1-line CLI |
| 既存テスト regression リスク | 低 (default False) | 中 | 低 | 低 (env var 範囲限定) | 低 |
| 概念的明快さ | **高** ("logical co-location for eval") | 中 ("freeze movement") | 中 (不完全) | 低 (env var hack) | 中 |

**結論: 代案 B 単独では 5.0 の bias_p=0.2 計算により 53% drift が残るため不採用**。

### 5.2 採用案: **初回案 (scheduler flag `eval_natural_mode`)** 単独

理由:
1. **完全性**: zone 制約 自体を bypass するので、agent が wander してもしなくても
   pair admit に影響しない。bias_p / preferred_zones / LLM 出力に依存しない。
2. **副作用最小**: integration/ 層内で完結、cognition/ や world/ には触れない。
   既存 1221 PASS は default False (= 既存挙動) で維持。
3. **概念的に正しい**: eval natural は「3 persona を論理的に同居させる」ための
   評価 setup であり、proximity-based 自然発火セマンティクスとは別の関心事。
4. CLI 1 行追加 (`InMemoryDialogScheduler(..., eval_natural_mode=True)`) は
   planning purity の "CLI 不変" 制約をわずかに違反するが、これは
   **「eval scheduler 構築時の opt-in」** であって CLI ロジック変更ではない。
   許容範囲とする (decisions.md ME-8 で justify)。

代案 B+ (env var mutation) は機能はするが env-driven hack で diagnosability が
低く、scheduler-side flag より監査性で劣る → 不採用。

## 6. 修正範囲 (採用案 = 初回案 scheduler flag)

### 6.1 修正ファイル

- `src/erre_sandbox/integration/dialog.py`:
  - `InMemoryDialogScheduler.__init__` に `eval_natural_mode: bool = False` 追加
    (keyword-only)
  - `tick()` 内で `eval_natural_mode=True` のとき
    `_iter_colocated_pairs` を呼ばず、`agents` の全 distinct pair を反復する
    新ヘルパ `_iter_all_distinct_pairs` を使用
  - `_REFLECTIVE_ZONES` 制約と `a.zone == b.zone` 制約を bypass
  - **Cooldown / probability / timeout は active のまま** (natural cadence 保持)
  - `schedule_initiate` の zone 制約 (line 156) は `eval_natural_mode=True` でも
    bypass する (eval では agent zone が自由に変わるため)
  - public attribute (driver から動的に切替可能) — `golden_baseline_mode`
    と同じパターン

- `src/erre_sandbox/cli/eval_run_golden.py`:
  - line 935-941 の `InMemoryDialogScheduler(...)` 呼び出しに
    `eval_natural_mode=True` を 1 引数追加 (`golden_baseline_mode=False` の隣)
  - これは構築時 opt-in のみで CLI ロジックは不変

- `tests/test_integration/test_dialog_eval_natural_mode.py` (新規):
  1. **Red → Green 転換確認**:
     - eval_natural_mode=False (既存挙動) で、3 agent が異なる zone に分散すると
       admission が停止することを assert (バグの document 化)
     - eval_natural_mode=True で、同じ scenario でも admission が継続することを assert
  2. **invariant 保持**:
     - cooldown は active (close 後 30 tick 待つ)
     - probability gate は active (rng > 0.25 → admit しない)
     - timeout は active (last_activity_tick + 6 で close)
     - `initiator_id == target_id` reject は active
     - 既に open な pair の二重 open reject は active
  3. **golden_baseline_mode との独立性**:
     - 両 flag を True にしても矛盾しない (golden_baseline が優先で zone bypass)
     - default 両方 False で M4-frozen Protocol 挙動
  4. **scheduler 単体テスト**: ManualClock 不要、`tick()` を直接呼んで
     AgentView 渡し、scheduler 内部状態 (`_open` / `_pair_to_id` /
     `_last_close_tick`) を inspect

### 6.2 既存 1221 テスト互換性

`eval_natural_mode: bool = False` default のため、既存挙動は完全に維持。
- `tests/test_integration/test_dialog.py` (既存 70 件): default False で全 PASS
- `tests/test_integration/test_dialog_golden_baseline_mode.py` (既存 10 件):
  golden_baseline_mode は eval_natural_mode と直交、両 default False / True で
  既存と同じ動作

### 6.3 schemas.py の Protocol 整合

`DialogScheduler` Protocol は `__init__` 引数を規定していない (M4 §7.5 frozen)
ので keyword-only flag 追加は Protocol 違反にあたらない。`tick()` /
`schedule_initiate()` / `record_turn()` / `close_dialog()` の signature は
完全に不変。

## 7. 受け入れ条件

- [ ] 新規 test_dialog_eval_natural_mode.py の Red→Green 転換テストが PASS
  - default False で zone drift の admission stop を再現
  - True で admission が継続
- [ ] cooldown / probability / timeout / 自己 dialog reject / 二重 open reject
      の invariant が True/False 両方で維持される
- [ ] 既存 1221 PASS 維持 (default False を確認)
- [ ] G-GEAR 再採取で focal 30 / total 90 / dialogs ~15 を 30-60 min wall
      で完走 (本セッションでは Mac で実機検証不可、次 G-GEAR セッションで確認)
- [ ] decisions.md に新規 ADR (ME-8) 追加: "eval natural condition は
      InMemoryDialogScheduler.eval_natural_mode=True で zone 制約を bypass"
- [ ] tasklist.md §P3a-decide にチェック項目追加

## 8. リスクと反証

- **リスク**: LLM が persona prompt を読んで「私は普段 STUDY にいる」等の認識を
  持ち、preferred_zones override に逆らって STUDY を utterance/thought に出す。
  → utterance 内容の影響であって physical zone は AGORA stay なので
  scheduler は admit する。文体には影響あるが eval 目的 (Burrows / Vendi の
  分布) には許容。
- **反証**: もし `preferred_zones` override 後も新規 admit が再開しない場合、
  仮説 D 以外の根本原因 (B/C も併発) があり得る → 次 G-GEAR セッションで
  再採取データを inspect。

## 9. Codex review

本ドキュメント完成 + 実装 diff 確定後、`gpt-5.5 xhigh` independent review に
回す。codex-review-prompt-natural-gating.md / codex-review-natural-gating.md を
verbatim 保存。HIGH は実装前に反映、MEDIUM は decisions.md ME-8 に取り込み。

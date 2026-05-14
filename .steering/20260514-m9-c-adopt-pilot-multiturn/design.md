# 設計 — m9-c-adopt pilot multi-turn investigation

## 実装アプローチ

### Codex review 反映 (重要)

**Codex independent review (`codex-review.md`、verbatim 保存) で MODIFY verdict +
HIGH 4 件 + MEDIUM 5 件 + LOW 2 件**。`decisions.md` D-1 で反映方針を確定:

- **HIGH-1**: 単 protocol change だけでは methodology dominant と言えない →
  **rank=8 no-LoRA SGLang control** を同 protocol で採取、primary comparison
  は **matched baseline** に切替、Scenario I 結論を「baseline-like no-prior
  multi-turn sampling is sufficient to reverse direction」に弱める
- **HIGH-2**: pilot 6 windows vs baseline 25 windows の不公平 → **matched
  baseline downsampling** を実施 (compute なし、consumer rerun のみ)
- **HIGH-3**: scenario criteria を **採取前** preregister (`decisions.md`
  DA-13 draft 内)
- **HIGH-4**: smoke 目視だけだと安全網がない → **post-capture validation
  query** を DA-13 acceptance gate に
- **MEDIUM-3**: checkpoint resume で incomplete multi-turn dialog 残存 →
  stimulus 単位 atomic commit に切替

### 核心観察 (baseline protocol 内面化)

`src/erre_sandbox/cli/eval_run_golden.py` と
`src/erre_sandbox/evidence/golden_baseline.py` を読み込んで判明した
baseline (M9-eval P3 stimulus condition) protocol の**重要な特性**:

1. `GoldenBaselineDriver.run_stimulus()` は `expected_turn_count` 回 loop し、
   `turn_index % 2 == 0` で focal、`% 2 == 1` で interlocutor の speaker_id を
   alternate (line 393-417)。
2. **両 speaker (focal + interlocutor) は同じ `inference_fn` 経由で生成される**。
   driver は `persona_id` と `prior_turns` を inference_fn に渡すが、stimulus
   condition 用 `_make_stimulus_inference_fn` (eval_run_golden.py:455-498) は
   `del persona_id, prior_turns` で **両方を捨てて、focal persona の system
   prompt + 同じ stimulus user prompt (turn=N marker のみ index 差し替え)** で
   呼び出す。
3. 結果: 各 turn は essentially **i.i.d. samples from same prompt** (turn marker
   のみ index 変動)。Burrows / Vendi は `WHERE speaker_persona_id = 'kant'` で
   focal turn のみ filter して計算。
4. stimulus YAML `expected_turn_count` 分布 (kant): 1 turn × 10 / 2 turn × 42 /
   3 turn × 18 (合計 70 stim、focal turn = 88/battery)。

→ multi-turn pilot で apples-to-apples を保つには、**完全に同じ protocol** を
SGLang LoRA adapter 経由で再現すればよい:

- `expected_turn_count` 回 loop
- 各 turn で SGLang `model=kant_r{rank}_real` に同じ system+user prompt (turn=N
  marker のみ index 変動)
- focal/interlocutor speaker_id alternation は DuckDB 行 (`speaker_persona_id`
  field) で記録
- `prior_turns` は SGLang chat にも渡さない (baseline と同じく削除)

### 拡張内容 (`scripts/m9-c-adopt/tier_b_pilot.py`)

1. **CLI flag 追加**:
   - `--multi-turn-max N` (default `1` で過去互換、investigation で
     `--multi-turn-max 6` を使用。Kant max expected_turn_count=3 のため 6 は
     no-op cap、future battery 用 future-proof、LOW-2 反映)
   - `--no-lora-control` (HIGH-1 反映、SGLang base model に route、
     `model=Qwen/Qwen3-8B` で adapter なし、`_ensure_adapter_loaded` skip)
   - rank=0 + `--no-lora-control` を受理する argparse 拡張
2. **`_focal_turn_count(stimulus, multi_turn_max)` 改修**:
   ```python
   def _focal_turn_count(stimulus: dict[str, Any], multi_turn_max: int) -> int:
       """Focal-speaker turn count per stimulus (baseline と同 protocol)."""
       expected = int(stimulus.get("expected_turn_count", 1))
       capped = min(expected, multi_turn_max)
       # baseline と同じ ceil(N/2) (driver alternates、focal は turn_index 0, 2, ...)
       return max(1, (capped + 1) // 2)
   ```
3. **`_stratified_slice` の呼び出し側**: `target_per_cycle` 計算は変更なし
   (`turn_count // cycle_count`、focal turn 数 budget は同じ意味のまま)。
4. **main 採取 loop 改修**: 単一 turn から expected_turn_count loop に変更:
   ```python
   capped = min(int(stimulus.get("expected_turn_count", 1)), args.multi_turn_max)
   for turn_index in range(capped):
       is_focal = (turn_index % 2 == 0)
       speaker_pid = persona_id if is_focal else _INTERLOCUTOR_ID
       addressee_pid = _INTERLOCUTOR_ID if is_focal else persona_id
       # SGLang chat 呼び出し: system_prompt + _build_user_prompt with turn=N
       resp = _sglang_chat(..., user_prompt=_build_user_prompt(stimulus, cycle_idx, turn_index))
       _insert_turn(con, ..., turn_index=turn_index, speaker_pid=speaker_pid,
                    addressee_pid=addressee_pid, utterance=resp.text)
       if is_focal:
           completed += 1
       tick += 1
   ```
5. **`_build_user_prompt` 改修**: 既存 hardcoded `turn=0` を `turn={turn_index}` に変更
   (baseline `_build_stimulus_user_prompt` と整合)。
6. **`_insert_focal_turn` を `_insert_turn` にリネーム + 引数化**: `turn_index`,
   `speaker_pid`, `addressee_pid` を引数として受け取り、row_id は
   `{run_id}:{dialog_id}:{turn_index}` に。
7. **checkpoint resume (MEDIUM-3 反映)**: stimulus 単位 atomic commit に切替。
   fatal 時に **in-progress `dialog_id` の rows を DELETE してから** checkpoint
   を flush、resume 後は last_stimulus_id の **次** から開始 (stimulus 内の
   turn loop の途中再開を許さない、incomplete dialog を shard に残さない)。
8. **default `--multi-turn-max`**: `1` (single-turn mode 過去互換)。investigation
   採取は `--multi-turn-max 6` で実行。
9. **`--no-lora-control` mode (HIGH-1 反映)**: SGLang base model に route
   (`model=Qwen/Qwen3-8B`)、`_ensure_adapter_loaded` skip。output run_id は
   `{persona}_nolora_run{idx}_pilot` (LoRA-on shard と分離可能)。

### 採取構成 (HIGH-1 + HIGH-2 反映)

- output dir: `data/eval/m9-c-adopt-tier-b-pilot-multiturn/` (single-turn pilot
  との共存)
- **LoRA-on 6 shard**: `kant_r{4,8,16}_run{0,1}_stim.duckdb`
- **no-LoRA control 2 shard** (HIGH-1): `kant_nolora_run{0,1}_stim.duckdb`
- `--turn-count 300 --cycle-count 6 --multi-turn-max 6`
- SGLang: 既存 `launch_sglang_icc.sh` (`--max-lora-rank 16` amendment 済) +
  `multi_pin_sanity.sh` で 3 adapter pin。no-LoRA control は同 server に対し
  `model=Qwen/Qwen3-8B` で route。

### Matched baseline (HIGH-2 反映)

`compute_baseline_vendi.py` / `compute_burrows_delta.py` を historical baseline
shard (`data/eval/golden/kant_stimulus_run*.duckdb`) に対して **pilot と同じ
`--window-size 100`** で再走らせ、ただし `--total-windows` を制限する手段が
consumer 側にあるか確認。なければ window-size を pilot focal 数 (300×2 runs) に
近い値に揃える。`tier-b-baseline-matched-kant-{vendi,burrows}.json` を出力、
primary comparison に使用。

primary direction comparison は以下のテーブル:

| 比較 | baseline 候補 | direction の意味 |
|---|---|---|
| **single-turn pilot (PR #165) vs multi-turn pilot LoRA-on** | -- | protocol effect 規模 (paired diff、MEDIUM-5) |
| **multi-turn pilot LoRA-on vs matched baseline** | matched (downsampled) | primary scenario判定 (HIGH-2) |
| **multi-turn pilot no-LoRA control vs matched baseline** | matched | protocol main effect 単独 (HIGH-1) |
| **multi-turn pilot LoRA-on rank=8 vs no-LoRA control** | no-LoRA control | LoRA effect 単独 (HIGH-1) |
| multi-turn pilot LoRA-on vs historical Ollama baseline | historical | diagnostic only (window mismatch)|

### Consumer 経路 (PR #165 の consumer をそのまま再利用)

```bash
# Vendi semantic
.venv/Scripts/python.exe scripts/m9-c-adopt/compute_baseline_vendi.py \
  --persona kant --shards-glob "data/eval/m9-c-adopt-tier-b-pilot-multiturn/kant_r${r}_run*_stim.duckdb" \
  --kernel semantic --window-size 100 \
  --output ".steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-r${r}-vendi-semantic.json"

# Big5 ICC (SGLang LoRA-on)
.venv/Scripts/python.exe scripts/m9-c-adopt/compute_big5_icc.py \
  --persona kant --shards-glob "..." \
  --responder sglang --sglang-host http://127.0.0.1:30000 \
  --sglang-adapter "kant_r${r}_real" --temperature 0.7 --window-size 100 \
  --output ".steering/20260514-.../tier-b-icc-multiturn-kant-r${r}.json"

# Burrows (Option A、langdetect)
.venv/Scripts/python.exe scripts/m9-c-adopt/compute_burrows_delta.py \
  --persona kant --shards-glob "..." --window-size 100 \
  --output ".steering/20260514-.../tier-b-pilot-multiturn-kant-r${r}-burrows.json"
```

### Matrix 拡張 (`scripts/m9-c-adopt/da1_matrix.py`)

`--include-multiturn` flag を追加し、追加 row (rank=4/8/16 multi-turn) を baseline
+ single-turn pilot 行と並べて 4 軸 PASS/FAIL judgment を出力。Cohen's d は
single-turn と multi-turn の **両者** を baseline 比較として併報告 (direction
変化の規模を見るため)。

## 変更対象

### 修正するファイル
- `scripts/m9-c-adopt/tier_b_pilot.py` — multi-turn 採取拡張 (上記)
- `scripts/m9-c-adopt/da1_matrix.py` — `--include-multiturn` flag 追加

### 新規作成するファイル
- `.steering/20260514-m9-c-adopt-pilot-multiturn/{requirement,design,tasklist,decisions,blockers}.md`
- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-r{4,8,16}-vendi-semantic.json` (採取後)
- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-icc-multiturn-kant-r{4,8,16}.json` (採取後)
- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-r{4,8,16}-burrows.json` (採取後)
- `.steering/20260514-m9-c-adopt-pilot-multiturn/da1-matrix-multiturn-kant.json` (採取後)
- `.steering/20260514-m9-c-adopt-pilot-multiturn/report.md` (PR description 候補)
- `.steering/20260514-m9-c-adopt-pilot-multiturn/next-session-prompt-*.md` (シナリオ別)
- `.steering/20260514-m9-c-adopt-pilot-multiturn/codex-review-prompt.md` + `codex-review.md` (independent review)

### 削除するファイル
- なし

## 影響範囲

- `scripts/m9-c-adopt/tier_b_pilot.py` の `--multi-turn-max` default は `1` の
  ため、過去呼び出し (single-turn mode) との後方互換性は保たれる。PR #165 で
  実行した single-turn pilot 採取は再現可能。
- `data/eval/m9-c-adopt-tier-b-pilot/` (single-turn 既存 shard) は変更なし、
  新 directory `data/eval/m9-c-adopt-tier-b-pilot-multiturn/` を追加。
- consumer scripts (Vendi / ICC / Burrows / da1_matrix) は本 PR 内で `--shards-glob`
  + `--output` 引数で multi-turn pilot を指定するだけで再利用可能、本体ロジックは
  変更なし。

## 既存パターンとの整合性

- baseline `GoldenBaselineDriver.run_stimulus()` の alternating speaker pattern を
  忠実に再現 (turn_index % 2 == 0 → focal、% 2 == 1 → interlocutor)。
- baseline stimulus inference_fn の "del persona_id, prior_turns" 設計を維持 —
  multi-turn pilot 側でも prior_turns を SGLang に渡さない。
- DuckDB schema (`raw_dialog.dialog`) は既存のまま、`turn_index` を 0..N-1 で
  記録、`speaker_persona_id` で alternating。
- run_id 命名は `{persona}_r{rank}_run{idx}_pilot` (single-turn と同形式、
  shard path の subdir で multi-turn 識別可)。
- checkpoint state schema 既存のまま (`pilot_state` table)。

## テスト戦略

- **単体テスト**: pilot driver の logic は既存単体テストなし (PR #165 で smoke
  test を script 直接実行で済ませた経緯)。本 PR では smoke test として
  `--turn-count 10 --multi-turn-max 6` で kant_r8_real adapter を 1 cycle 走らせ、
  DuckDB shard に turn_index 0..N-1 が alternating speaker で書き込まれていることを
  目視確認。
- **統合テスト**: 6 shard 採取完遂が事実上の統合テスト。consumer (Vendi/ICC/Burrows)
  が multi-turn shard を正しく読めるか (`raw_dialog.dialog` schema 不変なので
  問題ないはず)。
- **E2E テスト**: 不要 (本 PR は investigation script、live path 統合は Phase D)。

### Smoke test (実装後即実行)

```bash
.venv/Scripts/python.exe scripts/m9-c-adopt/tier_b_pilot.py \
  --persona kant --rank 8 --run-idx 0 \
  --turn-count 10 --cycle-count 2 --multi-turn-max 6 \
  --sglang-host http://127.0.0.1:30000 \
  --output data/eval/m9-c-adopt-tier-b-pilot-multiturn/_smoke_kant_r8_run0.duckdb \
  --skip-adapter-check
# 期待: 終了 rc=0、DuckDB 内に turn_index 0/1/0/1/... の row が ~10 focal + interlocutor 数
duckdb data/eval/m9-c-adopt-tier-b-pilot-multiturn/_smoke_kant_r8_run0.duckdb \
  "SELECT speaker_persona_id, turn_index, count(*) FROM raw_dialog.dialog GROUP BY 1,2 ORDER BY 1,2"
```

### Post-capture validation query (HIGH-4 反映、DA-13 acceptance gate)

採取後に全 8 shard (6 LoRA-on + 2 no-LoRA control) に対して以下を実行、
`validation-multiturn-kant.json` に集約。**全 check PASS** が DA-13 publish の
precondition:

```sql
-- Check 1: speaker_persona_id × turn_index distribution
SELECT speaker_persona_id, turn_index, count(*) FROM raw_dialog.dialog
GROUP BY 1, 2 ORDER BY 1, 2;
-- 期待: focal rows on turn_index ∈ {0, 2}, interlocutor rows on {1}

-- Check 2: focal count == target
SELECT count(*) FROM raw_dialog.dialog WHERE speaker_persona_id = 'kant';
-- 期待: focal_target (300) ± 5% per shard

-- Check 3: incomplete dialog detect
SELECT dialog_id, min(turn_index), max(turn_index), count(*)
FROM raw_dialog.dialog
GROUP BY dialog_id
HAVING max(turn_index) - min(turn_index) + 1 != count(*);
-- 期待: 0 rows (no partial dialogs from MEDIUM-3 atomic resume)

-- Check 4: focal-only consumer simulation
SELECT count(*) FROM raw_dialog.dialog WHERE speaker_persona_id NOT IN ('kant');
-- 期待: consumer はこの行を SELECT しない (filter 確認用)
```

## ロールバック計画

- pilot driver multi-turn 拡張は **default 1 で過去互換**、worst-case で
  `--multi-turn-max` を渡さなければ完全に single-turn pilot と同じ挙動。
- 新 directory `data/eval/m9-c-adopt-tier-b-pilot-multiturn/` への shard 書き出しは
  既存 single-turn shard と分離、削除のみで rollback 可能。
- DA-13 ADR は新規追加、DA-12 verdict は本 PR で revise しない (本 PR は DA-12 の
  empirical follow-up であり、DA-12 自体は immutable record)。

## 主要設計判断 (Codex independent review 対象)

1. **interlocutor 設計**: baseline の "same inference_fn for both speakers" 設計を
   忠実に再現する選択は妥当か? 代替案として "interlocutor は no-LoRA Ollama
   経由 (混在 backend)" や "interlocutor は固定 utterance (no-op)" を検討したが、
   baseline と同 protocol で対比するには same-inference-fn が最も apples-to-apples。
2. **`expected_turn_count` の handling**: `--multi-turn-max 6` で全 stimulus の
   1-3 turn を superset として cover、clamp は actual に発火しない (= 全 stim の
   expected_turn_count に従う)。これは methodology confound 切り分けに正しいか?
3. **focal turn budget の数え方**: baseline と同じ `ceil(N/2)` で focal speaker
   turn 数を見積もる approach は正しいか? 300 focal turn 目標時の total turn 数
   (focal + interlocutor) はどうなる?
4. **prior_turns を渡さない (delete) 選択**: baseline でも勝手にも捨てているので
   apples-to-apples だが、これは "本来の multi-turn 効果" を測れないことを意味する。
   methodology confound vs LoRA failure の identifiability を本当に切り分けられるか?
5. **シナリオ判定の criteria**: Vendi direction が逆転 (LoRA-on < baseline) =
   シナリオ I (methodology confound 主因) と認定する operational criterion は
   robust か? "改善するが thresholds 未達" = シナリオ III の境界 (両者 partial) は
   どう測るか?

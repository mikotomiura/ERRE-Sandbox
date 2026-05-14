Recorded the full review in [codex-review.md](C:/ERRE-Sand_Box/.steering/20260514-m9-c-adopt-pilot-multiturn/codex-review.md:1).

**Overall verdict: MODIFY before implementation.**

**HIGH**
- Scenario I overclaims identifiability. A direction reversal would show that baseline-style no-prior repeated prompting changes the metric, but it would not prove “methodology confound dominant” over LoRA conditional effects, backend/template effects, or windowing artifacts. See [requirement.md](C:/ERRE-Sand_Box/.steering/20260514-m9-c-adopt-pilot-multiturn/requirement.md:17), [design.md](C:/ERRE-Sand_Box/.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:204), [eval_run_golden.py](C:/ERRE-Sand_Box/src/erre_sandbox/cli/eval_run_golden.py:455).
- Baseline parity is incomplete. Planned pilot remains `300 focal × 2 runs = ~6 windows/rank`, while baseline is 25 windows / 2500 focal utterances. That leaves stimulus coverage and window-count confounds. See [design.md](C:/ERRE-Sand_Box/.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:82), [tier-b-baseline-kant-vendi-semantic.json](C:/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/tier-b-baseline-kant-vendi-semantic.json:7), [tier-b-baseline-kant-burrows.json](C:/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/tier-b-baseline-kant-burrows.json:13).
- Scenario thresholds need pre-registration. Vendi-only reversal is not enough because DA-12 failure was Vendi + Burrows. Define CI/direction criteria and mixed-rank handling before sampling. See [design.md](C:/ERRE-Sand_Box/.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:207), [decisions.md](C:/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/decisions.md:680).
- Smoke-only verification is too weak. Add automated assertions for focal/interlocutor tagging, turn_index distribution, focal-only consumer input, and shard validation. Consumers do filter focal rows, but the new producer must prove it writes them correctly.

**MEDIUM**
- Keep `prior_turns` excluded for core baseline parity, but document that this does not measure true dialog context. A rank=8 prior-turns adjunct can inform Phase E.
- Update compute estimate: planned 300 focal/run is about 534 stimulus calls/run, about 3204 SGLang capture calls total, plus about 900 ICC IPIP calls.
- Fix resume semantics so partial multi-turn dialogs cannot remain after a mid-stimulus failure.
- Report ICC(A,1), but do not use it as a multi-turn protocol diagnostic because the ICC consumer intentionally ignores utterance window content.
- Add paired single-turn vs multi-turn per-stimulus diagnostics.

No tests were run; this was a design/code-path review plus the review artifact write.
c-adopt-pilot-multiturn/design.md:77`
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:82`
  - `.steering/20260513-m9-c-adopt/tier-b-baseline-kant-vendi-semantic.json:7`
  - `.steering/20260513-m9-c-adopt/tier-b-baseline-kant-vendi-semantic.json:9`
  - `.steering/20260513-m9-c-adopt/tier-b-baseline-kant-burrows.json:12`
  - `.steering/20260513-m9-c-adopt/tier-b-baseline-kant-burrows.json:13`
  - `.steering/20260513-m9-c-adopt/tier-b-pilot-kant-r8-vendi-semantic.json:7`
  - `.steering/20260513-m9-c-adopt/tier-b-pilot-kant-r8-vendi-semantic.json:9`
- **問題**: design は baseline protocol parity を主張するが、planned pilot は
  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
  とどまる。一方 historical baseline は Vendi/Burrows とも 25 windows / 2500 focal
  utterances を使っている。さらに proposed `_focal_turn_count=ceil(N/2)` では
  Kant battery の full focal capacity は 88/battery なので、target_per_cycle=50 は
  full battery ではなく subset slice になる。これは single-turn vs multi-turn 以外の
  stimulus coverage / windowing confound を残す。
- **根拠**:
  - baseline Vendi は `window_size=100`, `total_windows=25`
    (`tier-b-baseline-kant-vendi-semantic.json:7`, `:9`)。
  - baseline Burrows は `total_utterances_seen=2500`
    (`tier-b-baseline-kant-burrows.json:12-13`)。
  - existing pilot は `total_windows=6`
    (`tier-b-pilot-kant-r8-vendi-semantic.json:7-9`)。
  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
    (`design.md:82`)。
  - proposed focal accounting and Kant distribution imply full battery
    88 focal / 148 total turns; target 50 focal/cycle selects a subset rather
    than the baseline-like full battery.
- **mitigation**:
  1. Apples-to-apples pilot を名乗るなら `--turn-count` を 500+ focal/run に上げ、
     `target_per_cycle >= 88` で full 70-stimulus battery を毎 cycle 回す。
     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
  2. 300 focal/run を維持するなら、baseline 側も exact same selected stimulus
     slice + same number of windows に downsample/recompute した matched baseline を
     作り、primary comparison は matched baseline にする。
  3. DA-13 には historical baseline comparison と matched comparison を分けて
     記録する。
- **verdict**: MODIFY

### HIGH-3 — Scenario criteria are under-specified and can move after seeing data

- **箇所**:
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/requirement.md:57`
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/requirement.md:61`
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/requirement.md:63`
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:108`
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:207`
  - `scripts/m9-c-adopt/da1_matrix.py:129`
  - `scripts/m9-c-adopt/da1_matrix.py:136`
  - `scripts/m9-c-adopt/da1_matrix.py:144`
  - `.steering/20260513-m9-c-adopt/decisions.md:680`
  - `.steering/20260513-m9-c-adopt/decisions.md:682`
- **問題**: Scenario I/II/III/IV の operational threshold が未定義。特に scenario
  I は Vendi のみで書かれているが、DA-12 の direction failure は Vendi semantic
  と Burrows Δ の両方で発生している。Vendi だけが反転し Burrows が失敗した場合、
  "methodology dominant" と close する根拠が弱い。
- **根拠**:
  - DA-12 は Vendi d positive と Burrows reduction negative の両方を direction
    failure としている (`decisions.md:680-683`)。
  - matrix script は Vendi axis と Burrows axis を別判定している
    (`da1_matrix.py:129-156`)。
  - design の scenario criteria は "direction が逆転" と "thresholds 未達" の
    境界を数式化していない (`design.md:207-210`)。
- **mitigation**:
  1. 採取前に DA-13 draft へ判定規則を固定する。
  2. Scenario I は少なくとも primary rank=8 で:
     - Vendi: multi-turn LoRA point < matched baseline point, and bootstrap CI
       for `(LoRA - matched_baseline)` has upper bound < 0。
     - Burrows: reduction point > 0 and CI lower > 0。DA-1 adoption まで進めるなら
       reduction >= 10% も必要。
     - mixed ranks は "rank-specific" とし、2/3 rank 以上が同方向でない限り
       methodology dominant と書かない。
  3. Scenario III は "single-turn からの改善量" を preregister する。例:
     `d_multi - d_single <= -0.5` だが CI が 0 を跨ぐ、または Vendi/Burrows の
     片方のみ改善。
- **verdict**: MODIFY

### HIGH-4 — Smoke-only, visual verification is insufficient for this empirical claim

- **箇所**:
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:157`
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:159`
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:164`
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:178`
  - `scripts/m9-c-adopt/compute_baseline_vendi.py:54`
  - `scripts/m9-c-adopt/compute_big5_icc.py:86`
  - `scripts/m9-c-adopt/compute_burrows_delta.py:75`
- **問題**: design は schema unchanged なので consumers は問題ないはず、としているが、
  この PR の empirical claim は `speaker_persona_id` filter、turn_index、focal
  accounting が正しく動くことに依存する。目視 smoke だけだと、interlocutor 混入や
  focal count drift が起きても見逃しやすい。
- **根拠**:
  - consumers は実際には `WHERE speaker_persona_id = ?` で focal のみ読む
    (`compute_baseline_vendi.py:54-63`, `compute_big5_icc.py:86-96`,
    `compute_burrows_delta.py:75-84`)。ここは design の主張どおりだが、
    new pilot shard 側の speaker tagging を自動検証する必要がある。
- **mitigation**:
  1. unit/smoke を最低 1 本追加し、synthetic 1/2/3-turn stimuli で
     `total_rows`, focal rows, interlocutor rows, `turn_index` distribution,
     `speaker_persona_id` alternation, consumer `_load_focal_utterances()` の
     focal-only behavior を assert する。
  2. full 6 shard 採取後に validation query を artefact 化する:
     `speaker_persona_id × turn_index`, distinct `dialog_id`, focal count,
     total count, rows where interlocutor appears in focal consumer input = 0。
  3. この validation を DA-13 の acceptance gate にする。
- **verdict**: MODIFY

## MEDIUM

### MEDIUM-1 — prior_turns inclusion は core ではなく adjunct として扱う

- **箇所**:
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:149`
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:204`
  - `src/erre_sandbox/evidence/golden_baseline.py:392`
  - `src/erre_sandbox/evidence/golden_baseline.py:405`
  - `src/erre_sandbox/evidence/golden_baseline.py:417`
- **判断**: baseline parity を主目的にするなら no-prior は妥当。ただし
  "本来の multi-turn dialog effect" は測れないので、scenario conclusion では
  明示する必要がある。
- **mitigation**: rank=8 だけ optional `--prior-turns-mode include` を別 artefact として
  採取し、Phase E A-6 の design input にする。primary DA-12 closure には使わない。
- **verdict**: ADOPT-WITH-NOTE

### MEDIUM-2 — Focal/total compute budget は 534 turn/shard + ICC calls で見積もる

- **箇所**:
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:82`
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:201`
- **判断**: Kant YAML distribution と proposed focal count では、300 focal/run
  は概算 534 total generation calls/run になる。6 shard で約 3204 SGLang
  stimulus calls。Big5 ICC は 6 windows/rank × 50 items × 3 rank = 約 900
  SGLang IPIP calls も別に発生する。
- **mitigation**: design/decisions に capture calls と ICC calls を分けて記載する。
  HIGH-2 の full-battery parity を採用するなら、capture は約 5328 calls、
  ICC は約 1500 calls に更新する。
- **verdict**: MODIFY

### MEDIUM-3 — Checkpoint resume must not leave partial multi-turn dialogs in shards

- **箇所**:
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:71`
  - `scripts/m9-c-adopt/tier_b_pilot.py:447`
  - `scripts/m9-c-adopt/tier_b_pilot.py:452`
  - `scripts/m9-c-adopt/tier_b_pilot.py:480`
- **問題**: current resume model skips the recorded `last_stimulus_id`. In multi-turn,
  a failure after turn 0/1 but before turn 2 can leave a partial dialog in the shard and
  skip the remainder on resume.
- **mitigation**: on fatal error, delete rows for the in-progress `dialog_id` before
  checkpointing, or checkpoint before starting each stimulus and re-run the whole
  stimulus after resume. Add a validation query for incomplete `dialog_id` turn ranges.
- **verdict**: MODIFY

### MEDIUM-4 — ICC(A,1) is useful but not a multi-turn protocol diagnostic

- **箇所**:
  - `scripts/m9-c-adopt/compute_big5_icc.py:16`
  - `scripts/m9-c-adopt/compute_big5_icc.py:17`
  - `scripts/m9-c-adopt/compute_big5_icc.py:270`
  - `.steering/20260513-m9-c-adopt/decisions.md:730`
  - `.steering/20260513-m9-c-adopt/decisions.md:734`
- **判断**: ICC(A,1) should be reported as LoRA self-report shift diagnostic, but it
  cannot tell whether multi-turn stimulus text changed persona-fit because
  `compute_big5_icc.py` deliberately does not condition on window utterances.
- **mitigation**: include ICC(A,1) in report, but do not use it to decide scenario I/II.
- **verdict**: ADOPT-WITH-NOTE

### MEDIUM-5 — Existing single-turn vs multi-turn paired diff should be included

- **箇所**:
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:108`
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:110`
- **判断**: Paired per-stimulus diff is the cheapest way to see whether direction
  movement is driven by turn=2 additions, category/stimulus mix, or broad windowing.
- **mitigation**: output a diagnostic table by `stimulus_id` / `turn_index`:
  single-turn turn=0 vs multi-turn turn=0; multi-turn turn=2 contribution for
  3-turn stimuli; Vendi/Burrows window membership.
- **verdict**: MODIFY

## LOW

### LOW-1 — Wording: avoid calling the baseline a true multi-turn dialog without qualifier

- **箇所**:
  - `.steering/20260513-m9-c-adopt/decisions.md:717`
  - `.steering/20260513-m9-c-adopt/blockers.md:255`
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:20`
- **問題**: baseline has alternating speaker metadata, but generation is no-prior
  repeated stimulus prompting. Calling it simply "multi-turn dialog" invites a
  stronger interpretation than the code supports.
- **mitigation**: use "baseline-style no-prior alternating-speaker stimulus protocol"
  or "multi-turn metadata / no-prior generation protocol".
- **verdict**: MODIFY

### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing

- **箇所**:
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:38`
  - `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md:198`
- **判断**: Kant stimulus max is 3; `6` does not fire. This is fine, but readers may
  wonder why 6 is used.
- **mitigation**: add "current Kant max expected_turn_count is 3; 6 is a no-op cap for
  future batteries".
- **verdict**: ADOPT-WITH-NOTE

## Overall Verdict

**MODIFY before implementation.**

The implementation approach is close to the historical baseline mechanics: it correctly
mirrors alternating speaker metadata, no-prior stimulus inference, and focal-only consumer
filtering. However, the current design does **not** fully identify methodology confound
vs LoRA failure. It can at most show whether a baseline-style no-prior repeated-prompt
sampling protocol changes the observed direction under the existing consumers. To support
DA-12 closure, the PR needs matched baseline/control comparisons, pre-registered scenario
thresholds, and automated validation that the new shards actually feed only focal turns
to the consumers.

# Codex independent review — m9-eval-system P3a-decide v2 (cooldown × cognition_period)

> Codex `gpt-5.5 xhigh` independent review request. Prompt として
> `cat .steering/20260430-m9-eval-system/codex-review-prompt-natural-gating-v2.md
> | codex exec --skip-git-repo-check` で起動。
> 出力は `codex-review-natural-gating-v2.md` に verbatim 保存。本 review は
> v1 (`codex-review-natural-gating.md`、Verdict: ship) の **後続**で、v1 の
> fix がデプロイされた後の empirical observation で別の dominant gate が
> 露呈したため。

---

## Context

You previously reviewed and shipped a fix (Verdict: ship, HIGH=0/MEDIUM=0/
LOW=2) for m9-eval-system P3a natural-condition pilot stalling. The fix
added `InMemoryDialogScheduler.eval_natural_mode: bool = False` flag that
bypasses zone-equality and reflective-zone gates so 3 personas can
sustain dialog after LLM-driven `destination_zone` scatters them.

**The fix worked partially**. G-GEAR Phase A re-capture (PR #131) showed:

| 指標 | v1 修正前 | v1 期待 | v1 修正後 実測 |
|---|---|---|---|
| focal_rows (kant) | 6 | 30 | **6** |
| total_rows | 12 | ~90 | **18** |
| dialogs | 2 | ~10 | **3** |
| nietzsche admit | 0 (starved) | included | **2 dialogs** ✅ |
| wall | 13 min (kill) | 5-8 min | **10 min wall timeout** |

**Zone scatter (hypothesis D) is solved** — Nietzsche starve is gone,
all 3 pairs admit at least once. But all 18 turns happened in `tick=1..5`,
then **8 minutes of zero admits**.

## Re-activated dominant gate (hypothesis B from design v1)

design v1 §2 **rejected** hypothesis B with the rationale "world_tick 50+
in 13 min wall makes 30-tick cooldown < 30% of wall, so cooldown alone
can't explain stall." That premise was **wrong empirically**:

```
empirical: 600 s wall → max(world_tick) = 5 ⇒ 1 tick ≈ 120 s
root cause: qwen3:8b Q4_K_M on RTX 5060 Ti — reflection (embed + chat) +
            action selection (chat) + dialog turn (chat × 6) accumulate as
            serial round-trips, blocking cognition tick advance
effective cooldown: COOLDOWN_TICKS=30 × 120 s = 60 min wall
                   ⇒ within 10 min wall, same pair re-admit is physically
                     impossible
```

`g-gear-phase-a-failure.md` (PR #131) inter-turn delta confirms: 18
utterances clustered in ~95 s burst, then 8 min plateau with no admits
even though Reflection trigger logs show cognition is alive (Reflection
fires every ~30 s after burst — tick rate ~1/30 s during reflection-only
phase, but ~1/120 s during dialog phase).

## Candidate space (G-GEAR §4 + Mac /reimagine)

G-GEAR proposed 5 candidates. Mac added 3 reimagine alternatives (ζ/θ/ι).

| 案 | 内容 | 実装複雑度 | 概念純度 | empirical 必達 | test impact |
|---|---|---|---|---|---|
| α | eval mode で COOLDOWN_TICKS=5 | 低 | 中 | 高 | 低 |
| β | wall budget 30→60 min for natural | 低 (CLI default) | 高 | 中 | 無 |
| γ | AUTO_FIRE_PROB_PER_TICK=1.0 | 低 | 中 | 低 (cooldown dominant) | 中 |
| δ | 1 cell 逐次採取 | 低 | 中 | 低 (cognition_period 不変) | 無 |
| ε | dialog_turn_budget 6→3 | 中 | 低 (stylo signal 薄) | 中 | 中 |
| **ζ** *(reimagine)* | wall-time-based cooldown (`time.monotonic()`) | 中 | 高 | 高 | 中 |
| **θ** *(reimagine)* | cooldown 完全廃止 + prob のみ | 低 | 中 | 中 | 低 |
| **ι** *(reimagine)* | β+δ ハイブリッド (cooldown 不変、wall 大、cell 逐次) | 低 | **最高** | 中 (3h × 3 cell) | 無 |

## Proposed fix v2: α + β hybrid

### Adopted rationale

1. **empirical 必達確率が高い**: 60 min wall × cooldown=5 ticks ⇒ 30 ticks /
   5 ticks per cycle ≈ 5-6 cycle ⇒ focal kant ≈ 30 (target 達成)
2. **実装最小**: `COOLDOWN_TICKS_EVAL: ClassVar[int] = 5` 別定数化 +
   `_effective_cooldown()` helper + CLI default 30→60 min の 3 箇所変更
3. **既存 test 完全互換**: live mode の `COOLDOWN_TICKS=30` 不変、既存 1248 PASS 維持
4. **ME-8 invariant 後退最小**: "cooldown active" → "cooldown active with
   eval-mode-specific reduced threshold" に文言更新するのみ、cooldown 概念自体は保持
5. **reimagine 代案で全敗**: ζ は M4 frozen Protocol 純粋関数性違反、θ は dominant
   gate 移転 (cooldown→prob)、ι は wall 12h × overnight × multi-run で運用コスト許容外

### Diff sketch

```python
# src/erre_sandbox/integration/dialog.py
class InMemoryDialogScheduler:
    COOLDOWN_TICKS: ClassVar[int] = 30  # live (unchanged)
    COOLDOWN_TICKS_EVAL: ClassVar[int] = 5  # NEW eval_natural_mode 限定

    def _effective_cooldown(self) -> int:
        return self.COOLDOWN_TICKS_EVAL if self.eval_natural_mode else self.COOLDOWN_TICKS

    # schedule_initiate (existing line ~200):
    if (
        last_close is not None
        and tick - last_close < self._effective_cooldown()  # was self.COOLDOWN_TICKS
        and not self.golden_baseline_mode
    ):
        return None

    # tick() (existing line ~337):
    if last_close is not None and world_tick - last_close < self._effective_cooldown():
        continue  # was self.COOLDOWN_TICKS
```

```python
# src/erre_sandbox/cli/eval_run_golden.py
# capture_natural の click option:
@click.option(
    "--wall-timeout-min",
    type=int,
    default=60,  # was 30
    help="Maximum wall-clock minutes for the natural capture phase.",
)
```

### Test plan (12→16 cases in test_dialog_eval_natural_mode.py)

1. **`test_eval_mode_uses_reduced_cooldown`**: eval_natural_mode=True で同一 pair が
   tick 5 後に再 admit 可能、tick 4 では reject
2. **`test_live_mode_cooldown_unchanged`**: eval_natural_mode=False で
   COOLDOWN_TICKS=30 が active、tick 29 で reject / tick 30 で admit
3. **`test_effective_cooldown_returns_correct_value`**: helper の純関数 contract
4. **`test_class_constants_unchanged`**: `COOLDOWN_TICKS == 30` /
   `COOLDOWN_TICKS_EVAL == 5` の sentinel test

CLI test に `--wall-timeout-min default=60` の 1 ケース追加。

### ME-8 ADR §invariant の partial-update

v1 ADR で「Cooldown / probability / timeout / 自己 dialog reject / 二重 open reject の
invariant は両 mode で active のまま」と書いた箇所を以下に Edit:

> **Cooldown (eval-mode 別 threshold = `COOLDOWN_TICKS_EVAL=5`、live は
> `COOLDOWN_TICKS=30`)** / probability / timeout / 自己 dialog reject /
> 二重 open reject の invariant は両 mode で active のまま — eval natural cadence
> は維持、proximity 制約のみ削除 + cooldown threshold を eval mode で reduce。

### 期待される empirical 値 (G-GEAR rerun)

```
60 min wall × 1 tick / 120 s = 30 ticks 進行
cooldown=5 ticks per cycle、prob 0.25 込みで実効 ~6 cycle  (G-GEAR 計算)
3 dialogs × 6 turns × 5 cycle ~= 90 utterance
focal kant per cell ≈ 90 / 3 = 30 ✓
```

ただし AUTO_FIRE_PROB_PER_TICK=0.25 の variance を加味した realistic estimate は:
```
1 cycle = 6 ticks (turn) + 5 ticks (cooldown) = 11 ticks/cycle
60 min wall × 30 ticks / 11 ticks per cycle ≈ 2.7 cycle
2.7 × 18 utt = 49 utterance/cell
focal kant per cell ≈ 16-30 (variance あり)
```

→ default=60 min は最低保証、不足なら 90/120 min に上げる。

## Specific questions to Codex

Please return findings in HIGH / MEDIUM / LOW format with file:line refs.
Particular concerns:

- **Q1**: §2.4 ι (β+δ ハイブリッド = cooldown semantics 不変 + 4h wall + 1 cell 逐次)
  を「wall 爆発」で棄却したが、ME-8 invariant 後退ゼロという観点で本当は ι が
  正解では？α+β は ME-8 ADR の invariant を後退させる semantic cost を払うが、
  ι は払わない。empirical wall コスト (12h × overnight) は許容外と判断したが、
  これは scoping bias で過剰に α+β に寄せていないか？
- **Q2**: `COOLDOWN_TICKS_EVAL=5` を hardcoded class const にしたが、CLI
  `--cooldown-ticks-eval N` で override 可能にすべきか？将来 cognition_period
  が変動した時の柔軟性 vs hardcoded sentinel test の robustness の trade-off。
- **Q3**: §5 リスク 2 で realistic estimate が focal=16-30 と margin が薄いと自己
  認定した。`--wall-timeout-min default=60` ではなく `default=90` にすべきか？
  90 min なら realistic 4 cycle = 72 utt = focal 24/cell が下限保証 (mean 30+)。
- **Q4**: ME-8 §invariant 文言の "active with reduced threshold" は v1 contract
  に対し silent な後退ではないか？v1 では "active" を厳格定義としていた可能性、
  本 v2 で文言を緩めるのは ADR re-open のままで OK か (新 ADR child 起票が必要か)。
- **Q5**: §3.3.3 で追加した 4 test のうち `test_class_constants_unchanged` は
  sentinel test として over-defensive ではないか？将来 COOLDOWN_TICKS_EVAL の
  empirical 再校正で値変更があった場合に false positive で test 落ちる。
- **Q6**: dialog_turn_budget=6 と reduced cooldown=5 の組合せで「close 直後 (tick T)
  → cooldown 抜け (tick T+5) → 即再 admit」が同 pair で連発する "ピンポン admit"
  が起こり得る。これは natural cadence の semantics 上問題ないか？dialog_turn_budget
  が同 pair 占有を最低 6 ticks 保証するので indirect には防がれるが、明示的な
  "minimum gap between dialogs of same pair" として cooldown=5 で意味的に十分か。
- **Q7**: §2 候補空間 で **γ (AUTO_FIRE_PROB_PER_TICK=1.0) を「cooldown が dominant
  gate のため効果限定」**と棄却したが、本 v2 で α+β に切り替えた後は **prob 0.25 の
  variance が新たな副次 dominant gate になる可能性**。realistic estimate の variance
  を抑えるため eval mode で prob=1.0 に上げる組合せ案 (= α+β+γ ハイブリッド) は
  考慮するべきでないか？
- **Q8**: design v1 では "Cooldown / probability / timeout は active のまま (natural
  cadence 保持)" を core invariant として claim したが、empirical で cognition_period
  120 s/tick が判明した今、cooldown=30 ticks の意味は live mode (cognition_period
  ~10 s/tick 想定) と eval mode で全く別物。**M4 frozen Protocol の "tick ベース
  cooldown" 抽象化自体が漏れている**のではないか (= ζ wall-time cooldown が本来正解
  だが overscoping で defer して良いか)。

## Files to consult (relative to repo root)

- `.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md` (本 design v2)
- `.steering/20260430-m9-eval-system/design-natural-gating-fix.md` (v1)
- `.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md` (PR #131 empirical report)
- `.steering/20260430-m9-eval-system/decisions.md` ME-8 ADR (v1)
- `.steering/20260430-m9-eval-system/codex-review-natural-gating.md` (v1 verdict)
- `src/erre_sandbox/integration/dialog.py` (修正対象、特に line 89-95 / 200-210 / 337)
- `src/erre_sandbox/cli/eval_run_golden.py` (`capture_natural` の click options)
- `tests/test_integration/test_dialog_eval_natural_mode.py` (12 既存 test、4 追加予定)

## Output format requested

```
## Verdict
[ship | revise | reject] — one-line summary

## HIGH (must fix before merge)
HIGH-1 ...  file:line + finding + recommendation

## MEDIUM (should consider)
MEDIUM-1 ...

## LOW (nice to have)
LOW-1 ...

## Answers to Q1-Q8
Q1: ...
Q2: ...
...
```

## Token budget reminder

`.codex/budget.json` daily=1M、本日 used=337,503 (~33%)。本 invocation は
per_invocation_max=200K 範囲内で完了させること。`gpt-5.5 xhigh` で。

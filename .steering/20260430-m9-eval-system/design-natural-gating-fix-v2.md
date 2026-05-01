# M5/M6 natural runtime gating bug — design v2 (P3a-decide v2)

> Plan-mode 等価ドキュメント (auto-mode 内 "Plan + /reimagine + Codex review"
> CLAUDE.md 制約)。本ファイルで初期案 + reimagine 代案 + 採用案 + Codex review
> 反映を一元化する。**design v1 (`design-natural-gating-fix.md`) の続編**:
> v1 は仮説 D (zone scatter) を解決したが、empirical で仮説 B (cooldown ×
> cognition_period の wall 換算) が re-activate された (PR #131
> `g-gear-phase-a-failure.md` 参照)。

## 1. v2 を起草する empirical 根拠

### 1.1 v1 fix 後の G-GEAR Phase A 観測 (PR #131)

| 指標 | v1 修正前 (PR #129) | v1 期待値 | **v1 修正後 実測 (本セッション根拠)** |
|---|---|---|---|
| focal_rows (kant) | 6 | 30 | **6** |
| total_rows | 12 | ~90 | **18** |
| dialogs | 2 | ~10 | **3** |
| nietzsche admit | 0 (starved) | included | **2 dialogs** ✅ |
| wall | 13 min (kill) | 5-8 min | **10 min wall timeout** |

**v1 の効果**: nietzsche starve は解消 (zone bypass が機能)、3 pair 全部 admit。
**v1 で未解決**: 18 turn 全部が tick 1-5 内、tick=5 以降 8 min 0 admit (= cooldown 中)。

### 1.2 dominant gate の empirical 確定

```
empirical: 600 s wall → max(world_tick) = 5 ⇒ 1 tick ≈ 120 s
原因: qwen3:8b Q4_K_M on RTX 5060 Ti で
      reflection embed + chat + action selection + dialog turn × 6 が
      serial round-trip で蓄積、cognition tick advance を blocking
```

実効 cooldown = `COOLDOWN_TICKS=30` × 120 s/tick = **60 min wall**
⇒ 10 min wall 内で同一 pair が再 admit されるのは物理的に不可能。

### 1.3 design v1 §2 仮説 B の再評価

design v1 は仮説 B を「△ 補助」とし、棄却根拠として以下を引いた:
> kant_natural 13 min wall で nietzsche cognition_period=7s + WorldRuntime
> DEFAULT_COGNITION_PERIOD_S=10s → world_tick は 50+ 進むはず

これは **誤った前提**。実機の 7B-Q4 ローカル推論では LLM round-trip が
cognition_period の名目値を完全に upper-bound として支配しない。本 design v2
では仮説 B を「◎ 主因」に格上げし、design v1 §2 の判断を v2 §1 で **明示的に
覆す**。

## 2. 候補空間 (G-GEAR §4 の 5 案 + /reimagine 代案 3)

G-GEAR `g-gear-phase-a-failure.md` §4 の 5 案 + 本 Mac セッションの /reimagine
で 3 案追加 (ζ / θ / ι)。

| 案 | 内容 | 実装複雑度 | 概念純度 | empirical 必達確率 | test impact |
|---|---|---|---|---|---|
| α | eval mode で COOLDOWN_TICKS=5 (現状 30) | 低 | 中 | 高 (10 min wall × 5 ticks/cooldown 必要) | 低 |
| β | wall budget 30→60 min for natural | 低 (CLI flag default 変更) | 高 | 中 (cooldown=30 単独では 1 cycle のみ) | 無 |
| γ | AUTO_FIRE_PROB_PER_TICK 0.25→1.0 | 低 | 中 | 低 (cooldown が dominant gate のため効果限定) | 中 |
| δ | 1 cell 逐次採取 (3 並列廃止) | 低 (CLI 運用変更) | 中 | 低 (cognition_period 不変、wall 単純倍化のみ) | 無 |
| ε | dialog_turn_budget 6→3 | 中 | 低 (per-dialog stylo signal が薄まる) | 中 | 中 |
| **ζ** *(reimagine)* | wall-time-based cooldown (`time.monotonic()`) | 中 (monotonic 経路 + monkeypatch test) | 高 (tick rate 変動に robust) | 高 | 中 |
| **θ** *(reimagine)* | cooldown 完全廃止 + AUTO_FIRE_PROB_PER_TICK のみ | 低 | 中 (prob が gate に) | 中 (prob 0.25 で variability 大) | 低 |
| **ι** *(reimagine)* | β + δ ハイブリッド (cooldown 不変、wall 大拡張、cell 逐次) | 低 | **最高** (cooldown semantics 不変) | 中 (3h × 3 cell = 9h、overnight) | 無 |

### 2.1 G-GEAR 推奨 α + β ハイブリッドの empirical 計算

```
60 min wall × 1 tick / 120 s = 30 ticks 進行
cooldown=5 ticks × 120 s/tick = 10 min wall cooldown
30 ticks / 5 ticks per cycle ≈ 6 cycle (G-GEAR 計算 5 cycle、prob 0.25 込みで)
3 dialogs × 6 turns × 5 cycle = 90 utterance
focal kant per cell ≈ 90 × (1/3) = 30 ✓ (target 達成)
```

### 2.2 /reimagine 代案 ζ (wall-time cooldown) の検討

**仮想実装**:
```python
import time
self._last_close_wall: dict[frozenset[str], float] = {}

# schedule_initiate / tick で:
last_close_wall = self._last_close_wall.get(key)
if last_close_wall is not None and (time.monotonic() - last_close_wall) < COOLDOWN_WALL_S:
    return None
```

**利点**:
1. tick rate (cognition_period) の変動に対し robust。将来 FP16 化で cognition_period が
   60 s/tick に半減しても cooldown semantics が崩れない。
2. 「natural cadence 1 min = 1 dialog 開始」という人間直感と一致。

**欠点**:
1. **M4 frozen Protocol の純粋関数性違反**: `DialogScheduler` Protocol は tick ベースの
   deterministic semantics で、`time.monotonic()` 注入は副作用源を増やす。test では
   `monkeypatch time.monotonic` が全 cooldown test に必要 (現状 1228+ test の cooldown
   関連 ~20 件全部に影響)。
2. ManualClock + tick 駆動の既存 test fixture を破壊。
3. CLAUDE.md "コードに既存パターンに従う" 原則違反 (cooldown は M4 から tick ベース)。
4. eval mode 専用 → 別経路 if 分岐 → コード経路 fork、ME-8 invariant を二重定義することに。

**評価**: ζ は overscoping。本タスクのターゲットは "natural pilot 30 focal を 60 min wall
で完走" であり、将来の cognition_period 変動 robustness は本タスクスコープ外。本タスクで
解決すべきは empirical な cooldown semantics の再校正のみ。**棄却**。

### 2.3 /reimagine 代案 θ (cooldown 完全廃止) の検討

**仮想実装**:
```python
# eval_natural_mode=True のとき cooldown check 全 bypass
if self.eval_natural_mode:
    pass  # cooldown チェック飛ばす
```

**利点**:
1. mental model 最小化 (cooldown 概念が無くなる)。
2. AUTO_FIRE_PROB_PER_TICK=0.25 が唯一の cadence 制御 → tunable は 1 個のみ。

**欠点**:
1. **dominant gate が cooldown から prob に移転**するだけで、prob 0.25 の cognition_period
   依存性が浮上。120 s/tick × 30 ticks × 0.25 = 7.5 admit 期待 (variance 大、focal target
   30 達成の確実性が cooldown=5 案より低)。
2. 同 pair の即時連続 admit リスク: dialog close 直後 (last_activity_tick の次の tick) に
   AUTO_FIRE が当たれば即 admit、3 pair 全部が同 tick で同時に admit する "burst 多発"
   が起こり得る。dialog_turn_budget=6 で「同 pair が 6 tick 占有」されることで indirect に
   防がれるが、これは fragile な暗黙依存。
3. ME-8 ADR §invariant の "cooldown active" を完全削除する必要、PR #130 で確定した
   contract から後退。

**評価**: cooldown 概念削除は ME-8 ADR の意味的後退。dominant gate を prob に移すだけで
empirical robustness が改善するわけでもない。**棄却**。

### 2.4 /reimagine 代案 ι (β + δ) の検討

**仮想実装**:
- α/cooldown 不変 (`COOLDOWN_TICKS=30` keep)
- β: wall=30 min → 240 min (4h)
- δ: 3 並列 → 1 cell 逐次運用

**期待計算**:
```
240 min × 1 tick / 120 s = 120 ticks
cooldown=30 → 4 cycle (cycle 間隔 30 ticks × 120 s = 60 min)
4 cycle × 3 dialogs × 6 turns = 72 utterance
focal kant ≈ 72 / 3 = 24 (target 30 にやや不足)
1 cell 4h × 3 cell = 12h overnight 採取
```

**利点**: cooldown semantics 不変、ME-8 §invariant は v1 のまま、test 影響ゼロ。

**欠点**:
1. wall 12h overnight 採取は stimulus 採取 (cell ~3 min、3 cell 並列 ~3 min) との運用乖離が
   大きい。stimulus + natural の両建てで 12h × 5 run = 60h overnight が現実的でない。
2. focal target 30 を満たすには wall=300 min 以上必要、運用ぎりぎり。
3. 1 cell 逐次は 3 並列より wall 効率が常に悪い。

**評価**: 概念純度は最高だが運用コストが許容外。**棄却**。

## 3. 採用案: α + β ハイブリッド

### 3.1 採用根拠

1. **empirical 必達確率が高い**: §2.1 計算で focal kant ≈ 30 達成、G-GEAR 推奨と一致。
2. **実装最小**: `COOLDOWN_TICKS_EVAL: ClassVar[int] = 5` 別定数化 + `_effective_cooldown()`
   helper + CLI default 30→60 min の 3 箇所変更。
3. **既存 test 完全互換**: live mode の COOLDOWN_TICKS=30 不変、既存 1248 PASS 維持。
4. **ME-8 invariant 後退最小**: "cooldown active" → "cooldown active with eval-mode-specific
   reduced threshold" に文言更新するのみ、cooldown 概念自体は保持。
5. **/reimagine 代案 ζ/θ/ι の trade-off で全敗**: ζ は overscoping、θ は dominant gate
   移転、ι は wall 爆発 — α+β が支配的。

### 3.2 棄却サマリ

| 案 | 主棄却理由 |
|---|---|
| γ | cooldown が dominant gate のため prob 単独調整は効果限定 |
| δ | cognition_period 不変、wall 単純倍化のみ |
| ε | per-dialog stylo signal を薄める (Burrows/MATTR の measurement 劣化) |
| ζ | M4 frozen Protocol の純粋関数性違反、overscoping |
| θ | cooldown→prob の dominant gate 移転、ME-8 invariant 後退 |
| ι | wall 12h × overnight × 多 run で運用コスト許容外 |

### 3.3 採用案の修正範囲

#### 3.3.1 `src/erre_sandbox/integration/dialog.py`

```python
class InMemoryDialogScheduler:
    COOLDOWN_TICKS: ClassVar[int] = 30
    """Live multi-agent run の cooldown (live cognition_period での
    natural cadence 維持)。"""

    COOLDOWN_TICKS_EVAL: ClassVar[int] = 5
    """eval_natural_mode=True 時の reduced cooldown。実測 cognition_period
    ≈ 120 s/tick (qwen3:8b Q4_K_M on RTX 5060 Ti) で 60 min wall = 30 tick
    のうち 5-6 cycle 完走を保証する empirical 値。re-open 条件: 推論
    backend が変わって cognition_period が ±50% 以上変動した場合は
    本値を再評価。"""

    def _effective_cooldown(self) -> int:
        """eval_natural_mode flag に応じた cooldown ticks を返す純関数。"""
        return self.COOLDOWN_TICKS_EVAL if self.eval_natural_mode else self.COOLDOWN_TICKS
```

`schedule_initiate` の cooldown check と `tick()` 内の cooldown check 両方を
`self._effective_cooldown()` 経由に統一。`golden_baseline_mode=True` の cooldown bypass
は既存通り (両 flag 同時 True は v1 で reject 済)。

#### 3.3.2 `src/erre_sandbox/cli/eval_run_golden.py`

**empirical 訂正** (Codex HIGH-1 反映): 現状の
`_DEFAULT_WALL_TIMEOUT_MIN: Final[float] = 90.0` (line 122) であり、G-GEAR
Phase A の 10 min wall は operator が手動で sanity 用に短縮した値。default 90
min は §2.1 の minimum 計算を既に満たしているが、§5 conservative estimate
(variance 込みで focal=16-30) に対し margin を強化するため、本 v2 では
**default を 90 → 120 min に拡張**する。

```python
# src/erre_sandbox/cli/eval_run_golden.py:122
# 既存
_DEFAULT_WALL_TIMEOUT_MIN: Final[float] = 90.0
# v2
_DEFAULT_WALL_TIMEOUT_MIN: Final[float] = 120.0
```

Codex Q3 verdict: 「90 keep か 120 上昇のいずれか、60 は不可」。本 v2 は **120
を採用** (Codex 推奨 + §5 conservative estimate からの margin 確保)。

stimulus 側 default は影響なし (capture_stimulus は wall budget 持たない、
turn_count 駆動)。`--wall-timeout-min N` で操作者 override 可能を維持。

#### 3.3.3 `tests/test_integration/test_dialog_eval_natural_mode.py` 改訂

**Codex HIGH-2 反映**: 既存 v1 test 12 件のうち
`test_eval_natural_mode_preserves_cooldown_via_tick` (line 226-252) は
`scheduler.COOLDOWN_TICKS=30` で eval mode の cooldown を検証している。本 v2 で
`_effective_cooldown()` 経由化すると eval mode は 5 ticks に変わるため、**この
既存 test は v2 で fail する**。「追加」ではなく「rewrite + 追加」必要。

##### 既存 test の rewrite (1 件)

- `test_eval_natural_mode_preserves_cooldown_via_tick`:
  - rename → `test_eval_natural_mode_uses_reduced_cooldown`
  - `range(1, scheduler.COOLDOWN_TICKS)` を `range(1, scheduler.COOLDOWN_TICKS_EVAL)` に
  - `scheduler.tick(world_tick=scheduler.COOLDOWN_TICKS, ...)` を
    `scheduler.tick(world_tick=scheduler.COOLDOWN_TICKS_EVAL, ...)` に
  - docstring 更新: "Cooldown still applies after a close — eval mode uses
    `COOLDOWN_TICKS_EVAL=5` instead of the live `COOLDOWN_TICKS=30`."

  もう一つの `test_eval_natural_mode_sustains_admission_after_initial_burst`
  (line 295-343) も `far_tick = 6 + scheduler.COOLDOWN_TICKS  # 36` を
  `far_tick = 6 + scheduler.COOLDOWN_TICKS_EVAL  # 11` に rewrite。

##### 新規追加 test (Codex Q5 反映で sentinel test 削除、3 件)

1. **`test_effective_cooldown_returns_eval_value_when_flag_true`**:
   `eval_natural_mode=True` で `_effective_cooldown() == 5`、direct helper test
2. **`test_effective_cooldown_returns_live_value_when_flag_false`**:
   `eval_natural_mode=False` で `_effective_cooldown() == 30`、live mode 不変を保証
3. **`test_live_mode_cooldown_unchanged_via_tick`**: live mode の behavior test:
   close 後 tick 29 で reject、tick 30 で re-admit (既存 `test_dialog.py` line 131
   の単発 test と独立に、eval-mode test ファイル内で live invariant を明示)

Codex Q5 verdict: 「`test_class_constants_unchanged` は over-defensive、
behavior tests を優先」→ sentinel test は **採用しない**。

##### CLI test 追加 (1 件)

`tests/test_cli/test_eval_run_golden.py` (既存 12 mock test) に:
- `test_wall_timeout_min_default_is_120`: argparse から default 120 を確認

##### test 件数まとめ

- 既存 12 件のうち 2 件 rewrite (cooldown 数値を `COOLDOWN_TICKS_EVAL` に)
- 新規 3 件追加 (helper test 2 + live mode behavior test 1)
- CLI test 1 件追加
- → file 内 13 件 + CLI 1 件 = **総 14 件 (前回 12 件)**

##### 既存 1248 PASS 維持の影響範囲

- `tests/test_integration/test_dialog.py` (line 131, 147, 362): live mode の
  COOLDOWN_TICKS=30 を直接参照、影響なし
- `tests/test_integration/test_dialog_golden_baseline_mode.py` (line 107, 200):
  golden_baseline_mode で cooldown bypass、eval mode 経路と independent
- 他の cooldown 参照は無し

### 3.4 ME-8 ADR の **explicit amendment** (Codex MEDIUM-1 反映)

Codex MEDIUM-1 verdict: 「ME-8 should be explicitly amended, not silently
softened」。v1 の "active in both modes" 文言を silent に書き換えるのではなく、
**dated amendment section** として ME-8 §決定 / §影響 / §再採取での観測ターゲット /
§re-open 条件に **2026-05-01 amendment block** を追加:

```markdown
### ME-8 amendment 2026-05-01 (P3a-decide v2 — cooldown × cognition_period)

**Trigger**: ME-8 §re-open 条件 第 3 項「fix 後も admit が初動 burst で停止する場合」
が PR #131 G-GEAR Phase A 再採取で発火 (focal=6/30、wall 10 min sanity timeout)。

**Empirical evidence**: 600 s wall で max(world_tick)=5 → cognition_period
≈ 120 s/tick (qwen3:8b Q4_K_M on RTX 5060 Ti)。実効 cooldown =
COOLDOWN_TICKS=30 × 120 s = 60 min wall ⇒ 10 min wall 内で再 admit 物理的不可能。
v1 design.md §2 で棄却した仮説 B (cooldown × cognition_period の wall 換算) を
empirical で ◎ 主因に再格上げ。

**Amendment to §決定**: `eval_natural_mode=True` のときの cooldown threshold を
`COOLDOWN_TICKS=30` flat から `COOLDOWN_TICKS_EVAL=5` に分離。`_effective_cooldown()`
helper を導入し、`schedule_initiate` / `tick()` の cooldown check を経由化。
live mode (`eval_natural_mode=False`) の `COOLDOWN_TICKS=30` は完全不変。

**Amendment to §影響 (semantic naming)**: eval mode の cooldown=5 は live multi-agent
の "natural cadence" ではなく **"eval cadence calibration"** として位置付け
(Codex Q6 反映)。dialog_turn_budget=6 が 6 ticks 占有を強制し、5 ticks cooldown と
合わせて 11 ticks/cycle (≈ 22 min wall) の effective cycle を作る。これは
empirical な G-GEAR cognition_period に校正された値であり、別 backend 環境では
再校正必要。

**Amendment to §再採取での観測ターゲット**:
- focal=30 / total=90 / dialogs ~15 を **120 min wall** で完走 (`_DEFAULT_WALL_TIMEOUT_MIN`
  default 90 → 120 min に拡張)
- conservative estimate (§5.1): 4 cycle × 18 utt × (1/3 pair share) ≈ focal 24/cell
  を下限期待値とする
- `last_close_tick` の cluster spread が 5 tick + 6 tick = 11 tick 間隔で並ぶことを確認

**Amendment to §re-open 条件 (三度目)**:
- **fix v2 後も focal<25 で stop** → 別 dominant gate (prob 0.25 variance / 推論
  deadlock / world_tick 進行停止) を再特定。Codex Q7 反映で γ (prob=1.0) を新規
  ADR child で起票
- **推論 backend が変わって cognition_period が 60s 以下 / 240s 以上に変動** →
  COOLDOWN_TICKS_EVAL=5 の妥当性を再評価 (60s なら cooldown=10 候補、240s なら
  cooldown=3 候補、empirical 再採取で確定)
- **wall=120 min × 3 cell parallel で run-time が 6h overnight に伸びた場合** →
  ι (1 cell 逐次) への切り替え検討 (Codex Q1 reference)
```

本 amendment block を `decisions.md` ME-8 §影響 と §re-open 条件 の間に挿入する
(=既存 §re-open 条件は保持しつつ、新 amendment が後続 ADR の history 化)。

### 3.5 design v1 §採用案との差分明示

design v1 §6.1 の "Cooldown / probability / timeout は active のまま (natural cadence 保持)"
を design v2 §3.3 で **明示的に書き換え**:

> v1 では cooldown_ticks=30 を eval mode でも flat に保持していたが、empirical で
> dominant gate と判明。v2 では eval mode 限定で COOLDOWN_TICKS_EVAL=5 に reduce
> (live mode は影響無し)。Cooldown 概念自体は両 mode で保持される (= ピンポン admit
> 防止の semantics は eval mode でも生きている)。

## 4. 受け入れ条件 (本 Mac セッション完了時)

- [x] design v2 起草 (本ドキュメント、5 + 3 案比較 + 採用)
- [x] codex-review-prompt-natural-gating-v2.md 起草
- [x] Codex `gpt-5.5 xhigh` independent review verbatim 保存
      (`codex-review-natural-gating-v2.md`、145,717 tokens、Verdict: **revise**、
      HIGH=2 / MEDIUM=2 / LOW=1)
- [x] Codex HIGH/MEDIUM 反映で design v2 改訂 (HIGH-1 wall default 不整合 / HIGH-2
      既存 cooldown test rewrite / MEDIUM-1 ME-8 explicit amendment / MEDIUM-2
      conservative estimate primary 化 / Q5 sentinel test 削除 / Q6 eval cadence
      calibration 命名)
- [ ] decisions.md ME-8 amendment block 挿入 (§3.4 verbatim)
- [x] dialog.py + eval_run_golden.py 修正 + test rewrite 2 + 新規 4 (dialog 3 + CLI 1)
      → full suite **1251 passed / 31 skipped / 27 deselected** (baseline 1248 +3 dialog
      tests in default CI、CLI test 1 件は `pytestmark = pytest.mark.eval` でモジュール
      全体が deselect される既存規約、`-m eval` で単発検証 PASS)
- [ ] g-gear-p3a-rerun-prompt-v2.md 起草 (Phase A 期待値の桁再校正、wall 120 min)
- [ ] PR 作成 (PR #131 リンク参照、Codex review verdict と HIGH 反映状況明記)

## 5. リスクと反証 + Empirical estimate (Codex MEDIUM-2 反映で conservative を primary 化)

### 5.1 Conservative estimate (primary、wall default 確定根拠)

§2.1 G-GEAR 計算 (5 cycle × 18 utt = 90 utterance) は **AUTO_FIRE_PROB_PER_TICK=0.25
の variance と dialog duration を込めていない過大評価**。conservative estimate を
primary に置き、本 estimate から wall default を逆算する:

```
1 cycle 構成 (eval mode, fix v2 後):
  dialog duration = 6 ticks (dialog_turn_budget=6 で exhausted close)
  cooldown gap   = 5 ticks (COOLDOWN_TICKS_EVAL)
  prob 0.25 admit = mean wait ~4 ticks (geometric distribution の期待値)
                    ≈ admission を 1 tick で fire できる場合は 0、4 tick 待つ場合あり
  → 1 cycle ~= 6 + 5 + 4 = 15 ticks (per pair)

3 pair concurrent:
  3 pair が tick 0 で同時 admit する確率 = 0.25^3 + ... (combinatorial)
  保守的に "1 pair / 1 cycle" で計算 (mean 1 admission per ~15 ticks)

cognition_period 120 s/tick (G-GEAR empirical):
  1 cycle ≈ 15 × 120 s = 30 min wall

wall default 120 min:
  expected cycles = 120 / 30 = 4 cycle
  expected utterance per cell = 4 × 18 utt × (1/3 pair share) = 24 utt
  focal kant per cell ≈ 24 (target=30 にやや不足だが margin 内)

wall default 90 min (Codex Q3 alternative):
  expected cycles ≈ 3
  expected utterance ≈ 18 utt
  focal kant per cell ≈ 18 (target=30 達成 less probable)
```

**結論**: `--wall-timeout-min default=120` は conservative estimate で focal=24/cell
を期待、target=30 に対し下振れリスクあるが許容 margin。`90` だと下振れ確率 25-50%、
`60` (元案) だと 50%+ で fail predicted。Codex Q3 「60 不可」と一致。

### 5.2 Optimistic estimate (G-GEAR 計算、参考値)

```
60 min wall × 30 ticks / 5 ticks-cooldown = 6 cycle (上限)
6 cycle × 18 utt = 108 utterance/cell (3 pair concurrent admit 全部一致した場合)
focal kant per cell ≈ 36
```

これは "全 3 pair が tick 0 で完全に同時 admit、cooldown 抜け直後即再 admit" の
無風シナリオ。empirical な prob 0.25 variance を込めると §5.1 conservative の
2-3 倍の estimate であり、**representative ではない**。

### 5.3 リスク 1: 推論 backend 変動による cognition_period 不安定

G-GEAR は qwen3:8b Q4_K_M / RTX 5060 Ti / Ollama 0.22.0 で empirical
cognition_period ≈ 120 s/tick を確定。将来:
- FP16 化で cognition_period が 60 s/tick に半減した場合、`COOLDOWN_TICKS_EVAL=5`
  は 5 min wall cooldown となり burst 過多リスク
- 7B → 14B への scale up で cognition_period が 240 s/tick に倍増した場合、
  cooldown=5 でも 20 min wall cooldown、wall=120 min では 2-3 cycle のみ達成

→ ME-8 §re-open 条件に「cognition_period が 60s 以下 / 240s 以上に変動した場合は
COOLDOWN_TICKS_EVAL を再評価」を追加 (§3.4)。

### 5.4 リスク 2: prob 0.25 が新 dominant gate 化

cooldown 緩和後、AUTO_FIRE_PROB_PER_TICK=0.25 の variance が cycle yield を支配
する可能性。Codex Q7 verdict: 「γ (prob=1.0) は同 patch で追加しない、attribution
保持のため」。fix v2 後も focal<25 で再 stall した場合、別 PR で γ を ME-8 child
ADR で起票。

### 5.5 リスク 3: ピンポン admit (eval cadence の純度)

dialog close 直後 (tick T) → cooldown 5 抜け (tick T+5) で同 pair が即再 admit
する "ピンポン" 動作。dialog_turn_budget=6 が 6 ticks 占有を強制するので、
T → T+6 close → T+11 再 admit (real gap 11 ticks ≈ 22 min wall) となり、
**6 + 5 = 11 ticks/cycle** が effective cycle 周期。Codex Q6 verdict:
「cooldown=5 は eval mode で意味的に十分、dialog duration が real gap を作る。
これは live natural cadence ではなく **eval cadence calibration** として
ME-8 で文書化」。本 v2 では eval mode の cooldown を「natural cadence」ではなく
「**eval cadence calibration**」と命名し、ME-8 invariant 文言で明確に区別する
(§3.4 で反映)。

## 6. Codex review (実施済 — 2026-05-01、Verdict: revise)

`codex-review-natural-gating-v2.md` (145,717 tokens) verbatim 保存済。
- HIGH-1 (wall default 不整合 60/90/120) → §3.3.2 で 120 に確定
- HIGH-2 (既存 cooldown test rewrite 必要) → §3.3.3 で rewrite 2 件 + 新規 3 件 + CLI 1 件 に再構成
- MEDIUM-1 (ME-8 explicit amendment) → §3.4 で dated amendment block を起草
- MEDIUM-2 (success estimate optimistic) → §5.1 conservative estimate primary 化
- LOW-1 (prompt artifact の Click→argparse 不整合) → review verbatim 保存後の cosmetic、
  prompt artifact は historical record として保持 (Edit せず)

Codex Q&A verdict 採用:
- Q1: ι は P3a fix として正解ではない → α+β 採用、ME-8 explicit amend で対応
- Q2: CLI `--cooldown-ticks-eval` 追加せず、class const で empirical calibration を保持
- Q3: default=120 (60 不可、90 keep または 120、本 v2 は 120 採用)
- Q4: contract change として ME-8 explicit amendment、silent 変更にしない
- Q5: sentinel test 削除、behavior test 優先
- Q6: eval cadence calibration として命名分離、live natural cadence と区別
- Q7: γ は同 patch で追加せず、focal<25 再発時に ADR child で起票
- Q8: ζ (wall-time cooldown) は long-term clean だが本 P3a では defer (test/semantics 影響大)

## 7. design v1 → v2 → 採用案 の差分要約

| 軸 | design v1 (PR #130) | design v2 (本 PR) |
|---|---|---|
| 解決した hypothesis | D (zone scatter) | B (cooldown × cognition_period の wall 換算) |
| flag | `eval_natural_mode: bool = False` | (同) — 拡張のみ |
| 新定数 | (なし) | `COOLDOWN_TICKS_EVAL: ClassVar[int] = 5` |
| cooldown threshold | 30 (両 mode) | live=30 / eval=5 (`_effective_cooldown()` helper) |
| wall default | 90 min | 120 min |
| ME-8 §invariant | "active in both modes" | "active with eval-mode reduced threshold (eval cadence calibration)" |
| Codex Verdict | ship (HIGH=0/MED=0/LOW=2) | revise → 改訂後 ship 相当 (HIGH=2/MED=2/LOW=1 全反映) |
| Pass count | 1248 / 26 deselected | **1251** / 27 deselected (default CI に +3、CLI 1 件は `-m eval` で単発確認) |
- Q4: ME-8 §invariant 文言の "active with reduced threshold" 表現は v1 contract に対し
  silent な後退ではないか？(明示的な ADR re-open + 文言再定義で良いか)
- Q5: §3.3.3 で追加 4 test のうち、`test_class_constants_unchanged` の sentinel test は
  本当に必要か (over-defensive ではないか)？

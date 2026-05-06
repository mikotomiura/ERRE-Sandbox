# Codex Independent Review — Phase 2 run0 wall-timeout incident

## 依頼内容 (you are gpt-5.5 xhigh,独立 reviewer)

m9-eval-system Phase 2 run0 で 3 cell (kant / nietzsche / rikyu) すべてが
360 min wall budget で natural-condition capture FAILED。Mac ローカルで
コードを精読した Claude (opus-4-7) が partial data 救出 + CLI fix +
Phase 2 残りの budget 戦略を立てたが、過去にも線形外挿で empirical を
誤った前科 (3-parallel contention 1.5x → 実測 2.0x+) があるため、
独立 review で誤判定を切り出してほしい。

## 報告フォーマット

各 finding を以下で:

```
[HIGH|MEDIUM|LOW] <id>: <one-line summary>
- 根拠: <該当ファイル:行 / empirical 数値 / 仕様根拠>
- リスク: <reflect しなかった場合の悪化シナリオ>
- 推奨アクション: <具体的修正 / 代替案 / verify 手順>
```

最後に Verdict: **proceed-as-planned** / **revise (HIGH 反映必須)** /
**block (再設計必要)** を明記。

## 背景: empirical 観測

| 項目 | 線形外挿 (Claude が事前に計算) | empirical (run0 実測) |
| --- | --- | --- |
| 1 cell single 推計 | 4.35 h | (未測定) |
| 3-parallel contention 倍率 | 1.5x | 2.0x+ |
| focal/hour 実測 | — | kant 63.5 / nietzsche 64.9 / rikyu 66.5 |
| 360 min 内 focal 到達 | (500 想定) | 381 / 390 / 399 (= 76-80%) |
| total rows | — | 1158 / 1169 / 1182 |
| return code | — | 全 2 (= fatal_error path) |

P3 spec (stage 2 close、PR #134 merged) では turn_count=500 / cycle_count=3
(stimulus) + wall_timeout_min=120 (default) / focal_budget=500 (natural)。
Phase 2 では `--wall-timeout-min 360` を G-GEAR 側で override していた。

## Claude の現状理解 (要 verify)

### 1. CLI ロジック分析: `.tmp` データは実際には残存している (はず)

`src/erre_sandbox/cli/eval_run_golden.py::capture_natural`:

```python
# line 975-996: watchdog
runtime_task = asyncio.create_task(runtime.run(), name="p3a-natural-runtime")
wall_deadline = time.monotonic() + wall_timeout_min * 60.0

async def _watchdog() -> None:
    while True:
        if state.fatal_error is not None: return
        if enough_event.is_set(): return
        if runtime_task.done(): return
        if time.monotonic() >= wall_deadline:
            state.fatal_error = f"wall timeout ({wall_timeout_min} min) exceeded"
            return
        await asyncio.sleep(0.5)

# line 998-1010: finally
try:
    await _watchdog()
finally:
    runtime.stop()
    try:
        await asyncio.wait_for(runtime_task, timeout=_RUNTIME_DRAIN_GRACE_S)
    except TimeoutError:
        state.fatal_error = ...
        runtime_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await runtime_task

write_with_checkpoint(con)   # ← line 1012, **無条件実行**
```

`evidence/eval_store.py::write_with_checkpoint`:

```python
def write_with_checkpoint(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CHECKPOINT")
    with contextlib.suppress(duckdb.Error):
        con.close()
```

`_async_main` (line 1176-1188):

```python
if result.fatal_error is not None:
    logger.error("capture FAILED ...")
    return 2
atomic_temp_rename(temp_path, final_path)
```

**Claude の主張**: refuse されているのは rename だけ。`.tmp` ファイルは
CHECKPOINT 済みで、focal_rows=381/390/399 という値も
`_make_duckdb_sink` 内 INSERT 完了後の incrementer なので、INSERT も
コミット済み。つまり G-GEAR 上に
`data/eval/phase2/<persona>_natural_run0.duckdb.tmp` (3 個) が partial data
として残っているはず。

**Codex に問う**:
- (a) この主張は code 上正しいか? CHECKPOINT 後の `con.close()` は WAL を
  確実に flush するか (DuckDB の仕様根拠を引用)?
- (b) `runtime_task` の cancel が DuckDB sink の最後の INSERT を中断する
  race はあり得ないか? (`_make_duckdb_sink` は同期 closure だが、
  scheduler 経由で呼ばれる経路を要確認)
- (c) `.tmp` ファイルが SIGKILL や OOM-killer で消える経路はあるか?
  (G-GEAR 上で OS-level に process が killed された場合)

### 2. 救出戦略: `.tmp` rename + sample-size correction で run0 採用

Claude 案:

```bash
# G-GEAR で
mv data/eval/phase2/kant_natural_run0.duckdb.tmp \
   data/eval/phase2/kant_natural_run0.duckdb
# nietzsche / rikyu 同様
```

その後 P3a-finalize で確立した Codex HIGH-1 sample-size correction
(`width × sqrt(n / n_target)`、参照: codex-review-p3a-finalize.md)
を適用して run0 を正規 sample として採用。

**Codex に問う**:
- (d) 380-400 focal は target 500 の 76-80%。`width × sqrt(n / n_target)`
  の前提 (Burrows scale-dominant) はこの範囲で valid か?
- (e) Big5 ICC (P4 territory、stage 3 で本格採取) の事前準備として、
  partial data を validation set に組み込むのは適切か?
- (f) IPIP-NEO 100 (stimulus 必須) が 1158-1182 rows に対し 100 items の
  カバレッジ十分か? stimulus 側は 500 ではなく cycle ベースで設計されて
  いるが、natural と stimulus で run_id が異なるので 380-400 の影響は
  stimulus には及ばないという理解で正しいか?
- (g) run0 救出を採用すると Phase 2 の "5 runs × 3 personas × 2 conditions"
  matrix の run0 だけ wall_timeout=360 / partial、run1-4 は別 budget という
  混在になる。post-hoc の sample-size correction でカバー可能か、それとも
  run0 を破棄して全 5 runs を同 budget で再採取すべきか?

### 3. CLI fix 設計: soft_timeout vs fatal_error 分離

Claude 案 (~30 行):

```python
@dataclass
class _SinkState:
    total: int = 0
    focal: int = 0
    fatal_error: str | None = None    # DuckDB INSERT 失敗 / runtime drain 失敗
    soft_timeout: str | None = None   # ← 新設: wall timeout 到達
    last_zone_by_speaker: dict[str, str] = field(default_factory=dict)

# watchdog 内:
if time.monotonic() >= wall_deadline:
    state.soft_timeout = f"wall timeout ({wall_timeout_min} min) exceeded"
    return

# capture_natural return:
return CaptureResult(
    ...,
    fatal_error=state.fatal_error,  # 既存 (HIGH-3/HIGH-6 spec)
    soft_timeout=state.soft_timeout,  # ← 新設
    partial_capture=state.soft_timeout is not None,  # ← 新設フラグ
)

# _async_main 修正:
if result.fatal_error is not None:
    logger.error("capture FAILED (fatal) ...")
    return 2
if result.soft_timeout is not None:
    logger.warning(
        "capture PARTIAL (wall timeout) — renaming as partial: focal=%d/%d",
        result.focal_rows, args.turn_count,
    )
    atomic_temp_rename(temp_path, final_path)
    return 0  # partial だが publish は許可
atomic_temp_rename(temp_path, final_path)
return 0
```

**Codex に問う**:
- (h) Codex HIGH-3/HIGH-6 (P3a Step 1 review) の spec 「partial captures
  cannot masquerade as complete」の主旨に照らして、wall timeout を soft
  に降格する設計は spec 違反になるか? それとも DuckDB INSERT 失敗との
  本質的差異 (data corruption vs operational limit) を区別する正当な改良か?
- (i) `partial_capture=True` フラグを CaptureResult に持たせ、analytics
  layer で `width × sqrt(n / n_target)` を自動適用する経路は contract 上
  破綻なく機能するか? (raw_dialog schema 自体は変更不要、metrics 層で
  partial flag を読む)
- (j) return code 0 vs 1 の選択: 0 (success with warning) は CI / launch
  script 側で「成功」と誤認するリスク。明示的に 3 (= partial publish)
  を新設すべきか?

### 4. Phase 2 残り 4 runs の budget 戦略

empirical 65 focal/hour を採用した試算:

| 戦略 | wall budget | 5 runs × 3-parallel 総 wall | overnight 数 (16h/夜) |
| --- | --- | --- | --- |
| A: 480 min (8h) | 480 | 8h × 4 残 = 32h | 2 |
| B: 540 min (9h) | 540 | 9h × 4 残 = 36h | 2.25 |
| C: 600 min (10h) | 600 | 10h × 4 残 = 40h | 2.5 |
| D: turn 削減 (400) | 360 維持 | 6h × 4 残 = 24h | 1.5 |

D は P3 spec 確定 (stage 2 close、PR #134 merged) を覆すので Claude は
回避を推奨。run0 救出 (380-400 focal) を採用するなら、残り 4 runs も
同等 ~400 focal で揃える方が matrix 一貫性が高いという議論もある。

**Codex に問う**:
- (k) 安全率 0.85 (= 65 focal/hour × 480 min × 60 / 3600 / 0.85 ≈ 612 focal、
  500 target に対し +22% margin) は適切か? 0.95 だと 526 focal で margin
  +5% しかなく再 timeout リスク。0.75 だと 480 min budget に対し target
  450 focal となり P3 spec を実質下方修正。
- (l) run0 が 76-80% で stop している事実から、3-parallel での
  cognition_period に turn-count に依存する degradation (memory growth、
  embedding cache contention 等) がないか。線形外挿の 2 度目の失敗を
  避けるため、run1 で empirical 再校正する step を入れるべきか?
- (m) P3 spec の `--wall-timeout-min 120` default (cognition_period
  ≈120s/tick × COOLDOWN_TICKS_EVAL=5 × dialog_turn_budget=6 ≈ 22 min/cycle)
  と、Phase 2 で必要な 8h は 4x の乖離。design-natural-gating-fix-v2.md
  §5.1 の試算と empirical の差異の root cause は何か?
  (qwen3:8b Q4_K_M loading? GPU 共有? memory growth?)

### 5. 並行性: run1 を CLI fix 前に launch すべきか

選択肢:
- **fix-first**: CLI fix を merge → run1-4 を全部新 binary で実行
- **salvage-first**: run0 を救出 + run1 launch を CLI fix 待たずに開始
  (=現 binary でも `.tmp` は残存するという仮説に賭ける)
- **hybrid**: run0 救出 + CLI fix 並行作業 + run1 は fix 後 launch

Claude は hybrid 推奨だが、CLI fix の test 実装 + PR review + merge で
1-2 日遅延する。Phase 2 全体の deadline は明記されていない (m9-b LoRA
は M9 milestone 内、Phase 2 は eval foundation)。

**Codex に問う**:
- (n) salvage-first は process が killed された場合を想定すると `.tmp`
  消失リスクがある。CLI fix 完了前に run1 を launch する判断は妥当か?
- (o) PR review 待ちを短縮するために、Codex 自身が CLI fix 設計を
  独立 review する timing と本 review の timing をどう分けるべきか?

## 参照ファイル

- `src/erre_sandbox/cli/eval_run_golden.py` (1230 行、本件の主体)
- `src/erre_sandbox/evidence/eval_store.py` (436 行、ME-2 helpers)
- `.steering/20260430-m9-eval-system/decisions.md` §ME-2, §ME-4
- `.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md` (HIGH-1
  sample-size correction の根拠、`width × sqrt(n / n_target)`)
- `.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md` §5.1
  (cognition_period 試算、120 min wall budget の根拠)
- `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md`
  (Phase 2 launch 仕様)

## 補足: Codex 過去 review 実績

このタスクで本件は 6 回目の Codex review。過去 5 回はいずれも HIGH を
事前切出し、Claude 単独では未発見だった HIGH を切ってきた:

- 2026-04-30 design.md: HIGH 5 件
- 2026-05-01 P2a wording: MEDIUM 5
- 2026-05-01 P3a Step 1 CLI: HIGH 6
- 2026-05-01 P3a v2 cooldown: HIGH 2
- 2026-05-05 P3a-finalize: HIGH 3 (うち HIGH-1 が `width × sqrt(n / n_target)`)

特に直近の HIGH-1 で sample-size correction を切り出した経験は本件に
直結しているので、その文脈を活かして review してほしい。

## 制約 / 留意点

- 個人プロジェクト、予算 1M tok/day (現使用 80K)
- Mac ローカル + G-GEAR (Linux GPU 機) の 2 マシン構成、HTTP rsync で
  同期 (memory: project_m9_eval_p3a_finalize_merged.md)
- `main` ブランチ直 push 禁止、PR 経由必須
- P3 spec stage 2 close 済 (PR #134、turn=500 確定) を覆す方向は避ける

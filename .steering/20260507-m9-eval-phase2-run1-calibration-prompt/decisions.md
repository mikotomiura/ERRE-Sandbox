# 重要な設計判断 — m9-eval-phase2-run1-calibration-prompt

> Plan mode で確定した採用案 (B + R-2 + F-1/F-4 + S-2 + L-1) と、Codex
> `gpt-5.5 xhigh` independent review (2026-05-07、tokens=176,193、Verdict:
> Adopt-with-changes) を経た HIGH/MEDIUM/LOW の採否記録。

## 判断 1: 採用パッケージ確定 (Plan mode、AskUserQuestion 経由)

| Q | 採用 | 主因 |
|---|---|---|
| Q1 cell 戦略 | **B 案: kant only × 5 wall sequential (run_idx=100..104)** | ADR 厳守 + 現 CLI 完結 |
| Q2 v1 関係 | **R-2: v1 残置 + v2 新設** | 既存 `g-gear-p3a-rerun-prompt-v2.md` 命名パターン踏襲 |
| Q3 wall budget 数式 | **F-1 (linear) + F-4 (contention 1.76)** | empirical-grounded、Codex H2 (sample-size correction) 棄却を反映 |
| Q4 stimulus | **S-2: pre-flight smoke test 追加** | sidecar / return 3 path の path coverage |
| Q5 Codex review | **C-1: 1 round (Plan 確定後、prompt 起票前)** | 公開 API 相当 + 複数案 + run0 incident 教訓 |
| Q6 配置 | **L-1: `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md`** | requirement 明示 + history 同居 |

不採用案の根拠は `design.md` の「不採用案」節に記録。

## 判断 2: HIGH 3 件 (Codex 2026-05-07) を全反映

Codex Verdict: Adopt-with-changes。HIGH 3 件は v2 prompt 起票前に必反映。

### H1. stimulus 500 focal が現 command (`--turn-count 500 --cycle-count 3`) で **到達不能**
- **発見**: Codex read-only 解析で kant/nietzsche/rikyu battery は cycle_count=3
  だと total_focal=264。**PR #140 後は `focal_rows < args.turn_count` が fatal
  になる**ため、v1 流用の stimulus 全 cell が fatal で fail する。
- **採用**: 反映必須
- **変更**: v2 prompt §Phase B の stimulus invocation を
  `--turn-count 500 --cycle-count 6` に変更 (focal≈504、target 500 を満たす)。
  これは P3 spec 変更ではなく既存の `cycle_count` パラメータの調整のみ
  (CLI 改修不要)。

### H2. run1 `--turn-count 1000` は 600 min endpoint を潰す
- **発見**: single rate 1.87/min 期待値で 600 min cell の focal≈1122。
  `--turn-count 1000` だと 600 min cell が約 535 min で early stop し、
  最重要の 600 min wall sample が取れない。
- **採用**: 反映
- **変更**: v2 prompt §Phase A の calibration invocation を
  `--turn-count 2000` に変更 (Codex 推奨: 1500 以上、保守的に 2000)。
  120/240/360/480/600 wall cell の **全 endpoint で wall-limited stop** を
  確保。calibration cell の return code 3 (partial) は **正常な calibration
  partial として扱い、production audit と混ぜない** 運用。

### H3. calibration と production の audit/rsync を混ぜない
- **発見**: design.md の「全 30 cell + 5 calibration cell」batch audit は意図的
  partial が混ざる。さらに v1 rsync は DuckDB だけ copy しており、PR #140 後に
  必須の `.capture.json` が Mac 側で欠けると audit return 4 になる。
- **採用**: 反映
- **変更**:
  1. calibration output を `data/eval/calibration/run1/` に **隔離** (新規 dir)
  2. production は `data/eval/golden/` の run0..4 のみを exact glob/list で audit
  3. rsync receipt は **DuckDB と `.duckdb.capture.json` の md5 を両方** 含める
  4. v2 prompt §Phase D の rsync コマンドで `.duckdb*` glob を使い sidecar も
     rsync 対象に含める

## 判断 3: MEDIUM 3 件の採否

### M1. 5 wall sequential は ME-9 の "single 600 min cell" から実質変更
- **背景**: ADR は 1 cell × 600 min + intermediate samples。本案の 5 cell sweep
  は同一 memory growth の時系列ではない。
- **採用**: 反映 (本 decisions.md に明記、ADR 改訂はしない)
- **理由**: Codex H1 ADR 文言「kant のみ」は維持、CLI snapshot 未実装で
  intermediate sampling が技術的に難しい。endpoint sweep は **代替手段** として
  受容、memory growth の継続性は失うが (a) calibration 主旨 (focal/min 確定)
  には十分、(b) cell ごと独立 RNG seed (`derive_seed(persona, run_idx)`) で
  再現性確保、(c) ADR 改訂より prompt 起票で先送り合理。
- **影響**: design.md / 本 decisions.md / v2 prompt 冒頭に「ADR の intermediate
  sample は CLI snapshot 未実装のため endpoint sweep で代替」と明記。

### M2. stimulus smoke の wall 設計は CLI 上 no-op
- **背景**: `--wall-timeout-min` は natural 用 watchdog で、stimulus には
  watchdog も return 3 path もない (`eval_run_golden.py:958` の
  `partial_capture=False` ハードコード)。smoke は sidecar complete/fatal path の
  確認に留まる。
- **採用**: 反映
- **変更**: v2 prompt §Phase 0 で「stimulus の `--wall-timeout-min` flag は
  natural 用、stimulus には効かない安全弁。外部 timeout (shell `timeout 60m
  uv run ...`) を併用」と明記。

### M3. `contention_factor=1.76` は固定仮定として扱う
- **背景**: run1 n=5 single samples からは single-rate variance は出せるが、
  contention factor 自体は再推定できない (parallel sample がない)。
- **採用**: 反映 (Q1 への回答 A も同じ)
- **変更**: v2 prompt §Phase A 結果解析節で「contention_factor=1.76 は **固定
  仮定**、run1 n=5 で出すのは single-rate の 95% CI 説明統計のみ。3-parallel
  contention の信頼区間ではない」と明記。3-parallel calibration 追加は
  blockers.md D-7 に persistent defer。

## 判断 4: LOW 1 件は採用 (cheap)

### L1. `.gitignore` に calibration/partial DuckDB の明示 ignore がない
- **採用**: 反映
- **変更**: v2 prompt §Phase 0 / §Phase A の前置きで「calibration 出力は
  commit しない、`git status` で確認」と注記。`.gitignore` への
  `data/eval/calibration/` 追加は本 PR 外、blockers.md D-8 に defer (cheap
  follow-up)。

## Codex Q&A 簡易記録

| Q | Codex 回答 | 採用判断 |
|---|---|---|
| Q1 contention_factor 信頼区間 | A (fixed assumption) + descriptive CI | M3 反映 (固定扱い + 説明統計) |
| Q2 cooldown systematic bias | bias 低い (`COOLDOWN_TICKS_EVAL=5` 一貫、commit `c6d6409` 以降不変) | 採用 (本案で OK) |
| Q3 run_idx=100 downstream フィルタ | コード変更不要、calibration dir 隔離 + production exact glob | H3 と統合反映 |
| Q4 stimulus smoke wall 設計 | A (wall=60 turn=50) + caveat (wall flag no-op) | M2 反映 |
| Q5 ME-9 re-open trigger 連動 | C (Codex review/child ADR)、720 強行は trigger 空文化 | 採用 (v2 prompt §ブロッカー予測で明記) |

## 変更後の v2 prompt summary (反映後)

- **§Phase 0 smoke**: kant_stimulus_run0 wall=60 turn=50 + 外部 `timeout 60m`
  併用、stimulus wall flag は no-op を明記
- **§Phase A calibration**: kant only × 5 wall sequential、run_idx=100..104、
  `--turn-count 2000` (early stop 抑制) で 120/240/360/480/600 wall endpoint を
  全 wall-limited 取得
- **§Phase A 結果解析**: F-1+F-4 数式、observed focal/min の **single-rate 95% CI**
  のみ (contention_factor は固定 1.76 として表)
- **§Phase B stimulus**: `--turn-count 500 --cycle-count 6` (focal≈504)、新
  contract audit 適用
- **§Phase C natural**: wall は §Phase A から確定 (default 600 min)、3-parallel
  × 5 run、kant drain timeout fallback 維持、run0 を `--allow-partial-rescue` で
  再採取
- **§Phase D audit/rsync**: production = `data/eval/golden/*.duckdb` exact glob
  + `.duckdb.capture.json` 同時 rsync、calibration = `data/eval/calibration/run1/`
  別 audit (--allow-partial)、rsync receipt に sidecar md5 を含める
- **§ブロッカー予測**: ME-9 re-open trigger (focal/h ≤55 / ≥80) で **C 案
  (Codex review + child ADR)** を default、720 強行は禁止

## 関連参照

- Codex review: `codex-review-run1-calibration.md` (verbatim、HIGH 3 / MEDIUM 3 / LOW 1)
- Codex prompt: `codex-review-prompt-run1-calibration.md`
- 起点 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
- 前 PR (CLI fix): PR #140 merged、main = `0304ea3`
- 承認 plan: `~/.claude/plans/sleepy-fluttering-lake.md`

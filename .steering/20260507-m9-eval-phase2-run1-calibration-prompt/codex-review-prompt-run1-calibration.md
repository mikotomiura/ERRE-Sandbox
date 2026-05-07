# Codex Independent Review Prompt — m9-eval-phase2-run1-calibration-prompt

> **target model**: `gpt-5.5 xhigh`
> **mode**: read-only independent review、prompt 起票前
> **input**: 採用案 (B + R-2 + F-1/F-4 + S-2 + L-1) + 5 specific questions
> **output 期待**: HIGH / MEDIUM / LOW 区分の指摘リスト + Verdict (Adopt /
> Adopt-with-changes / Reject) + 5 questions 回答

---

## 0. Repository orientation

ERRE-Sandbox プロジェクト (`/Users/johnd/ERRE-Sand Box`)。本タスクは **Mac
セッション側 planning タスク**で、CLI コード変更なし、`g-gear-p3-launch-prompt-v2.md`
(launch prompt 文書) の起票が成果物。

- 関連 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
  (run0 wall-timeout incident 後の CLI fix + run1 calibration 方針)
- 直前 PR: PR #140 (`feat(eval): m9 — partial-publish CLI fix + eval_audit gate`、
  main = `0304ea3`、2026-05-06 merged) で sidecar v1 + return code 0/2/3 +
  `eval_audit` CLI が live
- 旧 v1 prompt: `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md`
  (366 行、§Phase 3 audit step だけ新 contract、§Phase 1/2 は run0 incident
  前のまま)

## 1. 背景: run0 incident と ME-9 ADR の確定方針

2026-05-06 Phase 2 run0 で 3 cell が wall=360 min で FAILED
(focal=381/390/399 prefix censored)。Codex `gpt-5.5 xhigh` 6 回目 review
(`codex-review-phase2-run0-timeout.md`) HIGH 4 件を切出後、ME-9 ADR で:

1. **CLI fix + sidecar + audit CLI** を別タスクで実装 (PR #140 merged 済)
2. **run1 = kant のみ 1 cell × 600 min single calibration**、120/240/360/480 min
   で intermediate sample → run2-4 wall budget を empirical 確定
3. run0 partial は primary 5 runs matrix から外す、`data/eval/partial/` 隔離

本タスクは方針 2 を **G-GEAR 側で `/clear` 後コピペ可能な launch prompt v2** に
落とし込む Mac セッション (planning)。

## 2. empirical 起点 (Phase 1 で確定済の事実、再探索しない)

- pilot single-cell natural: **1.87 focal/min** (`data/eval/pilot/_summary.json`
  の kant_natural_run0 = focal 30 / wall 16 min)
- run0 3-parallel contended: **1.06 focal/min** (kant 381 / 360 min、
  nietzsche 390 / 360 min、rikyu 399 / 360 min)
- contention factor ≈ **1.76×** (1.87 / 1.06)
- Codex H1 budget basis: 65 focal/h ≈ 1.08/min (`decisions.md:607`)
- `_RUNTIME_DRAIN_GRACE_S = 60.0` (PR #140 で 30→60 raise 済)
- `_DEFAULT_WALL_TIMEOUT_MIN = 120.0` (eval_run_golden.py:131-141 の M8
  amendment)

## 3. 採用案 (B + R-2 + F-1/F-4 + S-2 + L-1)

### 3.1 Q1: cell 戦略 = **B 案 kant only × 5 wall sequential**

ADR 厳守で、kant 1 persona × 5 cell sequential、run_idx=100..104、wall
=120/240/360/480/600 min。`--turn-count 1000` で focal=500 early-stop を抑制
(calibration 主旨)。

**Critical caveat**: kant single-cell では focal/min ≈ 1.87 が観測される
(pilot empirical)。これは 3-parallel run2-4 の focal/min ≈ 1.06 と異なる。
run2-4 wall budget は **contention_factor=1.76** を仮定して逆算する。

不採用案:
- 案 A (CLI で intermediate snapshot): scope 拡張で別 PR 化、deadline 延伸
- 案 B' rev2 (3-parallel calibration): ADR 文言「kant のみ」と齟齬
- 案 C (.tmp 直読): WAL 同期保証なし、stale read リスク

### 3.2 Q2: v1 関係 = **R-2 (v1 残置 + v2 新設)**

既存 `g-gear-p3a-rerun-prompt-v2.md` (PR #133 で追加) と同パターン。v1 冒頭
注記 (L17-49) に「v2 が active、本 prompt は legacy reference」リンク追記、
本文は不変。

### 3.3 Q3: wall budget 数式 = **F-1 (linear) + F-4 (contention 1.76)**

```
focal_per_min_single   = run1 calibration で実測 (期待値 ~1.87)
contention_factor      = 1.76 (pilot single / run0 parallel、run1 で再校正)
focal_per_min_parallel = focal_per_min_single / contention_factor
safety_factor          = 0.85
wall_budget_min        = ceil(focal_target / focal_per_min_parallel / safety_factor)
                       ≈ ceil(500 / 1.063 / 0.85) ≈ 553 → 切上げ 600 min
```

**run2-4 default wall budget = 600 min**。observed 値次第で +120 min 拡張。

不採用 F-2 (sample-size correction `width × sqrt(n / n_target)`): Codex H2
(`decisions.md:608`) で wall-time prefix censoring が random missing でないと
明示的棄却済。

### 3.4 Q4: stimulus = **S-2 (pre-flight smoke test 追加)**

§Phase 0 として `kant_stimulus_run0 wall=60 turn=50` dry run を追加。PR #140
の sidecar / return code 3 path が stimulus でも正しく動くか sanity-check
(`eval_run_golden.py:958` の `partial_capture=False` ハードコード path coverage)。

### 3.5 Q5: Codex review = **C-1 (1 round、prompt 起票前)**

本 review がそれ。

### 3.6 Q6: 配置 = **L-1**

`.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md`。requirement
明示 + history (ME-9 ADR / run0 incident docs) と同居。

### 3.7 v2 prompt の章立て

1. 冒頭 metadata (`main = 0304ea3` / PR #140 merged 前提 / v1 リンク)
2. §Phase 0 — pre-flight smoke test (S-2)
3. §Phase A — run1 calibration (kant only × 5 wall sequential)
4. §Phase A 結果解析 (Mac 側、F-1+F-4 数式、observed → run2-4 wall 確定)
5. §Phase B — stimulus 全 15 cell (現 v1 §Phase 1 を新 contract で書き換え)
6. §Phase C — natural 全 15 cell + run0 再採取 (現 v1 §Phase 2 の置換)
7. §Phase D — eval_audit batch + rsync (現 v1 §Phase 3-4 を流用)
8. §Phase E — PR 作成 (現 v1 §Phase 5 を流用)
9. ブロッカー予測 + fallback

## 4. 投げる 5 個の specific questions (必須回答)

### Q1. contention_factor=1.76 の信頼区間
pilot single 1.87 / run0 parallel 1.06 の **2 サンプル比較**で求めた値。
run1 calibration n=5 (5 wall point × kant single 1 cell) から再推定するのは
妥当か、それとも別途 3-parallel calibration cell を追加すべきか。

**選択肢**:
- (A) 1.76 を fixed assumption として使用、run1 で再校正しない
- (B) run1 5 sample から focal/min variance を出し、95% CI を提示
- (C) run1 後に追加 1 cell × 3-parallel (wall=600 min) を **calibration として**
  実行し、empirical contention_factor を直接観測

(A) は実用、(C) は厳密だが ADR 改訂を要する。本案では (A) を採用予定だが、
HIGH リスクが残るか判定希望。

### Q2. cooldown 設定の systematic bias (fact-check)
pilot single = P3a-fix-v2 cooldown=5 適用後、run0 parallel も cooldown=5 の
**はず**。ME-8 と ME-9 の間で `COOLDOWN_TICKS_EVAL` が変化していないか
git log で fact-check 依頼。値が異なる場合 contention_factor=1.76 自体に
systematic bias が入る。

### Q3. run_idx=100..104 calibration 専用域の downstream フィルタ
本案では P3 production の run_idx=0..4 と衝突回避のため calibration 専用域
100..104 を使う。`raw_dialog.dialog.run_id` は `kant_natural_run100` 形式
になるが、後続 Tier B/C metric 計算 (Vendi / IPIP-NEO / Big5 ICC) や
`scripts/p3a_decide.py` が run_idx ∈ {0..4} を仮定する箇所がないか
grep して fact-check 依頼。

ハードコードがあれば、本タスクで calibration filter を追加するか別タスクで
defer するかの判断を仰ぐ。

### Q4. stimulus smoke test の wall 設計
§Phase 0 の `kant_stimulus_run0 wall=60 turn=50`。drain timeout 60s grace で
ぎりぎり (50 turn × ~1 min/turn = 50 min wall + drain 1 min ≈ 51 min < 60 min)。

**選択肢**:
- (A) wall=60 turn=50 (現案、ぎりぎり)
- (B) wall=90 turn=50 (安全側)
- (C) wall=60 turn=30 (turn を絞る)
- (D) wall=120 turn=50 (`_DEFAULT_WALL_TIMEOUT_MIN` 一致、最安全)

stimulus は cognition memory 不要 (battery 駆動) で 1 turn ≈ 30s の
empirical 実測あり (`pilot 198 focal / 30 min = 6.6 focal/min`)。安全マージン
の妥当値を推奨してほしい。

### Q5. ME-9 re-open 条件との連動
ME-9 ADR re-open 条件 (`decisions.md:646` "focal/hour rate が 65 を大きく外れる、
例: ≤55 / ≥80") と本案の wall budget gating ロジックの連動方針。

run1 で observed focal/min が 0.92 (≤55/h、ME-9 re-open trigger 該当) を
観測した場合:
- (A) wall 720 min に拡張して run2-4 強行 (焼き直し)
- (B) `COOLDOWN_TICKS_EVAL` 再調整 ADR を起票して run1 やり直し
- (C) 別途 Codex review 起動 (incident 再評価)
- (D) ハイブリッド (例: wall を 720 に拡張しつつ、run2 のみ pilot として観測、
  問題なければ run3-4 を 720 で連投)

どれを v2 prompt の default 推奨にすべきか。

## 5. その他、独立 review してほしい点

- `--turn-count 1000` で focal=500 early-stop を抑制する設計は意図通りに動くか
  (`eval_run_golden.py:1057-1071` の watchdog で `focal>=turn_count` 到達時
  enough_event を set しているので、turn_count=1000 なら focal=500 では
  stop しない。ただし 1000 を超えるサンプルは取れないが、wall=600 min で
  expected focal ≈ 1122 (single 1.87) は超過するため `--turn-count 1500` の
  方が安全か?)
- run1 calibration の合計 wall = 120+240+360+480+600 = 1800 min = 30h。kant
  single なので overnight×2 で完結。Mac/G-GEAR 同期ポイントは 5 cell 完了後
  に 1 回 (rsync receipt) で十分か、または 3 cell ごとに intermediate rsync
  すべきか
- F-1+F-4 数式の `safety_factor=0.85` の根拠 (Codex H1 で示された値、別 PR で
  validated か?)
- run0 再採取で `--allow-partial-rescue` が必要になる場合の運用 (sidecar
  validation 失敗時は `--force-rescue` を別途要求する PR #140 の M4 反映を
  v2 prompt が言及しているか確認)

scope 外: ADR 改訂を要する変更 (例: kant only → 3-parallel calibration、
sidecar schema 変更) は HIGH に昇格しない、MEDIUM 以下で記録。

## 6. 報告フォーマット (必須)

```markdown
## Verdict
- [Adopt / Adopt-with-changes / Reject]
- 一文で判定理由

## HIGH (実装前必反映)
### H1. [タイトル]
- 該当箇所: file:line
- 問題: ...
- 推奨: ...

## MEDIUM (採否は実装側判断、ただし decisions.md に記録)
### M1. [タイトル]
...

## LOW (持ち越し可、blockers.md に記録)
### L1. [タイトル]
...

## 5 questions への回答
### Q1: [選択肢 + 理由]
### Q2: [fact-check 結果 + 推奨]
### Q3: [grep 結果 + 推奨]
### Q4: [選択肢 + 理由]
### Q5: [選択肢 + 理由]

## Out-of-scope notes
(本タスクで対応しないが将来課題として記録すべき点)
```

## 7. 守ってほしい制約

- **read-only**: file 編集なし、テスト実行なし、`git log` / `grep` での fact-check は OK
- **scope 厳守**: 本タスクは prompt 起票のみ。CLI 改修や ADR 改訂は scope 外、
  MEDIUM 以下で記録
- 出力は **markdown 単一ファイル** で 4000 語以内目安、verbatim 保存される

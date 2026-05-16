# ブロッカー記録 — Plan B eval generation + verdict

## ブロッカー 2 (RECORDED): Codex review session が中断 (Windows PowerShell tool hook failure)

- **発生日時**: 2026-05-17 (Codex independent review 起動時)
- **症状**: `codex exec --skip-git-repo-check` を Windows PowerShell
  経由で呼んだ際、Codex 内部の rg / Get-Content tool 経由の探索が
  "hook: PreToolUse Failed" を繰り返し、最終的に session が
  HIGH/MEDIUM/LOW summary を emit する前に exit 0 で完了。
- **原因**: Codex CLI on Windows が PowerShell exec hooks と相互
  作用して中断。Codex は探索系の tool 呼び出しを大量に行うが
  Windows PowerShell wrapping の hook check で失敗していた様子。
- **暫定対応**:
  - 本 PR の core verification は本セッションで実施済み:
    - rescore CLI 8 unit test PASS
    - pre-push-check 4 段 PASS (ruff format / ruff check / mypy / pytest -q 1510 件)
    - verdict aggregator は manual に出力確認、PHASE_E_A6 routing
      が design 通り
  - Codex 部分出力 (.steering/.../codex-review.md) は audit trail
    として保持
- **次セッション対応**: WSL2 経由で `codex exec` を呼ぶことで
  PowerShell hook を回避し、full HIGH/MEDIUM/LOW review を取得する
  (DA-16 ADR 起票時に併せて実施)
- **教訓**:
  - Windows + Codex CLI + PowerShell の組み合わせは hook 干渉が
    起こりやすい。長時間 review は WSL2 から起動する pattern を
    推奨

## ブロッカー 1 (RESOLVED): shard metadata に `pilot_rate_focal_per_s` が無い

- **発生日時**: 2026-05-17 (本セッション中、aggregator 設計時に判明)
- **症状**: `aggregate_plan_b_axes.py` 設計時に「shard の
  `raw_dialog.metadata` テーブルから rate を読む」を想定したが、生成された
  shard には `metadata` テーブル自体が存在しない (`raw_dialog.dialog` +
  `main.pilot_state` のみ)。
- **試したこと**:
  1. duckdb で schema 列挙 → `metadata` テーブル不在を確認
  2. `pilot_state` テーブル列を確認 → `last_cycle_idx`, `last_stimulus_id`,
     `completed_turns`, `updated_at` のみで rate 情報なし
- **原因**: `tier_b_pilot.py` は shard に rate metadata を保存していない。
  rate は stdout log にのみ出力される。
- **解決方法**: DE-5 (decisions.md) で `aggregate_plan_b_axes.py` を
  改修し、eval-sequence.log の `pilot done` 行から rate を parse する。
  `tier_b_pilot.py` 改修は本 PR scope 外とする。
- **教訓**:
  - eval shard 設計時、forensic metadata (rate / elapsed / start_time
    など) を `metadata` テーブルに保存する pattern を `tier_b_pilot.py`
    にも適用する別 PR を起こす価値あり (本 PR scope 外、blockers.md に
    記録)

## 未解決ブロッカー候補 (本 PR では発生していない、reference のみ)

### Plan B Phase E A-6 移行 (REJECT 確定、本 PR の verdict)

- **発生条件 (CONFIRMED)**: 本 PR の `da14-verdict-plan-b-kant.json`
  で verdict = **PHASE_E_A6**。encoder agreement axis FAIL + Burrows
  FAIL。decisions.md DR-1 参照。
- **次 PR 対応**: 別 PR で **DA-16 ADR** (rank=16 spike) を起票
- **DA-16 起票時の include項目** (本 PR で考慮された設計):
  1. どの axis が fail したか (encoder agreement / Burrows / ICC /
     throughput のどれが gate を割ったか)
  2. fail した axis ごとの within-language d パターン (rank=16 で
     resolveable な capacity 不足か、corpus tuning 不足か判別)
  3. WeightedTrainer Blocker 2 (sample weight collapse) が verdict に
     影響した可能性の評価
  4. nietzsche / rikyu の Plan B 展開を rank=16 spike 完了まで保留する
     判断

### nietzsche / rikyu の Plan B 展開時 (verdict ADOPT の場合)

- **発生条件**: kant verdict が ADOPT され、他 persona の Plan B
  retrain + verdict を実施する場合
- **対応**: 別 PR で各 persona について
  - retrain artifact 生成 (本 PR の `train_kant_lora.py` 相当)
  - eval shard 採取 (本 PR の `tier_b_pilot.py` invocation を persona
    swap)
  - 4-encoder rescore + Burrows + ICC + verdict (本 PR pipeline 完全
    流用)
- **設計検討項目**: shards の language distribution が persona ごとに
  異なる場合、DE-1 の "pool-fit lexical_5gram with ~equal mass" 前提が
  崩れる可能性。pool-fit vs per-window-fit semantics 再評価が必要

### WeightedTrainer Blocker 2 (sample weight collapse) の修正

- **持ち越し元**: `.steering/20260518-m9-c-adopt-plan-b-retrain/
  blockers.md` ブロッカー 2
- **対応**: 本 PR の Plan B verdict ADOPT なら保留 (DA-14 weighting
  が効いていなくても ADOPT に至った = weighting への dependency 弱い)、
  REJECT なら別 PR で優先 (DA-14 weight 不発の影響を切り分ける)
- **判断タイミング**: 本 PR の `da14-verdict-plan-b-kant.json` 出力後

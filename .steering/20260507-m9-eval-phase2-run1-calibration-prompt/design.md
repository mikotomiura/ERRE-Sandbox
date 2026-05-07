# 設計 — m9-eval-phase2-run1-calibration-prompt

> **status**: APPROVED (2026-05-07、Plan mode で 6 設計判断確定)
>
> 承認 plan file: `~/.claude/plans/sleepy-fluttering-lake.md`
> 起点 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
> 採否記録: `decisions.md` (本タスク内、Codex review 後に更新)

## 採用パッケージ

| Q | 採用 | 主因 |
|---|---|---|
| Q1 cell 戦略 | **B 案: kant only × 5 wall sequential (run_idx=100..104)** | ADR 厳守 + 現 CLI 完結 |
| Q2 v1 関係 | **R-2: v1 残置 + v2 新設** | 既存 `g-gear-p3a-rerun-prompt-v2.md` 命名パターン踏襲 |
| Q3 wall budget 数式 | **F-1 (linear) + F-4 (contention 1.76)** | empirical-grounded、Codex H2 (sample-size correction) 棄却を反映 |
| Q4 stimulus | **S-2: pre-flight smoke test 追加** | sidecar / return 3 path の path coverage |
| Q5 Codex review | **C-1: 1 round (Plan 確定後、prompt 起票前)** | 公開 API 相当 + 複数案 + run0 incident 教訓 |
| Q6 配置 | **L-1: `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md`** | requirement 明示 + history 同居 |

## 不採用案 (記録のみ)

- **Q1 案 A (CLI 拡張で intermediate snapshot)**: scope 拡張 (eval_run_golden.py
  に `--snapshot-at-min` flag 追加) → 別 PR 化で deadline 延伸、本タスクは
  prompt 起票限定で却下
- **Q1 案 B' rev2 (3-parallel calibration)**: ADR 文言「kant のみ」と齟齬、ADR
  改訂が必要、本タスクで対応せず
- **Q1 案 C (.tmp 直読)**: DuckDB の WAL 同期保証なし、stale read リスク
- **Q3 F-2 (sample-size correction `width × sqrt(n / n_target)`)**: Codex H2
  で wall-time prefix censoring が random missing でないと棄却済 (`decisions.md`
  L608)
- **Q6 L-3 (v1 を v2 に書き換え)**: history archeology の喪失、git log
  だけだと旧 prompt の rendered context が読めない

## empirical 起点 (Phase 1 で確定済)

- pilot single-cell natural: **1.87 focal/min** (`data/eval/pilot/_summary.json`)
- run0 3-parallel contended: **1.06 focal/min** (`blockers.md` active incident)
- contention factor ≈ **1.76×** (1.87 / 1.06)
- Codex H1 budget basis: 65 focal/h ≈ 1.08/min (`decisions.md:607`)
- `_RUNTIME_DRAIN_GRACE_S = 60.0` (PR #140 で 30→60 raise 済)

## v2 prompt の章立て

1. **冒頭 metadata** — `main = 0304ea3` / PR #140 merged 前提 / v1 との関係明示
2. **§Phase 0** — pre-flight smoke test (S-2): kant_stimulus_run0 wall=60
   turn=50 dry run、sidecar status=complete + return 0 を確認
3. **§Phase A** — run1 calibration (kant only × 5 wall sequential):
   - run_idx=100..104、wall=120/240/360/480/600 min
   - `--turn-count 1000` で focal=500 early-stop を抑制 (calibration 主旨)
   - 各 cell 完了後 audit + sidecar 確認
4. **§Phase A 結果解析 (Mac 側)** — F-1 + F-4 数式の operator 向け明文化、
   `focal_per_min_observed` 平均 + variance 算出、run2-4 default wall budget
   = 600 min、observed 値次第で +120 min 拡張
5. **§Phase B** — stimulus 全 15 cell (現 v1 §Phase 1 を新 contract で書き換え):
   - run_idx=0..4 × 3 persona、wall=120 (現状維持)、return code 3 / sidecar
     検証を audit step に追加
6. **§Phase C** — natural 全 15 cell + run0 再採取 (現 v1 §Phase 2 の置換):
   - wall は §Phase A 結果から確定 (default 600 min)
   - 3-parallel × 5 run、kant drain timeout fallback は維持
   - run0 を `--allow-partial-rescue` で再採取、partial 判定なら `data/eval/partial/` 隔離
7. **§Phase D** — eval_audit batch + rsync (現 v1 §Phase 3-4 を流用、新 contract 完整):
   - 全 30 cell + 5 calibration cell に対し `eval_audit --duckdb-glob` batch
   - HTTP rsync (`python -m http.server 8765` + curl + md5)、receipt template
8. **§Phase E** — PR 作成 (現 v1 §Phase 5 を流用)
9. **ブロッカー予測 + fallback** — run0 incident 教訓を反映、wall budget 過小評価リスク

## 数式 (F-1 + F-4)

```
focal_per_min_single   = run1 calibration で実測 (期待値 ~1.87)
contention_factor      = 1.76 (pilot single / run0 parallel、run1 で再校正)
focal_per_min_parallel = focal_per_min_single / contention_factor
safety_factor          = 0.85
wall_budget_min        = ceil(focal_target / focal_per_min_parallel / safety_factor)
                       ≈ ceil(500 / 1.063 / 0.85) ≈ 553 → 切上げ 600 min
```

期待値 table (focal_target=500、safety=0.85):

| focal/min observed | parallel? | wall budget |
|---|---|---|
| 1.87 (single) | no | 314 min |
| 1.06 (3-parallel observed) | yes | 555 min |
| 1.08 (Codex H1 pre-run1 estimate) | yes | 545 min |
| 1.87 (single) → 1.063 (parallel via /1.76) | yes | 553 min |

## 影響範囲

- caller 影響ゼロ (prompt 文書、Python コード変更なし)
- 旧 v1 prompt は無傷で残置、冒頭注記に v2 リンク追加のみ
- v2 prompt は新規ファイル → revert で完全復元

## 既存パターンとの整合性

- 旧 v1 prompt の §Phase 0 (dry run) / §Phase 4 (rsync) / §Phase 5 (PR) — 構造を
  v2 で再利用、S-2 smoke test と F-1/F-4 数式を追記
- `data/eval/pilot/_rsync_receipt.txt` rsync receipt template (P3a-finalize で
  validated) を踏襲
- `eval_audit --duckdb-glob` の正確な flag (`src/erre_sandbox/cli/eval_audit.py`)
- `SidecarV1` schema (`src/erre_sandbox/evidence/capture_sidecar.py:60-83`)

## テスト戦略

- 単体テスト: 不要 (prompt 文書のみ)
- 統合テスト: 不要 (本 PR では実走しない、後続 G-GEAR タスクで実施)
- markdownlint: `g-gear-p3-launch-prompt-v2.md` で MD022/MD032 警告ゼロ
- v2 内コマンド snippet を `bash -n` で構文 check (チェック可能な範囲)
- v2 内の `eval_audit` / `eval_run_golden` flag が実 CLI `--help` 出力と一致

## ロールバック計画

- 単一 PR (squash merge 想定)、revert で完全復元
- v1 prompt は無傷、後戻りコストゼロ

## Codex review 投入疑問点 (5 個、Phase 0 で投入)

1. **contention_factor=1.76 の信頼区間**: pilot single 1.87 / run0 parallel 1.06
   の 2 サンプル比較。run1 calibration n=5 (5 wall point × kant single 1 cell)
   から再推定するのは妥当か、それとも別途 3-parallel calibration cell を追加
   すべきか
2. **cooldown 設定の systematic bias**: pilot single = P3a-fix-v2 cooldown=5
   適用後、run0 parallel も cooldown=5 のはず。`COOLDOWN_TICKS_EVAL` の値推移
   を git log で fact-check 依頼
3. **run_idx=100..104 calibration 専用域の downstream フィルタ**:
   `scripts/p3a_decide.py` 等が run_idx ∈ {0..4} を仮定する箇所があるか grep
   して、calibration capture を exclusion filter する実装が必要か
4. **stimulus smoke test の wall 設計**: kant_stimulus_run0 wall=60 turn=50 で
   drain timeout (60s grace) ぎりぎり。安全側 wall=90 min が妥当か、turn=30
   wall=60 min が妥当か
5. **ME-9 re-open 条件との連動**: run1 で observed focal/min が 0.92 (≤55/h)
   を観測した場合、(a) wall 720 min 拡張で run2-4 強行、(b) cooldown 再調整
   ADR 起票して run1 やり直し、(c) Codex review 再起動、のどれを default に
   するか

## 関連参照

- spec hand-off: `.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md`
- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
- run0 incident: `.steering/20260430-m9-eval-system/blockers.md` "active incident"
- 前 PR (CLI fix): `.steering/20260506-m9-eval-cli-partial-fix/` (PR #140 merged、
  main = `0304ea3`)
- v1 prompt: `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md`
- 承認 plan: `~/.claude/plans/sleepy-fluttering-lake.md`

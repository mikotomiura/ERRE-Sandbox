# タスクリスト — m9-eval ME-9 trigger 解釈 ADR (旧称: cooldown-readjust-adr)

## Phase A — ME-9 Amendment 2026-05-07 起票 (PR #142、merged)

- [x] Codex 9 回目 review prompt 起票 (`codex-review-prompt-trigger-interpretation.md`)
- [x] Codex review 実行 (`codex-review-trigger-interpretation.md` verbatim、81K tok)
- [x] Verdict 取得 (hybrid A/C、HIGH 3 / MEDIUM 3 / LOW 1)
- [x] `decisions.md` (本タスク) に Codex review 経緯と採用判断記録
- [x] M9-eval `decisions.md` ME-9 に **Amendment 2026-05-07** ブロック追記
  (rate basis single vs parallel 明示、context-aware trigger zone)
- [x] `g-gear-p3-launch-prompt-v2.md` §A.4 期待値 table を saturation model に
  更新、§B-1 を rate basis 明示で書き直し、§B-1b で run102 resume 手順追加
- [x] `blockers.md` に B-1/B-2 解消、REJ-1 棄却記録
- [x] PR merge (PR #142、ME-9 trigger 擬陽性修正、main=`ab3206d` 等)

## Phase B — Phase A run1 calibration 採取 (G-GEAR、本セッション外で完了)

- [x] G-GEAR で v2 prompt §B-1b の resume 手順実行 (run102/103/104)
- [x] kant only × 5 wall sequential (120/240/360/480/600) 全 cell 完了
  (2026-05-08 18:49)
- [x] G-GEAR HTTP server 経由 md5 receipt + 10 file 配布 (`192.168.3.85:8765`)

## Phase C — Mac 受領 + ADR finalize (本セッション、PR #149 後の handoff)

- [x] HTTP rsync (G-GEAR `192.168.3.85:8765`) で 10 file pull + md5 verify
  (10/10 一致)
- [x] 既存 partial state (`_checksums_run1_partial.txt` + sidecar 2 件) を
  full snapshot で上書き
- [x] DuckDB read_only sanity inspect (5/5 cells、total_rows と sidecar 一致、
  status=partial / drain_completed=true)
- [x] M9-eval `decisions.md` ME-9 に **Amendment 2026-05-08** 追記 (5-cell
  empirical rates / mean=1.587 / contention=1.502 / wall_budget=600)
- [x] 本タスク `decisions.md` に lock-step update + W-2 / W-3 解消方向追記
- [x] 本タスク `tasklist.md` (本書) populate
- [x] 本タスク `blockers.md` で D-1 (run102-104 採取) を解消済に move、
  Phase A 完了で W-2 / W-3 resolved を反映
- [ ] PR 起票 (`feature/m9-eval-phase-a-run1-complete`、calibration data の
  git 取込み + ME-9 Amendment 2026-05-08)

## Phase D — Phase B + C launch prompt 起草 (任意、handoff §4)

- [ ] `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md` の
  §Phase B / §Phase C を base に Phase B+C 起動プロンプト (G-GEAR 投入用) を
  新規作成
  - §Phase B (stimulus 15 cell × cycle_count=6, ~3-5h)
  - §Phase C (natural 15 cell × wall=600 min × 3-parallel, ~24-48h overnight×2)
  - run0 partial 再採取 (§C.3、`--allow-partial-rescue`)
  - ME-9 Amendment 2026-05-08 適用後の trigger zone (3-parallel: <0.55-0.92/min
    or >1.20-1.33/min)

## 完了処理

- [x] design.md は Codex 9 回目 review prompt にて scope 明示済、別途追加なし
- [x] decisions.md は Codex 9 回目 review verbatim 経緯 + 採用判断 + lock-step
  update 2026-05-08 で完成
- [x] requirement.md は当初 working title (cooldown-readjust) と実 scope 乖離
  を decisions.md 冒頭で明示済、修正不要
- [ ] git commit (Phase A: PR #142 merged / Phase C: feature/m9-eval-phase-a-
  run1-complete 起票予定)

## 関連参照

- `.steering/20260430-m9-eval-system/decisions.md` ME-9 Amendment 2026-05-07
  + Amendment 2026-05-08 (本 task で起票)
- `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md` (§A.4 /
  §B-1 / §B-1b update 済)
- `data/eval/calibration/run1/` (10 file rsync 完了、md5 10/10 一致)
- `mac-rsync-and-handoff-prompt.md` (G-GEAR が起草、本 task で execute)

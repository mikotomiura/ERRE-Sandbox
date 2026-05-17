# タスクリスト — DA-17 ADR (ドイツ語失敗 preflight)

## 準備 (Phase 1)
- [x] PR-4 (#189) merged 確認 (gh pr view 189 → MERGED)
- [x] branch `feature/m9-c-adopt-da17-german-failure-preflight` (main 派生) 作成
- [x] `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/` 5 標準 file 起票
- [x] 関連 plan ファイル `C:\Users\johnd\.claude\plans\steering-20260517-m9-c-adopt-pr4-da14-r-bright-pearl.md` Read

## forensic 分析 (Phase 2)
- [x] **DA17-1**: v3 v4 within-language d 8 cell 表 + flip 分析 →
      `decisions.md`
- [x] **DA17-2**: v4 LoRA-on / no-LoRA shard から ドイツ語 utterance
      ≥10 ペア qualitative inspection (langdetect + DuckDB) →
      `decisions.md`
- [x] **DA17-3**: Burrows JSON (de-only、v3 v4) per-window + lang_routing
      内訳 → `decisions.md`
- [x] **DA17-4**: train_metadata + weight-audit + plan-b-corpus-gate
      audit (ja=38.9% anomaly を elevate) → `decisions.md`
- [x] **DA17-5**: prompt / chat template 構造の no-LoRA vs LoRA-on
      identical 検証 → `decisions.md`
- [x] **DA17-6**: 5 仮説 H1〜H5 pre-register (各 evidence-for ≥2 +
      evidence-against ≥2) → `decisions.md`
- [x] **DA17-7 初回案**: PR-5 scope 5 候補 (α/β/γ/δ/ε) 比較 + 初回案
      recommendation (β + ε 併用) → `decisions.md` (`/reimagine` で
      β 単独 + H8 pre-check に refine)

## `/reimagine` (Phase 3)
- [x] 別 Plan subagent で DA-17 結論を zero-base 再生成 (H6/H7/H8 新規
      hypothesis を獲得)
- [x] 初回案と再生成案を decisions.md DA17-7 に併記
- [x] 採用案 (hybrid: β 単独 + H8 pre-check) 確定 + 不採用案 defer
      reason 明示 (α / γ / δ / ε)

## next-session prompt + memory 更新 (Phase 4)
- [x] `next-session-prompt-FINAL-pr5-corpus-rebalance.md` 起票 (採用
      scope verbatim、日本語)
- [x] `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/next-session-prompt-FINAL-pr5-rank16-spike-reject.md`
      に DEFERRED 注記追加 (delete せず)
- [x] memory `project_plan_b_kant_phase_e_a6.md` 更新 (PR-4 #189
      merged + DA-17 結論 + 38.9% ja mass anomaly + 言語非対称
      empirical 教訓)
- [x] memory `MEMORY.md` index 更新 + 日本語デフォルト feedback 追加

## レビュー (Phase 5)
- [x] `pwsh/bash scripts/dev/pre-push-check.{ps1,sh}` 4 段全 pass
      (doc-only PR、ruff format --check / ruff check / mypy src /
      pytest -q、1513 passed / 47 skipped、102 秒)
- [x] Codex review prompt 起票
      (`.steering/<dir>/codex-review-prompt.md`、日本語、HIGH/MEDIUM/LOW
      フォーマット)
- [x] Codex review WSL2 経由実行、`codex-review.md` に verbatim 保存
      (verdict = ADOPT-WITH-CHANGES、HIGH 3 + MEDIUM 4 + LOW 2)
- [x] HIGH 反映: HIGH-1 (H8 stim shard 再生成 + sampling seed)、
      HIGH-2 (`mpnet_de_within_language_d` 指標明定 + 判定基準)、
      HIGH-3 (`uv.lock` を staging から除外、PR description で明示)
- [x] MEDIUM 反映: MEDIUM-1 (H5 qualitative tone down)、MEDIUM-2 (H2
      evidence 整理)、MEDIUM-3 (numbering collision 注記)、MEDIUM-4
      (tick/turn_index audit 結果記録)
- [x] LOW 反映: LOW-1 (本 tasklist 更新)、LOW-2 (`_da17_2_inspect.py`
      docstring 修正)

## ドキュメント
- [x] 本 ADR 自体が doc 更新の中心 (`.steering/` 配下 + memory)
- [ ] glossary 追加なし (用語追加なし)

## 完了処理 (Phase 6)
- [x] `decisions.md` の最終化 (DA17-1〜DA17-7 + `/reimagine` + Codex
      HIGH/MEDIUM/LOW 反映済)
- [x] `tasklist.md` の最終化 (本 file)
- [x] `blockers.md` の最終化 (該当なしを明示)
- [ ] git commit (日本語 message、HEREDOC、CLAUDE.md git ワークフロー準拠、
      Co-Authored-By: Claude Opus 4.7 (1M context))
- [ ] `git push -u origin feature/m9-c-adopt-da17-german-failure-preflight`
- [ ] `gh pr create --base main` (日本語 title + body)
- [ ] `/finish-task` Skill 起動で最終確認

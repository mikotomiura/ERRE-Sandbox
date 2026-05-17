# タスクリスト — PR-3 kant_r8_v4 forensic JSON commit

## 準備
- [x] PR #187 (PR-2) merged 済確認 (`gh pr view 187 --json mergedAt,state`)
- [x] main ブランチに切り替え + pull origin main
- [x] `feature/m9-c-adopt-pr3-kant-r8-v4-retrain` branch 作成 (main 派生)
- [x] kant_r8_v4 forensic JSON 4 file 内容確認 (train_metadata /
      plan-b-corpus-gate / weight-audit / adapter_config)
- [x] v3 forensic 4 file との schema 整合性確認 (key set 完全一致、
      数値のみ変動)
- [x] `.gitignore` で binary file (adapter_model.safetensors /
      checkpoint-* / tokenizer.json 等) 機械除外確認 (git check-ignore -v)

## .steering 起票
- [x] requirement.md 起票 (DP3-1 + HF push 後送り背景)
- [x] design.md 起票 (artefact-only scope + v3 と同 4 file commit)
- [x] decisions.md 起票 (DP3-1: HF Hub upload を PR-5 に後送り)
- [x] tasklist.md (本 file)
- [x] blockers.md 起票 (該当なし、template 形式)

## 実装 (forensic JSON commit)
- [ ] `git add` で 4 file (adapter_config / plan-b-corpus-gate /
      train_metadata / weight-audit) を staging
- [ ] `git diff --cached --stat` で commit size 確認 (想定 ~10 KB
      以下、binary 混入なら万 KB 超で即検出)
- [ ] 機械的に binary が漏れていないことを `git status --short` で
      最終確認 (v4 directory 配下 binary が untracked のまま残ること
      を期待)

## レビュー
- [x] code-reviewer は今回 skip (本 PR は artefact only で実装 diff ゼロ、
      Codex review で forensic 整合性 + DP3-1 妥当性を直接 verify したため
      重複削減)
- [x] Codex independent review (WSL2 経由、PR-2 と同経路):
  - [x] codex-review-prompt.md 起票 (焦点 a-d は requirement.md と
        design.md verbatim cite + DP3-1 妥当性)
  - [x] WSL2 codex exec (`xhigh` reasoning、~5 min)
  - [x] codex-review.md verbatim 保存 (sandbox read-only のため main
        agent 側で書き出し)
  - [x] **Verdict: ADOPT-AS-IS** (HIGH 0 / MEDIUM 0 / LOW 1 件 = staged
        size wording note のみ、design.md / requirement.md の "~10 KB"
        言い回しを精緻化して反映)

## ドキュメント
- [ ] PR-4 (DA-14 rerun verdict) + PR-5 conditional 用 next-session
      prompt 起票:
      `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/
      next-session-prompt-FINAL-pr4-da14-rerun-verdict.md`
      (PR-5 = ADOPT→HF push / REJECT→rank=16 spike を併記)
- [ ] memory `project_plan_b_kant_phase_e_a6.md` 更新 (PR-3 push +
      DP3-1 + PR-5 verdict 分岐)

## CI parity + push
- [ ] `pwsh scripts/dev/pre-push-check.ps1` で 4 段 (ruff format
      --check / ruff check / mypy src / pytest -q) 全 pass
      (本 PR は src/ 変更ゼロのため全 pass 想定)
- [ ] git commit (HEREDOC で commit message、Co-Authored-By 付き)
- [ ] git push -u origin feature/m9-c-adopt-pr3-kant-r8-v4-retrain
- [ ] gh pr create --base main (PR description で v3/v4 forensic
      対比表 + DP3-1 + PR-4/PR-5 conditional graph)
- [ ] PR URL を user に返却

## 完了処理
- [x] design.md は本セッション開始時の状態で確定 (artefact-only で
      新規実装ゼロのため finish-task 時の design 更新なし)
- [x] decisions.md 確定 (DP3-1 のみ、他に局所判断なし)
- [ ] git commit (上記 push step で完了)
- [ ] 次セッションは PR-4 (DA-14 rerun verdict) を起動

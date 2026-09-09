# retrospective — M13 M2 Layer1 実コード Loop

## 結果
全 6 issue (I1-I6) 緑 + 統合フル pre-push 4 段 ALL CHECKS PASSED (3581 passed) + DG-2 WSL byte parity PASS +
TASK-POST cross-review (code-reviewer LGTM + Codex degrade、MEDIUM 2 反映) → **PR #72**。各 issue 1 attempt で緑
(no_progress/budget stop なし)。

## うまくいったこと
- **subagent-per-issue で orchestrator context を温存**: heavy な実装 (society.py 1061 行等) は subagent
  fresh context で、orchestrator は簡潔サマリ + test-runner 独立検証 + commit のみ。8 commits を 1 session で回せた。
- **verify_level=recheck の独立再検証が機能**: 各 issue で test-runner(Haiku) が exit code を独立回収し self-申告を
  打ち消し。全て 6-7/7 exit 0 で客観確定。
- **I3 の gap を I4 で閉じた**: I3 で「dialog/affinity が record-mode driver で未発火」を検出 (DG-6)、I4 worker に
  dialog 配線を明示指示 → 実 driver で dialog 発火 (vacuous でない) を実現。over-read (proximity 同居だけで N体
  社会と主張) を回避。
- **決定的発見の catch**: I4 で uuid4 dialog_id の checksum 混入 latent 非決定を worker が実測検出 → per-pair
  seeded 採番で封鎖。silently determinism を壊しかねなかった。
- **DG-2 WSL byte parity を orchestrator step として分離**: cross-machine 検証を worker から切り出し、WSL-native
  venv (uv、core のみ) で golden byte 一致を実測。6 桁量子化が libm drift を封鎖することを Linux で確証。

## 学び / 次回への改善
- **Codex TASK-POST が Windows sandbox で degrade**: pwsh exec が `CreateProcessAsUserW 1312` で不可、最終
  verdict 未 emit。次回は `.codex/config.toml` の sandbox/exec 設定を事前確認、または WSL 側で Codex を回す
  検討。今回は code-reviewer(Opus) primary + narration fold-in で honest に処理。
- **spend guard の docstring 規約は移植不可**: society.py の raw-substring belt-and-suspenders を handoff に流用で
  false-positive (docstring 散文)。他モジュール guard 拡張は AST-only に留める (教訓、blockers.md)。
- **依存の線形性**: I1→I2→I3→I4/I5→I6 はほぼ線形ゆえ 1 feature branch 順次 land (B precedent 同型) が worktree
  並列より単純で有効だった。parallel 化の余地は I4/I5 のみで限定的。

## follow-up (LOW、別タスク)
blockers.md 参照: discovery guard 完全性 / private 越境 public seam 化 / cross-agent 非リーク test。
Layer2 mirror-sim ADR or 別 cleanup issue で対処。

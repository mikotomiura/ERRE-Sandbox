# Codex independent review prompt — PR-4 kant_r8_v4 DA-14 rerun verdict (local-path load)

**Scope**: v3 pipeline 派生 (新規設計判断なし) で kant_r8_v4 (rank=8、PR-2
`.mean()` reduce 後 retrain) に対する DA-14 rerun verdict を計算。verdict =
**PHASE_E_A6 (REJECT)**、direction discipline は部分解消 (E5-large の
sign-flip 強度半減) だが encoder agreement + Burrows axes は依然 FAIL。
PR-5 = rank=16 spike retrain への pivot を提案。

**Context**:
- PR #186 (DA-16 ADR、2026-05-17 merge): 候補 A 採用
- PR #187 (PR-2、2026-05-17 merge): WeightedTrainer `.mean()` reduce
- PR #188 (PR-3、2026-05-17 merge): v4 forensic JSON commit + DP3-1
  (HF push 後送り、PR-4 が local-path 依存)
- 2026-05-17 同 session 内で PR-3 merge 直後に PR-4 を実施 (eval shard
  4 runs ~25 min、post-eval pipeline ~3 min、direct G-GEAR 経路)
- v3 verdict (PR #184): PHASE_E_A6 (REJECT)、encoder agreement + Burrows
  FAIL、direction disagreement (MPNet −0.5264、E5-large +0.4781、lex5
  +0.1805、BGE-M3 +0.3317)
- **v4 verdict (本 PR-4)**: PHASE_E_A6 (REJECT)、direction 部分解消:
  MPNet −0.5211 (~不変)、E5-large +0.2014 (sign-flip 強度半減)、lex5
  +0.2596 (slight 悪化)、BGE-M3 +0.6385 (悪化)。Burrows reduction%
  −1.54% (v3 −1.95% から +0.41 pt 改善だが gate 遠い)、ICC 0.8768 (PASS
  維持)、Throughput 100.05% (PASS 維持)
- **PR-5 経路**: REJECT 経路 = rank=16 spike retrain (`kant_r16_v1` 生成、
  `.mean()` reduce 修正済 WeightedTrainer 経由、SGLang `--max-lora-rank
  16` VRAM fit spike 含む)

**Review focal points (HIGH/MEDIUM/LOW で報告)**:

## (a) WeightedTrainer fix の部分効果の解釈妥当性

- E5-large per-encoder natural d が v3 +0.4781 → v4 +0.2014 (Δ −0.2767)
  の sign-flip 強度半減を「WeightedTrainer Blocker 2 修正の effect」と
  解釈することは empirical に妥当か
- DA-16 候補 A の outcome (ii) "REJECT, direction converged but |d| 不足
  → capacity 仮説、PR-5 rank=16 を推進" に該当する判定は decision tree
  と整合しているか
- MPNet (不変) と lex5 / BGE-M3 (悪化) を "rank=8 capacity 制限内で意味的
  方向が de_monolog に偏った結果、character/lexical signal が伸びる余裕
  なし" と解釈する根拠は十分か (PR-5 で検証する仮説の articulation が
  正しいか)
- 代替解釈 (例: WeightedTrainer fix が一部 encoder で正効果、他では悪影響
  という mixed signal、または bootstrap CI 範囲内で偶然の direction 移動)
  との優先順位は妥当か

## (b) PR-5 経路選択 (REJECT → rank=16 spike) の論理妥当性

- DA-16 候補 A の outcome 4 パターン:
  > (i) ADOPT → Blocker 2 が dominant、weighting 修正で完了
  > (ii) REJECT, direction converged but |d| 不足 → capacity 仮説、
  >      PR-5 rank=16 を推進
  > (iii) REJECT, direction disagreement 残存 → corpus/encoder mismatch
  >       の深掘り (Plan C 候補)
  > (iv) REJECT, eval_loss 上昇 → fix 自体に regression、PR-2 を revert
- 本 PR-4 結果 (eval_loss 改善 -0.00213 + E5-large 半減 + MPNet/Burrows
  不変) は (ii) と (iii) の中間に位置する (E5 は converge、lex5/BGE-M3
  は disagreement 残存)。**(ii) 一択** とする判定の論理性は妥当か、
  あるいは (iii) Plan C 検討を併記する方が安全か
- rank=16 spike が「rank capacity 単独効果を切り分ける」と pre-register
  する PR-5 設計は、上記 mixed signal を受けても decisive evidence を
  生むか (rank=16 で MPNet |d| 拡大 + Burrows reduction% gate clear なら
  (ii) 確定、それでも FAIL なら (iii) Plan C へ pivot)

## (c) Burrows reduction% +0.41 pt 改善の有意性評価

- v3 Burrows reduction% −1.9482% (CI lo −5.07 hi 1.14) → v4 −1.5408%
  (CI lo −4.50 hi 1.34)、Δ +0.41 pt の改善が "noise within bootstrap
  CI" か "signal of partial fix effect" かの分類
- CI 重なり (v3 [-5.07, 1.14] と v4 [-4.50, 1.34]) が大きく overlap して
  いるため、改善が統計的に有意ではない可能性
- 本 PR description でこの改善を "slight 改善 (gate 遠い)" と表現する
  ことの妥当性、より conservative な "within-CI noise" 表現の方が適切か

## (d) script 派生の forensic 一貫性

- v4 用 3 script (`launch_sglang_plan_b_v4.sh` / `run_plan_b_eval_sequence_v4.sh`
  / `run_plan_b_post_eval_v4.sh`) が v3 script の adapter identifier +
  checkpoint path + 出力 path 差し替えのみで構成され、新規ロジック追加
  ゼロを保つこと (v3 と v4 で同一 pipeline = apples-to-apples 比較
  guarantee)
- `run_plan_b_eval_sequence_v4.sh` のみ v3 から大きく改変 (REPO 変数撤廃 +
  Git Bash on Windows 経由起動 pattern、v3 の WSL2 `/mnt/c/...` path
  + Windows python.exe 引数誤解釈問題を解決)。この変更が forensic 数値に
  影響しないことを assert できるか (両 script で同 `tier_b_pilot.py` を
  同 invocation 引数で起動、Python は同 Windows venv、SGLang は同 WSL2
  port 30000 経由、cwd 違いのみ)
- v3 verdict shard `data/eval/m9-c-adopt-plan-b-verdict/` を本 PR で
  削除していない (forensic 完全性のため v4 と並列共存) ことが git status
  で確認できるか

## (e) DA-14 thresholds 不変方針の遵守 (DA16-4)

- 本 PR-4 verdict が REJECT になったことで「閾値が厳しすぎる」議論が
  浮上する可能性があるが、DA16-4 で **Plan B でも v3 と同 gate を不変**
  と確定済
- `da14-verdict-plan-b-kant-v4.md` の thresholds 表が v3 verdict.md と
  完全一致 (`Vendi natural d ≤ -0.5`、`Burrows reduction% ≥ 5.0 + CI
  lower > 0`、`ICC ≥ 0.55`、`Throughput pct ≥ 70.0%`) であること
- PR-5 (rank=16) でも thresholds 不変が継続されることを `next-session-
  prompt-FINAL-pr5-rank16-spike-reject.md` で明示しているか

**報告フォーマット (verbatim 保存)**:

- 各 focal point ごとに HIGH / MEDIUM / LOW を分類して列挙
- HIGH 0 件なら "Verdict: ADOPT-AS-IS"
- HIGH ≥ 1 件なら "Verdict: ADOPT-WITH-CHANGES" + 反映必須事項
- MEDIUM/LOW は採否を本 session で決定 (採用なら decisions.md DP4-*
  追記、不採用なら blockers.md に defer 理由付記)

**参照ファイル (Codex に Read させる)**:

- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/requirement.md`
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/design.md`
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/decisions.md`
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/da14-verdict-plan-b-kant-v4.md` (本 PR 主 deliverable + v3 v4 対比表)
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/da14-verdict-plan-b-kant-v4.json` (raw verdict 数値)
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/next-session-prompt-FINAL-pr5-rank16-spike-reject.md` (PR-5 経路)
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-verdict-plan-b-kant.md` (v3 verdict、対比 baseline)
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DR-1
- `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜DA16-4
- `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/decisions.md` DP3-1
- `scripts/m9-c-adopt/launch_sglang_plan_b_v4.sh`
- `scripts/m9-c-adopt/run_plan_b_eval_sequence_v4.sh`
- `scripts/m9-c-adopt/run_plan_b_post_eval_v4.sh`
- `scripts/m9-c-adopt/run_plan_b_eval_sequence.sh` (v3 比較、cwd 差分の
  forensic 影響評価)

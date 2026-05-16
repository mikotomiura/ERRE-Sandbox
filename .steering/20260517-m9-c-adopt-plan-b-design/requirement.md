# m9-c-adopt Phase 2 — Plan B (Candidate C targeted hybrid retrain) design + collector driver

## 背景

PR #179 (`feature/m9-c-adopt-da15-implementation`, Plan A = Vendi kernel
swap) は **kant REJECT** (`.steering/20260516-m9-c-adopt-da15-impl/da15-
verdict-kant.md`) で merge 済。Plan A は eligible encoder ゼロで quorum
1/3 (ICC のみ pass) の不成立。DA-15 ADR D-1 (`.steering/20260516-m9-c-
adopt-da15-adr/decisions.md`) の sequential escalation 経路に従い、
Phase 2 = Plan B (Candidate C targeted hybrid retrain) を起票する。

Plan A の non-gating observation:

- **MPNet within-de d = -0.72** (point gate clear、CI gate fail) — LoRA が
  German 内で diversity を下げている兆候
- **E5-large within-en d = -0.58** (point gate clear、CI gate fail) — 同様の
  per-language signal
- **BGE-M3 natural d 符号反転** (+0.23) — retrieval-encoder artefact

→ 解釈: LoRA は per-language slice で persona-style diversity を下げる
効果があるが、global mixed-language 6-window bootstrap では bootstrap
sampling variance が大きすぎて統計的有意性が出ない。Plan B は per-language
diversity 強化を主目標とする。

Plan B 起動 rationale (Codex MEDIUM-1、ADR D-2 維持): **DA-14 verdict
REJECT + Candidate C spec pre-authorisation のみ**。DI-5 de+en mass
0.489 < 0.60 は **soft warning のまま固定** (retroactive hard trigger
化しない)、Plan B shape (de/en focus + ≥60 token + monolog/long-form
filter) を guide する役割。

## ゴール

本セッション (~7-8h) で以下を完遂:

1. Plan mode + `/reimagine` (Task tool subagent dispatch) で V1/V2/hybrid
   採用判定 + decisions.md 記録
2. de-focused monolog collector driver
   (`scripts/m9-c-adopt/de_focused_monolog_collector.py`) 実装 + unit test
3. `src/erre_sandbox/training/dataset.py` 拡張: language-stratified split
   option 追加 (de monolog re-cast の eval leak 防止)
4. achieved corpus stats audit script (de+en mass ≥ 0.60 + N_eff > 1500 +
   top 5% weight share < 0.35)
5. D-2 allowlist for Plan B verdict (HIGH-2 enforcement 機構の継承)
6. G-GEAR 採取準備 (WSL2 / Windows native ENV + PYTHONUTF8=1 経路 +
   stimulus list + shard naming with merge SHA embedding)
7. Codex independent review + HIGH 反映
8. commit + push + `gh pr create`

retrain 実行 (~20h G-GEAR overnight)・DA-14 rerun verdict は **次セッション**。

## スコープ

### 含むもの

- 新規 driver: de-focused monolog collector (G-GEAR で de-biased stimulus
  + ≥60 token + monolog/long-form bias で 250-500 example 採取)
- `dataset.py` の language-stratified split option (kw-only flag、既存
  group-aware split に optional layer 追加)
- audit script: achieved corpus stats を機械的に check (run gate)
- Plan B 専用 D-2 allowlist (本 PR merge 後の retrain verdict で使用)
- G-GEAR 採取 runbook (ENV、stimulus list、shard naming)
- Codex independent review

### 含まないもの

- retrain 実行 (~20h G-GEAR overnight、別セッション)
- DA-14 rerun verdict 計算 (retrain 完了後の別 PR)
- Plan C (rank=16) の起票 (Phase E A-6 まで延期、ADR scope 外)
- Hybrid H-α (Plan A pre-stage の retroactive 適用、ADR で Plan A pass 時
  保留方針確定済、本 PR では含めない)
- nietzsche / rikyu の Plan B 展開 (kant ADOPT 後の Phase C で判断)
- SGLang サーバー設定変更 (既存 multi_pin_sanity.sh 経路を再利用)

## 受け入れ条件

- [ ] `feature/m9-c-adopt-plan-b-driver` branch (main 派生)
- [ ] `.steering/20260517-m9-c-adopt-plan-b-design/` の 5 標準 file
- [ ] `/reimagine` で V1 / V2 / hybrid 採用判定 + decisions.md 記録
- [ ] de-focused monolog collector driver 実装 + unit test
- [ ] `dataset.py` の language-stratified split option 追加 + unit test
- [ ] achieved corpus stats audit script + unit test
- [ ] G-GEAR 採取の stimulus list + shard naming + ENV 確定
- [ ] D-2-style encoder allowlist for Plan B verdict (HIGH-2 enforcement
      機構の継承)
- [ ] Codex independent review 起票 + HIGH 反映
- [ ] commit + push + `gh pr create` (design + driver + 採取準備、
      retrain 実行前)

## 留意点

- **HIGH-3 遵守**: DA-14 thresholds は不変、Plan B 採用判定は **achieved
  corpus stats + empirical DA-14 rerun verdict のみ** で行う (Codex
  MEDIUM-2 反映、predicted d は non-gating prior)
- **Codex MEDIUM-1 維持**: DI-5 de+en=0.489 < 0.60 は **soft warning** の
  まま固定
- **Plan A non-gating observation の活用**: per-language diversity 強化を
  主目標、global mixed-language diversity 改善は二次目標
- **BGE-M3 sign flip 教訓**: Plan B 採用判定 eval encoder panel に MPNet
  + E5 + BGE-M3 + lexical-5gram を含め、encoder agreement axis を追加
- **eval_loss monitoring**: v2 retrain の eval_loss step 2000=0.166 →
  final=0.180 mild overfit を踏まえ、Plan B retrain は **early stopping**
  (eval_loss 上昇 ≥ 3 step で halt) を必須化
- **manifest convention 維持**: `data/lora/m9-c-adopt-v2/<adapter>/manifest
  .json` に encoder name / version / git SHA + 本 PR merge SHA を埋め込む
  (DA-11)

## 関連ドキュメント

- `.steering/20260516-m9-c-adopt-da15-impl/da15-verdict-kant.md` (Plan A
  REJECT verdict + non-gating observations)
- `.steering/20260516-m9-c-adopt-da15-impl/decisions.md` D-α-FAIL
- `.steering/20260516-m9-c-adopt-da15-adr/decisions.md` D-1
- `.steering/20260516-m9-c-adopt-da15-adr/design.md` Phase 2 セクション
- `.steering/20260516-m9-c-adopt-da15-adr/codex-review.md` MEDIUM-1
- `.steering/20260513-m9-c-adopt/decisions.md` DA-11 + DA-13 + DA-14
- `.steering/20260515-m9-c-adopt-retrain-v2-verdict/decisions.md` DI-1〜DI-5
- `src/erre_sandbox/training/dataset.py` (monolog re-cast 実装)
- `src/erre_sandbox/training/weighting.py` (language constant、N_eff)
- `scripts/m9-c-adopt/tier_b_pilot.py` (generation-side prompt base)
- `scripts/m9-c-adopt/validate_multiturn_shards.py` (shard validation)

# Codex independent review — DA-16 ADR (kant Plan B PHASE_E_A6 順序判断)

## 起動経路

本セッションで WSL2 Ubuntu 22.04 に Node 20 (`apt-get install -y nodejs`、
NodeSource setup_20.x) + Linux native Codex CLI v0.130.0
(`npm install -g @openai/codex`) を構築。`CODEX_HOME=/mnt/c/Users/johnd/
.codex` で Windows 側 auth.json + config.toml を流用、cwd
`/mnt/c/ERRE-Sand_Box` (Windows mount) でプロジェクトの `.codex/config.
toml` (`model = gpt-5.5` / `model_reasoning_effort = xhigh`) を pick-up。

起動 invocation:
```bash
wsl -d Ubuntu-22.04 -- bash -c '
  export CODEX_HOME=/mnt/c/Users/johnd/.codex && \
  cd /mnt/c/ERRE-Sand_Box && \
  cat .steering/20260517-m9-c-adopt-da16-design/codex-review-prompt.md | \
  codex exec --skip-git-repo-check -c model_reasoning_effort=xhigh
'
```

Codex CLI process は本セッション中 background で起動、~10 min 経過時点で
stdin/file enumeration 段階が完了し steering / weighting.py / 4 axis
verdict 関連の読み込みが進行していたが、user (Hamada) から並行 channel
で要点の review feedback が得られたため、本セッションは user feedback を
**authoritative review** として採用、Codex CLI の background process は
budget 超過リスク回避のため `TaskStop` で停止。本 file は user feedback を
verbatim に近い形で記録した review summary。

## Review feedback (user/Hamada verbatim)

> plan 中の「v3 と v4 の eval_loss は直接比較不能」は少し言い過ぎです。
> 現行コードでは eval examples は sample_weight=1.0、eval batch も 1
> なので、eval_loss 自体は標準 CE として比較可能です。比較不能になるのは
> 主に train_loss の scale と学習軌道の意味。ここはドキュメントだけ
> 直すとよさそうです。
>
> 3 つ目。テストは必ず batch=1 の loss 値 と gradient norm の両方を見る
> べきです。これは plan 通りで OK。加えて、既存 batch=2 テストは今の
> fixture だと per-example loss が同じで、weight 効果の検出力が弱いので、
> できれば「per-example loss が異なるケース」も入れるとより硬いです。
>
> なので実装方針としては:
>
> - weighting.py は `.sum()/weights.sum()` から `.mean()` へ
> - docstring を「batch=1 + grad_accum で weight を gradient に乗せる
>   ため」と更新
> - train_kant_lora.py の WeightedTrainer.compute_loss は触らない
> - test_weighted_trainer.py に batch=1 loss scaling / gradient scaling
>   を追加
> - docs の eval_loss 直接比較不能 表現だけ少し弱める

## HIGH 指摘 (本 PR 内で反映)

### HIGH-1: eval_loss 比較性に関する記述が過剰

**該当箇所**:
- `decisions.md` DA16-2 トレードオフ section:
  > 「**絶対 loss 値の変化**: 既存 v3 retrain の `eval_loss=0.18259` と
  > v4 retrain の eval_loss は **直接比較できなくなる** (semantic は同等
  > でも scale が変わる)。」
- `design.md` 影響範囲 section:
  > 「`compute_weighted_causal_lm_loss` の意味論変更 → v3 の `eval_loss=
  > 0.18259` と v4 の eval_loss は **直接比較不能**」
- memory `project_plan_b_kant_phase_e_a6.md`:
  > 「eval_loss は v3 v4 間で **直接比較不能** (scale 変化、DA16-2
  > トレードオフ参照)」

**問題**: `src/erre_sandbox/training/train_kant_lora.py:761-765`:
```python
# Eval examples carry sample_weight=1.0 so the WeightedTrainer's
# compute_loss reduces to a standard (un-weighted) mean over the eval
# batch (design.md S-5).
for ex in eval_examples:
    ex["sample_weight"] = 1.0
```

eval batch=1 (`per_device_eval_batch_size=1`、DR-6) + sample_weight=1.0
の組み合わせなら:
- 旧式: `(l[0] * 1.0) / 1.0 = l[0]`
- 新式 (`.mean()`): `(l[0] * 1.0).mean() = l[0]`

→ **eval_loss は両式で同一値**。v3 v4 間で標準 CE として比較可能。
不能になるのは **train_loss scale + 学習軌道の意味 (weighted vs
unweighted gradient による convergence path 変化)** のみ。

**修正方針**: docs を「eval_loss 自体は比較可能、train_loss scale +
学習軌道の意味のみ非比較可能」に書き換える。

### HIGH-2: 既存 batch=2 test fixture の weight 検出力が弱い

**該当箇所**:
- `tests/test_training/test_weighted_trainer.py:55-111`
  `test_weighted_trainer_compute_loss_weighted_sum_matches_manual`

**問題**: 既存 fixture (`_build_logits_targeting` で全ターゲットに同じ
margin=2.0) では per-example CE が両 example 同一になるため、weights
を `[3.0, 1.0]` にしても expected = unweighted mean = per_example_loss[0]
と等しく、weight 効果が assertion 上でゼロ。test 自体は数式の正しさを
検証するが、**weight 効果の "回帰検出力" が弱い**:

```python
# 同 file L102-111 で test 自身が明示:
# The two examples are constructed to have IDENTICAL per-token CE per
# position (same margin construction), so per_example_loss is the same
# for both. The weighted mean then collapses to that shared value
# regardless of the (3.0, 1.0) weight vector.
```

**修正方針**: PR-2 で既存 2 件の expected を `.mean()` 基準に書き換える
だけでなく、**新規 batch=2 test 1 件追加** — 「per-example loss が異なる
fixture (例: example A は margin=2.0、example B は margin=0.5)」で
weight 効果が weighted mean に反映されることを assert。これにより既存
fixture の盲点を補強し、後続 PR で reduce 式が再変更された場合に確実に
fail させる。

## MEDIUM 指摘

(本 review session では特になし。Codex CLI background が完走していれば
追加 MEDIUM が出ていた可能性あるが、user feedback で要点 3 つに集約
済みとして処理。)

## LOW 指摘

(本 review session では特になし。)

## Verdict

**ADOPT-WITH-CHANGES** — HIGH-1 (eval_loss 比較性) + HIGH-2 (batch=2
test fixture 強化) を本 PR 内で反映、続 PR-2 用 next-session prompt にも
test plan の追加項目を反映。

修正後に commit + pre-push CI parity → push + `gh pr create`。

## 反映 trace

- `decisions.md` DA16-2 トレードオフ section: HIGH-1 反映 (修正後)
- `design.md` 影響範囲 / テスト戦略 sections: HIGH-1 + HIGH-2 反映 (修正後)
- `next-session-prompt-FINAL-pr2-weighted-trainer-fix.md`: HIGH-2 test
  plan 追加 + HIGH-1 eval_loss 注記の書き換え (修正後)
- memory `project_plan_b_kant_phase_e_a6.md`: HIGH-1 反映 (修正後)

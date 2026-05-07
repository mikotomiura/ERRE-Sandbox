# m9-eval-phase2-run1-calibration-prompt

## 背景

2026-05-06、PR #140 (`feat(eval): m9 — partial-publish CLI fix + eval_audit gate`、
main = `0304ea3`) で ME-9 ADR の CLI fix + sidecar + audit gate が main へ反映
された。これにより partial publish が機械的に区別可能になり、Phase 2 run1
calibration の実行前提が整った。

しかし、現行の `g-gear-p3-launch-prompt.md` は §Phase 3 audit step のみ新
contract に書き換わっており、§Phase 1/2 採取と §empirical 工数推計は依然
**wall=360** (run0 incident の元凶) のまま。**そのまま G-GEAR で起動すると
run0 incident を再現するリスク** がある。

ME-9 ADR は run1 を「kant のみ 1 cell × wall 600 min single calibration」で
120/240/360/480/600 min の 5 サンプル点を取り、focal/min から run2-4 の wall
budget を empirical 確定する方針。本タスクはこの方針を **G-GEAR 側で `/clear`
後にコピペ可能な launch prompt v2 として起票** する Mac 側の planning タスク。

## ゴール

`g-gear-p3-launch-prompt-v2.md` が `.steering/20260430-m9-eval-system/` 配下に
起票され、以下を含む状態:

1. run1 calibration 専用の手順 (kant 1 cell × wall 600 min single、または 5
   サンプル点 sweep、設計は Plan mode で確定)
2. audit step は新 contract (`eval_audit --duckdb-glob ... --focal-target 500`)
3. Mac/G-GEAR HTTP rsync workflow (md5 + sidecar + DuckDB + cognition_period
   実測の receipt)
4. run2-4 の wall budget 決定ロジック (focal/min ratio から target=500 を
   逆算する数式)
5. 旧 `g-gear-p3-launch-prompt.md` との関係を冒頭で明示 (置換 / supersede /
   並列のいずれか、Plan mode で判断)
6. (高難度判断時のみ) 着手前 Codex independent review verbatim を併走

## スコープ

### 含むもの
- `g-gear-p3-launch-prompt-v2.md` の起票
- run1 calibration の手順設計 (Plan mode + Opus + 必要なら `/reimagine`)
- audit step の新 contract 反映 (本 PR #140 の `eval_audit` 仕様)
- rsync receipt フォーマット (P3a-finalize 2026-05-05 で validated パターン
  を踏襲)
- run2-4 wall budget 決定の数式 / 判断基準の明文化
- 旧 launch prompt との関係定義 (supersede 注記または冒頭リンク)
- (高難度判断時) `codex-review-prompt-...md` 起票 + Codex `gpt-5.5 xhigh`
  review + verbatim 保存

### 含まないもの
- run1 の **実走** 自体 (G-GEAR タスク、本タスクは prompt 起票のみ)
- run2-4 の実走および merge 後の matrix 確定 (M9-eval 全体タスクへ持ち越し)
- CLI コード修正 (PR #140 で完了済)
- Mac 側の Tier B/C metric 計算 (別タスク、P3 完了後)
- vLLM / SGLang / LoRA 周辺 (M9-B 系統)

## 受け入れ条件

- [ ] `g-gear-p3-launch-prompt-v2.md` が `.steering/20260430-m9-eval-system/`
  配下に作成され、上記 6 項目を含む
- [ ] markdownlint MD022/MD032 警告ゼロ (今回の PR では blockers/decisions の
  cleanup を含めるか defer かは判断)
- [ ] run1 calibration の "1 cell vs 5 sample sweep" 設計判断が `decisions.md`
  に記録されている
- [ ] audit step が PR #140 の `eval_audit --duckdb-glob` 構文で記述
- [ ] rsync receipt フォーマットが現行 P3a と一貫 (`md5 -r` + sidecar +
  cognition_period 行)
- [ ] run2-4 wall budget 決定ロジックが運用者にとって明確 (例: `target_focal /
  observed_focal_per_min × safety_factor`)
- [ ] 旧 `g-gear-p3-launch-prompt.md` の冒頭に「v2 へ移行、本 prompt は legacy
  reference」の注記が追加されている
- [ ] (高難度判断時) Codex review verbatim を `codex-review-...md` に保存、
  HIGH 全反映、`.codex/budget.json` 更新
- [ ] PR description で v1 prompt との差分を明示し、ME-9 ADR をリンク参照

## 関連ドキュメント

- spec hand-off: `.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md`
- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9 ("Phase 2 run0
  wall-timeout incident: CLI partial-publish contract + run1 calibration")
- incident: `.steering/20260430-m9-eval-system/blockers.md` "active incident:
  Phase 2 run0 wall-timeout (2026-05-06)"
- Codex review (incident): `.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.md`
- 旧 launch prompt: `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md`
- 関連 memory:
  - `project_m9_eval_cli_partial_fix.md` (PR #140 merged、本タスクの前提)
  - `project_m9_eval_phase2_run0_incident.md` (run0 incident、本タスクの動機)

## 運用メモ

- タスク種別: **その他** (prompt / doc 起票、`/add-feature` でも `/fix-bug` でも
  ない。`/reimagine` 単独 + Plan mode で進める)
- 破壊と構築 (`/reimagine`) 適用: **Yes (推奨)**
- 理由: CLAUDE.md 高難度判定の以下に該当
  - **設計判断を伴う**: run1 calibration の手順 (1 cell vs 5 sample sweep
    vs adaptive)、wall budget 決定ロジックの数式、旧 prompt との関係 (supersede
    vs link) のいずれも複数案ありうる
  - **公開 API 相当**: launch prompt は G-GEAR 側 operator が verbatim 実行
    するため、書き方の不備が直接 incident を起こしうる
  - run0 incident で「Claude 単独案」が破綻した実例あり、同種バイアスを避ける
    ため `/reimagine` + 必要なら Codex independent review で多角化
- 前任タスク: `.steering/20260506-m9-eval-cli-partial-fix/` (PR #140 merged)
- 後続タスク: G-GEAR セッション (run1 実走) → Mac セッション (受信解析、
  run2-4 wall budget 確定、matrix 計画起票)

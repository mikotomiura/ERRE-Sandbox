# retrospective — M13 ECL v0 determinism hardening Phase 1

## 成果
FROZEN ADR の 5 determinism 漏れ (P1/P2/W/R/C) を 3 縦スライスで塞ぐ superseding 実装を統合ブランチ
`feat/ecl-v0-hardening` に land。単一 PR (`→main`) 予定。

- **α (4d25425)** = P2 + W: Plane2 を outcome union 化 (raised/unparseable replay 再現) + record-mode の
  wall_clock/created_at pin。pre-push 3364 passed。
- **β (aea74d8)** = R: `_rank_scope` を truncation 前に `(-strength,created_at,id)` 全順序化。golden 不変 (実測)。
  full regression 3366 passed。
- **γ (26ab07e)** = P1 + C + re-bake + version: RNG memoize (run-sequence) + checksum canonical + golden v2 再生成
  (checksum `11a4554…`) + `MANIFEST_SCHEMA_VERSION -2`。2x-bake 決定的。3369 passed。

## Loop Engineering 運用
- grill (未解決分岐 0)・issue-slicing (3 縦スライス) を Skill 実起動。
- 実装は **subagent (fresh context) を逐次 dispatch** で実現 (user 指摘「別シェルなら context 問題なし」を反映)。
  各 slice が独立 full context、orchestrator は結論サマリのみ受領 → 単一セッション肥大を回避。
- **単一ブランチ逐次**を採用 (worktree 並列の代替): α/β/γ はファイル非交差、単一エージェント逐次では worktree
  隔離の利得は index 競合回避のみ。「α・β merge 後 γ bake」の ADR 要件は「γ bake が α+β を含む tree で走る」で充足。

## TASK-PRE Codex (issue 分解の第二意見)
Adopt-with-changes、HIGH なし。sequencing 主張 (α/β 独立 merge 可・γ last) 妥当。5 findings 反映
(詳細 = `codex-taskpre-reflection.md`)。決定的 = **β golden-invariance を orchestrator が実測確認** (Codex LOW-2
「1 memory/tick 不正確、余分 0001-01 有」を受け、candidates ≤ k_ecl=8 で truncation 不発を実 test で確定)。

## TASK-POST /cross-review 統合結果 (二者レビュー)
### 対象
範囲 `c0a5080..HEAD` / src 5 ファイル + golden 4 fixtures + test 5 ファイル / 統合 CI 緑 SHA 26ab07e (以降 loop docs のみ)。

### 一致点 (両者・高確度)
- **HIGH なし = Mergeable** (両者)。
- raised replay の stream 前進 (再送前に index/_used 前進) + driver の len(used) 差分対応付け = correct。
- flag-off byte-invariance 保持。後方互換 (`data.get("outcome","ok")`) OK。
- checksum canonical (非有限 raise) + `_rng_cache` frozen-dict mutation = correct。
- golden re-bake + 2x-bake gate が {P1+C+W+β 波及} を十分カバー。
- measurement 非再入 (evidence/spdm/runningness import 皆無、AST guard 維持)。arch/GPL/cloud 違反なし。

### 相違点
- **code-reviewer のみ**: MEDIUM 2 (CR-M1 `replay_checksum_json_rules` DRY / CR-M2 checksum rules 2 箇所複製)、
  LOW 3 (CR-L1 guard 不統一 / CR-L2 outcome unparseable 未使用 / CR-L3 separators list vs tuple)。
- **Codex のみ**: LOW 1 (backward-compat parser の直接 regression test 欠 → legacy outcome-欠 parse test 追加)。

### 反映方針 (CLAUDE.md 反映ルール)
- **HIGH**: なし → merge 可。
- **MEDIUM 採用 (merge 前反映、安価・実リスク低減)**: CR-M1 = `replay_checksum_json_rules` を
  `CANONICAL_JSON_RULES` から導出 (drift 防止)。CR-M2 = 構造上 import cycle 回避で inline は ADR-sanctioned・
  test が digest 一致 pin ゆえ現状維持 + docstring 相互参照追記。
- **LOW 採用**: Codex-L1 = legacy (outcome 欠) decisions.jsonl parse 回帰 test 追加 (後方互換契約 pin)。
  CR-L2 = outcome docstring に「unparseable は将来拡張、record path は ok/raised のみ」明記。
- **LOW 現状維持 (記録のみ)**: CR-L1 (fallback の外側 guard は defensive・コメント済で意図的)、
  CR-L3 (separators=list は JSON 定数として正)。
- → review-fixes commit で CR-M1 / CR-M2 docstr / CR-L2 docstr / Codex-L1 test を適用、pre-push 再緑後に PR。

## 学び
- FROZEN ADR + TASK-PRE 実測検証の組合せで、Codex LOW 指摘 (β の memory 数前提) を早期に empirical 反証でき、
  β の main 単独 merge 安全性を確証。sequencing 主張は「文書の意図」でなく「実 test」で固める。
- subagent 逐次 dispatch は「context 分離 = 別シェル」を Agent tool 内で実現する有効手段。並列/逐次は
  wall-clock 差のみで context 分離とは独立。

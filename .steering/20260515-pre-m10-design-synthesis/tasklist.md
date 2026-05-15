# タスクリスト — pre-M10 design synthesis

> **Status**: 本 repair pass 2026-05-15 後の整理版。
> 旧 stale 記述 (`m10-0-social-tom-eval` scaffold / 「次 task scaffold 3 件」/ 重複 memo 整理セクション) は ADR-PM-6 / ADR-PM-8 で SUPERSEDED として撤去。

## 準備
- [x] `idea_judgement.md` / `idea_judgement_2.md` 内容把握
- [x] v2 draft `m10-0-concrete-design-draft.md` (PR #159) 全文読了
- [x] 当初 slug `m10-0-individual-layer-schema-add` が M9 task で実装完了済を確認
  (`evidence/eval_store.py:88` / `:188-216` / `training/train_kant_lora.py:286-`)
- [x] User 直接指示 (2026-05-15) 「ToM などを含めた評価体制を具体的に強固に設計してから決めてください」を受領、design-first 方針に逆転
- [x] Plan mode で plan 起票 + User 承認

## design synthesis (initial)
- [x] `.steering/20260515-pre-m10-design-synthesis/` ディレクトリ作成
- [x] `requirement.md` 起票 (User 追加方針反映、ADR-PM-1〜PM-5 / design.md §1-§7 構成宣言)
- [x] `design.md` initial 起票 — §1 memo 要旨 / §2 v2 既吸収 mapping / **§3 M10-0 評価体制 concrete robust design (10 subsection)** / §4 配置決定 / §5 v2 Addendum patch / §6 次 task scaffold 草稿 / §7 memo 最終配置案
- [x] `decisions.md` 起票 — ADR-PM-1 (source_navigator 並列) / ADR-PM-2 (Social-ToM 独立 sub-task 格上げ、後に ADR-PM-6 で SUPERSEDED) / ADR-PM-3 (PEFT registry M12+ linkback) / ADR-PM-4 (memo rename move) / ADR-PM-5 (Emotional alignment M11+ defer)
- [x] `tasklist.md` 起票 (本ファイル initial)

## /reimagine phase (User 指示「ベストを尽くせ」を受けて、CLAUDE.md「Plan 内 /reimagine 必須」規約に従い実行)
- [x] initial `design.md` を `design-original.md` にコピー退避 (506 行、capability-oriented scenario-lib 案)
- [x] `design-reimagine.md` を意図的に異視点でゼロから起草 (process-trace + power-first 案、~330 行)
- [x] `design-final.md` を起票 (§A 対照 / §B Hybrid 採用判断 / §C-§I concrete design、~600 行)
- [x] **Hybrid-A revised 採用**: reimagine Layer 2 + original から 4 scenario spec doc 救出、新 table 廃止、Social-ToM 専用 sub-task 廃止
- [x] `decisions.md` に ADR-PM-6 (Hybrid-A revised 採用) + ADR-PM-2 再 revise 追加

## Codex 13th independent review (User 指示「ベストを尽くせ」を受けて)
- [x] `codex-review-prompt.md` 起草
- [x] prompt + design-final.md + design-original.md + design-reimagine.md + decisions.md を concat (~103KB、1525 行)
- [x] `cat /tmp/codex_input.md | codex exec --skip-git-repo-check > codex-review.md 2>&1` を実行 (b28oakdy1、66,261 tokens、Verdict: ADOPT-WITH-CHANGES)
- [x] Codex output を `codex-review.md` に verbatim 保存 (1767 行、HIGH 4 / MEDIUM 5 / LOW 3)
- [x] **HIGH 4 全反映** (design-final.md §0/§C.2/§C.6/§C.7/§C.8 + claim boundary 警告 + A12 split + M-L2-3 baseline 修正 + block/cluster bootstrap)
- [x] **MEDIUM 5 全反映** (ADR-PM-2 SUPERSEDED status / WP11 handoff metadata / M-L2-1 descriptive only / namespace allowlist test / deprecation headers)
- [x] **LOW 3 全反映** (絶対日付 / supersession 明示 / 用語統一 `Cite-Belief Discipline`)
- [x] `decisions.md` に ADR-PM-7 (Codex 13th 反映完了) を追加

## repair pass (本 session 後半、ADR-PM-8)
- [x] `design-final.md` の不整合を後続 review で発見:
  - M-L2-1 が現行 `SemanticMemoryRecord.belief_kind` (`trust/clash/wary/curious/ambivalent`) と矛盾する `provisional/promoted` transition 前提
  - "Layer 2 3 metric が active 計測 / `status='valid'` ≥90%" 主張が schema/data 実状と乖離
  - Phase B+C 30 cell × 504 tick が unconditional 前提だが Mac 上 natural 15 DuckDB 本体不在 (sidecar のみ)
  - "DDL 変更ゼロ" 表現が誤読 (`metrics.individuation` は M10-0 main で新規 DDL 追加が必要、現行 `bootstrap_schema()` は `metrics.tier_{a,b,c}` のみ)
  - 実装配置 `src/erre_sandbox/eval/individuation/` が現行 evidence layer pattern とズレ
- [x] `design.md` を canonical として新規起票 (本 repair pass の正本、§X repair-log で changelog 記録)
- [x] `design-final.md` の header に SUPERSEDED 宣言 + `design.md` への pointer 追加 (本文は historical reference として保持)
- [x] `decisions.md` に **ADR-PM-8 追加** — M10-0 final freeze gate を G-GEAR QLoRA retrain v2 verdict 後に置く、本 repair pass では steering / design boundary fix まで
- [x] `tasklist.md` の stale 記述整理 (`m10-0-social-tom-eval` scaffold / 「次 task scaffold 3 件」/ 重複 memo 整理 / 重複レビューセクションを撤去)
- [x] 重要制約遵守確認: `src/erre_sandbox/` コード変更ゼロ / `data/` artefact 削除ゼロ / `_checksums_mac_received.txt` 等 untracked file 保持 / 次 task scaffold 未作成 / 未 commit

## memo 整理 (rename move、本 task で完了)
- [x] `idea_judgement.md` → `.steering/20260515-pre-m10-design-synthesis/idea-judgement-source-navigator.md` に rename move (mv 使用、untracked のため git mv 不可)
- [x] `idea_judgement_2.md` → `.steering/20260515-pre-m10-design-synthesis/idea-judgement-pdf-survey.md` に rename move
- [x] `git status` で root から `idea_judgement*.md` 消えていることを確認
- [x] 重複 `design.md` 削除 (design-original.md と byte-for-byte 同一、cp の残骸) — ※本 repair pass で `design.md` を canonical として再起票している

## レビュー
- [x] Codex 13th review が code-reviewer に相当 (independent stress-test、HIGH 4 全反映済)
- [ ] (任意) Codex 14th review を retrain v2 verdict 後に実施し、final freeze 文書 (本 `design.md` 改訂版) を再度独立 review にかける

## コミット (本 repair pass の output)
- [ ] `git status` で staging 内容確認 (`.steering/20260515-pre-m10-design-synthesis/design.md` 新規 / `design-final.md` header 更新 / `decisions.md` ADR-PM-8 追加 / `tasklist.md` 整理)
- [ ] `git diff -- .steering/20260515-pre-m10-design-synthesis/` で変更要約確認
- [ ] commit 文言案: `docs(steering): repair pass for pre-M10 design synthesis (ADR-PM-8, schema/data/DDL/placement fix)`
- [ ] commit message に「Codex 13th 反映後の `design-final.md` を canonical `design.md` で repair、ADR-PM-8 で M10-0 final freeze gate を retrain v2 verdict 後に置く」を含む
- [ ] commit は **User 明示指示後**

## 完了処理 (次セッションへの引き継ぎ)
- [ ] memory `MEMORY.md` に本 repair pass のエントリ追加 (canonical `design.md` 配置 / ADR-PM-8 追加 / retrain v2 verdict gate)
- [ ] (任意) `/finish-task` skill で closure
- [ ] PR 起票 (docs+steering only、レビュー軽量)

## 本 task の次アクション (本 repair pass で確定、ADR-PM-8)
- [ ] **G-GEAR QLoRA retrain v2 verdict 確認** (ADOPT / REJECT)
- [ ] PC-2 (natural 15 DuckDB body) 受領 + checksum verify (G-GEAR rsync)
- [ ] verdict 確定後、`design.md` を ADR-PM-8 の retrain v2 verdict-after action plan に従って update (acceptance threshold band と next task scaffold の baseline 前提を ADOPT/REJECT 別に確定)
- [ ] retrain v2 verdict 後の sub-task scaffold 起票: `m10-0-individuation-metrics` + `m10-0-source-navigator-mvp` (2 並列、`m10-0-social-tom-eval` は ADR-PM-6 で廃止、Social-ToM proper は M11-C へ defer)

## 本 task では実施しないこと (明示、scope creep 防止)
- ❌ v2 draft `m10-0-concrete-design-draft.md` 本体への commit (Addendum patch は `design.md` §G に保持、本体への commit は次 task `m10-0-individuation-metrics` scaffold 時、retrain v2 verdict 後)
- ❌ 次 task scaffold (`m10-0-individuation-metrics` / `m10-0-source-navigator-mvp` の `.steering/` ディレクトリ作成) — ADR-PM-8 gate により retrain v2 verdict 後
- ❌ コード変更 (`src/erre_sandbox/schemas.py` / `contracts/` / `evidence/` / `training/` / `tests/`)
- ❌ `data/eval/golden/_checksums_mac_received.txt` 等 untracked / dirty file の削除 / revert
- ❌ `m11-emotional-alignment-rubric` scaffold (ADR-PM-5、M11+ defer)
- ❌ `m12-peft-ablation-qdora` scaffold (ADR-PM-3、M12+ defer)
- ❌ `m10-0-social-tom-eval` scaffold (ADR-PM-2 → ADR-PM-6 で SUPERSEDED、Layer 2 を main 統合に再 revise)
- ❌ `m11-c-social-tom-proper` scaffold (M11-C 移送、本 task は WP11 4 scenario spec doc で M11-C handoff 文書化のみ)
- ❌ `SemanticMemoryRecord.belief_kind` schema 拡張 (本 repair pass: 別 task で要件再定義、M-L2-1 active 化の prerequisite)
- ❌ Codex 14th review 実走 (任意、retrain v2 verdict 後に final freeze 文書を独立 review にかける選択肢として残す)

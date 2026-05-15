# タスクリスト — pre-M10 design synthesis

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
- [x] `design.md` 起票 — §1 memo 要旨 / §2 v2 既吸収 mapping / **§3 M10-0 評価体制 concrete robust design (10 subsection)** / §4 配置決定 / §5 v2 Addendum patch / §6 次 task scaffold 草稿 (3 件) / §7 memo 最終配置案
- [x] `decisions.md` 起票 — ADR-PM-1 (source_navigator 並列) / ADR-PM-2 (Social-ToM 独立 sub-task 格上げ、本 phase 時点) / ADR-PM-3 (PEFT registry M12+ linkback) / ADR-PM-4 (memo rename move) / ADR-PM-5 (Emotional alignment M11+ defer)
- [x] `tasklist.md` 起票 (本ファイル)

## /reimagine phase (User 指示「ベストを尽くせ」を受けて、CLAUDE.md「Plan 内 /reimagine 必須」規約に従い実行)
- [x] `design.md` を `design-original.md` にコピー退避 (506 行、capability-oriented scenario-lib 案)
- [x] `design-reimagine.md` を意図的に異視点でゼロから起草 (process-trace + power-first 案、~330 行)
- [x] `design-final.md` を起票 (§A 対照 / §B Hybrid 採用判断 / §C-§I concrete design、~600 行)
- [x] **Hybrid-A revised 採用**: reimagine Layer 2 + original から 4 scenario spec doc 救出、新 table 廃止、Social-ToM 専用 sub-task 廃止
- [x] `decisions.md` に ADR-PM-6 (Hybrid-A revised 採用) + ADR-PM-2 再 revise 追加

## Codex 13th independent review (User 指示「ベストを尽くせ」を受けて)
- [x] `codex-review-prompt.md` 起草 (§1 Context / §2 採用構造要旨 / §3 Reimagine 経由の根本逆転 / §4 Q1-Q12 specific questions / §5 期待 format / §6 制約理解)
- [x] prompt + design-final.md + design-original.md + design-reimagine.md + decisions.md を concat (~103KB、1525 行)
- [x] `cat /tmp/codex_input.md | codex exec --skip-git-repo-check > codex-review.md 2>&1` を実行 (b28oakdy1、66,261 tokens、Verdict: ADOPT-WITH-CHANGES)
- [x] Codex output を `codex-review.md` に verbatim 保存 (1767 行、HIGH 4 / MEDIUM 5 / LOW 3)
- [x] **HIGH 4 全反映** (design-final.md §0/§C.2/§C.6/§C.7/§C.8 + claim boundary 警告 + A12 split + M-L2-3 baseline 修正 + block/cluster bootstrap)
- [x] **MEDIUM 5 全反映** (ADR-PM-2 SUPERSEDED status / WP11 handoff metadata / M-L2-1 descriptive only / namespace allowlist test / deprecation headers)
- [x] **LOW 3 全反映** (絶対日付 / supersession 明示 / 用語統一 `Cite-Belief Discipline`)
- [x] `decisions.md` に ADR-PM-7 (Codex 13th 反映完了) を追加

## memo 整理
- [x] `idea_judgement.md` → `.steering/20260515-pre-m10-design-synthesis/idea-judgement-source-navigator.md` に rename move (mv 使用、untracked のため git mv 不可)
- [x] `idea_judgement_2.md` → `.steering/20260515-pre-m10-design-synthesis/idea-judgement-pdf-survey.md` に rename move
- [x] `git status` で root から `idea_judgement*.md` 消えていることを確認
- [x] 重複 `design.md` 削除 (design-original.md と byte-for-byte 同一、cp の残骸)

## レビュー (任意)
- [x] Codex 13th review が code-reviewer に相当 (independent stress-test、HIGH 4 全反映済)
- [ ] (任意) `code-reviewer` agent で synthesis 文書群を最終レビュー (User 判断)

## memo 整理
- [x] `idea_judgement.md` → `.steering/20260515-pre-m10-design-synthesis/idea-judgement-source-navigator.md` に rename move (mv 使用、untracked のため git mv 不可)
- [x] `idea_judgement_2.md` → `.steering/20260515-pre-m10-design-synthesis/idea-judgement-pdf-survey.md` に rename move
- [x] `git status` で root から `idea_judgement*.md` 消えていることを確認

## レビュー (任意)
- [ ] `code-reviewer` agent で 4 synthesis 文書をレビュー
- [ ] HIGH 指摘あれば反映、なければ skip

## コミット
- [ ] `git status` で staging 内容確認 (synthesis 4 ファイル新規 + memo 2 ファイル rename + root deletion)
- [ ] `git diff --stat` で差分量確認 (docs+steering only、source 変更ゼロ)
- [ ] Conventional Commits: `docs(steering): pre-M10 design synthesis (Social-ToM eval concrete)`
- [ ] commit message に「User 直接指示 (2026-05-15) 反映で design-first に逆転、Social-ToM 独立 sub-task 格上げ」を含む

## 完了処理 (次セッションへの引き継ぎ)
- [ ] memory `MEMORY.md` に本 synthesis のエントリ追加 (次 task scaffold 3 件の起票準備が整った旨)
- [ ] (任意) `/finish-task` skill で closure
- [ ] PR 起票 (docs+steering only、レビュー軽量)
- [ ] PR merge 後、次セッションで `/start-task m10-0-individuation-metrics` + `/start-task m10-0-social-tom-eval` + `/start-task m10-0-source-navigator-mvp` を順次起票

## 本 task では実施しないこと (明示、scope creep 防止)
- ❌ v2 draft `m10-0-concrete-design-draft.md` 本体への commit (Addendum patch は design-final.md §G に保持、本体への commit は次 task `m10-0-individuation-metrics` scaffold 時に同時 commit)
- ❌ 次 task scaffold (`m10-0-individuation-metrics` / `m10-0-source-navigator-mvp` の `.steering/` ディレクトリ作成) — design-final.md §H で inline 草稿のみ
- ❌ ~~Codex 13th review — 本セッション defer~~ → **本 session で実施完了 (User 「ベストを尽くせ」指示)、HIGH 4 / MEDIUM 5 / LOW 3 全反映済**
- ❌ コード変更 (schemas.py / contracts/ / evidence/ / training/ / tests/)
- ❌ `m11-emotional-alignment-rubric` scaffold (ADR-PM-5、M11+ defer)
- ❌ `m12-peft-ablation-qdora` scaffold (ADR-PM-3、M12+ defer)
- ❌ `m10-0-social-tom-eval` scaffold (ADR-PM-2 → ADR-PM-6 で SUPERSEDED、Layer 2 を main 統合に再 revise)
- ❌ `m11-c-social-tom-proper` scaffold (M11-C 移送、本 task は WP11 4 scenario spec doc で M11-C handoff 文書化のみ)

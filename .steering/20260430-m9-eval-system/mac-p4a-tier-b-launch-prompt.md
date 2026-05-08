# Mac P4a Tier B 起草 — 新セッション launch prompt (cold-start ready)

> 本書は新しい Claude Code セッションで `/clear` 直後に投げかけるための
> 自己完結 prompt。下記 §「コピペ用 prompt」を一括で貼り付けるだけで Plan
> mode 立ち上げまで進む。reference files は cold-start でも Read するように
> 指示済。
>
> **作成**: 2026-05-08 (PR #146 P5 hardening merge 直後、main=`dbd480b`)
> **対象タスク**: M9-eval-system P4a — `src/erre_sandbox/evidence/tier_b/` ゼロ起草
> **想定工数**: ~8h、1-2 セッション
> **必須プロセス**: Plan mode + /reimagine + Codex `gpt-5.5 xhigh` independent review

## なぜ Plan + /reimagine + Codex 必須か

下記 5 つの methodological 判断はいずれも **複数案ありうる** ため、CLAUDE.md
規約 (architecture / 公開 API / 高難度設計) で全 3 関門が起動する:

1. Vendi Score kernel: semantic (MPNet) vs unigram count vs hybrid
2. IPIP-NEO 版: short 50 (Goldberg 1992) / mini 20 (Donnellan 2006) / full 300
3. Big5 ICC formula: ICC(2,k) vs ICC(3,1) vs ICC(2,1)、convergence 閾値
4. per-100-turn windowing × cluster_only bootstrap の statistical validity
5. LIWC alternative (Empath / spaCy / 自作) の honest framing

直近の M9-eval Codex review 履歴 (P3a-finalize HIGH-1、Phase 2 run0 timeout
HIGH 4、CLI partial-fix HIGH 2、run1 calibration HIGH 3、ME-9 trigger
hybrid A/C) はいずれも「Claude solo では発見不能だった HIGH を切出」した
empirical 実績があり、本案でも同様の質的補正が期待される。

## コピペ用 prompt (これをそのまま新セッションに貼る)

```
M9-eval-system P4a を起動する。`src/erre_sandbox/evidence/tier_b/` を
ゼロから起草するタスク。CLAUDE.md 規約より Plan mode + /reimagine + Codex
`gpt-5.5 xhigh` independent review の 3 関門を全部通すこと。

## Mission (1 文)

LoRA 採用判定 (DB9 quorum) の心理学・多様性 metric として `tier_b/`
ディレクトリに 3 metric (Vendi Score / IPIP-NEO Big5 / Big5 ICC) を起草、
bootstrap_ci 統合 + eval_store.py 統合 + tests を全部 1 PR で通す。

## Context (cold start でも理解可能、必ず Read)

### 直近 commit / 環境
- main = dbd480b (PR #146 P5 hardening 2026-05-08 merged)
- 直前 3 PR: #144 cognition-deepen 7-point / #145 DB11 contamination prevention /
  #146 P5 hardening (block_length auto-estimation + cluster_only mode)
- G-GEAR で run1 calibration 走行中 (kant 1 cell × 5 wall = 30h overnight×2)、
  本タスクは触らない

### 既存 infrastructure (流用)
- `src/erre_sandbox/evidence/bootstrap_ci.py` (24 unit tests PASS):
  - `bootstrap_ci()` percentile bootstrap
  - `hierarchical_bootstrap_ci(cluster_only=True)` ← Tier B per-100-turn
    windowed metric の effective sample size 25 を扱う専用 mode、本タスクで
    流用必須
  - `estimate_block_length()` Politis-White-inspired auto block (PR #146)
- `src/erre_sandbox/evidence/tier_a/` ← Burrows Δ / MATTR / NLI / MPNet
  novelty / Empath proxy 既に存在。Tier B は Tier A と orthogonal、Burrows
  / Empath を duplicate しない
- `src/erre_sandbox/evidence/eval_store.py` ← sub-metric retrieval API、
  Tier B 値もここに統合する (新 access path 追加)

### ADR 制約 (絶対遵守)
- DB5/DB6 (M9-B PR #127): raw_dialog (metric-free) と metrics (sidecar) の
  物理分離。Tier B 計算結果は metrics 側に書く
- DB6: `evaluation_epoch=false` only training eligible
- DB9: 2-of-3 sub-metric が CI で baseline 方向 = LoRA 採用条件。Tier B は
  Vendi / Big5 ICC / Burrows Δ の 3 sub-metric を提供する (Burrows は tier_a
  既存、Tier B は残り 2 を新規)
- DB10 LIWC alternative honest framing: Empath/spaCy は proxy であって
  LIWC 等価ではない、Big5 claim は LIWC 商用 license + validation あって
  初めて成立。proxy framing を README/docstring/コメントで明示
- DB11 (M9-B PR #145 2026-05-08): Tier B 計算は eval-side のみで生じるので
  直接の影響なし。ただし metric 値の persistence path が training に漏れない
  構造を design 段階で確認

### 解像度低い設計判断 (Plan + /reimagine + Codex で確定する 5 点)

1. Vendi Score kernel 選定:
   - semantic (sentence-transformers MPNet
     `paraphrase-multilingual-mpnet-base-v2`) vs unigram count vs hybrid
   - 計算コスト trade-off (per-100-turn 25 windows × 3 persona = 75 calls)
   - 直交 one-hot で score=N が成立するか (sanity test 必須)

2. IPIP-NEO 版選定:
   - short 50 / mini 20 / full 300?
   - agentic loop: persona に Big5 質問を回答させる、temperature=0
     deterministic
   - 何 turn ごとに 1 回測定?(per-100-turn と整合?)
   - 日本語 prompt 整備 (kant / rikyu / nietzsche persona conditioned)

3. Big5 ICC formula:
   - ICC(2,k) (random raters, average) vs ICC(3,1) (fixed raters, single)
     vs ICC(2,1)?
   - convergence 閾値: 1.0 同一回答列 = sanity check、実運用 baseline?
   - bootstrap CI: cluster_only mode (per-run 5 cluster) で計算

4. per-100-turn windowing:
   - 500-turn run を 5 つの 100-turn window に分割
   - 各 window で Vendi / IPIP-NEO / Big5 ICC を計算
   - 5 runs × 5 windows = 25 windows / persona
   - bootstrap_ci の cluster_only mode (PR #146) を活用

5. LIWC alternative:
   - Empath (Stanford) / spaCy custom dict / 完全自作?
   - Vendi / IPIP-NEO 結果との相関を validate
   - DB10 honest framing: Big5 claim は LIWC 等価ではない

### Codex review で必須に問うこと

- prior art 調査 (web search 必須):
  - Vendi Score 2023 paper (https://arxiv.org/abs/2210.02410) の kernel 選択
  - IPIP-NEO short comparison (Donnellan 2006 / IPIP-50 vs Mini-IPIP-20)
  - ICC for LLM personality stability 2024-2026 prior art
  - LIWC vs Empath empirical equivalence research
- 日本語 persona の Big5 測定における言語間 cross-validation 問題
- bootstrap_ci の cluster_only mode が Tier B per-100-turn で statistically
  valid か
- per-window sample size 100 turn は ICC 計算に sufficient か (rule of thumb
  / power analysis)

## 期待 deliverable (PR scope)

### 新規 files
- `src/erre_sandbox/evidence/tier_b/__init__.py`
- `src/erre_sandbox/evidence/tier_b/vendi.py`
- `src/erre_sandbox/evidence/tier_b/ipip_neo.py`
- `src/erre_sandbox/evidence/tier_b/big5_icc.py`
- `tests/test_evidence/test_tier_b/__init__.py`
- `tests/test_evidence/test_tier_b/test_vendi.py`
- `tests/test_evidence/test_tier_b/test_ipip_neo.py`
- `tests/test_evidence/test_tier_b/test_big5_icc.py`

### 既存 files への変更 (additive)
- `src/erre_sandbox/evidence/eval_store.py` — Tier B sub-metric retrieval 追加
- `tests/test_evidence/test_eval_store.py` — Tier B 統合 test
- `.steering/20260430-m9-eval-system/tasklist.md` — P4a sub-items [x] 化

### 新規 .steering 資産 (verbatim 保存規律)
- `.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md` (Plan mode 初回案)
- `.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md` (/reimagine 後)
- `.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md`
- `.steering/20260430-m9-eval-system/codex-review-prompt-p4a.md`
- `.steering/20260430-m9-eval-system/codex-review-p4a.md` (verbatim 保存、要約禁止)
- `.steering/20260430-m9-eval-system/p4a-tier-b-design-final.md` (Codex HIGH 反映後の最終)

### Acceptance criteria (定量)

- ruff check / format / mypy clean
- 既存 1318+ tests pass (no regression、特に test_evidence/ 全体)
- 新規 tier_b/ tests 全 PASS、各 metric は次の sanity を満たす:
  - Vendi: 直交 one-hot input → score = N (within float tolerance)
  - IPIP-NEO: deterministic temperature=0 で identical input → identical
    output (replay determinism test)
  - Big5 ICC: 同一回答列 → ICC = 1.0 (within tolerance、既存 P5 tasklist 要件)
- bootstrap_ci 統合: 各 metric × 25 windows の per-100-turn は cluster_only
  mode で CI 計算可能 (integration test 必須)
- M9-eval-system tasklist の P4a sub-items すべて [x] 化、P5 残「Vendi
  orthogonal one-hot」「Big5 ICC 1.0 収束」も同時 close
- PR description に `codex-review-p4a.md` link + HIGH 反映マッピング表

### scope 外 (この PR で触らない)

- LoRA training 実装 (M9-C-adopt 範囲)
- Tier C judge LLM (P6 範囲)
- G-GEAR golden baseline 採取 (P3 範囲、calibration 完了待ち)
- Burrows reference corpus 整備 (Tier A 既存範囲、blockers.md defer 中)
- persona refactor / philosopher_seed (M10-A 範囲、認知深化 PR #144)
- DB11 contamination assert 実装 (M9-C-adopt 範囲)

## 必読 reference files (cold start で Read、優先度順)

1. `.steering/20260430-m9-eval-system/design-final.md` — Tier B が DB9
   quorum で果たす役割
2. `.steering/20260430-m9-eval-system/decisions.md` — ME-1 / ME-4 ADR、
   Tier B sub-metric 候補、LIWC alternative honest framing
3. `.steering/20260430-m9-eval-system/tasklist.md` — P4a 既存 checklist
   (435 行付近の P5、別の P4a section)
4. `.steering/20260430-m9-eval-system/codex-review.md` — 既存 HIGH 5 反映
   状況、Tier B 関連の指摘
5. `.steering/20260430-m9-eval-system/blockers.md` — LIWC license / Burrows
   multi-language defer
6. `src/erre_sandbox/evidence/bootstrap_ci.py` — cluster_only / auto_block /
   estimate_block_length (PR #146 で追加した API、Tier B で流用必須)
7. `src/erre_sandbox/evidence/tier_a/__init__.py` — 既存 Tier A の構造
   (paralleled に作る、import path / docstring 体裁を踏襲)
8. `src/erre_sandbox/evidence/eval_store.py` — sub-metric retrieval API、
   Tier B 統合先
9. `.steering/20260430-m9-b-lora-execution-plan/decisions.md` DB1-DB11 —
   LoRA 採用判定における Tier B の位置づけ
10. CLAUDE.md — Plan mode + /reimagine + Codex 強制ルール、.steering 記録規律

## 起動シーケンス

```
# 1. Plan mode (Shift+Tab 2回) + Opus に切替
# 2. 上記 reference files を Read (1-9 順)
# 3. /start-task m9-eval-p4a-tier-b で .steering scaffold (
#    既存 .steering/20260430-m9-eval-system/ 内に派生 design 系列を作る、
#    別 dir 切らない)
# 4. requirement.md ＋ 上記「解像度低い設計判断 5 点」を design-v1 として
#    記述
# 5. /reimagine で v1 を破棄、別の出発点 (例: methodological prior art 起点)
#    から v2 を生成
# 6. design-comparison.md で v1 vs v2、必要なら hybrid v3
# 7. codex-review-prompt-p4a.md 起票 (上記「Codex review で必須に問うこと」
#    全件 + reference files link 含む)
# 8. cat .steering/20260430-m9-eval-system/codex-review-prompt-p4a.md |
#    codex exec --skip-git-repo-check  # bash で実行
# 9. codex-review-p4a.md verbatim 保存 (要約禁止)
# 10. Verdict + HIGH 全反映 → p4a-tier-b-design-final.md
# 11. context 30%↑なら /clear で切る (design-final + decisions Read で再開)
# 12. Implementation: tier_b/ 3 metric + tests + eval_store.py 統合
# 13. Branch: feat/m9-eval-p4a-tier-b
# 14. Local 4 gate (ruff / format / mypy / pytest tests/test_evidence/) 全 green
# 15. Commit + push + gh pr create (PR description に codex-review link)
```

## 想定工数 (solo cadence)

| Phase | 推定 |
|---|---|
| Read reference + Plan mode v1 | 1h |
| /reimagine v2 + comparison | 1h |
| Codex review prompt + execution | 30min |
| Codex 反映 + design-final.md | 1h |
| (context 30%↑なら /clear hand-off) | 0min |
| tier_b/ 3 files 実装 | 2h |
| tests 9-15 件実装 | 1.5h |
| eval_store.py 統合 + 既存 test 維持 | 30min |
| PR description + commit + push | 30min |
| **合計** | **~8h** (1-2 セッション) |

## 注意事項 (anti-pattern 防止)

- 「将来の柔軟性」を理由に scope を膨らませない (ERRE は research prototype、
  bloat = 価値破壊)
- Vendi / IPIP-NEO / Big5 ICC を **3 つすべて同 PR** で投入する。1 metric
  ずつの incremental は DB9 quorum gate が機能する状態で merge できないので
  無意味
- LIWC 商用 license は依然 blocker (blockers.md)、Empath / spaCy / 自作
  のいずれかで proxy framing
- 日本語 persona の Big5 測定は言語間 cross-validation 問題があり、Codex に
  prior art 調査を依頼すること
- ME-9 incident 教訓: rate basis / 前提の明示性を必ず check。empirical
  threshold (e.g. ICC 0.6 cutoff) は ADR で root justification を明示
- bootstrap_ci.cluster_only mode を使うときは effective sample size = 25 を
  PR description / docstring で明示 (Codex P5 review で要求された
  framing と整合)
```

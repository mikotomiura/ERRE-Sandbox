# タスクリスト

## 準備
- [x] `.steering/_template/` から 5-file copy
- [x] 必須内面化 Read (DA-9/12/13 + Codex HIGH 4 件 + train_metadata.json +
  next-session-prompt-scenario-II-retrain-v2.md + 4-axis matrix)
- [x] `requirement.md` v1
- [x] file-finder 相当 (3 Explore agent 並列で代替済)

## Step 1: training data 特性分析
- [x] `scripts/analysis/` directory 作成
- [x] `scripts/analysis/analyze_kant_training_corpus.py` 実装
  - [x] `build_examples()` reuse (lazy import via `iter_shard_rows`)
  - [x] token length 分布 (whitespace × 1.3 proxy、Qwen3-8B tokenizer は
    optional)
  - [x] persona self-reference markers density (de pronouns + Kantian lex)
  - [x] dialog vs monolog ratio (addressee_persona_id 有無)
  - [x] per-stim category coverage (shard-level natural/stimulus + kant.yaml ref)
  - [x] utterance language distribution (heuristic、langdetect 非 dep)
- [x] `tests/test_analysis/test_kant_corpus.py` 3-case smoke
- [x] `pytest tests/test_analysis/` green
- [x] `corpus-analysis-kant.{json,md}` 生成 (5022 examples 確認)
- [x] `design.md` に falsifiable claim 4 件記録 (C1-C4 + 統合解釈)

## Step 2: retrain v2 spec design + /reimagine
- [x] design.md gap finding (4 claims)
- [x] 3 candidates 比較 (volume / signal / hybrid)
- [x] `design-final.md` 確定 (signal-driven 採用、§1-7 必須節埋め)

## Step 3: Codex independent review
- [x] `codex-review-prompt.md` 起草
- [x] `codex exec --skip-git-repo-check` 実行 (260,485 tokens, gpt-5.5 xhigh)
- [x] `codex-review.md` verbatim 保存 + `codex-review.stderr` capture
- [x] HIGH 反映:
  - [x] HIGH-A → design-final.md §2 (Candidate C narrow) + §3.3 group-aware split
  - [x] HIGH-B → design-final.md §3.5 (compute envelope + eval guards)
  - [x] HIGH-C → design-final.md §3.2 (WeightedTrainer + normalisation + heuristic
    rationale)
  - [x] HIGH-D → design-final.md §4 (Burrows 5% / ICC(A,1) primary 根拠強化)
- [x] MEDIUM-1/2/3 採否 → `decisions.md` DR-2
- [x] LOW-1/2 → `decisions.md` DR-2 + design-final.md fold-up

## Step 4: DA-14 ADR
- [x] `.steering/20260513-m9-c-adopt/decisions.md` に DA-14 append
- [x] `da1-thresholds-recalibrated.json` 機械可読 pin file

## Step 5: next-session handoff prompt
- [x] `next-session-prompt.md` 起草 (branch / 5-step 目的 / Read order /
  compute envelope / abort triggers / 完了条件)

## Step 6: commit + PR
- [ ] ruff format / ruff check 全 file
- [ ] pytest 再実行 (回帰確認)
- [ ] commit (Conventional Commits `design(adopt):`、Refs: で .steering 参照)
- [ ] `git push -u origin feature/m9-c-adopt-retrain-v2-design`
- [ ] `gh pr create` (HEREDOC body、design-only 明記)

## 完了処理
- [x] tasklist.md 全 check (Step 6 残)
- [ ] PR URL 確認

# DA-17 ADR — ドイツ語失敗 preflight (rank=16 直行を保留)

## 背景

PR-4 (#189、2026-05-17T06:54:37Z merged) で `kant_r8_v4` の DA-14
verdict が `PHASE_E_A6` (REJECT) と確定した。当初の PR-5 plan は
**rank=16 spike retrain** (GPU 6–8h) だったが、v3→v4 within-language
Vendi d (4 encoder × {de, en} = 8 cell) を計算すると、**capacity 仮説単独
では説明不能な「言語別正反対 effect」** が現れた:

- **英語 (en)**: 4/4 encoder で Δ < 0 (LoRA-on が kant に converge、
  改善方向)。WeightedTrainer fix (PR-2 `.mean()` reduce) が英語側では
  意図通り効いている
- **ドイツ語 (de)**: 3/4 encoder で Δ > 0 (LoRA-on が kant から
  divergence、悪化方向)。残り 1 encoder (E5-large de) も +0.76 → +0.05
  の zero 収束で negative にならず

特に MPNet de は v3 −0.38 → v4 **+1.12** (Δ **+1.50**) と強い flip。
Burrows reduction% = −1.54% (de-only、Akademie-Ausgabe 参照) も同方向
で、kant の formal philosophical German 参照から LoRA-on が更に離れた。

capacity scaling (rank=8 → rank=16) は通常「学習している方向を強める」
だけで、encoder ごと / 言語ごとに sign を flip させない。この
「英語改善 / ドイツ語悪化」は別 root cause を示唆し、rank=16 spike に
GPU 6–8h を投下する前に root cause を切り分けるべきである。

## ゴール

1. v3→v4 の言語別正反対 effect の root cause を **forensic 分析のみ**
   (retrain ゼロ) で切り分け、複数仮説の証拠を articulate
2. PR-5 scope を **α (rank=16) / β (corpus rebalance) / γ
   (language-aware LoRA) / δ (Plan B retrospective) / ε (prompt-side
   fix)** の 5 案から 1〜2 案に narrow down
3. 採用 scope の next-session prompt を起票、不採用案は defer reason
   明示で archive (将来再評価可能化)

## スコープ

### 含むもの
- 既存 forensic JSON / DuckDB shard / train metadata の read-only 分析
- v3 v4 within-language d 全数値の verbatim 引用と flip 分析
- v4 LoRA-on / no-LoRA shard からの ドイツ語 utterance qualitative
  inspection (langdetect 経由、10 ペア以上)
- 既存 Burrows JSON (de-only) の per-window 内訳分析
- train_metadata audit (de_en_mass / n_eff / top_5_pct +
  per_language_weighted_mass の anomaly 確認)
- chat template + prompt 構造の no-LoRA vs LoRA-on 同一性検証
- 5 hypothesis (H1〜H5) の pre-register + evidence-for / -against
- `/reimagine` による別 ADR 結論生成 + 採用案 finalize
- next-session prompt 起票 (採用 PR-5 scope)
- memory `project_plan_b_kant_phase_e_a6.md` 更新

### 含まないもの
- retrain (rank=16 / corpus rebalance / prompt-tuning 全て PR-5 scope)
- corpus 再生成 (Akademie-Ausgabe 再 ingest 等)
- WeightedTrainer 再修正 (PR-2 fix は frozen)
- `personas/kant.yaml` / `tier_b_pilot.py` の prompt template 編集
  (PR-5 ε 採用後の別 PR で実装)
- nietzsche / rikyu Plan B 展開
- DA-14 thresholds 緩和 (DA16-4 binding)
- `src/erre_sandbox/` 配下の python code 変更

## 受け入れ条件

- [ ] PR-4 #189 merged 状態確認 (gh pr view 189)
- [ ] branch `feature/m9-c-adopt-da17-german-failure-preflight`
      (main 派生) 作成
- [ ] `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/`
      5 標準 file 起票 (本 file 含む)
- [ ] `decisions.md` の DA17-1〜DA17-7 全埋め (JSON から verbatim、
      recompute 無し)
- [ ] DA17-1 v3 v4 within-language d table が plan ファイル
      `C:\Users\johnd\.claude\plans\steering-20260517-m9-c-adopt-pr4-da14-r-bright-pearl.md`
      Context table と verbatim 一致 (CI bounds 込み)
- [ ] DA17-2 ≥10 ドイツ語 utterance ペア (LoRA-on vs no-LoRA) を
      langdetect prob ≥0.85 で inspect、side-by-side 表に整理
- [ ] DA17-3 Burrows per-window 内訳 (v3 v4 de_fraction / window 単位
      mean Burrows / 全体 trajectory)
- [ ] DA17-4 train_metadata audit 数値 (de_en_mass=0.6010、ja_mass=0.389
      の anomaly 明示)
- [ ] DA17-5 prompt 構造同一性検証 (system prompt が no-LoRA / LoRA-on
      で identical を file:line 引用で確認)
- [ ] DA17-6 5 仮説 (H1〜H5) を各々 evidence-for ≥2 + evidence-against
      ≥2 で articulate
- [ ] DA17-7 PR-5 scope 1〜2 案を選定、不採用案 defer reason 記録
- [ ] `/reimagine` で別 ADR 結論を生成、両案併記の上で採用根拠明示
- [ ] `next-session-prompt-FINAL-pr5-<scope>.md` 起票
      (採用 scope verbatim)
- [ ] 既存 `next-session-prompt-FINAL-pr5-rank16-spike-reject.md` に
      DEFERRED 注記 (delete せず)
- [ ] memory `project_plan_b_kant_phase_e_a6.md` 更新 (言語非対称
      finding + 38.9% ja mass anomaly + DA-17 結論)
- [ ] `pwsh scripts/dev/pre-push-check.ps1` 4 段全 pass (doc-only PR)
- [ ] commit + push + `gh pr create --base main`
- [ ] Codex independent review (WSL2)、verbatim 保存。401 時 PR
      description で defer 明示

## 関連ドキュメント

- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/da14-verdict-plan-b-kant-v4.md`
  — PR-4 verdict 結果 (v3 v4 forensic 対比表)
- `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜
  DA16-4 — 順序判断 (候補 A) + WeightedTrainer fix 方針 + thresholds
  不変方針
- `.steering/20260513-m9-c-adopt/decisions.md` — 横断 ADR
- memory `project_plan_b_kant_phase_e_a6.md` — Plan B kant 全体経緯
- `CLAUDE.md` — Plan mode + `/reimagine` + Codex 連携 + 禁止事項
- 本 ADR の plan ファイル: `C:\Users\johnd\.claude\plans\steering-20260517-m9-c-adopt-pr4-da14-r-bright-pearl.md`

# Next-session 開始プロンプト — DA-15 ADR 起票 (m9-c-adopt retrain v2 REJECT 受け)

**用途**: 新セッション最初に貼り付け (下の ``` で囲まれた部分のみ)
**前提**:
- 本 PR (`feature/m9-c-adopt-retrain-v2-train-execution`、training execution
  + multi-turn pilot recapture + DA-14 verdict) が **merge 済**
- DA-14 verdict = **REJECT** (1/3 primary axes passed、kant 2-of-3 quorum 未達)
- 方向性は改善 (Vendi reversed: prior +1.39 wrong → v2 -0.13 correct)、
  magnitude 不足
**branch**: 新規 `feature/m9-c-adopt-da15-adr` を **main** から切る (ADR + design + plan、
  実装は別 PR)
**compute**: ローカル設計のみ、~30-60min

---

```
M9-C-adopt **DA-15 ADR** を起票する。本セッションは Plan mode + Opus 中心。
retrain v2 が DA-14 thresholds で REJECT になったため、次に試す 3 案
(Vendi kernel swap / Candidate C targeted hybrid / longer training/rank拡大)
を ADR で trade-off 比較し、優先順位を決定する。

## 目的 (本セッション、~30-60min)

1. **DA-15 ADR の作成** (`.steering/20260513-m9-c-adopt/decisions.md` に追記):
   - DA-14 REJECT の根拠 (v2 verdict 結果) を引用
   - 3 案の trade-off:
     - Plan A: **Vendi kernel swap** — sentence-transformers/all-mpnet-base-v2
       (現行) が persona shift に over-invariant な可能性。multilingual-e5 /
       Ada-002 / domain-specific BERT 等の代替 embedding を試す。
     - Plan B: **Candidate C targeted hybrid** — de+en weighted mass 0.489
       (target 0.60) を補強。ドイツ語哲学語彙を重視した合成 monolog 追加
       (DI-3 cap=500 を解除 + de-focused subset を 250+ 採取)。
     - Plan C: **Longer training / rank 拡大** — max_steps 4000 → 8000 or
       rank 8 → 16。GPU envelope 16h → 32-48h、cost vs marginal gain は要見積。
   - 各案の予測 effect size (Cohen's d 改善見込み)、リスク、所要 compute
   - 採用案 (1 つ or hybrid) を ADR D-2 で確定
2. **採用案の design.md スケッチ** (`.steering/[YYYYMMDD]-m9-c-adopt-da15-impl/`):
   - 採用案の実装スコープ + scope narrowing
   - 期待 outcome (DA-14 thresholds 通過想定)
   - 不通過時の plan B
3. **/reimagine 必須** (高難度判定): 初回 ADR 案を一度破棄して再生成案と
   比較、ハイブリッドの可能性を検討

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260515-m9-c-adopt-retrain-v2-verdict/decisions.md` D-1 (REJECT 根拠)
2. `.steering/20260515-m9-c-adopt-retrain-v2-verdict/da14-verdict-v2-kant.json`
   (per-axis 数値 + directional vs prior LoRA)
3. `.steering/20260514-m9-c-adopt-retrain-v2-impl/decisions.md` DI-1〜DI-4
   (実装経緯、de+en mass 0.489 の原因分析)
4. `.steering/20260514-m9-c-adopt-retrain-v2-design/design-final.md`
   (retrain v2 設計の意図)
5. `.steering/20260513-m9-c-adopt/decisions.md` DA-1〜DA-14 (横断 ADR の流れ)
6. `.steering/20260514-m9-c-adopt-retrain-v2-design/da1-thresholds-recalibrated.json`
   (DA-14 thresholds 詳細)

## NOT in scope (本セッション)

- 採用案の実装 (別 PR で。本セッションは ADR + design のみ)
- nietzsche / rikyu の retrain (kant ADOPT 後に Phase C)
- Phase E A-6 (kant ADOPT 後)
- matrix script (`da1_matrix_multiturn.py`) の comparator 修正
  (DA-14 baseline = no-LoRA SGLang への切替、別 PR で実施推奨)

## 完了条件

- [ ] `feature/m9-c-adopt-da15-adr` branch (main 派生)
- [ ] `.steering/[YYYYMMDD]-m9-c-adopt-da15-adr/{requirement,design,
      decisions,tasklist,blockers}.md` の 5 file
- [ ] `.steering/20260513-m9-c-adopt/decisions.md` に DA-15 を append
      (immutable append convention)
- [ ] ADR D-2 で採用案 (or hybrid) 確定、trade-off 数値見積込み
- [ ] /reimagine で初回案を意図的に破棄、ゼロ生成案と比較
- [ ] 採用案の次セッション handoff prompt
- [ ] commit + push + `gh pr create`

## 留意点

- **HIGH-3 post-hoc threshold movement 禁止**: DA-14 thresholds は変更不可。
  ADR は新しい approach の妥当性を述べるもので、threshold を緩める ADR は禁止。
- **matrix script gap**: 本 PR の `da1-matrix-v2-kant.json` は scenario II と
  記載しているが、これは matched HISTORICAL Ollama 比較 (DA-11 era logic)。
  DA-14 verdict は manual 計算の `da14-verdict-v2-kant.json` を採用済。
  matrix script の更新は DA-15 ADR で別 PR タスクとして検討。
- **本 PR の merge SHA を DA-15 trace.HEAD に埋め込む** (DA-14 convention 踏襲)
```

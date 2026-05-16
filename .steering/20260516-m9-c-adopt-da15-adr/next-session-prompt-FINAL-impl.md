# Next-session 開始プロンプト — DA-15 Phase 1 implementation (Plan A: Vendi kernel swap)

**用途**: 新セッション最初に貼り付け (下の ``` で囲まれた部分のみ)
**前提**:
- 本 PR (`feature/m9-c-adopt-da15-adr`、DA-15 ADR 起票 + Codex review 反映) が
  **merged 済**
- 採用方針 = Plan A (Vendi kernel swap) → Plan B (Candidate C targeted hybrid)
  sequential、Hybrid H-α (Plan B driver pre-stage) を Plan A 走行中に isolated
  branch で並行、Plan C は Phase E A-6 へ migrate
- Codex HIGH-1 (新 versioned metric) / HIGH-2 (calibration panel) / MEDIUM 3 件
  / LOW-1 すべて反映済 (`.steering/20260516-m9-c-adopt-da15-adr/decisions.md`
  D-2 参照)
**branch**: 新規 `feature/m9-c-adopt-da15-implementation` を **main** から切る
**compute**: ローカル code work ~3h + calibration panel ~1h + rescore ~1-2h
= **~5-6h** (G-GEAR or CPU 可)

---

```
M9-C-adopt **DA-15 Phase 1 (Plan A = Vendi kernel swap)** を実装する。
本セッションは implementation + Codex review + verdict 出力までの一気通貫。

## 目的 (本セッション、~5-6h、abort 8h)

1. **`/start-task`** で `.steering/20260516-m9-c-adopt-da15-impl/` を起票
2. **vendi.py 引数化**: `src/erre_sandbox/evidence/tier_b/vendi.py:294-322`
   `_load_default_kernel(encoder_name: str | None = None)` で MPNet default
   維持、HF model 名で任意 encoder を load 可能に
3. **compute_baseline_vendi.py に `--encoder` CLI 引数追加** (default MPNet)
4. **calibration panel script 新規** (`scripts/m9-c-adopt/
   da15_calibration_panel.py`):
   - Kant Critique 邦訳 100 文 + Heidegger 邦訳 + 英訳 100 文 の test corpus
     用意 (出所: 既存 `data/eval/golden/kant_*.duckdb` の persona_id=kant
     turns から抽出 + Heidegger 関連 stim を control として手動 curate)
   - 各 candidate encoder で cosine similarity ベースの 2-class
     classifier (logistic regression) を fit + AUC 計算
   - **AUC ≥ 0.75 を primary gate 通過基準** (preregistered)
5. **encoder + revision pin pre-registration commit** (rescore 実施前に必須):
   - `.steering/20260516-m9-c-adopt-da15-impl/decisions.md` D-2 に候補 encoder
     name + HF revision SHA + transformers version + sentence-transformers
     version + commit SHA を固定
   - primary candidates: `intfloat/multilingual-e5-large` +
     `BAAI/bge-m3` (両方とも calibration AUC ≥ 0.75 が前提)
   - exploratory only (ADOPT 不寄与): philosophy-domain BERT (要 prior art
     確認)
6. **rescore script 新規** (`scripts/m9-c-adopt/rescore_vendi_alt_kernel.py`):
   - 既存 `.steering/20260515-m9-c-adopt-retrain-v2-verdict/matrix-inputs/`
     の v2 + no-LoRA pilot 出力を input
   - 各 primary encoder で v2 と no-LoRA を **apples-to-apples** で rescore
   - bootstrap 95% CI on `cohens_d` (seed=42)
   - **balanced bootstrap**:
     - language-balanced (de/en/ja 内 independent resampling)
     - token-length-balanced (各 length quartile 内 independent resampling)
   - **within-language d 併報告** (d_de, d_en, d_ja)
   - 出力: `.steering/20260516-m9-c-adopt-da15-impl/da15-rescore-{encoder}-
     kant.json` (per-encoder)
7. **DA-15 verdict 計算 + 文書化**:
   - 新 metric: `vendi_semantic_v2_encoder_swap` (point ≤ -0.5、CI upper < 0、
     balanced 条件維持)
   - MPNet `vendi_semantic` を historical record として併報告 (DA-14 fail の
     まま、DA-15 新 metric で評価)
   - 全 primary encoder の calibration panel AUC、balanced d、within-language
     d を集計
   - `.steering/20260516-m9-c-adopt-da15-impl/da15-verdict-kant.json` 出力:
     - per-encoder: d (overall), d (balanced lang), d (balanced length),
       d_de / d_en / d_ja, AUC, ICC（kernel 独立軸、再計算不要だが PASS 状態
       確認）
     - kant ADOPT 判定 (Plan A pass = 2-of-3 quorum、Vendi-swapped + ICC、
       Burrows は named limitation FAIL のまま)
8. **kant ADOPT verdict 文書** (`da15-verdict-kant.md`):
   - "Burrows reduction remains FAIL; German function-word stylometry is not
     improved. Plan A ADOPT rests only on DA-15
     `vendi_semantic_v2_encoder_swap` + ICC(A,1) の 2-of-3 quorum、Burrows
     axis は Phase 2 (Plan B retrain) または reference corpus work で別途
     追求する open issue" を **必須記載** (Codex LOW-1 反映)
9. **`scripts/m9-c-adopt/da1_matrix_multiturn.py` comparator 修正**:
   MATCHED HISTORICAL Ollama (DA-11 era) → no-LoRA SGLang (DA-14 baseline)
   に切替 (本 PR と同梱推奨、別 PR でも可)
10. **Codex independent review** (`.steering/20260516-m9-c-adopt-da15-impl/
    codex-review-prompt.md` 起草 → `codex exec`): Plan A 実装の HIGH-3
    compliance、calibration panel の妥当性、encoder 選定の statistical
    soundness を review

## /reimagine 不要 (理由)

本 implementation セッションは DA-15 ADR で確定した spec の **literal 実装**
であり、設計判断は ADR 段階で完了済。/reimagine は新規設計判断時のみ。

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260516-m9-c-adopt-da15-adr/decisions.md` D-1 (採用案) / D-2
   (Codex HIGH-1/2/MEDIUM/LOW 反映)
2. `.steering/20260516-m9-c-adopt-da15-adr/design.md` (Phase 1 sketch)
3. `.steering/20260516-m9-c-adopt-da15-adr/codex-review.md` (HIGH-2
   calibration panel mandate の literal text)
4. `.steering/20260513-m9-c-adopt/decisions.md` DA-15 (横断 ADR、本 PR で
   append 済)
5. `src/erre_sandbox/evidence/tier_b/vendi.py:294-322` (`_load_default_kernel`
   現状)
6. `scripts/m9-c-adopt/compute_baseline_vendi.py` (現行 default usage)
7. `.steering/20260515-m9-c-adopt-retrain-v2-verdict/da14-verdict-v2-kant.json`
   (rescore baseline 値)

## NOT in scope (本セッション)

- Plan B (Phase 2) の実装 (Plan A 失敗時に別 PR で起票)
- nietzsche / rikyu の Plan A 展開 (kant ADOPT 後の Phase C で判断)
- Phase E A-6 / Plan C (rank=16) (本 ADR scope 外)
- DA-15 trace.HEAD への本 PR merge SHA 埋め込み (本 PR merge 後の別 chore PR)
- Hybrid H-α の Plan B driver pre-stage (isolated branch で並行、Plan A の
  test/CI/PR には含めない)

## 完了条件

- [ ] `feature/m9-c-adopt-da15-implementation` branch (main 派生)
- [ ] `.steering/20260516-m9-c-adopt-da15-impl/` の 5 標準 file
- [ ] vendi.py / compute_baseline_vendi.py の encoder 引数化 (backward-compat、
      MPNet default 維持)
- [ ] calibration panel script で multilingual-e5-large + bge-m3 が AUC ≥
      0.75 を pass (fail なら Phase 2 へ直接 fall through)
- [ ] encoder + revision pin pre-registration commit (rescore 前に decisions.md
      D-2 へ固定)
- [ ] rescore script で v2 + no-LoRA を apples-to-apples で再 score、balanced
      bootstrap + within-language d 完了
- [ ] DA-15 verdict (`da15-verdict-kant.json` + `.md`) で kant ADOPT/REJECT
      確定
- [ ] kant ADOPT 時は Burrows named limitation を verdict 文書に必須記載
- [ ] da1_matrix_multiturn.py comparator 切替 (同 PR or 別 PR)
- [ ] Codex independent review 起票 + HIGH 反映
- [ ] commit + push + `gh pr create`

## 留意点

- **HIGH-3 遵守**: DA-14 thresholds は不変。Plan A は新 versioned metric
  `vendi_semantic_v2_encoder_swap` で評価、MPNet `vendi_semantic` は historical
  record として併報告。"DA-14 fail のまま DA-15 pass" を文書化
- **両 Claude arm 共通の cross-arm blind spot に注意**: V1/V2 共通で
  "multilingual-e5/bge-m3 は retrieval-trained で style discriminator でない"
  を見落とし。Codex HIGH-2 で救出。本セッションで calibration panel を妥協なく
  実装し、AUC 基準を満たさない encoder は ADOPT 寄与不可
- **Plan A pass で Burrows FAIL のまま kant ADOPT** する経路を明示的に許容
  (DA-14 kant quorum = 2-of-3、Vendi-swapped + ICC で 2)。named limitation を
  忘れず記載
- **Hybrid H-α** は別 branch (`feature/m9-c-adopt-da15-plan-b-prep`) で
  並行作業。本 PR には commit しない、Plan A test/CI に含めない
- **本 PR の merge SHA を DA-15 trace.HEAD に埋め込む** (別 chore PR、
  DA-14 convention 踏襲)
```

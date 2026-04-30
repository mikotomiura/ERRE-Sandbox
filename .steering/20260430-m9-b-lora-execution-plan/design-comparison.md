# Design Comparison — v1 vs v2 + Hybrid 採用案

## 比較目的

CLAUDE.md ルール「Plan 内 /reimagine 必須」に従い、design-v1.md (Claude 初回案) と
design-v2.md (/reimagine による再生成案、v2-B「評価基盤先行」) を並べ、
Codex independent review 前の hybrid 案を起草する。

## 軸別比較表

| 軸 | v1 (実装最優先) | v2 (評価基盤先行) | hybrid 採用 (案) |
|---|---|---|---|
| **A. 量子化** | QLoRA NF4 即採用 + 実装着手 | QLoRA NF4 を技術選定として採用、実装は gate | **v2 採用**: 選定は確定、実装は J 軸完成後 |
| **B. Library** | unsloth 即採用 | M9-eval-system 完了後 spike | **v2 採用**: premature 決定回避 |
| **C. Serving** | vLLM full migration | 現行 SGLang 維持、LoRA 決定後 | **v2 採用**: 移行コスト避ける |
| **D. Trigger 閾値** | 3 条件 AND | 4 条件 AND (prompting plateau 追加) | **v2 採用**: empirical 必要性検証 |
| **E. Parquet schema** | flat 結合 + persona partition | + Tier A-B metric を first-class field | **v2 採用**: 評価系統合 |
| **F. Evaluation epoch** | Run-level boolean flag | 同 + 頻度 policy | **hybrid**: v1 + 頻度 policy 追加 |
| **G. Persona N=4** | M9-B 中 YAML 起草 | 完全 defer to M10 | **v2 採用**: 評価系優先 |
| **H. Adapter swap** | M9-C 早期実装 | LoRA 適用決定後 | **v2 採用**: 不要なら捨てる |
| **I. Drift gate** | 守りのみ (margin 50%) | 双方向 (守 + 攻、攻は post-LoRA Tier B baseline 比較) | **v2 採用**: gate 完結 |
| **J. 評価系** | framework 宣言のみ | Tier A 完全実装 + Tier B 半実装 + golden baseline | **v2 採用**: M9-B の deliverable を評価系に再定義 |
| **J5 攻めの gate** | floor 維持のみ | 絶対 5% 改善要求 | **hybrid**: persona-conditional で 5%、ただし「初回 run のみ floor 維持に緩和」 |

## 判断: hybrid 採用案 (v2 ベース + F/J5 微調整)

**主軸**: v2 (評価基盤先行)

**v1 から保持する要素**:
- Parquet schema の flat 結合方針 (E)
- Run-level evaluation_epoch flag (F)
- 守りの drift gate margin 50% (I の片方)

**v2 で書き換える要素**:
- LoRA 適用判断の保留 (A/B/C/G/H すべて)
- 攻めの gate 追加 (D の条件 4、I の攻めの方向)
- 評価系を M9-B の主 deliverable 化 (J)
- N=4 を M10 完全 defer (G)

**hybrid 微調整 (v2 を緩める)**:
- F に「evaluation 頻度 policy」を追加 (毎 100 turn ごとに 1 evaluation run)
- J5 攻めの gate を「絶対 5% 改善」固定ではなく「初回 LoRA run は floor 維持で許容、
  2 回目以降の run は 5% 改善要求」に緩和。理由: LoRA は warmup が必要、初回で 5% は厳しい

## hybrid 採用案の数値 gate

| Gate | 条件 | 動作 |
|---|---|---|
| Dataset trigger | dialog_turn≥500 AND div±10% AND floor (self_rep≤0.10, echo≤0.10) AND prompting plateau (<5% improvement 2 連続 run) | LoRA 適用 fire |
| Drift (守) | self_rep>0.15 OR cross_echo>0.15 | auto rollback |
| Drift (攻) | post-LoRA Tier B < pre-LoRA baseline | auto rollback (2 回目以降 run のみ) |
| 改善要求 (J5 攻めの gate) | 初回 run: floor 維持。2 回目以降: post-LoRA Tier B ≥ pre-LoRA + 5% | LoRA 採用 |
| VRAM | base 5GB + 3 adapter ≤ 7GB total (N=3 維持) | M10 で N=4 再評価 |
| 評価系 ready | golden baseline 採取完了 + Tier B (Vendi + Big5 ICC) 実装完了 | LoRA 適用判断 enabled |

## 採用 timeline (hybrid)

```
M9-B (本タスク, planning + design only):
  ├ Parquet schema 設計 (E)
  ├ Tier A metric interface 定義 (J 一部)
  ├ Burrows' Delta reference corpus 整備計画
  ├ LIWC license 検討 + alternative 候補
  ├ golden set 採取 technical spec
  └ M9-eval-system スコープ確定

M9-eval-system (新タスク):
  ├ Parquet pipeline 実装
  ├ Tier A 実装 (per-turn)
  ├ Tier B 実装 (Vendi / IPIP-NEO / Big5 stability)
  ├ golden baseline 採取 (3 persona × 5 run × 500 turn)
  ├ golden set 整備 (3 persona × 100 reference utterances)
  ├ Tier C 一部 (Prometheus 2 + G-Eval)
  └ evaluation pipeline 自動化

[GATE: 評価系 ready + dataset trigger fire 条件全部成立]

M9-C (LoRA 実装):
  ├ unsloth spike (Kant、rank=8)
  ├ vLLM --enable-lora migration
  ├ LoRA 学習 loop
  ├ 双方向 gate 実装
  ├ adapter swap runbook
  └ 3 persona 展開
```

## hybrid 採用案の残存リスク

(codex review で問うべき論点)

1. **M9 milestone 全体の delay**: M9-B + M9-eval-system で 2-3 セッション + M9-C で計 3-5 セッション。
   M9 全体で原計画より 2 倍程度の時間 → 外部 commit / OSF 事前登録への影響評価必要
2. **評価系の品質保証**: Prometheus 2 / G-Eval の出力を信用できるか? bias literature 警告
3. **golden set 整備の人手コスト**: 3 persona × 100 reference utterances は専門知識必要、
   ユーザ自身 (mikotomiura) がやるか外部 review 求めるか
4. **prompting plateau の operational 定義**: 「2 連続 run で <5% 改善」の noise floor 不明
5. **絶対 5% 改善要求の根拠**: LoRA paper の domain-general estimate を philosophical role-play
   に流用してよいか?
6. **N=3 漸近線の未知**: prompting で N=3 がどこまで伸びるか empirical に未測定
7. **M9-eval-system の design 自体が大規模化**: J 軸 framework だけだったはずが、評価系実装が
   独立タスクの規模になる → 当初の M9-B → M9-C 直行よりも複雑度増加

## 残された判断 (codex review に問う)

(これらは独立 reviewer の意見が決定的に有用な論点)

1. v2-B (評価基盤先行) は本当に v1 (実装最優先) より優れているか?
   それとも v1 のリスクを過大評価していないか?
2. M9 milestone の delay を許容する判断は研究プロジェクトとして合理的か?
3. golden set 整備を M9-eval-system に含めることの工数見積り (現実的か)
4. Prometheus 2 / G-Eval の bias literature を踏まえ、判定の信頼性をどう担保するか
5. AND 4 条件の中で最も relax 候補なのはどれか? (現実的に達成困難な条件があれば指摘)
6. evaluation_epoch flag の物理分離 (Parquet partition 別ディレクトリ) は overengineering か?
7. 攻めの gate を「初回 run は floor 維持」に緩める判断は妥当か?
8. LIWC license 評価が間に合わない場合の OSS alternative は適切か (Empath / spaCy)?
9. Burrows' Delta の翻訳汚染対応として multi-language strategy は何が現実的か?
10. M9-B で実装着手しないことの risk hedge (短期 deliverable を別形で出すか?)

→ 次フェーズ: codex-review-prompt.md 起草 → Codex 起動 → codex-review.md verbatim 保存

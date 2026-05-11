# Codex Independent Review — M10-0 concrete design (Reasoning model judgment 含む)

## あなた (Codex) の役割

私 (Claude) はユーザーの「Reasoning model」アイディア (post-training / RL / activation 分析 /
weight steering / 社会心理学的 trait 抽出を組み合わせた思考ドメイン model 開発) を ERRE M10+
phasing に射影した判定メモ (`reasoning-model-judgment.md`) を、PR #144 (merged design-final.md +
decisions.md DA-1〜DA-13) と PR #145 (DB11 contamination prevention) に対して validate し、
**M10-0 (Pre-flight: individuation metrics + dataset manifest + cache benchmark + prompt
ordering contract) の concrete design** を `m10-0-concrete-design-draft.md` として起こした。

あなたの仕事は arbitrate ではなく、**この 2 文書を独立 stress-test** すること:

1. `reasoning-model-judgment.md` の判定 (DEFER/ADOPT-WITH-CHANGES 配置) が既存 ADR 整合の
   うえでさらに structurally robust か
2. `m10-0-concrete-design-draft.md` の concrete design (channel × metric matrix、permanent
   layer、acceptance、threshold preregister、recovery protocol、WP 分割) が実装可能水準で
   miss / blind spot を含んでいないか

HIGH を必ず最低 3 件、できれば 5 件出すこと。「問題ない」と書くだけの review は失敗とみなす。

期待する独立性: Claude solo の判定と reimagine 未適用の concrete design に対し、
- M9-B LoRA contamination (DB11) との結合 risk
- LLM 自己宣言 pattern (DA-4 Q7) の再混入 risk
- empirical falsifiability の欠落
- mecab / Vendi kernel / Big5 ICC の operational definition 不足
- recovery protocol の ME-9 同型 false-positive risk
- M9-eval Phase 2 capture format との互換性

を厳しく見ること。Web search は **必須**: activation steering / representation engineering /
Identity Drift 系の 2024-2026 prior art を引用し、本提案が "weight-level intervention M12+ defer"
を正当化できるか確認すること。

## 出力フォーマット (必須)

```
## Verdict (1 行)
ADOPT-AS-IS / ADOPT-WITH-CHANGES / REVISE / RECONSIDER / REJECT

## HIGH (must-fix before M10-0 task scaffold 起票 — 最低 3 件、できれば 5 件)
- HIGH-1: ...
  - Risk: ...
  - Mitigation: ...

## MEDIUM (should consider, 採否は明示)

## LOW (nit / optional)

## reasoning-model-judgment.md 判定の妥当性 stress-test
1. Q1: "weight-level intervention M12+ defer" の妥当性 (2024-2026 activation steering / representation engineering の進展で M10/M11 active spike を許す根拠はあるか)
2. Q2: "trait 抽出 = sidecar metric" 化で User の Reasoning model 構想本来の表現力が失われていないか (失われていれば何を補うべきか)
3. Q3: §3.1 5 metrics (semantic_centroid_distance / belief_variance / world_model_overlap_jaccard / base_retention_burrows / intervention_recovery_rate) は概念的に直交か、重複測定はないか
4. Q4: §4 M11-C 再判定 gate の 4 条件は十分か (Burrows base retention + 3 divergence metrics + adoption rate + negative control)
5. Q5: §5 不採用 5 項目 (思考ドメイン model 開発 / base+individual 同一 LoRA / SWM+Dev+Arc 即 post-training / cognitive_habits runtime 上書き / 人間らしさ RL) の defer は永久 defer か empirical gate ありか

## m10-0-concrete-design-draft.md の stress-test
6. Q6: channel × metric matrix (§2.2) で見落としている channel / metric は (reasoning_trace 利用、cognitive habit recall rate 等)
7. Q7: 永続化 layer (§2.3、DuckDB `individuation_metrics` table) が training-view loader filter (DB11) を bypass しない設計担保は十分か
8. Q8: acceptance A2 (mecab ja-tokenizer Burrows ±0.05 以内) は妥当か、A3 (semantic_centroid_distance N=1 degenerate) の handling は適切か
9. Q9: threshold preregister 表 (§2.5) で TBD のまま M10-0 を close する acceptance 構造 (TBD を M11-C 直前に固定) は empirical preregister 原則に違反しないか
10. Q10: recovery protocol (§2.6) の opposite-stance memory 強制注入は LLM 自己宣言 pattern (DA-4 Q7) を再導入しないか、Python が evidence-driven に発火させる代替設計はあるか
11. Q11: WP 分割 (§3) の WP4 (mecab 移行) を M10-0 timing で行うか、M10-B/C 後の別 task にすべきか (依存最小化観点)
12. Q12: §4 リスク表 (mecab Burrows 変動 / embedding reproducibility / Big5 ICC N=1 degenerate / recovery protocol T_* 数値 / Vendi MPNet 日本語性能) で見落としているものは

## 関連 prior art (web_search 必須)
- Anthropic Constitutional AI / Representation Engineering (2024-2026)
- Activation Steering / RepE (Zou et al. 2023-2026 最新動向)
- Identity Drift in LLM agents (2025-2026 EACL / NeurIPS)
- Generative Agents persistent identity follow-up
- Agent Identity Evals 2025 + 後続
- Anthropic Persona Vectors / character steering 系
- Vendi score multilingual kernel 動向
- IPIP-NEO short form Japanese validation

## Final notes (個人プロジェクト scope + 予算ゼロ制約への警告含む)
```

## 入力ファイル (verbatim 引用、要約しないこと)

### 1. `reasoning-model-judgment.md` (全文)

```
# Reasoning model アイディア設計判断メモ

- **作成日**: 2026-05-11
- **位置づけ**: M10+ cognition-deepening の外付け記憶
- **入力**: ユーザーと対話内の問い
- **結論**: **M10 本線で model weight / activation intervention として取り込むのは却下。M10-0〜M10-C の評価・抽出・bounded steering 設計として取り込むのは採用。**

## 0. 要旨

ユーザーの中心アイディアは「思考ドメインを持つ Reasoning model」を作るために、事後学習・強化学習・ステアリング・社会心理学・活性化/重み分析を組み合わせ、特性を抽出・交差・介入する研究開発である。

ERRE-Sandbox に対しては、この発想は **個体化を観測・制御する研究プログラム** として有効。ただし M10 ではモデル重みそのものを開発対象にしない。M10 の責務は、`PhilosopherBase` の base fidelity と `IndividualProfile` の divergence を分離して測れる状態を作ることであり、weight-level intervention は M11-C empirical validation 後の M12+ research gate に置く。

## 1. 判定

| アイディアの要素 | ERRE 判定 | 配置 |
|---|---|---|
| LLM の事後学習 / SFT / RL | **DEFER** | M12+。M10 では取り込まない |
| 活性化・重み分析 | **RESEARCH SPIKE ONLY** | M12+。M10 本線の acceptance にしない |
| 特性ドメイン抽出 | **ADOPT-WITH-CHANGES** | M10-0 sidecar metrics として実装候補 |
| 特性の交差・合成 | **DEFER/MODIFY** | M11-C 後。同一 base multi-individual の結果を見て判断 |
| ステアリング / 介入 | **ADOPT-WITH-CHANGES** | M10-C `WorldModelUpdateHint` の bounded primitive に限定 |
| 実証実験設計 | **ADOPT** | M10-0 の中心タスクに組み込む |

## 2. 理由

M10+ の operational thesis は「歴史的認知習慣を immutable substrate とする、観測可能に発達する人工個体」を作り、base の保存性と individual の発達を同時に測ることである。

そのため、M10 で weight-level の reasoning model 開発に入ると、次の 3 つが崩れる。

1. **Base / Individual 分離が崩れる**
   `PhilosopherBase` の LoRA-trained style と `IndividualProfile` の world model divergence が同じ重み空間に混ざり、何が base retention で何が個体化か測れなくなる。

2. **M9-B LoRA contamination 防止と衝突する**
   M9-B training は `individual_layer_enabled=false` の base-only data だけを使う制約を持つ。M10 で個体 layer の出力を training / post-training に混ぜると、この設計判断を破る。

3. **LLM 自己宣言による内部状態更新リスクが再発する**
   Reasoning model型の "介入" を free-form steering として入れると、ME-9 incident と同型の false-positive 構造になる。ERRE では LLM は候補提示のみ、Python が observable evidence に基づいて state transition する。

## 3. M10 で採用する形

### 3.1 M10-0: Reasoning trait sidecar metrics

Reasoning modelの「抽出」を model-internal analysis ではなく、まず ERRE の観測ログからの sidecar metric として定義する。

候補:

- `semantic_centroid_distance`: 同一 `PhilosopherBase` 由来 individuals の発話 embedding 距離
- `belief_variance`: `SubjectiveWorldModel` / promoted belief のばらつき
- `world_model_overlap_jaccard`: SWM entry key の重なりと分岐
- `base_retention_burrows`: Burrows ratio は base style retention 専用
- `intervention_recovery_rate`: perturbation 後に base habit へ戻るか、individual belief が残るか

Acceptance:

- 既存 M9 baseline data に対して metric が valid 値を返す
- Burrows と individualization metrics が同じ概念を二重測定していない
- M10-A schema scaffold 前に、metric 名・入力 channel・出力 sidecar schema を固定する

### 3.2 M10-B: Read-only subjective trait injection

Reasoning modelの「特性ドメイン」は、`SubjectiveWorldModel` の top-K entry として USER prompt 側に bounded injection する。

制約:

- SYSTEM prompt には入れない
- `_COMMON_PREFIX` + immutable `PhilosopherBase` block の cache 共有を壊さない
- prompt token 増分は +200 以内
- LLMPlan はまだ変更しない

### 3.3 M10-C: Bounded steering only

Reasoning modelの「介入」は、free-form steering ではなく `WorldModelUpdateHint` に限定する。

許可:

\`\`\`python
WorldModelUpdateHint(
    axis="env" | "concept" | "self" | "norm" | "temporal",
    key="...",
    direction="strengthen" | "weaken" | "no_change",
    cited_memory_ids=[...],
)
\`\`\`

禁止:

- arbitrary hidden-state patching
- free-form "personality update"
- LLM の自己申告による stage advance
- weight update / LoRA update
- `cited_memory_ids` を伴わない belief injection

Python 側が `cited_memory_ids ⊆ retrieved_memories` を検証し、threshold を満たす場合だけ merge する。

## 4. M11-C 後に再判定する形

M11-C で `kant` base から 3 individuals を走らせ、次が同時成立した場合だけ Reasoning model型の deeper intervention を再評価する。

- Burrows ratio が base retention を示す
- semantic centroid / belief variance / SWM overlap が individual divergence を示す
- `WorldModelUpdateHint` の adoption rate が `[0.05, 0.40]` 内に収まる
- free-form belief が採用されない negative control が通る

その後の M12+ research gate 候補:

- activation analysis spike
- representation steering spike
- individual LoRA spike
- same-base multi-individual RL / preference tuning
- reasoning-domain transfer test

## 5. 採用しない形

以下は少なくとも M10/M11 では採用しない。

- 「思考ドメインを持った Reasoning model」を ERRE の新しい中核 model として作る
- Kant / Nietzsche / Rikyū の base persona と individual divergence を同一 LoRA に混ぜる
- SWM / DevelopmentState / NarrativeArc を学習データとして即座に post-training へ流す
- `PhilosopherBase` の `cognitive_habits` を runtime 成長で上書きする
- 人間らしさを直接 objective にした RL

## 6. 実装メモ

M10-0 task を起票する時、このメモは次の requirement に変換する。

1. Reasoning model 型 trait extraction を **sidecar metrics** として preregister する
2. metric 入力 channel を `raw_dialog`, `reasoning_trace`, `semantic_memory`, `SubjectiveWorldModel` に分ける
3. Burrows = base retention、semantic/belief/SWM metrics = individual divergence と明記する
4. M10-B/C の steering は `WorldModelUpdateHint` に閉じる
5. weight-level intervention は M12+ research gate に明示 defer する
```

### 2. `m10-0-concrete-design-draft.md` (本 prompt と同一 directory に配置済、Read で参照)

Path: `.steering/20260508-cognition-deepen-7point-proposal/m10-0-concrete-design-draft.md`

主要セクション:
- §1 memo 判定 (Claude solo)
- §2.2 Channel × Metric matrix (9 metrics × 4 channels)
- §2.3 永続化 layer (DuckDB additive table + JSON sidecar key)
- §2.4 Acceptance A1-A8
- §2.5 Threshold preregister 表 (8 thresholds、一部 TBD)
- §2.6 Intervention recovery protocol (T_base=200 / T_perturb=50 / T_recover=200 tick)
- §2.7 out-of-scope (M10-A/B/C / M11-A/B/C / M12+ への送り先)
- §2.8 PR #127 (M9-B LoRA) 追記事項
- §2.9 PR #148 P4a Tier B 接続 (Vendi / Big5 ICC)
- §3 WP 分割 (8 WP、production ~1400 LOC + test ~400)
- §4 リスク (HIGH 1 / MEDIUM 3 / LOW 1)

## 既存 ADR / merge 済 PR 引用 (Codex は file Read 可)

- `.steering/20260508-cognition-deepen-7point-proposal/design-final.md` (PR #144 merged) — §0 thesis re-articulation、§1 二層 architecture、§2 M9 trunk 接続、§3 phasing、§5 acceptance
- `.steering/20260508-cognition-deepen-7point-proposal/decisions.md` (PR #144 merged) — DA-1 〜 DA-13
- `.steering/20260430-m9-b-lora-execution-plan/design-final.md` (PR #145 で DB11 ADR Addendum 2026-05-08 追記) — base-only training data 制約
- `src/erre_sandbox/eval/tier_b/` (PR #148 merged) — Vendi / IPIP-NEO / Big5 ICC 実装
- `data/eval/golden/` (M9-eval Phase 2 capture format) — `_audit_stimulus.json` + per-cell `*.duckdb.capture.json`

## 個人プロジェクト scope への警告

- 予算ゼロ制約 (クラウド LLM API 非依存、ローカル SGLang+Ollama)
- 個人開発、現実的に M10-0 〜 M12 まで empirical 走行に 数ヶ月単位
- M9-eval Phase 2 run1 calibration は G-GEAR で overnight×2 (30h × 5 cells) かかる種類
- Codex review は HIGH 切出で実装前に compress するための tool であり、scope 拡大には使わない

## Verdict 解釈基準

- ADOPT-AS-IS: 何の修正もなく M10-0 task scaffold 起票可
- ADOPT-WITH-CHANGES: HIGH 反映で起票可 (推奨着地点)
- REVISE: HIGH 数件が structural、design を draft 段階に戻す
- RECONSIDER: 既存 ADR (PR #144/#145) との整合性を再検討する必要
- REJECT: 本提案を破棄し別アプローチ (例: M10-0 を skip して M10-A scaffold 直行)

以上。Web search を必ず使い、HIGH 最低 3 件 (理想 5 件) を出すこと。要約せず HIGH/MEDIUM/LOW
ごとに Risk + Mitigation を verbatim 提示すること。

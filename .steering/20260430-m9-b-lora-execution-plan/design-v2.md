# Design v2 — /reimagine 再生成案 (10 軸: 評価基盤先行 = v2-B 路線)

> ⚠️ **このドキュメントは /reimagine による v1 破棄後のゼロベース再生成案。
> v2-B「評価基盤先行 (LoRA 適用前に J 軸を確立)」をアンチテーゼ仮説として採用。
> 実装方針は design-final.md で確定する。**

## 設計思想 (v2 の前提転換)

**v1 の暗黙前提**: 「LoRA を回せば persona divergence は伸びる」
**v2 の前提**: 「**LoRA 適用の成否を測れない状態で適用してはならない**」

Why: 既存 Evidence Layer は守備的 metric (repetition_rate / cross_persona_echo_rate) のみ。
「思想家らしさが向上したか」を測る攻めの metric が ζ time でも未定義。LoRA を適用しても
**それが効いたかどうかすら分からない** 構造的欠落。

加えて、prompting + persona YAML 拡張で現在の divergence をどこまで伸ばせるかの **天井**
を測っていない。LoRA 適用の必要性自体が empirically 立証されていない (research-evaluation-metrics.md
最終 caveat 参照)。

→ **M9-B では LoRA 適用判断を保留し、評価系を先に立てる**。LoRA 関連は技術調査
(A 量子化選定、E Parquet schema 設計) は維持しつつ、実装着手は評価系完成後に gate する。

これにより M9-B の deliverable は「LoRA 実装 plan」ではなく「**LoRA 適用 / 不適用の go-no-go
判定基盤**」に再定義される。

## 10 軸の決定 (v2)

### A. 量子化戦略 → **QLoRA (NF4) を技術選定として採用、適用判断は defer**

**決定**:
- 技術調査として QLoRA NF4 を採用候補とする (VRAM 16GB 制約下の唯一現実解)
- ただし「いつ適用するか」は J 軸 (評価系) の baseline + gate 確立後に再評価
- 不要と判明した場合は full FP16 + prompting 路線も残す

**根拠 (v1 と同):** G-GEAR 16GB + qwen3:8b + 3 persona swap は QLoRA 必須

**v1 との差**: 採用は決めるが、実装着手は gate する

### B. Library 選定 → **defer until evaluation baseline 採取後**

**決定**: PEFT vs unsloth spike は **M9-eval-system 完了後の M9-C kickoff 時** に実施
**根拠**: 学習 library 選定は LoRA を実際に走らせる時点で十分。先行決定する benefit なし
**v1 との差**: v1 は B を即断したが、これは premature optimization

### C. Serving 移行判断 → **現行 SGLang/Ollama 維持、vLLM 移行は LoRA 適用判断後**

**決定**:
- M9-B / M9-eval-system 期間は現行 SGLang/Ollama 維持
- vLLM 移行は LoRA 適用が決まった時点で実装フェーズの一部として遂行
- M5 以降の resonance 機構 / ERRE mode FSM の再配線リスクを評価系完成後に評価

**根拠**: SGLang 撤退は大規模変更、LoRA 必要性が empirical に立証されてから判断すべき
**棄却**: v1 の「vLLM full migration を M9-C 早期に実行」 — premature

### D. Dataset trigger 閾値 → **4 条件に拡張、攻めの gate を組み込み**

**決定**: 以下 **すべて** が満たされたら LoRA 適用 fire:
1. `dialog_turn ≥ 500` per persona
2. `divergence_ratio` (ζ 36:74:16 cadence 起点) が ±10% 以内維持
3. `baseline floor`: self_rep ≤ 0.10 AND cross_echo ≤ 0.10
4. **NEW**: `prompting ceiling`: prompting + persona YAML 拡張のみで Tier A-B metric が
   2 連続 run で plateau (改善幅 < 5%) — つまり「prompting で伸ばせる限界に達した」証拠

**根拠**:
- 条件 4 は v1 の「LoRA を回せば divergence 伸びる」前提を empirical に検証する
- prompting で伸ばせるなら LoRA は不要、伸ばせないなら LoRA を適用する正当な根拠あり
- 「天井未確認で LoRA 適用」は実験設計として弱い (LoRA の効果か prompting の余地かを区別不能)

**v1 との差**: 攻めの gate (条件 4) を追加、AND 強条件のまま

### E. Parquet export schema → **評価系 Tier A-B metric を組み込んだ拡張 schema**

```
schema:
  - run_id: str
  - persona_id: str (partition key)
  - turn_idx: int
  - timestamp: float
  - mode: str (ERREMode)
  - zone: str
  - dialog_turn_text: str
  - reasoning_trace_text: str (nullable)
  - episodic_log_event: str (nullable)
  - embedding: list[float] (768d, nomic)
  - evaluation_epoch: bool
  # NEW Tier A metrics (per-turn)
  - liwc_categories: dict[str, float] (~100 categories) | null  # license 確定後
  - burrows_delta_to_persona: float | null
  - mattr_score: float
  - semantic_novelty: float
  - repetition_rate: float
  - cross_persona_echo_rate: float
  - persona_contradiction_rate: float | null
  # NEW Tier B metrics (per-100-turn aggregate, sparse)
  - vendi_score_window_200: float | null
  - ipip_neo_big5: list[float] | null  # 5d, 100-turn 周期で更新
  - personality_stability_icc: float | null
```

partition: `persona_id=*/run_id=*/`

**v1 との差**: 評価 metric を Parquet schema に first-class field として組込。
training data と evaluation data が同 schema で扱える

### F. 評価 epoch 分離 → **Run config + Parquet partition で物理分離 (v1 と同)**

- `evaluation_epoch: bool` を Run config + Parquet schema 必須化
- Default `False`
- Evaluation run は手動切替、autonomous log と Parquet partition 別ディレクトリ
- **NEW**: evaluation run の頻度を policy として決める (例: 毎 100 turn ごとに 1 evaluation run)

### G. Persona N=4 拡張時期 → **完全 defer to M10**

**決定**: agora 主体 (4 人目) の追加は M10 まで完全保留
**根拠**:
- M9-B / M9-eval-system 期間は **N=3 の divergence 漸近線** を測ることが優先
- N=3 で prompting ceiling に達し、評価系が立ったら、N=4 追加が必要かを再判断
- 早すぎる persona 拡張は評価系設計を複雑化させる (4 thinker の reference corpus / golden set 整備コスト)

**棄却**: v1 の「M9-B 中 YAML 起草」 — premature commitment

### H. Adapter swap runbook → **defer until LoRA 適用決定後**

**決定**: vLLM LoRARequest API ラッパ実装は LoRA 適用決定 (条件 D 4 つすべて満たし) 後
**根拠**: 適用しないなら不要、適用するなら適用と同時に実装

### I. Baseline drift gate → **双方向 gate (守り + 攻め)**

**決定**: drift gate を 2 方向で運用
- **守り (劣化 detect)**: self_rep > 0.15 OR cross_echo > 0.15 で auto rollback (v1 と同)
- **攻め (改善要求)**: LoRA 適用 run で Tier B (Vendi Score + IPIP-NEO Big5 stability)
  が pre-LoRA baseline より **下回った** 場合は次 run でも auto rollback
- baseline は J6 で採取する pre-LoRA golden baseline (M9-eval-system 成果物)

**根拠**: 守りだけでは「適用が効いた」を測れない、攻めがあって初めて gate 完結

**v1 との差**: 攻めの方向 (改善要求) を gate に組込

### J. 思想家らしさ評価系 framework → **M9-B 内で Tier A 完全実装 + Tier B 半分実装 + golden baseline 採取**

**決定**:

#### J1 評価次元 (確定)
1. **思想的深度**: ROSCOE informativeness + Wachsmuth Toulmin 5 dimension
2. **内部一貫性**: Personality stability ICC (Big Five across mode) + persona_contradiction_rate
3. **対話的非自明性**: Vendi Score + semantic novelty
4. **persona-fit**: Burrows' Delta to thinker reference + LIWC analytic style
5. **概念連結性**: concept-graph density (defer to M10、proxy として MATTR)

#### J2 定量化手法 (確定)
- Per-turn (Tier A): LIWC-22 (license 確定後) / Burrows' Delta / MATTR / semantic novelty / contradiction NLI
- Per-100-turn (Tier B): Vendi Score (semantic kernel) / IPIP-NEO-120 / Big Five stability ICC
- Per-session (Tier C): Prometheus 2 rubric assessment / G-Eval logit-weighted / FANToM-adapted ToM probe / ROSCOE on reasoning trace
- Sparse manual (Tier D): FActScore against canonical corpus / 専門家 qualitative review

#### J3 golden set
**必要**。3 persona × 100 reference utterances を canonical corpus から抽出 (Critique / Zarathustra / Nampōroku)。**M9-eval-system タスクの最初の deliverable**

#### J4 baseline 採取方針
- LoRA 適用前 (= 現状の prompting + persona YAML のみ) で Tier A-B metric を 5 run 連続採取
- 各 run 200-500 turn / persona、計 ~3000 turn の baseline corpus
- Parquet で persistent 保存、再現可能

#### J5 攻めの gate (確定)
- **採用**: 「floor 維持のみ」(v1) ではなく「pre-LoRA baseline からの **絶対 5% 以上の改善**」を要求
- 5% は現実的な fine-tuning による divergence 改善幅 (LoRA paper の estimate)
- baseline は persona-conditional (Rikyu LOW idea density は適正、Kant HIGH も適正)

#### J6 切り出し
- M9-B 内: Tier A 全実装 + Tier B のうち Vendi Score + Big Five stability ICC 実装 + golden baseline 採取の準備
- M9-eval-system: Tier B 完全実装 (Prometheus 2 rubric / FANToM-adapted / FActScore-adapted) + 専門家 review pipeline + golden set 採取

**v1 との差**: v1 は J 軸を framework のみで内容空白に近かったが、v2 は実装の半分を M9-B に
取り込み、golden baseline を積極採取する。LoRA 適用判断は J 軸完成後

## 数値 gate サマリ (v2)

| Gate | 条件 | 動作 |
|---|---|---|
| Dataset trigger | dialog_turn≥500 AND div±10% AND floor (self_rep≤0.10, echo≤0.10) AND **prompting plateau (<5% improvement 2 runs)** | LoRA 適用 fire |
| Baseline drift (守) | self_rep>0.15 OR cross_echo>0.15 | auto rollback |
| **Baseline drift (攻)** | post-LoRA Tier B < pre-LoRA baseline | auto rollback |
| **改善要求 (J5 攻めの gate)** | post-LoRA Tier B - pre-LoRA baseline ≥ 5% | LoRA 採用 |
| VRAM | base 5GB + 3 adapter ≤ 7GB total (N=3 維持) | M10 で N=4 再評価 |
| 評価系 ready | golden baseline 採取完了 + Tier B Vendi+ICC 実装完了 | LoRA 適用判断 enabled |

## 実装順序 (M9-B + M9-eval-system + M9-C handoff)

### M9-B (本タスク内): plan のみ + Tier A 設計
1. Parquet pipeline 設計 (E schema 拡張 + evaluation_epoch flag)
2. Tier A metric の interface 定義 (実装は M9-eval-system)
3. Burrows' Delta reference corpus 整備計画 (Critique / Zarathustra / Nampōroku 入手 + 前処理)
4. LIWC license 検討 (商用 license vs OSS alternative)
5. golden set 採取の technical spec
6. M9-eval-system タスクのスコープ確定

### M9-eval-system (新タスク, M9-B 後): 評価系実装
1. Parquet pipeline 実装 (E schema)
2. Tier A metric 実装 (per-turn pipeline)
3. Tier B metric 実装 (Vendi Score + IPIP-NEO + Big Five stability)
4. golden baseline 採取 (3 persona × 5 run × 500 turn)
5. golden set 整備 (3 persona × 100 reference utterances)
6. Tier C 一部 (Prometheus 2 + G-Eval) 実装
7. evaluation pipeline 自動化 + dashboard 化

### M9-C (LoRA 実装、M9-eval-system 完了後の go-no-go gate 通過後): LoRA 適用
1. PEFT vs unsloth spike (1 persona = Kant、rank=8)
2. vLLM `--enable-lora` 起動 + SGLang から migration
3. LoRA 学習 loop 実装
4. 双方向 gate (守 + 攻) 実装
5. adapter swap runbook 文書化
6. 3 persona に展開
7. LoRA 効果評価 (Tier A-D 全 layer で baseline 比較)

## v2 が解決する v1 の弱点

| v1 弱点 | v2 解決 |
|---|---|
| 評価系後置の論理矛盾 | 評価系を M9-B / M9-eval-system で先行実装、LoRA 適用前に baseline 採取 |
| AND 強条件の現実性 | 条件 4 (prompting plateau) で **prompting 天井未確認のまま LoRA 適用** を防止 |
| vLLM full migration コスト | LoRA 適用決定後にだけ migration、不要なら現行維持 |
| LIWC license | M9-B 期間中に評価、商用不可なら OSS alternative (Empath / spaCy) に切替 |
| 「LoRA を回せば divergence 伸びる」前提の検証なし | 条件 4 で empirical に検証 (prompting で伸びるなら LoRA 不要) |
| Burrows' Delta 翻訳汚染 | reference corpus 整備計画で multi-language strategy を M9-B に組込 |
| idea density persona-conditional 性 | persona-baseline からの相対 deviation で gate 設計 (J5 で絶対 5% 改善要求は persona-conditional) |

## v2 が抱える新しい弱点 (self-critique)

(これは codex review でも追及されるべき論点候補)

1. **時間コスト**: M9-B + M9-eval-system + M9-C の 3 タスク化により LoRA 実装着手が 2-3 倍延伸
2. **評価系自体の品質保証**: Prometheus 2 / G-Eval / FANToM-adapted の出力を信用できるか?
   judge bias literature が示すように LLM-judge は systematic bias を持つ
3. **golden set 整備の人手コスト**: 3 persona × 100 reference utterances の質的選定は専門知識必要
4. **prompting plateau の operational 定義**: 「2 連続 run で <5% 改善」は noisy、何を以て plateau とするか曖昧
5. **絶対 5% 改善要求の根拠**: LoRA paper estimate は domain-general、philosophical role-play 用途では noise floor が異なる可能性
6. **N=3 漸近線が不明**: prompting で N=3 がどこまで divergence するか M9-B 時点では未知。
   絶対値 plateau 判定が困難
7. **M9-C を保留することのリスク**: M9 milestone 自体の delay、外部 stakeholder への commit 影響

## v1 vs v2 比較 (高レベル)

| 観点 | v1 (実装最優先) | v2 (評価基盤先行) |
|---|---|---|
| LoRA 適用 timing | M9-C 早期 | 評価系完成後 + prompting plateau 確認後 |
| 評価系 | framework 宣言のみ | Tier A 完全実装 + Tier B 半実装 |
| Serving migration | M9-C で vLLM full migration | LoRA 適用決定後に limited migration |
| Persona N=4 | M9-B で YAML 起草 | M10 へ完全 defer |
| Trigger 条件 | 3 条件 AND | 4 条件 AND (prompting plateau 追加) |
| Drift gate | 守りのみ | 双方向 (守 + 攻) |
| 攻めの gate (J5) | floor 維持のみ | 絶対 5% 改善要求 |
| Risk profile | LoRA を打つ前提が empirical に未検証 | 評価系自体の品質と timing リスク |
| 短期 deliverable | M9-C 早期着手 | 評価系の完成 (LoRA は遅延) |
| 長期妥当性 | LoRA 適用の成否判定が事後不能 | empirical foundation 重視 |

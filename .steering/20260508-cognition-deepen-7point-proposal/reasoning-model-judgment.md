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

```python
WorldModelUpdateHint(
    axis="env" | "concept" | "self" | "norm" | "temporal",
    key="...",
    direction="strengthen" | "weaken" | "no_change",
    cited_memory_ids=[...],
)
```

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

## 7. 参照

- `design-final.md` §0: operational thesis re-articulation
- `design-final.md` §3: M10-0 → M12+ phasing
- `decisions.md` DA-1 / DA-8 / DA-10 / DA-12
- `docs/architecture.md` §9: 計画中アーキテクチャ
- `.steering/20260430-m9-b-lora-execution-plan/design-final.md` Addendum 2026-05-08

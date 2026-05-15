# LLM研究開発手法・評価調査からの改善案メモ 2

Last reviewed: 2026-05-13  
Status: 設計候補。現時点では実装しない。M10-0/M11 の評価拡張と、M12+ の PEFT 比較実験へ分割して扱う。

## 結論

PDF「LLM研究開発手法と評価調査」の中で ERRE-Sandbox に実際に効くのは、
**FT 手法そのものより先に、人格・社会性・個体化を測る評価基盤を厚くする部分**である。

QDoRA は有望な比較候補だが、現時点の ERRE 本線へ入れるのは早い。理由は単純で、
DoRA/QDoRA が LoRA より良いかどうかを判断するための観測系がまだ足りないため。
M10-0 の individuation metrics、Social-ToM 評価、training contamination guard が整うまでは、
QDoRA を採用しても「何が良くなったのか」を厳密に判定できない。

判定:

- M10-0 で人格・個体化・社会性評価を拡張する: **9/10、必須**
- QDoRA を M9/M10 の既定 FT 手法にする: **3/10、不採用**
- QDoRA を M12+ の PEFT ablation arm に追加する: **8/10、採用候補**
- DoRA/QDoRA を Individual layer の重み焼込みに使う: **2/10、M12+ でも慎重**
- QDoRA の前に QLoRA-LoRA baseline を固定する: **10/10、必須**

## 参照した外部情報

- DoRA paper: https://arxiv.org/abs/2402.09353
- Hugging Face PEFT LoRA/DoRA guide: https://huggingface.co/docs/peft/developer_guides/lora
- Hugging Face PEFT quantization guide: https://huggingface.co/docs/peft/developer_guides/quantization
- Hugging Face PEFT `LoraConfig`: https://huggingface.co/docs/peft/main/package_reference/lora
- bitsandbytes overview: https://huggingface.co/docs/bitsandbytes/main/en/index
- SGLang LoRA serving: https://docs.sglang.io/advanced_features/lora.html
- PDF: `/Users/johnd/Downloads/LLM研究開発手法と評価調査.pdf`

## ピックアップ項目と ERRE 判断

| PDF 項目 | ERRE での価値 | 判断 | 改善・拡張先 |
|---|---:|---|---|
| SCOPE / HumanLLM / BIG5-CHAT | 高 | persona を自己申告ではなく、多面的な行動・価値観・一貫性で見る方向は合う | persona/source checklist、M10-A schema validation |
| ExploreToM / SocialEval | 最高 | ERRE の 3D 社会で最も欠けている評価。ToM・誤信念・情報非対称を測れる | M10-0/M11-C Social-ToM harness |
| MentalBench / MentalAlign / HEART | 中-高 | 臨床主張は不可。ただし emotional/cognitive alignment 評価としては有用 | Tier C/D rubric、manual sparse review |
| SFT/DPO/RLVR/GRPO | 中 | 報酬関数未成熟のため、今は危険。検証可能 reward が必要 | M12+ preference/RL research gate |
| DoRA/QDoRA | 中-高 | LoRA より低 rank で強い可能性。ただし serving と評価 gate が未検証 | M12+ PEFT ablation arm |
| Quantum-PEFT | 中 | 圧縮効率は魅力だが、実装・license・serving 互換が未確定 | watch item、M12+ 以降 |
| MoE/SSM/最新 reasoning model | 低 | ERRE のローカル・ゼロ予算制約では即効性が低い | model-watch のみに留める |
| Tutorial Fine-Tuning | 中-高 | ERRE の解釈学的 loop と相性は良い | training ではなく counterfactual/eval protocol に先に反映 |

## QDoRA の技術的位置づけ

### DoRA とは何か

DoRA は LoRA の重み更新を **direction** と **magnitude** に分ける手法。
LoRA が低ランク行列で方向更新を担当し、別の学習可能な magnitude パラメータが
重みベクトルの大きさを調整する。

概念的には、事前学習済み重みを以下のように分ける。

```text
W ~= m * normalize(V)
V' = V + LoRA_update
W' = m' * normalize(V')
```

この分解により、通常 LoRA が苦手な「重み方向と大きさの独立した変化」を扱いやすくなる。
DoRA paper は、LoRA と full fine-tuning の差の一部をこの分解で埋めることを狙っている。

### QDoRA とは何か

QDoRA は、独立した新アルゴリズムというより、
**量子化された base model に DoRA adapter を載せる実用構成**として扱うのが安全。

実装上はおおむね以下の組み合わせになる。

```python
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.bfloat16,
)

lora_config = LoraConfig(
    use_dora=True,
    target_modules="all-linear",
    r=8,
    lora_alpha=16,
    lora_dropout=0.0,
)
```

つまり、ERRE での比較軸は以下になる。

| arm | base | adapter | 位置づけ |
|---|---|---|---|
| A | 4-bit NF4 | LoRA | 現行 QLoRA baseline |
| B | 4-bit NF4 | rsLoRA | LoRA 安定化 baseline |
| C | 4-bit NF4 | DoRA | QDoRA candidate |
| D | 4-bit NF4 | DoRA + all-linear | 高容量 QDoRA candidate |
| E | 8-bit or bf16 | LoRA/DoRA | NF4 劣化確認用 fallback |

## QDoRA の期待値

### 良い可能性

1. **rank=8 付近で LoRA より強い可能性**

ERRE の M9 設計は初期 rank=8 を基準にしている。DoRA は低 rank での LoRA 弱点を補う
方向の手法なので、rank を大きくできない 16GB VRAM 環境では理屈上の相性が良い。

2. **persona style の細かい強弱を表しやすい可能性**

ERRE の `PhilosopherBase` は、語彙だけでなく思考癖・文体密度・反応の強度を固定したい。
direction だけでなく magnitude を持つ DoRA は、style intensity の調整に効く可能性がある。

3. **QLoRA と同じメモリ制約内で比較できる可能性**

PEFT は bitsandbytes 量子化重みとの DoRA 利用を QDoRA として扱えるため、
M12+ の単一 GPU 実験候補にはなる。

### 悪い可能性

1. **SGLang dynamic LoRA serving との互換が未確定**

ERRE は SGLang の dynamic LoRA loading / multi-LoRA serving を前提にしている。
SGLang が期待する adapter が通常 LoRA 形式のみなら、DoRA の magnitude パラメータは
そのまま載らない可能性がある。

この場合、DoRA を merged model として使う手はあるが、persona ごとに full merged
artifact を持つことになり、ERRE の multi-persona adapter swap 設計と相性が悪い。
したがって **SGLang が未 merged DoRA adapter を安全に load できるか** は hard gate。

2. **DoRA は純 LoRA より overhead がある**

PEFT docs でも DoRA は pure LoRA より overhead が大きく、inference では merge 推奨とされる。
ERRE は tick latency と multi-agent throughput が重要なので、少しの精度改善だけでは採用できない。

3. **QDoRA は DeepSpeed ZeRO2 などで報告 issue がある**

ERRE は当面 single GPU だが、将来 FSDP/DeepSpeed を使うならこの互換性問題は無視できない。

4. **評価系が弱いまま使うと persona overfit を見抜けない**

QDoRA は表現力が上がる分、史料人格の再現ではなく、評価刺激への過適合や
role-play 語尾の強化だけを拾う危険がある。

## 採用しないライン

以下はやらない。

- M9/M10 の既定を QLoRA-LoRA から QDoRA に置き換える。
- QDoRA の改善を確認する前に `PhilosopherBase` / `IndividualProfile` schema を変える。
- Individual layer の world model / belief / narrative を QDoRA に焼き込む。
- Social-ToM / individuation metrics がない状態で DoRA の人格改善を主張する。
- SGLang direct-load 未確認のまま DoRA adapter を runtime contract に入れる。
- merged full model per persona を標準配布形式にする。
- benchmark leaderboard や単発 loss 低下だけで QDoRA 採用を決める。

## 実際に改善・拡張すべき箇所

### 1. M10-0 individuation metrics を先に拡張する

QDoRA より先に、以下を実装対象にする。

- `metrics.individuation`
- `AnalysisView` loader
- `cognitive_habit_recall_rate`
- `action_adherence_rate`
- `zone_behavior_consistency`
- `intervention_recovery_rate`
- metric correlation matrix
- `thresholds.md` with `calibrate_before_unblinding`

理由:

QDoRA が「persona base を保ったまま個性を改善した」のか、
単に文体が派手になっただけなのかを分けるには、文体・意味・行動・社会応答を
複数 channel で見る必要がある。

### 2. Social-ToM harness を追加する

ExploreToM / SocialEval 系の発想を ERRE 向けに変換し、以下のような評価 scenario を作る。

- chashitsu で agent A だけが見た object event
- agora で agent B が誤った伝聞を持つ
- garden で counterfactual challenge を注入
- retrieved memory と counterfactual challenge を別 channel に隔離
- 介入後に base habit へ戻るか、個体 world model が過剰に書き換わるかを測る

出力は training data ではなく evaluation-only metrics に限定する。

### 3. persona/source checklist を作る

SCOPE / BIG5-CHAT / HumanLLM から直接 dataset を作るのではなく、
`personas/*.yaml` と `PhilosopherBase` が以下を持っているかを検査する。

- cognitive habits
- values / motives
- conversational stance
- social behavior pattern
- preferred zones
- source provenance
- legend/speculative/fact の区別
- Big Five 的 self-report ではなく、行動証拠への接続

これは M10-A schema 実装前の doc/validator 候補。

### 4. PEFT ablation registry を作る

M12+ で以下の比較を同一条件で走らせるため、先に registry 形式を決める。

```yaml
experiment_id: m12-peft-ablation-kant
base_model: qwen3-8b
dataset_view: raw_dialog_training_only
persona_id: kant
individual_layer_enabled: false
arms:
  - qlora_lora_r8_nf4
  - qlora_rslora_r8_nf4
  - qdora_r8_nf4
  - qdora_all_linear_r8_nf4
metrics:
  - burrows_delta_to_reference
  - vendi_score
  - big5_stability_icc
  - cognitive_habit_recall_rate
  - action_adherence_rate
  - zone_behavior_consistency
  - self_rep
  - cross_echo
  - train_vram_peak_gb
  - train_tokens_per_sec
  - adapter_size_mb
  - sglang_load_latency_ms
  - ttft_p50_ms
  - ttft_p95_ms
```

### 5. training contamination guard を QDoRA 用にも拡張する

QDoRA 実験は LoRA より表現力が高い可能性があるため、評価漏洩への感度も上げる。

必須条件:

- training loader は `raw_dialog` training view のみ読む。
- `metrics.*` は常に reject。
- `metrics.individuation` poison row test を通す。
- `evaluation_epoch=true` は hard fail。
- `individual_layer_enabled=true` は hard fail。
- Social-ToM scenario output は training manifest に入らない。
- `reasoning_trace` を使う場合は用途を明記し、評価 rubric や judge score を含めない。

## M12+ QDoRA spike 提案

タスク名案:

```text
2026xxxx-m12-peft-ablation-qdora
```

目的:

QDoRA が ERRE の persona base retention と社会的行動一貫性を、現行 QLoRA-LoRA baseline より
改善するかを、同一 dataset・同一 seed・同一評価 pipeline で比較する。

### 前提 gate

以下が満たされるまで QDoRA spike は開始しない。

- M10-0 individuation metrics が実装済み。
- Social-ToM harness の最小 probe がある。
- M9/M10 の QLoRA-LoRA baseline が 1 persona 以上で採取済み。
- training contamination guard が `metrics.individuation` を reject 済み。
- SGLang が未 merged DoRA adapter を load できるか、または代替 serving path が明文化されている。
- QDoRA 実験に使う PEFT / transformers / bitsandbytes の version が lock されている。

### 実験 arm

最小構成:

| arm | config | 目的 |
|---|---|---|
| A | QLoRA-LoRA r=8, alpha=16, NF4 | 現行 baseline |
| B | QLoRA-rsLoRA r=8, alpha=16, NF4 | scaling 安定化の差分 |
| C | QDoRA r=8, alpha=16, NF4 | DoRA 効果の主比較 |
| D | QDoRA r=4, alpha=8, NF4 | 低 rank で LoRA を上回るか |
| E | QDoRA r=8 all-linear, NF4 | 容量増加の上限確認 |

オプション:

- LoftQ initialization
- PiSSA initialization
- 8-bit LoRA fallback

ただし初回 spike ではオプションを増やしすぎない。

### 採用 gate

QDoRA を採用候補に上げる条件:

- DB9 の 2-of-3 quorum で QLoRA-LoRA baseline を上回る。
- `self_rep > 0.15` または `cross_echo > 0.15` が出ない。
- `cognitive_habit_recall_rate` と `action_adherence_rate` が baseline を下回らない。
- Social-ToM probe で誤信念・情報非対称への応答が悪化しない。
- peak VRAM が 16GB 予算を超えない。
- train throughput 低下が baseline 比 25% 以内。
- adapter load / swap latency が ERRE tick budget を壊さない。
- SGLang runtime で adapter direct-load、または運用可能な変換手順がある。

QDoRA を不採用にする条件:

- 評価 metric は上がるが Social-ToM が悪化する。
- Burrows/Big5/Vendi のどれか単一 metric だけが上がり、行動 channel が改善しない。
- merged model でしか動かず、multi-persona adapter swap と両立しない。
- training contamination guard を緩めないと実験できない。
- M9/M10 の local runtime 予算を壊す。

## 推奨ロードマップ

### M10-0

- individuation metrics
- `metrics.individuation`
- `AnalysisView`
- contamination poison row test
- thresholds preregistration
- Social-ToM 最小 spec

### M10-A / M10-B

- persona/source checklist
- `PhilosopherBase` / `IndividualProfile` の validation 方針
- prompt ordering contract
- source provenance discipline

### M11

- Social-ToM harness 実走
- counterfactual challenge protocol
- multi-individual same-base validation
- narrative / world model persistence の観測

### M12+

- QLoRA-LoRA baseline 再採取
- QDoRA ablation
- serving compatibility spike
- PEFT registry formalization
- preference/RL は QDoRA より後

## 最終判断

QDoRA は ERRE にとって「やる価値のある実験」だが、
「今すぐ採用すべき本線」ではない。

ERRE の本質的なリスクは、FT 手法の不足ではなく、
**人格・個体化・社会性の改善を、重み更新から独立して測れるか**にある。
ここを先に固めれば、QDoRA はかなり良い比較候補になる。
逆にここを飛ばすと、QDoRA は単に強い role-play adapter を作るだけで、
ERRE の研究仮説を前に進めない。

採用順序:

1. M10-0 evaluation expansion
2. Social-ToM / counterfactual protocol
3. QLoRA-LoRA baseline freeze
4. QDoRA ablation
5. M12+ で採否判断

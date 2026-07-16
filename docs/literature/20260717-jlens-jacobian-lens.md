# 文献カード: J-lens（Jacobian lens）/ Verbalizable Representations Form a Global Workspace in Language Models

> **カード目的**: aha!/DMN-ECN forward roadmap（`project_aha_dmn_ecn_forward` /
> `.steering/20260713-aha-dmn-ecn-forward/`）の **Phase 3 前段 = J-lens scoping spike**。Anthropic の J-lens
> （Jacobian lens、2026-07-06 OSS）を、Phase 2 §(b) で設計した **二相捕捉 regime の候補 instrument** として採用してよいか
> を判定する doc-only spike の一次情報カード。「J-lens が *何を測るか* / J-space の主張 / global workspace theory 接続 /
> 検証 / 限界」を落合フォーマットで確定し、末尾 constraint-audit 節（software repo [26]）で採否判断の技術前提を整理する。
>
> 出典 SSOT = `docs/references.md`（本カードで [25]（論文）+ [26]（software repo）を append）。索引 = `docs/literature/_index.md`。

---

## ⚠️ over-read guard（本カードに優先する不可侵条項）

- 本カードは **doc-only**。**J-lens を走らせない・実 spend なし・measurement を authorize しない**。R-budget=0 / holding /
  凍結 measurement-line は door を明示的に開けるまで不変（`project_m13_post_cproper_disposition`）。
- **J-lens は本質的に「内部状態の定量読み出し（measurement-grade）」instrument** である。これを aha/二相の **scorer** に
  用いるのは Phase 2 §(b) over-read guard 原則5（neural ROI → 内部軌跡の比喩写像禁止）に抵触し、door② を勝手に開ける
  行為に相当するため **禁止**（採否判定は fork ADR、door-open は user 裁定）。
- J-lens の neural / global-workspace 用語（"workspace" "broadcast" "reportable"）は **Claude 系 proprietary モデルの
  内部機構に対する主張**であり、ERRE の DMN/ECN スペクトル（sampling params 上の暗黙軸）への構造的類推は **実証的架橋が
  存在しない**。この非対称は fork ADR で load-bearing に扱う。

---

# (A) 論文カード — [25] Verbalizable Representations Form a Global Workspace in Language Models

- **日付**: 2026-07-17
- **トピック**: jlens-jacobian-lens
- **出典**: [25] (docs/references.md)
- **key**: URL:https://transformer-circuits.pub/2026/workspace/
- **公開**: 2026-07-06 / Anthropic（transformer-circuits.pub） / 著者順・§4 検証モデル名/バージョンは公開前に原典再確認（citation-ssot 規則6）

### 1. それはどんなもの?
言語モデルの中間層 activation を、**平均 Jacobian**（`J_ℓ = E_{t, t'≥t, prompt}[∂h_final,t' / ∂h_ℓ,t]`、〜1000 の
pretraining-like prompt と source/subsequent 位置で平均）で出力空間へ transport し、`lens(h_ℓ) = softmax(W_U·norm(J_ℓ·h_ℓ))`
で語彙 token のランク付きリストへ decode する interpretability 手法（**J-lens = Jacobian lens**）。単一 context で verbalize
された表現でなく「**verbalize され得る（poised to be spoken about）**」表現を平均によって分離する。この J-lens ベクトルの
疎な **subframe**（proper subspace でなく非直交な張り = cone union）を **J-space** と呼び、モデルが「言い得るが必ずしも
言わない」概念を silent に保持する内部ワークスペースだと主張する。

### 2. 先行研究と比べてどこがすごい?
**logit lens**（J_ℓ=I の特殊系）は早層で noise が乗るが、J-lens は層間の表現ずれを Jacobian で補正するため **早層でも
解釈可能な内容を回収**する（最終数層では両 lens はほぼ一致）。**tuned lens**（相関目的で層別線形写像を学習）は「出力へ
skip ahead する」傾向で中間表現を surface せず、著者はどちらの lens より有用でないと報告。**SAE**（多数 activation → feature）
と違い、J-lens ベクトルは「モデルが実際に *report し得る* verbalizable 概念」だけを singling out する superposition 下の
subframe と位置づける。

### 3. 技術や手法の肝はどこ?
**「平均線形化影響（averaged linearized effect）」= future token への平均 Jacobian** が肝。(i) 1 文脈の逐語出力でなく
コーパス平均で「発話ポテンシャル」を定義することで verbalizable/verbalized を分離、(ii) J-space が持つとされる 5 性質
（reportability / directed modulation / internal reasoning mediation / flexible generalization / selectivity）を global
workspace theory の機能的性質に対応づける。J-space は総 activation variance の **10% 未満**（層により変動）、同時に有意味な
のは **≤25 本の J-lens ベクトル**（blog の「数十概念」表現に対応するが、厳密には概念数でなく **J-lens ベクトル数**）という
「小さな共有チャネル」主張。

### 4. どうやって有効だと検証した?
proprietary **Claude Sonnet 4.5 / Haiku 4.5 / Opus 4.5・一部 Opus 4.6** 上での causal 介入群:
- **Read（swap）**: J-lens ベクトル swap が出力を確実に変える（カテゴリ swap 88%、two-hop 中間 60–70%）。
- **Write/Inject**: steering で概念を reportable 化、ablation で抑制。J-space 成分は variance の 6–7% しか持たないのに
  swap 成功の 59–88% を駆動（非 J-space 残差は 〜5%）→ **selectivity / control** の証拠。
- **Directed modulation**: 「柑橘に集中せよ」等の明示指示で標的概念が J-space に賦活。
- **Internal reasoning**: 中間 J-lens ベクトル swap（spider↔ant 等）が最終解を 60–70% で変え、多段中間が層順に surface。
- **Selectivity**: 言語同定は連続/異常検出/明示報告で等しく J-lens に現れるが、swap は report と柔軟推論のみに効き、
  自動処理には効かない。

### 5. 議論はあるか?
著者自身が明記する限界: (i) **J-lens は単一 token に対応する概念しか同定しない**（多 token 概念は取りこぼす、拡張は言及のみ）、
(ii) **"imperfect tool, only approximately and incompletely captures the model's underlying workspace structure"**、
(iii) 早層の J-lens 内容欠如は「真の不在」か「J-lens degeneracy」か区別不能、(iv) 脳の recurrent 結合や encapsulated
processor 競合とは非対応（broadcast は単一 feedforward pass 内）、(v) **何が J-space に入るかを決める機序は不明**。加えて
global workspace theory への対応は機能的類推であり「Claude が意識を持つ/感じるかは何も言わない」と留保。
→ **ERRE 文脈での含意**: J-space は Claude 系での主張で、**本論文・公式 reference repo の範囲では qwen3:8b は未検証**
（第三者実装は範囲外）。DMN/ECN 二相への写像は論文が張らない架橋であり、over-read guard 原則5 が禁じる比喩写像に該当する。

### 6. 次に読むべき論文は?
Farrell, L. et al. — *Jacobian Sparse Autoencoders: Sparsify Computations, Not Just Activations*（arXiv:2502.18147, 2025）。
J-lens が依拠する「Jacobian で *計算* をスパース化する」系譜の先行手法で、SAE との関係（活性でなく計算のスパース化）を
J-space subframe 主張の背景として補完する（本カードでは登録外、Phase 3 以降で必要時に追加）。

---
## やり残し (1 行)
> J-lens は **measurement-grade（内部状態の定量読み出し）** であり、二相捕捉 regime（§(b) は think=True *text trace* の
> 質的 existence 観察用）に fold すると regime の性質を「質的 existence」→「定量内部読み出し」へ変質させる。加えて
> qwen3 未検証・白箱 backward-pass 必須ゆえ、採否は fork ADR で guard-first に判定する（この spike の主対象）。

---

# (B) software repo カード — [26] anthropics/jacobian-lens（制約 audit の技術前提）

- **出典**: [26] (docs/references.md) / **key**: URL:https://github.com/anthropics/jacobian-lens
- **License**: **Apache-2.0**（GitHub LICENSE 明記 "Code is released under the Apache License 2.0"）
- **Framework / 白箱要件**: **PyTorch + HuggingFace transformers**。`hf = transformers.AutoModelForCausalLM.from_pretrained(...).cuda()`
  の白箱 load を前提に、**全層 hidden state への hook + 入出力 Jacobian（backward pass）が必須**（"The transport is the
  average input–output Jacobian over a text corpus"）。→ 現行 organ の **Ollama 推論（inference-only、activation 非露出）とは
  別経路**。
- **対応モデル**: HF decoder（README "Examples use Qwen" / "other HuggingFace decoders adapt cleanly"）。**Qwen3 の明示
  言及なし**。pre-fitted lens は `JacobianLens.from_pretrained("org/lens-repo")` で org 依存（qwen3:8b は自前 fit 要）。
- **依存**: transformers / torch / numpy / **huggingface_hub**（`pip install -e .`、pyproject）。→ 白箱 transformers 直依存は
  `reference_wsl_transformers_sglang_conflict`（sglang pin と両立不可）に抵触。
- **GPU/VRAM**: 明示文書なし。ただし README "**fitting time is dominated by the model's own backward pass**"、"This is a
  reference implementation and is not optimized"、fit は "1000 sequences of 128 tokens"。→ qwen3:8b は inference-only で既に
  fp8 綱渡り（`reference_qwen3_sglang_fp8_required`）、backward pass は activations 保持で更に重く **16GB fit は重大リスク・
  desk inconclusive**。
- **Cloud 依存**: **なし（完全ローカル・API key 不要）**。Neuronpedia hosted デモ（open-weights 上、neuronpedia.org/jlens）は
  *任意* であって OSS 実装は self-contained → budget-zero 適合（Neuronpedia 依存を採る場合のみ cloud 抵触）。ただし
  **model weights / lens / corpus は repo に bundled されず事前 cache/取得が要る**（実行時 API は不要だが取得経路は要考慮）。
- **成熟度**: **"Reference implementation. Not maintained and not accepting contributions."** release/version tag なし、
  open issue/PR 各 3、star 〜1.4k。→ API 安定性リスクあり（Apache ゆえ vendor/fork は可能）。

---
> 出典は `docs/references.md` に append-only 登録（[25] 論文 / [26] software repo）。
> カードの 6 項目フォーマットは `.claude/skills/literature-card/` が強制する。

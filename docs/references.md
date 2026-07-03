# 参考文献 (References)

中央書誌 SSOT。設計書・実験ノートの本文 `[n]` はここを参照する。
採番は **append-only**。番号は **恒久 ID** (表示順ではない)。削除は **tombstone**、再利用禁止。
重複登録防止キー: DOI / arXiv ID / 正規化 URL。

> ⚠️ **引用前の原典再確認**: 下表の初期エントリは進行済みプロジェクトの記録・記憶からの
> 再構成 (recall) であり、DOI / arXiv ID / 巻号は **正式引用 (論文・公開物) の前に原典で
> 必ず再確認**すること。確認済みの行は「状態」を `active` のまま保持し、未確認の疑いが
> ある行は備考にその旨を残す。

| [n] | key (DOI/arXiv/URL) | 著者・タイトル | 出典・年 | 使用箇所 | 状態 |
|---|---|---|---|---|---|
| [1] | DOI:10.1037/a0036577 | Oppezzo, M. & Schwartz, D. L. — *Give Your Ideas Some Legs: The Positive Effect of Walking on Creative Thinking* | J. Exp. Psychol. LMC, 40(4), 1142–1152, 2014 | research-positioning §1/§3/§4/§7 | active |
| [2] | arXiv:2304.03442 | Park, J. S. et al. — *Generative Agents: Interactive Simulacra of Human Behavior* | arXiv, 2023 | research-positioning §3/§4; glossary (Memory Stream) | active |
| [3] | arXiv:2309.02427 | Sumers, T. R. et al. — *Cognitive Architectures for Language Agents (CoALA)* | arXiv, 2023 | research-positioning §3; glossary (CoALA) | active |
| [4] | arXiv:2411.00114 | AL et al. (Altera) — *Project Sid: Many-agent simulations toward AI civilization* | arXiv, 2024 | research-positioning §3/§4; glossary (PIANO) | active |
| [5] | DOI:10.1093/llc/17.3.267 | Burrows, J. — *'Delta': a measure of stylistic difference and a guide to likely authorship* | Literary and Linguistic Computing, 17(3), 267–287, 2002 | research-positioning §3; glossary (Burrows Δ) | active |
| [6] | DOI:10.1371/journal.pone.0347878 | Thabane, A. et al. — *The impact of walking on creative thinking: A systematic review and meta-analysis* | PLOS ONE, 21(5), e0347878, 2026 | research-positioning §3/§7 | active |
| [7] | DOI:10.3758/s13428-020-01453-w | Beaty, R. E. & Johnson, D. R. — *Automating creativity assessment with SemDis: An open platform for computing semantic distance* | Behavior Research Methods, 53(2), 757–780, 2021 | docs/literature/20260702-divergent-thinking-benchmarks.md | active |
| [8] | DOI:10.1073/pnas.2022340118 | Olson, J. A., Nahas, J., Chmoulevitch, D., Cropper, S. J. & Webb, M. E. — *Naming unrelated words predicts creativity* | PNAS, 118(25), e2022340118, 2021 | docs/literature/20260702-divergent-thinking-benchmarks.md | active |
| [9] | DOI:10.1037/a0027373 | Hills, T. T., Jones, M. N. & Todd, P. M. — *Optimal Foraging in Semantic Memory* | Psychological Review, 119(2), 431–440, 2012 | docs/literature/20260702-divergent-thinking-benchmarks.md; research-positioning §3 | active |
| [10] | DOI:10.1038/s41562-018-0467-4 | Wu, C. M., Schulz, E., Speekenbrink, M., Nelson, J. D. & Meder, B. — *Generalization guides human exploration in vast decision spaces* | Nature Human Behaviour, 2, 915–924, 2018 | docs/literature/20260702-divergent-thinking-benchmarks.md | active |
| [11] | DOI:10.1093/brain/awae199 | Bartoli, E. et al. — *Default mode network electrophysiological dynamics and causal role in creative thinking* | Brain, 147(10), 3409–3425, 2024 | docs/literature/20260702-divergent-thinking-benchmarks.md | active |

## 追加・撤回ルール

1. 新規文献は末尾に次番号で追加する (既存番号を振り直さない)。
2. 撤回時は行を残し「状態」を `tombstone` にする。番号は再利用しない。
3. 同一文献の二重登録は key 列 (DOI / arXiv / 正規化 URL) で検出して防ぐ。
4. 正式公開前に全 `active` 行の書誌情報 (DOI / arXiv / 巻号 / 著者順) を原典で再確認する。

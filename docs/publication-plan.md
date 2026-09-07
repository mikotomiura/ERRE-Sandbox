# 論文化プラン (Springer Nature)

> 対象 = ERRE-Sandbox の **計測方法論**を主張とする 1 本目の論文。
> 科学的中身 (問い・仮説・verdict) の SSOT は `docs/research-positioning.md`。
> 本ファイルは **投稿戦略と手順のみ** を持つ。命題・数値の再掲はしない (SSOT 二重化の禁止)。
> 調査日: 2026-09-06。APC・制度は変わるので投稿直前に再確認すること。

## 1. 前提の訂正 (調査で覆った点)

- **Nature Machine Intelligence は presubmission enquiry を一切受け付けない** (公式明記)。
  「まず NMI に照会を投げる」という当初案は撤回。
- NMI / Nature Human Behaviour の APC = **£9,390 / $12,850 / €10,850**。予算的に非現実。
- NHB の presubmission は Review/Perspective/How To に限定、Comment/Correspondence/Research は不可。
- 日本は SN の所得ベース自動 waiver 対象外。**ZEN University は SN の日本 transformative agreement
  機関一覧に不在** (2026 の OASE consortium 会員名簿は未確認 → 要照会)。
- SN の individual waiver は **投稿時のみ申請可**。投稿後の遡及申請は不可。忘れると詰む。
- arXiv preprint は Nature Portfolio 全誌で明示的に許容 (投稿資格を損なわない)。

## 2. 決定的な発見 — 近接論文が既に 2 本ある

| 論文 | 誌 | DOI |
|---|---|---|
| Larooij & Törnberg (2025) *Validation is the central challenge for generative social simulation: a critical review of LLMs in agent-based modeling* | Artificial Intelligence Review | 10.1007/s10462-025-11412-6 |
| Tomašević et al. (2026) *Towards operational validation of LLM-agent social simulations* | EPJ Data Science | 10.1140/epjds/s13688-026-00674-x |

含意は 2 つ。**(a) 投稿先が実在することの最強の証拠**。scope 文の解釈より強い。
**(b) 「検証が難しい」という主張自体はもう新規ではない**。

→ したがって delta を狭める。主張は「validation is hard」ではなく
**「循環性の具体的機序を数値で示し、それを事前に止めるゲートを装置として事前登録した」**。
Larooij & Törnberg は critical review であって apparatus を持たない。そこが空いている。

## 3. 論文の主張 (1 文)

> 埋め込みベースの新規性スコアラは、生成元モデル自身の anchor を認識しているだけであり、
> leave-anchor-out audit をかけると崩壊する。ゆえに生成エージェントの創発/創造性の主張は、
> スコアラ妥当性を非循環に事前検証するゲートなしには成立しない。本稿はそのゲートを
> 事前登録された verdict 語彙と scorer candidate ladder として実装し、実際に発火させた。

## 4. ERRE-Sandbox の「どこを書くか」

### 4.1 中核 = Table 1 (scorer candidate ladder)

出典 `experiments/20260701-es4-scorer-diag/diagnostic.json`。これが論文の心臓部。

| candidate | gold AUC (full) | gold AUC (leave-anchor-out) | adversarial AUC | rarity_ok |
|---|---|---|---|---|
| C0-mpnet-max-full (incumbent) | 0.99 | **0.755** | 0.158 | false |
| C1-mpnet-mean-full | 0.555 | 0.43 | 0.176 | false |
| C0-mpnet-max-full-lenctrl | 0.6575 | **0.275** | 0.213 | false |
| C5-jaccard-full | — | — | — | true (ただし entropy 還元可能) |

読み筋: gold ラベルに対し AUC 0.99 を出すスコアラが、anchor を抜くと 0.755 に落ち、
adversarial では 0.158 (= 逆張り)。**測っていたのは novelty ではなく anchor membership**。
候補ラダー全体が同じ壁で落ちることが「たまたま実装が悪かった」を排除する。

### 4.2 併せて書く証拠

- **ES-4 Phase 0 sealed run**: verdict `INVALID_SCORER`
  (a1 min AUC 0.500 < floor 0.8 / a2 held-out residual ΔDQ CI_lower −0.0083 ≤ 0)、
  n_clusters=48、n_aut_generations=2240。出典 `experiments/20260630-es4-phase0/verdict-phase0.json`
- **offline diagnostic**: `NO_VALID_SCORER`、候補ラダー全滅
- **事前登録 verdict 語彙 5 語** (`PASS` / `INCONCLUSIVE_UNDERPOWERED` / `INVALID_SCORER` /
  `INVALID_TASK_BATTERY` / `NO_GO_EFFECT_ABSENT`) と、**apparatus-invalid を low power と
  混同しない**規律 — これが方法論寄与の本体
- **ES-2**: JS divergence は非飽和を達成したが全 64 seed で d_obs<d_self →
  metric artifact ではなく真の低検出力、と峻別した手続き
- **D0 structural track**: `NO_STRUCTURAL_FLOOR`、median(Δ_1)=0.0、64 seed 中 63 が exact zero。
  および **anti-collapse gate** の設計 (R1 が R0 を黙って再測定する偽 GO の封鎖)
- **再現性**: `experiments/<YYYYMMDD>-<name>/` 規約、seed 固定、`uv.lock` 凍結、
  `repro.sh` の byte-parity、凍結 apparatus (`src/erre_sandbox/evidence/`) の不変性

### 4.3 **書かないもの** (これが同じくらい重要)

| 削るもの | 理由 |
|---|---|
| 偉人ペルソナ / 3D / Godot / MR / Blender | 査読者の攻撃面が増えるだけで主張に一切寄与しない。全カット |
| ERRE モード (守破離・茶室・座禅) の認知科学的正当化 | 同上。カット |
| Oppezzo / 歩行→拡散的思考の warrant | **導入 1 段落に落とす**。厚く書くと「身体性の論文」に見えて即死 |
| 中核命題 H0 / ES-1 / ES-3 の GO | 付録に 1 段落。conformance であって効果ではない、と明記 |

**Introduction は歩行の話から始めない。**「創発主張が測定妥当性ゲートを持たない」から始める。

### 4.4 仮タイトル

> Novelty scorers recognize their own anchors: a leave-anchor-out audit and a preregistered
> verdict protocol for emergence claims in LLM agent simulations

## 5. 投稿前に埋めるべきギャップ

### G1. 外的妥当性 — **最重要・最大の穴** (2-3 週)

現状は単一 apparatus・qwen3:8b 単体・単著。「あなたのコードベース内だけの話では?」に返す弾がない。

最小の解決 = **公開実装 1 つ** (Generative Agents / Concordia / GPTeam 等) の出力に
**同じ leave-anchor-out audit をかけ、同じ崩壊が再現するか**を示す。
1 本でも外部データが乗れば、論文の性格が「自分の失敗談」から「分野の性質」に変わる。

`experiments/<date>-external-audit/` で **事前登録してから実走**。
再現しなかった場合は主張を「ERRE apparatus 固有」に正直に縮退させる (two-sided guard をここにも適用)。

### G2. Related work — 計測妥当性側がほぼ空 (1-2 週)

`docs/references.md` は 26 件、大半が認知神経科学側。方法論論文を名乗る以上ここが空なのは致命的。
`citation-ssot` skill で append-only 登録、`literature-card` で必須文献をカード化。

**必須 8 本 (これを欠くと「自分の分野を知らない」と判定される)**

1. Schaeffer, Miranda, Koyejo — *Are Emergent Abilities of LLMs a Mirage?* NeurIPS 2023, arXiv:2304.15004
   — 「メトリクス選択が創発の見かけを生む」= 本稿と同型の議論構造。絶対に必要
2. Wei et al. — *Emergent Abilities of Large Language Models* TMLR 2022, arXiv:2206.07682 — 批判対象の原典。1 と対で引く
3. Panickssery, Bowman, Feng — *LLM Evaluators Recognize and Favor Their Own Generations* NeurIPS 2024, arXiv:2404.13076
   — **自己認識循環性の直接的先行研究。本稿の中核主張の出典**
4. Jacobs & Wallach — *Measurement and Fairness* FAccT 2021, DOI:10.1145/3442188.3445901 — construct validity 語彙の出典
5. Bean et al. — *Measuring what Matters: Construct Validity in LLM Benchmarks* NeurIPS 2025, arXiv:2511.04703 — 445 本の妥当性欠如の実証
6. **Vaccaro — *Preregistration for Experiments with AI Agents* ICML 2026 Spotlight, arXiv:2606.11217**
   — 本稿の立場と完全一致する同時代文献。**これを引かないと車輪の再発明に見える。最優先で読む**
7. Organisciak et al. — *Beyond Semantic Distance* Thinking Skills and Creativity 2023, DOI:10.1016/j.tsc.2023.101356
   — 意味距離ベース創造性スコアの限界
8. Chakrabarty et al. — *Art or Artifice?* CHI 2024, DOI:10.1145/3613904.3642731
   — LLM 出力の新規性が専門家評価と埋め込み評価で乖離する

加えて §2 の Larooij & Törnberg / Tomašević は **positioning のために必ず引く** (差分を明示する対象)。
補助: Card et al. *With Little Power Comes Great Responsibility* EMNLP 2020 (低検定力)、
Kapoor & Narayanan *Leakage and the Reproducibility Crisis* Patterns 2023, DOI:10.1016/j.patter.2023.100804。

### G3. 内部語彙の接地 (3 日)

`bounded close` / `NO_STRUCTURAL_FLOOR` / `anti-collapse gate` / `two-sided guard` は全部自作語。
construct validity / convergent-discriminant validity / researcher degrees of freedom /
statistical power / preregistration に翻訳する **対応表を 1 つ作る**。
これがないと査読者は本文に入る前に降りる。

### G4. arXiv preprint (1 日)

SN は preprint を明示許容。先に出して引用可能状態にし、反応を取る。

## 6. 投稿先 (優先順)

| 順 | 誌 | APC | 根拠 |
|---|---|---|---|
| 1 | **EPJ Data Science** | £1,340 / $1,990 | Tomašević が同型。scope に generative language models を明記。最安帯。**本命** |
| 2 | **Artificial Intelligence Review** | $3,390 | Larooij & Törnberg が同型。"critical evaluations" を scope に明記。フル OA |
| 3 | Humanities and Social Sciences Communications | 要直接確認 (公式ページ 404) | 初回判定中央値 16 日。AI agent 論文の掲載実績あり |
| 4 | npj Artificial Intelligence | $2,690 | Zomer & De Domenico (2026) が近接。ただし新設誌で引用文化未確立 |
| — | Scientific Reports | $2,850 | negative results collection は存在するが、方法論論文としては埋没する |
| — | NMI / NHB | $12,850 | APC 非現実 + presubmission 不可 + 単著無所属。今回は見送り |

**別ルート — Registered Report**: Scientific Reports が全分野に Stage 1/Stage 2 を開いている。
**G1 の外部監査を Stage 1 で事前登録し in-principle acceptance を取る**手がある。
結果が再び `NO_VALID_SCORER` でも出版される。この研究の性格に制度として最も合う。要検討。

## 7. 手順 (順番厳守)

| # | やること | 期間 |
|---|---|---|
| 0 | ORCID 取得 (corresponding author 必須)。所属欄の方針決定 (Independent Researcher / ZEN University)。OASE consortium に ZEN University が含まれるか照会 | 今週 |
| 1 | G2 文献埋め。`citation-ssot` で `references.md` に append、必須 8 本を `literature-card` 化 | 2 週 |
| 2 | G1 外部監査。事前登録 → 実走。再現しなければ主張を縮退 | 2-3 週 |
| 3 | G3 語彙対応表 + Table 1 確定 | 3 日 |
| 4 | 初稿 4,000-4,500 語 | 2 週 |
| 5 | Codex (gpt-5.5 / xhigh) independent review。HIGH 全反映 (既存 `.steering/` フロー流用) | 3 日 |
| 6 | arXiv 投稿 → 1-2 週反応待ち → **EPJ Data Science** 投稿 (waiver 申請は投稿時に同時) | — |
| 7 | reject 時 → Artificial Intelligence Review → HSSC | — |

## 8. リスク

- **G1 で外部再現が出ない**: 主張を apparatus 固有に縮退させ、Discover Artificial Intelligence
  ($1,690) に落とす。無理に一般化しない。
- **単著・無所属は desk reject 率を上げる**。共著者が 1 人つけば EPJ / AI Review の通過確率は
  明確に上がる。Step 1 と並行して打診する。**技術的準備よりリターンが大きい**。
- **APC**。EPJ DS $1,990 でも自腹なら重い。waiver は投稿時同時申請でしか出せない。

## 9. 未検証事項 (投稿前に潰す)

- HSSC / Discover series の現行 APC (公式ページが 404、第三者集計のみ)
- SN の individual hardship waiver の適用可否 (学生・個人が対象になるか)
- 2026 OASE consortium (日本、約 83 機関) に ZEN University が含まれるか
- HSSC / Discover の Registered Report 取扱いの有無
- 無所属著者の affiliation 欄の公式方針 (公式文書が見つからず)
- `docs/references.md` の初期エントリの DOI/巻号 (同ファイル冒頭の警告どおり、正式引用前に原典再確認)


## 10. 運用 — ERRE-Sandbox をオーケストレータにする (2026-09-07 決定)

論文 01/02 は独立リポジトリへ分離した (`C:\ERRE-Papersnchor-recognition-not-novelty` /
`powered-null`)。**分離は維持しつつ、道具はすべて ERRE-Sandbox 側から回す。**

### なぜ分離を畳まないか

paper repo は **PUBLIC**、ERRE-Sandbox は非公開 (OSS 公開 Phase 2-6 未了)。
物理的に分かれていることが「公開 repo に `.steering/` が入らない」の**構造的保証**になる。
同一ツリーに置いて `.gitignore` で守るのは**方針による保証**への降格であり、
**論文 01 の主張 (方針だけでは守れない、装置で止めろ) と矛盾する**。

### ここ (ERRE-Sandbox) から回すもと

| やること | コマンド | 理由 |
|---|---|---|
| artifact の取り込み | `pwsh paper/gather.ps1` | 原本 (`experiments/` / `src/`) がここにある |
| **同期チェック** | `pwsh paper/gather.ps1 -Verify` | 原本↔コピーの SHA-256 突合。乖離/欠落で exit 1 |
| 書誌の追加 | `docs/references.md` に append-only (`citation-ssot` skill) | **書誌 SSOT は分離後もここ**。paper 側 `refs.md` は `[n]` と役割のみ |
| 新規論文の切り出し | `pwsh paper/move-out.ps1` | 既定は 01/02 (03 は独立化しない) |

### paper repo 側でやるもの

本文執筆 (`manuscript/`)、`CITATION.cff` の記入、`env/pyproject.toml` の削り込みと `uv lock`、
`repro.sh` を exit 0 にすること、そして **commit / push**。

### 守るべき 1 つの習慣

**`experiments/` の artifact を再生成した / 凍結 apparatus を触った直後は
`pwsh paper/gather.ps1 -Verify` を回す。** `data-hashes.md` は *記録* であって *検査* ではないので、
これを回さないと乖離に気づけない。

### 注意 — オーケストレートするのは「道具」であって「タスク」ではない

3 リポジトリ分の作業を 1 セッションに詰めると context が破綻する
(CLAUDE.md の 50% ルール / タスク切り替えは `/clear`)。
**セッションは従来どおりタスク単位で切り、道具の起点だけをここに集約する。**

### orchestration では解けない残件

`.steering/20260629-m13-es3-impl/verdict-forensic.json` (論文 02 の `D_loco=0.0468` の出典) は
**原本が gitignore 配下、コピーは未 push** ゆえ G-GEAR 上にしか存在しない。
これは同期の問題ではなく **backup の問題**。push するか別媒体へ退避するかのどちらか。

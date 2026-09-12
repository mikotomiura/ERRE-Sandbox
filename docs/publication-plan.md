# 論文化プラン

> 3 本すべての **投稿戦略と手順** の SSOT。命題・数値の再掲はしない (SSOT 二重化の禁止)。
> 科学的中身 (問い・仮説・verdict) の SSOT は `docs/research-positioning.md`。
> APC・制度は変わるので投稿直前に再確認すること。

## 0. このファイルの読み方 (2026-09-12 追記)

**§1-§9 は論文 01 (scorer circularity) を Springer Nature 系に単独投稿するための計画である
(調査日 2026-09-06)。その前提は 2026-09-09 に覆った。**

- 2026-09-09、論文 01 案 2 (scope condition) の実走が `DO_NOT_WRITE` を返し、
  **「01 は単独では出さない。結果とハーネスは論文 03 に畳む」**と確定した
  (`project_paper01_scope_condition` / `project_paper_track`)
- したがって **§6 (投稿先) / §7 (手順) は「01 単独投稿ルートの記録」**である。
  **削除しない** — APC 表・waiver の制約・Registered Report ルート・presubmission 可否は
  02 / 03 でも再利用できる調査結果であり、消すと同じ調査をやり直すことになる
  (`feedback_never_freeze_not_yet_run` と同じ扱い: 期限切れ記述は削除でなく事後版へ反転する)
- **現時点で生きている投稿計画は §11** (論文 02 / 03)。まずそちらを読むこと

| 論文 | 投稿ステータス (2026-09-12) |
|---|---|
| 01 scorer circularity | **単独投稿しない** (確定)。結果とハーネスは 03 に畳む |
| 02 powered-null | 数値は取得済・未執筆。投稿先は **未定** → §11.3 |
| 03 two-plane determinism | 実装済・未執筆。投稿先は **未定 (user 裁定)** → §11.1 / §11.2 |

---

# 【§1-§9】論文 01 単独投稿ルートの記録 (2026-09-06 調査 / 2026-09-09 に前提が覆った)

> **この範囲は履歴である。** 01 は単独投稿しないと確定した (§0)。
> 生きている計画は §11。§1-§9 を「現在の方針」として読まないこと。

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

## 6. 投稿先 (優先順) — **01 単独ルートの調査結果。現行方針ではない (§0)**

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

## 7. 手順 (順番厳守) — **01 単独ルートの手順。現行方針ではない (§0)**

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


---

# 【§10-§11】現行 (2026-09-12)

## 10. 運用 — ERRE-Sandbox をオーケストレータにする (2026-09-07 決定)

論文 01/02 は独立リポジトリへ分離した (`C:\ERRE-Papers\anchor-recognition-not-novelty` /
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

> **2026-09-11 追記 (解消済)**: 上記 JSON は `experiments/20260629-m13-es3-locomotion/verdict-forensic.json`
> として追跡下へ退避した (`.steering/20260911-ci-selection-ssot/decisions.md` DA-CIS-4)。
> 対になる人間可読版 `verdict-result.md` は未退避 (同 `blockers.md` B-CIS-3)。

---

## 11. 投稿先の判断材料 — 論文 02 / 03 (2026-09-12 調査)

> **本節は材料であって決定ではない。** 投稿先の確定は確定タイトルと同じく **user 裁定事項**
> (`paper/03-two-plane-determinism/PREP-STEPS.md` [D] / DA-P03-5 = DEFERRED)。
> 調査日 2026-09-12。一次情報の出典と確認方法を各行に明記した。

### 11.0 3 つの制約 (どのルートを選んでも効く)

**制約 1 — 同時複数投稿は不可。**
ほぼ全誌が "not under consideration for publication elsewhere" を投稿宣言として要求する
(SoftwareX の Guide for authors "Submission declaration" で一次確認)。
複数の機会を得る正当な方法は 2 つだけ:

1. **preprint を先に出す** (preprint は "prior publication" に当たらないと明記されている)
2. **順番を事前に決めた ladder で 1 誌ずつ**出す

**制約 2 — APC ゼロが user 制約 (2026-09-12 user 明示)。**
§8 も「自腹なら重い」と書いている。§11.2 に**全工程 APC ゼロで成立する ladder** を 1 本示す。

**制約 3 — arXiv は初回投稿に endorsement が要る。**
「arXiv requires that users be endorsed before submitting their first paper to arXiv or a new
category」(info.arxiv.org/help/endorsement で一次確認)。
所属メールが無い場合は **既存 arXiv 著者から個人 endorsement を得るしかない**。
自動 endorsement の仕組みは無い。**無所属の単著はここで実際に詰まりうる。**
→ **代替 (endorsement 不要)**:

- **Zenodo に preprint を上げて DOI を取る** (アップロードに endorsement も所属も不要)
- **SSRN** — SoftwareX は投稿時に **SSRN への無料 preprint 掲載**を選べ、
  **preprint DOI** が付く (Guide for authors "Preprints" で一次確認)。
  掲載可否は編集判断 (desk review 通過後) に依存する点だけ注意

### 11.1 論文 03 の投稿先候補 — JOSS vs SoftwareX

| 軸 | **JOSS** (Journal of Open Source Software) | **SoftwareX** (Elsevier) |
|---|---|---|
| 形式 | `paper.md` (**Markdown**) + `paper.bib` | **専用テンプレート必須** (Word または LaTeX の Original Software Publication)。他形式は受理されない |
| 語数 | **750-1750 語** (「1750 語を大きく超えると短縮を求められる」) | **4,000 語上限** の短い記述論文 |
| APC | **無料** ("There are no fees for submitting or publishing in JOSS") | **USD 1,920** (excl. taxes)。waiver は **Research4Life 対象国のみ** = 日本は対象外 |
| 審査対象 | **リポジトリそのもの** (GitHub 上で公開レビュー) | 論文 + 公開リポジトリ。受理版のコードは**誌の GitHub へ複製保管**される |
| 必須節 | Summary / Statement of need / **State of the field** / **Software design** / **Research impact statement** / **AI usage disclosure** | Highlights (3-5 点・各 85 字) / graphical abstract / abstract 250 語 / code metadata 表 / data statement |
| 研究データ | — | **Option C**: データを repository に deposit し、論文から cite + link する (= **Zenodo DOI が実質必須**) |
| preprint | 可 | 可。**SSRN 無料 preprint + DOI** を投稿時に選べる |
| ライセンス | OSI 承認 OSS が必須 (本 repo = Apache-2.0 OR MIT で充足) | CC BY / CC BY-NC / CC BY-NC-ND から選択 |
| 生成 AI | **AI usage disclosure が必須節** | **Declaration of generative AI use** が必須 (本文末尾に節を立てる) |

出典: JOSS = `joss.readthedocs.io` の submitting / review_criteria / paper (2026-09-12 取得)。
SoftwareX = ScienceDirect の Guide for authors / Open access information (同日取得、APC は公式表)。

#### 03 の主張との適合・不適合

**prompt / 従来メモにあった前提を 1 つ訂正する。**
「JOSS はソフトウェアの記述であって新規研究主張の場ではない」は**半分だけ正しい**。
JOSS が禁じているのは *"Your paper must not focus on new research **results** accomplished
with the software"* であって、**software design の主張には `Software design` という必須節が
用意されている** ("the trade-offs you weighed, the design/architecture you chose, and why it
matters for your research application ... beyond a superficial code structure description")。

03 の delta 3 点 (`paper/03-two-plane-determinism/README.md` §2) との対応:

| delta | JOSS でどこに書くか | 収まるか |
|---|---|---|
| ① Plane 1 の決定化 (物理・RNG・時計・ID・スケジューラ順序) | `Software design` | ⭕ そのもの |
| ② OS 跨ぎ byte 一致の実証 | `Research impact statement` (reproducible materials) | ⭕ 実測値で書ける |
| ③ 量子化幅の数値的正当化 | `Software design` | ⭕ trade-off の説明として |

- **JOSS の有利**: APC ゼロ (制約 2 を満たす唯一の査読誌)。審査対象がリポジトリ本体なので、
  **本タスクで作った `REPRODUCING.md` + `docs/artifact-hashes.md` + 両 OS の CI がそのまま
  審査材料になる**。JOSS の `Research impact statement` は
  "realized impact (publications, external use, integrations) **or** credible near-term
  significance (benchmarks, **reproducible materials**, community-readiness signals)" を
  認めており、後者の弾がある
- **JOSS の不利・リスク (2 点、実測済)**:
  1. **公開 commit 履歴が短い。** JOSS の review criteria は
     "sustained development over time (preferably months or years)" / "6+ months" を挙げるが、
     本 repo の公開履歴は **2026-05-31 の単一クリーンコミット起点** (`4de3eb8`) で
     **約 3.5 か月** (2026-09-12 実測で 291 commits)
     (OSS 公開 cleanup Phase 4 で `rm -rf .git` したため)。**実際の開発期間より短く見える**。
     → 対処案: `docs/` と `experiments/` の日付連鎖 (2026-04〜) を Research impact statement で
     明示し、履歴短縮の理由を書く。**これは事前に潰しておく論点**
  2. **"evidence that the software is being used for research" を要求される。** 外部採用も
     被引用もまだ無い。弾は「reproducible materials」側のみ
- **SoftwareX の有利**: 語数 4,000 で余裕がある。二平面設計を丁寧に書ける。
  code metadata 表が本 repo の provenance pin と相性が良い
- **SoftwareX の不利**: **APC 1,920 USD が制約 2 に正面から抵触**。waiver 対象外。
  テンプレート (LaTeX/Word) 固定で Markdown 資産が使えない

### 11.2 APC ゼロで成立する ladder (制約 2 を満たす最低 1 本)

> **① は 2026-09-12 に完了した。** release `v0.0.1` (`main` = `555126b`) を Zenodo が拾い、
> **Concept DOI = `10.5281/zenodo.22718679`** / version DOI = `10.5281/zenodo.22718680` が発行済。
> `.zenodo.json` の著者メタデータ (Miura, Mikoto / Independent Researcher /
> ORCID 0009-0000-4196-0508 / Apache-2.0) もそのまま載った。**G2 = 達成。**

```
① Zenodo          GitHub release → DOI 発行       無料 / endorsement 不要 / 所属不要
       ↓  (これで artifact が永続参照可能になる = G2) ✅ 2026-09-12 完了
② preprint        arXiv (cs.SE / cs.MA)           無料。ただし endorsement が要る (制約 3)
                  └ 詰まったら Zenodo に preprint  無料 / endorsement 不要
       ↓
③ 査読誌          JOSS                            APC 無料
       ↓  (reject された場合のみ)
④ 次の段          SoftwareX 等 (APC 判断を user が下す)
```

- **①→②→③ の順序は入れ替えない。** JOSS も SoftwareX も受理時に archival DOI を要求し、
  SoftwareX は研究データの deposit + link を Option C として要求する。
  DOI を先に取っておけば両方に効く
- **② と ③ は同時進行してよい** (preprint は prior publication に当たらない)。
  ③ を 2 誌同時に出すのは制約 1 違反

### 11.3 論文 02 (powered-null) の投稿先 — **枠のみ。候補は未調査**

repo のどこにも 02 の投稿先が書かれていなかったので枠を作る。
**本タスクでは候補調査をしていない** (scope 外)。分かっていることだけを置く。

| 項目 | 状態 (2026-09-12) |
|---|---|
| 主張 | エージェント内部変調 → 下流離散選択のチャネルは、検出力を確保した設計の下で効果が検出されない |
| 数値 | **取得済** (`experiments/20260710-m13-c-proper/` ほか)。本文未執筆 |
| repo | `C:\ERRE-Papers\powered-null` (PUBLIC、commit `324d432`、**push 未実施**) |
| 残 gate | 2 個目のモデルでの再現 (`project_paper_track`) |
| 投稿先 | **未調査**。null result を正面から扱う誌を当たる必要がある。§6 の Registered Report ルート (Scientific Reports の Stage 1/Stage 2) は **02 にこそ効く** 可能性がある — 結果が null でも出版されるため |

### 11.4 次に潰すべき未確認事項

- JOSS の "Research impact statement" に対して、本 repo の弾 (reproducible materials) が
  十分と判断されるか — **pre-review issue を立てる前に JOSS の submission checklist を通す**
- SoftwareX の APC に対する institutional agreement の有無 (所属が付いた場合のみ意味がある)
- arXiv の endorser 候補の当て (無所属単著の最大のボトルネック)
- Zenodo の release 連携は **連携を有効にした後の release しか拾わない**ため、
  tag を切る前に repository を enable する順序を守ること (§G2 手順書)

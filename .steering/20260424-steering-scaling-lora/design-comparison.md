# Design Comparison — v1 vs v2

`/reimagine` 適用結果 (2026-04-24)。v1 は `design-v1.md`、v2 は `design.md` を参照。

## v1 (初回案) の要旨

tasklist.md にプリセットされた暫定採用 (ADR1=hybrid LoRA / ADR2=4th persona / ADR3=user-as-special-agent) をそのまま ADR 化するプラン。design.md は「ADR の書き方メタ」(~50 行) として位置付け、decisions.md に 5 節 ≤20 行で 3 ADR を書き下す流れ。MASTER-PLAN は M8 行追加と M9 前提追記。Plan agent 省略、/reimagine も省略。

## v2 (再生成案) の要旨

ADR の役割を "M8+ の意思決定材料" に厳格化。**architecture を先取り commit せず、M8 で何を計測したら commit 可能になるかを書く** 方針へ転回。選択肢の taxonomy を (a/b/c) から (a-f) に拡張し、ADR 2 と ADR 3 の交叉 (user as 4th agent) を明示。design.md を **substantive research repository** (~200 行) に格上げし、decisions.md は design.md を cite する ADR 集として薄くする。3 ADR の「次アクション」は M8 共通 preconditions (episodic log / baseline metric / session phase) に cross-reference することで M8 spike 起票粒度を一本化。User-IF は interface 選定ではなく方法論 (autonomy vs intervention) 問題として再フレーム、2-phase methodology (autonomous run + Q&A epoch) を採用。

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| ADR の時制 | "M8 で (c) hybrid LoRA 試作" = architecture 先取り | "M8 で baseline 計測、M9 まで architecture 判断 defer" |
| design.md の役割 | ADR 書き方メタ (~50 行) | substantive research repository (~200 行) |
| decisions.md の厚さ | 自己完結 (~60 行) | design.md 参照で薄く (~60 行、ただし evidence 外部化) |
| ADR 1 採用 | (c) hybrid LoRA 試作 | defer-and-measure (M9 まで判断先送り) |
| ADR 2 採用 | (a) 4th persona 補完 | observability-triggered (metric 閾値超過で +1) |
| ADR 3 採用 | (a) user-as-special-agent | (d) 2-phase methodology (time-separated epoch) |
| 選択肢の網羅 | (a/b/c) の 3 択 (tasklist 先入観継承) | (a-f) の 6 択 (RAG / 2 persona-set / pause-and-query 等を新規追加) |
| ADR 2-3 の交叉扱い | 独立 (scaling と user-IF は別問題) | 明示 (user を 4 体目として扱う案=両 ADR の交叉点として併記) |
| M8 preconditions | ADR ごとに個別列挙 | 3 ADR 共通の 3 件 (episodic log / baseline metric / session phase) に cross-ref |
| MASTER-PLAN M8 行 | "hybrid LoRA spike + 4th agent onboarding + user-dialogue IF contract" | "観察 → LoRA 判断の橋渡し spike" (判断素材収集が主) |
| 方法論的緊張 | 言及なし | §4 で「自律創発観察 vs 実験者介入」の矛盾を明示、A3-d 採用根拠に |
| 変更規模 | design.md 50 行 + decisions.md 60 行 ≈ 110 行 | design.md 200 行 + decisions.md 60 行 + comparison 50 行 ≈ 310 行 |
| リスク | architecture 先取り commit で M9 の選択肢を早期に縮退 | docs 量が増える (1-2h の時間制約を圧迫する可能性) |

## 評価 (各案の長所・短所)

### v1 の長所
- 軽量 (~110 行)、1-2h 見積に収まる
- tasklist.md の構造をそのまま使えるので執筆コスト最小
- 採用案が具体的 ((c)/(a)/(a))、M8 が何をすべきか明確に見える

### v1 の短所
- **architecture 先取り**: M9 の判断を M8 に前倒し、データ無しで LoRA の hybrid/full/none を選ぶ構造に。データが出た後に覆ると ADR 全体が再執筆対象に。
- **選択肢の貧困**: (a/b/c) しか検討せず、RAG / pause-and-query / 2-phase methodology 等の有力代替が視野から落ちている。
- **user-IF の方法論的盲点**: autonomous 研究姿勢との矛盾を扱わず、interface 選定問題に矮小化。
- **design.md の役割誤認**: requirement が明記する「調査結果を書き下ろす」を満たさない。

### v2 の長所
- **ADR が時間に対して堅牢**: defer-and-measure は新データで内容が "追加" されるだけで "棄却" されない。
- **選択肢網羅**: (a-f) で将来の第 2 選択肢が視野内にあり、M8 データ次第で採用転換の道筋が明確。
- **交叉の明示**: ADR 2-3 が実質同じ interface (4 体目 channel) を共有することを認識し、M8 spike の設計が一本化できる。
- **方法論整合**: autonomy claim の汚染回避が evaluation layer (M10-11) 設計と自然接続。
- **substantive design.md**: req.md の指示に沿う、将来のドリフト検知材料として残る。

### v2 の短所
- **docs 量 3 倍**: 1-2h 見積を圧迫。実測で 2.5-3h かかる可能性。
- **ADR の採用が抽象的**: "defer" / "observability-triggered" / "2-phase" は具体的 architecture を確定しないため、読み手には「結論を引き延ばした」印象も与えうる。
- **M8 spike の数が増える**: ADR 1 だけで 2 本 (`m8-episodic-log-pipeline` + `m8-baseline-quality-metric`)、全体で 4 本に膨張。
- **選択肢 taxonomy が調査的**: (a-f) の網羅は魅力だが、評価欄が主観になりがち。

## 推奨案

**v2 を採用** — 理由:

1. requirement.md 線 23-24 の明文指示 ("design.md に調査結果を書き下ろす") に v1 は違反、v2 は準拠。
2. ADR の目的が "M8+ 意思決定材料" (req.md 線 23) であるなら、architecture 先取り commit は目的に照らして逆機能。
3. v2 で拡張された選択肢 (A1-e RAG、A3-d 2-phase) は、v1 の (c)/(a)/(a) より **将来のデータで覆される可能性が低い**。堅牢性 > 即時具体性。
4. ADR 2-3 交叉の明示は「次セッションの M8 spike 起票」時に一本化効果が出る。v1 は別々に spike を立てて後で merge する手戻りを潜在。

ただし **v2 の短所への対処** を採用時に付帯:

- docs 量の圧迫 → design.md の §1 substantive facts は既に手元にあるため純執筆時間は短い (30-45min)。2h 以内に完走可能と見積もる。
- ADR の抽象度 → 各 ADR の「次アクション」で M8 spike task 名を具体的に列挙し、"defer" が骨抜きに見えないようにする。v2 ドラフトは既にこれを実装。

## 採用記録

- 採用: **v2**
- 採用日: 2026-04-24
- 採用者: 次の AskUserQuestion でユーザーが確定
- 根拠: 上記 "推奨案" の 4 点

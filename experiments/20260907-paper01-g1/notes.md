# paper01 G1 外部監査 — notes (issue 008: 実走と実験ディレクトリ一式)

## 検証する仮説

`docs/research-positioning.md` §5 の **H4** は on-task rarity 計測器 (embedding
rarity + leave-anchor-out audit) が `frozen apparatus` 下で非循環に建たなかった
(内部診断 verdict = `NO_VALID_SCORER`、`experiments/20260701-es4-scorer-diag/
diagnostic.json`) ことを「二重 bottleneck ①」として記述している。論文 01
(`anchor-recognition-not-novelty`) はこの内部崩落を「埋め込みベースの新規性
スコアラは生成元自身の anchor を認識しているだけ」という機序主張として書く。

本 issue (G1 = 外部監査) はこの機序主張が **ERRE の apparatus の外でも成り立つか**
を問う。H4 の効果 (locomotion actuator sufficiency) そのものを再検証するもので
はない — H4 とは別軸の、論文 01 の外的妥当性ゲート (`.idea/paper-01-writing-spec.md`
§7) である。生成過程が内部は qwen3:8b、外部は人間集団 (Cambridge / Ocsai の被験者)
という違いがあるため、`.steering/20260907-paper01-g1-external-audit/design-final.md`
§0.1 の対応表に従い、**「LLM が自分の anchor を認識している」ことを外部で示した
とは書かない** — 書けるのは「anchor 集合が採点対象と同じ生成過程から来るとき、
埋め込み rarity スコアラの見かけの判別力は LAO で崩れる (or 崩れない)」まで。

## 借用した apparatus / 出典 (無改変)

- `src/erre_sandbox/evidence/es4_actuator/**` (`constants` / `controls.auc` /
  `battery.AdversarialItem`) — 凍結。**本 issue でも touch していない**
  (`git status --porcelain` で pin、下記検証コマンド参照)。
- `scripts/es4_scorer_diag.py` — 凍結・read-only 再利用 (`make_encoder` /
  `embed_map` / `embed_rarity` / `jaccard_rarity` / `tfidf_rarity` /
  `Candidate` / `gold_good_vs_common` / `load_adversarial_labeled` /
  `load_common_uses`)。**本 issue でも改変していない**。
- `scripts/paper01_fetch_sources.py` (I-001) — Cambridge `.xlsx` パーサ /
  gold binarisation / Ocsai jsonl フェッチ。無改変。
- `scripts/paper01_external_audit.py` (I-002〜I-007 landed) — 事前登録定数 /
  §5 統計層 / §6 判定規則 / Cambridge・Ocsai アダプタ / §2 fidelity pin。
  **本 issue での変更は CLI 引数の追加 (`--audit-out`) と corpus status の
  対称化 (下記) のみ**。
- `experiments/20260701-es4-scorer-diag/diagnostic.json` (封印済 artifact) —
  §2 fidelity pin の比較先。再生成していない。

## corpus status の対称化 (本 issue、オーケストレータ裁定 DA-G1-28)

`results/external-audit.json` は元々 Ocsai ブロックにだけ `status` キー
(`"ok"` / `"source_unavailable"`) があり、Cambridge ブロックには無かった
(非対称)。`scripts/paper01_external_audit.py` の `run_cambridge_audit` に
`"status": "ok"` を追加して対称化し、`both_corpora_available()` (両 corpus の
`status` が `"ok"` かを見る新規の純粋関数) を追加した。`main()` の `--audit`
分岐はこの関数が `False` を返すと exit code 1 を返す — AC 008-7 (2 corpus
available でなければ G2 未達) は **`run.sh` の外側で新しい判定ロジックを
足すのでなく、この CLI の exit code に一本化**した。`source_unavailable` は
`VERDICT_ENUM` に含めていない (既存 `test_source_unavailable_is_not_a_verdict`
が pin、Codex HIGH-4)。

## TASK-POST cross-review 反映 (Opus HIGH-1/HIGH-2、MEDIUM 1-6、本セッション)

TASK-POST (`/cross-review`) の code-reviewer(Opus) 指摘 HIGH 2 件・MEDIUM 6 件
をすべて反映した (Codex は今回未実施)。**判定規則 (`decide_external`) ・floor・
アーム定義・対応付けは一切変更していない** — すべて「既に計算している値を
報告に出す」か「文書の記述を実測に合わせる」のどちらか。

- **HIGH-1 (§5.4 五つ組の外部露出)**: `potency_and_near_dup()` は
  `near_dup_good`/`near_dup_common` を返すのに `.potency` だけ取り出して
  外部経路 (`score_rows_for_draw`) で破棄していた。`DrawItems` /
  `CandidateExternalReport` に `near_dup_good`/`near_dup_common`/
  `auc_membership`/`dropped_anchor_fraction` (MEDIUM-3 が要求する
  `mean_dropped_anchor_fraction` の実測込み) を追加し、ARM-A の bootstrap
  経路だけでなく ARM-B/C/D/X・NC-1・NC-2 の単発 draw 経路
  (`_single_draw_candidate_report`、旧来はアームごとに個別実装されていた
  同型コードを 1 関数に統合) でも同じ 5 フィールドを出すようにした。
  近傍重複の二値指標 (`>= REF_DEDUP`) を 2 箇所 (外部の
  `score_rows_for_draw` と、既存の内部フィデリティ計測
  `fidelity_membership_and_potency`) が独立に inline していたのを
  `near_dup_flags_from_similarity()` に統合し、閾値比較が 1 箇所だけに
  なるようにした (`fidelity.json` の値は不変、`@pytest.mark.eval` の
  `test_internal_near_dup_asymmetry` で再確認済み)。
- **HIGH-2 (NC-2 の事前登録ゲートが記録から判定できない)**: 単発 draw の
  `auc_full`/`auc_lao`/`potency` は `_single_draw_candidate_report` の追加で
  ARM-B/C/D/X/NC-1/NC-2 すべてに乗るようになった。design-final.md §4.3
  「NC-2 で向きが反転しない → 計測器の実装疑い」を機械的に観測する
  `nc2_direction_reversed(auc_full) -> bool = auc_full < 0.5` を追加し、
  `negative_controls.NC-2.<候補>.direction_reversed` として記録する。**判定
  規則には一切接続しない** — 観測値と boolean を記録するだけで、次のアクション
  (verdict を出さず調査に戻すかどうか) は人間の判断のまま。
- **MEDIUM-1/2 (potency の誤記述と偏り)**: 「X3b は anchor の 39% が近傍
  複製として落ちる」は誤り (potency は採点項目側の割合、anchor 側の落下率
  ではない) だったので訂正し、候補別 potency を並記して X3b 単独への依存を
  避けるようにした (詳細は下の「結果」節)。
- **MEDIUM-3 (Ocsai の主 estimand の物体集中)**: `object_class_weights()`
  を追加し、`run_cambridge_split` (Cambridge・Ocsai 双方が共有) の結果に
  `object_weights` (`n_good`/`n_common`/`weight`/`weight_share` を物体別に)
  を追加した。
- **MEDIUM-4 (good クラス件数の誤り)**: 「32-51 件」→「40-51 件」に訂正
  (Limitations 節参照)。
- **MEDIUM-5 (eligible/engaged と survivors/collapsed の量の違い)**:
  caveat を明記 (下の「結果」節)。
- **MEDIUM-6 (`build_metrics.py` が negative control / sensitivity arm を
  落としている)**: `_split_summary()` に `sensitivity`/`negative_controls`/
  `arm_c`/`arm_x`/`object_weights` を追加した (読み取り専用の転記のみ、
  統計の再計算はしていない)。`gather.ps1` は `metrics.json` を論文 repo へ
  持ち出すため、これらは以前 repo 外に一切出ていなかった。
- 追加フィールドに対応する mutation-tested test 群を
  `tests/test_paper01_g1/{test_statistics,test_external_audit,
  test_ocsai_adapter,test_run_artifacts}.py` に追加した。実装後に
  `--audit` を 1 回再実走し (`results/external-audit.json`)、
  `build_metrics.py` で `results/metrics.json` を再生成した — **既存の
  verdict / 数値 (Cambridge 両分割 `INCONCLUSIVE_UNDERPOWERED`、Ocsai
  両分割 `PASS`、`collapse_reproduced` 全 `False`) は一切変わらず、新規
  フィールドの追加のみ**であることを、再走前後の JSON を再帰比較して確認
  済み (前後で値が変わった既存キーは 0 件)。

## 実行手順 (1 コマンド再現)

```bash
bash experiments/20260907-paper01-g1/run.sh
```

`PYTHON` 環境変数で python 実行体を上書き可能 (既定: `.venv/Scripts/python.exe`
→ 無ければ `.venv/bin/python` → 無ければ `python3`)。`run.sh` 内部で
`PYTHONHASHSEED` を `SEED` ファイルの値に固定し、`HF_HUB_OFFLINE=1` で追加
ダウンロードを起こさない。② `--fidelity` → ③ `--audit` (1回目) → ④ `--audit`
(2回目・別パス) + SHA-256 比較 → ⑤ `metrics.json` → ⑥ completion marker
(`{"event": "PAPER01_G1_RUN_COMPLETE", "status": "ok"}`) の順で走る。
進捗は tqdm 等の最新行でなく、PID 生存 + `results/run.log` 末尾の completion
marker で判定すること (`feedback_log_tail_completion_marker.md`)。

③ 単体で実測 **1408 秒 (約23分)**、④ がほぼ同じ時間を要するため **`run.sh`
全体で約47分**。フルスケール外部コーパス (Cambridge 4,148 行有効 / Ocsai
20,121 行) x 8 候補 x 複数 arm x `ANCHOR_DRAWS=200` draws x
`N_RESAMPLES=10000` bootstrap resamples の総量であり、想定内 (design-final.md
§9 の凍結値通り)。

## 結果 (honest — 再走・調整はしていない)

**外部 2 コーパスとも崩落が再現しなかった。**

| コーパス | 分割 | verdict | collapse_reproduced |
|---|---|---|---|
| Cambridge | SPLIT-BLOCK | `INCONCLUSIVE_UNDERPOWERED` | False |
| Cambridge | SPLIT-PARITY | `INCONCLUSIVE_UNDERPOWERED` | False |
| **Ocsai** | SPLIT-BLOCK | **`PASS`** (survivors X3a/X3b/X3c) | False |
| **Ocsai** | SPLIT-PARITY | **`PASS`** (survivors X0/X3a/X3b/X3c) | False |

`§6` の `PASS` は「LAO 監査を生き延びた埋め込みスコアラが存在した」の意味であり、
論文 01 の機序主張にとっては **極性が反転**する — PASS =「主張が外部で支持
されなかった」(`collapse_reproduced=false` を verdict と併置しているのはこの
極性反転を verdict の語だけで読み違えないため、Opus MEDIUM-8)。

`results/fidelity.json` (`--fidelity`, C0 = 0.9900/0.7550・C4 = 0.9950/0.7050)
は完全一致で緑 — **「別の計測器を当てただけ」ではない**。外部ハーネスは内部
apparatus と同じ配線 (`make_embed_candidate` 等) を通っている。

**否定の主語は常に計測器である** — 以下、その内訳:

- **potency の定義を正確に書く**: `potency` は「**採点項目のうち近傍 anchor
  (`max_r sim(x,r) >= REF_DEDUP`) を持つものの割合**」であり、**anchor 側が
  落ちる比率ではない**。以前の版はこれを「X3b は anchor の 39% が近傍複製
  として落ちる」と誤記していた (誤り)。正しくは **Ocsai の X3b
  (SPLIT-BLOCK) では採点項目の 37.5% が近傍 anchor を持つ**
  (`potency_at_median_draw = 0.375293`、`results/external-audit.json`
  `ocsai.splits.SPLIT-BLOCK.candidates.X3b.report`)。落下 anchor 率が
  欲しければ別の量 (`mean_dropped_anchor_fraction`、下記) を使う。
- **「potency が実質発火」の根拠を X3b 1 候補に依存させない**: Ocsai の
  survivors (SPLIT-BLOCK) の `potency_at_median_draw` は
  X0 **0.0266** / X3a **0.0407** / X3c **0.1142** / X3b **0.3753**
  (内部参照 C0 = 0.195)。0.025-0.04 程度を「実質発火」と呼ぶのは根拠として
  弱く、**候補間で 1 桁以上開いている**。さらに **X3b は encoder が
  `e5-small-v2`** であり、§8 Limitations が挙げる「`REF_DEDUP=0.90` の
  encoder 横断適用 (cos 分布のスケールが encoder ごとに違う)」の影響を
  最も受けうる候補である。よって「LAO 監査は実際に効いている」という主張は
  **候補別の potency を並記したうえで、X3b への依存に対する encoder
  スケール差の caveat を明示して**書く — X3b 単独の高い potency を全候補の
  代表値として一般化しない。
  同じ理由で Cambridge 側の記述も訂正する: Cambridge の
  `potency_at_median_draw` は X0/X1/X2/X3a/X3c が 0.0014-0.030 程度と
  低いが、**X3b だけ SPLIT-BLOCK 0.2029 / SPLIT-PARITY 0.2666 と
  Cambridge 内で最大**であり、これを「0.001-0.03 程度」という要約が
  暗黙に除外していた (誤り、訂正済)。Ocsai の記述では X3b を主役として
  引用し Cambridge の記述では同じ X3b を除外する、という**扱いの非対称**が
  あったため、以後は両コーパスとも候補別の値をすべて併記する。
- **ARM-B (uncapped, `N_R_MAX` 上限なし) でも崩落しない** — 「capped-30 で
  anchor が薄まっただけ」という説明も成り立たない。
- **`class_sizes` の good クラスは 40-51 件** (`results/metrics.json`
  `cambridge.splits.{SPLIT-BLOCK,SPLIT-PARITY}.class_sizes.good` =
  51 / 40)。旧版は「32-51 件」と書いていたが誤りで、**32 は bowl という
  1 物体の**ファイル全体**の good 件数** (`data/source-audit.json` の
  `cambridge.bowl.gold_good`) であり、`split1` (実際に採点される側) の
  pooled class size ではない。`MIN_CLASS_N=16` はクリアするものの
  ブートストラップ CI が floor を跨ぎやすい (`INCONCLUSIVE_UNDERPOWERED`
  の直接の原因)。
- **`eligible`/`engaged` (200 draw に対する割合 >= 0.5) と `survivors`/
  `collapsed` (drop 中央値 draw 1 本の bootstrap CI) は違う量である**、
  という caveat を明記する。実測: Cambridge SPLIT-BLOCK の X3c は
  `eligible=true` (200 draw のうち **72%** が `AUC_full >= floor` を満たす)
  だが、判定に使う中央値 draw では `auc_full_at_median_draw = 0.7922 <
  0.80` であり、bootstrap CI (`[0.7409, 0.8397]`) は floor をまたぐ
  (`INCONCLUSIVE_UNDERPOWERED` の一因)。**判定規則は凍結なので変えないが、
  この 2 種類の量を混同して読まないよう明示する**。
- **Ocsai の主 estimand は物体間で著しく偏っている**: §1 の重み
  `w(o) = n_good(o) * n_common(o)` を物体別に見ると、Ocsai primary battery
  (13 物体 SPLIT-BLOCK / 12 物体 SPLIT-PARITY、`|R_o| < N_R_MIN` または
  gold クラス不足で 21 物体中 8-9 物体を落とした残り) では **brick が
  重みの 64.4% (SPLIT-BLOCK) / 58.5% (SPLIT-PARITY)** を占め、4 物体
  sensitivity battery (brick/paperclip/bottle/shoe) では **brick が
  88.4% (SPLIT-BLOCK) / 87.9% (SPLIT-PARITY)** を占める
  (`results/metrics.json` の `object_weights`)。数値そのものは事前登録
  どおりで verdict は変わらないが、**Ocsai の `PASS` は実質 brick 1 物体の
  主張に近い**、という事実はこれまでどこにも書かれていなかった。
- **§5.4 の五つ組を外部候補についても実測する** (以前は `.potency` だけを
  外部で報告し、`near_dup_good`/`near_dup_common`/`auc_membership` は計算
  していたのに破棄していた): 恒等式
  `AUC_membership = 0.5 + (near_dup_common - near_dup_good) / 2` は
  24 通り (corpus × split × 候補 6 件) すべてで 6 桁量子化の精度で厳密に
  成立する (例: Ocsai SPLIT-BLOCK X3b は
  `near_dup_good=0.013937` / `near_dup_common=0.479839` →
  `0.5 + (0.479839-0.013937)/2 = 0.732951` = 実測の
  `auc_membership_at_median_draw` と完全一致)。**独立成分は 3 つしかない**
  という design-final.md §5.4 の指摘が実測でも裏付けられた。近傍重複は
  Ocsai・Cambridge のほぼ全候補で `near_dup_good ≈ 0.000` (good 側はほぼ
  anchor に重ならない) に対し `near_dup_common` が候補ごとに
  0.001〜0.48 まで幅がある — **非対称の向きは内部 C0 (good 0.000 /
  common 0.500) と同じ方向**だが大きさは候補・コーパスで大きく異なる。
  `mean_dropped_anchor_fraction` (LAO で落ちた anchor の平均本数 / |R_o|、
  埋め込み系候補のみ計測、報告専用) は Ocsai X3b が
  SPLIT-BLOCK 0.0494 / SPLIT-PARITY 0.0503 と最大、他候補は 0.0001-0.008
  程度。
- **NC-2 (good anchor) の向き反転を実測する**: design-final.md §4.3 の
  事前登録は「NC-2 で向きが反転しない → 計測器の実装疑い。verdict を出さず
  調査に戻す」という**人間の判断**であり、`decide_external` には一切接続
  していない (`nc2_direction_reversed(auc_full) = auc_full < 0.5` を記録
  するのみ)。実測: **Ocsai は両分割とも埋め込み系 6 候補 (X0/X1/X2/
  X3a/X3b/X3c) 全てで `AUC_full < 0.5` (反転、0.31-0.40 の範囲)**。
  Cambridge は埋め込み系候補のうち **X0/X1/X2/X3a/X3b は反転する
  (0.41-0.49) が X3c (bge-small-en-v1.5) は反転しない**
  (SPLIT-BLOCK 0.551185 / SPLIT-PARITY 0.654415、common 側に近いまま)。
  X5/X6 (lexical、判定対象外) は両コーパスとも反転しない。**判定は Ocsai
  側の verdict-bearing 候補は健全に反転しており計測器の実装疑いを支持する
  材料はないが、Cambridge の X3c だけは反転していない** — Cambridge は
  そもそも `INCONCLUSIVE_UNDERPOWERED` (good クラスが小さく検出力不足) で
  あり、X3c 単体の非反転がこの小さいクラスサイズによる統計的なノイズなのか
  X3c 固有の何かなのかは、本実走のデータからは**断定できない**。NC-1
  (別物体 anchor) / NC-2 の**同一アーム内の** full-vs-LAO drop は
  引き続きほぼ 0 (`median_drop` は -0.017〜+0.020 の範囲) であり、旧版の
  この記述自体は誤りではなかった — 向き反転 (`AUC_full` の 0.5 との比較)
  と drop (同一アーム内の LAO 効果) は別の観測量である。
- これは design-final.md §4.3 が**事前登録**していた分岐のうち「ARM-A で
  drop 無し → 崩落は外部で再現しなかった → 主張を apparatus 固有へ縮退させる」
  に該当する。**実走後に対応付け・floor・verdict 条件を変えていない** (S2 の
  Stop 条件に抵触していない)。

### 内部 (C0/C4) と外部 X3b の直接比較 (orchestrator 追加リクエスト、2026-09-08)

`fidelity_membership_and_potency` / `FidelityCandidateResult` に
`dropped_anchor_fraction` (内部版、`--fidelity` を再実走して実測) を追加し、
外部 X3b と並べて比較できるようにした (`run_fidelity()` / `measure_c0_
fidelity` / `measure_c4_fidelity` が内部 gold pair に対して同じ
`embed_dropped_anchor_counts` / `mean_dropped_anchor_fraction` を呼ぶ。
**既存の照合 `auc_full`/`auc_lao` (C0=0.9900/0.7550、C4=0.9950/0.7050、
`matches=true`) は不変** — `results/fidelity.json` 再生成後も
`all_match: true`)。

| | asym (nd_common−nd_good) | membership | AUC full→LAO | drop | dropped_anchor_frac |
|---|---|---|---|---|---|
| 内部 C0 (pooled) | +0.5000 | 0.7500 | 0.9900→0.7550 | 0.2350 | **0.0128** |
| 内部 C4 (pooled) | +0.4375 | 0.7188 | 0.9950→0.7050 | 0.2900 | **0.0171** |
| Ocsai X3b BLOCK (stratified) | +0.4659 | 0.7330 | 0.8631→0.8396 | 0.0235 | 0.0494 |
| Ocsai X3b PARITY (stratified) | +0.4660 | 0.7330 | 0.8934→0.8673 | 0.0260 | 0.0503 |

**非対称性 (asym) はほぼ同じ大きさ (0.44-0.50) なのに drop が内部と外部
X3b で約 10 倍違う** — この観察自体は正しい。

**しかし orchestrator が提案した機序仮説 (「外部は \|R_o\|=30 のうち LAO が
落とすのは約 4.9% で残り 28.5 本が項目を覆うが、内部は \|R_o\| が小さい
curated なので near-dup を落とすと被覆のうち遥かに大きい割合が消える」)
は、実測された `dropped_anchor_fraction` によって支持されない**:
内部 C0/C4 の `dropped_anchor_fraction` (0.0128 / 0.0171) は **外部 X3b
(0.0494 / 0.0503) より小さい** — 仮説が予測した向き (内部の方が大きい) と
**逆**である。したがって「LAO が anchor 集合の被覆をどれだけ削るか」を
崩落の機序として単独で採用することはできない。何が drop の 10 倍差を
説明するのかは本実測では**特定できていない** (候補: 内部は 41 項目・
14-16 物体で有効ペアがわずか 25 と少なく pooled AUC が少数項目の変化に
敏感、外部は数百〜数千項目で頑健、という「項目数」の違い。あるいは pooled
AUC (内部) と within-object 層別 AUC (外部) という**統計量そのものの違い**
(design-final.md §2 が明記する既知の非対称)。いずれも本実走では検証して
いない、未検証の仮説として記録するのみ)。

### 「崩落の前提が外部に無かった」か「機序が一般化しない」か (実測に基づく honest な読み)

design-final.md §4.2 の識別ロジックは「ARM-A に drop がありそれが NC-1 で
消えるか」を問う設計だが、**ARM-A 自体に (AUC ベースの) drop が実質的に
無かった**ため、この識別自体が発生しなかった (旧版の記述どおり、変更なし)。
その上で、今回追加で実測した近傍重複・NC-2 反転・dropped_anchor_fraction の
数値は以下を示す:

- **少なくとも Ocsai X3b については、崩落の前提はあった**: near-dup 非対称
  (+0.466、内部 C0/C4 の +0.4375〜+0.5000 と同程度)・NC-2 の向き反転
  (`AUC_full` 0.31-0.40 < 0.5)・非自明な potency (0.375) のすべてが揃って
  いる。それでも LAO 監査後の `AUC_LAO` は floor を割らず `survivors` が
  非空で `PASS` になった。**「崩落の前提が外部に無かった」は X3b について
  支持できない** — 前提はあったのに崩れなかった、と読む方が実測に忠実である。
  ただし機序 (なぜ崩れなかったか) は上記のとおり特定できていない。
- **caveat (X3b 固有のリスク)**: X3b は **e5-small-v2** であり、§8
  Limitations が挙げる「`REF_DEDUP=0.90` の encoder 横断適用 (cos 分布の
  スケールが encoder ごとに違う)」の影響を最も受けうる候補である。near-dup
  率自体が encoder スケールの artifact である可能性を排除できない。
- **caveat (他候補では前提が薄い)**: X3b 以外の 5 候補
  (X0/X1/X2/X3a/X3c、両コーパス・両分割) の near-dup 非対称は
  **0.0015〜0.164** と、内部 C0/C4 の 0.4375-0.5000 とは**桁が違う**。
  これらの候補については「前提が薄かった」こと自体が事実であり、X3b の
  読みを他候補に一般化できない。
- Cambridge は逆に potency がほとんどの候補で低く (0.0014-0.030、X3b のみ
  0.20-0.27) near-dup 非対称も弱いまま `INCONCLUSIVE_UNDERPOWERED` に
  終わっており、こちらは「前提が (Cambridge では) 十分に育たなかった」と
  いう読みの余地を残す。
- **結論は候補・コーパスで割れており、一律に断定しない**: X3b (Ocsai) は
  「前提はあったのに崩れなかった」を支持する最も強い材料だが、他の 5 候補は
  「前提が薄い」ままであり、Cambridge 全体としても検出力不足の域を出ない。
  **「機序が一般化しない」と一律に結論づけることも、「崩落の前提が外部に
  無かった」と一律に結論づけることも、どちらも実測を超えた過度の一般化に
  なる**。§7 の記述はこの候補依存性を honest に書き、「崩落は外部で
  再現しなかった → 主張を apparatus 固有へ縮退させる」という既存の縮退判断
  (design-final.md §4.3 の該当分岐、verdict そのもの) は変えない。

## Limitations (design-final.md §8 / issue 008 プロンプト、6 項目必須)

1. <!-- LIMITATION:participant-id --> **participant ID が両コーパスとも無い**:
   回答の独立性は仮定である。SPLIT-BLOCK (primary) / SPLIT-PARITY
   (sensitivity) の両方を報告することで、参加者が連続ブロックで並んでいる
   場合の漏れを緩和しているが、真の独立性は検証できていない。
2. <!-- LIMITATION:cambridge-no-a2 --> **Cambridge に高頻度層 (A2) が無い**:
   ARM-C (A1∪A2、内部レシピの組成に最も近いアーム) は Ocsai だけで走り、
   Cambridge には対応物が無い。
3. <!-- LIMITATION:rater-rotation --> **rater ローテーション / rater 数が
   行ごとに違う**: Cambridge は `rater1`〜`rater3` の値のある個数が行に
   よって異なる (2 名一致と 3 名一致は信頼度が違う)。`source_audit` に
   rater 数を共変量として記録しているが、gold 二値化そのものはこの差を
   重み付けしていない。
4. <!-- LIMITATION:ocsai-motes-provenance --> **Ocsai の MOTES 来歴
   グレーゾーン**: Ocsai `main2` は 9 研究の homogenized 合成スケールであり、
   基盤 MOTES コーパスの二次配布同意範囲が repo 側で明示されていない。
   行単位の provenance が無いため、MOTES 由来の混入を機械的に否定できない
   (この理由で再配布はしていない)。
5. <!-- LIMITATION:small-good-class --> **good クラスが小さい**: Cambridge
   の `split1` (実際に採点される側) の pooled good クラスは **40-51 件**
   (SPLIT-BLOCK 51 / SPLIT-PARITY 40、`results/metrics.json`
   `cambridge.splits.*.class_sizes.good`) しかなく、`MIN_CLASS_N=16` は
   クリアするもののブートストラップ CI が floor を跨ぎやすい
   (`INCONCLUSIVE_UNDERPOWERED` の直接の原因)。**訂正 (旧版の誤記)**:
   以前ここを「32-51 件」と書いていたが、32 は bowl という 1 物体の**ファイル
   全体**の good 件数 (`data/source-audit.json` の `cambridge.bowl.gold_good`)
   であり、`split1` の pooled class size ではない。
6. <!-- LIMITATION:narrow-object-set --> **物体が狭い**: Cambridge は bowl /
   paperclip の 2 物体のみ。Ocsai は 21 物体のうち `|R_o| < N_R_MIN` (=8)
   または gold クラス不足で 8-9 物体を落としている (`dropped_objects` に
   件数つきで記録)。

## 逸脱・気づき

- **すでに得られていた `results/external-audit.json` は書き換えていない**
  (値の意味では) — `run.sh` を実走すると、同じ SEED / `PYTHONHASHSEED` /
  凍結アルゴリズムで同じ内容が再生成される。本 issue が加えた唯一の構造変更は
  Cambridge ブロックへの `"status": "ok"` キー追加であり、既存の verdict /
  数値には一切触れていない。
- `main()` の `--audit` 分岐に `both_corpora_available()` チェックを追加した
  ことで、AC 008-7 (2 corpus 揃わなければ exit != 0) は `run.sh` 側に専用
  ロジックを持たせず、CLI の exit code 一本に集約できた — `run.sh` は
  `set -euo pipefail` があるので、この exit code がそのまま script 全体を
  落とす。
- SHA-256 byte-identity gate (AC 008-4) は `run_gate.py check-hashes` という
  独立した Python サブコマンドに切り出した。bash の文字列比較のまま埋め込む
  より、mutation testing で直接叩ける境界述語 (`hashes_match`) にできる
  (`feedback_witness_needs_mutation_testing.md` の教訓)。
- `metrics.json` は `results/external-audit.json` の**読み取り専用抽出**
  (`build_metrics.py`) であり、統計を再計算していない。壁時計は含めていない。

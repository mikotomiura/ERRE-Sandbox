# Retrospective: 20260907-paper01-g1-external-audit

## Task

論文 01 (`anchor-recognition-not-novelty`) の **G1 = 外部監査**。事前登録した
leave-anchor-out (LAO) 監査を、ERRE の apparatus の外にある人間 AUT コーパス 2 本
(Cambridge / Ocsai) に適用し、内部で観測した崩落が外部でも起きるかを測る。

**Done = G0 ∧ G1 ∧ G2 ∧ G3。全て達成。**

| ゲート | 条件 | 結果 |
|---|---|---|
| G0 | estimand ADR が FROZEN | ✅ 前セッションで完了 (`design-final.md`) |
| G1 | 事前登録が機械検証可能 | ✅ `pytest tests/test_paper01_g1` exit 0 (116 passed) |
| G2 | 外部監査が完走し 2 corpus 分の verdict が出る | ✅ `run.sh` exit 0、2 回実行で JSON byte 一致 |
| G3 | 1 コマンド再現 + 可搬 | ✅ paper repo 単体 exit 0、`-Verify` 175 MATCH |

## 中核結果 (honest)

**外部 2 コーパスとも崩落が再現しなかった。**

| コーパス | 分割 | verdict | collapse_reproduced | survivors |
|---|---|---|---|---|
| Cambridge | SPLIT-BLOCK | `INCONCLUSIVE_UNDERPOWERED` | False | — |
| Cambridge | SPLIT-PARITY | `INCONCLUSIVE_UNDERPOWERED` | False | — |
| **Ocsai** | SPLIT-BLOCK | **`PASS`** | False | X3a, X3b, X3c |
| **Ocsai** | SPLIT-PARITY | **`PASS`** | False | X0, X3a, X3b, X3c |

`PASS` は極性が反転している (Opus MEDIUM-8) — §8 の GO ではなく
「**LAO 監査を生き延びた埋め込みスコアラが存在した = 機序主張が外部で支持されなかった**」。

**「計測器が作動しなかっただけ」では説明できない**:
- Ocsai では potency が実質発火 (X3b は anchor の 39% が近傍複製として落ちる) しているのに
  `AUC_LAO` の CI 下限が floor 0.80 を上回った
- **ARM-B (uncapped) でも崩落しない**ので「capped-30 で anchor が薄まっただけ」も成り立たない
- **fidelity pin が完全一致** (C0 0.9900/0.7550・C4 0.9950/0.7050 が封印済 `diagnostic.json` と一致)
  なので「別の計測器を当てただけ」でもない

design-final §4.3 が**事前登録していた分岐**「ARM-A で drop 無し → 崩落は外部で再現しなかった
→ 主張を apparatus 固有へ縮退」に該当する。ADR §2 はこの結末を**予測していた**
(「最も大きく崩落する C4 は最も circular な配置」「崩落の大きさが一般化するとは言えない」)。

## Issues Completed

全 10 issue が DONE_CONFIRMED。

| # | 内容 | commit |
|---|---|---|
| I-001 | 外部コーパス取得層 + 形状/ライセンス audit | `56a1184` |
| I-002 | 事前登録の凍結 (`Final` 定数 + `config.json` 二重固定) | `ab1ba80` / `e7e45d6` |
| I-003 | 判定規則 `decide_external()` — 全域性と非恒真性 | `9a4d24a` |
| I-004 | 統計層 — within-object 層別 AUC / draw 集約 / bootstrap | `d45e2cf` |
| I-005 | Cambridge 縦スライス | `a10e2e3` |
| I-006 | Ocsai 縦スライス + ARM-C / ARM-X | `a12023f` |
| I-007 | fidelity pin | `b33ce15` |
| I-008 | 実走一式 + `run.sh` (= G2) | `19dee93` / `fd0ea6a` |
| I-009 | 可搬性 (= G3) | `7c91ba8` |
| I-010 | `writing-spec` §7 の締め + 書誌登録 | `c831a08` |

## Deferred

`blockers.md` に B-G1-1〜B-G1-9 として記録。特に:

- **B-G1-6 (次タスク確定、user 裁定 2026-09-08)**: 内部と外部の**対比そのもの**を主題に
  据え直し、scope condition を特定する追加測定。**この条件は G1 では測っていない = 現状は仮説**
- **B-G1-5**: タイトル / §0 の「own / 自身の」問題。G1 の結果で repo 名
  `anchor-recognition-not-novelty` の断定自体も再検討対象に
- **B-G1-8**: paper repo の Python 環境は単体で立っていない (Sandbox の `.venv` を借用)
- **B-G1-9**: (I-010 で main が即時解消) NOTICE.md の著者誤記

## What Worked

- **事前登録 → 凍結 → 実走の順序が守れた。** 結果が期待と逆でも `design-final` を開け直さず
  (S2 に触れず)、事前登録済み分岐にそのまま落とした
- **fidelity pin が結果の解釈を守った。** これが緑でなければ「外部で崩落しなかった」ではなく
  「別の計測器を当てただけ」になっていた
- **negative control を落とさなかった。** 結果的に ARM-A に drop が無く切り分ける差が
  発生しなかったが、それは**識別ロジックの失敗ではない**と正しく書けた
- **持ち出し先が本体と byte 一致の成果物を独立に再生成した** (両者 SHA-256 `d96bc4e6…`)。
  可搬性の主張として最も強い形
- **loop-watchdog / test-runner による客観検証**が subagent の自己申告を実際に打ち消した場面が
  複数あった (mypy の一過性 segfault、mutation の no-op 誤読)

## What Failed

- **Sonnet subagent が I-002 の途中で API rate limit に当たって落ちた。** 成果物は書き終えていたが
  報告が来ず、main が検証と仕上げ (lint 2 件 + test 関数 17 件の返り型注釈欠落) を引き取った
- **subagent が複数回「バックグラウンド完了待ち」で停止した** (I-005 / I-006 / I-008 / I-009)。
  長時間実走を含む issue では main 側で watcher を張り直す必要があった
- **issue ファイルが凍結 ADR に追随していなかった** — 002/005 が `ANCHOR_DRAWS=50` / 候補名
  `C0..C6` のまま。DA-G1-21 で design-final 側に裁定した

## Repeated Failure Patterns

### 1. mutation が「選ばれなかった行」を素通りする (3 issue で再発)

| issue | 初回生存 | 内容 |
|---|---|---|
| I-004 | **3/8** | `is_draw_engaged` の `potency > 0` → `>= 0` / `is_draw_collapsed` の `<` → `<=` / `engaged` 連言の削除 |
| I-005 | **1/6** | 物体除外ゲート `|R_o| < N_R_MIN` の境界を `<=` に緩める off-by-one |
| I-006 | **4/9** | 二値化 `== 10` の境界 / **ARM-X の anchor 出自すり替え** / gold クラス両存在ゲート 2 種 |

原因は 2 つに集約される:
- **既存 test が境界から遠い値しか使っていない** (pool=1 と pool=20 では pool==8 の
  off-by-one を突けない)
- **集約統計 (AUC) で配線を検査しようとした** — I-006 の ARM-X は stub encoder で
  good/common が綺麗に分離するため、Cambridge anchor でも Ocsai anchor でも AUC が同じになった。
  **spy で生の呼び出し引数を見る形に再設計して初めて kill できた**

→ **対策 (次タスクへ)**: 境界述語 (`>` vs `>=`、連言の各項、`min`/`max` の向き) は
**機械的に列挙して総当たり**する。配線の検査に集約統計を使わない。

### 2. mutation script の no-op を「生存」と誤読する

main 自身が I-002 で踏んだ。置換文字列がソースに存在せず mutation が適用されないと、
テストが通るので「生存」に見える。**`assert old in s` と `assert new != old` の二重確認**を
入れて以降は再発しなかった。**適用されなかった mutation は「生存」ではなく「未実施」。**

### 3. mutation testing はコードの内部整合しか見ない (2 件)

以下はどちらも **全 test 緑・全 mutant kill の状態で残っていた**欠落で、
**出力の数値を実際に読んで初めて**見つかった:

- **I-005**: `auc_full_median` 等が実は「across-draw 中央値」ではなく「drop の中央値 draw の値」
  だった。Cambridge SPLIT-PARITY の X0 は `0.8156` と報告されるのに floor を越える draw は
  32.5% しかなく、そのまま論文の表に並べると矛盾して読める。`*_at_median_draw` に改名
- **I-007**: `auc_membership` が連続値 max cosine を受けており `auc(1-m) ≡ auc_full` と
  数学的に恒等になっていた (committed 値 0.750 ではなく `auc_full` の丸写しを出力)

→ **対策**: mutation を通した後に**出力 JSON を読んで数字の意味を突き合わせる**工程を明示的に置く。

### 4. 過去タスクの教訓が効いた例

- `feedback_log_tail_completion_marker`: 長時間実走の完了判定を PID 生存 + log 末尾 marker で
  行い、tqdm 最新行を使わなかった
- `feedback_witness_needs_mutation_testing`: mutation を Done 条件に入れたことで上記の
  escaped mutant 8 件がすべて表に出た

## TASK-POST cross-review (2026-09-08)

| | HIGH | MEDIUM | LOW |
|---|---|---|---|
| Codex (gpt-5.5) | **0** | 4 | 2 |
| Opus (code-reviewer) | **2** | 7 | 6 |

**一致点: 二者とも「崩落を見逃した実装バグは無い」。** Opus の表現では
「**計測器が壊れていた線は潰せた**」。`decide_external` の全域性・非恒真性、
`auc_stratified` の定義準拠、draw 集約が周辺中央値でないこと、fidelity pin が
恒真でないこと — すべて別々に確認された。Opus は加えて Cambridge の評点 0 除外が
近傍複製の濃い層を削っていないこと、common プールに正規化後の完全重複がほぼ無いこと
(2,082 行 → 異なり 2,081) を独立に再計算し、**potency が低いのはコーパスの性質であって
実装欠陥ではない**と確認した。

**相違点が示唆的**: Codex は**実行時の堅牢性**を見て (encoder 欠損 / gate の緩さ /
定数の巻き戻し)、Opus は**報告の完全性**を見た (計算しているのに出していない量 /
事前登録ゲートが記録から評価できない)。**重なりがほとんど無く、二者レビューの価値が
実測で裏付けられた** ([[project_m13_society_live_code]] と同じパターン)。

### 反映した HIGH 相当

- **Codex MEDIUM-1**: `build_available_encoders()` の graceful skip が
  design-final §6「encoder が 1 つでも取得できなければ verdict を発行せず exit != 0」と
  **凍結 ADR に直接違反**していた → `MissingEncoderError` で fatal 化
- **Codex MEDIUM-4**: `NOTICE_TEXT` が旧い誤った attribution のままで、fetch 再実行が
  訂正済み NOTICE.md を巻き戻していた。**本タスクの `ENV_MD_TEXT` で一度直したのと
  同じ形を見落としていた**
- **Opus HIGH-1**: §5.4 の 5 つ組のうち**外部で出ていたのは 2 つだけ**。これが無いと
  「崩落が再現しなかった」と「崩落の前提が外部に無かった」を artifact から区別できない
- **Opus HIGH-2**: NC-2 の事前登録ゲート (§4.3「反転しなければ verdict を出さず調査に戻す」)
  が記録から評価できなかった → **実走で初めて反転を観測** (`AUC_full` 0.31-0.40 < 0.5)

### HIGH-1 反映で得られた追加の実測 (これが案 2 に直結する)

| | asym (nd_common−nd_good) | membership | AUC full→LAO | drop | dropped_anchor_frac |
|---|---|---|---|---|---|
| 内部 C0 | +0.5000 | 0.7500 | 0.9900→0.7550 | 0.2350 | 0.0128 |
| 内部 C4 | +0.4375 | 0.7188 | 0.9950→0.7050 | 0.2900 | 0.0171 |
| Ocsai X3b BLOCK | +0.4659 | 0.7330 | 0.8631→0.8396 | 0.0235 | 0.0494 |
| Ocsai X3b PARITY | +0.4660 | 0.7330 | 0.8934→0.8673 | 0.0260 | 0.0503 |

**非対称性がほぼ同じなのに drop が 10 倍違う。** よって **X3b については
「崩落の前提が外部に無かった」は支持できない — 前提はあったのに崩れなかった。**
ただし他 5 候補の非対称は 0.0015-0.164 と桁が違い「前提が薄かった」のが事実で、
X3b は §8 が挙げた `REF_DEDUP` の encoder 横断適用の影響を最も受けうる e5-small
なので、**一律に断定しない**。

### ★ orchestrator の機序仮説が実測で反証された

main は「崩落は LAO が anchor 集合の**被覆**をどれだけ削るかに依存する。外部は
`|R_o|=30` のうち 4.9% しか落ちないが、内部は `|R_o|` が小さい curated なので
被覆の大きい割合が消える」と仮説を立てた。**実測は逆向きだった** —
内部 `dropped_anchor_fraction` (0.0128 / 0.0171) は外部 X3b (0.0494 / 0.0503) より**小さい**。
subagent が検出して `notes.md` に明記した。**drop の 10 倍差を何が説明するかは
本実測では特定できていない。**

→ **教訓**: 同じデータから 2 つ仮説を出して 1 つ目が外れた。**案 2 は必ず
測る前に条件と判定規則を凍結する** (今回の G1 と同じ作法)。できれば仮説の生成に
使っていない配置で検証する。

## Docs Updates

- `docs/references.md` に **[32]** を append-only 追加 (削除行 0)。Ocsai の DOI は既存 **[22]** と
  一致するため citation-ssot 規則 4 に従い**再利用**し新規採番していない
- `.idea/paper-01-writing-spec.md` §7 を実際の verdict で閉じ、§7.1 (§0/§1 との齟齬 5 点) と
  §8.2 (G1 由来 Limitations 6 項目) を新設
- `.gitignore`: `paper/` を `paper/*` に変え、持ち出しツール 2 本だけを例外化 (user 裁定)

## Skill・Command Updates

**なし。** ただし次タスクへ持ち込むべき運用改善が 2 点:

1. **`/loop-issue` の mutation 指示に「境界述語の機械的総当たり」と「配線は spy で見る」を
   binding として入れる** — 3 issue 連続で同じパターンの escaped mutant が出た
2. **長時間実走を含む issue では main 側が watcher を持つ** — subagent が
   「バックグラウンド完了待ち」で停止するパターンが 4 回起きた

## Next Loop

**B-G1-6 = 案 2 (user 裁定 2026-09-08)**: 内部と外部の対比を主題に据え直し、
**scope condition を特定する追加測定**を行う。

- 内部 = anchor と gold が同一出所・curated で小さい参照集合 → 崩落する
- 外部 = anchor と gold が同一人間集団・大きいプール → potency 発火しても崩落しない
- 目標 = 「参照集合の構成がどういう条件のときスコアラは novelty ではなく
  reference-set membership を測っているか」を**反証可能な条件**として書く

**over-claim 防止**: この条件は **G1 では測っていない。現状は仮説**。検証には
`|R_o|` を振る / 同一コーパス内で anchor の出自だけを振る 等の追加測定が要る。
NC-1 は本来この切り分け装置だったが、**ARM-A 自体に drop が無かったため
切り分けるべき差が発生しなかった**。

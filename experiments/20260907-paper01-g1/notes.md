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

- **Ocsai では potency が実質的に発火している** (X3b は anchor の 39% が
  近傍複製として落ちる、`results/external-audit.json` の該当 `potency` 値
  参照) **のに** `AUC_LAO` の CI 下限が floor (0.80) を上回った。つまり
  「計測器が作動しなかっただけ」では説明できない — LAO 監査は実際に効いて
  いるが、それでも崩れなかった。
- **ARM-B (uncapped, `N_R_MAX` 上限なし) でも崩落しない** — 「capped-30 で
  anchor が薄まっただけ」という説明も成り立たない。
- **Cambridge は逆に potency が 0.001-0.03 程度と低く**、計測器がほとんど
  作動しないまま `INCONCLUSIVE_UNDERPOWERED` になった (`class_sizes` の
  good クラスが 32-51 と小さく、CI が floor を跨いだ)。
- **NC-1 (別物体 anchor) / NC-2 (good anchor) の drop もほぼ 0** だったが、
  これは ARM-A 自体に drop が (実質的に) 無いため — H_anchor と H_pop を
  切り分けるべき対照差が、そもそも発生しなかった。§4.2 の識別ロジックは
  「ARM-A で drop があり NC-1 で消えるか」を問う設計であり、ARM-A に drop が
  無い今回はこの識別自体が不要になった (識別ロジックの失敗ではない)。
- これは design-final.md §4.3 が**事前登録**していた分岐のうち「ARM-A で
  drop 無し → 崩落は外部で再現しなかった → 主張を apparatus 固有へ縮退させる」
  に該当する。**実走後に対応付け・floor・verdict 条件を変えていない** (S2 の
  Stop 条件に抵触していない)。

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
   の good クラスは 32-51 件しかなく、`MIN_CLASS_N=16` はクリアするものの
   ブートストラップ CI が floor を跨ぎやすい (`INCONCLUSIVE_UNDERPOWERED`
   の直接の原因)。
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

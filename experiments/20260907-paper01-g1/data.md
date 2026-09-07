# paper01 G1 外部監査 — 外部データ provenance

このディレクトリは `.steering/20260907-paper01-g1-external-audit/gate0-record.md`
(正典・実測値の凍結記録) と `design-final.md` §3.1 (入力ファイル SHA-256 pin) を
コードで再取得・再検証する Loop issue I-001 の成果物置き場。

取得・SHA-256 検証・形状/gold クラス件数 audit は `scripts/paper01_fetch_sources.py`
を実行することで再現できる:

```
.venv/Scripts/python.exe scripts/paper01_fetch_sources.py
```

exit 0 = 全件が下表の凍結値と一致 (Ocsai が到達不能でも Cambridge が一致していれば 0)。
exit 1 = いずれかの SHA-256 / 行数 / gold クラス件数が凍結値と食い違う (**凍結値の側は
動かさない**。upstream のデータが変わったことを意味するので停止して報告する)。
結果は `experiments/20260907-paper01-g1/data/source-audit.json` に書き出される。

## Cambridge-AUT-dataset (CC BY-NC-ND 4.0)

原 `.xlsx` 2 件を **byte 無改変** で `experiments/20260907-paper01-g1/data/raw/` へ
配置する (CC BY-NC-ND 4.0 Sec.2(a)(1)(A) の範囲、Sec.3(a) の attribution 要件は
`data/raw/NOTICE.md` に記載)。列 = `id` / `Responses` / `rater1` / `rater2` /
`rater3` / `average` (両ファイル共通)。

| ファイル | 取得元 URI | SHA-256 | 行数 | good | common |
|---|---|---|---|---|---|
| `bowl AUT dataset.xlsx` | https://raw.githubusercontent.com/ghydsgaaa/Cambridge-AUT-dataset/main/data/bowl%20AUT%20dataset.xlsx | `f8caa57cdebe1d8f19257c88e56c5346415f5289897efaa10f4150508341ac2d` | 3,380 | 32 | 2,082 |
| `paperclip AUT dataset.xlsx` | https://raw.githubusercontent.com/ghydsgaaa/Cambridge-AUT-dataset/main/data/paperclip%20AUT%20dataset.xlsx | `69e75792d0caa20363bf49a5dd57bbac731f2a19159a6b04753b0617999d7a96` | 3,650 | 47 | 2,047 |

gold 二値化 (design-final.md §3.3): 値のある rater が **全員ちょうど 1** → common /
**全員 3 以上** → good / それ以外 (0 を含む・2 を含む・band 跨ぎ・`Responses` 欠損)
→ 除外。

出典: Sun, Y., Gu, X., Myers, S. M., & Yuan, D. (2023). *A New Dataset and
Method for Creativity Assessment Using the Alternate Uses Task*. International
Conference on Intelligent Computing (IC 2023) / CCIS vol. 2036, pp. 125-138.
DOI: 10.1007/978-981-97-0065-3_9

ライセンス: **CC BY-NC-ND 4.0** (https://creativecommons.org/licenses/by-nc-nd/4.0/)
— 改変禁止 (ND) につき byte 無改変で配置し、NC (非営利) の範囲内で研究監査目的にのみ
使用する。attribution 4 要件は `data/raw/NOTICE.md` に記載。

## Ocsai `main2` (finetune-gt_main2_prepared_{train,val,test}.jsonl)

**再配布しない**。取得して SHA-256・形状・parse 成否・gold クラス件数のみを
`source-audit.json` に記録する。連結順は **train → val → test 固定**
(連結後の 0-origin 行 index が正典の走査順)。取得不能時は
`{"status": "source_unavailable"}` を記録して **exit 0** (黙って落とさない)。

| split | 取得元 URI | SHA-256 |
|---|---|---|
| train | https://raw.githubusercontent.com/massivetexts/ocsai/main/data/ocsai1/finetune-gt_main2_prepared_train.jsonl | `7b2ed8fb8a1b3c98dbb86428c222c5806870ab73a280d6e664aee137bf05ddfd` |
| val | https://raw.githubusercontent.com/massivetexts/ocsai/main/data/ocsai1/finetune-gt_main2_prepared_val.jsonl | `a40bc78a5275ad274baeac7f410f7c1beb37e7913b138f5ef5fcfee8e15ccd9b` |
| test | https://raw.githubusercontent.com/massivetexts/ocsai/main/data/ocsai1/finetune-gt_main2_prepared_test.jsonl | `bab9bf8fc28c27113a7d4d55e8f718edbad02214d14d53d98e8c78f07b3a4068` |

連結後の形状 (凍結値、`gate0-record.md` 参照):

- 全行数 = **20,121** (train 16,081 + val 1,010 + test 3,030)
- distinct object = **21**
- レコード形式 = `{"prompt": "AUT Prompt:<object>\nResponse:<text>\nScore:\n",
  "completion": "<score>"}`。parse 失敗 = **0 件**
- gold 二値化 (design-final.md §3.3): encoded **== 10** → common / **≥ 40** → good /
  11-39 → 除外
- pool good = **733** / pool common = **2,003**

ライセンス: リポジトリ (`massivetexts/ocsai`) 自体は **MIT**。ただし基盤となる
MOTES コーパスの来歴には **グレーゾーンがある** (二次配布元の同意範囲が repo 側で
明示されていない)。この理由で **再配布しない** — 取得・測定のみに用途を限定する。

## 検証コマンド

```
.venv/Scripts/python.exe -m pytest -q tests/test_paper01_g1
.venv/Scripts/python.exe scripts/paper01_fetch_sources.py
```

## 意図的に測っていないもの (forking-paths seal)

このディレクトリ・スクリプトはスコア・AUC・potency・membership・相関を一切計算しない。
それらは事前登録を凍結した後 (Loop issue I-002 以降) にしか計算しない。

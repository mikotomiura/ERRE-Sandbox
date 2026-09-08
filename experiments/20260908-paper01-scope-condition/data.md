# paper01 scope condition — 入力データ provenance

このディレクトリは `.steering/20260908-paper01-scope-condition/design-final.md`
(正典・凍結 ADR) の測定に使う。**新規コーパスの取得は一切行わない** — Loop
issue I-001 のスコープは、G1 (`.steering/20260907-paper01-g1-external-audit/`)
が既に取得・検証・SHA-256 pin 済みの外部コーパスをそのまま再利用することの
明記に限られる。

## 再利用元 (G1、変更なし)

| コーパス | 取得元・検証 | 場所 |
|---|---|---|
| Cambridge-AUT-dataset (`bowl` / `paperclip`) | `scripts/paper01_fetch_sources.py` (G1、無改変・無再実行) | `experiments/20260907-paper01-g1/data/raw/` |
| Ocsai `main2` (`train`/`val`/`test`) | 同上。**再配布しない** (来歴グレーゾーン、G1 data.md 参照) | 取得のみ、`source-audit.json` に記録 |

SHA-256 pin (G1 `config.json` / `data.md` から transcribe、**この ADR では
再検証しない — 変更が要ると判明したら停止して報告する**):

| ファイル | SHA-256 |
|---|---|
| `bowl AUT dataset.xlsx` | `f8caa57cdebe1d8f19257c88e56c5346415f5289897efaa10f4150508341ac2d` |
| `paperclip AUT dataset.xlsx` | `69e75792d0caa20363bf49a5dd57bbac731f2a19159a6b04753b0617999d7a96` |
| `finetune-gt_main2_prepared_train.jsonl` | `7b2ed8fb8a1b3c98dbb86428c222c5806870ab73a280d6e664aee137bf05ddfd` |
| `finetune-gt_main2_prepared_val.jsonl` | `a40bc78a5275ad274baeac7f410f7c1beb37e7913b138f5ef5fcfee8e15ccd9b` |
| `finetune-gt_main2_prepared_test.jsonl` | `bab9bf8fc28c27113a7d4d55e8f718edbad02214d14d53d98e8c78f07b3a4068` |

これらは `scripts.paper01_external_audit.CORPORA` (このモジュールが二経路
helper 経由で import する、無改変) が既に保持している値と同一である。
**本タスクのコードはこの定数を読むだけで、独自に再定義しない。**

## 内部データ (frozen apparatus、無改変)

Stage 1 / Stage 0 が参照する内部 gold は
`src/erre_sandbox/evidence/es4_actuator/data/adversarial_labeled.yaml`
(`es4_scorer_diag.load_adversarial_labeled()` 経由、読むだけ) と、封印済み
`experiments/20260701-es4-scorer-diag/diagnostic.json`
(`STAGE1_INTERNAL_DROP_REF` の出所、**touch しない**) である。いずれも
新規取得ではなく、既存の凍結資産の読み取りに限定される。

## 検証コマンド

```
.venv/Scripts/python.exe -m pytest -q tests/test_paper01_scope
```

(encoder 完全非依存。`[eval]` extras 不要。ネットワークアクセスなし。)

## 意図的に測っていないもの (forking-paths seal、I-001 スコープ)

このディレクトリ・スクリプトは τ / ρ / Δ / Stage 1 replicate / Stage 2 の
verdict を一切計算しない。それらは事前登録 (`config.json`) を凍結した後
(Loop issue I-002 以降) にしか計算しない。

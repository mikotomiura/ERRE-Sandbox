# notes — 論文 02 実走 driver の建設 (spend なし)

## この記録の位置づけ

**実走していない。** 本記録は 2 アーム driver を建設し、**9,600 draws を使う前に**
harness の誤りを殺しきった作業の記録である。spend 批准は別ゲート (DA-P3B-35)。

実 LLM を呼んだのは **smoke の 32 draws × 2 アーム = 64 draws (合計 約 2 分)** のみ。
これは spend ではない。

## Done 0 — 環境と封印の一致 (2026-09-14 実測)

| 項目 | 封印値 | 実測 | 判定 |
|---|---|---|---|
| `ollama_version` | `0.32.12` | `0.32.12` | ✅ |
| `llama3.1:8b` digest | `46e0c10c039e…a666e` | 一致 | ✅ |
| `qwen3:8b` digest | `500a1f067a9f…b8b41` | 一致 | ✅ |
| `bank_checksum` | `5e991dd63407…f71fb` | 一致 | ✅ |
| `uv.lock` sha256 | `9cc70f9dc5d6…0c0f7` | 一致 | ✅ |
| `python` | `3.11.15` | `3.11.15` | ✅ |

**封印は生きている。** ただし `ollama` が自動更新されれば崩れる (DA-P3B-36)。

## 成果物

- `scripts/paper02_run_arms.py` — 3 モード (`--preflight` / `--capture` / `--verify`)
- `tests/test_integration/test_paper02_run_arms.py` — **47 件**
  (`tests/test_scripts/` は gitignore されており CI に載らない — DA-RD-11)

## 実測 (すべて再現手順つき)

### 1. preflight が実封印に対し両アームで PASS

```
python scripts/paper02_run_arms.py --preflight --arm control   # exit 0
python scripts/paper02_run_arms.py --preflight --arm primary   # exit 0
```

値は**観測**である (`GET /api/version` / `GET /api/tags` / `uv.lock` の hash /
凍結 bank の再計算)。CLI 引数の default に封印値を置いていない。

### 2. smoke (M=2 / K=8 = 32 draws) を実 `verify_seal` に当てた

**封印との差分が `m_draws` 1 点だけになる**ように K は 8 のまま落とさなかった
(K を削ると bank が別物になる — DA-RD-8)。

```
[seal] FAIL
  - run-manifest.json: m_draws at run.m_draws is 2, sealed as 300 -- ...
  - run-verdict.json: threshold m_draws is 2.0, sealed as 300.0
```

**他 11 フィールドは実観測値で全一致した。**

### 3. 陽性対照 — 封印値どおりなら **通る**

M を 300 に直した合成 manifest は両アームとも PASS:

```
[seal] OK: control-manifest.json names this seal, and the control arm's model,
digest, think regime, environment, sampling plan, context bank and all 11
thresholds match the sealed arm spec
```

落ちるだけの検査は恒真でありうるので、この対照が無ければ 2 の結果は根拠にならない。

### 4. 変異 — `verify_seal` に対して 13/13 kill

model / digest / seed / bank_checksum / context_ids / think / ollama_version /
uv_lock / `sealed_manifest_sha256` 欠落 / 別の封印を名乗る / 閾値の改変・追加・削除。

### 5. 変異 — driver 自身に対して

| 段階 | 結果 |
|---|---|
| 初回 15 種 | **14 kill / 1 生存** |
| 生存 1 件 (`k_contexts` を引数書き写しへ) | 整合ガード導入後は**意味的 no-op** |
| Codex 指摘の修正を含む 23 種 | **23/23 kill** |
| code-reviewer(Opus) 指摘の修正後に再走 | **23/23 kill** (テスト 68 件) |

生存した 1 件は捏造で埋めず、no-op として記録した (DA-P3B-21)。

### 6. `repro.sh` step 13 の発火

合成 verdict を置いて実測。**確認後に削除済** (`git status --porcelain` が空)。

| 状態 | exit | 照合 |
|---|---|---|
| `reported-branch.txt` 無し | 0 | **無し** |
| `R1` (一致) | 0 | 有り |
| `R2` (食い違い) | 1 | 有り |

使い捨てコピーでは `repro.sh` が **14 step 全通過** (step 13 も実行) した。

### 7. 二者レビューで見つかった「実走の後にしか分からない壊れ方」

**Codex** (改竄と正しさ) と **code-reviewer(Opus)** (5 時間を生き延びるか / verify が
無言で緑になる経路) の指摘は**ほとんど重ならなかった**。片方だけでは実走できなかった。

実測で再現した 2 件 (いずれも Codex HIGH-2 を反映したときに私が作り込んだ):

- **論文 repo が存在しないと封印検査が 1 行も出さずに消え、exit 0** になった
- **digest を改竄した manifest に `sub_sealed_scale: true` を 1 行足すだけ**で
  封印検査の失敗が握り潰され exit 0 になった

反映後は両方とも exit 2 (前向き結果ではない) になることを実機で確認した。

## spend の前に片付ける必要がある 2 件 (本タスクの範囲外)

**F1**: 前向き verdict を `data/raw/` に置くと `verify_data_hashes` (step 3) が
`set -e` 停止し、step 13 に到達しない。`analysis/freeze-provenance.json` は
**封印済**なので provenance 行を足せない。**封印外**の `verify_data_hashes.py` に
`PROSPECTIVE_OUTPUTS` 除外を足せば 14 step 全通過することは実証済 (封印は無傷)。

**F2**: `manuscript/reported-branch.txt` が無いと step 13 は**緑のまま照合が消える**。

どちらも**論文 repo 側の変更**であり、凍結 prompt の binding
(「論文 repo に本タスクでは commit しない」) に従って本タスクでは適用していない。

## この記録が**言っていない**こと

- ✗ 「実走した」 — していない。32 draws × 2 の smoke のみ
- ✗ 「判定が出た」 — smoke の verdict は `INCONCLUSIVE`
  (`below-powered-scale`)。統計量は 1 つも計算されていない
- ✗ 「harness に誤りが無い」 — 見つけた誤りを潰しただけである。
  Codex は pytest を再実行できておらずコード読解ベースだと自己申告している
- ✗ 「封印が今後も生きている」 — `ollama` の自動更新で崩れる。
  実走の直前に Done 0 を再実測すること

# experiments/20260701-es4-scorer-diag

M13-ES4 **scorer offline diagnostic** (方向 C)。Phase 0 = INVALID_SCORER を受け、既取得 Phase A データ +
凍結 holdout 上で「(a1)(a2) を非循環に通す候補 scorer が存在するか」を **GPU 追加ゼロ** で検証する。

## 構成
- `diagnostic.json` — per-candidate metrics + forensic + decision (go/no-go)。
- `run.sh` — 1 コマンド再現 (CPU のみ)。

## 実行
```bash
bash experiments/20260701-es4-scorer-diag/run.sh
# or:
PYTHONPATH=src python scripts/es4_scorer_diag.py \
  --run-dir experiments/20260630-es4-phase0/phaseA \
  --out experiments/20260701-es4-scorer-diag/diagnostic.json
```

## 入力 (read-only、凍結)
- `experiments/20260630-es4-phase0/phaseA/{generations,judgements,scores}.jsonl` (Phase A 永続データ)。
- `src/erre_sandbox/evidence/es4_actuator/data/{adversarial_labeled,common_uses,aut_battery}.yaml` (凍結 battery)。
- harness は凍結 apparatus を **read-only 再利用** (改変なし)。

## 結果 (2026-07-01)
**VERDICT = NO_VALID_SCORER → 方向 B (arc pivot)**。embedding rarity 族は全て leave-anchor-out audit で
floor 未満に崩落 (Codex HIGH-1 の anchor 循環性の実証)、唯一 RARITY_OK を通した lexical Jaccard も entropy 還元
可能 + 効果 floor 未満。詳細 = `.steering/20260701-m13-es4-scorer-diagnostic/diagnostic-report.md`。

## 注記
- GPU 不使用。alt encoder (C3: MiniLM / e5-small / bge-small) は初回 model download に network を要する。
  offline では graceful skip され、結論は不変。
- 凍結 apparatus 不変 (`git status` で `src/erre_sandbox/evidence/` 変更ゼロ)。

## 再現性に関する既知の限定 (2026-09-07 実測)

`diagnostic.json` は **`PYTHONHASHSEED` を固定した場合にのみ bit 再現する**。
本ディレクトリの `run.sh` は固定していないため、**committed の `diagnostic.json` は
未固定の実行で生成されている**。

**実測** (論文 01 リポジトリへ持ち出した同一コードで検証):

| 条件 | 結果 |
|---|---|
| `PYTHONHASHSEED=0` を 2 回 | **JSON 完全一致** |
| `PYTHONHASHSEED=0` vs `1` | 3 フィールドのみ差 |
| 未固定 (committed / 再実行) | 同じ 3 フィールドが毎回変動 |

**差が出る 3 フィールドはすべて `C5-jaccard-full`**:

- `delta_ci_lower` / `delta_ci_upper` — bootstrap CI。4 桁目から動く
- `raw_delta_dq` — **最終 ULP のみ** (`0.01442902420948409` vs `0.014429024209484094`)

**影響を受けないもの**: `verdict` (= `NO_VALID_SCORER`)、全 9 candidate の
`gold_auc_full` / `gold_auc_leave_anchor_out` / `adversarial_auc` / `rarity_ok`
(= **論文 Table 1 の全列**)。他 8 candidate は 1 フィールドも動かない。

**機序**: `_tokens()` が返す `set[str]` の反復順が hash seed に依存し float の加算順が変わる。
単独では最終 ULP の差だが、bootstrap 再標本化がそれを CI の 4 桁目まで増幅する。
**bootstrap 自体は seed 済** (`np.random.default_rng(0)`) であり RNG の問題ではない。

**対処の状態**: 論文 01 リポジトリ側の `analysis/scripts/run-diagnostic.sh`
(`paper/gather.ps1` が生成) は `export PYTHONHASHSEED="$(cat SEED)"` を入れて固定済。
**本ディレクトリの `run.sh` と committed `diagnostic.json` は未変更** — 封印済 artifact を
事後に再生成しない方針のため。**2026-09-07 に user 裁定で「再生成しない」(案 a) が確定**。
根拠 = 決定に効く数値 (Table 1 の全列 + verdict) は seed に依らず同一であり再生成の利得が無い、
封印を事後に破らない規律と整合する。代わりに**論文 01 の Limitations に明記する**
(`.idea/paper-01-writing-spec.md` §8.1 に本文の一文を確定済)。

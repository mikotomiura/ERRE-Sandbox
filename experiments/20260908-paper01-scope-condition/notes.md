# paper01 scope condition — notes (issue 007: run.sh 一式 + 実走 + honest verdict)

**このファイルは I-007a (実走の前段、2026-09-08) と I-007b (実走、2026-09-09) の
両方の成果物である。「## 結果」以降が実測値と verdict を含む。**

> **訂正 (2026-09-09、I-007b)**: 本ファイルの冒頭は I-007a 時点で
> 「結果節はプレースホルダのみで、実測値・verdict は一切含まない」と宣言していたが、
> **実走後はその宣言自体が偽になる**ため差し替えた。凍結 annotation に「未実行」を
> 書き込むと実走後に必ず自己矛盾する、という既知の失敗型
> (`project_m13_society_live_real_run` の erratum) の再発である。
> 以下「## 結果」より前の節は **I-007a 時点の記録**として読むこと —
> 特に「手順 ... 実行はしていない」「I-007a の境界 (このセッションでは実行していない)」
> 「データ欠如と不一致の区別 (このセッションでの確認)」の 3 節は**当時の状態**の記述であり、
> **I-007b では実際に実行し、Ocsai もネットワークから取得している**。

## 検証する仮説

`docs/research-positioning.md` §5 の **H4** (ES-4、bounded closed as
measurement line; effect unjudged) が、この計測系列の親である。G1 外部監査
(`experiments/20260907-paper01-g1/`) は「埋め込み rarity スコアラが
frozen apparatus 下で非循環に建たなかった」という内部崩落 (`NO_VALID_SCORER`)
が **ERRE apparatus の外 (Cambridge / Ocsai の人間集団) でも成り立つか**を
問い、**外部 2 コーパスとも崩落が再現しなかった** (Cambridge 両分割
`INCONCLUSIVE_UNDERPOWERED`、Ocsai 両分割 `PASS`)。よって「埋め込み新規性
スコアラは anchor 認識をしている」という機序主張を**一般命題としては出せない**
状態で G1 は閉じた。

本タスク (paper01 案2 / scope condition) は G1 が残した単一の未説明事実 ---
「近傍重複の非対称 (asym) はほぼ同じなのに drop が内部/外部で約 10 倍違う」
--- に対する追加測定であり、H4 効果そのものを再検証するものではない。問うのは:

> 参照集合の構成がどういう条件のとき、埋め込み rarity スコアラは novelty
> ではなく reference-set membership を測っているのか。

`.steering/20260908-paper01-scope-condition/design-final.md` §0 が凍結した
問い、条件 C、判定規則をそのまま使う (本ファイルはそれを緩めない)。

## 借用した apparatus / 出典 (無改変)

- `src/erre_sandbox/evidence/es4_actuator/**` (`constants` / `battery.
  AdversarialItem`) --- 凍結。**touch していない**。
- `scripts/es4_scorer_diag.py` --- 凍結・read-only 再利用
  (`make_encoder` / `embed_map` / `embed_rarity` / `load_adversarial_
  labeled` / `load_common_uses`)。**改変していない**。
- `scripts/paper01_external_audit.py` (G1、I-001〜I-008 landed) ---
  事前登録定数 / §5 統計層 / §6 判定規則 / Cambridge・Ocsai アダプタ / §2
  fidelity pin / `run_fidelity()`。**この issue でも import のみ、
  一切編集していない** (design-final.md §6 実装制約)。
- `scripts/paper01_scope_condition.py` (Loop I-001〜I-006 landed) ---
  Stage 0/1/2 の判定・抽出・間引き層。本 issue (I-007a) が
  `# I-007:` anchor 節で追記したのは **`--fidelity` CLI 分岐の中身**
  (pin (b)+(c)) と **`--scope` の Cambridge セル配線** のみ --- 既存の
  I-002..I-006 anchor 節・凍結 dataclass のフィールドは無改変。
- `experiments/20260907-paper01-g1/data/raw/` の Cambridge `.xlsx` 2 本 ---
  G1 が既に取得・SHA-256 pin 済み。**本 issue は新規取得を一切行っていない**
  (再取得禁止、`experiments/20260908-paper01-scope-condition/data.md` 参照)。

## 手順 (1 コマンド再現、I-007a はここまでを実装 -- 実行はしていない)

```bash
bash experiments/20260908-paper01-scope-condition/run.sh
```

`PYTHON` 環境変数で python 実行体を上書き可能 (既定: `.venv/Scripts/
python.exe` → 無ければ `.venv/bin/python` → 無ければ `python3`)。`run.sh`
内部で `PYTHONHASHSEED` を `SEED` ファイルの値 (`20260908`) に固定し、
`HF_HUB_OFFLINE=1` / `PYTHONUTF8=1` を export する。

1. ① 環境変数 export。
2. ② `--fidelity` (design-final.md §6 pin (b)+(c))。**不一致 (`exit 1`)
   と source-unavailable (`exit 2`) を混同しない** ---
   `scripts.paper01_scope_condition.cli_fidelity` / `FIDELITY_EXIT_MISMATCH`
   / `FIDELITY_EXIT_SOURCE_UNAVAILABLE` 参照。pin (c) (内部 C0/C4) は
   凍結済み `_g1.run_fidelity()` にそのまま委譲 (再実装していない)。pin
   (b) (`cell(tau=REF_DEDUP,k=N_R_MAX)` が G1 の Ocsai SPLIT-BLOCK ARM-A
   を再現するか) は `measure_g1_arm_a_fidelity()` /
   `g1_arm_a_fidelity_matches()` が
   `tests/test_paper01_scope/test_cells.py::
   test_dense_cell_reproduces_g1_arm_a` (I-006 が既に書いていた実データ
   test、`ERRE_RUN_REAL_MPNET_TESTS=1` gate) と同じ配線を実行して比較する。
3. ③ `--scope` (1 回目) → `results/scope.json`。実装は
   `scripts.paper01_scope_condition.cli_scope` / `build_split_cells`
   (Stage 2 の 2x2 グリッド + DA-SC-3 の 4 セル共通交差 + MEDIUM-3 の
   τ* 隣接段チェック) / `_gather_cambridge` + `_score_cambridge_arm_s`
   (Cambridge ARM-S、SPLIT-BLOCK の τ*/k* を使う --- 本 issue 独自の
   設計選択、design-final.md はどちらの split の τ*/k* を使うか明示して
   いないため、`_CambridgeGather` のドキュストリングに理由を明記した)。
4. ④ `--scope` (2 回目、scratch パス) + `run_gate.py check-hashes` に
   よる SHA-256 一致ゲート (不一致で `exit 1`)。
5. ⑤ `build_metrics.py` --- `results/scope.json` からの**読み取り専用
   抽出**。統計は一切再計算しない (`extract`/`build_metrics` 関数は
   `dict.get` の組み合わせのみ)。
6. ⑥ completion marker (`{"event":
   "PAPER01_SCOPE_CONDITION_RUN_COMPLETE", "status": "ok"}`) を
   `run.log` の最終行に出す。

進捗は tqdm 等の最新行でなく、PID 生存 + `results/run.log` 末尾の
completion marker で判定すること (`feedback_log_tail_completion_marker.md`)。
**実走中はリポジトリのファイルを触らない。mutation testing と CI を並走
させない** (issue 007 Background、G1 の反省)。

### I-007a の境界 (このセッションでは実行していない)

- **Ocsai の取得・fetch を一切行っていない** --- ネットワークアクセスを
  伴うコマンドは実行していない。`--scope` / `--fidelity` の pin (b) は
  Ocsai 無しでは source-unavailable として `exit 2` (pin (b)) /
  `exit 1` (`--scope`) になることを、上記の CLI 実装のコード上の分岐
  として確認した (実際に実行して確かめてはいない --- 下記「データ欠如と
  不一致の区別」参照)。
- **`run.sh` を実行していない**。書いただけである。
- **`results/scope.json` を実データで生成していない**。verdict は出して
  いない。

### データ欠如と不一致の区別 (このセッションでの確認)

- `--fidelity` の pin (c) (内部 C0/C4): `_g1.run_fidelity()` が
  `RuntimeError` (encoder unavailable) または `FileNotFoundError`
  (封印済み Phase A artifact 欠損) を送出した場合、`cli_fidelity()` は
  これを **`unavailable = True`** として扱い、`all_match` が `False` の
  場合の **`mismatch = True`** とは別変数で管理する
  (`scripts/paper01_scope_condition.py` の `cli_fidelity()` 参照)。
  両方が発生した場合は mismatch を優先して報告する (より強いシグナルを
  先に出す、という本 issue 独自の設計判断)。
- `--fidelity` の pin (b) (外部 ARM-A 再現): `_gather_ocsai("SPLIT-BLOCK")`
  が `None` (Ocsai 到達不能または encoder 欠如) を返した場合も同じく
  `unavailable = True` として扱い、`g1_arm_a_fidelity_matches()` が
  `False` を返す場合の mismatch とは独立して記録する。
- `--scope`: Cambridge / Ocsai (両分割) / encoder のいずれかが欠如すると
  `_write_unavailable()` で `{"status": "source_unavailable"}` を書いて
  `exit 1` を返す (verdict は一切出さない、DA-SC-5 と同じ規律)。
- **この環境 (本セッションのサンドボックス) には Ocsai が存在せず、かつ
  ネットワークアクセスは禁止されているため、`--scope` と `--fidelity`
  の pin (b) は実際に走らせれば必ず source-unavailable 経路 (pin (b):
  `exit 2`、`--scope`: `exit 1`) を通る。これは「データが無い」であって
  「不一致」ではない --- コード上、`unavailable` と `mismatch` は別の
  bool 変数であり、`unavailable` のみが立った場合に `mismatch` 用の
  メッセージが出ることはない。**

### unit test での「データが揃えば完走する」証明

`--scope` の実配線 (Cambridge セル配線・`build_split_cells` の 2x2 グリッド
+ DA-SC-3 交差 + τ* 隣接段チェック) は、合成データ (既存の
`tests/test_paper01_scope/test_cells.py` の fixture パターンを踏襲した
hand-built `ObjectSplitContext` / フェイク encoder) を monkeypatch で
`_gather_ocsai` / `_gather_cambridge` / `_load_mpnet_or_none` に注入する
ことで、encoder 非依存のまま「データが揃えば `run_scope()` まで完走し
`results/scope.json` を書く」ことを pin した
(`tests/test_paper01_scope/test_scope_cli_wiring.py`)。

## 結果

**実走日時**: 2026-09-09 (I-007b)。`bash experiments/20260908-paper01-scope-condition/run.sh`、
**exit 0**、completion marker `{"event": "PAPER01_SCOPE_CONDITION_RUN_COMPLETE", "status": "ok"}`。
2 回実行の `scope.json` は SHA-256 一致
(`e96e1e4e30c99ea4b257853a3e10b48cbb8b2a1e2fe70ec427f888c7cdf624e8`)。

### fidelity pin (Gate 1 — ここが緑になるまで verdict を読まない)

`--fidelity` **exit 0** (= `FIDELITY_EXIT_OK`。`2` = source-unavailable ではない):

- **pin (c)** 内部 C0/C4: OK (凍結済み `_g1.run_fidelity()` に委譲)
- **pin (b)** 外部 `cell(τ=0.90, k=30)` が G1 ARM-A を再現: **OK**

**blockers.md ブロッカー 3 はこれで解消**した。この pin は本タスクで一度も実行されて
おらず、I-007b が初回実行である。不一致なら装置が壊れているとして verdict を読まずに
停止する約束だったが、一致したため verdict を読む資格が立った。

### verdict (凍結済み `decide_scope()` の出力、そのまま)

| フィールド | 値 |
|---|---|
| `verdict` | **`DO_NOT_WRITE`** |
| `condition_c_supported` | `false` |
| `deflation_supported` | `false` |
| `stage1_outcome` | `DEFLATION_REJECTED` |
| `single_point_dependent` | `false` |
| `t_confound_note_required` | `false` |
| `fail_reason` | `null` (F1-F7 のいずれにも該当せず) |
| `notes` | `[]` |

**出口 (design-final.md §5)**: 「Stage 1 で deflation 棄却 **かつ** Stage 2 で C 支持
(F1-F7 非該当)」でのみ「書く」。本走は Stage 1 が棄却まで到達したが **Stage 2 が C を
支持しなかった**ので、**「それ以外すべて」= 論文 01 は単独では出さない**枝である。

**F 分岐が立っていないことの意味**: これは「構成不能」(F1/F2) でも「監査未作動」(F3) でも
「外部矛盾」(F5) でもない。**装置は動き、条件 C が実測で支持されなかった**という実質的な
否定結果である。

### Stage 2 — C が支持されなかった中身

C 支持は `verdict(ARM-S) == NO_VALID_SCORER` かつ `verdict(ARM-A) == PASS` を両分割で
要求する。実測は **両分割・両アームとも `PASS`**:

| split | τ\* | ρ_ext(τ\*) | ρ_int | k\* | ARM-A (τ=0.90, k=30) | ARM-S (τ=τ\*, k=k\*) |
|---|---|---|---|---|---|---|
| SPLIT-BLOCK | 0.45 | 0.375421 | 0.384004 | 10 | `PASS` (n_leaders 118) | **`PASS`** (n_leaders 41) |
| SPLIT-PARITY | 0.50 | (0.398702 @0.50) | 0.384004 | 10 | `PASS` (n_leaders 42) | **`PASS`** (n_leaders 16) |

- **ARM-S は実際に疎化されている** — n_leaders 118→41 / 42→16、k 30→10、τ 0.90→0.45/0.50。
  ARM-A と同一のセルに潰れてはいない。
- **τ\* 較正は届いている** — ρ_ext は τ を下げると 0.657612 → 0.321498 (BLOCK) まで単調に
  下がり、ρ_int = 0.384004 を跨ぐ。F1 (ρ 到達不能) は成立しない。
- `single_point_dependent = false` — 隣接段でも結論は変わらない (F7 非該当)。
- 4 セル共通 active 物体は BLOCK 7 個 / PARITY 10 個で、ARM-A の active と**同一**
  (F2 の物体消失なし)。

**読み**: 参照集合を「用途クラスタごとに代表 1 件だけの canonical な非冗長リスト」へ
疎化しても、埋め込み rarity スコアラは **LAO 監査を生き延びた**。
条件 C が予言する「そう作ると壊れる」は、Ocsai 上では**起きなかった**。

### Stage 1 — deflation 棄却だが、帯は退行している

`drop_p5 = median_drop = drop_p95 = 0.0` (pooled / 層別 / eligible 限定、**すべて 0.0**)。
`eligible_fraction = 0.80`、`n_replicates = 500`、`n_objects_pool_short = 0`。
帯 [0.0, 0.0] は内部 C0 pooled drop `0.2350` を含まないので、事前登録した規則により
`DEFLATION_REJECTED`。

**この 0.0 が何を意味するかを、額面で受け取らずに実測で追った** (下記「出力 JSON の
意味突き合わせ」参照)。結論: **配線は健全で、drop が 0 なのは LAO の摂動が
この配置では極小だから**である。

### Cambridge (報告 + 非矛盾のみ)

`verdict = INVALID_TASK_BATTERY` (ARM-S、τ=0.45 / k=10、active = bowl / paperclip)。
F5 は `PASS` のときだけ成立するので**矛盾していない**。G1 baseline の
`INCONCLUSIVE_UNDERPOWERED` と同じく、Cambridge は確証に使えない (Limitation 7)。

### Stage 0 (記述・診断。verdict には使わない)

| source | candidate | ρ | n_common | n_good | mean_T_common | mean_S_common | mean_Δ_common |
|---|---|---|---|---|---|---|---|
| internal_c4 | C4 | 0.384004 | 7 | **0** | 0.963170 | 0.310457 | 0.652713 |
| external_ocsai_arm_a | X0 | 0.627753 | 41 | **0** | 0.946346 | 0.762210 | 0.184136 |

事前登録した読み: `|T_int − T_ext| = 0.008412` < `|S_int − S_ext| = 0.225877` ⇒ **S 由来**。
`|Δ_int − Δ_ext| = 0.234289` ≥ `DELTA_MATERIAL_EPS` = 0.01 ⇒ **F4 (機序不在) ではない**。
内外の Δ 差は主に S (残存被覆) 由来であり、冗長性を操作対象にする設計自体は素直だった
— **にもかかわらず Stage 2 で C は支持されなかった**。

### セル別 `object_weights` (design-final.md §3 LOW-2 の必須成果物)

- **SPLIT-BLOCK** (ARM-A / ARM-S 共通): brick **0.699180** / rope 0.096467 / box 0.057880 /
  knife 0.057715 / bottle 0.040401 / paperclip 0.033640 / fork 0.014717
- **SPLIT-PARITY** (同): brick **0.600098** / rope 0.117164 / box 0.099688 / knife 0.055423 /
  bottle 0.034460 / paperclip 0.031465 / table 0.018871 / fork 0.017230 / pants 0.014769 /
  tire 0.010830
- **Cambridge**: paperclip 0.641477 / bowl 0.358523

Limitation 6 (brick への重み集中) は**実測で再現し、しかも G1 の 0.644 より強い**
(BLOCK 0.699)。主判定は事実上 brick 1 物体に支配されている。

## 出力 JSON の意味突き合わせ (design-final.md §7 / AC 007-8・007-9 の必須工程)

**「全 test 緑・全 mutant kill でも意味が壊れている」型の欠陥を捕まえる最後の関門**として、
`scope.json` の数字を 1 つずつ実物に当てた。**推論で片付けず、実際に観測した。**
診断スクリプトは scratchpad の使い捨て (`diag_stage1.py`、リポジトリ外・凍結 apparatus 無改変・
読み取りのみ)。

### 追った異常 1: Stage 1 の drop が 500 replicate すべてで厳密に 0.0

`eligible_fraction = 0.80` は `auc_full` が replicate ごとに変動していることを意味するのに、
`auc_lao` が毎回それと完全一致する — 「`scores_lao` が `scores_full` と同じ配列に
なっている配線ミス」の疑いがあった。**実測で否定された**:

| 観測量 | 実測値 |
|---|---|
| `scores_full == scores_lao` (配列一致) | **False** |
| 1279 項目のうち LAO で値が変わる項目数 | **41** (3.2%) |
| `mean(|scores_full − scores_lao|)` | 0.005903 |
| コーパス全体の `auc_full` / `auc_lao` | 0.788416 / 0.788264 |
| **コーパス全体の drop** | **0.000152** |
| 500 replicate 中 `auc_full != auc_lao` の件数 | **6** (最大 \|drop\| = 0.043478) |
| 診断が再現した `eligible_fraction` | **0.80** (`scope.json` と一致) |
| replicate あたりの qualifying 物体数 | 全 500 replicate で 12 (13 active のうち 1 物体は good 0 件) |

**結論**: 配線は健全である。`scores_lao` は独立に計算されており、6 replicate では実際に
非ゼロの drop が出ている。494/500 が厳密 0 なので 5/50/95 パーセンタイルが 0.0 になる。
**帯 [0.0, 0.0] は正しい計算結果**であって、潰れた定数ではない。

**ただし読みは慎重にする**: drop が 0 に張り付く原因は縮小 (小標本化) ではなく、
**この配置では LAO 摂動そのものが極小**なことである (コーパス全体の drop = 0.000152)。
つまり Stage 1 は「小標本化しても 0.2350 の崩落は再現しない」を示したが、
その理由は「**縮小前から Ocsai は崩落していない**」であり、
**Stage 1 は「小標本が崩落を作らない」と「このコーパスはそもそも崩落しない」を
区別できない**。これは G1 (PR #95) の「外部 2 コーパスとも崩落せず」が Stage 1 の
水準で再出現したものである。**deflation 棄却は事前登録どおりの読みだが、
それ単独では内部崩落の非小標本性の積極的証拠にはならない。**
(下の Limitations 9 に持ち込む。)

### 追った異常 2: Stage 0 の `n_good = 0` (内部・外部とも)

`mean_t_good` / `mean_s_good` / `mean_delta_good` はすべて **0.0 フォールバックであって
測定値ではない**。原因は配線ミスではなく **engaged 述語の意味**である:
engaged = `near_dup_flags_from_similarity(max_sim_full, ref_dedup=0.90)` = 「anchor への
近似重複」であり、**good (創造的) 応答は定義上 anchor の近似重複にならない**。
コーパス側には good が確かに存在する (Ocsai SPLIT-BLOCK の active 13 物体で good 287 /
common 992) にもかかわらず、engaged 部分集合には 1 件も入らない。

**帰結 (伏せない)**:

1. `s_common_minus_s_good` (design-final.md §3 MEDIUM-1 が要求した「ラベル層別の残存被覆差」)
   は **`mean_s_common` と厳密に一致**する (内部 0.310457 / 外部 0.762210 で実測確認)。
   **この量は本走では推定されていない。**
2. `_stage0_t_s_delta()` は good/common の**非加重平均**を取るので、空クラスの 0.0 が
   T/S/Δ を機械的に半分にしている (Opus TASK-POST LOW-3 が defer した論点が、実データで
   実害のある形になった)。

**verdict への影響を実測で確認した (反転しない)**:

| 扱い | \|Δ_int − Δ_ext\| | F4 (機序不在) | t_driven |
|---|---|---|---|
| 凍結実装 (good/common 平均、good = 0.0 fallback) | 0.234289 | False | False (S 由来) |
| 参考: common のみ (空クラスを混ぜない) | 0.468577 | False | False (S 由来) |

どちらでも F4 は成立せず、由来判定も S のまま。**判定規則は書き換えていない** — 凍結実装の
値がそのまま verdict に入っている。参考行は「もし空クラスを混ぜなかったら結論が変わるか」を
確かめるための**事後の感度確認**であって、判定に使っていない。

### 突き合わせた対応 (`scope.json` の数字 ↔ 何と照合したか)

| `scope.json` の値 | 何と突き合わせたか | 結果 |
|---|---|---|
| `stage1.eligible_fraction = 0.8` | 独立診断が同じ配線で再計算した値 | 一致 |
| `stage1.drop_p5/p95/median = 0.0` | 500 replicate の `auc_full − auc_lao` 実分布 (494 件が厳密 0) | 一致・非潰れを確認 |
| `stage2.cells[*].arm_s.verdict = PASS` | 凍結 `decide_external()` の出力 | 一致 |
| `stage2.cells[*].tau_calibration.tau_star` | `argmin|ρ_ext(τ) − ρ_int|` を `rho_by_tau` から手計算 | 一致 (BLOCK 0.45 / PARITY 0.50) |
| `stage0.*.n_good = 0` | engaged 述語の定義 + コーパス側の実 good 件数 (287) | フォールバックであることを確認 |
| `verdict.fail_reason = null` | F1-F7 の各述語を実値で再評価 | 一致 (どれも立たない) |
| `verdict.verdict = DO_NOT_WRITE` | `write_eligible ∧ condition_c_supported` = `True ∧ False` | 一致 |
| pin (b) | G1 実測値 `auc_full 0.863122` / `auc_lao 0.839575` / `potency 0.375293` / `PASS` / survivors | `--fidelity` exit 0 で一致 |

## Limitations (design-final.md §8、8 項目必須)

1. <!-- LIMITATION:rho-is-proxy --> **ρ は S (残存被覆) の proxy であって
   代数的対応物ではない** (design-final.md §2.1 MEDIUM-1)。ρ は
   anchor--anchor の量、S は 項目--anchor の量であり、対応の妥当性は
   Stage 0 の実測 (ρ と S の並置) で記述的に示すだけである。
2. <!-- LIMITATION:tau-star-upstream-factor --> **τ* の較正は外部 anchor
   プールの幾何を使う** (design-final.md §2.4)。verdict は見ていないが、
   同じ幾何は AUC/LAO の上流因子である。ラダー全段と隣接段の感度を主表に
   出すことで緩和するが、消えてはいない。
3. <!-- LIMITATION:arm-s-constructed --> **ARM-S は我々が構成した配置**
   であり、実在のスコアラ運用がそうしている証拠ではない。条件 C は
   「そう作ると壊れる」であって「みんなそう作っている」ではない。
4. <!-- LIMITATION:c4-most-circular --> **内部 C4 は G1 ADR §2 が
   「最も circular な配置」と明記した候補**であり、ρ_int の主基準である
   (design-final.md §2.3 併記必須)。
5. <!-- LIMITATION:t-driven-not-rejected --> **T 由来の可能性は棄却して
   いない** (design-final.md §1 HIGH-3)。T 側の検査 (ARM-X / T 四分位
   層別) は探索的にとどまり、verdict には使わない。
6. <!-- LIMITATION:ocsai-brick-weight-concentration --> **Ocsai は brick
   に重みが集中する** (SPLIT-BLOCK で weight_share 0.644、G1 の実測値)。
   セル別 `object_weights` を必ず出す (design-final.md §3 LOW-2)。
7. <!-- LIMITATION:cambridge-underpowered --> **Cambridge は検出力不足
   であり確証には使わない** (G1 baseline で両分割
   `INCONCLUSIVE_UNDERPOWERED`)。本タスクでも Cambridge は報告 + 非矛盾
   のみに使う (§4 F5)。
8. <!-- LIMITATION:codex-70-80-percent-inconclusive --> **Codex の見立て
   では「特定できない」に倒れる確率は 70-80%** (design-final.md 凍結時の
   `codex-review.md` 末尾の見立て、そのまま記録)。

### 実走で発見した追加 Limitations (9-11、事前登録済みの 8 項目とは別)

以下は **2026-09-09 の実走で初めて分かったこと**であり、design-final.md §8 の凍結 8 項目には
含まれない。**判定規則は一切変えていない** (これらは verdict を反転させないことを実測で
確認済み)。事前登録した 8 項目と混同しないよう節を分けて記録する。

9. <!-- LIMITATION:stage1-cannot-separate-deflation-from-no-collapse -->
   **Stage 1 の「deflation 棄却」は、内部崩落が小標本効果でないことの積極的証拠には
   ならない。** 縮小 replicate の drop が 0 に張り付く原因は縮小そのものではなく、
   **縮小前から Ocsai の drop が 0.000152 しかない**ことである (LAO で値が変わる項目は
   1279 中 41 件のみ)。したがって Stage 1 は「小標本は崩落を作らない」と
   「このコーパスはそもそも崩落しない」を**区別できない**。G1 (PR #95) の
   「外部 2 コーパスとも崩落せず」が Stage 1 の水準で再出現したものである。
   事前登録の判定規則 (帯が 0.2350 を含むか) は満たしているが、
   **対立仮説の棄却として読むには検出力の前提が成立していない。**
10. <!-- LIMITATION:stage0-good-class-empty -->
    **Stage 0 の good クラスは内部・外部とも空 (`n_good = 0`) であり、
    ラベル層別の残存被覆差 `s_common_minus_s_good` は推定されていない**
    (`mean_s_common` と厳密一致する)。engaged 述語が「anchor への近似重複」である以上、
    good (創造的) 応答は構造的に engaged に入らない。design-final.md §3 MEDIUM-5 /
    §2.1 MEDIUM-1 が要求した層別診断は、**この engaged 定義の下では原理的に空になる**。
    加えて `_stage0_t_s_delta()` の非加重平均が空クラスの 0.0 を混ぜるため T/S/Δ が
    機械的に半減している (Opus TASK-POST LOW-3 の defer 分が実害化した)。
    **F4 と由来判定はどちらの扱いでも反転しないことを実測で確認済み** (「出力 JSON の
    意味突き合わせ」参照)。
11. <!-- LIMITATION:brick-dominates-verdict -->
    **主判定は事実上 brick 1 物体に支配されている** — セル別 `object_weights` の実測で
    brick が SPLIT-BLOCK 0.699180 / SPLIT-PARITY 0.600098 を占める。
    Limitation 6 が G1 実測 0.644 を引いて警告していた集中は、**本走でさらに強かった**
    (BLOCK)。両分割合意 (§3 Stage 2 条件 2) は独立な 2 証拠というより、
    同じ支配的物体を 2 通りに切り直したものに近い。

<!-- PREREGISTRATION-AMENDMENT:stage1-three-state -->
**事前登録の修正 (DA-SC-19、隠さず明記)**: 事前登録は **2026-09-08 に
一度修正されている** --- 実測前、Stage 1 の結果語彙を二値
(`deflation_supported: bool`) から三状態
(`STAGE1_OUTCOME_ENUM = ("DEFLATION_SUPPORTED", "DEFLATION_REJECTED",
"INCONCLUSIVE")`) へ拡張した。理由: 旧契約は「判定不能」を
`deflation_supported=False` に潰しており、design-final.md §5 の出口表では
これが「deflation 棄却」= 書く方向の前提として通ってしまう欠陥があった
(Codex TASK-PRE HIGH-3 が検出)。三状態化はバイアスを閉じる方向にしか
動かない (`decide_scope()` が `"WRITE"` を出せるのは
`stage1_outcome == "DEFLATION_REJECTED"` のときだけであり、
`not deflation_supported` から書く権利を導出することを禁止した --- AC で
pin 済み)。修正は測定を一度も走らせていない段階で行われており、実測後の
tune-to-pass (S1/S2) ではない。

## 逸脱・気づき

- **base 検証**: `git reset --hard cf501ff` (Merge I-006) から着手。
  anchor 5 個 / `85 passed, 1 skipped` を確認 (skip 対象は
  `test_dense_cell_reproduces_g1_arm_a`、`ERRE_RUN_REAL_MPNET_TESTS=1`
  で opt-in する実データ test --- 本 issue の boundary によりこのセッション
  では opt-in していない)。
- **`--fidelity` の exit code を 3 値に拡張した**
  (`FIDELITY_EXIT_OK=0` / `FIDELITY_EXIT_MISMATCH=1` /
  `FIDELITY_EXIT_SOURCE_UNAVAILABLE=2`)。G1 の `--fidelity`
  (`scripts/paper01_external_audit.py`) は 0/1 の 2 値だが、本 issue の
  orchestrator 指示 (「データが無い」と「不一致」を混同しない) を満たす
  ため、本タスク独自の 3 値スキームを採用した。**`scripts/
  paper01_external_audit.py` 自体は一切変更していない** (import のみ)。
- **Cambridge ARM-S セルの τ*/k* に SPLIT-BLOCK を使う、という設計判断**
  は design-final.md が明示的に凍結していない実装レベルの選択である
  (DA-SC-17 が「dataclass のフィールド名は研究設計の分岐でない」と
  区別したのと同種の区別) --- `_CambridgeGather` のドキュストリングに
  理由 (`SPLIT_SCHEMES` の `role="primary"` / `run_cambridge_audit` の
  `"primary_split": "SPLIT-BLOCK"` という既存の慣例を踏襲) を明記した。
  もし I-007b の実走前にこの選択に異論が出た場合は、実走前に決定を
  変えることは S1/S2 に抵触しない (まだ測っていないため)。
- **τ* 隣接段の single-point-dependence チェック**は、隣接段のセルを
  「主グリッドと同じ共通 active object 交差」で再スコアする実装にした
  (design-final.md はこの詳細を明示していない)。理由と代替案の非採用は
  `build_split_cells()` のドキュストリングに明記した。
- **run_gate.py / build_metrics.py は `experiments/20260907-paper01-g1/`
  の同名スクリプト (issue 008 の成果物) をほぼそのまま踏襲**した ---
  SHA-256 byte-identity gate (`hashes_match`)・completion marker
  (`run_sh_has_completion_marker`)・Limitations 完全性チェック
  (`notes_has_required_limitations`) の 3 パターンは同一。8 項目化と
  DA-SC-19 の事前登録修正マーカーのみ本タスク独自に追加した。

### I-007b (実走、2026-09-09) の逸脱・気づき

- **`--fidelity` を run.sh とは別に単独で先に回した** (Gate 1)。run.sh も内部で
  `--fidelity` を回すが、pin (b) が不一致なら **`--scope` に金を掛ける前に止める**ため。
  実際には一致したのでそのまま run.sh を通した。**この pin の初回実行は I-007b であり、
  I-007a までは一度も走っていない** (blockers.md ブロッカー 3)。
- **Ocsai はネットワークから取得したが、ディスクへは書いていない。**
  `load_ocsai_raw_bytes()` が `_fetch_ocsai_splits()` をメモリ上で呼ぶだけで、
  G1 の「取得のみ・再配布しない (来歴グレーゾーン)」の扱いを踏襲している。
  `--fidelity` と `--scope`×2 で計 5 回の取得が走った。
- **完了判定に tqdm 最新行を使っていない** (`feedback_log_tail_completion_marker`)。
  `run.log` 末尾の JSON completion marker + `RUNSH_EXIT=0` + python プロセス消滅の
  3 点で判定した。
- **自分が起動していないプロセスに一切触っていない** (このタスクで I-001b の executor が
  他者の pytest を強制終了した事故の再発防止)。
- **実走中はリポジトリのファイルを触っていない** (G1 で mutation と CI を並走させて
  結果が信用できなくなった前例)。診断スクリプトはリポジトリ外 (scratchpad) に置き、
  凍結 apparatus は import のみ。
- **Stage 1 の active 物体はセルの共通交差ではない** — `_stage1_result()` は
  `active_objects_for_cell(dense_k_max)` (13 物体) を使い、`scope.json` の
  `stage2.cells[*].arm_a.active_objects` (DA-SC-3 の 4 セル共通交差で 7 物体) とは
  別集合である。診断でこの差を確認した上で `_stage1_result()` の配線を忠実に再現している
  (両者を取り違えると Stage 1 の数字が再現しない)。
- **判定規則・凍結値・`design-final.md` は結果を見た後も一切変更していない。**
  意味突き合わせで出てきた「空クラスを混ぜない場合」の数字は**感度確認**として併記した
  だけで、verdict は凍結実装の出力のままである。

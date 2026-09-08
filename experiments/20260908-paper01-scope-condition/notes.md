# paper01 scope condition — notes (issue 007a: run.sh 一式 + notes.md 骨格)

**このファイルは I-007a (実走の前段) の成果物である。「結果」節は
プレースホルダのみで、実測値・verdict は一切含まない。実走 (I-007b、別
セッション、user 裁定を経て実施) の後に埋める。**

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

(未実走 — I-007b で埋める)

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

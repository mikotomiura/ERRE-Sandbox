# mutation-log — 統合版 (paper01 scope condition、全 issue)

**I-007b (2026-09-09) が全 issue 分を 1 ファイルに統合したもの。**
issue 007 Scope In「`results/mutation-log.md` の統合 (**全 issue 分**)」および
Codex TASK-PRE MEDIUM-5 (issue ごとに `mutation-log-I00X.md` に分けて書き、
統合は I-007 が行う) に従う。

**要約していない。** 各 issue のログを**そのまま順に束ねた**。
個別ファイル (`mutation-log-I001b.md` 〜 `mutation-log-I007a.md`) は
出所として残してある (削除していない)。

## 総計

| issue | mutant 数 | KILLED | 生存 | 備考 |
|---|---|---|---|---|
| I-001 | 19 | 19 | 0 | M13 の恒真化は 001-2 生存 / 001-3 単独 kill の非対称性を実測 |
| I-001b | 11 | 11 | 0 | 核心 = `INCONCLUSIVE`→`DEFLATION_REJECTED` の丸め |
| I-002 | 7 | 7 | 0 | M1/M6 は専用境界 fixture のみが kill することを実測で是正 |
| I-003 | 15 | 14 | 1 | 生存 1 件は**数学的に到達不能な同値 mutant** (理由をログに明記) |
| I-004 | 7 | 7 | 0 | 三状態の境界 3 mutant は専用 test が単独 kill |
| I-005 | 11 | 11 | 0 | 核心 = `not deflation_supported` から書く権利を導出する差し戻し |
| I-006 | 8 | 8 | 0 | パイプライン順序 / τ\* tie-break / 4 セル交差の union 化 |
| I-007a | 7 | 7 | 0 | 3 ファイル (CLI + run_gate + build_metrics) を SHA-256 で復元確認 |
| **合計** | **85** | **84** | **1** | 生存 1 は同値 mutant (実行不能な差異) |

TASK-POST 反映時に追加で 1 mutant を当てている
(`decide_scope()` の fail-closed を元実装へ差し戻す → 新規
`test_missing_ocsai_split_can_never_produce_write` が単独 kill、1 failed / 130 passed)。
詳細は `.steering/20260908-paper01-scope-condition/decisions.md` DA-SC-22。

---


<!-- ================= I001 ================= -->

# mutation-log — Loop I-001 (paper01 scope condition, AC 001-MUT)

対象: `scripts/paper01_scope_condition.py` (Loop I-001 スコープ = 冒頭の
paths/constants/preregistration + 共有 dataclass 契約のみ、Stage 0-2 のロジックは
まだ無い)。方式: `.venv/Scripts/python.exe` 経由で対象ファイルを 1 mutant ずつ
文字列置換 → `pytest -q tests/test_paper01_scope` を実行して exit code を記録 →
元のテキストへ復元 → 復元後の byte 一致を assert、を機械的に 19 件繰り返した
(スクリプト: scratchpad `mutate_paper01_scope.py`、リポジトリ外の使い捨てツール)。

**二重確認 (G1 の反省を binding で持ち込む)**: 19 mutant すべてで
`assert old in s` (置換対象が現在のソースに存在する) と `assert new != old`
(置換が no-op でない) を実施 (すべて pass、置換の空振りはゼロ件)。加えて
`original.count(old) == 1` (置換位置の一意性) と、書き込み直後に
`assert new in on_disk` (実際にディスクへ反映されたこと) も確認した。
最終復元は `restored == original` の byte 比較で確認し、スクリプト末尾の
`final restore check` と `git status --porcelain scripts/` (対象ファイル以外に
差分なし) の両方で裏取りした。

## I-001 のスコープにおける「境界述語」の棚卸し

I-001 に実装ロジックは薄く (Stage 0-2 の判定式は I-002 以降)、`>` vs `>=` /
`min`/`max`/`argmin` の向きに相当する述語は**まだ存在しない**
(design-final.md §9 の凍結値表そのものと、`config_matches_preregistration` の
等値比較、`collect_preregistration` の read-through 配線のみ)。したがって
本ラウンドの mutation は下記の 3 カテゴリで**機械的に総当たり**した:

1. **凍結定数の値・順序・構成を壊す** (M1-M12, M17): 各定数が
   `collect_preregistration()` → `config.json` の往復比較 (AC 001-2) と、
   個別 AC (001-4/001-5/001-6/001-7/001-8) の**両方**から守られているかを検証
2. **read-through 配線そのものを壊す (「恒真でない」ことの直接証明、AC 001-1/001-3)**
   (M13-M16): `config_matches_preregistration` の等値比較自体を壊す、および
   `collect_preregistration()` 内の `_c.AUC_FLOOR` / `_g1.MIN_CLASS_N` 読み出しを
   ハードコード値へ書き換える — これが通ると「import して再定義しない」という
   AC 001-1 の主張が空証明になる、最も重要な mutation
3. **共有 dataclass 契約が本当に凍結されているか** (M18-M19): `frozen=True` の
   剥奪、フィールド名の改変

## mutant 一覧と結果 (全 19 件 KILL、生存 0 件)

| # | 対象 | 置換内容 (要約) | pytest exit | 判定 | kill した AC |
|---|---|---|---|---|---|
| M1 | `SEED` | `20260908` → `1` | 1 (3 failed) | KILLED | 001-2, 001-3(前提), 001-4 |
| M2 | `STAGE1_REPLICATES` | `500` → `501` | 1 (2 failed) | KILLED | 001-2 |
| M3 | `STAGE1_DRAW_INDEX` | `0` → `1` | 1 (2 failed) | KILLED | 001-2 |
| M4 | `STAGE1_INTERNAL_DROP_REF` | `0.2350` → `0.3350` | 1 (2 failed) | KILLED | 001-2 |
| M5 | `DELTA_MATERIAL_EPS` | `0.01` → `0.02` | 1 (2 failed) | KILLED | 001-2 |
| M6 | `TAU_GRID` 先頭 2 要素 | `0.90,0.85` → `0.85,0.90` (降順崩し) | 1 (2 failed) | KILLED | 001-2, 001-5 (`sorted(reverse=True)` 不一致) |
| M7 | `TAU_GRID` 末尾 | `0.40` → `1.05` (レンジ逸脱) | 1 (3 failed) | KILLED | 001-2, 001-5 (`0<τ<1` 逸脱) |
| M8 | `TAU_GRID` 末尾 | `0.40` → `0.90` (重複混入) | 1 (3 failed) | KILLED | 001-2, 001-5 (`len(set)==len` 崩壊 + 降順崩し) |
| M9 | `DELTA_TS_CANDIDATES` | 末尾に `"X1"` 追加 (7 要素化) | 1 (3 failed) | KILLED | 001-2, 001-7 (完全一致・要素数チェック) |
| M10 | `FAIL_PRECEDENCE` 先頭 2 要素 | `F4,F1` → `F1,F4` (先頭崩し) | 1 (3 failed) | KILLED | 001-2, 001-8 (`precedence[0]=="F4"`) |
| M11 | `FAIL_PRECEDENCE` | `F7` を欠落 (6 要素化) | 1 (3 failed) | KILLED | 001-2, 001-8 (集合・件数チェック) |
| M12 | `STAGE1_INTERNAL_GOOD_COUNTS` 先頭要素 | `3` → `4` (合計 26 に) | 1 (3 failed) | KILLED | 001-2, 001-6 (sum/多重集合不一致) |
| M13 | `config_matches_preregistration` | 本体を `return True` に変更 (恒真化) | 1 (1 failed) | KILLED | **001-3 のみ** (001-2 は生存 = 想定通り、下記コメント参照) |
| M14 | `config_matches_preregistration` | `==` → `!=` (反転) | 1 (2 failed) | KILLED | 001-2, 001-3 |
| M15 | `collect_preregistration` 内 `auc_floor` | `_c.AUC_FLOOR` 読出し → `0.8` 直書き | 1 (1 failed) | KILLED | **001-1 のみ** (monkeypatch 追随が消える) |
| M16 | `collect_preregistration` 内 `min_class_n` | `_g1.MIN_CLASS_N` 読出し → `16` 直書き | 1 (1 failed) | KILLED | **001-1 のみ** |
| M17 | `SCOPE_VERDICT_ENUM` | `("WRITE","DO_NOT_WRITE")` → 順序反転 | 1 (2 failed) | KILLED | 001-2 (AC 表に無い追加定数も往復比較で保護されることの確認) |
| M18 | `DeltaDecomposition` | `frozen=True` を剥奪 | 1 (1 failed) | KILLED | 001-9 (`FrozenInstanceError` が上がらなくなる) |
| M19 | `DeltaDecomposition` | フィールド `rho` → `rho2` に改名 | 1 (1 failed) | KILLED | 001-9 (フィールド集合の完全一致チェック) |

**総括: 19 mutant 全 KILL、生存 0 件。**

## 注記: M13 で 001-2 が「生存」する理由 (恒真化の非対称性、意図通り)

M13 (`config_matches_preregistration` を `return True` に恒真化) を適用すると
AC 001-2 (`test_config_matches_preregistration`) 自体は **pass のまま**
(オンディスクの config は元々正しいので `True` を期待する 001-2 は
たまたま巻き添えを食わない)。これを「生存」と誤読しないために **AC 001-3
(`test_config_mismatch_is_detected`)** を独立に置いている —
M13 適用下では 001-3 の `assert not mod.config_matches_preregistration(on_disk)`
(monkeypatch 後に False を期待する) が **恒真化のせいで必ず失敗する**。
実測でも M13 は exit 1 (1 failed) で 001-3 だけが落ちており、**設計通り
「001-2 だけでは恒真化を検出できず、001-3 が無いと見逃す」を実地で確認できた**
(design-final.md §7 Test Plan がまさにこの非対称性を理由に 001-3 を要求している)。

## 出力 JSON の意味突き合わせ (mutation 後、design-final.md §7 の必須工程)

mutation 実施後、復元済みの `config.json` を実際に読み込んで各値の**意味**を
突き合わせた (スキーマ形状だけでなく数字そのものを確認):

```
seed                       = 20260908   (SEED ファイルと一致)
tau_grid                   = [0.9 .. 0.4] 全 11 要素、降順・重複なし
fail_precedence            = [F4, F1, F2, F3, F5, F6, F7]  (F4 先頭・F1-F7 過不足なし)
stage1_replicates          = 500, stage1_draw_index = 0
stage1_internal_drop_ref   = 0.235  (design-final.md §9 の 0.2350 と一致)
stage1_internal_good_counts合計/長さ = 25 / 16  (封印済み gold の実測 sum/len と一致)
delta_ts_candidates        = [X0, X3a, X3b, X3c, C0, C4]  (純 max-cos のみ、X1/X2 不在)
delta_material_eps         = 0.01
scope_verdict_enum         = [WRITE, DO_NOT_WRITE]
thresholds.auc_floor       = 0.8   (= es4_actuator.constants.AUC_FLOOR)
thresholds.ref_dedup       = 0.9   (= es4_actuator.constants.REF_DEDUP)
thresholds.n_r_min/n_r_max = 8 / 30
thresholds.ci_alpha        = 0.1
thresholds.n_resamples     = 10000
thresholds.min_class_n     = 16   (= paper01_external_audit.MIN_CLASS_N)
thresholds.anchor_draws    = 200  (= paper01_external_audit.ANCHOR_DRAWS)
```

design-final.md §9 の凍結値一覧と 1 対 1 で照合し、**数字の意味**まで
(単なる型・件数一致でなく) すべて一致することを確認した。不一致なし。

## 復元確認

- スクリプト末尾の `final restore check` で `TARGET.read_text() == original` を assert (pass)
- `git status --porcelain scripts/` は対象ファイルが依然 untracked (新規) のままで、
  意図しない差分は無い
- mutation 完了後に `pytest -q tests/test_paper01_scope` を再実行し `9 passed` を確認 (exit 0)

---

<!-- ================= I001b ================= -->

# Mutation log — Loop I-001b (contract fix: Stage1 tri-state + ScopeVerdict field + InternalReference owner + section anchors)

- **日時**: 2026-09-08
- **対象**: `scripts/paper01_scope_condition.py`（本 issue が触った差分のみ）
- **検証範囲**: `pytest -q tests/test_paper01_scope`（AC 001-1..001-9 + 001b-1..001b-8 全 15 test）
- **手法**: `feedback_witness_needs_mutation_testing` の規律に従い、判定行/契約を機械的に
  1 箇所ずつ壊す mutant を当て、test が落ちる (kill) か確認する。各 mutant で
  `assert old in s` → `assert new != old` → 書込み → `assert new in on_disk` → verify 実行 →
  復元 → **復元後の byte 一致を SHA-256 で assert**、の手順を自動化したハーネスで実施
  (`C:\Users\johnd\AppData\Local\Temp\claude\C--ERRE-Sand-Box\f33f2702-2785-4497-8a5a-f5a9ee7b5619\scratchpad\mutate_001b.py`)。
- **注意 (ツール側の学び)**: 本ファイルは Windows チェックアウトで一貫して CRLF
  (595/595 行が `\r\n`、bare LF 0)。`pathlib.Path.write_text()` のデフォルト
  universal-newline 変換に頼ると、`\n` 空間での mutate → 書込み → 復元の往復で
  意図せず改行コードが正規化され、**内容は正しいのに SHA-256 不一致になる**
  false failure を最初に踏んだ (M1 の 1 回目の試行)。修正: 読込時に `\r\n → \n` を
  明示変換してマッチングし、書込み時に `\n → \r\n` を明示変換してから
  raw bytes で書く方式に変更し、以後は正しく動作した。

## Mutant 一覧 (11 件、生存 0)

| # | 対象 | 変更内容 | 期待 kill 理由 (AC) | 結果 | kill した test |
|---|---|---|---|---|---|
| M1 | `STAGE1_OUTCOME_ENUM` | `"INCONCLUSIVE"` → `"DEFLATION_REJECTED"` (issue 001b-MUT 名指しの mutant。3 状態を 2 状態に潰す) | 001b-1, 001b-4, 001-2/001-3 | **KILLED** | `test_config_matches_preregistration`, `test_config_mismatch_is_detected`, `test_stage1_outcome_enum_is_frozen`, `test_inconclusive_is_not_rejection` |
| M2 | `STAGE1_OUTCOME_ENUM` | 先頭 2 要素を入れ替え (順序破壊) | 001b-1 (順序込み凍結) | **KILLED** | `test_config_matches_preregistration`, `test_config_mismatch_is_detected`, `test_stage1_outcome_enum_is_frozen` |
| M3 | `Stage1Result` | `drop_p5_eligible` フィールドを削除 | 001b-3, 001b-8 | **KILLED** | `test_shared_result_contracts_are_frozen`, `test_stage1_result_contract_is_extended`, `test_inconclusive_is_not_rejection` |
| M4 | `Stage1Result` | `n_objects_pool_short: int` → `float` (型のみ改変) | 001b-3, 001b-8 | **KILLED** | `test_shared_result_contracts_are_frozen`, `test_stage1_result_contract_is_extended` |
| M5 | `ScopeVerdict` | `t_confound_note_required` フィールドを削除 | 001b-5, 001b-8 | **KILLED** | `test_shared_result_contracts_are_frozen`, `test_scope_verdict_contract_is_extended` |
| M6 | `InternalReference` docstring | 所有者を I-006 → I-002 に差し戻し | 001b-6 | **KILLED** | `test_internal_reference_owner_is_i006` |
| M7 | 節 anchor | I-002 anchor ブロックを削除 | 001b-7 | **KILLED** | `test_section_anchors_exist_in_order` |
| M8 | 節 anchor | I-003 と I-004 の anchor 順序を入れ替え | 001b-7 | **KILLED** | `test_section_anchors_exist_in_order` |
| M9 | `Stage1Result` | `frozen=True` → `frozen=False` | 001b-8 | **KILLED** | `test_shared_result_contracts_are_frozen` |
| M10 | `ScopeVerdict` | `frozen=True` → `frozen=False` | 001b-8 | **KILLED** | `test_shared_result_contracts_are_frozen` |
| M11 | `collect_preregistration()` | `"stage1_outcome_enum"` キー登録を削除 | 001b-1, 001b-2 | **KILLED** | `test_config_matches_preregistration`, `test_config_mismatch_is_detected`, `test_stage1_outcome_enum_is_frozen` |

**生存 mutant: 0 / 11。**

## AC 001b-MUT の核心 mutant (M1) の確認

issue 本文が名指しした mutant ("`INCONCLUSIVE` を `DEFLATION_REJECTED` に写す") は M1。
**4 本の test に同時に落ちる** ことを確認した。特に `test_inconclusive_is_not_rejection`
(AC 001b-4 の専用 test) が、`mod.STAGE1_OUTCOME_ENUM` から値を読んで
`Stage1Result` インスタンスを構築する構造になっているため、
この mutant で `inconclusive.stage1_outcome == rejected.stage1_outcome`
(両方とも `"DEFLATION_REJECTED"` に潰れる) となり、
`assert inconclusive.stage1_outcome != rejected.stage1_outcome` で失敗する
— これが「判定不能が棄却に潰れたら test が落ちる」の直接証拠。

## 出力 JSON の意味突き合わせ (mutation 後の追加工程)

`experiments/20260908-paper01-scope-condition/config.json` を再生成後、実読みして
`design-final.md` §9 (frozen pre-registration table) および新規
`stage1_outcome_enum` と 1 対 1 で突き合わせた:

- `stage1_outcome_enum`: `["DEFLATION_SUPPORTED", "DEFLATION_REJECTED", "INCONCLUSIVE"]`
  — design-final.md §3 Stage 1 の表 (:165) が凍結した「判定不能として記録」の語彙と一致。
  3 値・この順序であることを確認 (`test_stage1_outcome_enum_is_frozen` が pin)。
- 既存 8 キー (`seed` / `tau_grid` / `stage1_replicates` / `stage1_draw_index` /
  `stage1_internal_good_counts` / `stage1_internal_drop_ref` / `delta_ts_candidates` /
  `delta_material_eps` / `fail_precedence` / `scope_verdict_enum` / `thresholds`) は
  値が無変更であることを diff で確認 (`git diff` は `stage1_outcome_enum` の
  5 行追加のみ)。**余分なキー追加・既存値の意図しない変化はゼロ**。
- 意味欠落の再発防止チェック: `Stage1Result` / `ScopeVerdict` の新規フィールドは
  すべて issue 001b の Scope In 表と名前・型が完全一致することを
  `test_stage1_result_contract_is_extended` / `test_scope_verdict_contract_is_extended`
  で個別 pin 済み (G1 の反省 — 全 test 緑・全 mutant kill でも意味欠落が
  JSON を読んで初めて見つかった、を再演しないための工程)。

## 復元確認

全 11 mutant 適用後、`scripts/paper01_scope_condition.py` を SHA-256 で
mutation 前の on-disk バイト列と比較し、**完全一致**を確認
(`final restore hash match: True`)。mutation 後の最終 sanity run
(`pytest -q tests/test_paper01_scope`) も exit 0 (15 passed)。

---

<!-- ================= I002 ================= -->

# Mutation testing log -- Loop I-002 (疎化層: leader clustering / rho)

Target: `scripts/paper01_scope_condition.py` §「I-002: sparsification layer」
(`leader_cluster_indices` / `reference_redundancy` / `corpus_redundancy`).
Test suite: `tests/test_paper01_scope/test_sparsify.py` (plus the pre-existing
`tests/test_paper01_scope/test_preregistration.py`, run in the same invocation
so a mutant that happens to break I-001/I-001b contracts would also surface).

Per `feedback_witness_needs_mutation_testing` / issue 002 AC 002-MUT: each
mutant below was **actually applied to the file, actually run through
pytest, and the failing test id(s) below are the real observed output** --
not an assumption about which assertion "should" catch it. Driver script
(`assert old in s` before mutating / `assert new != old` / `assert new in
on_disk` after writing / SHA-256 restore check after every mutant) ran from
`C:/Users/johnd/AppData/Local/Temp/claude/.../scratchpad/mutate_i002.py`
against this worktree's copy of the target file; the file was restored to
its pristine, hash-verified byte-identical state after every single mutant,
including after the final one (verified again at driver exit).

Command per mutant: `pytest -q tests/test_paper01_scope -v` (27 collected:
15 pre-existing + 12 new), full stdout+stderr captured, "short test summary
info" `FAILED <nodeid> - <reason>` lines parsed for the table below.

## Enumerated mutants (all 4 issue-mandated categories covered)

| id | category (issue text) | target |
|---|---|---|
| M1 | `<` vs `<=` | `leader_cluster_indices`: `cos.max() < radius` |
| M2 | `cap` 比較 | `leader_cluster_indices`: `len(kept) >= cap` |
| M3 | `max` vs `min` | `reference_redundancy`: `sims.max(axis=1)` |
| M4 | `r' ≠ r` の除外 | `reference_redundancy`: `np.fill_diagonal(sims, -np.inf)` dropped |
| M5 | 平均の分母 | `reference_redundancy`: `.mean()` -> `.sum()` |
| M6 | `<` vs `<=` (boundary) | `reference_redundancy`: `n < 2` -> `n <= 2` |
| M7 | 平均の分母 (unweighted vs weighted) | `corpus_redundancy`: simple mean -> size-weighted mean |

## Results

### M1: `leader_cluster_indices` `cos.max() < radius` -> `<= radius`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_sparsify.py::test_leader_cluster_boundary_equality_is_excluded`
- note: **not** caught by `test_leader_cluster_matches_greedy_dedupe_at_ref_dedup`
  (AC 002-1's random battery) -- an exact `cos == radius` tie has probability
  ~0 for continuously-sampled random unit vectors, so a dedicated
  exact-tie fixture (`A=(1,0)`, `B=(0.5, sqrt(3)/2)`, `cos(A,B)=0.5` exactly)
  was required. This confirms the random AC 002-1/002-2 tests alone would
  **not** have killed this mutant -- the dedicated boundary test is
  load-bearing, not redundant.

### M2: `leader_cluster_indices` cap check `>= cap` -> `> cap`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_sparsify.py::test_cap_truncates_prefix`
- note: killed via the `len(capped) <= cap` assertion -- the fixture
  (20 near-orthogonal 20-D points, `cap=5`) is specifically built so the
  uncapped run keeps far more than `cap`, guaranteeing the off-by-one
  produces a real length violation rather than a vacuous pass.

### M3: `reference_redundancy` `sims.max(axis=1)` -> `sims.min(axis=1)`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (4): `test_reference_redundancy_known_configurations`,
  `test_reference_redundancy_two_refs_not_degenerate`, `test_rho_is_not_max_pairwise`,
  `test_corpus_redundancy_is_unweighted`
- note: the last one fails only because `corpus_redundancy`'s expected
  values (0.5 unweighted mean) are computed from correct
  `reference_redundancy` output -- a cascading kill, not an independent
  witness of the `max`/`min` swap itself; the first three are the direct
  witnesses.

### M4: `reference_redundancy` drop `r' != r` exclusion (no `fill_diagonal`)

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (4): identical set to M3 (see above)
- note: with self-similarity (`cos(r,r)=1.0`) left in, every row max is
  forced to `1.0` regardless of geometry -- caught most directly by the
  orthogonal-set branch of `test_reference_redundancy_known_configurations`
  (expected ~0.0, mutant produces 1.0).

### M5: `reference_redundancy` denominator `.mean()` -> `.sum()`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (4): identical set to M3/M4 (see above)
- note: most directly caught by the all-identical branch of
  `test_reference_redundancy_known_configurations` (expected exactly
  `1.0`; a 5-row sum-of-ones instead of a mean returns `5.0`) and by
  `test_reference_redundancy_two_refs_not_degenerate` (expected `0.3`,
  sum-of-two returns `0.6`).

### M6: `reference_redundancy` boundary `n < 2` -> `n <= 2`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (2): `test_reference_redundancy_two_refs_not_degenerate`,
  `test_corpus_redundancy_is_unweighted`
- note: **not** caught by `test_reference_redundancy_known_configurations`
  or `test_rho_is_not_max_pairwise` (both use `n=4` or `n=5`, unaffected by
  a `n==2` boundary shift) or by `test_reference_redundancy_degenerate`
  (that AC's own fixtures are `n=0`/`n=1`, already degenerate under either
  predicate). Confirms the dedicated `n==2` boundary fixture is the one
  and only witness for this specific off-by-one -- exactly the kind of gap
  `feedback_witness_needs_mutation_testing` warns about. The
  `test_corpus_redundancy_is_unweighted` fixture also fails as a
  cascading effect because its object `"a"` has exactly 2 references.

### M7: `corpus_redundancy` unweighted mean -> object-size-weighted mean

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_corpus_redundancy_is_unweighted`
- note: this is the AC 002-9-dedicated witness by design (unweighted 0.5
  vs. size-weighted 0.25 for the 2-ref/6-ref fixture); confirmed it does
  **not** touch `test_corpus_redundancy_empty_is_zero` (the `if not
  by_object: return 0.0` early-return guard is untouched by this mutant,
  so that test correctly does not fire).

## Summary

- **7/7 mutants KILLED, 0 survivors.**
- All 4 issue-mandated predicate categories (`<` vs `<=`, `max` vs `min`,
  `cap` 比較, `r' ≠ r` の除外) plus the two "平均の分母" cases (the
  per-object mean inside `reference_redundancy`, and the cross-object mean
  inside `corpus_redundancy`) are each covered by at least one **dedicated**
  test whose failure was directly observed, not inferred.
- Two witnesses (M1's boundary-equality test, M6's `n==2` test) were only
  discovered to be load-bearing by actually running the mutation -- the
  random-battery ACs (002-1/002-2) do **not** kill them, matching this
  task's binding instruction to observe the real kill path rather than
  assert it from the docstring alone.
- File restore verified byte-identical (SHA-256) to the pristine pre-mutation
  content after every one of the 7 mutants and again at driver exit.

## Post-mutation semantic cross-check (design-final.md §7 item 4)

design-final.md §7's mutation discipline item 4 ("mutation の後に「出力
JSON を読んで数字の意味を突き合わせる」工程を明示的に置く") targets the
downstream stages that emit a `results/*.json` artifact (Stage 0/1/2 +
`decide_scope()`, owned by I-003..I-007). I-002 is a pure geometry layer
with no JSON-emitting entry point of its own (`config.json` is I-001's,
untouched here) -- there is no output artifact to cross-check numbers
against at this issue's scope. The applicable analogue used here instead is
the **AC 002-6/002-8/002-9 hand-computed values** (`rho=0.0` for an
orthonormal set, `rho=1.0` for an identical set, `rho=0.495` for the
1-dense-pair-plus-2-orthogonal fixture, `corpus=0.5` for the 2-ref/6-ref
fixture) -- each is a value derived independently by hand from the §2.1
formula, not read back from the implementation itself, so a mutant that
silently produces a "plausible-looking" wrong number (e.g. M5's `sum`
instead of `mean`, which is still a valid float) is still caught by a
number that was worked out on paper first.

---

<!-- ================= I003 ================= -->

# Mutation testing log -- Loop I-003 (Stage 0 Δ = T − S decomposition)

Target: `scripts/paper01_scope_condition.py` §「I-003: Stage 0 -- Delta = T -
S decomposition」(`_engaged_flags` / `_engaged_class_means` / `split_delta` /
`delta_is_material` / `delta_attribution`). Test suite:
`tests/test_paper01_scope/test_delta.py` (10 new tests), run together with
the full `tests/test_paper01_scope` package (49 tests total: the 39
pre-existing I-001/I-001b/I-002/I-005 tests + these 10) so a mutant that
happens to break an earlier issue's contract would also surface.

Per `feedback_witness_needs_mutation_testing` / issue 003 AC 003-MUT: each
mutant below was **actually applied to the worktree's own copy of the file,
actually run through pytest, and the failing test id(s) below are the real
observed output** -- not an assumption about which assertion "should" catch
it. Driver script (`assert old in s` before mutating / `assert new != old` /
`assert new in on_disk` after writing / SHA-256 restore check after every
mutant) ran from
`C:\Users\johnd\AppData\Local\Temp\claude\C--ERRE-Sand-Box\f33f2702-2785-4497-8a5a-f5a9ee7b5619\scratchpad\mutate_i003.py`
against this worktree's copy of the target file, using `Path.read_bytes()` /
`Path.write_bytes()` throughout (no newline translation -- the target file is
LF-only, and `write_text()`'s universal-newline translation is the exact
CRLF-corruption gotcha `mutation-log-I001b.md` and `mutation-log-I005.md`
already recorded for this same file; this driver was written byte-safe from
the start). The file was restored to its pristine, hash-verified
byte-identical state after every single mutant, including after the final
one (`final restore hash match: True`, pristine SHA-256
`8633c8f0214258ea735dd12bc7af96b78aaacca5ff60395cecc5d8081f9bfbcb`, confirmed
again by an independent hash check and a full four-command verify pass after
the driver exited).

**Tooling incident hit and fixed mid-session (honest record, not omitted)**:
before running the harness proper, a manual debugging `sed` command was used
to hand-verify one mutant's effect outside the driver. Its companion restore
command (`cp scripts/paper01_scope_condition.py.bak ...`) referenced a
backup file that a `||`-guarded earlier `cp` had never actually created (the
first `cp` to `/tmp` had already succeeded, short-circuiting the `.bak`
fallback), so the restore silently failed and the mutation was left applied
to the worktree file for one exchange. This was caught immediately via
`grep` (both the docstring and code occurrences of
`ref_dedup=_c.REF_DEDUP` showed `ref_dedup=0.5`) and fixed directly with a
precise `Edit` before any further work, then reconfirmed with all four pinned
verify commands (green) and `git diff --stat` (only the intended I-003
insertion). No mutation was left in the committed state. This is recorded
here rather than silently smoothed over, per this task's own honesty
discipline (`feedback_forensic_raw_log_whitespace` / DA-SC-21's "witnesses
must not over-claim" precedent) -- and it is what surfaced the real M8 bug
below (see "gotcha" note under M8).

Command per mutant: `pytest -q tests/test_paper01_scope -v` (49 collected),
full stdout+stderr captured, `FAILED <nodeid>` lines parsed for the table
below.

## Enumerated mutants (15 total: 14 required-kill + 1 documented equivalent)

| id | category (issue text / design-final.md §7) | target |
|---|---|---|
| M1 | 境界述語 `>=` vs `>` | `delta_is_material`'s exact-`DELTA_MATERIAL_EPS` boundary (AC 003-9) |
| M2 | `1.0 ± 0.1` の下端 (inclusive→exclusive) | `delta_attribution`'s both-band `lo <= ratio` |
| M3 | `1.0 ± 0.1` の上端 (inclusive→exclusive) | `delta_attribution`'s both-band `ratio <= hi` |
| M4 | 境界述語 `>` vs `>=` **[EQUIVALENT, documented, not counted]** | `delta_attribution`'s final `delta_t > delta_s` |
| M5 | `T`/`S` の引き算の向き | `split_delta`'s per-item `delta_vals.append(t - s)` |
| M6 | `T`/`S` の定義の向き | `split_delta`'s `t = 1.0 - full` / `s = 1.0 - lao` |
| M7 | engaged 述語の閾値 (flag 側) | `split_delta`'s `if flag != 1.0: continue` |
| M8 | engaged 述語の閾値 (`REF_DEDUP` 側) | `_engaged_flags`'s `ref_dedup=_c.REF_DEDUP` hardcoded away |
| M9 | 平均の分母 (good) | `_engaged_class_means`'s `len(good)` → `len(values)` |
| M10 | 平均の分母 (common) | `_engaged_class_means`'s `len(common)` → `len(values)` |
| M11 | ラベル層別の割当 | `_engaged_class_means`'s `good` list selector `label == 1` → `label == 0` |
| M12 | ラベル層別の割当 (件数側) | `split_delta`'s `n_good` selector `label == 1` → `label == 0` |
| M13 | 適用範囲ゲート (AC 003-4 の核) | `split_delta`'s `if candidate not in DELTA_TS_CANDIDATES:` → `in` |
| M14 | `S_common - S_good` の引き算の向き | `s_common_minus_s_good=mean_s_common - mean_s_good` |
| M15 | 連言 `and` vs `or` | `delta_attribution`'s degenerate `delta_t == 0.0 and delta_s == 0.0` |

## Results

### M1: `delta_is_material` boundary `>=` -> `>`

```
-    return abs(delta_int - delta_ext) >= DELTA_MATERIAL_EPS
+    return abs(delta_int - delta_ext) > DELTA_MATERIAL_EPS
```

**KILLED** (exit 1). Failing: `test_delta_material_boundary` -- at exactly
`DELTA_MATERIAL_EPS` the mutant returns `False` instead of the frozen `True`
(AC 003-9's exact-boundary pin).

### M2: both-band lower bound made exclusive

```
-        if lo <= ratio <= hi:
+        if lo < ratio <= hi:
```

**KILLED** (exit 1). Failing: `test_delta_attribution_all_branches_reachable`
-- `delta_attribution(0.9, 0.0, 0.0, 1.0)` (ratio exactly `0.9` = `lo`) now
falls through to `"S"` instead of the frozen `"both"`.

### M3: both-band upper bound made exclusive

```
-        if lo <= ratio <= hi:
+        if lo <= ratio < hi:
```

**KILLED** (exit 1). Failing: `test_delta_attribution_all_branches_reachable`
-- `delta_attribution(1.1, 0.0, 0.0, 1.0)` (ratio exactly `1.1` = `hi`) now
falls through to `"T"` instead of the frozen `"both"`.

### M4: final T/S decision `>` -> `>=` [EQUIVALENT, diagnostic only]

```
-    return "T" if delta_t > delta_s else "S"
+    return "T" if delta_t >= delta_s else "S"
```

**SURVIVED (expected, confirmed equivalent)** (exit 0, no failures).

This mutant was run through the same harness as every other, not skipped --
its `SURVIVED` verdict is the actual observed outcome, and it is *not*
silently omitted from this log. Reasoning for why it cannot be killed under
the correctly-implemented spec: this line is reached only when `delta_s !=
0.0` (a `delta_s == 0.0` short-circuit at the guard above returns before
this line, except when `delta_t` is also `0.0`, itself intercepted even
earlier by the degenerate `both`-zero branch) and the both-band check above
it did *not* already return. `delta_t == delta_s` (both nonzero) always
produces `ratio == 1.0`, which is unconditionally inside `[0.9, 1.1]` --
so equality can never reach this final comparison at all, under the frozen
`1.0 ± 0.1` band definition itself (design-final.md §3). The `>`/`>=`
distinction on this line is therefore only observable via `delta_t ==
delta_s`, an input this implementation never lets arrive here. This was
verified empirically, not assumed: the mutant was applied and the full
49-test suite still passed. Not counted toward the "required-kill" count
below.

### M5: `T - S` subtraction direction flipped

```
-        delta_vals.append(t - s)
+        delta_vals.append(s - t)
```

**KILLED** (exit 1). Failing: `test_delta_matches_embed_rarity_max_agg`,
`test_delta_is_t_minus_s_not_s_minus_t` -- the latter test exists
specifically to isolate this sign with one item (`T=1.0`, `S=0.5` ->
`Δ=+0.5`; the mutant flips it to `-0.5`).

### M6: `T`/`S` definitions swapped

```
-        t = 1.0 - full
-        s = 1.0 - lao
+        t = 1.0 - lao
+        s = 1.0 - full
```

**KILLED** (exit 1). Failing: `test_delta_matches_embed_rarity_max_agg`,
`test_delta_is_t_minus_s_not_s_minus_t`, `test_label_stratified_means`,
`test_s_common_minus_s_good`.

### M7: engaged-flag keep predicate flipped

```
-        if flag != 1.0:
+        if flag != 0.0:
```

**KILLED** (exit 1). Failing: `test_delta_matches_embed_rarity_max_agg`,
`test_delta_is_t_minus_s_not_s_minus_t`, `test_label_stratified_means`,
`test_s_common_minus_s_good` -- this inverts which items are "engaged"
(keeps non-near-dup items, drops near-dup ones), breaking every fixture built
around the real engaged set.

### M8: `_engaged_flags`'s `REF_DEDUP` threshold hardcoded away

```
     return tuple(
-        _g1.near_dup_flags_from_similarity(max_sim_full, ref_dedup=_c.REF_DEDUP)
+        _g1.near_dup_flags_from_similarity(max_sim_full, ref_dedup=0.5)
     )
```

**KILLED** (exit 1). Failing: `test_engaged_predicate_matches_potency`.

**Gotcha hit and fixed while building this mutant (recorded honestly)**: the
identical string `_g1.near_dup_flags_from_similarity(max_sim_full,
ref_dedup=_c.REF_DEDUP)` appears **twice** in the source -- once inside this
function's own docstring (a literal restatement of the call, in double
backticks) and once in the actual executable `return` statement immediately
below it. A first version of this mutant's `old`/`new` pair used only the
bare call expression, which `str.replace(old, new, 1)` matched against the
**first** occurrence (the docstring) and left the real code line untouched --
the driver still reported `SURVIVED` because runtime behaviour genuinely had
not changed (verified by hand: `pytest -v` on the single test showed no
failure with only the docstring mutated). This was caught by the "expected
KILLED but got SURVIVED" mismatch the harness flags explicitly (`MISMATCH`
in its summary), not missed. Fixed by widening the `old`/`new` snippets to
include the surrounding `return tuple( ... )` lines, which are unique to the
code occurrence; re-running the harness after the fix shows the mutant
correctly `KILLED` above. This is exactly the discipline
`feedback_witness_needs_mutation_testing` asks for -- a witness's claimed
kill path was checked against the *actual* observed behaviour, a real gap
was found, and it was fixed rather than the log being written from
assumption.

### M9: `mean_good` denominator widened to the total engaged count

```
-    mean_good = float(sum(good) / len(good)) if good else 0.0
+    mean_good = float(sum(good) / len(values)) if good else 0.0
```

**KILLED** (exit 1). Failing: `test_delta_matches_embed_rarity_max_agg`,
`test_label_stratified_means`, `test_s_common_minus_s_good`.

### M10: `mean_common` denominator widened to the total engaged count

```
-    mean_common = float(sum(common) / len(common)) if common else 0.0
+    mean_common = float(sum(common) / len(values)) if common else 0.0
```

**KILLED** (exit 1). Failing: `test_delta_matches_embed_rarity_max_agg`,
`test_label_stratified_means`, `test_s_common_minus_s_good`.

### M11: good/common class assignment swapped inside `_engaged_class_means`

```
-    good = [v for v, label in zip(values, labels, strict=True) if label == 1]
+    good = [v for v, label in zip(values, labels, strict=True) if label == 0]
```

**KILLED** (exit 1). Failing: `test_delta_matches_embed_rarity_max_agg`,
`test_delta_is_t_minus_s_not_s_minus_t`, `test_empty_survivor_gives_full_coverage`,
`test_label_stratified_means`, `test_s_common_minus_s_good`.

### M12: `n_good`/`n_common` label swapped in `split_delta`'s own count

```
-    n_good = sum(1 for label in engaged_labels_t if label == 1)
+    n_good = sum(1 for label in engaged_labels_t if label == 0)
```

**KILLED** (exit 1). Failing: `test_delta_matches_embed_rarity_max_agg`,
`test_delta_is_t_minus_s_not_s_minus_t`, `test_empty_survivor_gives_full_coverage`,
`test_label_stratified_means`, `test_s_common_minus_s_good`.

### M13: candidate scope gate inverted (AC 003-4's core mutant)

```
-    if candidate not in DELTA_TS_CANDIDATES:
+    if candidate in DELTA_TS_CANDIDATES:
```

**KILLED** (exit 1). Failing: `test_delta_matches_embed_rarity_max_agg`,
`test_delta_is_t_minus_s_not_s_minus_t`, `test_empty_survivor_gives_full_coverage`,
`test_length_control_cancels_in_delta`, `test_mean_agg_candidate_is_rejected`,
`test_engaged_predicate_matches_potency`, `test_label_stratified_means`,
`test_s_common_minus_s_good` -- the widest blast radius of any mutant here,
as expected: this inverts *every* call's accept/reject outcome (valid
candidates now raise, X1/X2 now silently proceed).

### M14: `s_common_minus_s_good` sign flipped

```
-        s_common_minus_s_good=mean_s_common - mean_s_good,
+        s_common_minus_s_good=mean_s_good - mean_s_common,
```

**KILLED** (exit 1). Failing: `test_label_stratified_means`,
`test_s_common_minus_s_good` (AC 003-7's dedicated hand-computed check).

### M15: `delta_attribution`'s degenerate connective `and` -> `or`

```
-    if delta_t == 0.0 and delta_s == 0.0:
+    if delta_t == 0.0 or delta_s == 0.0:
```

**KILLED** (exit 1). Failing: `test_delta_attribution_all_branches_reachable`
-- `delta_attribution(0.0, 1.0, 0.0, 0.0)` (only `delta_t == 0.0`, `delta_s
!= 0.0`, expected `"S"`) now short-circuits to `"both"`.

## Summary

- **Required-kill set: 14/14 KILLED, 0 survived, 0 unexplained.**
- **Documented-equivalent set: 1 (M4), confirmed SURVIVED by actual
  execution, with the mathematical reason it is unreachable given the
  already-frozen `1.0 ± 0.1` band definition (not merely asserted).**
- Final restore verified byte-identical to pristine
  (`8633c8f0214258ea735dd12bc7af96b78aaacca5ff60395cecc5d8081f9bfbcb`) both
  by the driver's own SHA-256 check after every mutant and by an independent
  post-run hash check; all four pinned verify commands (`pytest -q
  tests/test_paper01_scope`, `mypy src`, `ruff check ...`, `ruff format
  --check ...`) re-confirmed green after the driver exited.

---

<!-- ================= I004 ================= -->

# Mutation testing log -- Loop I-004 (Stage 1 deflation test)

Target: `scripts/paper01_scope_condition.py` §「I-004: Stage 1 -- deflation
test」(`internal_shaped_replicates` / `_stage1_object_order` /
`_stage1_good_counts` / `_stage1_pool_short_objects` / `_stage1_seed` /
`same_object_pair_share` / `_stage1_auc_unweighted_by_object` /
`stage1_outcome` / `stage1_deflation_supported` / `stage1_drop_distribution`).
Test suite: `tests/test_paper01_scope/test_stage1.py` (24 tests), run together
with the full `tests/test_paper01_scope` package (59 tests total: the 35
pre-existing I-001/I-001b/I-002/I-005 tests + these 24) so a mutant that
happens to break an earlier issue's contract (e.g. `collect_preregistration`'s
read-through of `STAGE1_DRAW_INDEX`) would also surface.

Per `feedback_witness_needs_mutation_testing` and this issue's `## Allowed
Files` §「mutation testing (必須)」: each mutant below was **actually applied
to the worktree's own copy of the file, actually run through pytest, and the
failing test id(s) below are the real observed output** -- not an assumption
about which assertion "should" catch it. Driver script (`assert old in
original` before mutating / `assert on_disk == mutated` after writing /
SHA-256 restore check after every mutant, plus a final restore-hash
comparison at driver exit) ran from
`C:\Users\johnd\AppData\Local\Temp\claude\C--ERRE-Sand-Box\f33f2702-2785-4497-8a5a-f5a9ee7b5619\scratchpad\run_mutation_i004.py`
against this worktree's copy of the target file, using `Path.read_bytes()` /
`Path.write_bytes()` exclusively (never `read_text()`/`write_text()`, which
would apply universal-newline translation and could turn an LF-only checkout
into CRLF, corrupting the byte-identity restore check -- the same class of
gotcha `mutation-log-I001b.md`/`mutation-log-I005.md` recorded).

**Tooling gotcha hit and fixed (stale `__pycache__` bytecode cache, Windows
mtime resolution)**: the driver's first invocation ran `pytest` without
disabling Python's bytecode cache. Because the driver mutates, tests, and
restores the same source file multiple times within the same wall-clock
second, Windows' coarser filesystem mtime resolution let a stale `.pyc`
(compiled from a still-mutated version of the file) survive the restore and
get reused by a later `import` -- a fresh restore + full `pytest -q
tests/test_paper01_scope` run afterwards showed 3 spurious failures
(`test_deflation_band_both_branches`,
`test_reference_drop_on_band_boundary_is_supported`,
`test_mutant_band_open_interval_is_killed`) even though `inspect.getsource`
on the live module and a direct SHA-256 comparison both showed the on-disk
`.py` file was byte-identical to the pristine original. Deleting
`scripts/__pycache__` and re-running with `python -B` (module bytecode
writing disabled) confirmed the file was never actually corrupted -- it was
purely a bytecode-cache staleness artifact of the mutation loop's own rapid
writes. Fixed by (a) adding `-B -p no:cacheprovider` to every mutant's test
invocation in the driver and (b) clearing `__pycache__` before the final
recorded run and before every subsequent manual verify command in this
session. The results below are from the `-B`-flagged run; the four verify
commands were re-run clean (fresh `__pycache__`) immediately afterwards.

Command per mutant: `python -B -m pytest -q -p no:cacheprovider
tests/test_paper01_scope`, full stdout+stderr captured, `FAILED <nodeid>`
lines parsed for the table below.

## Enumerated mutants (7, all within this issue's own anchor section)

| id | category (issue text `## mutation testing (必須)` / 004-MUT) | target |
|---|---|---|
| M1 | 境界述語 `<=` vs `<` (**issue-named, eligible-fraction floor**) | `stage1_outcome`: `eligible_fraction <= _STAGE1_ELIGIBLE_FRACTION_FLOOR` relaxed to strict `<` |
| M2 | `"INCONCLUSIVE"` を `"DEFLATION_REJECTED"` に写す (**issue-named**) | `stage1_outcome`'s first branch return value |
| M3 | 帯の包含判定を開区間にする (**issue-named**) | `stage1_outcome`: `band_low <= reference_drop <= band_high` relaxed to strict `<` |
| M4 | `draw_index` の定数 | `STAGE1_DRAW_INDEX: Final[int] = 0` changed to `1` |
| M5 | 巡回割当の開始位置 | `_stage1_good_counts`: `STAGE1_INTERNAL_GOOD_COUNTS[i % n]` shifted to `[(i + 1) % n]` |
| M6 | pooled/層別の取り違え | `stage1_drop_distribution`'s pooled `auc_full`/`auc_lao` computed via `_stage1_auc_unweighted_by_object` instead of `_g1.auc_stratified` |
| M7 | `"DEFLATION_SUPPORTED"`/`"DEFLATION_REJECTED"` 取り違え | `stage1_outcome`'s two terminal return values swapped |

## Results

### M1: `eligible_fraction <= floor` relaxed to strict `<`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (2): `test_eligible_fraction_exactly_half_is_inconclusive`,
  `test_mutant_eligible_floor_strict_less_than_is_killed`
- note: **this is one of the three issue-mandated core mutants.** With the
  mutant applied, `eligible_fraction == 0.5` exactly falls through the first
  branch instead of returning `"INCONCLUSIVE"` -- both dedicated boundary
  tests assert `stage1_outcome(..., eligible_fraction=0.5) ==
  "INCONCLUSIVE"` directly and both failed under the mutant, confirming the
  `<=` (not `<`) floor is load-bearing exactly at the boundary.

### M2: `"INCONCLUSIVE"` folded into `"DEFLATION_REJECTED"`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (5): `test_median_draw_outcome_never_feeds_primary_outcome`,
  `test_eligible_fraction_exactly_half_is_inconclusive`,
  `test_ineligible_majority_is_recorded_as_undecidable`,
  `test_mutant_eligible_floor_strict_less_than_is_killed`,
  `test_mutant_inconclusive_folded_to_rejected_is_killed`
- note: **this is the issue's core mutant** (Background: "`INCONCLUSIVE` を
  `DEFLATION_REJECTED` に丸めてはならない -- 丸めると design-final.md:251 の
  出口表で「書く」方向へ倒れる"). Every test that asserts an
  ineligible-majority or exactly-half-eligible case reports
  `"INCONCLUSIVE"` failed once the string literal was swapped, including
  the dedicated `test_mutant_inconclusive_folded_to_rejected_is_killed`
  witness. `test_ineligible_majority_is_recorded_as_undecidable` (AC 004-8)
  failing here is the direct proof that the paper-writing-direction bias
  this mutant would introduce is caught.

### M3: band closed-interval check relaxed to open interval

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (2): `test_reference_drop_on_band_boundary_is_supported`,
  `test_mutant_band_open_interval_is_killed`
- note: **issue-mandated core mutant** (Codex TASK-PRE MEDIUM-3: "0.2350 が
  drop_p5/drop_p95 にちょうど一致する場合... 含む =
  `DEFLATION_SUPPORTED` に凍結"). With `<` instead of `<=`, a
  `reference_drop` exactly equal to a band edge flips from
  `"DEFLATION_SUPPORTED"` to `"DEFLATION_REJECTED"` -- both boundary-pinning
  tests assert the closed-interval (inclusive) result directly and both
  failed under the mutant.

### M4: `STAGE1_DRAW_INDEX` constant changed `0` -> `1`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (3): `test_config_matches_preregistration`,
  `test_config_mismatch_is_detected`, `test_stage1_uses_draw_index_zero_not_median`
- note: caught **twice, independently**: (a) this issue's own AC 004-4 spy
  test (`test_stage1_uses_draw_index_zero_not_median`) asserts every
  observed `anchor_draw_indices(..., draw_index=...)` call equals the
  literal `0`, not merely `mod.STAGE1_DRAW_INDEX` (which would have passed
  vacuously under this mutant, since `internal_shaped_replicates` reads the
  constant live) -- catching exactly the "the constant itself silently
  drifted" failure mode; and (b) the pre-existing I-001 preregistration
  read-through tests fail too, because `STAGE1_DRAW_INDEX` is also emitted
  into `collect_preregistration()`'s `stage1_draw_index` field (design-final.md
  §9) -- an unplanned but legitimate cross-issue kill, confirming the two
  issues' contracts stay mutually consistent.

### M5: cyclic assignment starting position shifted by +1

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (4): `test_replicate_shape_matches_internal`,
  `test_cyclic_assignment_wraps_past_sixteen_objects`,
  `test_insufficient_pool_objects_are_surfaced`,
  `test_all_objects_short_is_also_surfaced`
- note: shifting `STAGE1_INTERNAL_GOOD_COUNTS[i % n]` to `[(i + 1) % n]`
  reassigns every object's good-count share by one position -- the AC 004-1
  shape test (exact per-object counts `{obj_a: 3, obj_b: 3, obj_c: 1,
  obj_d: 3, obj_e: 1}`) and the wrap-around test (exact values at positions
  16/17) both directly assert the *un-shifted* assignment and fail under
  the mutant; the two pool-shortage tests fail as a side effect because
  their hand-picked "short" object no longer receives the count the test
  assumed.

### M6: pooled AUC conflated with the stratified (unweighted) statistic

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (1): `test_stratified_statistic_diverges_from_pooled_under_skewed_weights`
- note: this test was added specifically to close a gap the other AC tests
  did not cover (none of AC 004-1..004-9 individually pins the *value* of
  `drop_p5_strat`/`drop_p95_strat` against an independently-computed
  expectation) -- a weight-skewed fixture (`object "big"`, weight 9, vs.
  `object "small"`, weight 1) makes the pooled drop (0.4) and the
  layer-stratified drop (0.0) provably different; routing the pooled
  computation through the unweighted per-object function collapses that
  difference and the dedicated assertion fails. No other test in the suite
  happened to be sensitive to this swap, confirming the gap was real before
  this witness was added.

### M7: `"DEFLATION_SUPPORTED"` / `"DEFLATION_REJECTED"` terminal values swapped

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (3): `test_deflation_band_both_branches`,
  `test_reference_drop_on_band_boundary_is_supported`,
  `test_mutant_band_open_interval_is_killed`
- note: AC 004-7's non-tautology test (both branches reachable) directly
  asserts the two labels attach to the correct branch and fails when they
  are swapped; the two boundary-pinning tests fail for the same reason
  (they assert the boundary-equal case is specifically
  `"DEFLATION_SUPPORTED"`, not just "some fixed string").

## Summary

- **7/7 mutants KILLED, 0 survivors.**
- All 6 categories the issue's `## mutation testing (必須)` section names
  are covered: `<=`/`<` percentile-boundary predicates (M1, M3),
  `draw_index` の定数 (M4), 巡回割当の開始位置 (M5), 過半の `>` vs `>=`
  (M1, same predicate as the eligible-fraction floor), pooled/層別の取り違え
  (M6) -- plus the two explicitly issue-named mutants (`eligible_fraction
  <= 0.5` relaxed to `<`, `"INCONCLUSIVE"` mapped to `"DEFLATION_REJECTED"`)
  and one additional outcome-label-swap mutant (M7) for defense in depth.
- **The three-state boundary mutants (M1/M2/M3) -- the ones this issue's
  Background explicitly calls out as the most deflating-bias-relevant --
  were all individually killed by dedicated boundary-pin tests
  (`test_eligible_fraction_exactly_half_is_inconclusive`,
  `test_mutant_inconclusive_folded_to_rejected_is_killed`,
  `test_reference_drop_on_band_boundary_is_supported`), not merely as a
  side effect of unrelated assertions.**
- witness effectiveness was **observed by actually applying each mutant and
  reading the real pytest output**, not asserted from reading the
  implementation first -- the table above lists exactly the `FAILED
  <nodeid>` lines the driver captured, and M6's gap (no other test caught
  it) was found by first checking without the dedicated test, then adding
  it, matching `feedback_witness_needs_mutation_testing`'s discipline.
- file restoration verified via **SHA-256** after every single mutant and
  again at driver exit: pristine hash
  `5bf93ff4ad7cc923c21bf24a24d9a6682f5b74482c286b1c515fbfae7a259c1a`,
  `final restore hash match: True`. A post-mutation-run, fresh-`__pycache__`
  execution of all four pin verify commands (`pytest -q
  tests/test_paper01_scope`, `mypy src`, `ruff check ...`, `ruff format
  --check ...`) was re-confirmed green (59 passed / no mypy issues / all
  ruff checks passed / all files formatted) after the mutation run
  completed, independent of the driver's own in-loop checks.

## 復元確認

全 7 mutant 適用後、`scripts/paper01_scope_condition.py` を都度 SHA-256 で
mutation 前の on-disk バイト列と比較し、**毎回完全一致**を確認
(driver 内 `assert restored == original` + `assert sha256(restored) ==
original_hash`)。driver 終了時の最終確認 (`final restore hash match: True`)
に加え、セッション終盤に独立に `python -c "hashlib.sha256(...)"` で
再計算したハッシュ値も pristine 値と完全一致することを確認した。
`git status --short` は本 issue の意図した 1 ファイル追加
(`tests/test_paper01_scope/test_stage1.py`) と 1 ファイル変更
(`scripts/paper01_scope_condition.py`、I-004 anchor 内のみ) のみを示し、
CRLF 警告は出ていない。

---

<!-- ================= I005 ================= -->

# Mutation testing log -- Loop I-005 (判定規則 decide_scope())

Target: `scripts/paper01_scope_condition.py` §「I-005: decision rule --
decide_scope()」(`decide_scope` / `_stage0_t_s_delta` / the `FAIL_PRECEDENCE`
consumption inside `decide_scope`). Test suite:
`tests/test_paper01_scope/test_decision_rule.py` (11 tests), run together
with the full `tests/test_paper01_scope` package (39 tests total: the 28
pre-existing I-001/I-001b/I-002 tests + these 11) so a mutant that happens to
break an earlier issue's contract would also surface.

Per `feedback_witness_needs_mutation_testing` / issue 005 AC 005-MUT: each
mutant below was **actually applied to the worktree's own copy of the file,
actually run through pytest, and the failing test id(s) below are the real
observed output** -- not an assumption about which assertion "should" catch
it. Driver script (`assert old in s` before mutating / `assert new != old` /
`assert new in on_disk` after writing / SHA-256 restore check after every
mutant) ran from
`C:\Users\johnd\AppData\Local\Temp\claude\C--ERRE-Sand-Box\f33f2702-2785-4497-8a5a-f5a9ee7b5619\scratchpad\mutate_i005.py`
against this worktree's copy of the target file; the file was restored to
its pristine, hash-verified byte-identical state after every single mutant,
including after the final one (verified again at driver exit:
`final restore hash match: True`).

**Tooling gotcha hit and fixed (byte-safety)**: the driver's first run used
`Path.read_text()` / `Path.write_text()`, which apply universal-newline
translation. This worktree's copy of the target file is LF-only; the first
`write_text()` call silently turned it into CRLF, and the restore-hash
assertion correctly caught the mismatch (`git diff --stat` afterwards showed
only the intended 195-line insertion in content terms, but `git status`
warned "CRLF will be replaced by LF"). Fixed by switching the driver to
`Path.read_bytes()` / `Path.write_bytes()` with manual UTF-8 decode/encode
(no newline translation at all) before re-running -- this is the same class
of gotcha `mutation-log-I001b.md` recorded for its CRLF checkout, mirrored
here for an LF checkout. The file was manually re-normalised to LF and all
four verify commands re-confirmed green before the mutation run that
produced the results below.

Command per mutant: `pytest -q tests/test_paper01_scope -v` (39 collected),
full stdout+stderr captured, `FAILED <nodeid>` lines parsed for the table
below.

## Enumerated mutants (11, all within this issue's own anchor section)

| id | category (issue text / design-final.md §7) | target |
|---|---|---|
| M1 | Stage 1 override (**this issue's named core mutant, AC 005-MUT**) | `write_eligible` re-derived from `not stage1.deflation_supported` instead of `stage1_outcome == "DEFLATION_REJECTED"` |
| M2 | 境界述語 `<` vs `>` | F4: `no_material_delta` direction |
| M3 | 境界述語 `>` vs `<` | T-confound: `t_driven` direction |
| M4 | 境界述語 `<` vs `>` | F2: `object_loss` direction |
| M5 | 述語の比較対象 | F3: `audit_inactive` target string |
| M6 | 述語の否定 `==` vs `!=` | F5: `cambridge_contradiction` |
| M7 | 境界述語 `>` vs `<` | F1: `rho_unreachable` direction |
| M8 | `FAIL_PRECEDENCE` の順序 | `fail_reason` の走査順を `reversed(FAIL_PRECEDENCE)` に |
| M9 | 連言の各項 (§3 condition 3) | `condition_c_supported` から `both_splits_robust` 項を削除 |
| M10 | 連言の各項 (§3 condition 1&2) | `condition_c_supported` から `both_splits_supported` 項を削除 |
| M11 | 連言の各項 (§3 condition 4) | `condition_c_supported` の F1-F6 ゲート項を `True` 定数に置換 |

## Results

### M1: Stage 1 override -- `not stage1.deflation_supported` へ差し戻し

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_decision_rule.py::test_inconclusive_never_derives_write_right`
- note: **this is the issue-mandated core mutant.** `INCONCLUSIVE` と
  `DEFLATION_REJECTED` はどちらも `deflation_supported == False` を共有する
  ため、`not deflation_supported` から書く権利を導出すると
  `stage1_outcome == "INCONCLUSIVE"` の入力でも `verdict == "WRITE"` に
  なってしまう。実際に当てて確認したところ、
  `test_inconclusive_never_derives_write_right` の
  `assert inconclusive.verdict == "DO_NOT_WRITE"` が直接落ちた
  (mutant 下では `inconclusive.verdict == "WRITE"` になっていた) --
  「INCONCLUSIVE から WRITE を出す mutant が kill される」ことを実地で確認。
  他の 9 テストは無関係 (`deflation_supported` が絡む分岐を通らない) ため
  巻き込まれず、この 1 本だけが単独で落ちた -- 過大申告を避けるため、
  この mutant を kill するのは他ではなくこの assertion だけであることを
  明記する。

### M2: F4 `no_material_delta` 方向反転 (`<` -> `>`)

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (10): `test_both_outcomes_are_reachable`,
  `test_each_fail_branch_is_reachable`,
  `test_fail_precedence_resolves_simultaneous_branches`,
  `test_deflation_overrides_stage2`,
  `test_inconclusive_never_derives_write_right`,
  `test_split_disagreement_is_not_support`,
  `test_single_point_dependence_is_not_support`,
  `test_cambridge_contradiction_only_on_pass`,
  `test_t_attribution_requires_note_but_does_not_fail`,
  `test_no_material_delta_is_f4`
- note: この方向反転は「材料差あり」の baseline fixture (diff=0.39) を
  誤って F4 発火させ、あわせて「材料差なし」の fixture (diff=0.005) の
  F4 発火を止める -- 影響範囲が広く、`_supportive_cells()` を使う
  ほぼ全 test が連鎖的に落ちた。直接の専用 witness は
  `test_no_material_delta_is_f4` (F4 が消える方) と
  `test_both_outcomes_are_reachable` (baseline に誤って F4 が付く方)。

### M3: T-confound `t_driven` 方向反転 (`>` -> `<`)

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_t_attribution_requires_note_but_does_not_fail`
- note: 他の 10 test には影響しない -- `t_driven` は
  `t_confound_note_required` のみに効き、`condition_c_supported` /
  `verdict` / `fail_reason` を一切動かさない設計 (design-final.md HIGH-3:
  T 側は探索的、verdict には使わない) の通り、単独 witness になった。

### M4: F2 `object_loss` 方向反転 (`<` -> `>`)

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (8): `test_both_outcomes_are_reachable`,
  `test_each_fail_branch_is_reachable`, `test_deflation_overrides_stage2`,
  `test_inconclusive_never_derives_write_right`,
  `test_split_disagreement_is_not_support`,
  `test_single_point_dependence_is_not_support`,
  `test_cambridge_contradiction_only_on_pass`,
  `test_t_attribution_requires_note_but_does_not_fail`
- note: `_supportive_cells()` の baseline は ARM-A/ARM-S が同数の
  active_objects (4件=4件) を持つため、`len(s) < len(a)*0.5` は元々
  False (4 < 2 は False)。反転後は `len(s) > len(a)*0.5` (4 > 2 は
  True) となり baseline 全体が誤って F2 発火 -- 連鎖的に多数の supportive
  系 test が落ちた。専用 witness は `test_each_fail_branch_is_reachable`
  の F2 ケース (`fail_reason == "F2"` が別の値になる)。

### M5: F3 `audit_inactive` 比較対象を `INVALID_TASK_BATTERY` -> `NO_VALID_SCORER`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (8): M4 と同一集合
- note: mutant 下では f3_cells (`arm_s.verdict == "INVALID_TASK_BATTERY"`)
  の `audit_inactive` が False になり `fail_reason` が `None` に落ちる
  (`test_each_fail_branch_is_reachable` の F3 ケースが直接 witness)。
  同時に `_supportive_cells()` の baseline (`arm_s.verdict ==
  "NO_VALID_SCORER"`) が誤って `audit_inactive=True` になり、baseline を
  使う他の test も連鎖的に落ちた。

### M6: F5 `cambridge_contradiction` 否定 (`==` -> `!=`)

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (9): M2 と同一集合 + `test_fail_precedence_resolves_simultaneous_branches`
- note: PASS/非PASS が完全に反転するため、AC 005-9 の両方向
  (`test_cambridge_contradiction_only_on_pass`) と、F4/F5 同時到達を扱う
  `test_fail_precedence_resolves_simultaneous_branches` も直接巻き込まれた
  (mutant 下では baseline の `INCONCLUSIVE_UNDERPOWERED` が誤って F5 を
  発火させる)。

### M7: F1 `rho_unreachable` 方向反転 (`>` -> `<`)

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (8): M4 と同一集合
- note: baseline (`rho_int_primary=0.5`, `rho_by_tau[-1]=0.40`) は本来
  `0.40 > 0.5` = False (F1 不発火) だが、反転後は `0.40 < 0.5` = True と
  なり baseline 全体が誤って F1 発火。専用 witness は
  `test_each_fail_branch_is_reachable` の F1 ケース。

### M8: `FAIL_PRECEDENCE` 走査順を `reversed(...)` に

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_fail_precedence_resolves_simultaneous_branches`
- note: F4/F5 同時到達 fixture で `fail_reason` が `"F4"` から `"F5"` に
  変わり、AC 005-4 の中心アサーションが直接落ちた -- 他の test は
  F1-F7 が単独でしか到達しない fixture のため影響を受けなかった
  (優先順位の入れ替えは「複数同時到達」以外では観測不能)。この test
  内部の `monkeypatch.setattr(mod, "FAIL_PRECEDENCE", ...)` による
  非恒真性チェックと合わせて、`FAIL_PRECEDENCE` の消費順序が
  実際に load-bearing であることを二重に確認した。

### M9: `condition_c_supported` から `both_splits_robust` 項を削除

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_each_fail_branch_is_reachable` (F7 ケース),
  `test_single_point_dependence_is_not_support`
- note: F7 (単点依存) fixture は `both_splits_supported=True` かつ
  `both_splits_robust=False` だが F1-F6 はどれも該当しない --
  robust 項を落とすと `condition_c_supported` が誤って `True` になる。
  §3 condition 3 (τ* 隣接段) が単独で load-bearing であることの直接証拠。

### M10: `condition_c_supported` から `both_splits_supported` 項を削除

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_both_outcomes_are_reachable`,
  `test_one_sided_evidence_is_not_support`
- note: AC 005-6 の fixture (両分割とも ARM-A が `PASS` でない = cond1
  両方 False、分割は一致) は F6 (分割不一致) を誘発しない -- そのため
  `both_splits_supported` 項を落とすと、他に条件 C を否定する項が無く
  `condition_c_supported` が誤って `True` になった。
  §3 condition 1&2 が F6 とは独立に load-bearing であることの直接証拠
  (F6 は「不一致」だけを見るため「両方とも不支持で一致」なケースを
  捕まえられない -- この mutant が生きていたら見逃していた穴)。

### M11: `condition_c_supported` の F1-F6 ゲート項を `True` 定数に置換

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_each_fail_branch_is_reachable` (F4 ケース),
  `test_cambridge_contradiction_only_on_pass`, `test_no_material_delta_is_f4`
- note: F4 (材料差なし) fixture は `both_splits_supported=True` かつ
  `both_splits_robust=True` -- F1-F6 ゲートだけが `condition_c_supported`
  を `False` にしている。ゲートを定数 `True` に置換すると誤って `True`
  になり、AC 005-11 の中心アサーションが直接落ちた。

## Summary

- **11/11 mutants KILLED, 0 survivors.**
- 事前登録された 4 分類 (issue 本文 / design-final.md §7) を全てカバー:
  連言の各項 (M9/M10/M11)、境界述語の向き (M2/M3/M4/M7)、
  `FAIL_PRECEDENCE` の順序 (M8)、Stage 1 上書き (M1)。
- **M1 (この issue の核: 「INCONCLUSIVE から WRITE を出す mutant」)は
  実地で kill を確認した** -- `test_inconclusive_never_derives_write_right`
  の `verdict == "DO_NOT_WRITE"` アサーションが直接落ち、他のどの test も
  この mutant では巻き込まれなかった (過大申告なし)。
- witness の効き方は **すべて実際に mutant を当てて観測**した
  (docstring から「効くはず」と書く前に driver の実行結果を先に見た) --
  M9/M10 はどちらも「§3 の 4 条件のうち特定の 1 項だけが独立に
  load-bearing である」ことを、他の項では代替不可能な fixture で
  直接証明している (とくに M10 は F6 だけでは捕まえられない
  「両分割一致で不支持」というケースの穴を塞いでいることを確認した)。
- ファイル復元は毎回 SHA-256 で pristine と完全一致することを確認
  (`final restore hash match: True`)。最終 sanity run
  (`pytest -q tests/test_paper01_scope`) も exit 0 (39 passed)。

## Post-mutation semantic cross-check (design-final.md §7 item 4)

`decide_scope()` はこの issue の scope では JSON を emit しない
(`results/scope.json` は I-007 の責務)。適用可能な代替として、
各 mutant 適用後に手計算した期待値 (baseline `delta_int=0.20` /
`delta_ext=0.59` -> diff=0.39 > EPS=0.01、T 由来 fixture
`t_int-t_ext=0.40` > `s_int-s_ext=0.01`、F2 の `4 < 4*0.5=2` は False
だが `2 < 10*0.5=5` は True 等) を、実装を読み返す前に本ログの各節へ
先に書き下し、driver の実測結果と突き合わせた。数値の意味が
「もっともらしいが誤った値」にすり替わっていないかを、実装から
読み取った値でなく紙の上で導いた値で確認する discipline
(`mutation-log-I002.md` と同じ手順) を踏襲している。

## 復元確認

全 11 mutant 適用後、`scripts/paper01_scope_condition.py` を SHA-256 で
mutation 前の on-disk バイト列と比較し、**完全一致**を確認
(`final restore hash match: True`)。`git diff --stat` は本 issue の意図した
195 行追加のみを示し、CRLF 警告は出ていない (driver 初回実行時に
`Path.write_text()` の universal-newline 変換で一度 CRLF 化する事故が
あったが、`Path.read_bytes()`/`write_bytes()` へ切り替えて再実行し、
手動で LF に正規化した上で最終確認済み)。

---

<!-- ================= I006 ================= -->

# Mutation testing log -- Loop I-006 (τ* 較正 / セル配線 / CLI)

Target: `scripts/paper01_scope_condition.py` §「I-006: tau* calibration /
cell wiring / CLI」(`build_cell` / `internal_rho_and_k` / `calibrate_tau` /
`adjacent_tau_indices` / `active_objects_for_cell` / `common_active_objects`
/ `score_cell` / `run_scope`). Test suite:
`tests/test_paper01_scope/test_cells.py` (10 tests, 1 skipped by design --
AC 006-1's real-encoder fidelity pin, `@pytest.mark.eval` +
`ERRE_RUN_REAL_MPNET_TESTS=1` opt-in) +
`tests/test_paper01_scope/test_calibration.py` (8 tests), run together with
the full `tests/test_paper01_scope` package (85 passed / 1 skipped total:
the 69 pre-existing I-001/I-001b/I-002/I-003/I-004/I-005 tests + these 16
new) so a mutant that happens to break an earlier issue's contract would
also surface.

**Each mutant below was actually applied to the worktree's own copy of the
file, actually run through pytest, and the failing test id(s) below are the
real observed output** -- not an assumption about which assertion "should"
catch it. Driver script (`assert old in s` before mutating / `assert new !=
old` / `assert new in on_disk` after writing / SHA-256 restore check after
every mutant, `Path.read_bytes()`/`Path.write_bytes()` throughout, never
`read_text`/`write_text` -- the CRLF-translation gotcha I-001b/I-005 already
hit) ran from
`C:\Users\johnd\AppData\Local\Temp\claude\C--ERRE-Sand-Box\f33f2702-2785-4497-8a5a-f5a9ee7b5619\scratchpad\mutate_i006.py`
against this worktree's copy of the target file; the file was restored to
its pristine, hash-verified byte-identical state after every single mutant,
including after the final one (verified again at driver exit against the
pristine SHA-256 `174e439aa7402c183539411dcbd18bc81ee3028a79ebc416d3ceae742b1a7514`,
and cross-checked with `sha256sum` after the driver finished).

Command per mutant: `python -B -m pytest -p no:cacheprovider -q
tests/test_paper01_scope -v` (avoids the stale-`__pycache__`-bytecode false
negative I-004 hit when mutate/test/restore cycles run fast on Windows).

## Enumerated mutants (8, all within this issue's own anchor section)

| id | category (issue text binding / design-final.md §7) | target |
|---|---|---|
| M1 | パイプライン順序 (issue **必須**, Codex HIGH-4) | `build_cell`: `leader_cluster_indices` の `cap` を uncapped (`n_pool`) からこの cell 自身の `cap` 引数に差し替え (dedupe を先に cap してしまう) |
| M2 | パイプライン順序 (issue **必須**) | `build_cell`: `k_eff = min(cap, n_leaders)` の `min` を `max` に反転 |
| M3 | ρ_int の主基準 (issue **必須**, Codex HIGH-1) | `internal_rho_and_k`: `rho_primary` の集計元を `rho_primary_c4` (C4-raw) から `rho_secondary_c0` (C0-dedup) に差し替え |
| M4 | τ* の tie-break (issue **必須**) | `calibrate_tau`: `if gap < best_gap:` を `<=` に反転 (小さい τ 側が勝つよう反転) |
| M5 | 4セル共通 active 交差 (issue **必須**, Codex MEDIUM-4) | `common_active_objects`: `set.intersection` を `set.union` に差し替え |
| M6 | 境界述語 `>=` vs `>` | `active_objects_for_cell`: `n_leaders >= N_R_MIN` を `>` に反転 (ちょうど N_R_MIN の物体を誤って除外) |
| M7 | 境界述語 (grid 下端) | `adjacent_tau_indices`: `tau_star_index > 0` を `>= 0` に反転 (存在しない -1 隣接を報告) |
| M8 | 境界述語 (grid 上端) | `adjacent_tau_indices`: `tau_star_index < n - 1` を `<= n - 1` に反転 (存在しない n 番目の隣接を報告) |

## Results

### M1: dedupe を uncapped でなく cell の `cap` で行う

```diff
-    leader_idx = leader_cluster_indices(emb, radius=tau, cap=n_pool)
+    leader_idx = leader_cluster_indices(emb, radius=tau, cap=cap)
```

- exit code: 1 (killed)
- `1 failed, 84 passed, 1 skipped`
- `FAILED tests/test_paper01_scope/test_cells.py::test_cell_pipeline_order_is_dedupe_then_cap_then_draw`
  -- スパイが `leader_cluster_indices` の実引数 `cap` を確認しており、
  期待値 `cap == 7` (= `len(pool)`) に対し実際は `cap == 3` (cell 自身の
  cap) になるため fail。

### M2: `k_eff = min(cap, n_leaders)` を `max` に反転

```diff
-    k_eff = min(cap, n_leaders)
+    k_eff = max(cap, n_leaders)
```

- exit code: 1 (killed)
- `1 failed, 84 passed, 1 skipped`
- `FAILED tests/test_paper01_scope/test_cells.py::test_cell_pipeline_order_is_dedupe_then_cap_then_draw`
  -- 同テストの `cell.k_effective == min(3, cell.n_leaders)` assertion が、
  実際の `k_effective` が `max(3,7)=7` になることで fail。

### M3: `rho_primary` を C0-dedup (`rho_secondary_c0`) から集計

```diff
-    rho_primary = float(sum(r.rho_primary_c4 for r in references) / len(references))
+    rho_primary = float(sum(r.rho_secondary_c0 for r in references) / len(references))
```

- exit code: 1 (killed)
- `FAILED tests/test_paper01_scope/test_calibration.py::test_rho_int_reports_both_bases`
  (`comparison failed`) -- `internal_rho_and_k` の `rho_primary` が
  `brick.rho_primary_c4` でなく `brick.rho_secondary_c0` になり、fixture が
  意図的に異なる値にしてある両基準の assertion が fail。

### M4: τ* tie-break を小さい τ 側に反転

```diff
-        if gap < best_gap:
+        if gap <= best_gap:
```

- exit code: 1 (killed)
- `1 failed, 84 passed, 1 skipped`
- `FAILED tests/test_paper01_scope/test_calibration.py::test_tau_tie_breaks_high`
  -- τ=0.85/0.80 が完全同着になるよう仕組んだ fixture で、`tau_star` が
  期待の `0.85` (大きい τ) でなく `0.80` (grid 降順走査で後から来る、より
  小さい τ) になり fail。

### M5: 4セル共通 active 交差を union に差し替え

```diff
-    common = set.intersection(*sets)
+    common = set.union(*sets)
```

- exit code: 1 (killed)
- `FAILED tests/test_paper01_scope/test_cells.py::test_object_collapse_is_f2`
  -- `common_active_objects` が疎セルで脱落したはずの物体まで含めて
  union してしまい、`intersection == sorted(sparse_active)` assertion と、
  それに続く `decide_scope` の F2 到達 assertion の両方が fail。

### M6: `active_objects_for_cell` の境界を `>` に反転

```diff
-            if anchors.n_leaders >= _c.N_R_MIN
+            if anchors.n_leaders > _c.N_R_MIN
```

- exit code: 1 (killed)
- `FAILED tests/test_paper01_scope/test_cells.py::test_active_objects_for_cell_boundary_at_n_r_min`
  -- `n_leaders == N_R_MIN` ちょうどの `"at_floor"` オブジェクトが
  active から誤って除外される。

### M7: `adjacent_tau_indices` 下端境界を `>= 0` に反転

```diff
-    if tau_star_index > 0:
+    if tau_star_index >= 0:
```

- exit code: 1 (killed)
- `FAILED tests/test_paper01_scope/test_calibration.py::test_adjacent_tau_at_grid_edges`
  -- grid の先頭 (`tau_star_index == 0`) で、存在しない `-1` を隣接として
  返してしまい `adjacent_tau_indices(0) == (1,)` assertion が fail。

### M8: `adjacent_tau_indices` 上端境界を `<= n - 1` に反転

```diff
-    if tau_star_index < n - 1:
+    if tau_star_index <= n - 1:
```

- exit code: 1 (killed)
- `FAILED tests/test_paper01_scope/test_calibration.py::test_adjacent_tau_at_grid_edges`
  -- grid の末尾 (`tau_star_index == len(TAU_GRID) - 1`) で、存在しない
  `n` 番目 (out of range) を隣接として返してしまい
  `adjacent_tau_indices(last) == (last - 1,)` assertion が fail。

## Summary

**8/8 mutants killed.** 0 survived. File restored byte-identical
(SHA-256 `174e439aa7402c183539411dcbd18bc81ee3028a79ebc416d3ceae742b1a7514`)
after every mutant, verified again after the full driver run completed
(`sha256sum scripts/paper01_scope_condition.py` matched). Pristine file
re-confirmed `85 passed, 1 skipped` (`pytest -q tests/test_paper01_scope`)
after the mutation run.

## Witness discipline note (this issue's binding requirement)

The two `test_cell_pipeline_order_is_dedupe_then_cap_then_draw` kills (M1,
M2) are spy-based, reading the *actual* keyword arguments
`leader_cluster_indices`/`anchor_draw_indices` received -- never inferred
from an aggregate statistic (this issue's Test Plan: "AUC などの集約統計で
配線を検査しない"). The `test_object_collapse_is_f2` kill (M5) exercises the
*real* `active_objects_for_cell` → `common_active_objects` → `CellResult.
active_objects` → `decide_scope` wiring end to end (not a hand-typed
`active_objects` tuple bypassing `common_active_objects` entirely), so a
docstring claim that "the F2 pathway is wired through
`common_active_objects`" is backed by an actual mutation kill on that exact
function, not merely on `decide_scope`'s own (already I-005-tested) F2
predicate.

---

<!-- ================= I007a ================= -->

# Mutation testing log -- Loop I-007a (実走の前段: run.sh 一式 / notes.md 骨格)

Target: `scripts/paper01_scope_condition.py` §「I-007: fidelity pin (b)+(c)
の中身、--scope の Cambridge セル配線」(`cli_fidelity` / `measure_g1_arm_a_
fidelity` / `g1_arm_a_fidelity_matches` / `build_split_cells` /
`_gather_cambridge` / `_score_cambridge_arm_s` / `cli_scope`)、
`experiments/20260908-paper01-scope-condition/run_gate.py`
(`hashes_match`)、`experiments/20260908-paper01-scope-condition/
build_metrics.py` (`build_metrics`)。

Test suites:
- `tests/test_paper01_scope/test_scope_cli_wiring.py` (28 tests, I-007a 新規)
- `tests/test_paper01_scope/test_run_artifacts.py` (20 tests, I-007a 新規)
- 既存の `tests/test_paper01_scope` フルパッケージ (129 passed / 1 skipped
  合計 -- 上記 2 ファイルの計 48 test を含む)

**各 mutant は実際に worktree の対象ファイルへ適用し、実際に pytest を
走らせ、下記の fail した test id は実測の出力そのものである** (「落ちる
はず」という想定ではない)。driver script (`assert old in content` を
mutate 前に / `assert new in content` を write 後・pytest 実行前に /
`Path.read_bytes()`/`Path.write_bytes()` のみ使用、`read_text`/`write_text`
は CRLF 変換の懸念があるため一切使わない / 各 mutant 後に元バイト列へ
restore し SHA-256 で照合、最後の mutant 後も含めすべて照合済み) は
`C:\Users\johnd\AppData\Local\Temp\claude\C--ERRE-Sand-Box\
f33f2702-2785-4497-8a5a-f5a9ee7b5619\scratchpad\mutate_i007a.py` に置き、
この worktree のコピーに対して実行した。

**pristine SHA-256** (driver 起動時に記録、全 mutant 処理後も一致を確認済み):

| ファイル | SHA-256 |
|---|---|
| `scripts/paper01_scope_condition.py` | `36ca5b575e674a7c20d3878a82ecb7a6921655db050494f1e96b136e8275f9e5` |
| `experiments/20260908-paper01-scope-condition/run_gate.py` | `78470f15dc75eb12b56ab1bd28cd52df541ae2e1181cfb8f5a8462024f274aa2` |
| `experiments/20260908-paper01-scope-condition/build_metrics.py` | `5949724d8baada43a3f8bacca569ffb879d2a9a9d234de2018be52aa4439f801` |

Command per mutant: `C:/ERRE-Sand_Box/.venv/Scripts/python.exe -B -m pytest
-p no:cacheprovider -q <該当 test ファイル>` (`-B` = `.pyc` を書かない、
`-p no:cacheprovider` = 直前の I-006/I-004 が踏んだ stale bytecode 型の
false negative を避ける、issue 007 指示どおり)。

## Enumerated mutants (7 -- issue 007 が明記した必須 3 種 (M1-M3) + 本
issue 自身の新規コードに対する追加 4 種 (M4-M7))

| id | 分類 (issue 必須 / 追加) | target |
|---|---|---|
| M1 | **issue 007 必須**: 「SHA-256 一致ゲートを常に真にする」 | `run_gate.hashes_match`: `hash_a == hash_b` を `True` に差し替え |
| M2 | **issue 007 必須**: 「--fidelity の不一致で exit 0 を返す」 | `cli_fidelity`: `if mismatch: return FIDELITY_EXIT_MISMATCH` の戻り値を `FIDELITY_EXIT_OK` に差し替え |
| M3 | **issue 007 必須**: 「build_metrics が抽出でなく再計算する」 | `build_metrics.build_metrics`: `stage1.get("median_drop")` の**そのまま返す**箇所を `drop_p5 + drop_p95` の再計算式に差し替え |
| M4 | 境界述語 (追加) | `g1_arm_a_fidelity_matches`: 6 項連言のうち後半 3 項の `and` を `or` に反転 |
| M5 | データ欠如と不一致の優先順位 (追加、issue 007 の「別々の exit code で区別する」に対応) | `cli_fidelity`: mismatch 優先の判定順序を unavailable 優先に反転 |
| M6 | 境界述語 (追加、DA-SC-3 隣接段判定) | `build_split_cells`: `condition1_at_star` の `and` を `or` に反転 |
| M7 | 境界値 (追加) | `G1_ARM_A_TOLERANCE`: `1e-6` を `1.0` に緩める |

## Results

### M1: `hashes_match` を常に `True` にする

```diff
-    return hash_a == hash_b
+    return True
```

- exit code: 1 (**KILLED**)
- `3 failed, 17 passed`
- `FAILED test_hashes_match_detects_mismatch`
- `FAILED test_sha256_of_file_reflects_content`
- `FAILED test_run_gate_check_hashes_cli_exit_code`
  -- `run_gate.main(["check-hashes", a, c])` が異なる内容のファイルに
  対しても `0` を返すようになり、`== 1` の assertion が fail。
  **issue 007 の必須 mutant を実測で kill 済み。**

### M2: `--fidelity` の mismatch 分岐を exit 0 に差し替える

```diff
     if mismatch:
-        return FIDELITY_EXIT_MISMATCH
+        return FIDELITY_EXIT_OK
     if unavailable:
         return FIDELITY_EXIT_SOURCE_UNAVAILABLE
     return FIDELITY_EXIT_OK
```

- exit code: 1 (**KILLED**)
- `3 failed, 21 passed`
- `FAILED test_cli_fidelity_pin_c_mismatch_never_reports_exit_ok`
- `FAILED test_cli_fidelity_pin_b_mismatch_never_reports_exit_ok`
- `FAILED test_cli_fidelity_mismatch_takes_priority_over_unavailable`
  -- 不一致が発生しても `cli_fidelity()` が `0` を返すようになり、
  「不一致は必ず非ゼロ」を確認する 3 test が fail。
  **issue 007 の必須 mutant を実測で kill 済み。**

### M3: `build_metrics` が `median_drop` を再計算するよう差し替える

```diff
-            "median_drop": stage1.get("median_drop"),
+            "median_drop": (stage1.get("drop_p5") or 0) + (stage1.get("drop_p95") or 0),
```

- exit code: 1 (**KILLED**)
- `2 failed, 18 passed`
- `FAILED test_build_metrics_extracts_verbatim_values_never_recomputed`
  -- 入力に設定した sentinel `0.20`(`median_drop`) がそのまま出てくる
  はずが、`drop_p5(0.10) + drop_p95(0.30) = 0.40` という**別の値**に
  変わり fail。
- `FAILED test_build_metrics_changing_the_sentinel_changes_the_output`
  -- 入力の `median_drop` を `0.987654` に変えても出力が `drop_p5+drop_p95`
  の再計算値のままになり `assert metrics[...]["median_drop"] == 0.987654`
  が `assert 0 == 0.987654` — 抽出でなく再計算していることが実測で判明。
  **issue 007 の必須 mutant を実測で kill 済み。**

### M4: `g1_arm_a_fidelity_matches` の連言を選言に緩める

```diff
-        and result.cell_verdict == G1_ARM_A_EXPECTED_CELL_VERDICT
+        or result.cell_verdict == G1_ARM_A_EXPECTED_CELL_VERDICT
         and result.overall_verdict == G1_ARM_A_EXPECTED_OVERALL_VERDICT
         and result.survivors == G1_ARM_A_EXPECTED_SURVIVORS
```

- exit code: 1 (**KILLED**)
- `8 failed, 16 passed`
- `test_g1_arm_a_fidelity_matches_rejects_any_single_disagreement` の
  6 パラメータ全ケース + `test_g1_arm_a_fidelity_matches_tolerance_boundary`
  + `test_cli_fidelity_pin_b_mismatch_never_reports_exit_ok` が fail --
  6 項連言のどれか 1 つだけ食い違う perturbed result が誤って match と
  判定されるようになったことを、パラメータ化 test の全ケースが捕まえた。

### M5: `cli_fidelity` の判定順序を反転 (unavailable を先に return)

```diff
-    if mismatch:
-        return FIDELITY_EXIT_MISMATCH
     if unavailable:
         return FIDELITY_EXIT_SOURCE_UNAVAILABLE
+    if mismatch:
+        return FIDELITY_EXIT_MISMATCH
     return FIDELITY_EXIT_OK
```

- exit code: 1 (**KILLED**)
- `2 failed, 22 passed`
- `FAILED test_cli_fidelity_pin_c_mismatch_never_reports_exit_ok`
  (pin (b) が同時に unavailable なシナリオで、mismatch でなく
  unavailable (`2`) が返るようになり `== 1` が fail)
- `FAILED test_cli_fidelity_mismatch_takes_priority_over_unavailable`
  (この mutant がまさに壊す性質そのものを確認する test)

### M6: `build_split_cells` の `condition1_at_star` を選言に緩める

```diff
-    condition1_at_star = arm_s.verdict == "NO_VALID_SCORER" and arm_a.verdict == "PASS"
+    condition1_at_star = arm_s.verdict == "NO_VALID_SCORER" or arm_a.verdict == "PASS"
```

- exit code: 1 (**KILLED**)
- `1 failed, 23 passed`
- `FAILED test_build_split_cells_no_neighbour_check_when_condition1_absent`
  -- このシナリオは ARM-A が `NO_VALID_SCORER`(≠PASS) なので本来
  condition 1 は成立せず隣接段チェックを一切呼ばないはずが、`or` に
  緩めたことで ARM-S 側の `NO_VALID_SCORER` だけで condition 1 が
  成立してしまい、隣接段 (`tau=0.55`) への余分な `score_cell` 呼び出しが
  発生 -- `calls` リストへの記録件数が `[0.5, 0.9]` の想定 2 件から
  `[0.5, 0.55, 0.9]` の 3 件に増えて fail。

### M7: `G1_ARM_A_TOLERANCE` を `1e-6` から `1.0` へ緩める

```diff
-G1_ARM_A_TOLERANCE: Final[float] = 1e-6
+G1_ARM_A_TOLERANCE: Final[float] = 1.0
```

- exit code: 1 (**KILLED**)
- `4 failed, 20 passed`
- `test_g1_arm_a_fidelity_matches_rejects_any_single_disagreement` の
  数値 3 ケース (`auc_full_at_median_draw` / `auc_lao_at_median_draw` /
  `potency_at_median_draw` をそれぞれ `0.5` にずらしたケース) +
  `test_cli_fidelity_pin_b_mismatch_never_reports_exit_ok` が fail --
  許容誤差が `1.0` まで緩むと `0.5` ずれた perturbed result も
  「一致」と判定されてしまうことを実測で確認。
  (`cell_verdict`/`overall_verdict`/`survivors` の文字列一致ケースは
  この mutant では影響を受けないため引き続き fail しない -- 期待どおり。)

## 生存 mutant

**0 件。** 上記 7 件すべてが実測で KILLED。

## mutation 後の意味突き合わせ工程 (issue 007 の binding 指示)

`--scope` / `--fidelity` は本セッション (I-007a) では実データで一度も
走っていない (Ocsai 到達不能・実走禁止の boundary、`notes.md` 参照) ため、
「出力 JSON の数字を読んで意味を突き合わせる」対象の実データ JSON は
存在しない。代わりに、本 issue が新規に書いたコードが読む・書く実在の
アーティファクトに対して同種の突き合わせを行った:

- `results/mutation-log-I007a.md` (本ファイル) 自体 --
  各 mutant の fail 出力 (上記の pytest 実測ログ) を**要約せず転記**した。
- M3 の突き合わせで、`build_metrics` の出力する `metrics.json`
  相当の dict (`_FAKE_SCOPE` fixture 由来) の `stage1.median_drop`
  フィールドが、mutation 前は入力の `0.20`/`0.987654` (sentinel) と
  **完全一致**し、mutation 後は `drop_p5+drop_p95` の再計算値
  (`0.40`) に変わることを、pytest の assertion diff (`assert 0 ==
  0.987654` 等) で実測確認した -- これは「全 test 緑・全 mutant kill
  でも意味が壊れている」型の欠陥 (G1 ADR §7 の反省) を、build_metrics
  の**出力値そのもの**を突き合わせることで捕まえる設計になっている。
- M6 の突き合わせで、`build_split_cells` が実際に `score_cell` へ渡す
  `tau` 引数列 (`calls` リスト) を直接記録・比較し、隣接段チェックが
  「呼ばれるべきでない場面で呼ばれていないか」を生の呼び出し引数で
  確認した (集約統計でなく配線そのものを見る、design-final.md §7 の
  「spy で生の呼び出し引数を見て kill」規律)。

## 逸脱・気づき

- 必須 3 mutant (M1-M3) はすべて 1 回で KILLED (再試行不要)。
- M6 は当初「4-cell 交差を union に緩める」(I-006 の M5 と同型) も
  候補にしていたが、`common_active_objects` 自体は I-006 の anchor
  節にあり本 issue の Allowed Files 外 (既存 issue の anchor 節を
  書き換えない、という binding 制約) のため対象から外し、代わりに
  本 issue 自身が新規に書いた `condition1_at_star` の連言を対象にした。
- driver 実行中の pytest 出力が Windows のデフォルトコンソール
  エンコーディング (cp932) の都合で日本語コメント部分が文字化けして
  見えたが、assertion の実測内容 (fail した test id / exit code /
  診断メッセージ) は文字化けせず正しく読めており、判定には影響していない。

---

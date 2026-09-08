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

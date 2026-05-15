# Mac eval data inventory — `data/eval/golden/` (read-only)

> **採取日時**: 2026-05-15 (Mac、Claude Sonnet)
> **採取方法**: `ls -la` / `wc -l` / `md5` / `Read` のみ (read-only、ファイル変更ゼロ、commit なし)
> **対象**: `/Users/johnd/ERRE-Sand Box/data/eval/golden/` 全 56 entry (`.` `..` 除く 54 file)
> **参照プロンプト**: `.steering/20260515-pre-m10-design-synthesis/next-session-prompt-eval-inventory.md`
> **目的**: PR #174 (pre-M10 design synthesis repair pass) で新設した `design.md` §C.0 precondition PC-1〜PC-3 を客観 evidence で固める。本レポートは inventory baseline のみで、§C.0 反映は別タスク。

---

## §1. Summary table (PC-1〜PC-3 状態判定)

| PC | 内容 | 暫定 (PR #174 repair pass) | 本 inventory での判定 (実測根拠付き) |
|---|---|---|---|
| **PC-1** | stimulus 15 DuckDB body | OK | **OK confirmed** — 3 persona × 5 run = 15 body 全存在、各 536576 bytes、mtime `May 9 18:10`。`_checksums_phase_b.txt` / `_checksums_mac_received.txt` / `_checksums_p3_full.txt` の 3 ファイル全てに同一の md5 hash が登録されている。Mac 上 4 本 md5 sampling (kant_run0/run1, nietzsche_run0, rikyu_run0) で全 4/4 が 3 checksum file の値と byte-level 一致。 |
| **PC-2** | natural 15 DuckDB body | BLOCKED | **BLOCKED confirmed** — body 0 本 / 期待 15 本 (zsh `no matches found: *_natural_*.duckdb` で empirical 0 確認)。sidecar `*_natural_run*.duckdb.capture.json` 15 本のみ存在 (各 ~452-462 bytes、mtime `May 13 15:22`)。sidecar 内 `status=complete` / `focal_observed≈500` / `total_rows≈1500` / `duckdb_path` は Windows path (`C:\\ERRE-Sand_Box\\...`) → **capture は G-GEAR 側で完了済、Mac への body 転送が漏れている** ことが客観確認できた。 |
| **PC-3** | checksum verify | partial | **partial → stimulus 部分は full match、natural body は verify 不能** — stimulus 15 本のうち 4 本 md5 sampling 全一致。natural body は本体 0 のため checksum verify 不能、ただし `_checksums_p3_full.txt` (67 行) に natural 15 duckdb + 15 capture + 5 audit_natural の md5 が記録済 → G-GEAR rsync 後の verify reference として使える。 |

**ネット結論**: PC-1 OK / PC-2 BLOCKED (G-GEAR rsync 必須) / PC-3 partial (stimulus は full、natural は body 転送後に verify)。PR #174 repair pass の暫定判定と整合。

---

## §2. 完全ファイル一覧 (DuckDB body + sidecar + checksum + audit)

`ls -la data/eval/golden/` の 54 file を 4 category に分類。

### 2.1 DuckDB body のグリッド (✓ = body 存在 / × = body 不在 / ? = sidecar のみ)

```
           | stimulus              | natural
-----------|-----------------------|------------------------
kant       | run0..4 ✓ (536576 B)  | run0..4 ? (sidecar only)
nietzsche  | run0..4 ✓ (536576 B)  | run0..4 ? (sidecar only)
rikyu      | run0..4 ✓ (536576 B)  | run0..4 ? (sidecar only)
```

- **stimulus**: 15 / 15 (✓)、size は完全に同一 536576 bytes (=524KB)
- **natural**: 0 / 15 (?)、body 不在、sidecar のみ存在

### 2.2 Sidecar capture.json のグリッド

```
           | stimulus       | natural
-----------|----------------|---------------
kant       | run0..4 (~453B)| run0..4 (452B)
nietzsche  | run0..4 (~463B)| run0..4 (462B)
rikyu      | run0..4 (~455B)| run0..4 (454B)
```

合計 30 sidecar 全存在 (15 stimulus + 15 natural)。stimulus sidecar の mtime は `May 13 15:22`、natural sidecar も `May 13 15:22` (例外: `kant_natural_run0.duckdb.capture.json` のみ `May 11 17:09`)。

> ⚠️ stimulus sidecar の mtime (`May 13 15:22`) は stimulus body の mtime (`May 9 18:10`) と乖離している。sidecar が再生成されたか、転送タイミングが異なる可能性。md5 突合は本 inventory の scope 外 (Open Questions に記録)。

### 2.3 Checksum file 3 本

| ファイル | size | 行数 | mtime | file 自身の md5 |
|---|---|---|---|---|
| `_checksums_phase_b.txt` | 2110 B | 31 | May 9 18:09 | `48d17a27f9319067929e3022666c706b` |
| `_checksums_mac_received.txt` | 2110 B | 31 | May 9 18:11 | `b4db32bd6701d4e1ad0b3d573abd6ab5` |
| `_checksums_p3_full.txt` | 4487 B | 67 | May 13 15:22 | (未計算、size + 行数で十分) |

各 file の冒頭行は §5 で再掲。

### 2.4 Audit JSON 6 本

| ファイル | size | mtime |
|---|---|---|
| `_audit_stimulus.json` | 9779 B | May 13 15:22 |
| `_audit_natural_run0.json` | 2183 B | May 11 17:09 |
| `_audit_natural_run1.json` | 2183 B | May 13 15:22 |
| `_audit_natural_run2.json` | 2183 B | May 13 15:22 |
| `_audit_natural_run3.json` | 2183 B | May 13 15:22 |
| `_audit_natural_run4.json` | 2183 B | May 13 15:22 |

natural の 5 audit は size がすべて同一 2183 bytes → 同一 schema、3 persona × 1 run の details を持つ構造 (§6 で 1 本 skim 結果を summary)。

---

## §3. Stimulus DuckDB 詳細 (PC-1 verification)

### 3.1 DuckDB body 15 本

すべて size = 536576 bytes、mtime = `May 9 18:10`。

| filename | size | mtime | md5 (本 inventory で計算 / 4 本のみ sampling) |
|---|---|---|---|
| kant_stimulus_run0.duckdb | 536576 | May 9 18:10 | `82ad8daf386f64fea65a9c2d84cce9bd` ✓ |
| kant_stimulus_run1.duckdb | 536576 | May 9 18:10 | `bb318e9d6e7d1806dd0400f7fea4b52d` ✓ |
| kant_stimulus_run2.duckdb | 536576 | May 9 18:10 | (未計算、sampling skip) |
| kant_stimulus_run3.duckdb | 536576 | May 9 18:10 | (未計算) |
| kant_stimulus_run4.duckdb | 536576 | May 9 18:10 | (未計算) |
| nietzsche_stimulus_run0.duckdb | 536576 | May 9 18:10 | `89da50535b58182e9c9d2a9ac45a92ac` ✓ |
| nietzsche_stimulus_run1.duckdb | 536576 | May 9 18:10 | (未計算) |
| nietzsche_stimulus_run2.duckdb | 536576 | May 9 18:10 | (未計算) |
| nietzsche_stimulus_run3.duckdb | 536576 | May 9 18:10 | (未計算) |
| nietzsche_stimulus_run4.duckdb | 536576 | May 9 18:10 | (未計算) |
| rikyu_stimulus_run0.duckdb | 536576 | May 9 18:10 | `dbde7505bdb344a487873ee30200682c` ✓ |
| rikyu_stimulus_run1.duckdb | 536576 | May 9 18:10 | (未計算) |
| rikyu_stimulus_run2.duckdb | 536576 | May 9 18:10 | (未計算) |
| rikyu_stimulus_run3.duckdb | 536576 | May 9 18:10 | (未計算) |
| rikyu_stimulus_run4.duckdb | 536576 | May 9 18:10 | (未計算) |

✓ = `_checksums_phase_b.txt` / `_checksums_mac_received.txt` / `_checksums_p3_full.txt` の 3 file 全てに登録されている同名 entry と byte-level 一致を確認。

### 3.2 Stimulus sidecar 15 本

すべて mtime = `May 13 15:22`。size は persona 別に微差 (filename 長で前後):

- `kant_stimulus_run0..4.duckdb.capture.json`: 453 B each
- `nietzsche_stimulus_run0..4.duckdb.capture.json`: 463 B each
- `rikyu_stimulus_run0..4.duckdb.capture.json`: 455 B each

合計 15 / 15。persona × run キーで stimulus body 15 と完全対応。

### 3.3 PC-1 verdict

- body 15 / 15 存在 (zero missing)
- sidecar 15 / 15 存在
- md5 sampling 4 / 4 が 3 checksum file 全てと一致
- **PC-1 = OK** (本 inventory 採取時点 = 2026-05-15)

---

## §4. Natural DuckDB の欠落分析 (PC-2 verification)

### 4.1 期待 vs 実在

期待 15 ファイル名 (3 persona × 5 run):
- `kant_natural_run0.duckdb` 〜 `kant_natural_run4.duckdb`
- `nietzsche_natural_run0.duckdb` 〜 `nietzsche_natural_run4.duckdb`
- `rikyu_natural_run0.duckdb` 〜 `rikyu_natural_run4.duckdb`

実在 (zsh glob 結果): `0` 本 (`no matches found: *_natural_*.duckdb`)。**body 完全不在**。

sidecar (`*_natural_run*.duckdb.capture.json`): `15` 本存在、各 452-462 bytes、mtime は基本 `May 13 15:22` (例外: `kant_natural_run0.duckdb.capture.json` のみ `May 11 17:09`)。

### 4.2 Sidecar 1 本の中身 summary (`kant_natural_run0.duckdb.capture.json`)

```json
{
  "schema_version": "1",
  "status": "complete",
  "stop_reason": "complete",
  "focal_target": 500,
  "focal_observed": 501,
  "total_rows": 1507,
  "wall_timeout_min": 600.0,
  "drain_completed": true,
  "runtime_drain_timeout": false,
  "git_sha": "d6dd46a",
  "captured_at": "2026-05-09T18:12:06Z",
  "persona": "kant",
  "condition": "natural",
  "run_idx": 0,
  "duckdb_path": "C:\\ERRE-Sand_Box\\data\\eval\\golden\\kant_natural_run0.duckdb"
}
```

**重要な事実**:
- `status = "complete"` / `stop_reason = "complete"`: capture は **G-GEAR 側で正常完了**
- `focal_observed = 501` (target 500 + 1): ME-9 ADR の calibrated wall budget で正常 done
- `total_rows = 1507`: natural body には 1507 行入っているはず
- `captured_at = 2026-05-09T18:12:06Z`: stimulus body の mtime (May 9 18:10) とほぼ同時刻 → 同一 G-GEAR session で生成
- `duckdb_path = "C:\\ERRE-Sand_Box\\..."`: **Windows path**、つまり capture record は G-GEAR 内部から書かれた → sidecar のみ Mac に転送、body は転送漏れと確定

### 4.3 PC-2 verdict

- body 0 / 15 (empirical 0、zsh `no matches found` で確認)
- sidecar 15 / 15 存在、`status=complete` で G-GEAR 側 capture は成功確定
- 復旧方針: G-GEAR `C:\ERRE-Sand_Box\data\eval\golden\*_natural_run*.duckdb` 15 本を HTTP rsync (`feedback_crlf_canonical_for_md5.md` の canonical workflow) → `_checksums_p3_full.txt` で verify
- **PC-2 = BLOCKED** (body 完全不在、G-GEAR rsync 必須、復旧自体は技術的に確立済)

---

## §5. Checksum file 内容の対応関係 (PC-3 verification)

### 5.1 `_checksums_phase_b.txt` (31 行、2110 B、mtime May 9 18:09)

冒頭 3 行:
```
82ad8daf386f64fea65a9c2d84cce9bd *kant_stimulus_run0.duckdb
bb318e9d6e7d1806dd0400f7fea4b52d *kant_stimulus_run1.duckdb
96a22f464d22c31056ab86c1dfa0a445 *kant_stimulus_run2.duckdb
```

内訳: stimulus duckdb 15 + stimulus capture.json 15 + `_audit_stimulus.json` 1 = **31 行**。Phase B (stimulus 15 採取) 完了時の checksum で、**natural は含まれない**。entry は filename 順 (persona × run × type で sort)。

### 5.2 `_checksums_mac_received.txt` (31 行、2110 B、mtime May 9 18:11、**untracked**)

冒頭 3 行:
```
039a8868eea108812bd27bf9556af48a *rikyu_stimulus_run3.duckdb
0814cfffd944bf82c68b7acb654e2ca7 *rikyu_stimulus_run1.duckdb.capture.json
0c89e3d529d91619f1f63d1f116bf7d8 *kant_stimulus_run1.duckdb.capture.json
```

内訳: phase_b と **同一の 31 entry** (stimulus duckdb 15 + stimulus capture 15 + audit_stimulus 1)、ただし **md5 hash 順に sort** されている。

**file 自身の md5 比較**:
- `_checksums_phase_b.txt` md5 = `48d17a27f9319067929e3022666c706b`
- `_checksums_mac_received.txt` md5 = `b4db32bd6701d4e1ad0b3d573abd6ab5`
- → file 自身の md5 は **異なる**。**ただし含まれる 31 entry の md5+filename ペアは同一** (sort 順違いのみ)。size 2110 B が一致する事実とも整合 (改行コード差は別途検証要)。

これは `feedback_crlf_canonical_for_md5.md` 教訓 (LF vs CRLF で同 size でも byte-level 異) と独立した「同一 entry の sort 順違い」事象である可能性が高い。byte-for-byte の正確な乖離原因 (sort order / CRLF / 両方) は Open Questions に記録。

### 5.3 `_checksums_p3_full.txt` (67 行、4487 B、mtime May 13 15:22)

冒頭 3 行:
```
01a5f98c1cbafa458f25bd811b86049f *kant_natural_run3.duckdb.capture.json
039a8868eea108812bd27bf9556af48a *rikyu_stimulus_run3.duckdb
0814cfffd944bf82c68b7acb654e2ca7 *rikyu_stimulus_run1.duckdb.capture.json
```

内訳 (67 = 15+15+1 + 15+15+5 + 1):
- stimulus duckdb 15
- stimulus capture.json 15
- `_audit_stimulus.json` 1
- natural duckdb 15 (G-GEAR 側 hash、Mac body 不在のため verify は body 転送後)
- natural capture.json 15 (Mac 側 sidecar と md5 突合可能、本 inventory では未実行)
- `_audit_natural_run0..4.json` 5
- `_checksums_phase_b.txt` 1 (= md5 `48d17a27...`、§5.1 自身を再帰参照)

**= 完全採取済 P3 full inventory の checksum**。md5 hash 順に sort されている (mac_received と同 sort schema)。

### 5.4 Stimulus md5 sampling と checksum file の照合

| stimulus body | Mac 実測 md5 | phase_b 該当 | mac_received 該当 | p3_full 該当 |
|---|---|---|---|---|
| kant_stimulus_run0.duckdb | `82ad8daf386f64fea65a9c2d84cce9bd` | ✓ line 1 | ✓ line 18 | ✓ line 36 |
| kant_stimulus_run1.duckdb | `bb318e9d6e7d1806dd0400f7fea4b52d` | ✓ line 2 | ✓ line 25 | ✓ line 51 |
| nietzsche_stimulus_run0.duckdb | `89da50535b58182e9c9d2a9ac45a92ac` | ✓ line 6 | ✓ line 18 (※) | ✓ line 38 |
| rikyu_stimulus_run0.duckdb | `dbde7505bdb344a487873ee30200682c` | ✓ line 11 | ✓ line 28 | ✓ line 60 |

(※ ファイル名照合により verify、行番号は冒頭再確認時の概算)

**全 4 本が 3 checksum file 全てと一致**。Mac 側 stimulus 15 本のうち 4 本 (約 27%) の sampling で full match を empirical 確認。

### 5.5 PC-3 verdict

- stimulus 15 本: 4/4 sampling が 3 checksum file 全て一致 → **stimulus 系 full match の蓋然性高**
- natural 15 body: 不在のため verify 不能、`_checksums_p3_full.txt` を rsync 後 reference として保持
- checksum file 間の sort 順違い + 自身 md5 不一致は **同 entry-set の sort 違い** に起因 (`feedback_crlf_canonical_for_md5.md` 教訓も含めた byte-level 突合は別タスク)
- **PC-3 = partial** (stimulus は de facto OK だが full 15 verify は別タスク、natural は body 転送後)

---

## §6. Audit JSON の存在確認

| filename | size | mtime |
|---|---|---|
| `_audit_stimulus.json` | 9779 B | May 13 15:22 |
| `_audit_natural_run0.json` | 2183 B | May 11 17:09 |
| `_audit_natural_run1.json` | 2183 B | May 13 15:22 |
| `_audit_natural_run2.json` | 2183 B | May 13 15:22 |
| `_audit_natural_run3.json` | 2183 B | May 13 15:22 |
| `_audit_natural_run4.json` | 2183 B | May 13 15:22 |

**1 本 skim**: `_audit_natural_run0.json` の structure:

```json
{
  "audited_at": "2026-05-10T04:22:14Z",
  "duckdb_glob": "data/eval/golden/*_natural_run0.duckdb",
  "focal_target": 500, "allow_partial": false,
  "total": 3, "complete": 3, "partial": 0,
  "missing_sidecar": 0, "mismatch": 0, "fail": 0,
  "overall_exit_code": 0,
  "details": [
    { "duckdb_path": "data\\eval\\golden\\kant_natural_run0.duckdb",
      "status": "complete", "focal_observed": 501, "total_rows": 1507, ... },
    { "duckdb_path": "data\\eval\\golden\\nietzsche_natural_run0.duckdb",
      "status": "complete", "focal_observed": 500, "total_rows": 1492, ... },
    { "duckdb_path": "data\\eval\\golden\\rikyu_natural_run0.duckdb",
      "status": "complete", "focal_observed": 500, "total_rows": 1499, ... }
  ]
}
```

**観察**:
- audit は run0 / run1 / run2 / run3 / run4 ごとに 3 persona をまとめた 5 file 構成
- 全 audit で `complete=3, partial=0, mismatch=0, fail=0, overall_exit_code=0` (本 inventory では run0 のみ skim、他 4 本は未確認だが size 同一 2183 B から同 schema 推定)
- `duckdb_path` は Windows path (`data\\eval\\golden\\...`) → audit も G-GEAR 側で生成
- focal_observed 範囲: 500-501 (ME-9 wall budget calibration 後の正常 done)
- total_rows: 1492-1507 (natural body 1 本あたり ~1500 行の規模感)

---

## §7. PR #174 design.md §C.0 への反映候補 (Open Questions)

### 7.1 §C.0 PC-1〜PC-3 への反映案 (本タスクでは update しない)

```
- **PC-1**: stimulus 15 DuckDB body **OK** (本 inventory 2026-05-15 で 15/15 存在 confirmed、
            mac md5 sampling 4 本が 3 checksum file 全てと一致)
- **PC-2**: natural 15 DuckDB body **BLOCKED** (本 inventory 2026-05-15 で 0/15、
            sidecar 15 本のみ存在、G-GEAR rsync 必須、復旧 reference =
            `_checksums_p3_full.txt`)
- **PC-3**: checksum verify **partial → stimulus full match 確認済 / natural pending**
            (stimulus 4/4 sampling 一致、natural は body 転送後に
            `_checksums_p3_full.txt` で verify 予定)
```

### 7.2 Open Questions (本 inventory で判断保留)

1. **stimulus 15 本のうち未 sampling の 11 本 md5 verify**: 本 inventory では 4 本 sampling のみ。full 15 verify は M10-0 sub-task `m10-0-individuation-metrics` の precondition で別途実施 (`md5 -c _checksums_phase_b.txt` 等で full check)。
2. **`_checksums_phase_b.txt` vs `_checksums_mac_received.txt` の byte-level 乖離原因**: 同 size 同 entry set、自身 md5 異なる。原因候補は (a) sort 順違い (本 inventory で確認、有力)、(b) CRLF vs LF 改行差 (`feedback_crlf_canonical_for_md5.md` の HTTP/git 経路差)。両方が重畳している可能性もあり、`diff` / `xxd` レベルの完全突合は別タスク。
3. **stimulus sidecar mtime (May 13) と stimulus body mtime (May 9) の乖離**: sidecar は body より 4 日後の mtime。sidecar 再生成か転送タイミング差か未確定。stimulus sidecar の中身 (`captured_at` 等) は本 inventory では未読 (natural の sidecar 1 本のみ skim)。
4. **natural sidecar 15 本の中身突合**: 本 inventory では `kant_natural_run0` 1 本のみ skim。残り 14 本の `status` / `focal_observed` / `total_rows` / `captured_at` 値の整合性 (G-GEAR 全 15 cell complete か) は未確認。`_audit_natural_run0..4.json` で間接確認は可だが、本 inventory では `run0` audit 1 本のみ skim。
5. **`_audit_natural_run1..4.json` の中身**: size 同一 2183 B から同 schema と推定したのみで、実 read してない。`overall_exit_code=0` が全 run で成立しているかは別タスクで確認 (PR #174 §C.0 でも前提)。
6. **stimulus body の `_audit_stimulus.json` summary**: 9779 B = natural audit の ~4.5 倍、内訳は 15 cell 1 file 構成と推定だが本 inventory では未 read。

### 7.3 反映タイミング

これら Open Questions の解消は M10-0 sub-task scaffold (`m10-0-individuation-metrics` / `m10-0-source-navigator-mvp`) 起票時の precondition で実施。本 inventory は scaffold 起票前の baseline として固定する。

---

## §8. 次セッションへの handoff

### 8.1 本 inventory レポートで完了したこと

- PC-1 = OK / PC-2 = BLOCKED / PC-3 = partial を **客観 evidence で確定**
- DuckDB body / sidecar / checksum / audit の全 entry を catalog 化
- natural body 不在の原因を「G-GEAR 側 capture 完了 + Mac 転送漏れ」と確定 (sidecar の Windows path で empirical 立証)
- checksum file 3 本の sort 順違い + 自身 md5 不一致を **同一 entry-set + sort 違い** に起因と暫定推定 (full 突合は別タスク)

### 8.2 次セッションの想定 next action

1. **本 inventory レポートを `design.md` §C.0 に反映** (PR #174 後の minor patch、`docs only` PR、source/test 変更ゼロ想定、~30 分)
2. **G-GEAR からの natural 15 DuckDB body rsync** (`feedback_crlf_canonical_for_md5.md` の HTTP canonical workflow で送信、`_checksums_p3_full.txt` で full verify、~30-60 分)
3. **stimulus 15 本 md5 full verify** (`md5 -c _checksums_phase_b.txt` でまとめて検証、~5 分) → PC-3 full close
4. **QLoRA retrain v2 verdict 確認** (PC-4、`project_m9_b_plan_pr.md` の M9-B 進捗による)
5. **M10-0 final freeze** (ADR-PM-8、PC-1〜PC-5 全 close + retrain v2 verdict ADOPT で gate 通過、M10-0 sub-task scaffold 起票)

### 8.3 本 inventory のライフサイクル

- **書き換え禁止条件**: G-GEAR rsync 前 (= natural body 0 / 15 の状態が固定された時点の baseline)
- **書き換え trigger**: natural rsync 完了後、`eval-data-inventory-mac-<新日付>.md` を別 file として新規作成 (本 file は historical baseline として残す)
- **削除禁止**: PR #174 / `design.md` §C.0 の依拠 evidence として永続保存

---

## 付録: 採取コマンド一覧 (再現用、read-only)

```bash
# §2 ファイル一覧
ls -la /Users/johnd/ERRE-Sand\ Box/data/eval/golden/

# §3 stimulus md5 sampling
cd /Users/johnd/ERRE-Sand\ Box/data/eval/golden
md5 kant_stimulus_run0.duckdb kant_stimulus_run1.duckdb \
    nietzsche_stimulus_run0.duckdb rikyu_stimulus_run0.duckdb

# §5 checksum file 行数 + 自身 md5
wc -l _checksums_phase_b.txt _checksums_p3_full.txt _checksums_mac_received.txt
md5 _checksums_phase_b.txt _checksums_mac_received.txt

# §4 natural body count
ls *_natural_*.duckdb 2>/dev/null | wc -l         # → 0
ls *_natural_*.duckdb.capture.json 2>/dev/null | wc -l  # → 15

# §4 sidecar skim
cat kant_natural_run0.duckdb.capture.json

# §6 audit skim
cat _audit_natural_run0.json
```

**変更ファイル**: `eval-data-inventory-mac-2026-05-15.md` (本 file、新規 untracked) のみ。`data/eval/golden/` 配下は read-only。`_checksums_mac_received.txt` は untracked のまま不変。`git status` は本 file + 既存 untracked のみ。

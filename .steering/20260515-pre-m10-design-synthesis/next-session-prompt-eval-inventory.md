# 次セッション用プロンプト — Mac eval data inventory (read-only)

> **想定使用**: 次セッション開始時、Claude Code (Sonnet 推奨、Plan mode 不要) にコピペで投入。
> **目的**: `data/eval/golden/` の現状を **read-only で inventory 化** し、PR #174 (本 repair pass) で確定した PC-1〜PC-3 precondition を客観 evidence で更新する。
> **想定所要**: ~15-25 分。
> **制約**: 一切のファイル削除 / 移動 / 上書き / commit を禁止。inventory レポートを `.steering/` に出力するだけ。

---

## コピペ用プロンプト本文 (ここから ↓)

`data/eval/golden/` 配下の評価データ inventory を作成してください。コード変更ゼロ、ファイル削除/移動/上書きゼロ、commit しない、untracked file (特に `_checksums_mac_received.txt`) は **絶対に触らない**。**read-only inventory のみ**。

## 背景

PR #174 (本 repo merge 済) の pre-M10 design synthesis repair pass で、`design.md` §C.0 に precondition PC-1〜PC-5 を新設しました。本タスクの目的は、その PC-1〜PC-3 (Mac 上の data availability) を客観 evidence で確定し、次セッション (QLoRA retrain v2 verdict 後の M10-0 sub-task scaffold 起票) のための inventory baseline を整えることです。

repair pass 時点の暫定判定:
- PC-1: stimulus 15 DuckDB body **OK** (3 persona × 5 run、各 ~536KB)
- PC-2: natural 15 DuckDB body **BLOCKED** (本体不在、sidecar `.capture.json` のみ存在の疑い)
- PC-3: checksum verify **partial** (`_checksums_phase_b.txt` / `_checksums_mac_received.txt` / `_checksums_p3_full.txt` の対応関係未確認)

本タスクはこの暫定判定を、ファイル名一覧 + サイズ + (任意で) md5 hash で固めた inventory レポートに変換します。

## 重要制約

- ❌ `data/eval/golden/` 配下のファイルを **一切** 削除 / 移動 / 上書きしない
- ❌ `_checksums_mac_received.txt` は **絶対に触らない** (read のみ可)
- ❌ `data/eval/calibration/` や `data/lora/` には踏み込まない
- ❌ `src/erre_sandbox/` / `tests/` / `contracts/` / `evidence/` などコードは一切触らない
- ❌ commit / push / PR 作成 / branch 作成 はしない
- ❌ ADR の新規追加 / decisions.md 更新 / design.md 更新は **本タスクでは行わない** (inventory レポート保存のみ)
- ✅ read-only コマンド (`ls` / `wc` / `md5` / `du` / `file` / `python -c "import duckdb; ..."` で DuckDB 構造を読むのは可) のみ使用
- ✅ inventory レポートを `.steering/20260515-pre-m10-design-synthesis/eval-data-inventory-mac-<YYYY-MM-DD>.md` に保存
- ✅ 不明 / 判断保留事項は「Open Questions」セクションに残す (sweep して埋めようとしない)

## 期待 output: inventory レポート

`.steering/20260515-pre-m10-design-synthesis/eval-data-inventory-mac-<YYYY-MM-DD>.md` に以下の section 構成で出力 (Markdown、~150-250 行想定):

### §1. Summary table (PC-1〜PC-3 状態判定)

repair pass の precondition table を inventory 実測値で update:

| PC | 内容 | 暫定 (repair pass) | 本 inventory での判定 (実測根拠付き) |
|---|---|---|---|
| PC-1 | stimulus 15 DuckDB body | OK | (本 inventory で確認) |
| PC-2 | natural 15 DuckDB body | BLOCKED | (本 inventory で確認) |
| PC-3 | checksum verify | partial | (本 inventory で確認) |

### §2. 完全ファイル一覧 (DuckDB body + sidecar + checksum + audit)

`ls -la data/eval/golden/` 全件を 4 category に分類:

1. **DuckDB body** (`.duckdb` 拡張子のみ、`.capture.json` を含まない): persona × run × variant (stimulus / natural) のグリッドで表示
2. **Sidecar capture.json** (`*.duckdb.capture.json`): 同じくグリッド表示
3. **Checksum file** (`_checksums_*.txt`): 各ファイルの行数 + 先頭 3 行 (どの DuckDB の checksum か把握)
4. **Audit JSON** (`_audit_*.json`): ファイル名のみ列挙

DuckDB body のグリッドは以下のフォーマット:

```
persona × variant × run のグリッド (✓ = body 存在、× = body 不在、? = sidecar のみ)

           | stimulus  | natural
-----------|-----------|----------
kant       | run0..4   | run0..4
nietzsche  | run0..4   | run0..4
rikyu      | run0..4   | run0..4
```

各 cell に `(✓ size=536576)` or `(× sidecar only)` を入れる。

### §3. Stimulus DuckDB 詳細 (PC-1 verification)

stimulus 15 本それぞれについて:
- filename
- size (bytes)
- mtime (`stat -f "%Sm"` macOS)
- (任意) md5 hash — `md5 <file>` で計算可

sidecar `.capture.json` 15 本それぞれについて:
- filename
- size
- mtime

両者の persona × run キーが 15 / 15 で対応しているか verify。

### §4. Natural DuckDB の欠落分析 (PC-2 verification)

natural 15 本の DuckDB body **不在** を客観確認:

- 期待 15 ファイル名 list (3 persona × 5 run): `kant_natural_run0.duckdb` 〜 `rikyu_natural_run4.duckdb`
- 実在 0 / 期待 15 を ls 結果で再確認
- sidecar `.capture.json` は 15 本存在することを再確認 (= body 不在だが capture 記録は残っている事実)
- sidecar 1 本 (例: `kant_natural_run0.duckdb.capture.json`) を **read** して中身 (`run_id` / `wall_seconds` / `tick_count` / capture timestamp 等) を summary、capture 自体は成功して body が転送漏れだった事実を確認

### §5. Checksum file 内容の対応関係 (PC-3 verification)

3 checksum file それぞれを read し、何の checksum が記録されているかを文字列 grep で identify:

- `_checksums_phase_b.txt` (~2110 bytes、stimulus 系の疑い)
- `_checksums_p3_full.txt` (~4487 bytes、stimulus + natural の疑い)
- `_checksums_mac_received.txt` (~2110 bytes、Mac 受信時の checksum、size が phase_b と同一 = stimulus 系の疑い)

各 file の **行数** + **記録されている filename pattern (grep -o '\.duckdb' / persona 名 / variant 名 等)** + **冒頭 3-5 行 verbatim** を report。

その上で:
- stimulus 15 本の md5 hash (§3 で計算) と `_checksums_*.txt` の値が一致するか **目視で 1-2 本確認** (全本の verify は M10-0 sub-task の precondition で別途、本 inventory では sampling のみ)
- 一致 / 不一致 / 部分一致 のいずれかを判定

**重要**: checksum file の中身を **変更しない**。read-only で内容を report に転記するだけ。

### §6. Audit JSON の存在確認

`_audit_stimulus.json` / `_audit_natural_run0.json` 〜 `_audit_natural_run4.json` のファイル名 + size + mtime を列挙。中身読込は任意 (1 本のみ skim して structure を summary すれば十分)。

### §7. PR #174 design.md §C.0 への反映候補 (Open Questions)

本 inventory で確定した PC-1〜PC-3 状態を `design.md` §C.0 にどう反映するかを **提案のみ** (本タスクでは update しない):

- PC-1: 「OK (本 inventory で stimulus 15 confirmed at <date>)」のような明示
- PC-2: 「BLOCKED (sidecar 15 本のみ存在、body 0 本、G-GEAR rsync 必須)」のような明示
- PC-3: 「partial → __ (stimulus md5 sampling で <一致 / 不一致> 確認)」

加えて Open Questions として、本 inventory で判断保留した事項を列挙:
- 例: `_checksums_phase_b.txt` と `_checksums_mac_received.txt` の size が同一だが、内容が byte-for-byte 同一か (W-7 教訓: 内部 git checkout LF vs HTTP CRLF で同 file size でも内容が違う可能性) は inventory レベルでは判断保留、md5 確認を別タスクで
- 例: stimulus 15 本の md5 が `_checksums_mac_received.txt` と全 match するかは full verification を別タスクで

### §8. 次セッションへの handoff

本 inventory レポートを `design.md` §C.0 に反映する作業は **別タスク** (本タスクでは inventory 提出まで)。

次セッションの想定 next action:
1. 本 inventory レポートを `design.md` §C.0 に反映 (PC-1〜PC-3 を inventory 実測値で update)
2. G-GEAR からの natural 15 DuckDB body rsync (PC-2 解消)
3. checksum full verify (PC-3 解消)
4. QLoRA retrain v2 verdict 確認 (PC-4)
5. M10-0 final freeze (ADR-PM-8)

## 完了条件 (本タスク)

- [ ] `.steering/20260515-pre-m10-design-synthesis/eval-data-inventory-mac-<YYYY-MM-DD>.md` が新規作成され、§1-§8 が埋まる
- [ ] inventory レポート以外の **どのファイルも変更されていない** (`git status` で確認、本 inventory file 以外 untracked / modified が出ない)
- [ ] `data/eval/golden/_checksums_mac_received.txt` が変更されていない (`git status` で untracked のまま、または既存と同一)
- [ ] `git diff` がゼロ (本 inventory file は新規 untracked なので diff には出ない)
- [ ] PC-1 / PC-2 / PC-3 の状態判定が客観 evidence (ファイル名一覧 + size + md5 sampling) に基づく
- [ ] Open Questions が明示され、判断保留事項を後続タスクに handoff 可能

## 報告フォーマット (本タスク完了時、User への報告)

```
- inventory レポート: <path>
- PC-1: <judgement> (root evidence)
- PC-2: <judgement> (root evidence)
- PC-3: <judgement> (root evidence)
- Open Questions: <count> 件 (代表 2-3 件を 1 行 summary)
- 触ったファイル: <inventory レポート 1 件のみ>
- 触らなかったことを確認したファイル: _checksums_mac_received.txt / その他 data/eval/golden/ 配下
- 次セッションの first action: <design.md §C.0 反映>
```

報告は ~200 字以内、簡潔に。

## 参照

- `PR #174` (本 repair pass、merged 後の main): `design.md` §C.0 PC-1〜PC-5
- `decisions.md` ADR-PM-8 (M10-0 final freeze gate を retrain v2 verdict 後に置く根拠)
- `feedback_crlf_canonical_for_md5.md` (HTTP CRLF が canonical の教訓、checksum 突合の前提)
- `project_m9_eval_phase2_run0_incident.md` (ME-9 ADR、Phase 2 run0 で 3 natural cell FAILED の incident、natural body の所在に関わる背景)

## コピペ用プロンプト本文 (ここまで ↑)

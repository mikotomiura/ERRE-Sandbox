# G-GEAR セッション用プロンプト — Phase 2 run0 `.tmp` rescue verify

> このプロンプトは Mac セッション (2026-05-06、PR #137 merge 直後想定) で起草。
> G-GEAR (Windows / RTX 5060 Ti 16GB / Ollama 0.22.0) で `/clear` 後に
> 全文をコピペして送る前提。
>
> **本セッションは採取しない**。Phase 2 run0 で wall=360 min FAILED した
> 3 cell の `.tmp` が DuckDB として読めるかを検証して報告するのが唯一の
> 目的。CLI fix が未 merge なので、partial の rescue を確定させずに調査だけ
> 行う。詳細は `decisions.md` ME-9、`blockers.md` "active incident: Phase 2
> run0 wall-timeout (2026-05-06)"、`cli-fix-and-audit-design.md` を参照。

---

## 本セッションで実行すること

タスク `20260430-m9-eval-system` の Phase 2 run0 wall-timeout incident の
rescue verify。**確定アクション 5 段の Step 1**。

成果物:
1. `.tmp` + `.tmp.wal` + 関連 sidecar の存在確認 (3 cell)
2. DuckDB として read 可能、行数が known empirical (focal/total) と一致するか
3. memory sqlite (`/tmp/p3_natural_*_run0.sqlite` など) の存在と sanity
4. 上記をまとめた report を Mac へ持ち帰る (HTTP rsync で 1 file 送るか、
   Mac 側に貼り付ける形でも OK)

**禁止事項** (CLI fix merge 前なので):
- `.tmp` を `*.duckdb` に rename しない (Codex H4: stale unlink 経路あり、
  primary 採取への混入禁止)
- 同 path で再採取コマンドを起動しない (`_resolve_output_paths` が `.tmp` を
  unlink する)
- run1 を打たない (本セッションは verify only)

## まず Read (この順)

```bash
# 1. 最新 main を pull
cd <repo-root>  # G-GEAR 上での ERRE-Sandbox path
git fetch origin
git checkout main
git pull --ff-only

# 2. 該当 .steering を読む
cat .steering/20260430-m9-eval-system/decisions.md | grep -A 80 "^## ME-9"
cat .steering/20260430-m9-eval-system/blockers.md | grep -A 80 "active incident"
cat .steering/20260430-m9-eval-system/cli-fix-and-audit-design.md
```

## Step 1 — `.tmp` ファイル存在確認

Phase 2 採取時の output path は launch prompt 通り `data/eval/golden/` のはず
だが、実機運用次第で `data/eval/phase2/` にしている可能性もあるので両方を
広めに探す。

```bash
# .tmp / .tmp.wal / .capture.json (将来の sidecar、現バイナリでは未生成) を
# 全部表示
find data/eval -maxdepth 3 -type f \( -name "*natural_run0*" -o -name "*natural*tmp*" \) -ls 2>/dev/null

# 期待される候補 (どれか一致):
#   data/eval/golden/kant_natural_run0.duckdb.tmp
#   data/eval/golden/kant_natural_run0.duckdb.tmp.wal  (←存在すれば未 CHECKPOINT)
#   data/eval/phase2/kant_natural_run0.duckdb.tmp
#   ...
```

`.tmp.wal` の有無は重要:
- **`.tmp` だけある & `.tmp.wal` 無し**: graceful path 通過済 (CHECKPOINT 完了)、
  read 可能性高い
- **`.tmp` + `.tmp.wal` 両方ある**: CHECKPOINT 直後で WAL replay が必要、
  DuckDB が再開時に統合してくれる (read-only open でも内部で replay)
- **`.tmp` 無し**: Codex H4 のシナリオ (SIGKILL / OOM / stale unlink)、rescue
  不能、incident close 条件 1 を即時 satisfy

## Step 2 — DuckDB read/count cross-check

```bash
# uv run python ... で repo の deps を使う (G-GEAR の Python から duckdb
# import)
uv run python <<'PY'
import duckdb
import os
import json
from pathlib import Path

# Phase 2 run0 の expected counts (Mac 側 incident report 由来)
EXPECTED = {
    "kant":      {"focal": 381, "total": 1158},
    "nietzsche": {"focal": 390, "total": 1169},
    "rikyu":     {"focal": 399, "total": 1182},
}

# 候補 path を全探索
candidates = []
for base in ("data/eval/golden", "data/eval/phase2"):
    for persona in ("kant", "nietzsche", "rikyu"):
        for suffix in (".duckdb.tmp", ".duckdb"):
            p = Path(base) / f"{persona}_natural_run0{suffix}"
            if p.exists():
                candidates.append((persona, p))

print(f"=== {len(candidates)} candidate file(s) ===")
report = {"verified_at": None, "cells": []}
import datetime
report["verified_at"] = datetime.datetime.now(datetime.UTC).isoformat()

for persona, path in candidates:
    info = {
        "persona": persona,
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "wal_exists": path.with_suffix(path.suffix + ".wal").exists(),
        "expected_focal": EXPECTED[persona]["focal"],
        "expected_total": EXPECTED[persona]["total"],
    }
    try:
        con = duckdb.connect(str(path), read_only=True)
        total = con.execute("SELECT COUNT(*) FROM raw_dialog.dialog").fetchone()[0]
        focal = con.execute(
            "SELECT COUNT(*) FROM raw_dialog.dialog WHERE speaker_persona_id = ?",
            [persona],
        ).fetchone()[0]
        max_tick = con.execute(
            "SELECT MAX(tick) FROM raw_dialog.dialog"
        ).fetchone()[0]
        run_ids = con.execute(
            "SELECT DISTINCT run_id FROM raw_dialog.dialog"
        ).fetchall()
        con.close()
        info.update({
            "read_ok": True,
            "actual_total": total,
            "actual_focal": focal,
            "max_tick": max_tick,
            "run_ids": [r[0] for r in run_ids],
            "focal_match": focal == EXPECTED[persona]["focal"],
            "total_match": total == EXPECTED[persona]["total"],
        })
    except Exception as exc:  # noqa: BLE001
        info.update({
            "read_ok": False,
            "error": f"{type(exc).__name__}: {exc!s}",
        })
    report["cells"].append(info)
    print(json.dumps(info, ensure_ascii=False, indent=2))

# memory sqlite 存在確認
print("\n=== memory sqlite ===")
mem_candidates = list(Path("/tmp").glob("p3*_natural_*_run0.sqlite")) + \
                 list(Path("/tmp").glob("p3a_natural_*_run0.sqlite"))
report["memory_sqlite"] = []
for mp in mem_candidates:
    info = {"path": str(mp), "size_bytes": mp.stat().st_size}
    report["memory_sqlite"].append(info)
    print(json.dumps(info, ensure_ascii=False))

# report を保存
out = Path("/tmp/p3_run0_rescue_report.json")
out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(f"\n=== report saved: {out} ===")
PY
```

**判定基準**:

| 状況 | rescue 判定 | 次アクション |
|---|---|---|
| 3 cell 全て `read_ok=True` & `focal_match=True` & `total_match=True` | **PASS — partial rescue 可** | `data/eval/partial/` に **コピー** (mv ではない) して保存、blockers.md に PASS 記録 |
| 一部 cell が `read_ok=False` | **PARTIAL — 検証可能 cell のみ rescue 可** | 検証成功 cell のみ `data/eval/partial/` に copy、失敗 cell は破棄 |
| `focal_match=False` または `total_match=False` (count 不一致) | **MISMATCH — Codex M1 in-flight drop の影響** | 実数値と Mac 側 expected の差分を blockers.md に記録、rescue は `actual_focal` を真値として |
| 全 cell `.tmp` 存在せず | **LOST — Codex H4 シナリオ確定** | rescue 不能、incident close 条件 1 を即時 satisfy、blockers.md に LOST 記録 |

## Step 3 — `.tmp` を破棄しないよう保全 copy

判定が PASS / PARTIAL / MISMATCH の場合のみ実行 (LOST はスキップ)。

```bash
# 保全先ディレクトリを新設 (本タスク外、CLI fix 完了後に正式 path 確定するが
# まず非破壊で stash)
mkdir -p data/eval/partial-stash-2026-05-06

# .tmp を copy (mv ではない、原本を残す)
for P in kant nietzsche rikyu; do
  for BASE in data/eval/golden data/eval/phase2; do
    SRC="${BASE}/${P}_natural_run0.duckdb.tmp"
    if [ -f "$SRC" ]; then
      cp -p "$SRC" "data/eval/partial-stash-2026-05-06/${P}_natural_run0.duckdb"
      # .wal も copy (DuckDB が読む時に同梱で動作するように)
      [ -f "${SRC}.wal" ] && cp -p "${SRC}.wal" "data/eval/partial-stash-2026-05-06/${P}_natural_run0.duckdb.wal"
      echo "stashed: $SRC -> data/eval/partial-stash-2026-05-06/${P}_natural_run0.duckdb"
    fi
  done
done

ls -la data/eval/partial-stash-2026-05-06/
```

**copy 後** に元 `.tmp` を消すかどうかは Mac の指示待ち (CLI fix 確定後に
`data/eval/partial/` 正式 path へ移動する想定)。

## Step 4 — report を Mac へ送る

```bash
# 1. report json を確認
cat /tmp/p3_run0_rescue_report.json

# 2. md5 receipt
cd /tmp && md5sum p3_run0_rescue_report.json | tee p3_run0_rescue_report.md5

# 3. Mac から取りに来る側のために HTTP server で expose
#    (P3a-finalize 2026-05-05 で validated パターン)
# G-GEAR (admin PowerShell):
New-NetFirewallRule -DisplayName "claude-rescue-report" -Direction Inbound `
  -Protocol TCP -LocalPort 8765 -Action Allow `
  -Program "C:\Users\johnd\AppData\Local\Programs\Python\Python311\python.exe"

# G-GEAR (作業 shell):
cd /tmp && python -m http.server 8765
# ipconfig | findstr IPv4 で G-GEAR LAN IP を確認

# Mac (別セッション、<G-GEAR-IP> は ipconfig の値):
#   curl -fOSs --connect-timeout 5 \
#     "http://<G-GEAR-IP>:8765/p3_run0_rescue_report.json"
#   curl -fOSs --connect-timeout 5 \
#     "http://<G-GEAR-IP>:8765/p3_run0_rescue_report.md5"

# 完了後 (admin PowerShell):
#   Remove-NetFirewallRule -DisplayName "claude-rescue-report"
```

**file size が小さい (<10KB JSON) ので、HTTP server を立てる代わりに
report の中身を本セッションで Mac へ直接貼り付ける選択肢もある**。
判断は user に委ねる。

## Step 5 — blockers.md 追記用テンプレート

Mac 側で本セッション report を受領したら、`.steering/20260430-m9-eval-system/
blockers.md` の active incident block の status 直前に以下を追記する。
G-GEAR セッションで report 内容を Mac に渡す際に、このテンプレートを
事前に埋めて貼り付けるのが効率的。

```markdown
### G-GEAR rescue verify 結果 (YYYY-MM-DD)

**判定**: PASS / PARTIAL / MISMATCH / LOST のいずれか
**source path**: data/eval/golden/ または data/eval/phase2/
**stash path**: data/eval/partial-stash-2026-05-06/ (G-GEAR local)

| persona | .tmp 存在 | .tmp.wal 存在 | read_ok | actual_focal | actual_total | match |
|---|---|---|---|---|---|---|
| kant | (yes/no) | (yes/no) | (yes/no) | <int> | <int> | (yes/no) |
| nietzsche | ... | ... | ... | ... | ... | ... |
| rikyu | ... | ... | ... | ... | ... | ... |

**memory sqlite**: <list of paths and sizes>
**追加観察**: <free-form note、特に Codex M1 in-flight drop の symptom が
あれば記録>
```

## 期待値とブロッカー予測

### 期待値 (Codex H4 の確率分析)

- **PASS シナリオ (~70%)**: graceful wall timeout path 通過、`finally` で
  `runtime.stop()` + drain + `write_with_checkpoint` 完走。`.tmp` 存在 + read 可
- **MISMATCH シナリオ (~20%)**: `.tmp` 存在 + read 可だが count 不一致 (Codex
  M1 in-flight turn drop)。partial として価値あり
- **PARTIAL シナリオ (~5%)**: 一部 cell のみ rescue 可
- **LOST シナリオ (~5%)**: SIGKILL / OOM-killer / 異常終了で `.tmp` 消失。
  この場合は incident close 条件を満たして次へ進む

### ブロッカー予測

1. **path が予想外 (`data/eval/...` 以下に存在しない)** — `find` 範囲を repo
   root 直下まで拡げて再走 (`find . -maxdepth 6 -name "*natural_run0*tmp*"`)
2. **DuckDB version mismatch で read エラー** — G-GEAR の DuckDB version を
   `uv run python -c "import duckdb; print(duckdb.__version__)"` で確認、
   採取時と差があれば本タスクで G-GEAR 側 deps を上書きせず、その version
   差を blockers に記録
3. **memory sqlite が参考にならない** — embedding のみで dialog data 無し
   (Mac 側 memory note 通り)、size 確認だけで十分

## 失敗時の Mac との交信

- 本セッション中に判断不能な状況 (例: `.tmp` 存在するが `read_only=True` でも
  `IO Error: Database file lock` 等) → 該当エラーメッセージを verbatim 抜き
  出して Mac へ。Codex 7 回目 review 候補に
- `.tmp.wal` 統合の挙動が DuckDB の予想と異なる → DuckDB version + OS +
  full traceback を保存、Mac で再現可能か確認

---

**所要見込み**: 15-30 min (探索 + verify + report 送信、CLI fix と並行で
Mac でやれる作業多数あるため気にせず実行可能)

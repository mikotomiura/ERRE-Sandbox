# Mac-side prompt — Phase B 30 binary files rsync from G-GEAR

**作成**: 2026-05-09 (G-GEAR Phase B 完了直後)
**用途**: Mac master セッション (Auto mode、Sonnet 推奨) で `/clear` 後の最初の prompt として貼り付け
**前提**: G-GEAR 側で `python -m http.server 8765 --bind 0.0.0.0` が `data/eval/golden/` で起動済 (G-GEAR Claude session が手配)

---

```
G-GEAR で 2026-05-09 に M9-eval Phase B (stimulus 15 cell) が完了 (commit
2812285、branch feature/m9-eval-phase-b-stimulus-baseline、origin push 済)。
本セッションは Mac master 側で G-GEAR から Phase B 30 binary files (15 .duckdb +
15 sidecar) を HTTP server 経由で pull し、md5 receipt と一致確認するセッション。
audit json と receipt は git push 済なので git fetch でも取得可能、HTTP は
binary 本体専用。

## 前提

- G-GEAR LAN IP: **192.168.3.85** (Wi-Fi 経由)
- HTTP server port: **8765** (G-GEAR 側で `data/eval/golden/` を root として serving)
- 期待ファイル: 32 件
  - 15 × `{kant,nietzsche,rikyu}_stimulus_run{0..4}.duckdb` (~524 KB each = 7.7 MB)
  - 15 × `*_stimulus_run*.duckdb.capture.json` (sidecars, ~470 B each)
  - `_audit_stimulus.json` (~10 KB、git でも取得可)
  - `_checksums_phase_b.txt` (md5 receipt 31 行、git でも取得可)
- Mac 側保存先: `/Users/johnd/ERRE-Sand Box/data/eval/golden/`
- 合計転送量: ~7.7 MB (LAN なら数秒)

## 最初にやること

### 1. 前提確認

```bash
# (a) Mac main HEAD が最新か (origin の Phase B receipt commit を含むか)
cd "/Users/johnd/ERRE-Sand Box"
git fetch origin
git log origin/feature/m9-eval-phase-b-stimulus-baseline -1 --oneline
# 期待: 0d4ea3e docs(m9): Phase B 完了記録 + 判断 8 (Windows native 転換) + Phase C handoff
git log origin/main -1 --oneline
# 期待: ae679ac Merge pull request #156 ...

# (b) G-GEAR 到達確認 (HTTP server 起動済前提)
curl -fsS --max-time 5 http://192.168.3.85:8765/ -o /dev/null && echo "G-GEAR HTTP OK" || echo "G-GEAR HTTP NOT REACHABLE"
# NG なら G-GEAR 側で server 未起動 → G-GEAR Claude session に「HTTP server 起動して」と依頼

# (c) Mac 側 data/eval/golden/ ディレクトリ作成
mkdir -p data/eval/golden/
ls -la data/eval/golden/
```

### 2. Receipt + audit を git で取得 (HTTP より git の方が auditable)

```bash
git checkout origin/feature/m9-eval-phase-b-stimulus-baseline -- \
  data/eval/golden/_checksums_phase_b.txt \
  data/eval/golden/_audit_stimulus.json
ls -la data/eval/golden/_checksums_phase_b.txt data/eval/golden/_audit_stimulus.json
wc -l data/eval/golden/_checksums_phase_b.txt  # 期待: 31 行
```

### 3. Binary 30 ファイルを HTTP で pull

```bash
cd data/eval/golden/
BASE="http://192.168.3.85:8765"
for P in kant nietzsche rikyu; do
  for RUN in 0 1 2 3 4; do
    F="${P}_stimulus_run${RUN}.duckdb"
    echo "--- pull ${F} ---"
    curl -fOSs "${BASE}/${F}"
    curl -fOSs "${BASE}/${F}.capture.json"
  done
done
echo "=== fetched count ==="
ls -1 *.duckdb | wc -l           # 期待: 15
ls -1 *.duckdb.capture.json | wc -l  # 期待: 15
cd -
```

### 4. md5 verify (G-GEAR receipt と一致確認)

```bash
cd data/eval/golden/
# Mac の md5 を G-GEAR receipt と同じフォーマットで計算
md5 -r *.duckdb *.duckdb.capture.json _audit_stimulus.json | \
  awk '{printf "%s *%s\n", $1, $2}' | sort > _checksums_mac_received.txt
sort _checksums_phase_b.txt > _checksums_phase_b.sorted.txt
diff _checksums_mac_received.txt _checksums_phase_b.sorted.txt
diff_rc=$?
if [ $diff_rc -eq 0 ]; then
  echo "✅ md5 31/31 一致"
else
  echo "❌ md5 mismatch、diff 内容を G-GEAR に報告"
fi
rm _checksums_phase_b.sorted.txt
cd -
```

### 5. sanity inspection (任意、1-2 cell)

```bash
PYTHONUTF8=1 uv run python -c "
import duckdb
for path in ['data/eval/golden/kant_stimulus_run0.duckdb', 'data/eval/golden/rikyu_stimulus_run4.duckdb']:
    con = duckdb.connect(path, read_only=True)
    print(f'{path}:')
    print('  schema cols:', [r[1] for r in con.execute(\"PRAGMA table_info(\\\"raw_dialog.dialog\\\")\").fetchall()])
    print('  row_count:', con.execute('SELECT COUNT(*) FROM raw_dialog.dialog').fetchone()[0])
    print('  individual_layer truthy_or_null:', con.execute(\"SELECT COUNT(*) FROM raw_dialog.dialog WHERE individual_layer_enabled IS NOT FALSE\").fetchone()[0])
    con.close()
"
# 期待:
#   schema cols: 16 列 (id, run_id, ..., individual_layer_enabled, created_at) を含む
#   row_count: ~852 (各 cell)
#   individual_layer truthy_or_null: 0 (B-1 contract: 全行 false)
```

### 6. 完了確認 → G-GEAR に報告

`md5 31/31 一致` を G-GEAR Claude session に伝える (新メッセージで「Mac sync OK、HTTP server 停止して」)。G-GEAR 側で server を停止する。

## fail 時の対応

- **G-GEAR HTTP NOT REACHABLE** → G-GEAR 側で `python -m http.server 8765 --bind 0.0.0.0` が起動しているか確認 (または auto mode classifier で blocked された可能性あり、G-GEAR session で明示許可が必要)
- **md5 mismatch** → diff 内容 (どのファイルが mismatch か) を G-GEAR に報告。CHECKPOINT 後の md5 と比較しているか確認
- **curl 401/403/404** → G-GEAR 側 server の cwd が `data/eval/golden/` になっているか確認 (file path は `/${filename}` で引ける必要あり)
- **fetched count ≠ 15** → 失敗ファイルだけ個別 retry (`curl -fOSs $BASE/$file`)

## 完了条件 (本セッション)

- [ ] Mac の `/Users/johnd/ERRE-Sand Box/data/eval/golden/` に 32 ファイル揃う
  (15 .duckdb + 15 sidecar + _audit_stimulus.json + _checksums_phase_b.txt)
- [ ] `md5 31/31 一致` を G-GEAR に報告、HTTP server 停止確認
- [ ] (任意) sanity inspect で 16 cols + B-1 contract を視認

## 関連参照

- `.steering/20260509-m9-individual-layer-schema-add/decisions.md` 判断 8
  (Phase B Windows native 転換の経緯)
- `.steering/20260509-m9-individual-layer-schema-add/next-session-prompt-phase-c.md`
  (Phase C kick の handoff、本 sync は Phase C kick の事前 sanity check として位置付け可能)
- `.steering/20260430-m9-eval-system/g-gear-phase-bc-launch-prompt.md §Phase D`
  (HTTP server 経由の rsync protocol、P3a-finalize 2026-05-05 validated pattern)
```

---

## G-GEAR 側で本 prompt を Mac へ渡す前にやること

- [ ] G-GEAR Claude session で HTTP server 起動許可を確認 (auto mode で blocked 既往あり)
- [ ] 起動後、Mac master 側で本 prompt を `/clear` 後に貼り付け
- [ ] Mac 側 sync 完了 → Mac から G-GEAR へ「sync OK」報告
- [ ] G-GEAR 側で HTTP server 停止

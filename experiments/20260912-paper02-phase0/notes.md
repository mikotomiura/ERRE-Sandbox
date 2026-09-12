# notes — 論文 02 Phase 0 (verdict-blind feasibility pilot)

## 検証する仮説 / 位置づけ

**この pilot は仮説検証ではない。** 上位 ADR
(`.steering/20260912-paper02-route/design-final.md` §3) が定める
**実行可能性の確認**であり、判定を 1 つも計算しない。

- 上位の研究仮説 (`docs/research-positioning.md` §5) に対する寄与は **ゼロ**。
  それは Phase 3 の実走が担う
- 借用 apparatus = `src/erre_sandbox/integration/embodied/bank.py` (`run_bank_mloop`) /
  `bank_fixtures.py` (`run_provenance_pass`)。**いずれも無改変で read-only に使用**

### なぜ判定を計算してはならないか

PCI RR の Level 制で、**結論 (または likely conclusions) を知ってしまうと Level 0 = 対象外**
となり Registered Report が恒久的に出せなくなる。一方 §2.7 が
「... or to demonstrate the **feasibility** of their proposed methods」を認め、
§2.6 末尾が「levels ... **do not apply to any completed preliminary studies or pilot data**」
と明文である。

**→ 判定を計算しない pilot は Level 6 を維持したまま実行できる。**

⚠ これは **2 条項の組み合わせによる defensible な読み**であって、
PCI RR の明文の保証ではない。「Level 6 preserved (保証)」とは書かない。

## 実測結果 (`results/metrics-*.json`)

### 1. モデルは 16,311 MiB に載るか → **載る (余裕あり)**

| | primary `llama3.1:8b` | reference `qwen3:8b` |
|---|---|---|
| GPU peak | **7,492 MiB (46%)** | 7,854 MiB (48%) |
| `ollama ps` PROCESSOR | **100% GPU** | 100% GPU |

CPU へのこぼれは無い。headroom は 8.8 GB ある。

### 2. `think` 指定の挙動 → **`think=False` は受理される**

`llama3.1:8b` は thinking モデルではないが、`think=False` を付けた要求は
**エラーにならず通る**。`think` を省略した要求も通る。

→ 上位 ADR §4.2 の「primary は think 相なし (native non-thinking)」という前提のまま、
`bank.py:284` が強制する `think=False` を**変更せずに**別モデルを通せる。
**凍結 apparatus を触る必要がない**ことが実測で確認できた。

### 3. per-draw latency → 9,600 draws の総実行時間

| アーム | per-draw | 4,800 draws |
|---|---|---|
| primary `llama3.1:8b` | 1.7533 s | 2.34 h |
| reference `qwen3:8b` | 2.0663 s | 2.76 h |
| **合計 (9,600 draws)** | | **≈ 5.09 h** |

上位 ADR §4.9 の概算「5–6 時間」と一致する。**この値で置き換える。**

**版ドリフトの影響は小さい**: C-proper の実測 (ollama 0.31.1) は 4,800 draws / 2h44m
= 2.0500 s/draw。本 pilot (0.32.12) は 2.0663 s/draw で **差は 0.8%**。

> ただしこれは **throughput の比較にすぎない**。
> 「版ドリフトが判定を動かさない」ことの証拠では**ない**。それは Phase 3 の
> control アーム (R5) が判定する。ここでその推測をしてはならない。

### 4. 5-way zone annotation は parse できるか → **成立**

`llama3.1:8b` の primary アームで:

- `plan_parse_band` = **`gte_0.8`** (JSON として妥当な plan が得られた割合)
- `zone_present_band` = **`gte_0.8`** (行き先が非 null で得られた割合)

**実数ではなくバンドで記録している。** 上位 ADR §4.5 の R4 分岐が
pooled `none_rate > 0.5` を条件に含むため、実数を見ると分岐を予見しうる
(Codex HIGH-4)。バンドの境界は **0.2 / 0.8** に置き、**0.5 と一致させていない**。

reference アーム (`qwen3:8b`) は **parse 系を一切収集していない** —
このモデルは Phase 3 の control そのものなので、parse 挙動を見ると
R5 の予備結果を覗くことになる (Codex HIGH-3)。

### 5. ディスク容量

- モデル: `llama3.1:8b` 4.92 GB (pull 済)
- Phase 3 の成果物見積り: C-proper の実測 18.4 MB / 4,800 draws → **2 アームで ≈ 37 MB**
- 空き: **555 GB**。十分

### 6. 版 / digest / 再実行手順

`env.md` に転記済。再実行は `run.sh` (ただし byte 一致 replay ではない。`env.md` 参照)。

## 上位 ADR §3.4 チェックリスト (Stage 1 投稿前の全通過条件)

| # | 項目 | 判定 | 根拠 |
|---|---|---|---|
| 1 | 2 個目モデルの digest を固定して記録した | ✅ | `46e0c10c039e…a666e` (`env.md` / `results/`) |
| 2 | ollama version を固定して記録した | ✅ | 0.32.12 |
| 3 | per-draw latency から総実行時間が現実的だと確認した | ✅ | **5.09 h** (§3) |
| 4 | parse が成立した | ✅ | 両バンドとも `gte_0.8` (§4) |
| 5 | ディスク容量が足りる | ✅ | 必要 ≈ 37 MB + 4.92 GB / 空き 555 GB |
| 6 | 再実行手順が書かれている | ✅ | `run.sh` (+ 限界を `env.md` に明記) |
| 7 | pilot が P-1〜P-4 を破っていないことを test で機械検査した | ✅ | test 38 件 + mutation **21/21 kill (survived 0)** |

**7 項目すべて通過。**

## 判断材料 (Phase 1 へ進むか、モデル選定をやり直すか)

**やり直す理由は 1 つも出なかった。**

- 載る (46% / CPU こぼれ無し) / `think=False` が通る / parse が成立する /
  5.09 h は 1 セッションで収まる / ディスクは足りる
- 上位 ADR §4.8 が「許容逸脱として扱わない」としたモデル差し替えは**不要**

→ **Phase 1 (Stage 1 protocol 執筆) へ進める状態にある。**
ただし進む判断そのものは user の裁定に属する。

## この pilot が**言っていない**こと (over-read guard)

- ✗ 「`llama3.1:8b` で null が再現する / しない」 — 判定を計算していない
- ✗ 「版ドリフトが判定に影響しない」 — 測ったのは throughput と VRAM だけ
- ✗ 「Level 6 が保証された」 — defensible な読みであって保証ではない
- ✗ 「Phase 3 の結果が予見できる」 — parse バンドは装置が作動するかの確認にすぎない
- ✗ 「この pilot は replay 可能」 — draw を保存していないので構造的に不可能

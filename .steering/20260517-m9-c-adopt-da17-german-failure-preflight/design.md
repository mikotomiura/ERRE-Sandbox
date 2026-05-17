# 設計 — DA-17 ADR (ドイツ語失敗 preflight)

## 実装アプローチ

**全て forensic 分析のみ、retrain ゼロ、`src/` 変更ゼロ**。本 ADR は
doc-only PR で完結し、続く PR-5 (scope は DA17-7 で確定) で初めて
code / weight 変更が入る。

分析は次の 7 段階で進める:

1. **DA17-1**: v3 v4 within-language d 全数値を 4 encoder × {de, en}
   = 8 cell で verbatim 引用、flip pattern を articulate
2. **DA17-2**: v4 LoRA-on / no-LoRA shard から langdetect 経由で
   ドイツ語 utterance 10 ペアを side-by-side で qualitative inspection
3. **DA17-3**: 既存 Burrows JSON (de-only) の per-window 内訳と
   lang_routing_counts を v3 v4 で対比
4. **DA17-4**: train_metadata + weight-audit + plan-b-corpus-gate JSON
   から de_en_mass / n_eff / top_5_pct + per-language weighted mass
   を読み、特に **ja=38.9% anomaly** を elevate
5. **DA17-5**: `personas/kant.yaml` + `tier_b_pilot.py` の prompt 構造
   を file:line 引用で verify、no-LoRA vs LoRA-on の system prompt
   identical を確認
6. **DA17-6**: 5 仮説 (H1 catastrophic forgetting / H2 trilingual
   interference / H3 distribution mismatch / H4 trilingual capacity
   competition / H5 style register mismatch) を evidence-for + -against
   で pre-register
7. **DA17-7**: PR-5 scope を α/β/γ/δ/ε から 1〜2 案に narrow down。
   `/reimagine` で別 ADR 結論を生成し、両案比較の上で採用案確定

## 変更対象

### 修正するファイル
- 該当なし (本 ADR は doc-only PR)

### 新規作成するファイル
- `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/requirement.md`
  — 本 ADR の背景・ゴール・受け入れ条件
- `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/design.md`
  — 本ファイル
- `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/decisions.md`
  — DA17-1〜DA17-7 を Phase 2-3 で埋める
- `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/tasklist.md`
  — Phase 1〜6 を checkbox 化
- `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/blockers.md`
  — 該当なしで起票 (空シェル)
- `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/next-session-prompt-FINAL-pr5-<scope>.md`
  — DA17-7 で採用された scope の次セッション起動 prompt
- `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/codex-review-prompt.md`
  + `codex-review.md` — Codex 経由の independent review

### 更新するファイル
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/next-session-prompt-FINAL-pr5-rank16-spike-reject.md`
  — 先頭に DEFERRED 注記追加 (delete せず保持、α 採用時に再評価可能化)
- `C:\Users\johnd\.claude\projects\C--ERRE-Sand-Box\memory\project_plan_b_kant_phase_e_a6.md`
  — PR-4 #189 merged + DA-17 結論 + 38.9% ja mass anomaly + 言語非対称
  empirical 教訓

### 削除するファイル
- 該当なし

## 影響範囲

- 本 PR doc-only のため `src/` テスト / build / inference path に
  影響なし
- 後続 PR-5 (DA17-7 採用 scope) で初めて code / weight が動く:
  - α 採用 → `scripts/m9-c-adopt/train_plan_b_kant.sh` の `--lora-rank
    16` + SGLang `--max-lora-rank 16` 確認 spike
  - β 採用 → `scripts/m9-c-adopt/build_*` の corpus mass 再計算
    (ja drop or 削減)
  - γ 採用 → Plan C 寄り、`src/erre_sandbox/inference/` の prompt
    routing 拡張 + multi-adapter load
  - δ 採用 → Plan B 全体 retrospective ADR (doc-only)
  - ε 採用 → `personas/kant.yaml` or `tier_b_pilot.py:224-247` の
    system prompt 追加指示
- nietzsche / rikyu Plan B 展開は引き続き blocked (DA16-1 binding)

## 既存パターンとの整合性

- **`.steering/[YYYYMMDD]-[task-name]/` 構造**: CLAUDE.md「作業記録
  ルール」準拠、5 標準 file 必須
- **DA-N 連番**: `.steering/20260517-m9-c-adopt-da16-design/decisions.md`
  の DA16-1〜DA16-4 を継ぐ形で DA17-1〜DA17-7 を使用
- **doc-only PR pattern**: DA-16 ADR (PR #186) と同 pattern (Codex
  review + WSL2 + 日本語 PR description)
- **Codex review WSL2 経路**: PR #186 / #187 / #188 / #189 で確立した
  `cd /mnt/c/ERRE-Sand_Box && codex exec --skip-git-repo-check -c
  model_reasoning_effort=xhigh` を使用、401 時は PR description で defer
- **DA-14 thresholds 不変** (DA16-4 binding): 「閾値緩和」案は本 ADR
  scope 外、提案あれば reject

## DA17-1 抽出 script (verbatim)

planning session で実行済、結果は本 plan ファイル Context table。
decisions.md DA17-1 にも CI bounds 込みで verbatim 記録:

```powershell
.venv\Scripts\python.exe -c @'
import json
from pathlib import Path

encs = ['mpnet','e5large','lex5','bgem3']
v3_dir = Path('.steering/20260516-m9-c-adopt-plan-b-eval-gen')
v4_dir = Path('.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict')

print(f'{"encoder":<10} {"lang":<4} {"v3 d":>9} {"v3 lo":>9} {"v3 hi":>9}  {"v4 d":>9} {"v4 lo":>9} {"v4 hi":>9}  {"delta d":>9}')
for e in encs:
    v3 = json.loads((v3_dir / f'da14-rescore-{e}-plan-b-kant.json').read_text(encoding='utf-8'))
    v4 = json.loads((v4_dir / f'da14-rescore-{e}-plan-b-kant-v4.json').read_text(encoding='utf-8'))
    for lang in ['de','en']:
        v3w = v3['within_language'][lang]
        v4w = v4['within_language'][lang]
        d3 = v3w.get('cohens_d'); d4 = v4w.get('cohens_d')
        if d3 is None or d4 is None: continue
        print(f'{e:<10} {lang:<4} {d3:>9.4f} {v3w["diff_lo"]:>9.4f} {v3w["diff_hi"]:>9.4f}  {d4:>9.4f} {v4w["diff_lo"]:>9.4f} {v4w["diff_hi"]:>9.4f}  {d4-d3:>+9.4f}')
'@
```

## DA17-2 utterance inspection script (read-only one-off)

`.venv\Scripts\python.exe` で実行する read-only script。本 ADR で
`_da17_2_inspect.py` として commit (再現性 / PR-5 再利用のため)、
出力 verbatim を decisions.md DA17-2 に貼る:

```python
import random
from pathlib import Path

import duckdb

# langdetect は project の compute_burrows_delta.py:67 と同じ dep
from langdetect import DetectorFactory, detect_langs

DetectorFactory.seed = 0  # compute_burrows_delta.py と同 seed

LORA_SHARD = Path('data/eval/m9-c-adopt-plan-b-verdict-v4/kant_r8v4_run0_stim.duckdb')
NOLORA_SHARD = Path('data/eval/m9-c-adopt-plan-b-verdict-v4/kant_planb_nolora_run0_stim.duckdb')

THRESH = 0.85  # compute_burrows_delta.py と同 threshold


def load_de_kant(shard: Path):
    con = duckdb.connect(str(shard), read_only=True)
    rows = con.execute(
        "SELECT dialog_id, tick, turn_index, utterance FROM raw_dialog.dialog "
        "WHERE speaker_persona_id='kant' ORDER BY dialog_id, tick, turn_index"
    ).fetchall()
    con.close()
    de_rows = []
    for dialog_id, tick, turn_index, utt in rows:
        if not utt or len(utt.strip()) < 5:
            continue
        try:
            langs = detect_langs(utt)
        except Exception:
            continue
        if not langs:
            continue
        top = langs[0]
        if top.lang == 'de' and top.prob >= THRESH:
            de_rows.append((dialog_id, tick, turn_index, utt))
    return de_rows


lora_de = load_de_kant(LORA_SHARD)
nolora_de = load_de_kant(NOLORA_SHARD)
print(f"LoRA-on de utterances: {len(lora_de)}")
print(f"no-LoRA de utterances: {len(nolora_de)}")

# 同 (dialog_id, tick) で join
nolora_idx = {(d, t): u for (d, t, ti, u) in nolora_de}
paired = [(d, t, lu, nolora_idx[(d, t)])
          for (d, t, ti, lu) in lora_de if (d, t) in nolora_idx]
print(f"Paired (same dialog_id+tick): {len(paired)}")

random.seed(42)
sample = random.sample(paired, min(10, len(paired)))
for i, (d, t, lu, nu) in enumerate(sample, 1):
    print(f"\n=== sample {i} | dialog_id={d} tick={t} ===")
    print(f"[no-LoRA]  {nu}")
    print(f"[LoRA-on]  {lu}")
```

実行結果は decisions.md DA17-2 に verbatim 貼り付け、各サンプルへの
qualitative comment (Akademie-Ausgabe 語彙か / 現代会話ドイツ語か /
英語混入の有無) を別段落で付ける。

## DA17-3 Burrows per-window read-only inspection

`tier-b-plan-b-kant-r8v4-burrows.json` と同 v3 の lang_routing_counts
+ per_window mean_burrows を `python -c` で抽出。recompute 不要:

```powershell
.venv\Scripts\python.exe -c @'
import json
from pathlib import Path

v3 = json.loads(Path('.steering/20260516-m9-c-adopt-plan-b-eval-gen/tier-b-plan-b-kant-r8v3-burrows.json').read_text(encoding='utf-8'))
v4 = json.loads(Path('.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/tier-b-plan-b-kant-r8v4-burrows.json').read_text(encoding='utf-8'))

for name, j in [('v3', v3), ('v4', v4)]:
    print(f'--- {name} ---')
    print(f'shards: {j["shards"]}')
    print(f'lang_routing_counts: {j["lang_routing_counts"]}')
    print(f'bootstrap point/lo/hi: {j["bootstrap"]["point"]:.4f} / {j["bootstrap"]["lo"]:.4f} / {j["bootstrap"]["hi"]:.4f}')
    print(f'per_window means: {[round(w["mean_burrows"], 2) for w in j["per_window"]]}')
'@
```

decisions.md DA17-3 に verbatim 結果。no-LoRA 側の Burrows
(`tier-b-plan-b-kant-planb-nolora-v4-burrows.json`) と対比して
reduction% の計算過程も明示。

## DA17-4 train_metadata audit (planning で収集済)

`data/lora/m9-c-adopt-v2/kant_r8_v4/{train_metadata,weight-audit,plan-b-corpus-gate}.json`
の数値は planning session で全て収集済。decisions.md DA17-4 に
table 形式で verbatim、特に:

- `per_language_weighted_mass`: de=0.3854 / en=0.2156 / **ja=0.3890** /
  mixed=0.0100
- `bucket_histogram` から raw counts: de=1392 (24.5%) / en=1165 (20.5%)
  / **ja=3065 (53.8%)** / mixed=71 (1.2%)
- 重み付けで de は +14pt 上げ、ja は −15pt 下げ、en はほぼ不変
- **ja は依然 de とほぼ同じ mass を消費 (38.9% vs 38.5%)** = H2/H4 の
  trilingual interference 仮説の証拠

## DA17-5 prompt structure verify (planning で確認済)

Explore agent で確認済の file:line 引用を decisions.md DA17-5 に転載:

- `personas/kant.yaml:111-114` `default_sampling: temperature=0.60,
  top_p=0.85, repeat_penalty=1.12`
- `personas/kant.yaml` 全体に **言語別指示なし** (de/en/ja 固有 prompt
  なし)
- `scripts/m9-c-adopt/tier_b_pilot.py:224-247` `_build_system_prompt()`
- `scripts/m9-c-adopt/tier_b_pilot.py:243-245` 文字数制約
  「80 Japanese characters or 160 Latin characters」
- `scripts/m9-c-adopt/tier_b_pilot.py:482, 577` no-LoRA vs LoRA-on で
  同一 `system_prompt` を渡す
- `apply_chat_template` 呼び出しなし、SGLang OpenAI-compatible で直接
  `[{"role":"system",…}, {"role":"user",…}]`

結論: **prompt-side fix (ε) は構造的に viable** (system prompt clean、
ドイツ語固有 text なし)。adapter 重みのみが条件間の唯一の変数。

## DA17-6 仮説 pre-register (詳細は decisions.md)

5 仮説 H1〜H5 を decisions.md DA17-6 で table 化。各仮説は本 plan
ファイルの仮説表と同内容、evidence-for + evidence-against を DA17-1〜
DA17-5 の数値 / 観察と file:line 引用で紐付ける。

## DA17-7 PR-5 scope decision + `/reimagine`

5 候補 (α rank=16 / β corpus rebalance / γ language-aware LoRA /
δ Plan B retrospective / ε prompt-side fix) を decisions.md DA17-7
table で envelope + 検証 H + 失敗 pivot 含めて比較。

**初回案 recommendation**: ε-first → β-second (低コスト spike → 中コスト
retrain の順)。

**`/reimagine` 適用**: CLAUDE.md「Plan 内 /reimagine 必須」要請に従い、
DA-17 結論を一度退避して独立 subagent (Plan or `/reimagine` Skill 経由)
で別案を再生成。両案を decisions.md DA17-7 に併記の上で採用案確定 +
不採用案は defer reason 明示。

## テスト戦略

- 単体テスト: 該当なし (doc-only PR)
- 統合テスト: 該当なし
- E2E テスト: 該当なし

検証は **受け入れ条件 (requirement.md)** の checkbox で代替:
- DA17-1 table が plan ファイル Context table と verbatim 一致
- DA17-2 ≥10 ペアの ドイツ語 inspection
- DA17-3 Burrows 内訳 v3 v4 対比
- DA17-4 train_metadata 数値 verbatim
- DA17-5 prompt 同一性の file:line 引用
- DA17-6 5 仮説 各 evidence-for ≥2 + evidence-against ≥2
- DA17-7 PR-5 scope 確定 + `/reimagine` 別案併記

## ロールバック計画

- 本 PR doc-only なので revert は単一 commit revert で完了
- `next-session-prompt-FINAL-pr5-rank16-spike-reject.md` の DEFERRED
  注記は revert すれば PR-4 時の状態に戻る (delete していない)
- memory 更新は revert 対象外 (git 管轄外)。誤更新時は手動修正
- 万一 DA-17 結論が誤っていた場合、続く PR-5 (採用 scope) で
  decisions.md DA17-7 を更新し別 ADR (DA-18) を切る

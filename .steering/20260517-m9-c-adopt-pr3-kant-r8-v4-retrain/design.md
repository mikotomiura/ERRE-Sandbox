# 設計 — PR-3 kant_r8_v4 forensic JSON commit (artifact-only)

## 実装アプローチ

**forensic JSON 4 file のみ git commit**、adapter binary + tokenizer +
checkpoint は `.gitignore` で機械除外 (`data/lora/**/adapter_model.safetensors`
/ `data/lora/**/checkpoint-*` / `data/lora/**/tokenizer.json` 等は既に
v3 PR (#181) 時に追加済、v4 でも同 pattern が自動適用される)。

retrain 自体は本 PR scope 外で既に完走済 (PR-2 push 直後の 2026-05-17 同
session 内、WSL2 GPU)。本 PR は artefact 取り込みのみで GPU 不要、
~1h envelope。

**HuggingFace Hub upload は本 PR scope 外** (DP3-1)。PR-4 verdict ADOPT
確定後の PR-5 で実施する (REJECT 時の無駄 upload 回避 + repo organisation
を ADOPT 版に集中)。PR-4 の verdict 計算は v4 adapter を **local path
経由で load** する (`data/lora/m9-c-adopt-v2/kant_r8_v4/`)、HF Hub
からの自動 download は使えない (本 PR で push しないため)。

## 変更対象

### 修正するファイル
- なし (`.gitignore` は v3 時に既に正しい pattern を持つため変更不要、
  Bash で `git check-ignore -v` で確認済)

### 新規作成するファイル
- `data/lora/m9-c-adopt-v2/kant_r8_v4/adapter_config.json` (LoRA config、
  ~1 KB)
- `data/lora/m9-c-adopt-v2/kant_r8_v4/plan-b-corpus-gate.json` (DA-14
  corpus gate pass 数値、~600 bytes)
- `data/lora/m9-c-adopt-v2/kant_r8_v4/train_metadata.json` (best
  eval_loss / best step / peak VRAM / shard_stats、~4 KB)
- `data/lora/m9-c-adopt-v2/kant_r8_v4/weight-audit.json` (weight 分布、
  ~1.3 KB)
- (forensic JSON 合計 ~7 KB、Codex verify 実測値)
- `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/` (本 5 file)
- `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/codex-review-prompt.md`
  + `codex-review.md` (Codex review artefact)
- `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/next-session-prompt-FINAL-pr4-da14-rerun-verdict.md`
  (PR-4 用 prompt + PR-5 conditional 併記)

### 削除するファイル
- なし

### git 外で保持するファイル (本 PR で commit しない)
- `data/lora/m9-c-adopt-v2/kant_r8_v4/adapter_model.safetensors` (30.7 MB、
  `.gitignore:74` で除外)
- `data/lora/m9-c-adopt-v2/kant_r8_v4/checkpoint-2000/` + `checkpoint-2500/`
  (binary 全 file、`.gitignore:76` で除外)
- `data/lora/m9-c-adopt-v2/kant_r8_v4/tokenizer.json` (11 MB、
  `.gitignore:77` で除外)
- `data/lora/m9-c-adopt-v2/kant_r8_v4/tokenizer_config.json` /
  `chat_template.jinja` / `README.md` (`.gitignore:78,80,81` で除外)

## 影響範囲

### 直接の影響
- main の `data/lora/m9-c-adopt-v2/kant_r8_v4/` に forensic 4 file が
  追加され、v3 と並列で reference できる
- PR-4 が `kant_r8_v4` adapter を **local path 経由で load** して
  DA-14 rerun verdict を計算する経路を確立 (HF Hub からの auto
  download は使えない、DP3-1)

### 間接の影響
- nietzsche / rikyu Plan B 展開は PR-4 verdict ADOPT まで保留 (DA-16
  ADR DA16-1 と整合)
- PR-5 scope は verdict 結果で分岐: ADOPT → HF push (DP3-1 後送り分
  実施)、REJECT → rank=16 spike retrain (HF push skip、別 adapter 生成)

### 互換性
- v3 forensic 4 file との JSON schema 互換 (v3 と v4 は同 `lora_rank=8`
  / `gradient_accumulation_steps=8` / `quantization=nf4` / `max_steps=2500`
  / `seed=42` で生成、reduce 式のみ `(l*w)/w` → `(l*w).mean()` で異なる)
- `train_metadata.json` の数値 field は v3 と完全同一の key set (新規
  field 追加なし)

## 既存パターンとの整合性

- **DV-3 (forensic JSON のみ commit)**: v2 baseline + v3 retrain と
  同じ pattern (`.steering/20260516-m9-c-adopt-plan-b-eval-gen/
  decisions.md` DV-3)。v4 で逸脱しない
- **v3 commit file 構成**: `git ls-files data/lora/m9-c-adopt-v2/kant_r8_v3/`
  で確認: `adapter_config.json` / `plan-b-corpus-gate.json` /
  `train_metadata.json` / `weight-audit.json` の 4 file。v4 も同 4 file
  で揃える (PR description で v3/v4 schema 整合性を主張するために
  必須)
- **HF Hub push timing** (DP3-1 で新規追加): v3 は当時 push 済が結果的に
  baseline 比較用に役立っているが、v4 は同 pattern を踏襲する必要なし。
  verdict 結果に依存する公開行為は確定後に行う方針を新採用

## テスト戦略

- 単体テスト: 該当なし (実装コード変更なし、artefact 取り込みのみ)
- 統合テスト: 該当なし
- E2E テスト: 該当なし
- **検証手段**:
  1. `git diff --cached --stat` で commit size 確認 (forensic JSON 単独
     ~7 KB、+ .steering 5 file + codex review file 込みで commit 全体
     ~28-30 KB 想定、binary 混入なら万 KB 超で即検出。Codex LOW-1
     反映で size 言い回し精緻化)
  2. `git check-ignore -v` で binary file が `.gitignore` で正しく
     除外されることを確認 (本セッション開始時に既に確認済)
  3. JSON schema 整合性: v3 と v4 の `train_metadata.json` を diff、
     新規 field 追加 / 既存 field 削除がないことを目視確認
  4. Codex independent review で forensic 一貫性 (HIGH/MEDIUM/LOW)
  5. pre-push CI parity 4 段 (ruff format --check / ruff check /
     mypy src / pytest -q、本 PR は src/ 変更ゼロのため全 pass 想定)

## ロールバック計画

- forensic JSON commit のみで実装変更なし、ロールバックは git revert
  単発で完結
- v4 adapter binary 自体は local + 個別 backup (G-GEAR の WSL2
  `/root/erre-sandbox/.venv` 経路で生成されたものを Windows path
  `data/lora/m9-c-adopt-v2/kant_r8_v4/` に rsync 済)
- 万が一 forensic JSON に誤りが見つかった場合、`train_kant_lora.py`
  invocation を WSL2 で再実行 (~3h GPU) して artefact 再生成可能 ‒
  ただし seed=42 + 同 corpus + 同 hyperparameter で deterministic
  再現を期待 (DI-7 と同 envelope)

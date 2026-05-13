# ブロッカー記録 — m9-c-spike

> Codex review (HIGH-3 / MEDIUM-6 反映) で明示化された hard / soft blocker と
> defer 事項。本タスク全体の実行依存を可視化する。

## Hard blockers (Phase β real training 着手不可)

### B-3: WSL2 training venv に `peft / bitsandbytes / accelerate` 未インストール (2026-05-13) ✅ 解消済 (2026-05-13)

- **解消メモ** (A 案採用): `/root/erre-sandbox/.venv` に `python -m ensurepip --upgrade` で pip 0.24.0 を bootstrap、
  続いて `pip install peft>=0.13 bitsandbytes>=0.43 accelerate>=0.30` を実施。
  実 install version: peft 0.19.1 / bitsandbytes 0.49.2 / accelerate 1.13.0。
  既存の sglang 0.5.10.post1 / torch 2.9.1+cu128 / transformers 5.3.0 / datasets 3.6.0 は無変更。
  hf_transfer 0.1.9 も追加 install (HF_HUB_ENABLE_HF_TRANSFER=1 で xet 並列 DL 高速化)。
  Phase K-β 本訓練を 2.07h で完遂、SGLang serve も同 venv で動作確認。
- **発生日時**: 2026-05-13 (Phase K-β 実装 PR セッション、Plan A 採用直後)
- **症状**: G-GEAR WSL2 Ubuntu-22.04 の `/root/erre-sandbox/.venv` には
  `sglang 0.5.10.post1` + `cu128 torch` + `transformers 5.3.0` が install 済だが、
  訓練に必要な `peft / bitsandbytes / accelerate` が未インストール。Windows
  side の uv venv は `torch==2.11.0+cpu` で GPU 訓練不可。本 PR の inner loop
  は実装済だが kick できない (`ImportError` で即 fail)
- **依存タスク**: 別 PR (feature/m9-c-spike-k-beta-real-train、次セッション scope)
- **解決方法 (planned)**:
  1. **A 案**: 既存 WSL2 venv に `peft / bitsandbytes / accelerate` 追加 install
     - 懸念: pyproject.toml の `[training]` extras pin は `transformers>=4.45,<5`
       で WSL2 の `transformers 5.3.0` (sglang 同居) と衝突
     - 解決: peft 0.19.x / bitsandbytes 0.49.x / accelerate 1.x が
       `transformers 5.x` を受け付ける確認 (Windows side は実際に組み合わせて
       通っている、CPU だが)
  2. **B 案**: 別 venv (`/root/erre-sandbox/.venv-training`) に [training] のみ
     install、訓練終了後に既存 SGLang venv に戻して serving
     - 利点: stack 衝突回避、production な分離
     - 欠点: GPU メモリ占有切り替え時に process restart 必要
  3. **C 案**: pyproject.toml `[training]` の `transformers` pin を `>=4.45,<6` に
     緩和 → A 案を pyproject 整合で実施
- **影響範囲**: Phase K-β 実訓練 (S-3..S-9)
- **教訓**: 「lazy import なら CI default install で gate のみ走らせられる」と
  「実訓練を kick できる venv が存在する」は **別問題**。実装 PR と訓練 PR は
  分けるのが正解 (Plan A、本 PR で empirical 確認)
- **trigger** (本 blocker fire / 解消判断):
  - 解消条件: WSL2 で `python -c "import peft, bitsandbytes, accelerate, torch;
    assert torch.cuda.is_available()"` が exit 0
  - fire 継続条件: 上記いずれかの import fail or torch.cuda.is_available()=False

### B-1: `m9-individual-layer-schema-add` 未完了 (CS-3 / Codex HIGH-3) ✅ 解消済 (2026-05-13)

- **解消メモ**: PR-A (`m9-individual-layer-schema-add`) merge により
  `ALLOWED_RAW_DIALOG_KEYS` + `_RAW_DIALOG_DDL_COLUMNS` に
  `individual_layer_enabled` 追加、`_DuckDBRawTrainingRelation.__init__` で
  construction-time aggregate assert (Codex HIGH-2) を実装。本 PR の dry-run
  実測 (kant 10 cells) で blocker fire しないことを確認 (5022 examples /
  rc=0)
- **発生日時**: 2026-05-08 (m9-c-spike Plan 起草時)
- **症状**: `ALLOWED_RAW_DIALOG_KEYS` (`src/erre_sandbox/contracts/eval_paths.py`)
  に `individual_layer_enabled` field が未追加。DB11 (PR #145) は training-view
  contract に `individual_layer_enabled=false AND evaluation_epoch=false` の
  enforcement を要求するが、現状 schema に該当 field が無いため
  `assert_phase_beta_ready()` (CS-3 gate) は `BlockerNotResolvedError` で
  hard-fail
- **依存タスク**: `m9-individual-layer-schema-add` (M9-eval-system P4a の
  blockers.md でも記録済、follow-up task として scaffold 必要)
- **解決方法 (planned)**:
  1. `eval_paths.py::ALLOWED_RAW_DIALOG_KEYS` に `individual_layer_enabled`
     追加 (BOOLEAN、default=false)
  2. `eval_store.py::_RAW_DIALOG_DDL_COLUMNS` に同 field 追加 + bootstrap DDL
     更新
  3. `connect_training_view()` 入口で `evaluation_epoch=false AND
     individual_layer_enabled=false` assert
  4. CI grep gate に sentinel 検証
- **影響範囲**: m9-c-spike Phase K β、M9-C-adopt、M10-A 全体
- **教訓**: DB11 ADR (PR #145) は contract / docstring を更新したが
  schema enforcement は別タスクに defer されていた。**ADR の "DB5 で構造的に
  保証" は actual schema が allow-list に必要 column を含む場合のみ成立**。
  ADR と schema 実装の lockstep を Codex P4a MEDIUM-3 で再指摘されている。

### B-2: M9-eval P3 golden baseline 採取完了 (CS-3 / Codex HIGH-3) ✅ 解消済 (2026-05-13)

- **解消メモ**: PR #160 merge (Phase B+C 30 cell golden baseline) で kant_*.duckdb
  10 cells (natural run0-4 + stimulus run0-4) が `data/eval/golden/` に揃った。
  本 PR の dry-run 実測で raw_dialog 11,761 rows / persona examples 5,022
  (CS-3 threshold 1000 に対し 5.02x margin) を確認、min_examples gate 余裕
  通過 (`.steering/20260508-m9-c-spike/k-beta-dry-run.log`)
- **発生日時**: 2026-05-08 (m9-c-spike Plan 起草時)
- **症状**: Kant 単独 pilot data ~40-50 turn は LoRA training に不足 (Codex
  HIGH-3、Anthropic persona vector / P-Tailor / BIG5-CHAT prior art に対し
  "~2500 turn" estimate ですら spike scope 専用、universal sufficient ではない)。
  CS-3 gate (`min_examples=1000`) を通過する量の training-eligible row を
  確保するには P3 golden baseline (3 persona × 5 run × 500 turn = 7500 turn)
  採取完了が前提
- **依存タスク**: M9-eval P3 (G-GEAR run1 calibration → run2-4 normal runs)
- **現状進捗**: G-GEAR run1 calibration overnight×2 走行中 (kant 1 cell × 5
  wall = 30h)、run1 完了見込み + run2-4 で full corpus
- **解決方法 (planned)**:
  - run1 calibration 完了 → ME-9 Amendment 2026-05-07 に従い run2-4 実走
    (3-parallel cooldown saturation 整理後の wall budget で)
  - 採取完了の DuckDB snapshot を ME-2 protocol で Mac に rsync
  - `assert_phase_beta_ready(min_examples=1000)` 通過確認
- **影響範囲**: m9-c-spike Phase K β real training は **本 blocker 解消まで
  起動不可**
- **教訓**: spike の data dependency を design phase で明示化することで
  scope-blocked 期間中に **Phase α (mock-LoRA infra proof)** 等の data-
  independent work で並行進捗を確保できる (本 spike では CS-9 mock を
  data-independent path として用意)

## Soft blockers (Phase α は実行可能、Phase β / 実走時に要確認)

### S-1: SGLang 0.5.10.post1 G-GEAR install (CS-1 / Codex HIGH-1)

- **発生日時**: 2026-05-08 (Plan 起草時)
- **症状**: SGLang 0.5.10.post1 の CUDA 12.x 公式 wheel が G-GEAR (RTX 5060
  Ti 16GB、CUDA driver version 確認要) で install 通るか未確認
- **依存タスク**: Phase G (`pyproject.toml` `[inference]` extra) + Phase K α
  (G-GEAR install + `--enable-lora` 起動確認)
- **解決方法 (planned)**:
  1. G-GEAR で `python -m pip install sglang==0.5.10.post1` (CUDA wheel)
  2. `python -m sglang.launch_server --enable-lora` 起動確認
  3. install 失敗時は CS-1 re-open + 別 version pin 検討 (e.g. v0.5.9 / v0.5.11)
- **影響範囲**: Phase K α 全体、install 失敗なら Phase K β も block
- **教訓**: pre-release wheel の CUDA version compatibility は **release
  date と GPU driver の match を Codex web search で事前確認** (本 spike
  では Codex MEDIUM-1 で 2026-04-08 release を確認済)

### S-2: VRAM 予算実測 (CS-4 / Codex MEDIUM-3)

- **発生日時**: 2026-05-08 (Plan 起草時)
- **症状**: G-GEAR RTX 5060 Ti 16GB で QLoRA NF4 + double quant +
  gradient_checkpointing + batch=1 + seq=2048 の peak memory が CS-4 estimate
  ~8.7GB に収まるか未実測
- **依存タスク**: Phase K β real training run (peak memory logging を training
  entry point に組込済)
- **解決方法 (planned)**:
  1. Phase K β で `nvidia-smi` peak memory logging
  2. 実測 ≤12GB なら CS-4 そのまま (headroom 4GB)
  3. 実測 >12GB なら CS-4 amendment (batch / seq / accumulation 再調整、
     最悪 7B base に switch)
- **影響範囲**: Phase K β training run (OOM で abort のリスク)
- **教訓**: VRAM estimate は Codex MEDIUM-3 が指摘した通り optimistic に
  なりがち。**実測前に固定 config を decide せず、`gradient_accumulation_steps`
  等で recovery path を残す**

### S-3: PEFT format SGLang 受付 (CS-6 / Codex MEDIUM-2)

- **発生日時**: 2026-05-08 (Plan 起草時)
- **症状**: `peft.save_pretrained()` が emit する `adapter_config.json` +
  `adapter_model.safetensors` を SGLang `/load_lora_adapter` が直接受付するか
  未確認 (Qwen3-8B specific target_modules q_proj / k_proj / v_proj / o_proj)
- **依存タスク**: Phase K α 内 PEFT direct load test
- **解決方法 (planned)**:
  1. mock-LoRA を PEFT default で生成 (Phase J)
  2. SGLang `/load_lora_adapter` に直接 POST、HTTP 2xx 確認
  3. 失敗時は CS-6 re-open + conversion script 別タスク化 (本 spike では
     Phase J / K に conversion 実装含めない、Codex MEDIUM-2 整合)
- **影響範囲**: Phase K α / K β load 失敗で全体 block
- **教訓**: format conversion は failure mode が判明するまで投資価値低い
  (premature optimization 禁止、Codex MEDIUM-2 / CS-6 整合)

## Defer (本 spike では取り扱わない、別タスク化)

### D-1: vLLM full migration 実装

- **defer 理由**: M9-B DB3 で SGLang-first 確定、vLLM は fallback 経路。本
  spike で SGLang 経路が機能不全と判明したら別タスク `m9-c-spike-vllm-fallback`
  として fire (CS-8 trigger 整合)
- **vLLM v0.15+ multi-LoRA** が runtime load/unload (`VLLM_ALLOW_RUNTIME_LORA_
  UPDATING=True`、security risk warn) を support、Codex MEDIUM-5 で current
  state を確認済 (旧 v0.6+ baseline は破棄)
- **trigger**: CS-8 即時 fire (API failure / FSM regression) または Phase K β
  real adapter confirmation で >500ms latency / N=3 collapse fire

### D-2: PEFT vs unsloth final 選定

- **defer 理由**: M9-B DB2 で M9-C-spike は PEFT 暫定、final 選定は
  M9-C-adopt rank=8 統一 spike + rank sweep で
- **trigger**: 本 spike 完了後の M9-C-adopt 着手時

### D-3: 3 persona 展開 (Nietzsche / Rikyū)

- **defer 理由**: M9-B 第3の道 ADR で "bounded, non-authoritative single-
  persona Kant LoRA spike"、3 persona は M9-C-adopt 範囲
- **trigger**: 本 spike 完了 + DB9 quorum 通過 + M9-C-adopt 着手時

### D-4: PEFT format conversion script

- **defer 理由**: CS-6 / Codex MEDIUM-2 で「直接 load 試験先行、失敗時のみ
  自前 conversion」と確定
- **trigger**: Phase K α で PEFT direct load 失敗 (CS-6 re-open 条件)

### D-5: SGLang `--enable-lora` 連携部分の `inference/server.py` 統合

- **defer 理由**: 本 spike は `SGLangChatClient` を新設するが、live inference
  path (`inference/server.py`) との統合は M9-C-adopt 範囲 (採用判定通過後の
  production wiring)
- **trigger**: M9-C-adopt 着手時、本 spike の adapter swap runbook (DB8) を
  base に統合実装

### D-6: ME-9 trigger interpretation Amendment への影響

- **defer 理由**: m9-c-spike は M9-eval P3 golden baseline 採取に **依存**
  するが採取自体は ME-9 / G-GEAR run1 calibration 範囲。run2-4 wall budget
  確定後に本 spike Phase β trigger fire
- **trigger**: G-GEAR run1 calibration 完了 + run2-4 採取完了

## 設計上の不確実性 (記録のみ、defer ではない)

### U-1: rank=8 が persona-conditional adaptation に sufficient か (CS-5 hypothesis)

- Codex MEDIUM-4 で「rank=8 は continuity hypothesis、universal adequacy
  主張せず」と確定済
- 反復: Phase K β 実測で Tier B Vendi / Big5 ICC が persona-discriminative
  かを M9-eval-system 側で観測、不足なら CS-5 re-open

### U-2: adapter swap latency 500ms threshold の妥当性 (CS-8 operational SLO)

- Codex Prior art 7 で「literature constant ではない、ERRE operational SLO」
  と確認済
- 反復: Phase K β 5 condition 実測 (cold/warm/pinned/unpinned/no-LoRA) で
  threshold が production workload と整合か確認、不適切なら CS-8 amendment

### U-3: Mock-LoRA で M5 resonance / ERRE FSM smoke が confuse しないか
       (CS-9 PEFT default no-op)

- Codex LOW-2 で「PEFT default `init_lora_weights="default"` で B=0 identity
  transform、FSM smoke を confuse しない」と確認済
- 反復: Phase K α 内で SGLang load → mock 経由 chat round trip → base model
  と output 一致確認 (CS-9 acceptance criterion)

### U-4: Codex web search による SGLang version pin の future-proofness

- 本 spike commit 時点 (2026-05-08) で `sglang==0.5.10.post1` が PyPI latest、
  v0.6 stable 未発見
- 反復: 実装着手時 (次セッション) に再 web search、新 release があれば
  Phase G で再判定 (S-1 と相互依存)

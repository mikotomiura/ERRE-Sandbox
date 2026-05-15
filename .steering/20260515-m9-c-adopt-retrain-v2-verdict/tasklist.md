# タスクリスト — retrain v2 training execution + verdict

## 準備
- [x] `.steering/20260514-m9-c-adopt-retrain-v2-impl/decisions.md` を Read
- [x] DA-14 thresholds-recalibrated.json の存在確認
- [x] no-LoRA SGLang baseline artefacts を `.steering/20260514-m9-c-adopt-pilot-multiturn/` で確認
- [x] new branch `feature/m9-c-adopt-retrain-v2-train-execution` を main から派生
- [x] `.steering/20260515-m9-c-adopt-retrain-v2-verdict/` 5 file template 配置

## Phase 1: real-tokenizer audit ✅
- [x] `train_kant_lora --dry-run -v` (real tokenizer) 実行 (15:08 JST)
- [x] `weight-audit.json` を inspect、N_eff=3886.4 / top 5%=0.139 / de+en=0.489
- [x] DI-5 (real-tokenizer audit 結果) を decisions.md に追記
- [x] fallback trigger 判定: PASS (N_eff >> 1000、top 5% << 0.50)

## Phase 2: training execution ✅
- [x] Windows-native venv で初回起動 → bf16 GPU 不可で 5min で死亡 (blockers.md B-1)
- [x] WSL2 CUDA venv に切替えて再起動 (PID 631、PYTHONPATH=/mnt/c/.../src 経由)
- [x] 全 4000 steps 完走 (16h19m 経過、SIGINT 効かず natural completion)
- [x] train_metadata.json: train_loss=1.316、eval_loss=0.180、peak_vram=10.62GB
- [x] 最終 adapter @ root (byte-identical to checkpoint-4000)

## Phase 3: multi-turn pilot recapture ✅
- [x] SGLang を WSL で起動 (PID 362、max-lora-rank 8)
- [x] kant_r8_v2 adapter を POST /load_lora_adapter で登録
- [x] tier_b_pilot.py run 0 → 6.1 min、run 1 → 6.0 min
- [x] validate_multiturn_shards.py PASS 2/2 shards all checks

## Phase 4: consumer + matrix + verdict ✅
- [x] Big5 ICC (SGLang LoRA-on、T=0.7、6 windows) 実行
- [x] Vendi semantic consumer 実行
- [x] Burrows consumer 実行
- [x] da1_matrix_multiturn.py で 4 軸数値計算 (matched HISTORICAL 比較)
- [x] **DA-14 verdict 手動再計算** (no-LoRA SGLang 比較、`da14-verdict-v2-kant.json`)
- [x] **REJECT** (primary 1/3) を decisions.md D-1 に verbatim 記録

## 完了処理
- [x] DA-15 ADR 起票用 handoff prompt 生成
      (`next-session-prompt-FINAL-da15-adr.md`)
- [ ] git commit (artefacts + steering)
- [ ] git push -u origin feature/m9-c-adopt-retrain-v2-train-execution
- [ ] gh pr create

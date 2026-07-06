# env — ECL v0 sealed live run (Issue 003, first-contact)

## 実行環境 (G-GEAR)
- machine: G-GEAR (Windows 11、本作業ディレクトリ = 実行機)
- OS: Windows 11 (bake side = UCRT libm)
- Ollama: 0.31.1 (http://127.0.0.1:11434)
- model: qwen3:8b (digest 500a1f067a9f7826、5.2 GB)、**think=False** (ThinkOffChatClient wrapper、Codex HIGH-1)
- embedding: constant-vector mock (D-4、minimal reality surface = live は action LLM chat のみ、real
  nomic-embed-text 不使用)
- VRAM: 16 GB
- uv.lock sha256 (先頭): 9cc70f9dc5d61f6c
- 日時: 2026-07-06 20:51-20:53 JST

## 事前登録 protocol (sealed run 前固定、tune-to-pass 封鎖)
- N_cognition=32 (D-1) / persona=kant, 単一 agent (D-2) / seed=0 / physics 20/cognition = 640 physics row
- sampling = live cycle resolved を verbatim 記録 (D-3、think のみ False)
- 観測量 O1-O5、Done=O1∧O2∧O3a∧O3b (manifest observables overlay に pre-registered)

## 結果 (verdict = GO、construction validated)
| 観測量 | 結果 |
|---|---|
| **O1 完走** | ✅ 32 cognition × 20 physics = 640 row、例外なく完走 (exit 0) |
| **O2 replay 再現** | ✅ committed decisions のみ replay → checksum byte 一致 + inner_invocations==0 |
| **O3a cross-platform** | ✅ **WSL Linux (glibc) replay = Windows (UCRT) checksum** `a528d547…` byte 一致 (libm cos/sin drift を 6桁量子化が吸収) |
| **O3b cross-platform** | ✅ 同一 raw Plane2 → artifact re-render SHA が Linux/Windows 一致 |
| **Done=O1∧O2∧O3a∧O3b** | ✅ **HOLDS** |
| O5 parsed-history-dependent-action (annotation、非 gate) | **32/32 tick** で `llm_status==ok` ∧ `plan≠None` ∧ MoveMsg `resolved_from==memory_centroid` (first-contact 存在証明が ≥1 を大きく超過。think=False が load-bearing = 全 tick parseable) |
| O4 非縮退 (annotation、非 gate) | distinct destination_zone = 2 ({peripatos:28, study:4})、distinct move target = 32 (全 tick 相異) |

replay_checksum (authoritative) = `a528d5472c3fc1b939ab151e0bdb8089a23a8b5ae39b7b7961aeed91d94cc249`

## cross-platform 実測手順 (feedback_golden_crossplatform_float_drift)
1. Windows で `bash experiments/20260706-ecl-v0-live-capture/run.sh` → artifacts/ を bake (UCRT)。
2. WSL Linux venv (`uv pip install .`、glibc) で
   `python scripts/ecl_v0_live_capture.py --verify --artifact-dir experiments/20260706-ecl-v0-live-capture/artifacts`
   → replay checksum が Windows-baked と byte 一致 = **cross-platform hold 実測確認済**。
3. CI (GitHub Actions Linux) は Issue 004 の `test_ecl_live_golden.py` が committed live artifact を replay-verify
   (Ollama-free) するため、Linux CI 自体も cross-platform gate。

## 判定 (軸5 = GO)
Done (O1∧O2∧O3a∧O3b) HOLDS + O5=32/32 + O4 非縮退 → **GO (construction validated)**。ECL v0 organ が real
qwen3:8b で substrate を end-to-end 駆動し、captured Plane2 のみで cross-platform に deterministic replay。
**construction validation であって measurement verdict でない** (floor/landscape/verdict 非出力、holding 不可侵)。
次 primary = 候補 B (N体化) or C (measurement gate) を別 ADR で (arc-close 却下・holding 継続)。

# 環境 / status — 論文 02 Phase 0 (verdict-blind feasibility pilot)

- **実験**: 論文 02 の 2 個目モデル (`llama3.1:8b`) が実走可能かを、
  **判定を一切計算せずに**実測する。上位 ADR = `.steering/20260912-paper02-route/design-final.md` §3。
- **apparatus**: `scripts/paper02_phase0_pilot.py` (新規 sibling driver)。
  再利用 (read-only) = `bank.py` (`run_bank_mloop`) / `bank_fixtures.py` (`run_provenance_pass`) /
  `ollama_adapter.py` / `cognition/parse.py`。**`src/erre_sandbox/**` は 1 行も変更していない。**
- **実装設計**: `.steering/20260912-paper02-phase0/design-final.md`。

## status (実走済 — 2026-09-12)

両アームとも完走した。取得した値は `results/metrics-*.json`。

| 項目 | primary | reference |
|---|---|---|
| モデル | `llama3.1:8b` | `qwen3:8b` |
| digest (full) | `46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e` | `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` |
| モデルサイズ | 4,920,753,328 B (4.92 GB) | 5,225,388,164 B (5.23 GB) |
| draw 数 | 96 (K=8 × M=6 × 2) | 96 |
| GPU baseline | 1,623 MiB | 1,623 MiB |
| GPU peak | **7,492 MiB** / 16,311 | **7,854 MiB** / 16,311 |
| モデル実効占有 | ≈ 5,869 MiB | ≈ 6,231 MiB |
| `ollama ps` | 6.0 GB / **100% GPU** | 6.4 GB / **100% GPU** |
| `think=False` | **受理** | 受理 |
| `think` 省略 | 受理 | 受理 |
| latency mean / p95 | 1,753 / 2,051 ms | 2,066 / 2,214 ms |
| per-draw | **1.7533 s** | **2.0663 s** |

- **ollama**: 0.32.12 (C-proper の pin は 0.31.1 — 版ドリフトあり)
- **GPU**: NVIDIA GeForce RTX 5060 Ti / 16,311 MiB total
- **platform**: Windows-10-10.0.26200-SP0 (= Windows 11、build 26200。
  `platform.release()` は Windows 11 でも "10" を返すので `platform.platform()` を記録している)
- **python**: 3.11.15 / pydantic 2.13.2 / httpx 0.28.1
- **uv.lock sha256**: `9cc70f9dc5d61f6c74c08dee4dd73815993861022a80781a75ef5d873860c0f7`
  (C-proper の pin と**同一**)
- **`ERRE_ZONE_BIAS_P`**: 0.2 (未設定時の既定値。M-loop 内では `bank.py` が 0 に pin する)

## 再現性の限界 (**重要。誇張しないための明記**)

**この pilot は封印 bundle ではない。**

- draw を **1 つも保存しない**。保存すると後から判定を計算できてしまい、
  Level 0 のトリガ (結論を知ってしまうこと) を装填したまま置くことになる
- したがって **byte 一致の replay-verify は構造的に不可能**である。
  C-proper (`experiments/20260710-m13-c-proper/`) の「WSL ⇔ Windows byte 一致」は
  **記録済み出力の再生 (replay-verify)** の性質であって、本 pilot には存在しない
- `run.sh` が与える再現は「**同じ凍結 context・同じ K/M で新しい draw を引き直す**」。
  latency / VRAM / parse バンドは再現するが、個々の draw は一致しない

> この区別を曖昧にしないこと。「再現できる」とだけ書くと
> `feedback_checker_handed_target_is_not_checked` と同型の誤りになる。

## 実走の経緯 (3 回引き直している。理由を残す)

VRAM の測り方に 2 つの欠陥が見つかり、**計器を直して測り直した**。
判定を計算していないので、引き直しに tune-to-pass のリスクはない
(選び直す対象となる結論が存在しない)。

1. **1 回目**: baseline を think probe の**後**に測っていたため、
   モデル load 後の値 (8,291 MiB) が baseline として入った → baseline を probe の前へ移動
2. **2 回目**: 対象モデルだけ unload していたため、直前のアームのモデルが常駐したまま
   peak に混ざった (reference の peak が 13,617 MiB) → 常駐モデルを全部 unload するよう変更
3. **3 回目 (採用)**: `ollama stop` が非同期で、直後に測るとまだ解放されていない
   (直後 7,486 MiB / 数秒後 1,623 MiB) → 解放が落ち着くまで待つ処理を追加。**本 env.md の値**

## 禁止 P-1〜P-4 の強制 (装置であって方針ではない)

`scripts/paper02_phase0_pilot.py` の G1-G6 と
`tests/test_integration/test_paper02_phase0_pilot.py` (38 件) が機械検査する。
非恒真性は `scripts/paper02_phase0_mutation_check.py` が
**21 改変すべてを kill (survived 0)** で実証している (`uv run python scripts/paper02_phase0_mutation_check.py`)。

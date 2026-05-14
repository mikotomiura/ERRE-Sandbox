# Next-session handoff prompt — DA-12 identifiability resolution via multi-turn pilot (m9-c-adopt 後続第 1 セッション)

**作成**: 2026-05-14 (Phase B PR #165 merge 後)
**前提**: PR #165 merge 済、DA-12 verdict = DEFER 確定、`feature/m9-c-adopt-phase-b-rank-sweep` branch は close 候補。
**用途**: 新セッション最初の prompt として貼り付け。本セッションは
**multi-turn pilot 採取 + DA-1 4 軸 intersection 再評価 + DA-13 ADR
(DA-12 identifiability 解消) + 後続経路判定 (retrain v2 / Phase E A-6
direct / REJECT) + PR 起票** を実施。
**branch**: 新規 `feature/m9-c-adopt-pilot-multiturn-investigation` を main から切る。

---

```
M9-C-adopt の **Phase B closure 後の investigation セッション** を実行する。
PR #165 (2026-05-14 merge) で Phase B 完遂 + DA-12 verdict = DEFER 確定。
DA-12 ADR が明示した「direction failure の 2 因子 identifiability 不能」を
empirical に切り分けるため、**pilot を multi-turn 採取に変更して DA-1
4 軸 intersection を再評価** する小 PR を実施する。

## 目的 (本セッション内で完遂)

1. DA-12 で identifiability 不能と認定された 2 因子のうちどちらが dominant
   かを multi-turn pilot data で empirical に判定:
   - **因子 A**: pilot single-turn vs baseline multi-turn の methodology
     confound (baseline は M9-eval P3 multi-turn dialog で focal kant が
     alternating turn、pilot は単発 stim → 1 turn focal)
   - **因子 B**: LoRA が IPIP self-report neutral midpoint を実質 shift
     しない (Codex MEDIUM-4 で予告済の ICC consumer 限界)
2. 結果に基づいて DA-12 ADR を close + DA-13 ADR (resolution) 起票
3. 後続経路を決定:
   - **A 優位 (methodology confound dominant)**: DA-12 close、Phase E A-6
     direct path、retrain v2 skip 可能
   - **B 優位 (LoRA failure dominant)**: feature/m9-c-adopt-retrain-v2
     を別 PR で起票する正当性 confirmed、Phase D 着手前 prereq として保持
   - **A + B 両者**: retrain v2 + multi-turn 採取 protocol fix の組み合わせ
     が必要、両者を Phase E A-6 内に integrate

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260513-m9-c-adopt/decisions.md` DA-1 (4 軸 intersection
   採用基準) + DA-9 (marginal pass retrain path) + DA-11 (Phase B 第 3
   セッション scope narrowing) + **DA-12 (Phase B 第 4 セッション DA-1
   verdict = DEFER、direction failure hot decision)**
2. `.steering/20260513-m9-c-adopt/phase-b-report.md` (Phase B 完遂報告 +
   実測 matrix + Cohen's d / Burrows reduction の direction 解析)
3. `.steering/20260513-m9-c-adopt/da1-matrix-kant.json` (PR #165 で
   merge 済、本セッションで multi-turn 値と比較する baseline)
4. `.steering/20260513-m9-c-adopt/blockers.md` U-6 (pilot single-turn vs
   baseline multi-turn methodology confound) + H-1 partial verify status
5. `scripts/m9-c-adopt/tier_b_pilot.py` (本セッションで multi-turn 拡張する
   driver)
6. `scripts/m9-c-adopt/compute_big5_icc.py` / `compute_burrows_delta.py` /
   `compute_baseline_vendi.py` / `da1_matrix.py` (再利用、変更なし)

## scope

### 1. pilot driver multi-turn 拡張 (~1h)

`scripts/m9-c-adopt/tier_b_pilot.py` 内 `_focal_turn_count()` を
hardcoded `return 1` から **stimulus YAML の `expected_focal_turn_count`
field 参照 or CLI flag 経由** に変更:

```python
def _focal_turn_count(stimulus: dict[str, Any], multi_turn_max: int) -> int:
    """Return focal turn count per stimulus.

    Single-turn mode (Phase B 第 3 セッション pilot、DA-11):
        always 1.
    Multi-turn mode (本セッション investigation):
        min(stimulus.get('expected_focal_turn_count', 1), multi_turn_max).
    """
    fc = int(stimulus.get("expected_focal_turn_count", 1))
    return max(1, min(fc, multi_turn_max))
```

CLI: `--multi-turn-max N` (default 1 で過去互換、本セッション investigation
で 6-10 を試行)

multi-turn 採取時の interlocutor 設計:
- 単発 stim ではなく、focal kant が **alternating turn 発話** (M9-eval
  baseline と同 protocol)
- interlocutor utterance は no-op stim repeat or M9-eval golden の
  `_build_interlocutor_prompt()` 流用
- 各 turn で SGLang LoRA adapter routing は同じ (kant_r{rank}_real)

DuckDB sink は既存 schema 維持 (`raw_dialog.dialog`)、`turn_index` が
1..N まで連番、`speaker_persona_id` alternation で multi-turn 認識可能。

### 2. multi-turn pilot 採取 (~1-2h G-GEAR compute)

- 3 rank × 2 run × **300 focal turn (same total as single-turn)** =
  1800 focal turn total
- 採取モード: multi-turn (`--multi-turn-max 6` で stim × 6 alternating
  turns = 50 stim/run、各 stim は 6 turn のうち focal kant turn 3 本)
- 出力: `data/eval/m9-c-adopt-tier-b-pilot-multiturn/kant_r{4,8,16}_run{0,1}_stim.duckdb`
  (6 shard、新 directory、single-turn pilot との共存)
- SGLang launch 既存 `launch_sglang_icc.sh` 再利用、3 adapter load 後採取
- 採取 ~1-2h (single-turn ~21 min の 3-6× 程度を見込み)

### 3. DA-1 4 軸 intersection 再評価 (~30 min compute)

multi-turn pilot 6 shard に対して既存 consumer を**そのまま走らせる**:

```bash
# Vendi semantic
for r in 4 8 16; do
  .venv/Scripts/python.exe scripts/m9-c-adopt/compute_baseline_vendi.py \
    --persona kant \
    --shards-glob "data/eval/m9-c-adopt-tier-b-pilot-multiturn/kant_r${r}_run*_stim.duckdb" \
    --kernel semantic --window-size 100 \
    --output ".steering/.../tier-b-pilot-multiturn-kant-r${r}-vendi-semantic.json"
done

# Big5 ICC (SGLang LoRA-on、Ollama baseline は再利用)
for r in 4 8 16; do
  .venv/Scripts/python.exe scripts/m9-c-adopt/compute_big5_icc.py \
    --persona kant \
    --shards-glob "data/eval/m9-c-adopt-tier-b-pilot-multiturn/kant_r${r}_run*_stim.duckdb" \
    --responder sglang --sglang-host http://127.0.0.1:30000 \
    --sglang-adapter "kant_r${r}_real" --temperature 0.7 \
    --window-size 100 \
    --output ".steering/.../tier-b-icc-multiturn-kant-r${r}.json"
done

# Burrows
for r in 4 8 16; do
  .venv/Scripts/python.exe scripts/m9-c-adopt/compute_burrows_delta.py \
    --persona kant \
    --shards-glob "data/eval/m9-c-adopt-tier-b-pilot-multiturn/kant_r${r}_run*_stim.duckdb" \
    --window-size 100 \
    --output ".steering/.../tier-b-pilot-multiturn-kant-r${r}-burrows.json"
done

# 4 軸 matrix 再集約 (da1_matrix.py に --suffix multiturn flag 追加 or
# 新規 da1_matrix_multiturn.py)
```

baseline は **PR #165 と同じ multi-turn baseline** (`data/eval/golden/
kant_stimulus_run*.duckdb`) を再利用、変更なし。**比較の方向**:

| 比較対象 | direction の意味 |
|---|---|
| **single-turn pilot (PR #165) vs multi-turn pilot (本 PR)** | 同 LoRA-on で protocol を変えると Vendi/Burrows の値がどう動くか → methodology confound 規模 |
| **multi-turn pilot vs baseline** | 同 protocol で LoRA on/off で値がどう動くか → LoRA effect の真の direction |

### 4. judgment matrix + DA-13 ADR

`scripts/m9-c-adopt/da1_matrix.py` に `--include-multiturn` flag 追加 or
新規 `da1_matrix_v2.py`:

```
| rank | Vendi multiturn | ICC multiturn | Burrows multiturn | axes PASS |
|---|---|---|---|---|
| baseline (multi-turn、既存) | ... | ... | ... | -- |
| single-turn pilot (PR #165) | 33-35 (FAIL direction) | 0.97-0.98 (PASS) | 112-114 (FAIL direction) | 2/4 |
| 4 multi-turn (本 PR) | (新測) | (新測) | (新測) | ?/4 |
| 8 multi-turn | (新測) | (新測) | (新測) | ?/4 |
| 16 multi-turn | (新測) | (新測) | (新測) | ?/4 |
```

**判定** (DA-13 ADR で記録):

| シナリオ | multi-turn pilot vs baseline | 結論 | 後続経路 |
|---|---|---|---|
| **シナリオ I (A 優位)** | direction が逆転 (LoRA-on Vendi < baseline) | methodology confound dominant、Phase B pilot は方法論欠陥のみ、LoRA は機能している | DA-12 close、**Phase E A-6 direct path**、retrain v2 skip |
| **シナリオ II (B 優位)** | direction 変わらず (LoRA-on Vendi > baseline) | LoRA は実質 persona-discriminative でない、retrain 必要 | DA-12 close、**feature/m9-c-adopt-retrain-v2** 経路 confirmed |
| **シナリオ III (A + B 両者)** | direction 改善するが thresholds 未達 | 両因子寄与、両者修正必要 | DA-12 partial close、Phase E A-6 内で multi-turn protocol + retrain v2 を combine |
| **シナリオ IV (新情報なし)** | multi-turn pilot 採取 fail or CI 広すぎる | identifiability 不能のまま | DA-12 維持、Phase E A-6 で 7500-turn full 採取が唯一の closure path |

シナリオ別の合意:
- **シナリオ I**: rank=8 を **provisional → adopted** に格上げの強い根拠、
  Phase D 着手前 prereq から retrain v2 を外す
- **シナリオ II**: retrain v2 PR の trigger を確定、Phase D 着手前 prereq
  順序は (retrain v2 → A-6) のまま
- **シナリオ III**: A-6 設計を multi-turn + retrain v2 を組み合わせた形に
  amend (DA-9 retrain spec amendment)

### 5. PR 起票 + handoff

- `decisions.md` に **DA-13 (Phase B Phase 後 multi-turn investigation
  ADR)** 起票:
  - 5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件)
  - DA-12 との関係 (close / partial-close / 維持)
  - 採用したシナリオ + 後続経路
- `blockers.md` U-6 status update (closure / 維持 / partial closure)
- `tasklist.md` Phase D 着手前 dependency 順序 update
- 新 directory `.steering/20260513-m9-c-adopt-pilot-multiturn-investigation/`
  または `20260513-m9-c-adopt/` 直下に artefact (どちらでも可、separate
  task として `.steering/2026MMDD-m9-c-adopt-pilot-multiturn/` 推奨)
- commit + push + `gh pr create` (PR description に matrix + シナリオ
  判定 + DA-13)

## NOT in scope (本セッション)

- 3 persona expansion (nietzsche / rikyu) — Phase C / E、別 PR
- `MultiBackendChatClient` 実装 — Phase D、retrain v2 + investigation 後
- production loader `_validate_adapter_manifest()` — Phase F
- FSM smoke 24 cell — Phase E
- nietzsche / rikyu baseline ICC / Burrows / Vendi 算出 — Phase E
- Phase E A-6 7500 turn full Tier B 採取 — 別 PR
- training v2 (min_examples 3000) — 本セッションで「必要かどうか」を判定
  するのが目的、実行は別 PR

## 注意 (incident 教訓 + 既知の落とし穴)

- **WSL2 → Windows-native Ollama 不通**: ICC consumer の Ollama 経路は
  Windows-side `.venv/Scripts/python.exe` から実行 (PR #165 で確認)。
  本セッションでは Ollama baseline ICC は再利用 (PR #165 artefact)、
  multi-turn pilot は SGLang のみ使用
- **SGLang VRAM ~10.5-11 GB peak with 3 adapter pin**: pilot 採取と
  ICC consumer を同時実行する場合は VRAM tight、queue 直列化に注意
- **T=0.7 + per-call seed mutation** is required for ICC (PR #165 hot
  decision、`compute_big5_icc.py` 内で `args.temperature` で実装)。
  baseline は PR #165 artefact (T=0.7) と整合する
- **windowing**: window_size=100 で baseline 5 windows / multi-turn pilot
  は 3 windows × 6 shard = 18 windows 想定 (single-turn pilot と同等)
- **interlocutor 設計**: multi-turn 採取で interlocutor utterance を何に
  するかが research design decision。M9-eval baseline の interlocutor
  protocol を参照 (`_build_stimulus_system_prompt` + `_build_interlocutor_prompt`)
- **CRLF warnings**: Windows native venv で JSON 出力時 git warn (LF への
  自動変換)、CI で問題なし
- main 直 push 禁止 / 50% 超セッション継続禁止 (`/smart-compact`)
- GPL を `src/erre_sandbox/` に import 禁止

## 完了条件 (本セッション = closure 1 PR)

### 採取 + 分析
- [ ] `tier_b_pilot.py` multi-turn 拡張 (CLI flag 追加 + interlocutor 設計)
- [ ] multi-turn pilot 採取 (3 rank × 2 run × 300 focal turn = 6 shard)
- [ ] Vendi semantic / Big5 ICC / Burrows Δ 全 3 metric × 3 rank 再算出
- [ ] DA-1 4 軸 matrix 再集約 + judgment + Cohen's d diagnostic

### ADR
- [ ] `decisions.md` DA-13 ADR 起票 (5 要素 + シナリオ判定 + 後続経路)
- [ ] `blockers.md` U-6 status update
- [ ] `tasklist.md` Phase D 着手前 dependency 順序 update

### PR
- [ ] 新 branch `feature/m9-c-adopt-pilot-multiturn-investigation`
- [ ] commit + push + `gh pr create` (PR description に matrix + DA-13 +
  シナリオ判定 + 後続 trigger 明示)
- [ ] Mac master review 待ち

### 後続経路の起票準備
- **シナリオ I** 採用時: `next-session-prompt-phase-c-or-e-direct.md` 起草
  (Phase C: nietzsche / rikyu training の入口 or Phase E A-6 direct)
- **シナリオ II** 採用時: `next-session-prompt-retrain-v2.md` 起草
  (retrain v2 PR 起点)
- **シナリオ III** 採用時: `next-session-prompt-phase-e-amended.md` 起草
  (Phase E A-6 設計 amendment)
- **シナリオ IV** 採用時: `next-session-prompt-phase-e-direct.md` 起草
  (identifiability は Phase E 7500-turn 内で結着)

## 参照

- Phase B closure PR: #165 (2026-05-14 merge 済)
- DA-12 ADR: `.steering/20260513-m9-c-adopt/decisions.md` (DEFER verdict)
- Phase B report: `.steering/20260513-m9-c-adopt/phase-b-report.md`
- 既存 consumers: `scripts/m9-c-adopt/{compute_big5_icc,compute_burrows_delta,compute_baseline_vendi,da1_matrix,tier_b_pilot}.py`
- DB8 runbook: `docs/runbooks/m9-c-adapter-swap-runbook.md` (§2
  `--max-lora-rank 16` amendment 維持)
- Tier B framework: `src/erre_sandbox/evidence/tier_b/{vendi,big5_icc,ipip_neo}.py`
- Burrows: `src/erre_sandbox/evidence/tier_a/burrows.py` +
  `reference_corpus/` (kant_de.txt)
- bootstrap CI: `src/erre_sandbox/evidence/bootstrap_ci.py`
- Codex review (Phase A 由来): `.steering/20260513-m9-c-adopt/codex-review.md`
- M9-eval P3 baseline 採取 protocol (interlocutor 設計 reference):
  `scripts/m9_eval_run_golden.py` の `_build_interlocutor_prompt()` 候補
  (要確認)

まず **`decisions.md` DA-12** + **`phase-b-report.md`** の direction
failure hot decision を完全に内面化し、本セッションの**目的が「DA-12
identifiability の empirical 解消」** (採用 rank の確定でも retrain v2
着手でもない) であることを理解した上で、Step 1 (pilot driver multi-turn
拡張) から着手する。multi-turn pilot 採取 compute (~1-2h) は SGLang
serving 単独で済むため、Ollama baseline ICC との VRAM 衝突は不要
(Ollama は PR #165 artefact 再利用)。コンテキスト使用率 50% 超で
`/smart-compact` で区切る。

本セッションが完了すれば、後続 PR (retrain v2 / Phase C / Phase E A-6
direct / Phase E A-6 amended のいずれか) を起点する正当性が
**empirical に**確定する。
```

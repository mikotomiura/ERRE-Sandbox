# M13 Layer2 ミラー・シム real 封印実走 — raw 実測記録（construction、measurement でない）

> reproducibility 記録（生実測値）。honest finding の解釈は `.steering/20260713-m13-layer2-mirror-sim-live-run/findings.md`。
> **construction であって measurement でない**: floor/verdict/scorer/magnitude/divergence 非 emit、R-budget=0。
> acceptance は非意味論 boolean のみ（Codex HIGH-1）。think=False 縮退/rendering collapse は non-gating human memo
> （semantic uptake not assessed）。

## 実行環境（env pins、2026-07-13、G-GEAR）
- モデル: qwen3:8b, digest `sha256:500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`
- Ollama: 0.31.2（Windows native, port 11434）
- think=False（ThinkOffChatClient 強制）/ seed=0 / N=3（a_kant/a_nietzsche/a_rikyu）/ horizon=12 / self_other_enabled=True
- uv.lock sha256 `9cc70f9dc5d61f6c74c08dee4dd73815993861022a80781a75ef5d873860c0f7`
- GPU RTX 5060 Ti 16GB / 再現: `experiments/20260713-m13-layer2-live/run.sh`
- 実走時間: 約 1.5 分（16:06:26 → 16:07:58）

## capture 結果
- 5 artifacts → `tests/fixtures/m2_layer2_live_golden/`（decisions / ecl_trace / envelope_stream / expected_placement / manifest）
- replay_checksum = `094f6e7f4b8075d5316de920cd41a93be8c01ae3b5bb4198e8c786985018ad99`
- event_log_checksum = `a8adc97e66974bd0c37f887264dbb92f1f216f6aae35df51973d2000f097a6cc`
- manifest env_pins: `self_other_enabled: True (bool)` / run_id=m2-layer2-live-golden / cognition_ticks=12

## (3) Windows replay-verify（Ollama-free）
```
[verify] OK fixed_constructor_fingerprint matches
[verify] OK replay checksum 094f6e7f...ad99
[verify] OK event_log_checksum a8adc97e...a6cc
[verify] OK manifest.json byte-identical re-render
[verify] OK 108 envelopes schema-conformant
[verify] SOCIETY LIVE ARTIFACT OK   (exit 0, inner_invocations=0)
```

## (4) WSL cross-platform byte-parity（Win==Linux）
WSL Ubuntu-22.04, /root/erre-sandbox/.venv/bin/python 3.11.15, PYTHONPATH=Windows src:
```
[verify] OK replay checksum 094f6e7f...ad99          ← Win と同一
[verify] OK event_log_checksum a8adc97e...a6cc       ← Win と同一
[verify] OK manifest.json byte-identical re-render
[verify] SOCIETY LIVE ARTIFACT OK   (exit 0)
```
→ **Win==Linux byte-parity 確認**（判断3 = envelope_provenance 量子化継承 + float-free segment）。

## (1)(2) existence preview（構造 boolean、非意味論、magnitude 非読取）
36 decisions（N=3 × horizon=12）。per (agent, tick) の framing 存在 + observed set:
- **tick 0**: 全 3 agent framing=False（prior window 無し = honest、prefix filter の対偶）
- **tick 1..11**: 全 3 agent framing=True、observed set == `sorted(all_agents) - {observer}`:
  - a_kant → {a_nietzsche, a_rikyu} / a_nietzsche → {a_kant, a_rikyu} / a_rikyu → {a_kant, a_nietzsche}
- 全 36 decision で plan が dict として構造 parse される（plan_ok=True、内容評価しない）

sample segment（a_kant tick=1）:
```
Others you observed one step ago — simulate each one's likely inner state and let it inform your
own next action. This is a functional analog of taking their perspective, not a claim about their true mind:
- a_nietzsche: zone=peripatos, moved_toward=agora
- a_rikyu: zone=peripatos, moved_toward=garden
```

## rendering collapse 診断（non-gating human memo、semantic uptake not assessed）
- LLM-authored distinct `destination_zone` across 36 decisions = **全 5 zone**: agora / chashitsu / garden /
  peripatos / study（R1「think=False で zone 移動しない」を empirical 反証、M4 と同 kernel）。
- segment 内の `zone=`（other の rendered/current zone）は peripatos に collapse（memory_centroid、M4 rendering
  collapse を再確認）。`moved_toward=`（LLM-authored）は distinct。
- **注意（over-read 禁止）**: 「他者観察が行動をどれだけ変えたか」は測っていない（covert scorer 禁止）。segment は
  genuine に注入され LLM は応答した、という**存在**のみ。semantic uptake は assessed でない。

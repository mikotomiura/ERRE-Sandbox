# experiment: 20260717-aha-phase3-think-true-live

aha!/DMN-ECN **Phase 3 — think=True LLM 稼働検証**（real qwen3:8b **construction spend**、verdict なし）。
Phase 2 で *設計だけ* した二相捕捉 regime（`.steering/20260713-aha-phase2-door-scoping/design-final.md` §(b)）を
実装し、think=True の reasoning trace で「生成→評価の二相構造が *存在するか*」を **存在確認**する。

> **これは construction spend であって measurement spend でない**（R-budget=0 不変、holding、
> measurement-line CLOSE 不変）。**verdict/scorer/floor/aha proxy を持たない**（over-read 禁止）。
> **観察器 = think=True text trace のみ**（J-lens 不採用、前段 spike 判定 B）。

## 設計要旨（design-final = `.steering/20260717-aha-phase3-think-true-live/design-final.md`）
- **prompt provenance（決定的、pin 可能）**: committed ECL v0 の 32 kant embodied cognition prompt
  （`experiments/20260706-ecl-v0-live-capture/artifacts/decisions.jsonl`、think=False 決定的、
  `manifest.json` の `replay_checksum` + JSONL sha256 で pin）を再利用。organ loop は回さない。
- **観察 pass（非決定、confined）**: 各 prompt を **think=True で別発行**し `message.thinking`+content を raw 記録。
- **prompt-replay capture であって live-loop execution ではない**（主張範囲、Codex M1）。
- **byte-parity verify 無し / manifest に Phase 3 replay_checksum 無し**（think=True 非決定、§(b) 原則3・Codex H2）。

## 再現（1 コマンド、G-GEAR Windows native）
```powershell
# 前提: Windows native Ollama 起動済 (127.0.0.1:11434) + qwen3:8b pull 済
#       (WSL2 からは Windows Ollama 不通ゆえ Windows native で実行, reference_wsl2_ollama_unreachable)
pwsh experiments/20260717-aha-phase3-think-true-live/run.ps1
# または pwsh 不在時:
powershell.exe -NoProfile -File experiments/20260717-aha-phase3-think-true-live/run.ps1
```
`run.ps1` は env pins（ollama version / qwen3 digest / VRAM / uv.lock sha256、Codex L3）を採取し、
`scripts/aha_phase3_think_capture.py --capture` を実行して `artifacts/{manifest.json, think_traces.jsonl}` を出力する。

## 観察（Ollama-free、封印実走後）
```powershell
python scripts/aha_phase3_think_capture.py --observe --traces experiments/20260717-aha-phase3-think-true-live/artifacts/think_traces.jsonl
```
再考マーカーの **excerpt inventory** + boolean 出現有無 + thinking 抜粋を surface する（Codex H4: count/score/
verdict は計算しない）。これを **raw 素材**に `observation-memo.md` を **人手記述**する（①二相構造の記述所見 +
②再考マーカー出現有無+例示、**非 verdict**）。

## Stop（honest）
think=True が動かない / thinking 空 / parse 不能 → **honest な技術所見として記録**（silent fail にしない）。
「観察できなかった」こと自体が Phase 2 反証条件(1) の入力。transport failure は nonzero exit + partial
diagnostic、empty/parse-unable は exit 0 + observation note（Codex H5）。

## 成果物
- `artifacts/manifest.json` — env pins + prompt_provenance + mechanical_technical_counts（非 verdict）
- `artifacts/think_traces.jsonl` — per-prompt raw trace（thinking/content + 技術的 facts）
- `observation-memo.md` — 人手記述の二相 existence 所見（非 verdict、封印実走後に作成）

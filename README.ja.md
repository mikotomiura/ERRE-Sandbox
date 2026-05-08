# ERRE-Sandbox

[English](README.md) | [日本語](README.ja.md)

ERRE-Sandbox は歴史的偉人 (アリストテレス、カント、ニーチェ、利休、道元ほか)
の認知習慣を、ローカル LLM で駆動される自律エージェント群として 3D 空間に
再実装する研究プラットフォームです。「意図的非効率性」と「身体的回帰」を
設計プリミティブとして、知的創発を観察します。

## 現在の状態 — M9-A merged、M9-B / M9-eval 進行中 (last verified 2026-05-08)

ワイヤースキーマは **`0.10.0-m7h`** (M9-A `event-boundary-observability`
での bump、その上に M7ζ `live-resonance` を載せた状態)。3 体エージェント社会
(カント / ニーチェ / 利休) は `uv run erre-sandbox --personas
kant,nietzsche,rikyu` で起動し、M5 の ERRE モード FSM・マルチターン LLM 対話、
5 ゾーン (`peripatos` / `chashitsu` / `zazen` / `agora` / `garden` および
`study` / `base_terrain`) のシーンが Godot 4.6 ビューア上で稼働しています。
M9-A で trigger-event タグが Python 側 `Reflector` から `ReasoningPanel` まで
伝搬し、観察者は反省発火の *理由* を確認できます。

最近の主要マイルストン (新しい順):

- **認知深化 7-point 提案 final 判定** (2026-05-08、本 PR — design only、
  source 変更なし): 3-source synthesis (Claude initial Plan-mode +
  independent reimagine subagent + Codex `gpt-5.5 xhigh` 197K tokens
  ADOPT-WITH-CHANGES、HIGH 7 / MEDIUM 5 / LOW 3) で将来の二層認知
  architecture を確定 (`PhilosopherBase` immutable inheritance +
  `IndividualProfile` mutable runtime + `SubjectiveWorldModel` /
  `DevelopmentState` S1–S3 / `NarrativeArc` / bounded
  `WorldModelUpdateHint`)。実装は **M9 完全終了後にゲート** (M10-0
  metric scaffolding が schema 作業に先行)。最終仕様は
  `.steering/20260508-cognition-deepen-7point-proposal/design-final.md`、
  ADR は `decisions.md`。G-GEAR の run1 calibration に影響なし。
- **M9-eval ME-9 trigger amendment** (2026-05-07、PR #142): run1 cell 100/101
  の正規 STOP を擬陽性 trigger と判定 (Codex 9 回目 hybrid A/C verdict)、
  cooldown 再調整は棄却。ADR ME-9 に Amendment 2026-05-07 + v2 prompt §A.4
  saturation model + §B-1b run102 resume 手順を追記。
- **M9-eval Phase 2 run1 calibration v2 prompt** (2026-05-07、PR #141):
  live `qwen3:8b` 用 G-GEAR launch prompt v2 (kant 1 cell × 5、wall ≈ 30 h
  × 2 晩)、golden battery driver + audit gate (`erre-eval-run-golden` /
  `erre-eval-audit`)、`raw_dialog` ↔ `metrics` の 4 層 schema contract
  (`src/erre_sandbox/contracts/eval_paths.py`)、`data/eval/calibration/run1/`
  への隔離と sidecar md5 receipt。
- **M9-eval CLI partial-fix** (2026-05-06、PR #140): `eval_audit` gate +
  capture-sidecar receipts + `--allow-partial` semantics、1318 tests PASS。
- **M9-B LoRA execution plan** (2026-04-30、PR #127): SGLang-first ADR
  (DB1–DB10) + Kant spike 並走。実装そのものは次マイルストン。
- **M9-A event-boundary observability** (2026-04-30、PR #117–#124、6/6 PASS):
  `TriggerEventTag` を reasoning panel まで貫通、`pulse_zone` の観測は
  ログベースの START counter に切替済。
- **Godot viewport layout** (2026-04-28、PR #115/#116): HSplit +
  reasoning panel collapse、RTX 5060 Ti 実機検収。
- **CI pipeline + Codex 環境構築** (2026-04-28、PR #113/#114): pre-commit
  + 3 並列 CI jobs (`lint` / `typecheck` / `test`)、`.codex/` 設定 +
  `AGENTS.md` で Codex CLI を first-class partner 化。
- **Contracts レイヤー** (2026-04-28、PR #111/#112):
  `src/erre_sandbox/contracts/` を ui-allowable な軽量 Pydantic 境界として
  新設 (thresholds、eval paths)。
- 過去のリリースタグ: `v0.1.0-m2` (contract 凍結) / `v0.1.1-m2` (1 体 MVP)
  / `v0.2.0-m4` (3 体 reflection + dialog) / `v0.3.0-m5` (ERRE FSM +
  LLM dialog + zone visuals)。

**次マイルストン**: (1) G-GEAR での M9-eval Phase 2 run1 wall-budget
calibration (kant 単体 cell × 5、~30 h × 2 晩)、(2) M9-B LoRA 実装
(`m9-c-spike`)、(3) `godot-ws-keepalive` の信頼性改善。M9 完全終了後に
**M10+ 認知深化** に着手 (M10-0 metric → M10-A 二層 schema scaffold →
M10-B SWM read-only → M10-C bounded `WorldModelUpdateHint` → M11-A
`NarrativeArc` → M11-B S1–S3 transition → M11-C kant-base × 3 individuals
validation; S4/S5 / retirement / individual LoRA は M12+ gate)。

## 主要コンポーネント

- **Python 3.11 コア** (`src/erre_sandbox/`): Pydantic v2 スキーマ
  (`schemas.py`)、推論アダプタ (Ollama / SGLang [planned])、記憶
  (sqlite-vec + `origin_reflection_id` を持つ semantic layer)、`Reflector`
  を組み込んだ CoALA 準拠認知サイクル、ERRE FSM (`erre/`)、ワールド tick
  ループ、proximity ベースの in-memory dialog scheduler。
- **Contracts レイヤー** (`src/erre_sandbox/contracts/`): pydantic + 標準
  ライブラリのみで構成された軽量境界モジュール (`thresholds.py`、
  `eval_paths.py`)。`ui/`、`integration/`、`evidence/` から重い依存を
  経由せず import 可能。
- **Evidence レイヤー** (`src/erre_sandbox/evidence/`): post-hoc 指標
  集計 — M8 baseline quality (`self_repetition_rate` /
  `cross_persona_echo_rate` / `bias_fired_rate`)、M8 scaling profile
  (`pair_information_gain` / `late_turn_fraction` / `zone_kl_from_uniform`)、
  M9-eval Tier-A pipeline (Burrows / MATTR / NLI / novelty / Empath proxy)、
  bootstrap CI、golden baseline driver、capture sidecar。
- **Eval CLI** (`src/erre_sandbox/cli/`):
  - `erre-sandbox` サブコマンド — `run` (default)、`export-log`、
    `baseline-metrics`、`scaling-metrics`。
  - 単体実行 — `python -m erre_sandbox.cli.eval_run_golden` /
    `python -m erre_sandbox.cli.eval_audit` (M9-eval)。
- **Godot 4.6 フロントエンド** (`godot_project/`): WebSocket 経由の
  3D 可視化。humanoid avatar、ERRE モード tint、dialog bubble、
  trigger-event タグ付き reasoning panel、6 シーン (`MainScene` +
  `BaseTerrain` + 5 ERRE zones)。
- **ペルソナ** (`personas/*.yaml`): 偉人ごとの認知習慣、ERRE モードの
  サンプリングオーバーライド、パブリックドメイン史料への参照。現行:
  `kant.yaml`、`nietzsche.yaml`、`rikyu.yaml` (追加ペルソナは
  observability-triggered scaling の trigger 待ち、`docs/glossary.md`
  参照)。

## 開発の始め方

```bash
uv sync
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -m "not godot"
```

pre-commit hook はコミット時にステージされた `src/` / `tests/` の Python
ファイルに対して `ruff check` と `ruff format --check` を実行します。
GitHub Actions CI (`.github/workflows/ci.yml`、`main` への push 時と PR 時)
は 4 つのチェック (`ruff check` / `ruff format --check` / `mypy src` /
`pytest -m "not godot"`) を `lint` / `typecheck` / `test` の 3 並列 jobs
で実行します。Godot バイナリ依存テスト (`@pytest.mark.godot` 付与) は CI から
deselect され、手動でのみ実行されます。 [uv](https://docs.astral.sh/uv/)
が必要です。クローン直後にローカル hook を有効化するには:

```bash
uv tool install pre-commit
pre-commit install
```

M9-eval パイプライン用の重い ML 依存 (sentence-transformers、scipy、
ollama、empath、arch) は `eval` extras に分離されています:

```bash
uv sync --extra eval
```

## ディレクトリ構成

正典は `docs/repository-structure.md`、全体のデータフローは
`docs/architecture.md` を参照してください。ERRE 固有用語 (peripatos、
chashitsu、守破離、observability-triggered scaling …) の定義は
`docs/glossary.md` にあります。

## ライセンス

**Apache-2.0 OR MIT** のデュアルライセンス。利用者が選択できます。
`LICENSE` / `LICENSE-MIT` / `NOTICE` を参照。Blender 連携は GPL-3.0 の
別パッケージ (`erre-sandbox-blender/`) に完全分離することで、本体の
ライセンス汚染を防いでいます。

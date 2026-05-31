<div align="center">

# 🏛️ ERRE-Sandbox

**偉人たちの認知習慣から創発する自律 3D 社会**

歴史的偉人の認知習慣を、ローカル LLM で駆動される自律エージェント群として
3D 空間に再実装する研究プラットフォーム。「**意図的非効率性**」と「**身体的
回帰**」を設計プリミティブとして、知的創発を観察します。

[![CI](https://github.com/mikotomiura/ERRE-Sandbox/actions/workflows/ci.yml/badge.svg)](https://github.com/mikotomiura/ERRE-Sandbox/actions/workflows/ci.yml)
[![License: Apache-2.0 OR MIT](https://img.shields.io/badge/license-Apache--2.0%20OR%20MIT-blue.svg)](#-ライセンス)
[![Python 3.11](https://img.shields.io/badge/python-3.11-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Godot 4.6](https://img.shields.io/badge/Godot-4.6-478CBF.svg?logo=godotengine&logoColor=white)](https://godotengine.org/)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://github.com/astral-sh/ruff)

[English](README.md) | **日本語**

</div>

---

## ✨ ERRE-Sandbox とは

ERRE-Sandbox は歴史的偉人 — 現行は **カント / ニーチェ / 利休** — を
ローカル LLM エージェントとして起動し、Godot 4.6 の世界の中で歩き・反省し・
対話させます。スループット最適化ではなく、*非効率性* (逍遥 / 茶室の静寂 /
坐禅) と *身体的回帰* (身体を動かして認知をリセットする) を設計プリミティブ
として扱い、そこから何が創発するかを観察します。

- 🧠 **認知習慣をコードに** — 各偉人の習慣・ERRE モードのサンプリング
  オーバーライド・パブリックドメイン史料への参照を `personas/*.yaml` に記述。
- 🌀 **ERRE モード FSM** — `peripatetic / chashitsu / zazen / shu-kata /
  ha-deviate / ri-create / deep-work / shallow` がサンプリングと行動を駆動。
- 🪟 **観察可能な推論** — trigger-event タグが Python 側 `Reflector` から
  Godot の reasoning panel まで伝搬し、反省発火の *理由* を可視化。
- 🔬 **証拠グレードの評価** — post-hoc 指標層 (Burrows Δ / MATTR / NLI /
  novelty / Big5 ICC / Vendi diversity) を階層 bootstrap CI 付きで、隔離した
  DuckDB shard 上で計測。

---

## 🧭 現在の状態

> **ワイヤースキーマ `0.10.0-m7h`** · 3 体エージェント社会が Godot 4.6 で稼働 ·
> M9-C-adopt (kant LoRA pilot) は **closed** · 次マイルストン: **M10-11 評価フレームワーク**

3 体エージェント社会は `uv run erre-sandbox --personas kant,nietzsche,rikyu`
で起動し、M5 の ERRE モード FSM・マルチターン LLM 対話、全ゾーンシーン
(`peripatos` / `chashitsu` / `zazen` / `agora` / `garden` および `study` /
`base_terrain`) が稼働します。

**M9-C-adopt — カント LoRA ADOPT pilot: REJECT verdict で完了 (2026-05-25)。**
kant-style LoRA は Burrows 文体忠実度を *改善できる* (ICC / throughput gate も
クリア) が、**encoder panel 横断で出力多様性を同時に集約できない** —
Vendi-Burrows の *同時達成* は tested 設計空間内で非達成 (構造的に異なる 2 機構
`case A` auxiliary-loss と `case B` preference optimization が同一軸で失敗)。
これは失敗ではなく **completion + 方法論 finding + ADOPT-negative** として記録。
研究プログラムは意図的に **terminate** (disposition と将来研究を会計分離)。

**次 — M10-11: 4 層評価フレームワーク + 統計レポート。**
Layer 1 空間的 / Layer 2 意味論的 / Layer 3 儀式的 / Layer 4 第三者
(LLM-as-judge)。Benjamini-Hochberg FDR 補正 (n ≥ 20) + OSF 事前登録を行い、
既存の Tier-A/B 証拠指標と DuckDB contract を再利用します。
`docs/functional-design.md` §5 / MASTER-PLAN §5 参照。

<details>
<summary>過去の主要マイルストン</summary>

- **M9-C-adopt Plan B kant chain** (2026-05): PR-7…PR-24 → retrain (KTO、
  composite Burrows preference) → PR-21 REJECT verdict → terminate ADR →
  terminal-hygiene cleanup (verdict narrative + da14⇆da19 fold doc 化)。
- **M9-eval Phase 2** (2026-05): `qwen3:8b` golden-battery driver +
  audit gate、4 層 `raw_dialog` ↔ `metrics` DuckDB contract。
- **M9-A event-boundary observability** (2026-04): `TriggerEventTag` を
  reasoning panel まで貫通。
- **CI パイプライン** (2026-04): 3 並列 CI (`lint` / `typecheck` / `test`)。
- リリースタグ: `v0.1.0-m2` → `v0.3.0-m5` (ERRE FSM + LLM dialog + zones)。

</details>

---

## 🧱 アーキテクチャ

| レイヤー | パス | 責務 |
|---|---|---|
| **Python コア** | `src/erre_sandbox/` | Pydantic v2 スキーマ、推論アダプタ (Ollama / SGLang)、sqlite-vec 記憶、CoALA 準拠認知サイクル (`Reflector`)、ERRE FSM (`erre/`)、ワールド tick ループ、proximity dialog scheduler |
| **Contracts** | `src/erre_sandbox/contracts/` | pydantic のみの軽量境界 (`thresholds.py` / `eval_paths.py`)。重い依存なしで import 可 |
| **Evidence** | `src/erre_sandbox/evidence/` | post-hoc 指標: M8 baseline/scaling、M9-eval Tier-A (Burrows / MATTR / NLI / novelty / Empath)、Tier-B (Big5 ICC / Vendi)、bootstrap CI、golden driver |
| **CLI** | `src/erre_sandbox/cli/` | `erre-sandbox` (`run` / `export-log` / `baseline-metrics` / `scaling-metrics`) + 単体 `eval_run_golden` / `eval_audit` |
| **Godot フロントエンド** | `godot_project/` | WebSocket 経由の 3D 可視化: humanoid avatar、ERRE モード tint、dialog bubble、reasoning panel、6 シーン |
| **ペルソナ** | `personas/*.yaml` | 偉人ごとの認知習慣・ERRE モードのサンプリングオーバーライド・パブリックドメイン史料 (`kant` / `nietzsche` / `rikyu`) |

依存方向は厳格です。`src/erre_sandbox/` は GPL コードを決して import せず
(Blender 連携は別パッケージ `erre-sandbox-blender/` に隔離)、クラウド LLM API
を必須依存にしません (予算ゼロ制約)。

---

## 🚀 開発の始め方

[uv](https://docs.astral.sh/uv/) が必要です。

```bash
uv sync
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -m "not godot"

# 3 体エージェント社会を起動
uv run erre-sandbox --personas kant,nietzsche,rikyu
```

評価パイプライン用の重い ML 依存 (sentence-transformers、scipy、ollama、
empath、arch) は extras に分離されています:

```bash
uv sync --extra eval        # M9-eval Tier-A/B 指標
```

CI (`.github/workflows/ci.yml`) は上記 4 チェックを 3 並列 jobs で `main` への
push 時と全 PR で実行します。クローン直後にローカル pre-commit hook を有効化:

```bash
uv tool install pre-commit && pre-commit install
```

### 🔐 WebSocket 認証 (任意)

オーケストレータの WebSocket は default-off の独立 3 ゲート (shared token /
Origin allow-list / session cap) を備えます。`bootstrap()` は
`host=0.0.0.0` かつ全ゲート off では起動を拒否するため、素の
`--host=0.0.0.0` でサーバが黙って露出することはありません。LAN 開発時:

```bash
uv run python -m erre_sandbox --allow-unauthenticated-lan   # 起動毎に警告
```

token の発行・ローテーション・優先順位は `docs/development-guidelines.md`
に記載しています。

---

## 🗂️ ディレクトリ構成とドキュメント

| ドキュメント | いつ読むか |
|---|---|
| `docs/functional-design.md` | 機能の意図・要件・4 層評価フレームワーク |
| `docs/architecture.md` | 技術スタックとデータフロー |
| `docs/repository-structure.md` | 正典のファイル配置・依存方向 |
| `docs/development-guidelines.md` | コーディング規約・Git ワークフロー・テスト方針 |
| `docs/glossary.md` | ERRE 固有用語 (peripatos、chashitsu、守破離 …) |

---

## 📜 ライセンス

利用者が選択できる **Apache-2.0 OR MIT** のデュアルライセンス —
`LICENSE` / `LICENSE-MIT` / `NOTICE` を参照。Blender 連携は **GPL-3.0** の
別パッケージ (`erre-sandbox-blender/`) に完全分離し、本体のライセンス汚染を
防いでいます。

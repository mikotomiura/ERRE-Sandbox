# Phase K-α handoff prompt — m9-c-spike mock-LoRA infrastructure proof

**Active task**: `20260508-m9-c-spike` (Bounded Kant LoRA spike on SGLang、
M9-B 第3の道 ADR、Codex 11 回目 review HIGH 4 / MEDIUM 6 / LOW 3 全反映済).

**This document is the handoff to the next G-GEAR session** that will run
Phase K-α physically — Phase G+H+I+J have already shipped via PR
`feature/m9-c-spike-phase-g-to-k-alpha` and merged on `main`. The Mac /
review session does not run this prompt; the G-GEAR (RTX 5060 Ti 16GB
CUDA host) session does, after a fresh `git pull origin main`.

## 目的

`SGLangChatClient` + `tools/spike/build_mock_lora` の実装が **G-GEAR 物理環境**
で正しく動くことを実走確認する。3 つの DB3 即時 fire 条件 (CS-8) を 3 つの
チェックで網羅する:

1. SGLang `--enable-lora` 起動成功 → 起動失敗 = DB3 即時 fire
2. `/load_lora_adapter` が PEFT directory を直接受け付け → format reject = DB3 即時 fire
3. M5 resonance / ERRE FSM が SGLang LoRA 経路で破綻なし → regression = DB3 即時 fire

Phase K-α scope **外**:

- Phase K β real Kant training (blockers B-1 / B-2 hard-block 中、別 PR)
- N=3 throughput 実測 (CS-7 protocol、Phase K β で SGLang `bench_serving` 経由)
- adapter swap latency 実測 (CS-8 diagnostic、real Kant adapter で confirmation 必須)

## 前提環境

- **G-GEAR** (`reference_g_gear_host.md` の auto-memory 参照):
  - OS: Windows 11 (本作業ディレクトリ)
  - GPU: RTX 5060 Ti 16GB / CUDA 12.x driver
  - Ollama 起動済 (M2 cognition cycle 用、SGLang と coexist)
- ブランチ: `main` (PR `feature/m9-c-spike-phase-g-to-k-alpha` merge 後の状態)
- `data/eval/calibration/run1/` は本タスクと無関係 (M9-eval P3 採取の artefact、
  K-α では無視)

## 環境セットアップ (`uv` extras 排他、CS-1 conflicts 整合)

`pyproject.toml` の `[tool.uv].conflicts` で `[inference]` ⇔ `[training]` を
排他宣言済 (transformers major version の衝突を universe 分割で解決)。手順は
SGLang 経路と mock-LoRA build 経路で **別 venv** を切り替えて使う:

### Step 0a: mock-LoRA build venv (`uv sync --extra training`)

```powershell
# mock-LoRA build に必要 (peft / transformers / accelerate / bitsandbytes / datasets)
uv sync --extra training
```

### Step 0b: SGLang serve venv (`uv sync --extra inference`)

```powershell
# SGLang server に必要 (sglang==0.5.10.post1 + flash-attn-4 prerelease)
uv sync --extra inference
```

両者は **同時に共存できない**。mock-LoRA を build した後、`uv sync --extra inference`
で venv を切り替えてから SGLang を起動する。adapter directory (`adapter_config.json`
+ `adapter_model.safetensors`) はファイルシステム上に残るので、venv 切替後も
`/load_lora_adapter` で読み出せる。

## Step 1: mock-LoRA build (CS-9)

```powershell
uv sync --extra training
uv run python -m tools.spike.build_mock_lora --output-dir checkpoints/mock_kant_r8
```

期待出力:
- `checkpoints/mock_kant_r8/adapter_config.json` — `metadata.mock == "true"`
- `checkpoints/mock_kant_r8/adapter_model.safetensors` — B 行列 = 0 (identity)

確認:
```powershell
uv run python -c "import json; print(json.load(open('checkpoints/mock_kant_r8/adapter_config.json'))['metadata'])"
```

## Step 2: SGLang launch (CS-1 launch args)

```powershell
uv sync --extra inference
python -m sglang.launch_server `
  --model qwen/Qwen3-8B `
  --enable-lora `
  --max-loras-per-batch 3 `
  --max-lora-rank 8 `
  --max-loaded-loras 3 `
  --port 30000
```

期待: server が `http://127.0.0.1:30000/health` で 200 を返す。

**STOP 条件** (CS-8 即時 fire #1): 起動失敗 → DB3 fire、Phase K-α abort。
原因記録 (e.g. CUDA driver mismatch / wheel install failure) を `decisions.md`
の CS-1 amendment に追記し、`m9-c-sglang-version-readjust` 別タスクで
re-pin 検討。

## Step 3: PEFT direct load (CS-6)

別ターミナルで:
```powershell
uv run python -c "
import asyncio, httpx
from pathlib import Path
from erre_sandbox.inference import LoRAAdapterRef, SGLangChatClient

async def main():
    async with SGLangChatClient(endpoint='http://127.0.0.1:30000') as llm:
        ref = LoRAAdapterRef(
            adapter_name='mock_kant_r8',
            weight_path=Path('checkpoints/mock_kant_r8'),
            rank=8,
            is_mock=True,
        )
        await llm.load_adapter(ref)
        print('loaded:', dict(llm.loaded_adapters))

asyncio.run(main())
"
```

期待: HTTP 200 + `loaded_adapters` registry に `mock_kant_r8` 追加。

**STOP 条件** (CS-8 即時 fire #2): HTTP 4xx/5xx (`SGLangUnavailableError`) →
DB3 fire、Phase K-α abort。CS-6 amendment に直接 load 失敗の specific
failure mode を記録し、conversion script を別タスク化 (`m9-c-spike-peft-conversion`).

## Step 4: chat round trip (CS-9 identity transform 確認)

```powershell
uv run python -c "
import asyncio
from pathlib import Path
from erre_sandbox.inference import (
    ChatMessage, LoRAAdapterRef, SGLangChatClient,
    ResolvedSampling, compose_sampling,
)
from erre_sandbox.schemas import SamplingBase, SamplingDelta

async def main():
    async with SGLangChatClient(endpoint='http://127.0.0.1:30000') as llm:
        ref = LoRAAdapterRef(
            adapter_name='mock_kant_r8',
            weight_path=Path('checkpoints/mock_kant_r8'),
            rank=8,
            is_mock=True,
        )
        await llm.load_adapter(ref)
        sampling = compose_sampling(
            SamplingBase(temperature=0.6, top_p=0.85, repeat_penalty=1.12),
            SamplingDelta(),
        )
        # Same prompt twice — once with adapter, once without
        prompt = [
            ChatMessage(role='system', content='You are Immanuel Kant.'),
            ChatMessage(role='user', content='Describe today\\'s walk briefly.'),
        ]
        with_adapter = await llm.chat(prompt, sampling=sampling, adapter='mock_kant_r8')
        without_adapter = await llm.chat(prompt, sampling=sampling)
        print('WITH MOCK    :', with_adapter.content[:120])
        print('WITHOUT      :', without_adapter.content[:120])
        # Identity expectation: outputs should match (deterministic seed needed
        # for byte-exact, but content shape should be substantially identical)

asyncio.run(main())
"
```

期待: `WITH MOCK` と `WITHOUT` の出力が **概ね一致** (PEFT default は B=0 で
identity transform、CS-9 / LOW-2)。決定的 seed なしの場合、temperature による
差は許容するが、語彙 / 文体 / 長さの大きな乖離は LoRA 経路の bug 候補。

## Step 5: ERRE FSM 8-mode smoke

各 ERRE mode の persona-system prompt を 1 turn ずつ流し、SGLang LoRA 経路で
8 mode の transition が破綻なく回るかを確認する。最小は `deep_work` 1 mode
だけでも可、本 PR では完全 8 mode を後続 Phase K-α extension PR で扱う。

```powershell
# 例: deep_work mode で chat → expected: ChatResponse 形状で finish_reason=stop
# (詳細 ERRE mode prompt template は cognition/prompting.py を参照)
```

**STOP 条件** (CS-8 即時 fire #3): いずれかの mode で `ChatResponse.model_validate`
失敗、`finish_reason="length"` 連発、または明らかな nonsense output → DB3 fire、
Phase K-α abort。原因 (LoRA pollution / adapter routing bug / format reject)
を `blockers.md` に記録し、SGLang 経路継続可否を判断。

## STOP 条件サマリ (CS-8)

本 K-α 実走中の **即時 fire 3 条件** はすべて mock-LoRA でも fire:

1. SGLang `--enable-lora` 起動失敗 (Step 2)
2. `/load_lora_adapter` PEFT format 拒否 (Step 3)
3. M5 resonance / ERRE FSM が SGLang LoRA 経路で regression (Step 5)

**diagnostic 扱い** (real Kant adapter で confirmation 必要、本 K-α では fire しない):

- adapter swap latency >500ms (CS-8 / Phase K β scope)
- N=3 throughput collapse (CS-7 / Phase K β scope)

**VRAM 補助条件** (Phase K β に向けた事前計測):

- `nvidia-smi` で SGLang server の peak VRAM が **8.7GB を大幅超過** (CS-4 estimate)
  → `--mem-fraction-static` 調整 + Step 2 から再起動。CS-4 amendment に実測値を
  追記してから次セッション続行。

## Report-back format (Mac 側 review session に戻す情報)

実走完了後、`.steering/20260508-m9-c-spike/k-alpha-report.md` を新規作成して
以下を記録 (commit + push、merge は Mac 側):

- 各 Step の actual command + output (stderr / stdout 抜粋)
- SGLang `--enable-lora` 起動時の VRAM 消費 (`nvidia-smi` snapshot)
- `/load_lora_adapter` HTTP status + response payload (PEFT direct load 成否)
- chat round trip の `WITH MOCK` / `WITHOUT` 出力比較
- FSM 8-mode 各 mode の合否
- DB3 fire 判断 (3 条件のいずれか fire したか / 全 pass で K-α 完了か)
- CS-N amendment に追記すべき実測値 (VRAM / latency 一次観測)

## Phase K β trigger 条件 (本 K-α では trigger しない)

- B-1 (`m9-individual-layer-schema-add`) 完了
  → `ALLOWED_RAW_DIALOG_KEYS` + `_RAW_DIALOG_DDL_COLUMNS` に
  `individual_layer_enabled` 追加 + training-view 入口 assert + grep gate
- B-2 (M9-eval P3 採取) 完了
  → run1 calibration → run2-4 の 3 persona × 5 run × 500 turn = 7500 turn 採取、
  `assert_phase_beta_ready(min_examples=1000)` 通過確認

両者 unblock 後、別 PR `feature/m9-c-spike-phase-k-beta` で:
- `train_kant_lora()` 関数の inner loop 実装 (peft / transformers / accelerate /
  bitsandbytes / datasets を関数内 lazy import で使用)
- Kant rank=8 PEFT QLoRA NF4 train run (~2-4h on G-GEAR)
- SGLang `bench_serving` で N=3 throughput 実測 (CS-7 protocol)
- 5 condition adapter swap latency 実測 (CS-8: cold/warm/pinned/unpinned/no-LoRA)
- DB3 fallback fire 最終判断 (real adapter confirmation)

## CLAUDE.md 禁止事項リマインド (G-GEAR session 用)

- main 直 push 禁止 (Phase K β は別 branch で扱う)
- `.steering/` 記録省略禁止 (本 K-α report-back は必須)
- 50% 超セッション継続禁止 (`/smart-compact` または `/clear`)
- GPL 依存を `src/erre_sandbox/` に import 禁止 (peft / transformers は
  Apache-2.0 / MIT 確認済)
- `train_kant_lora()` 関数本体実装は **本 K-α では絶対 trigger しない**
  (B-1/B-2 解消が前提条件)

---

**Refs**:
- `.steering/20260508-m9-c-spike/m9-c-spike-design-final.md` (HIGH 4 反映済 spec)
- `.steering/20260508-m9-c-spike/decisions.md` (CS-1 / CS-6 / CS-8 / CS-9)
- `.steering/20260508-m9-c-spike/blockers.md` (B-1 / B-2 / S-1 / S-2 / S-3)
- `tools/spike/build_mock_lora.py` (Phase J 実装)
- `src/erre_sandbox/inference/sglang_adapter.py` (Phase H 実装)

# M13 live-loop I7 — real qwen3 sealed 実走 — environment / status

- **実験**: M13 live 双方向ループ閉包の I7 = 配線 (PR #89 landed) を **real qwen3:8b +
  real nomic-embed-text** で封印実走し、各 seam への到達性を live で観察する (construction)
- **apparatus**: `scripts/m13_live_loop_capture.py` (`--capture` / `--capture --real
  --confirm-spend` / `--verify`) + `src/erre_sandbox/integration/embodied/live_loop.py` +
  `src/erre_sandbox/integration/inbound.py` (**両方とも無改変・import 駆動のみ**)
- **ADR**: `.steering/20260724-m13-live-loop-closure/design-final.md` (FROZEN、binding) §5 Issue 007
- **セッション記録**: `.steering/20260904-m13-live-loop-i7-real-run/`
- **仮説接続**: これは **construction validation** (配線が real backend で各 seam に届く boolean 観察)
  であって measurement ではない。effect / detectability は C-proper 第2リンク = 凍結 measurement line
  (非測定・非再入)。借用 apparatus = Phase 4b (`two_phase_live.py` の SamplingSpy / seeded factory /
  env_pins overlay) + traversal I4 (`EmbeddingRecordReplayClient` の二チャネル record/replay)。
  凍結 `src/erre_sandbox/evidence/` は touch しない。

## honest scope (不可侵)

**land しているのは配線であって aha / emergence / effect ではない。**
I7 が全 seam 到達 + firing を live で観測しても、主張できるのは
**"wiring reached each seam (live, real qwen3)"** のみ。door② UNMET・計測ライン CLOSE・
R-budget=0・holding 不変。

さらに I7 固有の 2 境界 (manifest `observables.scope_boundary` にも埋め込み済):

1. **real なのは cognition 面のみ**。摂動は事前登録した scripted bounded 列を `InboundSink` に
   直接投入する構成で、**live Godot クライアントは使わない** (Godot send 契約は I5 で検証済、
   本機に godot バイナリ無し)。実 Godot + real qwen3 の end-to-end は別タスク (MacBook、env-gate)。
2. **wall-clock real-time セッションではない**。byte-parity 規律のため `ManualClock(start=0.0)` を使う。
   「live」= cognition チャネルが real、という意味であって実時間で回したという意味ではない。

## status (2026-09-06 — sealed real run 実走済み)

- **rehearsal (Ollama-free) = 構造緑・commit 済** (`rehearsal/`)。sealed run と **同一形状**
  (32 cognition × 20 physics tick、knob=on、1 tick あたり 1 摂動)、同一 artifact 集合、
  **同一 verify コード経路**。したがって rehearsal の緑は real bundle の verify が構造的に
  通ることの実証になる (差分は Plane 1 backend のみ)。
- **sealed real run (`artifacts/`) = 2026-09-06 に 1 回だけ実走・全 gate 緑** (下記「結果」)。
  事前登録どおりのパラメータで走り、tuning・再走・パラメータ探索はゼロ。
  `--real` は `--confirm-spend` 無しでは exit 2 で拒否する (規約でなく apparatus が強制)。
- **L3 の WSL 直接実測は本機では引き続き不可** (WSL 側に project venv が無い。
  `/root/erre-sandbox/.venv` 不在・system python3 に pydantic 無しを本セッションで再確認)。
  → **Linux CI 経由で実測し PASS** (下記「L3」)。
- **Done = L1∧L2∧L3 は 3 つとも PASS**。ただし Done は reproducibility のみを意味し、
  effect / aha / emergence は依然として非測定・非主張である。

## 実走環境 (封印前 pre-register 固定・実走後 tuning ゼロ、実走後に追記)

- **日時**: 2026-09-06 09:29:11〜09:30:40 JST (所要 89 秒、1 回のみ・再走なし)
- **platform**: capture = Windows 11 native (G-GEAR、`Windows-10-10.0.26200-SP0`、
  CPython 3.11.15、`PYTHONUTF8=1`)、cross-platform verify = Linux CI (glibc) + Windows (UCRT)
- **qwen3:8b digest**: `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`
  (実走直前に Ollama `/api/tags` で再確認。Phase 4b で pin したものと一致 = 同一 pull)
- **ollama version**: 0.32.12 / **think**: False (`ThinkOffChatClient` 経由、`cognition/cycle.py` 無改変)
- **embed model**: `nomic-embed-text` (768d、Ollama-local、
  digest `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`)
- **VRAM**: RTX 5060 Ti 16GB (実走中の実測 peak ≈ 8.5 GiB / GPU util 98%)
- **uv.lock sha256**: `9cc70f9dc5d61f6c74c08dee4dd73815993861022a80781a75ef5d873860c0f7`
  (harness が checkout の `uv.lock` から自動導出)
- **replay_checksum**: `43eb904d11046b940ff03558cb60b12764b2c49c43e2f06b03b66d35762888eb`
- **rehearsal replay_checksum**: `2ad3a39db14262a5c206f3d7930bd1f48bff59deb17f56d898c72d440aa48ecb`

## 事前登録 (sealed-run-before、`scripts/m13_live_loop_capture.py::LIVE_LOOP_OBSERVABLES` が SSOT)

- **Done = L1∧L2∧L3** (reproducibility のみ)。
  - **L1**: 32×20 tick を live qwen3:8b (think=False) + live nomic-embed-text に対して
    knob=on で完走 (exit 0)
  - **L2**: committed `decisions.jsonl` + `embedding_record.jsonl` の両 Plane 1 チャネルを、
    committed `inbound_perturbations.jsonl` から再構成した観測列で **無改変**
    `run_two_phase_capture` に replay → `replay_checksum` byte 一致・両 client
    `inner_invocations == 0`。加えて Plane L 再駆動 (`run_live_loop_capture`) が同一 checksum
  - **L3**: 同一 bundle が Windows (UCRT) / WSL Linux (glibc) で同一 artifact SHA-256
    (6 桁量子化が libm/backend drift を吸収、`feedback_golden_crossplatform_float_drift`)
- **annotation 2 種は非 gate** (side file、boolean/count のみ、Done 集合外、tune-to-pass 禁止):
  - `wiring_reachability.json` — correlation-id ごとの seam 到達性 boolean + 素の count。
    **到達性は因果ではない**。`firing_summary` / `same_tick_envelope_observed` の 2 seam は
    tick 単位の共起であって per-correlation の因果ではない (correlation-id は outbound
    wire protocol に到達しない、grill G2)
  - `two_phase_firing_annotation.json` — 本 run 自身の λ>0 tick における evaluation-phase 符号反転。
    **settle (no_eligible_tick、λ が 0 のまま) は正当な結果として正直に記録し、発火するまで再走しない**
- **verdict なし** (`verdict: null` を明示 emit)。

## 結果 (2026-09-06 sealed real run、実測・tuning ゼロ)

コマンドは `run.ps1` (= `--capture --real --confirm-spend`、32×20 tick) を **1 回のみ**。
再走・パラメータ変更・`--force` は一切していない。生 log はセッション local (untracked、
本 repo の experiments 慣習どおり非 commit) で、下表がその転記。**追試の一次資料は
committed bundle (`artifacts/`) + `repro.ps1 -Real` であって log ではない**。

### Done set (L1∧L2∧L3)

| 観測 | 判定 | 実測 |
|---|---|---|
| **L1** 完走 | **PASS** | exit 0、real qwen3:8b (think=False) + real nomic-embed-text で 32×20 tick 完走、6 artifact 出力、injected perturbations = 32、所要 89 秒 |
| **L2** 決定論 replay | **PASS** | Plane G checksum `43eb904d…2888eb` = manifest 一致 / 両チャネル `inner_invocations=0` / embedding 97/97 消費 / request conformance LLM 32/32・embedding 97/97 / 5 artifact SHA-256 全一致 / `manifest.json` 再 render byte 一致 / envelope 96 通 schema 準拠 / **Plane L 再駆動が Plane G と同一 checksum** |
| **L3** cross-platform | **PASS** | 本機 WSL に project venv が無く直接実測は不可 (再確認済) → **Linux CI (glibc) で committed real bundle を verify**。PR #91 CI run `34002303463` job `101403225525` (ubuntu、3648 passed / 50 skipped) で `test_m13_live_loop_capture.py` が **24/24 pass・skip 0**、すなわち `test_committed_sealed_real_bundle_verifies` / `test_committed_sealed_real_bundle_is_a_real_capture` が **skip されず実行されて緑**。UCRT で bake した bundle が glibc replay で同一 checksum・同一 SHA |

**L3 が測っているものの正確な範囲**: Windows (UCRT) で bake した bundle の committed bytes が、
Linux (glibc) 上の replay で同一 checksum / 同一 SHA になること。**Linux 上で capture を再 bake
したのではない** (real Ollama が CI に無いので原理的に不可)。6 桁量子化が libm drift を吸収する、
という既存の主張 (`feedback_golden_crossplatform_float_drift`) の real bundle での確認である。

### annotation (非 gate、side file、Done 集合外、verdict=None)

| 観測 | 実測 |
|---|---|
| `wiring_reachability.json` | `all_correlation_ids_reach_all_seams=True` (32/32 corr-id が 5 seam 全到達) / `no_double_send=True` / `target_agent_mismatch_count=0` / envelope kind 各 32 (`move`/`speech`/`animation`/`agent_update`/`reasoning_trace`) |
| `two_phase_firing_annotation.json` | `evaluation_phase_sign_inversion_fired=True` / eligible tick 29 / 符号反転 29 / `fail_mode=None` / `checksums_match=True` / `record_knob_on_pinned=True` |

**settle しなかった (= firing した)。** ただし **tick 0-2 の 3 tick は λ=0 で非 eligible**
(agent が locomotion で λ を earn するまでの settle 区間)、tick 3 以降 29 tick が eligible。
rehearsal では非 eligible が tick 0 の 1 つだけだったので、**real backend の方が settle が 2 tick 長い**。
これは配線の失敗ではなく、real LLM の行動列が scripted rehearsal と違うという当然の帰結である。

### 結果が主張できること / できないこと (不可侵)

- **言える**: "wiring reached each seam (live, real qwen3)" — 事前登録した bounded 摂動が
  perception → cognition → knob → movement → envelope の各 seam に real backend 越しに到達し、
  その run 全体が committed bytes から決定論的に再構成できた。
- **言えない**: aha / emergence / effect / caused / divergence / detectability。
  firing (符号反転が起きた) は **detectability ではない** — bias が zone / 行動 / aha を
  変えるかは凍結された第2リンクであり、本 run は測っていない。
  door② UNMET・計測ライン CLOSE・R-budget=0・holding は**すべて不変**。
- **境界の再掲**: ①real なのは cognition 面のみ (摂動は scripted 列を `InboundSink` 直投入、
  live Godot クライアント不使用) ②`ManualClock(start=0.0)` ゆえ wall-clock real-time セッションではない。

## apparatus 側で強制しているゲート (Codex independent review 反映、2026-09-04)

事前登録を「規約」でなく **apparatus が強制**する。詳細と採否は
`.steering/20260904-m13-live-loop-i7-real-run/decisions.md` / `codex-review.md` (verbatim)。

- **spend ratify**: `--confirm-spend` 無しの real は client 構築前に拒否。ゲートは
  `capture()` 自体に置いてあるので CLI を迂回した Python 直呼びも同様に拒否 (H-1)。
- **provenance pin**: digest / ollama version / VRAM が未指定なら real を拒否
  (監査不能な sealed artifact を作らない)。uv.lock の SHA は checkout から自動導出 (H-2)。
- **sealed bundle 上書き禁止**: real の出力先が非空なら spend 前に拒否。`--force` は
  明示 + 理由記録が前提 (settle を握り潰す tune-to-pass の経路を塞ぐ、H-3)。
- **事前登録パラメータ固定**: real は model / embed / seed / N / physics が
  pre-registration と一致しないと拒否 (observables の固定文言が嘘にならないように、M-2)。
- **annotation は検証対象**: committed side annotation は byte 比較し、drift なら fail。
  更新は `--update-annotations` を明示 (H-4)。
- **request conformance**: organ の replay client は ordinal (質問を照合しない) ので、
  verify 層で prompt / (kind, text) を committed record と照合する (H-5)。
  organ 自体への strict replay 導入は ADR §4 (organ 無改変) ゆえ defer (`blockers.md` B-1)。

## 決定論 (Codex MED-5 踏襲)

- 強く主張できるのは **committed 2 チャネル replay の determinism + byte parity** であって、
  real qwen3 record の環境差完全再現ではない (過剰主張しない)。
- replay は committed 応答/ベクトルを再 serve、checksum は幾何のみ → knob 活性化は新非決定源ゼロ。
- 非決定源の封鎖: LLM = `RecordReplayChatClient`、embedding = `EmbeddingRecordReplayClient`
  (record 時に 6 桁量子化)、clock = `ManualClock(start=0.0)`、inbound `sent_at` = record-mode clock に pin
  (in-process 合成ゆえ実 send 時刻は非決定ノイズにしかならない)。

## SEED

`SEED` ファイル参照 (= 0)。`--seed` で上書き可だが sealed run は 0 固定。

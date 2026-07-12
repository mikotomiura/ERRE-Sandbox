# grill-goals — M4 society run enrichment（construction、sealed real-LLM golden）

> grilling skill 実起動（2026-07-12、main checkout、タスクにつき 1 回）の出力。HOW は
> `.steering/20260712-m13-m4-society-enrichment/design-final.md`（= 本 dir `design-final-ref.md`）で
> §A-F + AC + 凍結定数まで FROZEN 済（Plan mode + reimagine 独立2案収束 + user 承認）。
> 本 grill は「凍結契約を実コードに落とす際に残る唯一の非 HOW 判断分岐 =
> **tick budget(12) vs think=False での zone-move 確率が Done/Stop をどう決めるか**」を閉じた。

## grill で閉じた唯一の判断分岐

**問**: horizon=12 の sealed run で 3 agent が 1 つも zone-move しなかったら Done か Stop か？

**答（FROZEN 設計が既に解決）**: **Done（honest single-zone = first-class pass）**。
- AC2 = 「複数 distinct zone 出現 **OR** honest single-zone 報告 + 機序診断」。zone-move が
  起きるか否かは **Done gate ではない**。distinct-zone は annotation（`O4_distinct_zones` count）で
  あって floor/verdict/divergence stat でない。→ loop は zone-move へ **toward-tune できない**
  （tune 対象の gate が存在しない）。
- 唯一の Stop は「動きを scripted で捏造する」こと（`plan.destination_zone` は cycle.py:1394 が
  読む唯一の駆動源、完全 LLM authored のまま）。single-agent 知見「think=False が load-bearing」ゆえ
  zone 停留は現実的シナリオであり、それを honest に報告するのが本タスクの成果。
- 従って zone-move 確率は Done/Stop の軸に **入れない**。sealed run の outcome は
  multi-zone でも single-zone でも valid landed golden。

## 検証可能ゴール（Done = 各 test が exit code 0 + pre-push 4 段 pass + WSL byte parity）

| AC | test / コマンド（Done 判定） | issue |
|---|---|---|
| **AC1 record→replay byte 一致** | `pytest tests/test_integration/test_m4_society_live.py -q`（`_ScriptedInner` mock で 3 agent を `run_society_loop` 実駆動、record→replay byte-parity + `inner_invocations==0`）+ import-lint AST assert（measurement denylist 非在） | I1 |
| **AC1/AC5 verify（Ollama-free）** | `python scripts/m4_society_live_capture.py --verify --artifact-dir tests/fixtures/m4_society_live_golden` exit 0（committed decisions.jsonl から per-agent 復元 replay、全 client `inner_invocations==0`、replay_checksum 一致、全成果物 SHA-256、manifest 自身の再 render byte 一致 = anti-vacuous-pass）。mock bundle で完全 pytest 化 | I2 |
| **AC2 viewer parametrize（回帰ゼロ→N=3）** | `pytest tests/test_integration/test_m4_society_replay.py -q`（`[m2(N=2), m4(N=3)]` parametrize、既存 m2 golden が新形で先に全緑 = 回帰ゼロ証明、次いで m4 golden。godot-gated、`GODOT_BIN` 必須） | I3 |
| **AC2/AC3 golden landed（sealed）** | `--capture`（G-GEAR real qwen3:8b）→ 4 成果物 + `expected_placement.jsonl` commit → `--verify` + parametrized godot test local 緑 → **multi-zone-or-honest-single-zone 報告** | I4（非 Loop, human-run） |
| **AC5 cross-platform closure** | WSL `--verify` byte 一致実測（Ollama-free）+ `pwsh scripts/dev/pre-push-check.ps1` 4 段（ruff format --check / ruff check / mypy src / pytest -q）全 pass | I5 |

## DAG

`{I1, I2, I3}` → **I4（sealed capture、非 Loop human-run）** → **I5（cross-platform closure）**

I1/I2/I3 は Ollama-free & TDD 可能 → worktree `/loop-issue`（並行可）。verify_level:
I1/I2/I3/I5=recheck（AC 直結・再現性契約）、I4=非 Loop（VRAM 依存・非再現・一発、ECL Issue 003 posture）。

## 不可侵（binding、全 issue 共通）

- **construction ≠ measurement**: verdict/scorer/floor/D_*/family/landscape/divergence 非計算・非 emit。
  R-budget=0。measurement line CLOSE 済で再入しない。§D0.2 非反射条項遵守。
  fp/placement/checksum は再現性 witness で metric でない。observables は凍結 annotation 文字列。
- **scripted で zone 移動を捏造しない**: `plan.destination_zone` 完全 LLM authored。
  legitimate nudge のみ（初期 zone 分散 / per-agent observation_factories / persona 事前分布 / horizon=12）。
- **read-only 無改変**: society.py / handoff.py / EclReplayPlayer.gd / MainScene.tscn /
  既存 m2_society_golden / 凍結 evidence。編集は新 3 ファイル + 新 fixture dir +
  `SocietyReplayScene.tscn` に Avatar2 を 1 ノード append + `test_m4_society_replay.py` を parametrize のみ。
- **GPL 分離**: bpy 不使用、Godot は GDScript、src/ に import bpy 禁止。
- **凍結定数（tune-to-pass 封鎖、sealed run 後の変更は Stop）**: `SOCIETY_LIVE_N_COGNITION_TICKS=12` /
  seed=0 / 3 agent(kant/nietzsche/rikyu) / 初期 zone=study/peripatos/chashitsu /
  run_id="m4-society-live-golden" / think=False / model=qwen3:8b。
- HOW を越える判断が出たら Stop → superseding ADR。

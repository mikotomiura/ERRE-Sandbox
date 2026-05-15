### 5.1 Executive verdict

**ADOPT-WITH-CHANGES**

4 commits の方向性は妥当。ただし push 前に少なくとも **HIGH-1 (`recv_envelope`)** と **HIGH-3 (`--memory-db` default path symlink)** は直すべきです。どちらも局所修正 + regression test で閉じられるので、設計や commit 構造の作り直しは不要です。

---

## HIGH-1: `recv_envelope()` が heartbeat を silent-drop する

Verdict: **MODIFY**  
Severity: **HIGH**  
File: [tick.py](</Users/johnd/ERRE-Sand Box/src/erre_sandbox/world/tick.py:719>)

要旨:  
`asyncio.wait(FIRST_COMPLETED)` で両 queue の `get()` task が同時に done になると、main を返す一方で heartbeat 側の result は捨てられます。これは “main 優先” ではなく “heartbeat を consume して drop” です。`except BaseException` でも cancel 後に await していないため、loop close timing で pending task warning の余地があります。

証拠:
```text
got error main 1
rest []
```
上は heartbeat queue に 1 件、main queue に `ErrorMsg` 1 件を入れて `recv_envelope()` した結果。heartbeat は `drain_envelopes()` に残りませんでした。CPython 3.11 `asyncio.Queue.get()` は cancel 時に getter を cleanup しますが、task が既に done なら item は `get_nowait()` 済みです。Project は `requires-python = ">=3.11,<3.12"`。

推奨対応:
- `except BaseException` で cancel した task を `await asyncio.gather(..., return_exceptions=True)` する。
- both-done / cancel-race で heartbeat result を捨てない。main を返す場合も heartbeat result は heartbeat queue に coalesce requeue する、または明示的に “main 優先時は heartbeat drop” として test + doc に固定する。後者は liveness signal として弱いので前者推奨。
- regression test: `heartbeat queued + main queued -> recv returns main, heartbeat remains observable or documented dropped`.

---

## HIGH-2: `recv_envelope` と `drain_envelopes` の優先順が逆

Verdict: **MODIFY**  
Severity: **MEDIUM**  
File: [tick.py](</Users/johnd/ERRE-Sand Box/src/erre_sandbox/world/tick.py:753>), [test_tick.py](</Users/johnd/ERRE-Sand Box/tests/test_world/test_tick.py:463>)

要旨:  
`recv_envelope()` は main 優先、`drain_envelopes()` は heartbeat 優先です。API 用途が違うなら成立しますが、現状は同じ runtime を別 consumer が読むと観測順序が変わります。加えて heartbeat count は queue 経由では観測不能になりました。

証拠:
- `recv_envelope()` docstring: main queue prioritized over heartbeat.
- `drain_envelopes()` docstring: heartbeat queue first.
- `test_heartbeat_emits_world_tick_msgs_periodically` は `5` から `1` に変更。

推奨対応:
- HIGH-1 修正とセットで `recv_envelope` の mixed-ready test を追加。
- docstring に “streaming consumer は main priority / debug drain は heartbeat-first snapshot” と明記。
- heartbeat 発火回数が今後必要なら queue ではなく counter / metric / event log を別途追加。

---

## HIGH-3: default `/tmp/p3a_natural_*` branch が broken symlink を見逃す

Verdict: **MODIFY**  
Severity: **HIGH**  
File: [eval_run_golden.py](</Users/johnd/ERRE-Sand Box/src/erre_sandbox/cli/eval_run_golden.py:783>)

要旨:  
ADR は `os.path.lexists()` で symlink early detection としているが、実装は default branch で `Path.exists()` のみです。broken symlink は `exists() == False` なので helper が「存在しない」と誤判定し、symlink path を返します。

証拠:
```text
result /tmp/p3a_natural_codex-broken-symlink-check_run0.sqlite
Path.exists False
os.path.lexists True
is_symlink True
```

推奨対応:
```python
import os

if path is None:
    default = Path(f"/tmp/p3a_natural_{persona}_run{run_idx}.sqlite")
    if os.path.lexists(default):
        if default.is_symlink():
            raise argparse.ArgumentTypeError(...)
        default.unlink()
    return default
```
explicit path 側も `path.exists()` ではなく `os.path.lexists(path)` で existing gate を見る regression test を追加してください。

---

## HIGH-4: `web_search=live` / `network_access=false` split は有効だが恒久保証ではない

Verdict: **ADOPT**  
Severity: **MEDIUM**  
File: [.codex/config.toml](</Users/johnd/ERRE-Sand Box/.codex/config.toml:4>)

要旨:  
split は defense-in-depth として有効です。Codex docs/schema 上も `web_search` と network/sandbox settings は別 config surface です。ただし “恒久的に保証” とは言えません。Codex App/CLI 差分の既知 issue もあります。

証拠:
- config は `web_search = "live"` と `[sandbox_workspace_write] network_access = false`。
- Codex config reference は `web_search` mode と network permissions を別項目として記載。
- Codex sandbox docs は command sandbox の network restriction を説明。
- openai/codex issue #13373 は App と CLI の network behavior 差分を報告。

推奨対応:
PR description では “current Codex CLI/docs に基づく split” と書く。`web_search` で取得した内容を Codex が local file に書くこと自体は `network_access=false` では止まりません。止めているのは shell command など workspace sandbox 内の任意 egress です。

---

## HIGH-5: P4/P5 defer と “complete hardening” の scope がずれている

Verdict: **MODIFY**  
Severity: **HIGH**  
File: [tasklist.md](</Users/johnd/ERRE-Sand Box/.steering/20260513-security-hardening-pre-m10/tasklist.md:39>), [requirement.md](</Users/johnd/ERRE-Sand Box/.steering/20260513-security-hardening-pre-m10/requirement.md:40>)

要旨:  
この 4 commits は SH-3/4/5 と scaffold であり、元 finding の HIGH §1 hook bypass と MEDIUM §2 WS auth は未実装です。したがって “M10 前 hardening 完了” として push/PR するのは不正確です。

証拠:
- P4/P5 は tasklist 上未完了。
- `requirement.md` acceptance は §1/§2 も含む。
- `design-final.md` は `design.md` と byte-identical (`cmp_exit=0`) で、final artifact として更新されていません。
- P3 tasklist も commit 済みに対して未チェックのまま。

推奨対応:
- PR title/scope を “P0-P3 partial hardening” にするか、P4/P5 をこの branch で続ける。
- P3 tasklist を完了に更新。
- `design-final.md` を実装済み P0-P3 / deferred P4-P5 が分かる final artifact に更新。
- `blockers.md` に P4/P5 defer 理由と M10-0 go/no-go 条件を書く。

---

## MEDIUM: test coverage gaps

Verdict: **MODIFY**  
Severity: **MEDIUM**

P2 tests は symlink / prefix / exists / overwrite / default auto-unlink を押さえていますが、broken symlink default branch、explicit broken symlink、TOCTOU は未網羅です。P3 tests は overflow happy path と heartbeat coalesce のみで、`maxsize-1/maxsize/maxsize+1`、mixed ready `recv_envelope`、cancel path、repeated overflow count を未検証です。

---

## MEDIUM: overflow observability is only in-band

Verdict: **MODIFY**  
Severity: **MEDIUM**  
File: [tick.py](</Users/johnd/ERRE-Sand Box/src/erre_sandbox/world/tick.py:770>)

`runtime_backlog_overflow` は ErrorMsg として enqueue されますが、consumer が詰まっているから overflow しているので、in-band warning だけでは SRE 観測として弱いです。`logger.warning(...)` も出す方がよいです。warning envelope は維持でよいです。

---

## LOW: naming / typing / commit message

Verdict: **ADOPT**  
Severity: **LOW**

Commit messages は Conventional Commits と整合。`_envelopes` vs `_heartbeat_envelopes` は今は許容。将来 N-queue 化するなら `_main_envelopes` へ rename が自然です。`ControlEnvelope` 戻り値 union typing は mypy clean でした。

---

### 5.3 META

**META-1**  
P4/P5 を defer したまま **M10-0 に進む判断は不可**。特に SH-1 は元 HIGH で、未対応のまま “pre-M10 hardening complete” とは言えません。一方、今回の 4 commits を “P0-P3 partial hardening PR” として push/PR 化する判断は、HIGH-1/HIGH-3 修正後なら妥当です。

**META-2**  
prompt の情報量は十分でした。追加で読むべきだったものは実際に読んだ `pyproject.toml`, CPython `asyncio/queues.py`, Codex config/sandbox docs, `.codex/config.toml`, `.steering/*`, runtime/CLI/tests/reference gateway です。

**META-3**  
`next-session-prompt.md` は HEAD/P2 前提で stale です。現在 HEAD は `9061173` で P3 済みですが、prompt は `2440b0b` P2 前提の P3 実装指示です。未tracked なので commit には入っていませんが、次セッション起点としては更新必須です。

---

### 5.4 fact-check sheet

```text
git log main..HEAD --oneline
9061173 feat(world): bounded envelope queue + warning (SH-5)
609037c feat(cli): eval --memory-db symlink+prefix+overwrite guard (SH-4)
ad00499 chore(codex): network_access=false split (SH-3)
f5295b5 docs(security): security-hardening-pre-m10 P0 scaffold (SH-0〜SH-5 ADR)
```

```text
git diff main..HEAD --stat
16 files changed, 1397 insertions(+), 31 deletions(-)
```

```text
git diff main..HEAD -- data/eval/golden
<empty>

git diff main..HEAD -- src/erre_sandbox/evidence
<empty>
```

```text
git ls-tree -r --name-only HEAD data/eval/golden | rg '_run[0-4]\.duckdb\.capture\.json$' | wc -l
30
```

```text
rg -n "SCHEMA_VERSION|class ErrorMsg|kind: Literal\[\"error\"\]|code: str|detail: str" src/erre_sandbox/schemas.py
44:SCHEMA_VERSION: Final[str] = "0.10.0-m7h"
1126:class ErrorMsg(_EnvelopeBase):
1129:    kind: Literal["error"] = "error"
1130:    code: str
1131:    detail: str
```

```text
git diff main..HEAD -- src/erre_sandbox/schemas.py
<empty>
```

```text
rg world->integration / banned imports
world->integration refs
schemas src imports
banned imports in src
<all empty>
```

```text
.venv/bin/ruff check src tests
All checks passed!

.venv/bin/ruff format --check src tests
216 files already formatted

.venv/bin/mypy src
Success: no issues found in 82 source files

.venv/bin/pytest -q -m "not godot and not eval and not spike and not training and not inference"
1378 passed, 32 skipped, 52 deselected, 3 warnings in 4.05s
```

```text
git status --short
?? .steering/20260513-security-hardening-pre-m10/codex-review-prompt.md
?? .steering/20260513-security-hardening-pre-m10/codex-review.md
?? .steering/20260513-security-hardening-pre-m10/codex-review.stderr
?? .steering/20260513-security-hardening-pre-m10/next-session-prompt.md
?? data/eval/golden/_checksums_mac_received.txt
?? idea_judgement.md
?? idea_judgement_2.md
```

Sources used: [CPython 3.11 asyncio queues.py](https://github.com/python/cpython/blob/3.11/Lib/asyncio/queues.py), [Codex config reference](https://www.mintlify.com/openai/codex/configuration/reference), [Codex sandboxing docs](https://www.mintlify.com/openai/codex/architecture/sandboxing), [openai/codex issue #13373](https://github.com/openai/codex/issues/13373).

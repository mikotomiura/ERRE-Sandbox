# 設計案比較 — m2-functional-closure

`/reimagine` 適用。v1 (初回案) と v2 (再生成案) の比較。

## v1 (初回案) の要旨

新規コード `__main__.py` 1 ファイルのみ。`WorldRuntime` constructor に memory /
inference / cognition を注入し、既存 `gateway._main()` 同様に `uvicorn.run()` で
起動。`try/finally` と task cancel で lifecycle 管理。Persona YAML は main が
直接読む。**最小変更で MVP 完了** することに最適化した素直な案。

## v2 (再生成案) の要旨

Composition root を `bootstrap.py` に切り出し、`__main__.py` は argparse CLI shell
に徹する。`AsyncExitStack` でリソース登録、`asyncio.TaskGroup` で runtime と
uvicorn を対等 supervise、SIGINT/SIGTERM を明示ハンドル。`BootConfig` dataclass と
`load_persona()` pure fn でユニットテスト容易化。**Lifecycle の厳密性と将来拡張
容易性** に最適化した層分け案。

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| 新規ファイル数 | 1 (`__main__.py`) | 4 (`__main__.py`, `bootstrap.py`, `config.py`, `personas/_loader.py`) |
| 新規総行数 | ~50 | ~130 (config/loader 含む) |
| Composition root 位置 | `__main__.py::amain()` 関数内 | `bootstrap.py::bootstrap()` 関数 (`__main__.py` は 20 行の CLI shell) |
| Lifecycle 管理 | `try/finally` 手書き + `task.cancel()` | `AsyncExitStack.push_async_callback()` + `TaskGroup` + signal handler |
| 設定 | コード内定数 / argparse なし | `@dataclass(frozen=True) BootConfig` + argparse CLI |
| Persona 読込 | main 内で `yaml.safe_load()` | `personas/_loader.py::load_persona(slug)` (pure fn) |
| Shutdown 契機 | Ctrl+C → KeyboardInterrupt → finally | SIGINT/SIGTERM → `asyncio.Event` → graceful |
| Supervision | 並行 Task 手動 create + finally cancel | `asyncio.TaskGroup` で対等監視 (片方死亡 → 両方終了) |
| Unit test 可能性 | `amain()` 丸ごと mock が必要 → 実質 e2e のみ | `bootstrap(cfg)` 単体テスト可能 / `load_persona()` 個別テスト可能 |
| M4 拡張時のコード変更 | `__main__.py` 肥大化 (multi-persona YAML, multi-agent register) | `bootstrap.py` の register_agent ループ化のみ、CLI 無変更 |
| 依存 | Python 3.11 (既存と同等) | Python 3.11 必須 (TaskGroup) |
| レビュー負荷 | 小 (1 ファイル診ればよい) | 中 (4 ファイル横断) |

## 評価 (各案の長所・短所)

### v1 の長所
1. **最小変更**: PR 量が小さく、レビュー・リスクともに低い
2. **MVP 定義との一対一対応**: 1 ファイル追加 = MVP 完了、記述がそのまま
3. **学習コスト低**: 既存 `_main()` と対称でプロジェクト既存パターンと揃う

### v1 の短所
1. **Lifecycle の脆弱性**: `try/finally` 階層化は例外経路で抜け落ちやすい
   (`inference` 生成後に `WorldRuntime` 組立で例外 → `inference.close()` 未呼出リスク)
2. **Silent failure**: `runtime_task.cancel()` だけだと runtime が raise した時に
   uvicorn が keep running してしまう (ゴースト gateway)
3. **Unit test 困難**: `amain()` 全体が 1 コルーチンなので分割テストしづらく、
   事実上 e2e のみの validation
4. **M4 拡張で破綻しやすい**: multi-persona / multi-agent 対応時に `amain()` が
   肥大化、リファクタが必要になる

### v2 の長所
1. **構造的 lifecycle safety**: AsyncExitStack により resource leak を構造で防止
2. **対等 supervision**: TaskGroup で runtime 死亡 → uvicorn も即死、silent failure を排除
3. **Signal-aware shutdown**: SIGTERM で graceful、Docker/systemd 運用 ready
4. **Testability**: `bootstrap(cfg)`・`load_persona()`・`BootConfig.from_env()` が
   個別にユニットテスト可能 — v1 では e2e に頼るしかない挙動を pytest で捕らえられる
5. **M4 拡張時 untouchable**: `__main__.py` / `config.py` を変更せず `bootstrap.py`
   の register_agent ループ化だけで 3-agent 化できる
6. **オペレータ視点**: CLI help が出る (`--help`)、`--skip-health-check` で CI 運用可

### v2 の短所
1. **ファイル数増**: 4 ファイル新設。レビュー対象が散る
2. **YAGNI リスク**: MVP 完了という **1-Kant-walker 限定** の要件に対して、
   config dataclass / loader 分離は **過剰設計の可能性**
3. **M4 期待値を先取り**: 本タスク時点では 1 agent しかないので TaskGroup /
   AsyncExitStack の真価は試されない (benefit が見えにくい)
4. **既存パターン逸脱**: プロジェクト内に AsyncExitStack の前例なし、
   readability が初めて触る人には一段難しい

## リスクマトリクス

| リスク | v1 | v2 |
|---|---|---|
| MVP 完了までの時間 | 小 (0.5d 実装 + 0.5d e2e) | 中 (1d 実装 + 0.5d テスト + 0.5d e2e) |
| 実装時の未知バグ | 中 (lifecycle 手書き) | 小 (構造的 safety) |
| M4 移行時の負債 | 中 (リファクタ必要) | 小 (ほぼ変更なし) |
| 既存レビュワー学習コスト | 小 | 中 |
| Docker/systemd 運用時の挙動 | 中 (SIGTERM 非対応) | 小 (対応済) |
| テストカバレッジ | 低 (e2e 依存) | 中 (unit 可能) |

## 推奨案

**ハイブリッド (v2 ベース + v1 の "最小変更" 精神を部分採用)**

### 採用要素

| 要素 | 採択 | 根拠 |
|---|---|---|
| `bootstrap.py` 分離 | v2 採択 | 最大の価値。unit test 可能化 + M4 拡張容易性 |
| `AsyncExitStack` | v2 採択 | lifecycle safety は MVP でも享受できる |
| `asyncio.TaskGroup` supervision | v2 採択 | silent failure 排除。T19 で silent failure 調査に苦しんだ反省 |
| SIGINT/SIGTERM handler | v2 採択 | low cost / high value |
| `@dataclass BootConfig` + `from_env()` | **中間**: BootConfig dataclass は採用、ただし argparse は最小限 (host/port/db のみ) | MVP では環境変数ベースで十分、argparse は YAGNI 寄り |
| `personas/_loader.py` 分離 | **v1 寄せ**: 独立 module にせず `bootstrap.py` 内の関数 `_load_kant_persona()` として置く | 1 persona しかない MVP で新規 module は過剰 |

### 最終モジュール構成

```
src/erre_sandbox/
├─ __main__.py      # 新規: ~15-20 行 (argparse + asyncio.run(bootstrap(cfg)))
├─ bootstrap.py     # 新規: ~80 行
│                   #   ├─ BootConfig (inline dataclass, frozen)
│                   #   ├─ _load_kant_persona() (内部 pure fn)
│                   #   ├─ _build_kant_agent_state() (内部 pure fn)
│                   #   └─ bootstrap(cfg)  ← async composition root
```

**新規ファイル数: 2** (v1: 1, v2: 4 の中間)。
**新規行数: ~100** (v1: 50, v2: 130 の中間)。
**Unit test**: `bootstrap(cfg)` と 2 つの pure fn を個別にテスト可。

### 根拠

v1 の「最小変更で MVP 完了」は bragging right としては魅力的だが、T19 で経験した
silent failure (gateway ghost session) と同種の問題を lifecycle 手書きで再発し
やすい。v2 の構造的 safety は MVP でも価値あり。一方で、v2 の `config.py` +
`personas/_loader.py` は 1-Kant-walker の MVP には過剰であり、YAGNI 違反。

ハイブリッドは **lifecycle safety (v2)** と **ファイル数最小 (v1)** を両立し、
M4 拡張時の追加コスト (config.py / _loader.py の切り出し) も低い。

## 設計判断の履歴

- 初回案 (v1, `design-v1.md`) と再生成案 (v2, `design.md` §1) を比較
- **推奨採用: ハイブリッド** (v2 ベース + persona/config を bootstrap.py 内にインライン化)
- 根拠: T19 の silent failure 教訓を MVP 段階で取り込むメリットが大きく、かつ
  MVP 固有の YAGNI リスクを v1 の "ファイル数最小" 精神で抑える
- ユーザーの最終判断を仰ぐ

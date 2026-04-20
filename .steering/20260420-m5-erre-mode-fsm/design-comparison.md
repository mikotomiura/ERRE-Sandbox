# 設計案比較 — m5-erre-mode-fsm

## v1 (初回案) の要旨

`DefaultERREModePolicy` クラスの `next_mode` 内に 5 段階の **priority-ordered
ruleset** を if 文で並べる。各 rule は `reversed(observations)` で最後に該当する
Observation を探し、最初にマッチしたものを採用。優先順位:
`external > shuhari > fatigue > zone > hold`。`ZONE_TO_DEFAULT_ERRE_MODE` は
モジュール定数として直接参照。同一 mode への遷移は各 rule 内で個別にチェック。

## v2 (再生成案) の要旨

"時系列 event-driven reduction" として定式化。observation を **順方向 single
pass** で走査、`match/case` で dispatch、純関数 handler が候補 mode を返す。
最後に確定した候補を accumulated 値として採用 (**latest signal wins**)。
`ZONE_TO_DEFAULT_ERRE_MODE` は **dataclass field で DI**。末尾で 1 度だけ
`current` と比較して `None` or 新 mode を返す。

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| **決定モデル** | 固定 priority (external > shuhari > fatigue > zone) | 時系列順 (latest wins) |
| **走査方向** | rule 毎に `reversed(observations)` で後から前へ (O(n × rules)) | 順方向 single pass (O(n)) |
| **dispatch** | if-isinstance chain で各 rule 毎に分岐 | `match/case` で Observation 型別に unified |
| **handler** | `next_mode` 内インライン | module-level 純関数 × 3 (zone / internal / mode_shift) |
| **ZONE map の可差替性** | 固定 (module const を直参照) | dataclass field で DI 可能 |
| **ERREModeShiftEvent(reason)** | `"external"` のみ扱い、他は未実装 | 4 reason 全てを明示的に扱う (external は no-op、他は ev.current を尊重) |
| **idempotency check** | 各 rule 内で current 比較 (重複) | 末尾 1 回だけ wrap |
| **テスト surface** | FSM 単位の組合せ test | handler 単体 (pure) + FSM 統合 の 2 層 |
| **新 Observation 対応** | priority list を手で延長 | match ブランチを 1 個足すだけ |
| **コード行数 (概算)** | 60-70 行 (single class with long method) | 110-130 行 (handlers + dataclass) |
| **Python 新機能の使用** | `reversed()` + `isinstance` | `match/case` (py3.10+) + `@dataclass(frozen=True)` |

## 評価 (各案の長所・短所)

### v1 の長所
- single class / single method で構造が局所的。「この 60 行を読めば FSM が分かる」
  という可読性
- 各 rule の priority が if 順序で明示され、仕様書と 1:1 対応させやすい
- 既存の `_ZONE_TO_DEFAULT_ERRE_MODE` と似た直感 (module const、直参照)
- match/case 非使用で、py3.10 非対応の環境でも動く (本 repo では関係ないが保守的)

### v1 の短所
- priority ordering を "仕様" として固定。呼び出し側が chronological な意図を
  持っても FSM が上書きする
- 各 rule が観察を独立スキャンするので O(n × rules) で非効率
  (n × 4 = n×4 回のループ。実用上問題ないが構造的に冗長)
- 同一 mode への遷移チェックが rule ごとに散らばる (boilerplate)
- 新しい Observation 種別を足す際は priority list に差し込む位置を決める
  必要があり、仕様議論を伴う
- `ERREModeShiftEvent` の `reason` が `"external"` 以外で未定義な振る舞い
- handler を個別 test できない (FSM 経由でしか実行経路がない)

### v2 の長所
- **latest signal wins** は caller-side の chronological ordering を尊重する
  semantics で、"fatigue を感じた後に peripatos に入る" が "peripatetic" を選ぶ
  という直感的動作に合致 (v1 だと fatigue が常に勝つ)
- Observation 1 個あたり 1 回の match → single pass O(n)
- handler が module-level 純関数なので単体テストが 3 倍速い (parametrize しやすい)
- `match/case` は Observation discriminated union との親和性が高く、将来
  `PerceptionEvent` 等で mode に影響を与える signal が増えても一行追加で済む
- `ZONE_TO_DEFAULT_ERRE_MODE` の DI は、feature flag
  (`--disable-erre-fsm` で "zone map だけ live 化" モード) などに拡張しやすい
- `ERREModeShiftEvent` の `reason` を 4 種全て明示的にハンドル

### v2 の短所
- 行数が 2 倍弱。"1 画面で読める" 性は v1 に劣る
- `@dataclass(frozen=True)` の採用は repo 内の precedent を要確認。1 件目なら
  decisions.md にポリシーとして記録する必要
- `match/case` の使用も同様 (py3.11 最小要件は満たす)
- "latest wins" は直感的だが、caller が observation を chronological に並べない
  と破綻する。この不変条件を docstring で明示する必要
- DI 可能にしたことで、test が DI するか module const に依存するかで二択を
  迫られる (判断基準を明記しないと散らかる)

## 推奨案

**v2 (再生成案) を採用**

### 理由

1. **Protocol の署名と最も整合**: `ERREModeTransitionPolicy.next_mode` は
   `observations: Sequence[Observation]` を取るので、chronological に扱うのが
   シグネチャの意図に合う。v1 は "list の中から priority で 1 件選ぶ" 設計で、
   Sequence のセマンティクスを活用していない。
2. **handler 単体テストの価値が大きい**: `_on_internal` の prefix parsing は
   `InternalEvent` content のバリエーション (fatigue/shuhari_promote/未知 prefix)
   が多く、FSM 経由だと test fixture が重くなる。純関数なら parametrize で
   簡潔に書ける。
3. **DI の将来価値**: `m5-orchestrator-integration` で feature flag を入れる際、
   zone_defaults を差替える代案 (`--erre-zone-map` など) が残せる。v1 の
   module const 直参照だと flag 追加時に再設計が必要。
4. **`latest wins` の方が caller 側に優しい**: world/tick.py が observation を
   tick 順に並べれば "直前の signal で遷移" という直感に一致。v1 の固定 priority
   は caller が priority を逆転させたくても FSM 側を書き換えるしかなく、
   `m5-orchestrator-integration` で変更しにくい。
5. **ERREModeShiftEvent の 4 reason 全対応**: v1 は `external` だけで、他 reason
   (scheduled / zone / fatigue / reflection) の挙動が未定義。v2 は明示的に
   `ev.current` を受け入れるので、後続 sub-task が自由に emit できる。
6. **`match/case` は py3.11 (pyproject target) で正規に使える**: 使用すべき場面で
   避ける理由がない。Observation union との相性も良い。

### v2 採用後の留意事項 (decisions.md に記録予定)

- `@dataclass(frozen=True)` と `match/case` を repo に初導入する場合は、
  python-standards への言及と合わせて decisions.md で judgement として明記する
- "latest signal wins" の不変条件を `DefaultERREModePolicy.next_mode` docstring に
  明示する (observation は chronological 前提)
- `DI vs module const` のデフォルト方針 (= "引数に渡さなければ module const の
  コピーを使う") を docstring に明記

# 設計案比較 — m4-gateway-multi-agent-stream

## v1 (broadcast + capability 拡張のみ) の要旨

既存 `Registry.fan_out` の全 session 全 envelope broadcast を維持し、
`_SERVER_CAPABILITIES` に dialog_* 3 kinds を追加するだけ。
クライアント (Godot) が agent_id で dispatch 済なので routing は不要という立場。

## v2 (URL query param + server-side filter) の要旨

`/ws/observe?subscribe=kant,nietzsche` の query param で購読を表明。
server 側 `Registry.fan_out` が envelope の agent_id と突合して絞り込む。
schema 変更なし。未指定は broadcast (後方互換)。routing table を
`_envelope_target_agents(env)` で明示管理。

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| planning 検収「per-agent に分離」 | ❌ 満たせない | ✅ 満たす |
| schema 変更 | なし | なし (URL query param) |
| back-compat | 100% | 100% (未指定 = broadcast) |
| 実装量 | 1 行 + fixture 微調整 | ~80 行 (Registry 拡張、helper、parse) |
| テスト量 | 3 件 | 10 件 |
| 帯域効率 (N 客×M envelope) | O(N×M) 常時 | O(subscribe 幅) に絞れる |
| debug monitor 実装容易性 | 不可 (client filter) | 容易 (`?subscribe=kant`) |
| dialog_turn routing | broadcast (関与外も受信) | 関与 agent のみ |
| `_envelope_target_agents` helper | 不要 | 新規必要 (単体テスト可) |
| Godot クライアント変更 | 不要 | 不要 (URL に param 無くても broadcast) |

## 評価

### v1 の長所
- 実装が最小 (1 行変更 + 3 fixture bump)
- 既存 Registry の back-pressure / oldest-drop を一切触らない
- debug cycle が最小

### v1 の短所
- planning 検収条件 (broadcast が per-agent に分離して届く) を満たせない —
  これは致命的
- dialog_turn が関与外 agent の viewer にも届く = "最小権限" 原則違反
- future debug monitor (特定 agent のみ watch する UI) が不可能
- N agent × M viewer 爆発の回避策がない

### v2 の長所
- planning 検収条件を満たす
- URL query param なので HandshakeMsg 変更不要 = schema 凍結維持
- `?subscribe=` 未指定で既存 broadcast を維持 = back-compat 完全
- `_envelope_target_agents` が単体テスト可能な pure function
- debug monitor UI が自然に書ける (`?subscribe=kant` だけで動く)
- dialog envelope を参加者にだけ届ける = "最小知識" 原則

### v2 の短所
- 実装・テスト量が v1 の 10 倍強
- `Registry` の internal API 拡張 (`subscribed_agents: frozenset[str] | None`)
- dialog_close の participant 追跡をしない設計判断 (broadcast) で
  「なぜここだけ broadcast か」の explicit documentation が必要
  → decisions.md に明示して対応

## 推奨案

**v2 (URL query param + server-side filter) を採用**

### 理由

1. **planning 検収適合性**: 「broadcast が per-agent に分離して届く」
   検収条件は v1 では物理的に満たせない。v2 で初めて pass

2. **Contract-First との整合**: schema を触らず URL layer だけで
   subscription を表現 = foundation の凍結方針を守れる

3. **後方互換 100%**: 未指定 = broadcast なので既存 Godot / curl / test
   すべて無変更で動く

4. **future-proof**: debug monitor / 選択的 log streaming / per-agent
   replay など、"特定 agent を watch する" 系の UI を書くとき自然

5. **routing table の明示化**: `_envelope_target_agents` で各 envelope の
   routing 対象を pure function として単体テストできる。未来の M5+ で
   dialog scheduler が dialog_close に participants を載せたくなったとき、
   拡張点が明確

6. **security**: dialog_turn を unrelated agent の viewer に配布しないのは
   現状は LAN-only で無害だが、将来 WAN 公開や multi-user 運用で
   "最小知識原則" を崩す技術的負債にならない

### 採用判断

本タスクは memory `feedback_reimagine_trigger.md` に従い /reimagine を適用。
v1 vs v2 の 10 観点比較の結果、**v2 (URL query param + server-side filter)**
を採用する。詳細は `decisions.md` に記録。

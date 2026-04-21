# m5-godot-schema-version-bump — Godot WS client schema bump 0.2.0-m4 → 0.3.0-m5

## 背景

2026-04-21 の M5 live acceptance (PR #64) 実行中、MacBook から G-GEAR への
Godot WebSocket 接続が handshake 直後に close (code=1000) するループ現象を観測。

根本原因は `godot_project/scripts/WebSocketClient.gd:28` の
`CLIENT_SCHEMA_VERSION` が `"0.2.0-m4"` のまま残っていたこと。サーバー側は PR #56
`m5-contracts-freeze` で `SCHEMA_VERSION` を `"0.3.0-m5"` に bump 済で、
`integration/gateway.py:543-552` が client の schema_version を照合して
一致しないと `ErrorMsg code="schema_mismatch"` を送って close する契約。

PR #59 `m5-godot-zone-visuals` は Chashitsu / Zazen zone scene + dialog bubble +
mode tint を追加したが、WebSocket wire contract は触らなかった。PR #62
`m5-orchestrator-integration` も Godot 側には触れていない。結果、**Godot 側の
schema_version 更新だけが M5 Phase 2 で漏れていた**。

本 task は `.steering/20260421-m5-acceptance-live/acceptance.md` §Live
acceptance #5, #6 の blocker を解除する 1 行 fix。

## ゴール

`CLIENT_SCHEMA_VERSION` を `"0.3.0-m5"` に更新し、Godot WS client がサーバーと
正常に handshake を完了できるようにする。M5 live acceptance #5 (dialog bubble) /
#6 (ERRE mode tint) の録画収集が可能な状態に戻す。

## スコープ

### 含むもの

- `godot_project/scripts/WebSocketClient.gd:28` の 1 文字列更新
- 本 steering (requirement のみ、設計判断なし)

### 含まないもの

- `.steering/20260421-m5-acceptance-live/` への影響 (当該タスクで follow-up)
- M5 live acceptance 全体のワークフロー (PR #64 側で継続)
- `v0.3.0-m5` タグ付与 (user 確認後の別作業)
- 他の Godot 側 M5 追加機能 (既に PR #59 で完了済)

## 受け入れ条件

- [x] `WebSocketClient.gd` の `CLIENT_SCHEMA_VERSION` が `"0.3.0-m5"` になっている
- [x] Godot 側のテストやフィクスチャが bump 後でも通る
      (`tests/test_godot_*` / `fixtures/control_envelope/handshake.json`)
- [x] Python 側のテスト・lint・型は無変更 (触っていないので回帰ゼロ)
- [ ] PR merge 後、MacBook で Godot を再起動すると WS handshake が完了し
      `tick=N agents=3 clock=...` ラベル更新が観測できる (live 検証、user 作業)

## 関連ドキュメント

- `.steering/20260421-m5-acceptance-live/acceptance.md` §MacBook 側 2 項目 (#5, #6)
- `src/erre_sandbox/schemas.py` §1 `SCHEMA_VERSION` (= "0.3.0-m5")
- `src/erre_sandbox/integration/gateway.py` line 543 (schema_version 照合)
- PR #56 `m5-contracts-freeze` — schema bump コミット (Godot 側は射程外だった)
- PR #59 `m5-godot-zone-visuals` — Godot 側 M5 作業だが WS 契約は触らず

## 運用メモ

- タスク種別: **バグ修正** (/fix-bug に該当するが、1 行で reproducer まで明確なので
  軽量運用)
- 破壊と構築 (`/reimagine`) 適用: **No** (自明な 1 行修正)
- `/fix-bug` の TDD 原則 (回帰テスト先行) は、本件のような「バージョン文字列の
  人的書き漏れ」には過剰。Godot 側のフィクスチャ (`handshake.json`) が既に
  0.3.0-m5 で freeze 済のため、fixture drift テスト (あれば) が自動で catch する
- Acceptance task (`.steering/20260421-m5-acceptance-live/`) との関係:
  - 本 fix を merge してから user が Godot を再起動して #5, #6 録画
  - 収集した録画は acceptance task の follow-up commit で PR #64 に追加
- 発見経緯: PR #64 open 後の live 再実行でのみ発現するため、merge 前に
  catch する仕組みは CI に無い。将来 E2E (Godot × FastAPI) スモークを足す余地あり
  (本 PR 範囲外、M6+)

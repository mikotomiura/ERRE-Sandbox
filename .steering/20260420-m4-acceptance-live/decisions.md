# Decisions — M4 Live Validation

本タスクで下した非自明な判断と、その根拠を記録する。
今後の live 検証 / evidence 収集タスクで同じ場面に遭遇した際の参考。

## D1. WS probe を `websocat` ではなく Python `websockets` で実装

**決定**: handoff 記載の `websocat` を使わず、`.venv` 内の `websockets==14.2` を
使った独自 Python スクリプト `evidence/_stream_probe.py` で実装。

**理由**:

- G-GEAR (Windows + Git Bash) に `websocat` 未インストール
- プロジェクトは既に `websockets` 14.2 を依存に持つ → 追加依存ゼロ
- handshake / keep-alive / UTF-8 エンコーディング / 行単位 JSON dump
  など、検証固有の要件を自由にハンドリングできる

**代替案と不採用理由**:

- `pip install websocat` — Rust crate、Windows には pre-built wheel 無く面倒
- `winget install websocat` — 公式レポジトリに無い

## D2. client handshake の送信が必須

**決定**: probe は accept 直後に server handshake を受け、即座に client
HandshakeMsg を返送する。`fixtures/control_envelope/handshake.json` を
参考に `peer="macbook"` + 全 capabilities で構成。

**理由**:

- `gateway.ws_observe` は Phase 1 (AWAITING_HANDSHAKE) で `HANDSHAKE_TIMEOUT_S`
  以内に client HandshakeMsg を要求、未達なら ErrorMsg + 切断する
- 最初に handshake なしで接続したところ数秒で 1000 OK 切断された (実測)

**確認方法**: `gateway.py:517-552` を読み、Phase 1 の処理を把握。

## D3. keep-alive として handshake を 30s 間隔で再送

**決定**: probe は 30 秒ごとに client handshake JSON を再送する非同期タスク
(`_keepalive`) を走らせて idle_disconnect (60s) を回避。

**理由**:

- `gateway._recv_loop` は `protocol.IDLE_DISCONNECT_S=60s` client frame 無しで
  `idle_disconnect` ErrorMsg を返して切断する (実測: 120s probe が 60s で切れた)
- `_recv_loop` は「parsed envelopes は logged as warning but otherwise ignored」
  なので、handshake の再送は副作用なく idle timer をリセットできる
- WebSocket ping/pong ではなく application-level frame が必要 (仕様上)

## D4. phase 1 probe 完了後に DB とサーバを再起動

**決定**: 最初の 60s / 180s probe で dialog_close は見えたが dialog_initiate は
捕捉できず。一旦 gateway を停止、`var/m4-live.db` を `.phase1-backup` に退避して
fresh DB で再起動、probe を server 起動時から再接続。

**理由**:

- 初期 probe は server 起動から約 90s 遅れて接続したため、最初の dialog_initiate
  (tick ~2, server 起動直後) を取り損ねていた
- 再起動して起動直後から probe を張れば initiate を高確率で捕捉できる

**代替案と不採用理由**:

- そのまま長時間 probe を走らせて偶然の発火を待つ: `AUTO_FIRE_PROB_PER_TICK=0.25`
  で 30 tick cooldown があり、短時間では発火が不安定

**結果**: 2 回目の 300s probe で `dialog_initiate` × 1 を捕捉 (Nietzsche → Rikyū @ peripatos)

## D5. `sqlite3 CLI` ではなく Python + `PYTHONIOENCODING=utf-8` で DB dump

**決定**: handoff の `sqlite3 ... | tee` をそのままでなく、
`uv run python -c "..."` 経由でダンプ。

**理由**:

- Windows のデフォルト stdout encoding は `cp932` (Shift-JIS)
- semantic_memory の content は英語中心だが emoji/特殊記号 (`—`, U+2014 等) を含む
  場合があり、`cp932` で `UnicodeEncodeError` を起こす (実測)
- `io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')` で強制 UTF-8 出力

**教訓**: Windows 環境での CLI dump には常に encoding 指定が必要。

## D6. `#5 Godot` を同 branch の別 commit として分ける

**決定**: 本 branch (`feature/m4-acceptance-live-evidence`) に `#1-#4` の
evidence commit (`b3b22cc`) と、**MacBook が別 branch `evidence/m4-godot-live-capture`
に打った `#5` commit (`22841d5`)** を rebase で取り込む形にした。

**理由**:

- #5 は MacBook 側でしか実施不能 (Godot エディタ + 録画)
- G-GEAR と MacBook の同時並行作業を許すため、commit の粒度を揃える
- rebase で linear history を維持、cherry-pick / revert の単位を明確化

**結果**: 本 PR #51 の commit 列:

1. `22841d5` MacBook #5 (既に main 経由で取り込み済)
2. `b3b22cc` G-GEAR #1-#4
3. `e83cc8e` 全 PASS 反映 (acceptance/README/tasklist 更新)

## D7. handoff Step 2 の baseline 差分を PASS 扱いで続行

**決定**: `pytest -q` baseline が `497 passed / 26 skipped` で handoff 期待値
`503 / 20` と 6 件差。0 failures のため続行。

**理由**:

- handoff §Step 2 の停止条件は「失敗 test / モデル欠落」。skip 差分は該当しない
- 差分 6 件は `test_godot_*` の追加 skip で完全に説明がつく
  (G-GEAR に Godot 未インストール、設計通り)
- Godot 本体を G-GEAR に入れる意義が薄い (#5 は Mac 側で実施する前提)

## D8. DB file (`var/m4-live.db`, `var/m4-live.db.phase1-backup`) は commit しない

**決定**: `var/` は `.gitignore` 配下なので、DB ファイルは git に含まない。

**理由**:

- reflection summary が LLM 応答の raw text を保持 → 意図しない情報漏洩のリスク
- ファイルサイズ (各 3 MB 程度) がリポジトリを肥大化
- 代わりに `semantic-memory-dump-*.txt` でテキスト抜粋を commit、
  これで PASS 判定は可能

## D9. broken evidence file は commit 前に削除

**決定**: `cognition-ticks-20260420T155253.log` (0 envelope, handshake 前の試行) と
`semantic-memory-dump-20260420T155554.txt` (cp932 エラーで truncated) は commit 前に削除。

**理由**:

- 失敗した試行ログを残しても誤解を招く
- 代替の完全な evidence (T155354.log, T155606.txt) が別途存在
- ただし `cognition-ticks-20260420T155551.log` は 60s で `idle_disconnect` を
  受けた実測データで、D3 の根拠として価値があるので残す

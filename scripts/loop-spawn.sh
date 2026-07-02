#!/usr/bin/env bash
# loop-spawn.sh — 1 issue 用の worktree を切り、その中で Claude セッションを起動する人間用ヘルパ。
#   使い方:  bash scripts/loop-spawn.sh <issue-id> [short-slug]
#            bash scripts/loop-spawn.sh --cleanup <issue-id>
# worktree は main checkout の隣 (../wt/) に作る。events は main checkout の絶対パスに集約されるため
# 各 worker が同じ _loop-events.jsonl に append できる (DA-LOOP-1: loop/ 根、.steering/ ではない)。
set -euo pipefail

BASE_DEFAULT="${LOOP_BASE_BRANCH:-}"   # 未指定なら下で解決

die() { echo "loop-spawn: $*" >&2; exit 1; }

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || die "git リポジトリ内で実行してください"
cd "$repo_root"
repo_name="$(basename "$repo_root")"

# --- base branch の解決 (pin) ---
resolve_base() {
  if [ -n "$BASE_DEFAULT" ]; then echo "$BASE_DEFAULT"; return; fi
  # origin/HEAD が指す既定ブランチ → 無ければ main → master の順
  local b
  b="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')" || true
  if [ -z "${b:-}" ]; then
    if git show-ref --verify --quiet refs/heads/main; then b=main
    elif git show-ref --verify --quiet refs/heads/master; then b=master
    else b="$(git rev-parse --abbrev-ref HEAD)"; fi
  fi
  echo "$b"
}

# --- cleanup モード (merge 後の撤去) ---
if [ "${1:-}" = "--cleanup" ]; then
  id="${2:?--cleanup には issue-id が必要です}"
  # porcelain の worktree 行はプレフィックス除去で取得 (空白入りパスに耐える)
  wt="$(git worktree list --porcelain | awk -v id="$id" '/^worktree /{p=substr($0,10)} /^branch /&&$0 ~ ("loop/" id){print p}')"
  if [ -n "$wt" ]; then
    git worktree remove "$wt" 2>/dev/null || git worktree remove --force "$wt" \
      || echo "loop-spawn: worktree 撤去失敗 (dirty/locked?) — 手動確認を"
  else
    echo "loop-spawn: worktree 見つからず (既に撤去?)"
  fi
  # 同一 id の branch を 1 つずつ削除 (複数一致でも壊れない)
  git branch --list "loop/${id}-*" | sed 's/^[ *]*//' | while read -r b; do
    [ -n "$b" ] && { git branch -d "$b" 2>/dev/null || echo "loop-spawn: branch $b 未 merge か既に削除"; }
  done
  git worktree prune
  echo "loop-spawn: cleanup 完了 issue ${id}"
  exit 0
fi

id="${1:?issue-id を指定してください}"
short="${2:-issue}"
base="$(resolve_base)"
branch="loop/${id}-${short}"
wtdir="../wt/${repo_name}-${id}-${short}"

# --- dirty tree ハンドリング ---
if [ -n "$(git status --porcelain)" ]; then
  echo "loop-spawn: 作業ツリーに未コミット変更があります。worktree add は index を共有しません" >&2
  echo "            が、混乱を避けるため commit / stash を推奨します。続行するには LOOP_FORCE=1。" >&2
  [ "${LOOP_FORCE:-0}" = "1" ] || die "中断 (LOOP_FORCE=1 で強行可)"
fi

# --- stale worktree 検出 (basename 一致・空白入りパスに耐える) ---
target_bn="$(basename "$wtdir")"
if git worktree list --porcelain | awk '/^worktree /{print substr($0,10)}' \
     | while read -r p; do [ "$(basename "$p")" = "$target_bn" ] && echo HIT; done | grep -q HIT; then
  die "同名 worktree が既に存在: $wtdir  (完了済みなら --cleanup $id を先に)"
fi
if [ -d "$wtdir" ]; then die "ディレクトリ $wtdir が残存。手動で確認/削除してください"; fi
if git show-ref --verify --quiet "refs/heads/$branch"; then
  die "ブランチ $branch が既存。--cleanup $id で撤去してから再実行"
fi
git worktree prune   # 消えたパスの登録を掃除

# --- base を remote と同期し、可能なら remote-tracking から分岐 (stale local base を避ける) ---
start="$base"
if git remote get-url origin >/dev/null 2>&1; then
  if git fetch --quiet origin "$base"; then
    start="origin/$base"          # fetch 成功時は最新の remote から分岐
  else
    echo "loop-spawn: fetch 失敗 (オフライン?) ローカル base で続行"
  fi
fi

echo "loop-spawn: base=$base (start=$start) → branch=$branch / worktree=$wtdir"
git worktree add -b "$branch" "$wtdir" "$start"
cd "$wtdir"

echo "loop-spawn: worktree 準備完了。Claude を起動します → /loop-issue $id を実行してください"
# Windows(Git Bash) では claude が .cmd/.ps1 shim のことがあり exec が滑る。見つからなければ手順を案内。
if command -v claude >/dev/null 2>&1; then
  exec claude
else
  echo "loop-spawn: 'claude' が PATH に見つかりません。手動で:  cd \"$wtdir\" && claude"
  exit 0
fi

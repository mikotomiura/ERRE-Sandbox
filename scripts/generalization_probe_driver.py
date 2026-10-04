#!/usr/bin/env python
"""候補 G (汎化 probe) — null pilot と本走の実走 driver (prereg §4・§8.1・§9.2・§9.4).

凍結物 (battery の renderer・seed・定数、pilot 判定と scorer の parse・構造の検査・meta の検査、manifest の
照合) を import だけして、qwen3:8b を **逐次** に呼ぶ。自由度は足さない。判断記録 =
``.steering/20261002-generalization-probe-driver/decisions.md`` (DD-1〜、実データを見る前に commit)。

* **段** (``Stage``)。pilot と本走は同じ経路を通り、段ごとに plan・body の組み立て・parse・凍結済みの構造の検査・
  grid・参照する observed だけを差し替える (DD-1)。pilot = KNOW 108 → masked の単位 576、本走 = lever の単位
  (R = pilot の機械判定の R)。単位の順は (r, 族, つ組)、単位の中ではつ組の probe ごとに族内の 2 arm を交互に呼ぶ
  (prereg §4)。KNOW を先に置くのは §8.2 の判定の順に合わせたため (DD-4)。
* **予定表の事前検査** (DD-1)。候補 G は開ループで、どの呼び出しの body も plan のキーだけで決まる。全件の body を
  最初に作り、骨格の記録 (raw = null) を凍結済みの構造の検査・grid の完全性に、meta を凍結済みの ``meta_violations``
  に通す。外れたら run dir を作らず、モデルを 1 回も呼ばずに止まる (``ScheduleError``)。
* **送る直前の照合**。``ObservingTransport`` が wire の body を読み、key の集合・値と型 (False と 0、4096.0 と 4096 を
  区別する)・その位置のキーでの凍結済みの構造の検査 (seed と prompt) を照合する。外れたら送らずに止まる
  (``SentBodyMismatchError``)。POST は ``/api/chat`` と、observed を読む間の ``/api/show`` だけを通す。
* **通信は httpx を直接使う** (DD-2)。transport 失敗 = ``httpx.HTTPError`` 全般・HTTP が 200 でない・JSON でない・
  ``message.content`` が無いか文字列でない。同じ body (同じ seed) で再送を 3 回まで行う。解けなければ raw = null の
  行を書いて止まる (⊥ にしない)。それ以外の例外は行を書かずに止まる。再開しない。
* **observed** = ``/api/version`` の版・``/api/tags`` の凍結 model の digest・``/api/show`` の chat template の sha256。
  開始時に読んで meta.json に書き、終了時に読み直す。変わっていれば異常。本走は開始時の値が pilot の機械判定の
  observed と違えば、run dir を作らずに止まる。
* **成功したときだけ公開する** (v5 の DV-1・DV-4 を継ぐ、DD-3)。記録は ``records.partial.jsonl`` に書き、次を全て
  満たしたときだけ ``records.jsonl`` へ rename する。凍結 ``run.sh`` は ``test -f records.jsonl`` で止まるので、
  公開されていない run は判定まで進まない。transport 失敗の run も公開しない (やり直しは user の裁定)。

  - 全件に答えがあり、transport 失敗が無い。
  - 来歴の異常が無い (応答の model 名・observed が開始時と同じ)。
  - その段の manifest の照合が、公開の時点でも ``MANIFEST OK (stage <段>)``。
  - partial と meta.json を判定と同じ reader で読み戻し、凍結済みの構造の検査・meta の検査・完全性を通る。
  - partial と meta.json の bytes が、この run が書いた行と meta に一致する (別の run の記録・meta を混ぜない、
    Codex HIGH-1)。
  - 固定ファイルの sha256 が起動時と同じで、ディスクの driver が実行中の driver と同じ。公開時の manifest の照合と
    読み戻しの **後** に比べる (Codex HIGH-2)。

  来歴 (provenance.json) は二相: 未公開 (aborted・pending の注記) で書く → rename → 公開済みに書き直す。
  第 2 段が照合する 3 項目 (``driver_sha256``・``records_sha256``・``meta_sha256``) は、公開済みの来歴にだけ書く
  (途中で kill されたら 3 項目の無い来歴が残り、第 2 段が拒否する。DD-5)。3 項目は、実行中に保持した値 (起動時に
  読んだ driver の sha256・この run が書いた行と meta の bytes の sha256) から書き、rename の後のファイルが同じ bytes である
  ことを確かめてから書く。raw = null の行を書いた run (解けない transport 失敗) の来歴には ``status: not_computed`` を書く
  (prereg §4、DD-3。終了時の observed の取得中に中断しても残す)。
* **起動の前提** (``launch_problems``): driver の certification が manifest の契約を満たす・ディスクの driver が
  実行中の driver と同じ・固定ファイルが git で追跡され HEAD と一致・その段の manifest の照合が
  ``MANIFEST OK (stage <段>)``・run.sh と同じ interpreter の設定 (``PYTHONHASHSEED`` = SEED・``PYTHONUTF8=1``) で
  起動した。本走は pilot の機械判定が GO。固定ファイルの sha256 は起動の検査の前に取り、実走の終わりに比べる。
* **manifest の照合はこの process の中で行う** (``_run_manifest``、Codex 4 回目 HIGH-1)。封印済みの ``man.main`` を
  run.sh と同じ引数で呼ぶ。子プロセス (門も ``_PinnedFinder`` も無い) では、未追跡の ``scripts/__init__.py`` 等が
  実行されても照合の最後の行は変わらず、driver は受理してしまう。この process の中なら、照合の結論を出したコードは
  ``executed_problems`` が同定したコード (固定ファイルの bytes) になる。run.sh と同じ hash seed・UTF-8 mode は、
  子に環境変数を渡す代わりに、driver をその設定で起動したことを起動の前提にして保つ (decisions DF-5)。
* **実行したコードの同定** (``executed_problems``、Codex 再 review HIGH-1)。来歴の hash は、実行したプログラムを指す。
  driver は起動時に bytes を 1 回だけ読み、実行中のモジュールの code object がその bytes のコンパイル結果であることを確かめる
  (code object の等値。bytes の一致ではなく、末尾のコメントだけの差は等しい)。repo のモジュール (封印済みの依存と、
  certification の検査が import する driver の harness) は、起動のときだけ ``_PinnedFinder`` が 1 回だけ読んだ bytes から
  実行する (pyc を読まない)。起動の検査の後に、その bytes が固定ファイルで、起動の検査の前のディスクと同じことを照合する。
  それ以外のコードは、環境 (インタプリタと venv の prefix の下、repo を含む prefix は除く) のものだけを実行する
  (Codex 3 回目 MEDIUM-2)。起動のときは、driver の最初の文で import の門 (``_LaunchGate``) を入れ、環境の外に所在がある
  module (``scripts/`` に置いた ``numpy.py`` 等) を import させない (ImportError で exit 1、何も書かない)。``scripts`` は
  ``root/scripts`` だけを探す名前空間として作る (``__init__.py`` を実行しない)。門より前のコードは 2 段で見る
  (``executed_problems``): 走りうるもの = site が起動時に実行する customization (``sitecustomize``・``usercustomize``)・
  ``PYTHONPATH`` の entry と、Windows の getpath がレジストリから検索パスに足した entry (子キーは常に、キー自身の既定値は
  ``sys.path`` にあるとき。site が処理する ``.pth`` の import 行が、名前に依らず同名の module を読みうる、Codex 5 回目 HIGH-1)・
  user site の ``.pth`` の所在 (``startup_problems``。import に失敗したものは ``sys.modules`` に残らないので、実行されたかを問わず
  所在で拒否する、Codex 4 回目 HIGH-2・code-reviewer HIGH-2)、取り込まれたもの = ``sys.modules`` の所在 (``outside_problems``)。
  検証した起動 = 起動するシェルに ``PYTHONHOME`` の無い ``uv run python`` (uv の CPython 3.11.15、``-E``/``-I`` でない・``._pth`` なし、
  Codex 6 回目 LOW-2・code-reviewer HIGH)。venv の launcher (venv の ``Scripts`` の python) が子に ``PYTHONHOME`` = pyvenv.cfg の home
  (base の Python の dir) を渡して base の python を起動し、getpath は venv の分岐を通らず、venv は site が認識する。このとき getpath が
  検索パスに足す出所は、環境変数の PYTHONPATH・zip・レジストリ・build 時の既定 (この interpreter では prefix の下の相対)・stdlib と
  platstdlib の dir・Windows の executable の dir (venv の ``Scripts``) で、PYTHONPATH とレジストリ以外は環境 (prefix) の中。
  ``._pth`` は ``-E`` 扱いになり起動の前提が拒否する。Py_SetPath・埋め込みの再計算は対象外。レジストリのキー自身の既定値は、
  ``PYTHONHOME`` (home) のある起動では使われず、他の起動でも stdlib が見つからないときだけ使われる (使われたかは ``sys.path`` に
  あるかで見る)。その **空の** entry (= cwd) は、driver が足す repo root と区別できないので数えない (保証の外)。
  レジストリは起動の後に読み直すので、getpath から検査までの間にレジストリと
  検索パスが変わらないことを前提にする (pilot・本走の間に Python の install・update をしない、env.md)。所在は、Windows の拡張表記
  (長い path の接頭辞の付いた形) のドライブと UNC の path を通常の表記に揃えてから比べる (``_ordinary``、Codex 6 回目 HIGH-1)。
  driver の最初の文の ``from __future__`` が import する ``__future__`` は、成功すれば ``sys.modules`` の走査が、失敗すれば
  driver の import の失敗が止める。
  主張: driver の process で実行した repo のコードは、来歴の hash が指す固定ファイルの bytes のコンパイル結果。
  保証の外: 環境の中のコード (第三者のライブラリ・標準ライブラリ・インタプリタ・venv の ``.pth``、版は uv.lock が固定する)、
  環境の ``.pth`` が足す環境の外の path (editable install の ``src``) が後の ``.pth`` の import 行を横取りする経路、
  意図的な不正 (偽の endpoint・門より前に取り込まれて自分を ``sys.modules`` から消し、自分のファイルも消すコード等)、
  起動するシェルの ``PYTHONHOME`` で環境の prefix 自体を変えた起動 (launcher は上書きせず、getpath がその dir を prefix にする)、
  driver の外の process。
  凍結 ``run.sh`` の判定の process (manifest の照合・機械判定・scorer) は門を持たず、封印済みの
  module が repo root を ``sys.path`` の先頭に入れるので、run.sh と driver の起動の前に、repo root 直下と ``scripts`` に未追跡・ignored の
  import できるもの (source ``.py``・``.pyw``、source の無い ``.pyc``、拡張 module ``.pyd``・``.so``、package の initializer
  ``__init__.*``。Windows は拡張子の大文字小文字を区別しない) と link (reparse point) が無いこと、起動するシェルの ``PYTHONPATH``・
  ``PYTHONHOME`` が未設定か空であること (process の中では launcher が入れた ``PYTHONHOME`` が見える)、同じ Python で読むレジストリの
  検索パスの子キーが無いことを確かめる (運用、env.md の command、Codex 5 回目 MEDIUM-2・6 回目 MEDIUM-1)。
  Debian・Ubuntu の system Python を base にした venv では、標準ライブラリの sitecustomize が ``/etc`` への link なので、
  環境の外として起動を拒否されうる (安全側。uv が入れた Python では起きない)。

実行 (repo root から、GPU 実走は user 裁定の後)。run dir と endpoint は固定で、引数は段だけ。run.sh と同じ
``PYTHONHASHSEED`` (= ``<EXP>/SEED``) と ``PYTHONUTF8=1`` で起動する (違えば何も書かずに起動を拒否する)::

    $env:PYTHONUTF8 = "1"
    $env:PYTHONHASHSEED = (Get-Content experiments/20261001-generalization-probe-pilot/SEED).Trim()
    uv run python scripts/generalization_probe_driver.py --stage pilot

    export PYTHONUTF8=1 PYTHONHASHSEED="$(cat experiments/20261001-generalization-probe-pilot/SEED)"
    uv run python scripts/generalization_probe_driver.py --stage main
"""

from __future__ import annotations

# ruff: noqa: E402 — import の門 (下) を、他の import より前に入れる
import os
import sys

# ------------------------------------------------ import の門 (他の import の前、Codex 3 回目 MEDIUM-2)
# 起動 (__main__) のとき、環境 (インタプリタ・venv) と固定ファイルの外のコードを import させない (decisions DT-2・DT-4)。
# sys・os は起動時に読み込み済みなので、ここまでに driver の外のコードは実行されていない。固定ファイルの
# scripts.* は、門の前に入れる _PinnedFinder が先に引き受ける (門まで来た scripts.* は固定ファイルでない)。

_ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))  # noqa: PTH120


def _ordinary(resolved: str) -> str:
    r"""normcase 済みの Windows の拡張表記 (``\\?\c:\…``・``\\?\unc\…``) を通常の表記にする (Codex 6 回目 HIGH-1).

    ``realpath`` は入力が拡張表記なら接頭辞を保つので、環境の中の dir が通常の表記の root の下と判定されない。ドライブと
    UNC だけを戻し、他の名前空間 (``\\?\volume{…}`` 等) は変えない。比べるためだけで、開くのには使わない。
    """
    if resolved.startswith("\\\\?\\unc\\"):
        return "\\\\" + resolved[8:]
    if resolved.startswith("\\\\?\\") and resolved[5:7] == ":\\":
        return resolved[4:]
    return resolved


def _norm(path: str) -> str:
    resolved = os.path.normcase(os.path.realpath(path))
    return _ordinary(resolved) if os.name == "nt" else resolved


def _under(path: str, root: str) -> bool:
    """``path`` が ``root`` の下 (同じを含む) か。別ドライブ・相対と絶対の組は False.

    引数は両方とも ``_norm`` 済みであること (比べるのは正規化した文字列の path の要素)。
    """
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _environment_roots(repo: str = _ROOT_DIR) -> tuple[str, ...]:
    """環境 = インタプリタと venv の prefix (版は uv.lock が固定する)。repo を含む prefix は環境に数えない."""
    repo_n = _norm(repo)
    prefixes = (sys.prefix, sys.exec_prefix, sys.base_prefix, sys.base_exec_prefix)
    roots = {_norm(p) for p in prefixes}
    return tuple(sorted(r for r in roots if not _under(repo_n, r)))


def _in_environment(location: str, roots: Sequence[str]) -> bool:
    loc = _norm(location)
    return any(_under(loc, r) for r in roots)


def _spec_locations(spec: object) -> list[str]:
    """所在 = spec の origin (``has_location`` のとき) と package の探索場所。built-in・frozen は空."""
    out: list[str] = []
    origin = getattr(spec, "origin", None)
    if getattr(spec, "has_location", False) and isinstance(origin, str):
        out.append(origin)
    out.extend(str(p) for p in getattr(spec, "submodule_search_locations", None) or ())
    return out


class _LaunchGate:
    """環境の外に所在がある module を import させない門 (``sys.meta_path`` の先頭に入れる).

    他の finder に spec を探させ、最初に見つかった spec の所在が全て環境の中ならその spec を返す。外なら ImportError。
    """

    def __init__(
        self, roots: Sequence[str], finders: Sequence[object] | None = None
    ) -> None:
        self.roots = tuple(roots)
        self.finders = finders  # None なら sys.meta_path (自分を除く)

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        for finder in list(sys.meta_path if self.finders is None else self.finders):
            find = getattr(finder, "find_spec", None)
            if finder is self or find is None:
                continue
            spec = find(fullname, path, target)
            if spec is None:
                continue
            outside = [
                loc
                for loc in _spec_locations(spec)
                if not _in_environment(loc, self.roots)
            ]
            if outside:
                msg = (
                    "refusing to import code outside the pinned files and the environment: "
                    f"{fullname} ({outside[0]})"
                )
                raise ImportError(msg, name=fullname)
            return spec
        return None


if __name__ == "__main__":
    # 門を先に入れる。後で _PinnedFinder を門の前 (meta_path[0]) に入れるので、固定ファイルの scripts.* と
    # scripts の名前空間は門まで行かない (下の _PinnedFinder を入れる所と対)
    sys.meta_path.insert(0, _LaunchGate(_environment_roots()))

import argparse
import asyncio
import contextlib
import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import io
import json
import pathlib
import subprocess
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, TextIO

import httpx

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from importlib.machinery import ModuleSpec
    from types import CodeType, ModuleType


# ------------------------------------------------ 実行したコードの同定 (repo の import の前)
# 来歴の hash は、実行したプログラムを指す (Codex 再 review HIGH-1、decisions DX-1・DU-3)。driver 自身は、実行中の
# モジュールの code object を、起動時に 1 回だけ読んだ bytes のコンパイル結果と比べる。repo のモジュールは、起動
# (__main__) のときだけ、1 回だけ読んだ bytes から実行する (_PinnedFinder)。照合は executed_problems。


def _compiles_to(code: CodeType, data: bytes, path: pathlib.Path) -> bool:
    """``code`` が ``data`` のコンパイル結果と同じプログラムか.

    code object の等値は、定数・名前・行表・入れ子の関数まで比べる (ファイル名は比べない)。bytes の一致ではなく、
    末尾のコメントだけの差は等しい。
    """
    try:
        return code == compile(data, str(path), "exec", dont_inherit=True)
    except (SyntaxError, ValueError):
        return False


_DRIVER_PATH: pathlib.Path = pathlib.Path(__file__).resolve()
_DRIVER_BYTES: bytes = _DRIVER_PATH.read_bytes()
# 来歴の driver_sha256 は、起動時に 1 回だけ読んだ bytes の sha256 (Codex HIGH-2・再 review HIGH-1)
_DRIVER_SHA: str = hashlib.sha256(_DRIVER_BYTES).hexdigest()
# 実行中の driver が、その bytes のコンパイル結果か。起動でも test の import でも、この同じ行が走る
_DRIVER_RUNS_ITS_BYTES: bool = _compiles_to(
    sys._getframe(0).f_code,  # noqa: SLF001 — 実行中のモジュールの code object
    _DRIVER_BYTES,
    _DRIVER_PATH,
)


class _PinnedLoader(importlib.abc.Loader):
    """1 回だけ読んだ bytes をコンパイルして実行する loader (ディスクも pyc も読み直さない・pyc を書かない)."""

    def __init__(self, path: pathlib.Path, data: bytes) -> None:
        self.path = path
        self.data = data
        self.pinned_sha256 = hashlib.sha256(data).hexdigest()

    def exec_module(self, module: ModuleType) -> None:
        code = compile(self.data, str(self.path), "exec", dont_inherit=True)
        exec(code, module.__dict__)  # noqa: S102 — hash した bytes そのものを実行する


class _PinnedFinder(importlib.abc.MetaPathFinder):
    """``<package>.<name>`` を、``root/<package>/<name>.py`` から 1 回だけ読んだ bytes で import させる.

    ``<package>`` 自体は、``root/<package>`` だけを探す名前空間として作る (``__init__.py`` があっても実行しない、
    Codex 3 回目 MEDIUM-2)。
    """

    def __init__(self, root: pathlib.Path, package: str = "scripts") -> None:
        self.root = root
        self.package = package

    def find_spec(
        self,
        fullname: str,
        path: object = None,  # noqa: ARG002
        target: object = None,  # noqa: ARG002
    ) -> ModuleSpec | None:
        if fullname == self.package:
            spec = importlib.machinery.ModuleSpec(fullname, None, is_package=True)
            spec.submodule_search_locations = [str(self.root / self.package)]
            return spec
        head, _, name = fullname.partition(".")
        if head != self.package or not name or "." in name:
            return None
        file = self.root / self.package / f"{name}.py"
        if not file.is_file():
            return None
        loader = _PinnedLoader(file, file.read_bytes())
        return importlib.util.spec_from_file_location(fullname, file, loader=loader)


if __name__ == "__main__":
    # 実走の起動: repo のモジュールを、1 回だけ読んだ bytes から実行する (照合は起動の検査の後の executed_problems)。
    # 門の前に入れる (固定ファイルの scripts.* と scripts の名前空間は、門まで行かない)
    sys.meta_path.insert(0, _PinnedFinder(_REPO_ROOT))

from scripts import generalization_probe_battery as bat
from scripts import generalization_probe_manifest as man
from scripts import generalization_probe_pilot_gate as pg
from scripts import generalization_probe_scorer as sc

STAGE_PILOT: Final[str] = "pilot"
STAGE_MAIN: Final[str] = "main"
SEED_PATH: Final[pathlib.Path] = _REPO_ROOT / man.EXP / "SEED"
PILOT_DIR: Final[pathlib.Path] = _REPO_ROOT / man.EXP / "results" / "pilot"
RUN_DIR: Final[pathlib.Path] = _REPO_ROOT / man.EXP / "results" / "run"
GATE_PATH: Final[pathlib.Path] = _REPO_ROOT / man.PILOT_GATE
DRIVER_CERT: Final[pathlib.Path] = _REPO_ROOT / man.DRIVER_CERT
DEFAULT_ENDPOINT: Final[str] = "http://127.0.0.1:11434"
RECORDS_NAME: Final[str] = "records.jsonl"  # 公開名 (凍結 run.sh が test -f で見る)
PARTIAL_NAME: Final[str] = "records.partial.jsonl"  # 実走中・未公開の記録
META_NAME: Final[str] = "meta.json"
PROVENANCE_NAME: Final[str] = "provenance.json"
ATTEMPTS_NAME: Final[str] = "attempts.jsonl"
# rename の後の照合に落ちた記録を退ける名前 (公開名に残すと、凍結 run.sh の test -f を通ってしまう)
REJECTED_NAME: Final[str] = "records.rejected.jsonl"
# 二相の公開: rename の前に書く来歴の注記 (これが残っていれば、公開の前に中断した run)
PENDING_NOTE: Final[str] = (
    "publication pending (interrupted before the rename if this remains)"
)

RESENDS: Final[int] = 3  # 同じ seed での再送回数 (送信は初回と合わせて最大 4 回)
# 再送の待ち (秒)。attempt ごとに延ばす (Ollama の再起動・復帰を待つ。登録外・label と独立)
BACKOFF_SCHEDULE_S: Final[tuple[float, ...]] = (5.0, 30.0, 120.0)
TIMEOUT_S: Final[float] = 300.0  # モデルの再ロードで 60 秒を超えうる

REASON_COMPLETED: Final[str] = "completed"
REASON_TRANSPORT: Final[str] = "transport_failure"
REASON_ABORTED: Final[str] = "aborted"
EXIT_CODES: Final[dict[str, int]] = {
    REASON_COMPLETED: 0,
    REASON_TRANSPORT: 3,
    REASON_ABORTED: 4,
}

CHAT_PATH: Final[str] = "/api/chat"
SHOW_PATH: Final[str] = "/api/show"
BODY_KEYS: Final[frozenset[str]] = frozenset(
    {"model", "messages", "stream", "think", "options"}
)
OPTION_KEYS: Final[frozenset[str]] = frozenset(
    {"seed", "num_ctx", "num_predict", "temperature", "top_p", "repeat_penalty"}
)
# 送る値 (凍結 battery の定数)。seed 以外は全呼び出しで同じ
FIXED_OPTIONS: Final[dict[str, object]] = {
    "num_ctx": bat.NUM_CTX,
    "num_predict": bat.NUM_PREDICT,
    "temperature": bat.TEMPERATURE,
    "top_p": bat.TOP_P,
    "repeat_penalty": bat.REPEAT_PENALTY,
}

Key = tuple[str, int, str, int]  # (arm, replicate, probe_id, k) = 凍結 grid の要素
_MASKED_OF: Final[dict[str, str]] = {lever: m for m, lever in pg.MASKED_ARMS.items()}
_PROBES: Final[dict[str, bat.Probe]] = {p.probe_id: p for p in bat.probes()}


# ------------------------------------------------------------------- 段


@dataclass(frozen=True)
class Stage:
    """pilot と本走で差し替える部分 (DD-1)。経路 (事前検査・照合・再送・記録・公開) は共通."""

    name: str
    run_dir: pathlib.Path
    plan: tuple[Key, ...]
    grid: frozenset[Key]
    request: Callable[[Key], tuple[list[dict[str, str]], int]]  # → (messages, seed)
    parse: Callable[[str, str], str | None]  # (arm, raw) → parsed
    structure: Callable[[Sequence[sc.Sample]], list[str]]  # 凍結済みの構造の検査
    reference_observed: dict[str, str] | None = None


def unit_keys(rs: range, k_count: int, arm_name: Callable[[str], str]) -> list[Key]:
    """単位の順 (r, 族, つ組) に、つ組の probe ごとに族内の 2 arm を交互に並べる (prereg §4)."""
    out: list[Key] = []
    for r in rs:
        for family in bat.FAMILIES:
            for j in range(bat.N_TRIPLES):
                for p in bat.triple_probes(j):
                    for k in range(k_count):
                        out.extend((arm_name(arm), r, p.probe_id, k) for arm in family)
    return out


def pilot_plan() -> tuple[Key, ...]:
    """KNOW (key 番号 × 試行) → masked の単位 (r ∈ [PILOT_R0, PILOT_R0 + PILOT_R))."""
    know = [
        (pg.ARM_KNOW, 0, pg.know_probe_id(i), k)
        for i in range(len(bat.all_keys()))
        for k in range(bat.KNOW_K)
    ]
    rs = range(bat.PILOT_R0, bat.PILOT_R0 + bat.PILOT_R)
    return (*know, *unit_keys(rs, pg.PILOT_K, _MASKED_OF.__getitem__))


def main_plan(r_count: int) -> tuple[Key, ...]:
    return tuple(unit_keys(range(r_count), sc.FROZEN_K, str))


def pilot_request(key: Key) -> tuple[list[dict[str, str]], int]:
    arm, r, probe_id, k = key
    if arm == pg.ARM_KNOW:
        i = int(probe_id[1:])
        return bat.render_know_messages(i, k), bat.sample_seed("know", 0, i, k)
    lever = pg.MASKED_ARMS[arm]
    probe = _PROBES[probe_id]
    ns = f"pilot_fam{bat.ARM_FAMILY[lever]}"
    return (
        bat.render_messages(lever, probe, r, masked=True),
        bat.sample_seed(ns, r, probe.triple, k),
    )


def main_request(key: Key) -> tuple[list[dict[str, str]], int]:
    arm, r, probe_id, k = key
    probe = _PROBES[probe_id]
    ns = f"fam{bat.ARM_FAMILY[arm]}"
    return bat.render_messages(arm, probe, r), bat.sample_seed(ns, r, probe.triple, k)


def pilot_parse(arm: str, raw: str) -> str | None:
    """KNOW は分類名、masked は行動 label (凍結 pilot 判定の re-parse と同じ関数)."""
    return pg.parse_class(raw) if arm == pg.ARM_KNOW else sc.parse_choice(raw)


def main_parse(_arm: str, raw: str) -> str | None:
    return sc.parse_choice(raw)


def pilot_stage(run_dir: pathlib.Path) -> Stage:
    return Stage(
        name=STAGE_PILOT,
        run_dir=run_dir,
        plan=pilot_plan(),
        grid=frozenset(pg.pilot_grid()),
        request=pilot_request,
        parse=pilot_parse,
        structure=pg.structure_violations,
    )


def main_stage(
    run_dir: pathlib.Path, r_count: int, reference_observed: dict[str, str]
) -> Stage:
    def structure(samples: Sequence[sc.Sample]) -> list[str]:
        return sc.structure_violations(samples, r_count, sc.FROZEN_K)

    return Stage(
        name=STAGE_MAIN,
        run_dir=run_dir,
        plan=main_plan(r_count),
        grid=frozenset(sc.grid(r_count, sc.FROZEN_K)),
        request=main_request,
        parse=main_parse,
        structure=structure,
        reference_observed=dict(reference_observed),
    )


# ------------------------------------------------------- body と予定表


class ScheduleError(RuntimeError):
    """予定表が凍結済みの検査を通らない。モデルを 1 回も呼ばずに止まる (DD-1)."""


class SentBodyMismatchError(RuntimeError):
    """送ろうとした body が凍結値と違う。httpx 例外でないので再送されない."""


def body_for(stage: Stage, key: Key) -> dict[str, Any]:
    messages, seed = stage.request(key)
    return {
        "model": bat.MODEL,
        "messages": messages,
        "stream": False,
        "think": bat.THINK,
        "options": {"seed": seed, **FIXED_OPTIONS},
    }


def request_of(body: dict[str, Any]) -> dict[str, Any]:
    """Body から ``sc.request_meta()`` と同じ形の要求条件を読む."""
    opts = body["options"]
    return {
        "model": body["model"],
        "think": body["think"],
        "options": {
            "temperature": opts["temperature"],
            "top_p": opts["top_p"],
            "repeat_penalty": opts["repeat_penalty"],
            "num_ctx": opts["num_ctx"],
            "num_predict": opts["num_predict"],
        },
    }


def _exact(got: object, want: object) -> bool:
    """型まで一致 (False == 0、4096.0 == 4096 を通さない)."""
    return type(got) is type(want) and got == want


def _canonical(obj: object) -> str:
    """型まで区別する比較用の JSON (4096.0 と 4096、False と 0 を別物にする)."""
    return json.dumps(obj, sort_keys=True)


def shape_problems(body: object) -> list[str]:
    """Body の形と、seed 以外の値 (key の集合・型・凍結値)."""
    if not isinstance(body, dict) or set(body) != BODY_KEYS:
        return [f"body keys differ from {sorted(BODY_KEYS)}"]
    msgs = body["messages"]
    if not isinstance(msgs, list) or not all(
        isinstance(m, dict)
        and set(m) == {"role", "content"}
        and all(type(v) is str for v in m.values())
        for m in msgs
    ):
        return ["messages are not a list of role / content strings"]
    opts = body["options"]
    if not isinstance(opts, dict) or set(opts) != OPTION_KEYS:
        return [f"options keys differ from {sorted(OPTION_KEYS)}"]
    problems = [
        f"{name}={body[name]!r}"
        for name, want in (
            ("model", bat.MODEL),
            ("think", bat.THINK),
            ("stream", False),
        )
        if not _exact(body[name], want)
    ]
    problems.extend(
        f"options.{name}={opts[name]!r} (want {want!r})"
        for name, want in FIXED_OPTIONS.items()
        if not _exact(opts[name], want)
    )
    if type(opts["seed"]) is not int:
        problems.append(f"options.seed={opts['seed']!r} is not an int")
    return problems


def skeleton(index: int, key: Key, body: dict[str, Any]) -> sc.Sample:
    """送る body の候補記録 (raw = null)。seed と prompt は body から読む."""
    arm, r, probe_id, k = key
    return sc.Sample(
        call_index=index,
        arm=arm,
        replicate=r,
        probe_id=probe_id,
        k=k,
        seed=body["options"]["seed"],
        prompt_sha256=sc.messages_sha256(body["messages"]),
        raw=None,
        parsed=None,
    )


def build_schedule(stage: Stage) -> tuple[dict[str, Any], ...]:
    """plan の位置ごとの body (呼び出しの前に全部作る)."""
    return tuple(body_for(stage, key) for key in stage.plan)


def meta_for(
    schedule: Sequence[dict[str, Any]], observed: dict[str, str]
) -> dict[str, Any]:
    """meta.json = {"request": 予定表の要求条件, "observed": 開始時の observed} (prereg §4)."""
    return {"request": request_of(schedule[0]), "observed": dict(observed)}


def schedule_violations(
    stage: Stage, schedule: Sequence[dict[str, Any]], observed: dict[str, str]
) -> list[str]:
    """予定表全体と meta を、呼び出しの前に凍結済みの検査に通す (DD-1)."""
    out: list[str] = []
    if len(set(stage.plan)) != len(stage.plan) or set(stage.plan) != stage.grid:
        out.append("schedule: plan keys differ from the frozen grid")
    if not schedule or len(schedule) != len(stage.plan):
        out.append("schedule: bodies do not match the plan")
    for i, body in enumerate(schedule):
        out.extend(f"schedule: call {i}: {p}" for p in shape_problems(body))
    if out:
        return out
    cands = [
        skeleton(i, key, body)
        for i, (key, body) in enumerate(zip(stage.plan, schedule, strict=True))
    ]
    out.extend(f"schedule: {p}" for p in stage.structure(cands))
    meta = meta_for(schedule, observed)
    if _canonical(meta["request"]) != _canonical(sc.request_meta()):
        out.append("schedule: request conditions differ from the frozen values")
    out.extend(
        f"schedule: {p}" for p in sc.meta_violations(meta, stage.reference_observed)
    )
    return out


def check_sent_body(stage: Stage, index: int, body: object) -> None:
    """送信前の wire body を、plan の位置 index のキーで凍結値と凍結済みの構造の検査に照合する."""
    key = stage.plan[index]
    where = f"call {index} {key}"
    problems = shape_problems(body)
    if not problems:
        assert isinstance(body, dict)
        problems = stage.structure([skeleton(index, key, body)])
    if problems:
        msg = f"{where}: " + "; ".join(problems)
        raise SentBodyMismatchError(msg)


class ObservingTransport(httpx.AsyncBaseTransport):
    """inner transport を包み、POST の body を送信前に照合・記録する."""

    def __init__(self, inner: httpx.AsyncBaseTransport, stage: Stage) -> None:
        self.inner = inner
        self.stage = stage
        self.expected: int | None = None
        self.allow_show = False
        self.sent: dict[int, list[dict[str, Any]]] = {}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            path = request.url.path
            if path == SHOW_PATH and self.allow_show:
                pass
            elif path != CHAT_PATH:
                msg = f"unexpected POST path {path!r}"
                raise SentBodyMismatchError(msg)
            else:
                if self.expected is None:
                    msg = "chat request without an expected call"
                    raise SentBodyMismatchError(msg)
                body = json.loads(request.content)
                check_sent_body(self.stage, self.expected, body)
                self.sent.setdefault(self.expected, []).append(body)
        return await self.inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self.inner.aclose()

    def n_sent(self) -> int:
        return sum(len(v) for v in self.sent.values())


# ------------------------------------------------------------ observed


class PreflightError(RuntimeError):
    """Ollama / model / 環境の同定が使えない。run dir を作る前に止まる (label を 1 件も観測しない)."""


def _json_of(response: httpx.Response) -> object:
    if response.status_code != httpx.codes.OK:
        msg = f"{response.request.url.path} returned HTTP {response.status_code}"
        raise PreflightError(msg)
    return response.json()


def _model_digest(tags: object) -> str | None:
    if not isinstance(tags, dict):
        return None
    for m in tags.get("models", []):
        if isinstance(m, dict) and bat.MODEL in (m.get("name"), m.get("model")):
            digest = m.get("digest")
            return digest if isinstance(digest, str) and digest else None
    return None


async def read_observed(
    http: httpx.AsyncClient, observer: ObservingTransport
) -> dict[str, str]:
    """実行環境の同定 (prereg §4): Ollama の版・凍結 model の digest・chat template の sha256."""
    observer.allow_show = True
    try:
        version = _json_of(await http.get("/api/version"))["version"]  # type: ignore[index]
        digest = _model_digest(_json_of(await http.get("/api/tags")))
        show = _json_of(await http.post(SHOW_PATH, json={"model": bat.MODEL}))
        template = show["template"]  # type: ignore[index]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        msg = f"Ollama is not reachable: {type(exc).__name__}: {exc}"
        raise PreflightError(msg) from exc
    finally:
        observer.allow_show = False
    if not isinstance(version, str) or not version:
        msg = "Ollama version is missing"
        raise PreflightError(msg)
    if digest is None:
        msg = f"model {bat.MODEL!r} is not available (no digest in /api/tags)"
        raise PreflightError(msg)
    if not isinstance(template, str):
        msg = f"model {bat.MODEL!r} has no chat template in /api/show"
        raise PreflightError(msg)
    return {
        "model_digest": digest,
        "ollama_version": version,
        "template_sha256": hashlib.sha256(template.encode("utf-8")).hexdigest(),
    }


# ------------------------------------------------------------------- run


class TransportFailure(Exception):  # noqa: N818 — 再送の対象 (例外ではなく分類の名前)
    """1 回の送信が答えを返さなかった (再送する)."""


@dataclass(frozen=True)
class Reply:
    content: str
    model: object
    done_reason: object


async def send_chat(http: httpx.AsyncClient, body: dict[str, Any]) -> Reply:
    """1 回送る。transport 失敗は ``TransportFailure`` (それ以外の例外はそのまま上げる)."""
    try:
        response = await http.post(CHAT_PATH, json=body)
    except httpx.HTTPError as exc:
        msg = f"{type(exc).__name__}: {exc}"
        raise TransportFailure(msg) from exc
    if response.status_code != httpx.codes.OK:
        msg = f"HTTP {response.status_code}"
        raise TransportFailure(msg)
    try:
        payload = response.json()
    except ValueError as exc:
        msg = "non-JSON response"
        raise TransportFailure(msg) from exc
    message = payload.get("message") if isinstance(payload, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        msg = f"message.content is {type(content).__name__}, not a string"
        raise TransportFailure(msg)
    return Reply(content, payload.get("model"), payload.get("done_reason"))


@dataclass
class RunState:
    stage: Stage
    http: httpx.AsyncClient
    observer: ObservingTransport
    records_fh: TextIO
    attempts_fh: TextIO
    backoff_scale: float
    records: list[sc.Sample] = field(default_factory=list)
    lines: list[str] = field(
        default_factory=list
    )  # 書いた記録の行 (公開する bytes の正本)
    response_models: set[str] = field(default_factory=set)
    n_length: int = 0
    resends: int = 0


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _join(error: str | None, more: str) -> str:
    """来歴の error 欄に理由を足す (先の理由を消さない)."""
    return more if error is None else f"{error}; {more}"


def _write_line(fh: TextIO, obj: dict[str, Any]) -> str:
    """1 行 1 JSON。ensure_ascii=True: U+2028 / U+2029 / U+0085 を escape し、凍結 reader の
    ``splitlines()`` で 1 記録が 2 行に割れないようにする.
    """
    line = json.dumps(obj, ensure_ascii=True, sort_keys=True)
    fh.write(line + "\n")
    fh.flush()
    os.fsync(fh.fileno())
    return line


def json_text(obj: object) -> str:
    """JSON ファイルの中身 (meta.json の bytes は、この文字列の UTF-8 と一致しなければならない)."""
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def write_json_durable(path: pathlib.Path, obj: object, *, exclusive: bool) -> None:
    """Temp → flush → fsync → replace。exclusive なら既存ファイルを上書きしない."""
    if exclusive and path.exists():
        msg = f"refusing to overwrite {path}"
        raise FileExistsError(msg)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json_text(obj))
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)


async def call_with_resend(
    state: RunState, index: int, body: dict[str, Any]
) -> str | None:
    """同じ body を最大 1 + RESENDS 回送る。返り値 = content または None (解けない transport 失敗)."""
    state.observer.expected = index
    for attempt in range(1 + RESENDS):
        row: dict[str, Any] = {"call_index": index, "attempt": attempt, "at": _now()}
        reply: Reply | None
        try:
            reply = await send_chat(state.http, body)
        except TransportFailure as exc:
            row.update(outcome="transport_failure", error=str(exc))
            reply = None
        else:
            row.update(outcome="ok", model=reply.model, done_reason=reply.done_reason)
        _write_line(state.attempts_fh, row)
        if reply is not None:
            state.response_models.add(str(reply.model))
            state.n_length += reply.done_reason == "length"
            return reply.content
        if attempt < RESENDS:
            state.resends += 1
            await asyncio.sleep(BACKOFF_SCHEDULE_S[attempt] * state.backoff_scale)
    return None


def absorb(state: RunState, line: str, want: sc.Sample) -> None:
    """書いた行を、判定と同じ reader (``splitlines`` → ``load_records``) で読み戻す。1 記録で、書いた値と同じ."""
    rows = sc.load_records((line + "\n").splitlines())
    if rows != [want]:
        msg = f"written line does not read back as the record ({len(rows)} rows)"
        raise RuntimeError(msg)
    state.records.append(rows[0])
    state.lines.append(line)


async def run_calls(state: RunState, schedule: Sequence[dict[str, Any]]) -> str | None:
    """予定表を plan の順に呼ぶ。transport 失敗が解けなければ raw = null を書いて REASON_TRANSPORT."""
    for index, key in enumerate(state.stage.plan):
        raw = await call_with_resend(state, index, schedule[index])
        sent = state.observer.sent[index][-1]  # 送った body (照合を通ったもの)
        arm, r, probe_id, k = key
        rec = sc.Sample(
            call_index=index,
            arm=arm,
            replicate=r,
            probe_id=probe_id,
            k=k,
            seed=sent["options"]["seed"],
            prompt_sha256=sc.messages_sha256(sent["messages"]),
            raw=raw,
            parsed=None if raw is None else state.stage.parse(arm, raw),
        )
        line = _write_line(state.records_fh, vars(rec))
        absorb(state, line, rec)
        if (index + 1) % 100 == 0:
            _progress(f"[driver] {index + 1} calls ({_now()})")
        if raw is None:
            return REASON_TRANSPORT
    return None


def _progress(line: str) -> None:
    """進捗表示。stdout が使えない (detached 起動で閉じたハンドル等) ことで run を止めない."""
    try:
        print(line, flush=True)  # noqa: T201
    except (OSError, ValueError):
        pass


# ------------------------------------------------------------ 公開


def publication_problems(stage: Stage) -> list[str]:
    """公開前の判定: partial と meta.json を判定と同じ reader で読み戻し、凍結済みの検査にかける.

    構造・meta・完全性だけを見る (label から計算する量は見ない)。
    """
    try:
        lines = (stage.run_dir / PARTIAL_NAME).read_text(encoding="utf-8").splitlines()
        samples = sc.load_records(lines)
        meta = json.loads((stage.run_dir / META_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # RecordError を含む
        return [f"unreadable: {type(exc).__name__}: {exc}"]
    out = list(stage.structure(samples))
    out.extend(sc.meta_violations(meta, stage.reference_observed))
    keys = {(s.arm, s.replicate, s.probe_id, s.k) for s in samples}
    if len(samples) != len(stage.grid) or keys != stage.grid:
        out.append("records do not cover the frozen grid")
    if any(s.raw is None for s in samples):
        out.append("a transport failure is recorded")
    return out


def records_bytes(lines: Sequence[str]) -> bytes:
    """この run が書いた記録の bytes (partial と公開名のファイルは、これと一致しなければならない)."""
    return "".join(line + "\n" for line in lines).encode("utf-8")


def binding_problems(
    run_dir: pathlib.Path, records_name: str, records: bytes, meta: bytes
) -> list[str]:
    """ディスクの記録と meta.json が、この run が書いた bytes と一致すること (Codex HIGH-1).

    構造の検査だけでは、同じ grid の別の run の記録・別の observed の meta への差し替えを見抜けない。
    """
    out: list[str] = []
    for rel, want in ((records_name, records), (META_NAME, meta)):
        path = run_dir / rel
        if not path.is_file() or path.read_bytes() != want:
            out.append(f"{rel} differs from what this run wrote")
    return out


def publish(run_dir: pathlib.Path) -> None:
    """Partial を公開名へ rename する (commit point)。公開名が既にあれば上書きしない."""
    final = run_dir / RECORDS_NAME
    if final.exists():
        msg = f"refusing to overwrite {final}"
        raise FileExistsError(msg)
    (run_dir / PARTIAL_NAME).rename(final)


def prepare_run_dir(run_dir: pathlib.Path) -> None:
    """再開しない: 既に何かがある dir では起動しない."""
    if run_dir.exists() and any(run_dir.iterdir()):
        msg = f"run dir is not empty (no resume): {run_dir}"
        raise FileExistsError(msg)
    run_dir.mkdir(parents=True, exist_ok=True)


def _sha256(path: pathlib.Path) -> str | None:
    """ファイルの sha256。無い・読めないなら None (例外で来歴を書けなくしない。変化として異常に数える)."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    except OSError:
        return None


def _git(*args: str) -> str | None:
    """Git の stdout。実行できなければ None (「clean」に畳まない)."""
    try:
        proc = subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            cwd=str(_REPO_ROOT),
            capture_output=True,
            encoding="utf-8",
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return proc.stdout.strip()


def git_dirty() -> bool | None:
    """作業木に未 commit の変更 (untracked を含む) があるか。git が使えなければ None."""
    out = _git("status", "--porcelain")
    return None if out is None else bool(out)


# ------------------------------------------------------------ 起動の前提


def pinned(stage_name: str) -> tuple[str, ...]:
    """実走の前に commit 済みで HEAD と一致していなければならないファイル (manifest の list から作る)."""
    files = (
        *man.FROZEN_FILES,
        man.MANIFEST,
        man.DRIVER,
        man.DRIVER_HARNESS,
        man.DRIVER_TEST,
        man.DRIVER_CERT,
    )
    if stage_name == STAGE_MAIN:
        files = (*files, *man.MAIN_EVIDENCE, man.MANIFEST_MAIN)
    return tuple(dict.fromkeys(files))


def pinned_sha256(stage_name: str) -> dict[str, str | None]:
    """固定ファイルの現在の sha256 (実走の開始時と終了時に取り、変化を来歴の異常とする)."""
    return {rel: _sha256(_REPO_ROOT / rel) for rel in pinned(stage_name)}


def _run_manifest(stage_name: str) -> tuple[int, str]:
    """凍結 manifest の照合を、run.sh と同じ main・同じ引数で、この process の中で呼ぶ。返り値 = (exit code, 出力).

    子プロセスにしない (Codex 4 回目 HIGH-1、decisions DF-5): 子には門も ``_PinnedFinder`` も無く、未追跡の
    ``scripts/__init__.py`` 等が実行されても照合の最後の行は変わらない。この process の中なら、照合の結論を出すコードは
    ``executed_problems`` が同定したコード (固定ファイルの bytes)。run.sh と同じ hash seed・UTF-8 mode は
    ``interpreter_problems`` が起動の前提にする。例外 (``SystemExit`` を含む) は exit 1 と、その型と文の行に畳む
    (起動・公開のどちらでも拒否になる)。
    """
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            code = man.main(["--verify", "--stage", stage_name])
    except (Exception, SystemExit) as exc:  # noqa: BLE001 — 照合が走りきらなければ不合格
        return (
            1,
            f"{out.getvalue()}manifest check raised: {type(exc).__name__}: {exc}\n",
        )
    return code, out.getvalue()


def interpreter_problems(
    seed_path: pathlib.Path | None = None,
    environ: Mapping[str, str] | None = None,
    flags: object = None,
) -> list[str]:
    """run.sh と同じ interpreter の設定で起動したか: ``PYTHONHASHSEED`` = SEED・UTF-8 mode (decisions DF-5).

    process の中で呼ぶ manifest の照合 (``_run_manifest``) を、run.sh の照合と同じ設定で走らせる。``-E``・``-I`` の
    起動では Python が ``PYTHONHASHSEED`` を読まない (``os.environ`` には残る) ので拒否する (code-reviewer MEDIUM-3)。
    既定は ``SEED_PATH``・``os.environ``・``sys.flags`` (test は注入する)。
    """
    env = os.environ if environ is None else environ
    fl = sys.flags if flags is None else flags
    mode = getattr(fl, "utf8_mode", 0)
    problems: list[str] = []
    if getattr(fl, "ignore_environment", 0):
        problems.append(
            "not launched like run.sh: -E/-I ignores PYTHONHASHSEED and PYTHONPATH"
        )
    try:
        seed = (
            (SEED_PATH if seed_path is None else seed_path)
            .read_text(encoding="utf-8")
            .strip()
        )
    except OSError as exc:
        problems.append(f"SEED unreadable: {exc}")
    else:
        if env.get("PYTHONHASHSEED") != seed:
            problems.append(
                f"not launched like run.sh: PYTHONHASHSEED must be the SEED ({seed})"
            )
    if mode != 1:
        problems.append("not launched like run.sh: PYTHONUTF8 must be 1")
    return problems


def manifest_problems(stage_name: str) -> list[str]:
    """その段の manifest の照合が exit 0 で、最後の行がちょうど ``MANIFEST OK (stage <段>)``."""
    try:
        code, out = _run_manifest(stage_name)
    except OSError as exc:
        return [f"manifest --verify --stage {stage_name} could not run: {exc}"]
    # 最後の行は LF だけで切る。末尾の空白・空行を消さない (Codex LOW-5)。splitlines は LF 以外の区切り文字
    # (U+001C・U+0085・U+2028 等) でも割り、その後ろを捨てる (Codex 再 review LOW-1)。CRLF・CR は text mode が LF に直す
    last = out.removesuffix("\n").rsplit("\n", 1)[-1]
    want = f"MANIFEST OK (stage {stage_name})"
    if code != 0 or last != want:
        return [f"manifest --verify --stage {stage_name} did not end with {want}"]
    return []


def certification_problems(cert: pathlib.Path) -> list[str]:
    """Driver の certification が manifest の契約 (第 1 段で封印) を満たすこと."""
    try:
        obj = json.loads(cert.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [f"driver certification unreadable: {cert}"]
    return man.driver_certification_violations(obj, _REPO_ROOT)


def gate_problems(gate_path: pathlib.Path) -> list[str]:
    """本走の前提: pilot の機械判定が GO で、R と observed を持つ."""
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [f"pilot gate unreadable: {gate_path}"]
    if not isinstance(gate, dict) or gate.get("decision") != pg.DECISION_GO:
        return ["pilot gate did not decide GO"]
    if type(gate.get("R")) is not int or not isinstance(gate.get("observed"), dict):
        return ["pilot gate has no R or observed"]
    return []


def launch_problems(stage_name: str) -> list[str]:
    """実走の前提: driver が certified・固定ファイルが HEAD と一致・run.sh と同じ設定・manifest が OK (本走は gate も)."""
    problems = certification_problems(DRIVER_CERT)
    if _sha256(_DRIVER_PATH) != _DRIVER_SHA:
        problems.append("the driver on disk differs from the running driver")
    files = pinned(stage_name)
    for rel in files:
        if _git("ls-files", "--error-unmatch", rel) is None:
            problems.append(f"not tracked by git: {rel}")
    if _git("diff", "--quiet", "HEAD", "--", *files) is None:
        problems.append("pinned files differ from HEAD (or git unavailable)")
    problems.extend(interpreter_problems())
    problems.extend(manifest_problems(stage_name))
    if stage_name == STAGE_MAIN:
        problems.extend(gate_problems(GATE_PATH))
    return problems


def _module_locations(module: object) -> list[str]:
    """所在 = module の ``__spec__`` の所在と ``__file__``・``__path__``。built-in・frozen は空."""
    out = _spec_locations(getattr(module, "__spec__", None))
    file = getattr(module, "__file__", None)
    if isinstance(file, str):
        out.append(file)
    out.extend(p for p in getattr(module, "__path__", None) or () if isinstance(p, str))
    return out


def outside_problems(modules: Mapping[str, object], roots: Sequence[str]) -> list[str]:
    """``__main__`` と ``scripts.*`` 以外のモジュールが、環境の中か ``scripts`` の名前空間か (Codex 3 回目 MEDIUM-2).

    門より前に取り込まれ、``sys.modules`` に残っているものも捕まえる (import に失敗して残らないものは
    ``startup_problems`` が所在で見る)。``scripts`` は ``__file__`` が無く、探索場所が ``root/scripts`` だけの名前空間で
    なければならない (``__init__.py`` を実行していない)。
    """
    problems: list[str] = []
    namespace = [_norm(str(_REPO_ROOT / "scripts"))]
    for name in sorted(modules):
        if name == "__main__" or name.startswith("scripts."):
            continue
        module = modules[name]
        if name == "scripts":
            where = [_norm(str(p)) for p in getattr(module, "__path__", None) or ()]
            if getattr(module, "__file__", None) is not None or where != namespace:
                problems.append("scripts is not the namespace of the pinned files")
            continue
        outside = [
            loc for loc in _module_locations(module) if not _in_environment(loc, roots)
        ]
        if outside:
            problems.append(
                "run outside the pinned files and the environment: "
                f"{name} ({outside[0]})"
            )
    return problems


# site が起動時に (門より前に) 実行する customization の module 名
_STARTUP_MODULES: Final[tuple[str, ...]] = ("sitecustomize", "usercustomize")
# Windows の getpath が起動時に検索パスへ足すレジストリの key (CPython 3.11 の Modules/getpath.py の WINREG_KEY、{} = sys.winver)
_REGISTRY_KEY: Final[str] = r"SOFTWARE\Python\PythonCore\{}\PythonPath"


def _registry_paths(paths: Sequence[object], reg: Any = None) -> list[str]:
    """Windows の getpath が起動時にレジストリから検索パスへ足した entry (Codex 5 回目 HIGH-1、decisions DG-4).

    HKCU・HKLM の ``_REGISTRY_KEY`` の **子キー** の既定値は、``-E``/``-I`` でなければ venv でも常に足される。**キー自身** の
    既定値は stdlib が見つからないときだけ足されるので、空でない entry が ``paths`` (``sys.path``) にあるときだけ数える (python.org 版を
    入れた機械の既定値で、正当な起動を止めない)。読めない子キーは飛ばして次を読む (getpath は止まる = 上位集合で安全側)。
    ``reg`` の既定は winreg (起動時に getpath が import 済みの built-in、同じ process = 同じ registry view)。Windows 以外は無い。
    """
    if reg is None and sys.platform != "win32":
        return []
    r = importlib.import_module("winreg") if reg is None else reg
    key_name = _REGISTRY_KEY.format(getattr(sys, "winver", ""))
    on_path = {_norm(p) for p in paths if isinstance(p, str)}
    found: list[str] = []
    for hive in (r.HKEY_CURRENT_USER, r.HKEY_LOCAL_MACHINE):
        try:
            key = r.OpenKeyEx(hive, key_name)
        except OSError:
            continue  # key が無い hive は getpath も足さない
        try:
            i = 0
            while True:
                try:
                    sub = r.EnumKey(key, i)
                except OSError:
                    break
                i += 1
                try:
                    found += str(r.QueryValue(key, sub)).split(";")
                except OSError:  # 読めない子キーは飛ばして次へ (上位集合)
                    continue
            try:
                own = str(r.QueryValue(key, None)).split(";")
            except OSError:
                own = []
            found += [e for e in own if e and _norm(e) in on_path]
        finally:
            r.CloseKey(key)
    return found


def _user_site(site: object = None) -> str | None:
    """有効な user site の dir (site が無効にしていれば None).

    ``site`` の既定は ``sys.modules`` の site (import しない: ``-S`` の起動で site を走らせない)。
    """
    found_site = sys.modules.get("site") if site is None else site
    if not getattr(found_site, "ENABLE_USER_SITE", False):
        return None
    get = getattr(found_site, "getusersitepackages", None)
    found = get() if callable(get) else None
    return found if isinstance(found, str) else None


def startup_problems(
    paths: Sequence[object],
    roots: Sequence[str],
    user_site: str | None,
    pythonpath: str | None = None,
    registry: Sequence[str] = (),
) -> list[str]:
    """起動時に site が実行しうる、環境の外のコード (Codex 4 回目 HIGH-2・code-reviewer HIGH-2・Codex 5 回目 HIGH-1).

    import に失敗したものは ``sys.modules`` に残らないので、実行されたかを問わず所在で見る:

    * ``sitecustomize``・``usercustomize`` を ``paths`` (``sys.path``) の **各** entry で探し (import しない・門を通らない)、
      所在が環境の外なら拒否する (環境の中のものが前にあって実行されなかった外のものも拒否する = 安全側)。
    * ``PYTHONPATH`` (``pythonpath``、``-E``/``-I`` のときは None) の entry が環境の外なら拒否する。site が処理する
      ``.pth`` の import 行 (venv の ``_virtualenv.pth`` の ``import _virtualenv`` 等) は、site-packages より前にある
      PYTHONPATH の同名の module を、名前に依らず実行しうる。空の entry は cwd。
    * getpath がレジストリから足した entry (``registry``、``_registry_paths``) も、PYTHONPATH と同じ理由で名前に依らず見る。
    * user site が有効で環境の外なら、その ``.pth``。

    保証の外: 環境の ``.pth`` が足す環境の外の path (editable install の ``src`` 等) が、それより後に処理される ``.pth`` の
    import 行を横取りする経路 (今の venv は ``_virtualenv.pth`` → ``erre_sandbox.pth`` の順で、該当する import 行が無い)。
    """
    entries = [e for e in paths if isinstance(e, str)]
    problems: list[str] = []
    for entry in pythonpath.split(os.pathsep) if pythonpath else ():
        if not _in_environment(entry or os.getcwd(), roots):
            problems.append(
                f"startup code outside the environment: PYTHONPATH ({entry or '.'})"
            )
    for path in registry:
        if not _in_environment(path or os.getcwd(), roots):
            problems.append(
                f"startup code outside the environment: registry ({path or '.'})"
            )
    for name in _STARTUP_MODULES:
        specs = [importlib.machinery.PathFinder.find_spec(name, [e]) for e in entries]
        outside = [
            loc
            for spec in specs
            for loc in _spec_locations(spec)
            if not _in_environment(loc, roots)
        ]
        problems += [  # 名前ごとに 1 件
            f"startup code outside the environment: {name} ({loc})"
            for loc in outside[:1]
        ]
    if user_site is not None and not _in_environment(user_site, roots):
        site_dir = pathlib.Path(user_site)
        pth = sorted(site_dir.glob("*.pth")) if site_dir.is_dir() else []
        if pth:
            problems.append(f"startup code outside the environment: {pth[0]}")
    return problems


def executed_problems(
    stage_name: str,
    pinned_start: Mapping[str, str | None],
    modules: Mapping[str, object] | None = None,
    roots: Sequence[str] | None = None,
    paths: Sequence[object] | None = None,
    environ: Mapping[str, str] | None = None,
    registry: Sequence[str] | None = None,
) -> list[str]:
    """実行中の repo のコードが、起動の検査の前のディスクの bytes をコンパイルしたもの (Codex 再 review HIGH-1).

    driver: 実行中の code object が起動時に読んだ bytes のコンパイル結果で、その bytes が ``pinned_start`` と同じ。
    ``scripts.*`` のモジュール: ``_PinnedFinder`` が 1 回だけ読んだ bytes から実行し、その bytes が固定ファイルで
    ``pinned_start`` と同じ。その他のモジュール: 環境の中 (``outside_problems``、Codex 3 回目 MEDIUM-2)。
    起動時に site が実行しうるコード (customization・PYTHONPATH・レジストリの検索パス・user site): 環境の中
    (``startup_problems``、Codex 4 回目 HIGH-2・5 回目 HIGH-1)。
    ``main`` が起動の検査の **後** に呼ぶ (certification の検査と process の中の manifest の照合が import するものも含める)。
    ``modules`` の既定は ``sys.modules``、``roots`` の既定は ``_environment_roots()``、``paths`` の既定は ``sys.path``、
    ``environ`` の既定は ``os.environ`` (``PYTHONPATH`` を読む。``-E``/``-I`` の起動では Python が読まないので見ない)、
    ``registry`` の既定は ``_registry_paths(paths)`` (``-E``/``-I`` の起動では getpath が読まないので見ない)。
    """
    mods = sys.modules if modules is None else modules
    problems: list[str] = []
    if not _DRIVER_RUNS_ITS_BYTES:
        problems.append(
            "the running driver is not the compilation of the driver bytes it hashed"
        )
    if pinned_start.get(man.DRIVER) != _DRIVER_SHA:
        problems.append(
            "the driver on disk changed between start-up and the launch checks"
        )
    files = set(pinned(stage_name))
    for name in sorted(n for n in list(mods) if n.startswith("scripts.")):
        rel = f"scripts/{name.removeprefix('scripts.')}.py"
        loader = getattr(getattr(mods[name], "__spec__", None), "loader", None)
        sha = loader.pinned_sha256 if isinstance(loader, _PinnedLoader) else None
        if sha is None:
            problems.append(f"not run from the bytes it was hashed by: {name}")
        elif rel not in files:
            problems.append(f"run but not pinned: {rel}")
        elif sha != pinned_start.get(rel):
            problems.append(f"run bytes differ from the pinned file at start-up: {rel}")
    problems += outside_problems(mods, _environment_roots() if roots is None else roots)
    env = os.environ if environ is None else environ
    pythonpath = None if sys.flags.ignore_environment else env.get("PYTHONPATH")
    search = sys.path if paths is None else paths
    if registry is None:
        registry = [] if sys.flags.ignore_environment else _registry_paths(search)
    problems += startup_problems(
        search,
        _environment_roots() if roots is None else roots,
        _user_site(),
        pythonpath,
        registry,
    )
    return problems


# ------------------------------------------------------------------- 実行


async def final_observed(
    http: httpx.AsyncClient, observer: ObservingTransport, backoff_scale: float
) -> tuple[dict[str, str] | None, str | None]:
    """終了時の observed (再送 RESENDS 回・同じ backoff)。返り値 = (observed, 失敗の説明)."""
    error: str | None = None
    for attempt in range(1 + RESENDS):
        try:
            return await read_observed(http, observer), None
        except PreflightError as exc:
            error = f"final observed failed: {exc}"
        if attempt < RESENDS:
            await asyncio.sleep(BACKOFF_SCHEDULE_S[attempt] * backoff_scale)
    return None, error


async def run(
    stage: Stage,
    transport: httpx.AsyncBaseTransport,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    backoff_s: float = 1.0,
    pinned_start: dict[str, str | None] | None = None,
) -> str:
    """1 run を実行し、終了理由を返す.

    preflight (observed)・本走の observed の照合・予定表の事前検査は run dir を作る前 (失敗しても何も書かない)。
    非 transport の例外は来歴を書いてから再送出する。``backoff_s`` は再送の待ちに掛ける倍率 (test は 0)。
    ``pinned_start`` は起動の検査の前に取った固定ファイルの sha256 (``main`` が渡す。無ければ実走の開始時に取る)。
    """
    observer = ObservingTransport(transport, stage)
    async with httpx.AsyncClient(
        base_url=endpoint, transport=observer, timeout=TIMEOUT_S
    ) as http:
        observed = await read_observed(http, observer)
        ref = stage.reference_observed
        if ref is not None and observed != ref:
            msg = (
                f"observed environment differs from the pilot gate: {observed} != {ref}"
            )
            raise PreflightError(msg)
        schedule = build_schedule(stage)
        problems = schedule_violations(stage, schedule, observed)
        if problems:
            raise ScheduleError("; ".join(problems[:5]))
        prepare_run_dir(stage.run_dir)
        meta = meta_for(schedule, observed)
        write_json_durable(stage.run_dir / META_NAME, meta, exclusive=True)
        out = Outcome(
            started=_now(),
            pinned_start=dict(
                pinned_sha256(stage.name) if pinned_start is None else pinned_start
            ),
            observed_start=observed,
            meta_bytes=json_text(meta).encode("utf-8"),
        )
        return await _run_prepared(stage, schedule, http, observer, out, backoff_s)


@dataclass
class Outcome:
    """実走の終わりに来歴と公開を決める入力 (``run`` と ``_run_prepared`` が埋める)."""

    started: str
    pinned_start: dict[str, str | None]
    observed_start: dict[str, str]
    meta_bytes: bytes  # この run が書いた meta.json の bytes (公開の照合と来歴の正本)
    reason: str = REASON_ABORTED
    error: str | None = None
    observed_end: dict[str, str] | None = None
    state: RunState | None = None


async def _run_prepared(
    stage: Stage,
    schedule: Sequence[dict[str, Any]],
    http: httpx.AsyncClient,
    observer: ObservingTransport,
    out: Outcome,
    backoff_s: float,
) -> str:
    primary: BaseException | None = None
    try:
        with (
            (stage.run_dir / PARTIAL_NAME).open(
                "x", encoding="utf-8", newline="\n"
            ) as rf,
            (stage.run_dir / ATTEMPTS_NAME).open(
                "x", encoding="utf-8", newline="\n"
            ) as af,
        ):
            state = RunState(stage, http, observer, rf, af, backoff_s)
            out.state = state
            stop = await run_calls(state, schedule)
        # 実走中に環境が差し替わっていないこと (tag の再 pull・template の変更等)。transport 失敗で止まった
        # run は、終了時の読み取りが失敗しても分類を変えない (Ollama が落ちたままなのは transport 失敗の続き)
        observed_end, final_error = await final_observed(http, observer, backoff_s)
        out.observed_end = observed_end
        if final_error is not None:
            out.error = final_error
            if stop != REASON_TRANSPORT:
                stop = REASON_ABORTED
        out.reason = stop or REASON_COMPLETED
    except BaseException as exc:
        out.error = f"{type(exc).__name__}: {exc}"
        primary = exc
        raise
    finally:
        try:
            _finish(stage, observer, out)
        except Exception as exc:
            if primary is None:
                raise
            # 元の例外を隠さない: 来歴・公開の失敗は注記として足す
            primary.add_note(
                f"provenance / publication failed: {type(exc).__name__}: {exc}"
            )
    return out.reason


def _run_anomalies(out: Outcome) -> list[str]:
    """実走中の来歴の異常 (公開を止める): 応答の model・observed の変化."""
    models = set() if out.state is None else out.state.response_models
    anomalies: list[str] = []
    if models - {bat.MODEL}:
        anomalies.append(f"unexpected response models {sorted(models)}")
    if out.observed_end is not None and out.observed_end != out.observed_start:
        anomalies.append(
            f"observed environment changed: {out.observed_start} -> {out.observed_end}"
        )
    return anomalies


def _file_anomalies(stage: Stage, out: Outcome) -> tuple[list[str], list[str]]:
    """固定ファイルと driver の異常。返り値 = (異常, 起動時から変わった固定ファイル).

    公開時の manifest の照合と読み戻しの **後** に呼ぶ (照合の間の差し替えも捕まえる、Codex HIGH-2)。
    """
    pinned_end = pinned_sha256(stage.name)
    changed = sorted(p for p in pinned_end if pinned_end[p] != out.pinned_start.get(p))
    anomalies: list[str] = []
    if changed:
        anomalies.append(f"pinned files changed during the run: {changed}")
    if _sha256(_DRIVER_PATH) != _DRIVER_SHA:
        anomalies.append("the driver on disk differs from the running driver")
    return anomalies, changed


def _finish(stage: Stage, observer: ObservingTransport, out: Outcome) -> None:  # noqa: C901, PLR0912, PLR0915
    """来歴の異常・公開条件を判定し、来歴を書き、条件を満たせば公開する (二相).

    終了理由は ``out.reason`` に書き戻す。
    """
    reason, error, state = out.reason, out.error, out.state
    anomalies = _run_anomalies(out)
    if anomalies and reason == REASON_COMPLETED:
        reason = REASON_ABORTED
        error = _join(error, "; ".join(anomalies))
    # 公開の条件 (続き): 判定 (run.sh) が照合するその段の manifest が今も OK
    at_publication: list[str] | None = None
    if reason == REASON_COMPLETED:
        at_publication = manifest_problems(stage.name)
        if at_publication:
            reason = REASON_ABORTED
            error = _join(error, f"manifest at publication: {at_publication}")
    # 公開の最後の条件: 判定と同じ reader・凍結済みの検査で読み戻せ、bytes がこの run の書いたものと同じ
    written = records_bytes([] if state is None else state.lines)
    read_back: list[str] | None = None
    if reason == REASON_COMPLETED:
        read_back = publication_problems(stage) + binding_problems(
            stage.run_dir, PARTIAL_NAME, written, out.meta_bytes
        )
        if read_back:
            reason = REASON_ABORTED
            error = _join(error, f"read-back: {read_back}")
    late, changed = _file_anomalies(stage, out)
    anomalies += late
    if late and reason == REASON_COMPLETED:
        reason = REASON_ABORTED
        error = _join(error, "; ".join(late))
    publishable = reason == REASON_COMPLETED
    # raw = null の行 (解けない transport 失敗でだけ書く) を書いた run は計算しない。終了理由からでなく書いた事実から
    # 決める (終了時の observed の取得中に中断しても残す、Codex 再 review MEDIUM-2)
    wrote_null = state is not None and any(s.raw is None for s in state.records)
    provenance: dict[str, Any] = {
        "stage": stage.name,
        "started_at": out.started,
        "finished_at": _now(),
        # 二相の 1 相目: 公開する run も、rename が済むまでは未公開 (aborted) と書く
        "exit_reason": REASON_ABORTED if publishable else reason,
        # transport 失敗の run は計算しない (prereg §4、DD-3)。判定に渡さないので driver が書く
        "status": sc.STATUS_NOT_COMPUTED if wrote_null else None,
        "error": _join(error, PENDING_NOTE) if publishable else error,
        "anomalies": anomalies,
        "manifest_problems_at_publication": at_publication,
        "read_back_problems": read_back,
        "publishable": publishable,
        "published": False,
        "n_records": 0 if state is None else len(state.records),
        "n_sent": observer.n_sent(),
        "response_models": [] if state is None else sorted(state.response_models),
        "n_finish_length": 0 if state is None else state.n_length,
        "n_resends": 0 if state is None else state.resends,
        "observed_start": out.observed_start,
        "observed_end": out.observed_end,
        "pinned_sha256_start": out.pinned_start,
        "pinned_changed": changed,
        "git_head": _git("rev-parse", "HEAD"),
        "git_dirty": git_dirty(),
    }
    prov_path = stage.run_dir / PROVENANCE_NAME
    write_json_durable(prov_path, provenance, exclusive=True)
    if publishable:
        # commit point: 未公開の来歴 → rename → 公開済みの来歴 (どこで kill されても未公開側に倒れる)
        try:
            publish(stage.run_dir)
        except OSError as exc:
            reason = REASON_ABORTED
            provenance["error"] = _join(
                error, f"publication failed: {type(exc).__name__}: {exc}"
            )
        else:
            after = binding_problems(
                stage.run_dir, RECORDS_NAME, written, out.meta_bytes
            )
            if after:
                # rename の後に差し替わった: 3 項目を書かず (第 2 段が拒否する)、公開名からも退ける
                # (公開名に残すと run.sh が書き換えられた記録から gate を計算する、code-reviewer LOW)
                reason = REASON_ABORTED
                provenance["error"] = _join(
                    error, f"changed after the read-back: {after}"
                )
                try:
                    (stage.run_dir / RECORDS_NAME).rename(stage.run_dir / REJECTED_NAME)
                except OSError as exc:
                    provenance["error"] = _join(
                        provenance["error"], f"could not withdraw: {exc}"
                    )
            else:
                # 第 2 段が照合する 3 項目は、公開済みの来歴にだけ、保持した値から書く (DD-5、Codex HIGH-1・2)
                provenance.update(
                    exit_reason=REASON_COMPLETED,
                    error=error,
                    published=True,
                    driver_sha256=_DRIVER_SHA,
                    records_sha256=hashlib.sha256(written).hexdigest(),
                    meta_sha256=hashlib.sha256(out.meta_bytes).hexdigest(),
                )
        provenance["finished_at"] = _now()
        try:
            write_json_durable(prov_path, provenance, exclusive=False)
        except OSError as exc:
            if not provenance["published"]:
                raise
            # 公開済みでも、来歴は 1 相目 (3 項目なし) のまま残り、第 2 段が拒否する (DD-5)。
            # 第 2 段に使えない run なので completed で終えない (code-reviewer LOW)
            reason = REASON_ABORTED
            _progress(
                "[driver] published, but the final provenance was not written: "
                f"{type(exc).__name__}: {exc}"
            )
    out.reason = reason


def stage_from_gate(run_dir: pathlib.Path, gate_path: pathlib.Path) -> Stage:
    """本走の段: R と参照する observed は pilot の機械判定 (GO) から読む."""
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    return main_stage(run_dir, gate["R"], gate["observed"])


def main(argv: list[str] | None = None) -> int:
    """実走の入口。run dir と endpoint は固定 (登録外の実走経路を閉じる)."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=(STAGE_PILOT, STAGE_MAIN), required=True)
    args = ap.parse_args(argv)
    # 固定ファイルの sha256 は起動の検査の **前** に取り、実走の終わりに比べる (起動の検査の間の
    # 差し替えも捕まえる。Codex HIGH-2・code-reviewer LOW)
    pinned_start = pinned_sha256(args.stage)
    problems = launch_problems(args.stage)
    # 実行中のコードの照合は起動の検査の **後** (certification の検査が import する driver の harness も含める)
    problems += executed_problems(args.stage, pinned_start)
    if problems:
        for p in problems:
            _progress(f"[driver] refuse to launch: {p}")
        return EXIT_CODES[REASON_ABORTED]
    try:
        stage = (
            pilot_stage(PILOT_DIR)
            if args.stage == STAGE_PILOT
            else stage_from_gate(RUN_DIR, GATE_PATH)
        )
        reason = asyncio.run(
            run(stage, httpx.AsyncHTTPTransport(), pinned_start=pinned_start)
        )
    except Exception as exc:  # noqa: BLE001 — 終了理由は provenance.json に書いてある
        _progress(f"[driver] aborted: {type(exc).__name__}: {exc}")
        _progress(traceback.format_exc())  # detached で走らせても原因を追えるように
        return EXIT_CODES[REASON_ABORTED]
    _progress(f"[driver] exit_reason={reason}")
    return EXIT_CODES[reason]


if __name__ == "__main__":
    sys.exit(main())

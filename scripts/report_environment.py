"""Print a public-safe environment block for external reproduction reports.

Why this exists
----------------
``REPRODUCING.md`` asks a third party to run
``scripts/verify_committed_artifacts.py`` and paste the result into
``.github/ISSUE_TEMPLATE/reproduction-report.yml``. The claim under test is a
byte-exact replay, and byte-exact output is sensitive to variables an "OS: ..."
free-text field never captured: the checkout path (clone vs. zip, and
``core.autocrlf`` / ``core.eol``), the C runtime (glibc / musl / UCRT /
libSystem, because the six-digit float quantisation exists specifically to
absorb cross-libm drift), the CPU architecture, and the exact Python build.
Hardware fields (CPU model, core count, RAM) are collected too, but they are
diagnostic-only -- the verdict is the
verifier's exit code and its ``=== summary ===``/``[hashes]`` lines, not
anything printed here
(``REPRODUCING.md`` sections 2 and 7).

What this deliberately does not collect
----------------------------------------
This module reads **only** the keys in ``ALLOWLIST_ORDER`` below -- an
allowlist, not a denylist, because a denylist cannot promise it caught
everything it should have hidden. In
particular it never calls ``platform.node()``, ``getpass.getuser()`` or
``socket.gethostname()``, never prints a filesystem path, and reads the
process environment only to check whether ``PYTHONUTF8`` is set (never its
other variables, and never any other variable's value).

Must run everywhere, including a failed ``uv sync``
-----------------------------------------------------
This module and its ``main()`` must work with a bare
``python scripts/report_environment.py`` -- no ``uv``, no third-party import,
no import from ``erre_sandbox`` -- because it is exactly the machine a
``uv sync`` failed on that most needs to report why
(.steering/20260926-public-env-diagnostics/decisions.md D2). Every collector
below is best-effort: an unavailable command, an unreadable ``/proc`` file, or
any other failure resolves to ``"unknown"`` (or ``"unavailable"`` for
``uv.version``) rather than raising.
"""

from __future__ import annotations

import locale
import os
import platform
import re
import subprocess  # noqa: S404 -- fixed argv, best-effort diagnostics only
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

HEADER: Final[str] = "=== environment (public-safe) ==="

#: Every key this module ever emits, in the order they are printed. The test
#: suite keeps its own literal copy of this set rather than importing it, so
#: that copy is the frozen contract and this tuple cannot drift from it
#: unnoticed (memory ``feedback_negative_fixture_must_not_be_self_referential``:
#: a check must not be defined from the thing it is checking).
ALLOWLIST_ORDER: Final[tuple[str, ...]] = (
    "os.name",
    "os.release",
    "os.version",
    "os.arch",
    "c_runtime",
    "python.version",
    "python.implementation",
    "uv.version",
    "encoding.locale_preferred",
    "encoding.stdout",
    "encoding.pythonutf8",
    "source.git_checkout",
    "source.git_version",
    "source.core_autocrlf",
    "source.core_eol",
    "source.commit",
    "source.tree_clean",
    "hardware.cpu_model",
    "hardware.cpu_logical_count",
    "hardware.ram_gb",
)

_SUBPROCESS_TIMEOUT: Final[float] = 10.0

# This file lives at ``scripts/report_environment.py``; its grandparent
# directory is the repository root. Used only as a subprocess ``cwd`` and for
# ``.git`` presence checks -- never printed, so it is not a path leak.
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]


def _try(fn: Callable[[], str], *, default: str = "unknown") -> str:
    """Run ``fn``, falling back to ``default`` on any exception or empty value.

    Every public collector is wrapped through this so a single unexpected
    platform quirk degrades one field instead of crashing the whole report.
    """
    try:
        value = fn()
    except Exception:  # noqa: BLE001 -- best-effort diagnostics, never raise
        return default
    return value if value else default


def _run(argv: Sequence[str], *, timeout: float = _SUBPROCESS_TIMEOUT) -> str | None:
    """Run a fixed argv and return stripped stdout, or ``None`` on any failure."""
    try:
        completed = subprocess.run(  # noqa: S603 -- argv is always a literal list
            list(argv),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    output = completed.stdout.strip()
    return output or None


# --------------------------------------------------------------------------- #
# os.* / python.* / uv.*
# --------------------------------------------------------------------------- #


def _os_name() -> str:
    return platform.system()


def _os_release() -> str:
    return platform.release()


def _os_version() -> str:
    return platform.version()


def _os_arch() -> str:
    return platform.machine()


def _python_version() -> str:
    # ``sys.version`` is documented as a single display line; normalising any
    # embedded newline keeps the rendered block to one ``key: value`` per line.
    return sys.version.replace("\n", " ")


def _python_implementation() -> str:
    return platform.python_implementation()


def _uv_version() -> str:
    value = _run(["uv", "--version"])
    return value if value is not None else "unavailable"


# --------------------------------------------------------------------------- #
# encoding.*
# --------------------------------------------------------------------------- #


def _encoding_locale_preferred() -> str:
    return locale.getpreferredencoding(False)


def _encoding_stdout() -> str:
    encoding = sys.stdout.encoding
    return encoding if encoding else "unknown"


def _encoding_pythonutf8() -> str:
    # Only the set/unset state of this one variable -- never its siblings, and
    # never any other environment variable (module docstring, D3).
    value = os.environ.get("PYTHONUTF8")
    return "unset" if value is None else f"set={value}"


# --------------------------------------------------------------------------- #
# source.* (git)
# --------------------------------------------------------------------------- #


def _source_git_checkout() -> str:
    return "yes" if _is_own_checkout() else "no"


def _is_own_checkout() -> bool:
    # A ZIP/Zenodo copy unpacked *inside* some other git repository would
    # otherwise answer every ``git`` query below with that outer repository's
    # commit and status. Only this tree's own ``.git`` counts.
    return (_REPO_ROOT / ".git").exists()


_NOT_A_CHECKOUT: Final[str] = "n/a (not a git checkout)"


def _source_git_version() -> str:
    value = _run(["git", "--version"])
    return value if value is not None else "unknown"


def _git_config_get(key: str) -> str:
    """``git config --get <key>``, distinguishing "unset" from "unknown".

    Exit code 1 means the key is legitimately absent (``"unset"``); any other
    failure (no ``git``, no repository, timeout) is genuinely undeterminable
    (``"unknown"``).
    """
    try:
        completed = subprocess.run(  # noqa: S603, S607 -- fixed argv
            ["git", "config", "--get", key],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if completed.returncode == 0:
        value = completed.stdout.strip()
        return value if value else "unset"
    if completed.returncode == 1:
        return "unset"
    return "unknown"


def _source_core_autocrlf() -> str:
    if not _is_own_checkout():
        return _NOT_A_CHECKOUT
    return _git_config_get("core.autocrlf")


def _source_core_eol() -> str:
    if not _is_own_checkout():
        return _NOT_A_CHECKOUT
    return _git_config_get("core.eol")


def _source_commit() -> str:
    if not _is_own_checkout():
        return _NOT_A_CHECKOUT
    try:
        completed = subprocess.run(  # noqa: S603, S607 -- fixed argv
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    value = completed.stdout.strip()
    return value if value else "unknown"


def _source_tree_clean() -> str:
    if not _is_own_checkout():
        return _NOT_A_CHECKOUT
    # ``--untracked-files=no``: a reporter's own stray files (build output, an
    # editor swap file) must not paint an otherwise-clean checkout as dirty
    # (decisions.md / the task spec for this field, explicitly).
    try:
        completed = subprocess.run(  # noqa: S603, S607 -- fixed argv
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    return "yes" if completed.stdout.strip() == "" else "no"


# --------------------------------------------------------------------------- #
# c_runtime (best effort, OS-specific)
# --------------------------------------------------------------------------- #


def _musl_version() -> str | None:
    """Best-effort musl detection.

    musl's ``ldd --version`` writes to stderr and typically exits non-zero,
    unlike glibc's -- so this cannot reuse ``_run``, which treats a non-zero
    exit as failure.
    """
    try:
        completed = subprocess.run(  # noqa: S603, S607 -- fixed argv
            ["ldd", "--version"],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    combined = f"{completed.stdout}\n{completed.stderr}"
    if "musl" not in combined.lower():
        return None
    for line in combined.splitlines():
        if "musl" in line.lower():
            return line.strip()
    return "musl"


def _c_runtime() -> str:
    system = platform.system()
    if system == "Linux":
        lib, version = platform.libc_ver()
        if lib:
            return f"{lib} {version}".strip()
        musl = _musl_version()
        return musl if musl is not None else "unknown"
    if system == "Darwin":
        return "macOS libSystem"
    if system == "Windows":
        # CPython's official Windows builds have linked the Universal CRT
        # since 3.5; ``sys.version`` also carries the MSC toolset used to
        # build this interpreter, which is the closest obtainable detail
        # without an extra dependency.
        match = re.search(r"MSC v\.(\d+)", sys.version)
        return f"UCRT (MSC v.{match.group(1)})" if match else "windows"
    return "unknown"


# --------------------------------------------------------------------------- #
# hardware.* (diagnostic-only)
# --------------------------------------------------------------------------- #


def _hardware_cpu_model() -> str:
    system = platform.system()
    if system == "Linux":
        try:
            text = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "unknown"
        for wanted in ("model name", "Hardware", "Processor"):
            for line in text.splitlines():
                if line.startswith(wanted):
                    _, _, value = line.partition(":")
                    value = value.strip()
                    if value:
                        return value
        return "unknown"
    if system == "Darwin":
        value = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
        return value if value is not None else "unknown"
    if system == "Windows":
        value = platform.processor()
        return value if value else "unknown"
    return "unknown"


def _hardware_cpu_logical_count() -> str:
    count = os.cpu_count()
    return str(count) if count else "unknown"


def _hardware_ram_gb() -> str:
    system = platform.system()
    if system == "Linux":
        try:
            text = Path("/proc/meminfo").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "unknown"
        for line in text.splitlines():
            if line.startswith("MemTotal:"):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    kib = int(parts[1])
                    return f"{kib / (1024 * 1024):.1f}"
        return "unknown"
    if system == "Darwin":
        value = _run(["sysctl", "-n", "hw.memsize"])
        if value is not None and value.isdigit():
            return f"{int(value) / (1024**3):.1f}"
        return "unknown"
    if system == "Windows":
        return _windows_ram_gb()
    return "unknown"


def _windows_ram_gb() -> str:
    """``GlobalMemoryStatusEx`` via ``ctypes`` -- no third-party dependency."""
    try:
        import ctypes
        import ctypes.wintypes

        class _MemoryStatusEx(ctypes.Structure):
            _fields_ = (
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            )

        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(_MemoryStatusEx)
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return "unknown"
        return f"{status.ullTotalPhys / (1024**3):.1f}"
    except Exception:  # noqa: BLE001 -- best-effort diagnostics, never raise
        return "unknown"


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

_COLLECTORS: Final[dict[str, tuple[Callable[[], str], str]]] = {
    "os.name": (_os_name, "unknown"),
    "os.release": (_os_release, "unknown"),
    "os.version": (_os_version, "unknown"),
    "os.arch": (_os_arch, "unknown"),
    "c_runtime": (_c_runtime, "unknown"),
    "python.version": (_python_version, "unknown"),
    "python.implementation": (_python_implementation, "unknown"),
    "uv.version": (_uv_version, "unavailable"),
    "encoding.locale_preferred": (_encoding_locale_preferred, "unknown"),
    "encoding.stdout": (_encoding_stdout, "unknown"),
    "encoding.pythonutf8": (_encoding_pythonutf8, "unknown"),
    "source.git_checkout": (_source_git_checkout, "unknown"),
    "source.git_version": (_source_git_version, "unknown"),
    "source.core_autocrlf": (_source_core_autocrlf, "unknown"),
    "source.core_eol": (_source_core_eol, "unknown"),
    "source.commit": (_source_commit, "unknown"),
    "source.tree_clean": (_source_tree_clean, "unknown"),
    "hardware.cpu_model": (_hardware_cpu_model, "unknown"),
    "hardware.cpu_logical_count": (_hardware_cpu_logical_count, "unknown"),
    "hardware.ram_gb": (_hardware_ram_gb, "unknown"),
}


def collect() -> dict[str, str]:
    """Collect every allowlisted key. Never raises; unknowns fall back per key."""
    return {
        key: _try(fn, default=default) for key, (fn, default) in _COLLECTORS.items()
    }


def render(data: Mapping[str, str]) -> str:
    """Render ``data`` as the public-safe block, header first, allowlist order."""
    lines = [HEADER]
    lines.extend(f"{key}: {data.get(key, 'unknown')}" for key in ALLOWLIST_ORDER)
    return "\n".join(lines)


def main() -> int:
    print(render(collect()))
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point
    sys.exit(main())

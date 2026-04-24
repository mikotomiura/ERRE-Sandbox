"""CLI sub-commands for the ``erre-sandbox`` entry point.

Each module in this package exposes a pair of public symbols for
``erre_sandbox.__main__`` to wire up:

* ``register(subparsers)`` — attach this sub-command's argparse parser to the
  root subparsers object.
* ``run(args) -> int`` — execute the sub-command given parsed ``argparse.Namespace``
  and return a POSIX exit code.

Keeping sub-commands in their own modules keeps ``__main__`` thin and lets
each sub-command own its own flags / validation without growing a single
monolithic parser.
"""

from __future__ import annotations

from erre_sandbox.cli import export_log

__all__ = ["export_log"]

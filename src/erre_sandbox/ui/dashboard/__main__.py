"""CLI entry point: ``python -m erre_sandbox.ui.dashboard``.

Starts uvicorn on ``localhost:${ERRE_DASHBOARD_PORT:-8001}`` and serves the
stub-mode dashboard (see server.py).
"""

from __future__ import annotations

import os

import uvicorn

from erre_sandbox.ui.dashboard.server import create_app


def main() -> None:
    port = int(os.environ.get("ERRE_DASHBOARD_PORT", "8001"))
    host = os.environ.get("ERRE_DASHBOARD_HOST", "127.0.0.1")
    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

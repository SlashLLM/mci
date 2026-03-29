#!/usr/bin/env python3
"""API container startup: wait for Postgres, migrate, seed, exec uvicorn (no shell — avoids Windows CRLF issues)."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time


def wait_postgres() -> None:
    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    for _ in range(90):
        try:
            s = socket.create_connection((host, port), 2)
            s.close()
            print("[api] PostgreSQL is up", flush=True)
            return
        except OSError:
            time.sleep(1)
    print("[api] PostgreSQL not reachable", flush=True)
    sys.exit(1)


def main() -> None:
    wait_postgres()

    print("[api] Running migrations...", flush=True)
    r = subprocess.run(["alembic", "upgrade", "head"], check=False)
    if r.returncode != 0:
        sys.exit(r.returncode)

    if os.environ.get("RUN_SEED", "true").lower() not in ("0", "false", "no"):
        print("[api] Seeding demo data (RUN_SEED=false to skip)...", flush=True)
        s = subprocess.run([sys.executable, "-m", "app.scripts.seed_demo"], check=False)
        if s.returncode != 0:
            print("[api] Seed exited with", s.returncode, "(often OK if data exists)", flush=True)

    print("[api] Starting uvicorn...", flush=True)
    os.execvp("uvicorn", ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])


if __name__ == "__main__":
    main()

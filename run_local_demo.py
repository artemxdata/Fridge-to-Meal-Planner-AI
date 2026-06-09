"""Local demo entrypoint that runs with SQLite even when .env points to Docker/PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent
LOCAL_DATABASE_URL = f"sqlite+aiosqlite:///{(PROJECT_ROOT / 'data' / 'local_app.db').as_posix()}"

os.environ["DATABASE_URL"] = LOCAL_DATABASE_URL
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ.setdefault("APP_ENV", "development")

from app.main import app  # noqa: E402

__all__ = ["app"]


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"Fridge-to-Meal Planner AI local demo: http://127.0.0.1:{port}/pwa")
    print(f"SQLite database: {PROJECT_ROOT / 'data' / 'local_app.db'}")
    uvicorn.run("run_local_demo:app", host="127.0.0.1", port=port, reload=False)

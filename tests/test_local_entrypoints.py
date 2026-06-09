import subprocess
import sys


def test_local_demo_entrypoint_uses_sqlite_before_app_import() -> None:
    code = """
import os
os.environ["DATABASE_URL"] = "postgresql://user:pass@127.0.0.1:5432/fridge"
os.environ["AUTO_CREATE_TABLES"] = "false"
import run_local_demo
from app.config import settings
assert settings.database_url.startswith("sqlite+aiosqlite:///")
assert settings.auto_create_tables is True
assert run_local_demo.app.title == "Fridge-to-Meal Planner AI"
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

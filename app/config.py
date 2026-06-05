from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _csv_env(name: str, default: str) -> tuple[str, ...]:
    return tuple(value.strip() for value in os.getenv(name, default).split(",") if value.strip())


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{PROJECT_ROOT / 'data' / 'local_app.db'}")
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+asyncpg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return value


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Fridge-to-Meal Planner AI")
    app_version: str = os.getenv("APP_VERSION", "0.4.0")
    environment: str = os.getenv("APP_ENV", "development")
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(8 * 1024 * 1024)))
    max_image_pixels: int = int(os.getenv("MAX_IMAGE_PIXELS", "25000000"))
    database_url: str = _database_url()
    database_echo: bool = os.getenv("DATABASE_ECHO", "false").lower() == "true"
    auto_create_tables: bool = os.getenv("AUTO_CREATE_TABLES", "true").lower() == "true"
    cors_origins: tuple[str, ...] = _csv_env(
        "CORS_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000",
    )
    recipes_path: Path = PROJECT_ROOT / "data" / "recipes_ru.json"
    demo_path: Path = PROJECT_ROOT / "data" / "demo_scenario.json"
    frontend_path: Path = PROJECT_ROOT / "index.html"


settings = Settings()

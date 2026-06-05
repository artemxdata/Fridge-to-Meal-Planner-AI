import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_app.db"
os.environ["AUTO_CREATE_TABLES"] = "true"

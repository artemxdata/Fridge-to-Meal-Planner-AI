# Database Migrations

Alembic migrations are the production schema path.

Local development still defaults to `AUTO_CREATE_TABLES=true` for quick demos, but deployed environments should
run:

```bash
AUTO_CREATE_TABLES=false alembic upgrade head
```

The migration environment reads `DATABASE_URL` through `app.config.settings`, so the same URL format used by
FastAPI is used by Alembic.

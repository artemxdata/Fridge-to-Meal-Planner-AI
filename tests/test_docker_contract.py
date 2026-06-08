from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_docker_image_uses_migration_entrypoint() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    entrypoint = (ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")

    assert "COPY alembic.ini ./alembic.ini" in dockerfile
    assert "COPY migrations ./migrations" in dockerfile
    assert 'ENTRYPOINT ["/app/docker/entrypoint.sh"]' in dockerfile
    assert "alembic upgrade head" in entrypoint
    assert 'exec "$@"' in entrypoint


def test_compose_runs_migrations_instead_of_auto_create_tables() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    app_environment = compose["services"]["app"]["environment"]

    assert app_environment["AUTO_CREATE_TABLES"] == "false"
    assert app_environment["RUN_MIGRATIONS"] == "true"

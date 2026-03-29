import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.orm import Session


def _db_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def _with_db_name(url: str, db_name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{db_name}", parts.query, parts.fragment))


def _to_psycopg_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


BASE_DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/cortecero")
TEST_DB_URL = os.getenv("TEST_DATABASE_URL") or _with_db_name(BASE_DB_URL, f"{_db_name(BASE_DB_URL)}_test")
os.environ["DATABASE_URL"] = TEST_DB_URL

THIS_FILE = Path(__file__).resolve()
MIGRATIONS_DIR = None
for root in (THIS_FILE.parents[1], THIS_FILE.parents[2]):
    candidate = root / "db" / "migrations"
    if candidate.exists():
        MIGRATIONS_DIR = candidate
        break
if MIGRATIONS_DIR is None:
    raise RuntimeError("Migrations directory db/migrations not found for test bootstrap")
MIGRATION_FILES = sorted(MIGRATIONS_DIR.glob("*.sql"))
if not MIGRATION_FILES:
    raise RuntimeError(f"No migration files found in {MIGRATIONS_DIR}")
TEST_DB_NAME = _db_name(TEST_DB_URL)
ADMIN_DB_URL = _with_db_name(TEST_DB_URL, "postgres")

from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402


def _ensure_test_database() -> None:
    with psycopg.connect(_to_psycopg_url(ADMIN_DB_URL), autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB_NAME,)).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DB_NAME)))


def _reset_schema() -> None:
    with psycopg.connect(_to_psycopg_url(TEST_DB_URL), autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE;")
        conn.execute("CREATE SCHEMA public;")
        conn.execute("GRANT ALL ON SCHEMA public TO CURRENT_USER;")
        for migration_file in MIGRATION_FILES:
            conn.execute(migration_file.read_text(encoding="utf-8"))


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_database() -> None:
    _ensure_test_database()


@pytest.fixture(autouse=True)
def _reset_db_per_test() -> None:
    engine.dispose()
    _reset_schema()
    seed()
    yield
    engine.dispose()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

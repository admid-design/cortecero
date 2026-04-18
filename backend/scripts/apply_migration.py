from pathlib import Path
import os

import psycopg2


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    # Strip SQLAlchemy driver prefix so psycopg2.connect() accepts the URL
    if database_url.startswith("postgresql+psycopg2://"):
        database_url = database_url.replace("postgresql+psycopg2://", "postgresql://", 1)
    elif database_url.startswith("postgresql+psycopg://"):
        database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    project_root = Path(__file__).resolve().parents[1]
    migrations_dir = project_root / "db" / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        raise SystemExit(f"No migration files found in {migrations_dir}")

    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    try:
        cursor = conn.cursor()
        for migration_file in migration_files:
            sql_text = migration_file.read_text(encoding="utf-8")
            cursor.execute(sql_text)
            print(f"Applied migration: {migration_file}")
    finally:
        conn.close()

    print(f"Applied {len(migration_files)} migration files")


if __name__ == "__main__":
    main()

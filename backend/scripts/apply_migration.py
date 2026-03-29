from pathlib import Path
import os

import psycopg


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    if database_url.startswith("postgresql+psycopg://"):
        database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    project_root = Path(__file__).resolve().parents[1]
    migrations_dir = project_root / "db" / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        raise SystemExit(f"No migration files found in {migrations_dir}")

    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            for migration_file in migration_files:
                sql_text = migration_file.read_text(encoding="utf-8")
                cur.execute(sql_text)
                print(f"Applied migration: {migration_file}")

    print(f"Applied {len(migration_files)} migration files")


if __name__ == "__main__":
    main()

from pathlib import Path
import os

import psycopg


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    if database_url.startswith("postgresql+psycopg://"):
        database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    project_root = Path(__file__).resolve().parents[2]
    migration_file = project_root / "db" / "migrations" / "001_init.sql"
    sql = migration_file.read_text(encoding="utf-8")

    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)

    print(f"Applied migration: {migration_file}")


if __name__ == "__main__":
    main()

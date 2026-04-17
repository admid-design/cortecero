from collections.abc import Generator
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from app.config import settings


# In serverless environments (Vercel/Lambda), connection pooling causes EBUSY
# errors because pool connections are tied to a specific process and become
# invalid after a Lambda cold-start or process fork. Use NullPool in serverless.
_is_serverless = os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")

engine = create_engine(
    settings.database_url,
    poolclass=NullPool if _is_serverless else QueuePool,
    **({"pool_pre_ping": True} if not _is_serverless else {}),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from collections.abc import Generator

from sqlalchemy import Connection, create_engine

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)


def get_db() -> Generator[Connection, None, None]:
    with engine.connect() as conn:
        yield conn

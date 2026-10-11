import os
from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings
from app.timing import register_timing_listeners


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
register_timing_listeners(engine)


class Base(DeclarativeBase):
    pass


if os.getenv("SKIP_DB_INIT") != "1":

    @event.listens_for(engine, "connect")
    def set_search_path(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute(f"SET search_path TO {settings.schema_name}, public")
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_schema() -> None:
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {settings.schema_name}"))
        conn.execute(text(f"SET search_path TO {settings.schema_name}, public"))
        Base.metadata.create_all(bind=conn)

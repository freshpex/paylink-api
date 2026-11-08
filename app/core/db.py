from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool
from app.core.config import settings


class Base(DeclarativeBase):
    pass


def database_engine(url):
    options = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    elif url.startswith("postgresql+psycopg://"):
        # Neon supplies the connection pool. Avoid retaining idle connections in
        # serverless instances and bound cold-start connection failures.
        options["poolclass"] = NullPool
        options["connect_args"] = {"connect_timeout": 10, "prepare_threshold": None}
    return create_engine(url, **options)


engine = database_engine(settings().database_url)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db

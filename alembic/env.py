from alembic import context
from app.core.config import settings
from app.core.db import Base, database_engine
from app.models import entities  # noqa: F401


def run():
    config = settings()
    url = config.database_url_unpooled or config.database_url
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=Base.metadata, literal_binds=True, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = database_engine(url)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run()

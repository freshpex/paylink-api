from alembic import context
from app.core.db import Base, engine
from app.models import entities  # noqa: F401


def run():
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run()

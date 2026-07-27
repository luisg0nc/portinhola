from sqlalchemy import create_engine

import portinhola.db.models  # noqa: F401  (registers models on Base.metadata)
from alembic import context
from portinhola.config import Config
from portinhola.db.base import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    config = Config()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(config.database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()

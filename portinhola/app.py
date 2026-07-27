from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from portinhola.api import health
from portinhola.config import Config
from portinhola.db.base import make_engine


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config()
    config.data_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Portinhola")
    app.state.config = config
    app.state.engine = make_engine(config.database_url)
    app.state.sessionmaker = sessionmaker(bind=app.state.engine)

    app.include_router(health.router, prefix="/api")
    return app

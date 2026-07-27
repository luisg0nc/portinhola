from fastapi import FastAPI

from portinhola.api import health
from portinhola.config import Config


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config()
    config.data_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Portinhola")
    app.state.config = config

    app.include_router(health.router, prefix="/api")
    return app

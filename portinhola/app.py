from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from portinhola.api import (
    alerts,
    app_settings,
    auth,
    bills,
    consumption,
    dashboard,
    health,
    jobs,
    supply_points,
)
from portinhola.config import Config
from portinhola.core.secrets import load_or_create_app_key
from portinhola.db.base import make_engine
from portinhola.static import mount_frontend


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config()
    config.data_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Portinhola")
    app.state.config = config
    app.state.app_key = load_or_create_app_key(config.data_dir)
    app.state.engine = make_engine(config.database_url)
    app.state.sessionmaker = sessionmaker(bind=app.state.engine)

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api/auth")
    app.include_router(app_settings.router, prefix="/api/settings")
    app.include_router(supply_points.router, prefix="/api/supply-points")
    app.include_router(bills.router, prefix="/api/bills")
    app.include_router(dashboard.router, prefix="/api/dashboard")
    app.include_router(jobs.router, prefix="/api/jobs")
    app.include_router(alerts.router, prefix="/api/alerts")
    app.include_router(consumption.router, prefix="/api/consumption")

    if config.enable_scheduler:
        from portinhola.core.scheduler import setup_scheduler

        setup_scheduler(app)
    mount_frontend(app)
    return app

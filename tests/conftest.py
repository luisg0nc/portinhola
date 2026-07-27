import pytest
from fastapi.testclient import TestClient

from portinhola.app import create_app
from portinhola.config import Config
from portinhola.db.base import Base


@pytest.fixture
def app(tmp_path):
    application = create_app(Config(data_dir=tmp_path))
    Base.metadata.create_all(application.state.engine)

    from portinhola.api import auth as auth_api

    auth_api._failed_logins.clear()
    return application


@pytest.fixture
def client(app):
    return TestClient(app)

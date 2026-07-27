from fastapi.testclient import TestClient

from portinhola.app import create_app
from portinhola.config import Config


def test_health(tmp_path) -> None:
    client = TestClient(create_app(Config(data_dir=tmp_path, enable_scheduler=False)))
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

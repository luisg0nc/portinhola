from fastapi.testclient import TestClient

import portinhola.static
from portinhola.app import create_app
from portinhola.config import Config


def test_spa_fallback_and_assets(tmp_path, monkeypatch) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>portinhola-shell</html>")
    (dist / "favicon.png").write_bytes(b"png-bytes")
    monkeypatch.setattr(portinhola.static, "FRONTEND_DIR", dist)

    client = TestClient(create_app(Config(data_dir=tmp_path / "data")))

    assert "portinhola-shell" in client.get("/").text
    assert "portinhola-shell" in client.get("/bills").text  # SPA fallback
    assert client.get("/favicon.png").content == b"png-bytes"
    assert client.get("/api/health").json() == {"status": "ok"}  # API untouched


def test_missing_frontend_dir_is_tolerated(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(portinhola.static, "FRONTEND_DIR", tmp_path / "nope")
    client = TestClient(create_app(Config(data_dir=tmp_path / "data")))
    assert client.get("/api/health").status_code == 200

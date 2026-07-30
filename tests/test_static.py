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

    client = TestClient(create_app(Config(data_dir=tmp_path / "data", enable_scheduler=False)))

    assert "portinhola-shell" in client.get("/").text
    assert "portinhola-shell" in client.get("/bills").text  # SPA fallback
    assert client.get("/favicon.png").content == b"png-bytes"
    assert client.get("/api/health").json() == {"status": "ok"}  # API untouched


def test_missing_frontend_dir_is_tolerated(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(portinhola.static, "FRONTEND_DIR", tmp_path / "nope")
    client = TestClient(create_app(Config(data_dir=tmp_path / "data", enable_scheduler=False)))
    assert client.get("/api/health").status_code == 200


def test_cache_headers_and_missing_asset_404(tmp_path, monkeypatch) -> None:
    """A stale index.html must never be served from cache after a deploy,
    hashed chunks may cache forever, and a missing chunk must 404 — the
    old index.html fallback fed HTML to module loads and killed the page."""
    dist = tmp_path / "dist"
    (dist / "_app" / "immutable" / "entry").mkdir(parents=True)
    (dist / "index.html").write_text("<html>portinhola-shell</html>")
    (dist / "_app" / "immutable" / "entry" / "start.abc123.js").write_text("//js")
    monkeypatch.setattr(portinhola.static, "FRONTEND_DIR", dist)

    client = TestClient(create_app(Config(data_dir=tmp_path / "data", enable_scheduler=False)))

    assert client.get("/").headers["cache-control"] == "no-cache"
    assert client.get("/calculator").headers["cache-control"] == "no-cache"
    chunk = client.get("/_app/immutable/entry/start.abc123.js")
    assert chunk.status_code == 200
    assert chunk.headers["cache-control"] == "public, max-age=31536000, immutable"
    # chunk from a previous deploy: honest 404, not index.html-as-JS
    assert client.get("/_app/immutable/entry/start.old999.js").status_code == 404

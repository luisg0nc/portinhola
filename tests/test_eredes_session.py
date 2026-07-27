import json

from portinhola.core.crypto import decrypt, encrypt
from portinhola.integrations.eredes_session import clear, load_cookies, save_cookies

KEY = b"k" * 32


def test_crypto_roundtrip() -> None:
    data = b"secret payload"
    token = encrypt(KEY, data)
    assert token != data
    assert decrypt(KEY, token) == data


def test_cookie_store_roundtrip(app) -> None:
    cookies = [{"name": "session", "value": "abc", "domain": ".e-redes.pt"}]
    with app.state.sessionmaker() as db:
        assert load_cookies(db, KEY) is None
        save_cookies(db, KEY, cookies)
    with app.state.sessionmaker() as db:
        loaded = load_cookies(db, KEY)
        assert loaded == cookies
        clear(db)
        assert load_cookies(db, KEY) is None


def test_assisted_login_ws_flow(client, monkeypatch) -> None:
    from portinhola.integrations import eredes_login

    page_html = (
        "<html><head><title>login</title></head><body>"
        "<button style='width:200px;height:100px' "
        "onclick=\"document.title='DONE'\">enter</button></body></html>"
    )
    monkeypatch.setattr(eredes_login, "LOGIN_URL", "data:text/html," + page_html)

    async def title_is_done(page) -> bool:
        return await page.title() == "DONE"

    monkeypatch.setattr(eredes_login, "is_logged_in", title_is_done)

    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})
    with client.websocket_connect("/api/eredes/login") as ws:
        first = json.loads(ws.receive_text())
        assert first["type"] == "frame"
        assert first["w"] > 0
        ws.send_text(json.dumps({"type": "click", "x": 100, "y": 50}))
        message = None
        for _ in range(50):
            message = json.loads(ws.receive_text())
            if message["type"] != "frame":
                break
        assert message is not None
        assert message["type"] == "success"

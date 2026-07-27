import time


def _login(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})


def test_run_and_list_jobs(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PORTINHOLA_DATA_DIR", str(tmp_path))
    _login(client)
    assert client.post("/api/jobs/heartbeat/run").status_code == 202
    deadline = time.time() + 20
    jobs = []
    while time.time() < deadline:
        jobs = client.get("/api/jobs").json()
        if jobs and jobs[0]["status"] == "success":
            break
        time.sleep(0.3)
    assert jobs and jobs[0]["type"] == "heartbeat"
    assert jobs[0]["status"] == "success"


def test_run_unknown_job_rejected(client) -> None:
    _login(client)
    assert client.post("/api/jobs/nope/run").status_code == 404


def test_alerts_list_and_mark_read(client, app) -> None:
    _login(client)
    from portinhola.core.alerts import raise_alert

    with app.state.sessionmaker() as db:
        raise_alert(db, "job_failed", "something broke")
    alerts = client.get("/api/alerts?unread=true").json()
    assert len(alerts) == 1
    alert_id = alerts[0]["id"]
    assert client.post(f"/api/alerts/{alert_id}/read").status_code == 204
    assert client.get("/api/alerts?unread=true").json() == []
    assert len(client.get("/api/alerts").json()) == 1


def test_settings_extended_roundtrip(client) -> None:
    _login(client)
    res = client.put(
        "/api/settings",
        json={"language": "pt", "apprise_urls": "ntfy://topic", "eredes_sync_time": "06:30"},
    )
    assert res.status_code == 204
    data = client.get("/api/settings").json()
    assert data["apprise_urls"] == "ntfy://topic"
    assert data["eredes_sync_time"] == "06:30"


def test_test_notification_without_urls(client) -> None:
    _login(client)
    res = client.post("/api/settings/test-notification")
    assert res.status_code == 200
    assert res.json() == {"sent": False}

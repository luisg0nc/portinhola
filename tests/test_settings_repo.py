from portinhola.db.settings_repo import get_setting, set_setting


def test_get_missing_setting_returns_none(app) -> None:
    with app.state.sessionmaker() as db:
        assert get_setting(db, "nope") is None


def test_set_then_get_setting(app) -> None:
    with app.state.sessionmaker() as db:
        set_setting(db, "language", "pt")
    with app.state.sessionmaker() as db:
        assert get_setting(db, "language") == "pt"


def test_set_overwrites_existing(app) -> None:
    with app.state.sessionmaker() as db:
        set_setting(db, "language", "pt")
        set_setting(db, "language", "en")
    with app.state.sessionmaker() as db:
        assert get_setting(db, "language") == "en"

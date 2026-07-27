from sqlalchemy.orm import Session

from portinhola.db.settings_repo import get_setting


def send(db: Session, title: str, body: str) -> bool:
    urls_raw = get_setting(db, "apprise_urls") or ""
    urls = [u.strip() for u in urls_raw.splitlines() if u.strip()]
    if not urls:
        return False

    import apprise

    notifier = apprise.Apprise()
    for url in urls:
        notifier.add(url)
    return bool(notifier.notify(title=title, body=body))

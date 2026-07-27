from collections.abc import Callable

from sqlalchemy.orm import Session

JobFunc = Callable[[Session], str]

JOB_TYPES: dict[str, JobFunc] = {}


def job(name: str) -> Callable[[JobFunc], JobFunc]:
    def decorator(func: JobFunc) -> JobFunc:
        JOB_TYPES[name] = func
        return func

    return decorator


@job("heartbeat")
def heartbeat(db: Session) -> str:
    return "ok"

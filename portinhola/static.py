from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

FRONTEND_DIR = Path(__file__).parent / "frontend_dist"


def mount_frontend(app: FastAPI) -> None:
    frontend_dir = FRONTEND_DIR
    if not frontend_dir.exists():
        return

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = frontend_dir / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(frontend_dir / "index.html")

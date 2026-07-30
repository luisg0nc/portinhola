from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

FRONTEND_DIR = Path(__file__).parent / "frontend_dist"

# SvelteKit content-hashes everything under _app/immutable — safe to cache
# forever. Everything else (index.html above all) must be revalidated on
# every load: a stale index.html kept across a deploy references chunk
# hashes that no longer exist and breaks the app.
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
STATIC_CACHE = "public, max-age=86400"  # icon, manifest, fonts — un-hashed
HTML_CACHE = "no-cache"


def mount_frontend(app: FastAPI) -> None:
    frontend_dir = FRONTEND_DIR
    if not frontend_dir.exists():
        return

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = frontend_dir / path
        if path and candidate.is_file():
            if path.startswith("_app/immutable/"):
                cache = IMMUTABLE_CACHE
            elif path.endswith(".html"):
                cache = HTML_CACHE
            else:
                cache = STATIC_CACHE
            return FileResponse(candidate, headers={"Cache-Control": cache})
        # A missing asset must 404 — falling back to index.html here feeds
        # HTML to <script type="module"> loads, which kills the page far
        # more confusingly than a clean 404 would.
        if "." in path.rsplit("/", maxsplit=1)[-1]:
            raise HTTPException(status_code=404)
        return FileResponse(
            frontend_dir / "index.html", headers={"Cache-Control": HTML_CACHE}
        )

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter(tags=["pages"])

DIST_DIR = Path(__file__).resolve().parents[2] / "static" / "dist"
INDEX_HTML = DIST_DIR / "index.html"


def _spa_index():
    if not INDEX_HTML.is_file():
        return HTMLResponse(
            "<h1>Frontend not built</h1><p>Run <code>cd frontend && pnpm install && pnpm run build</code>.</p>",
            status_code=503,
        )
    return FileResponse(INDEX_HTML)


@router.get("/")
@router.get("/mfa")
@router.get("/admin/events")
def spa_routes():
    return _spa_index()

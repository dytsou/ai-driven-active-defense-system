import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.line_webhook import router as line_webhook_router
from app.api.routes.mfa import router as mfa_router
from app.api.routes.oauth import router as oauth_router
from app.api.routes.register import router as register_router
from app.api.routes.pages import router as pages_router
from app.middleware.gateway import AuthGatewayMiddleware
from app.services.redis_client import init_redis

FRONTEND_DIST = Path(__file__).resolve().parent / "static" / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"


def _should_bootstrap_database() -> bool:
    return os.getenv("DB_BOOTSTRAP_ON_START", "").lower() in {"1", "true", "yes"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _should_bootstrap_database():
        from app.db.bootstrap import bootstrap_database

        bootstrap_database()
    if not getattr(app.state, "redis", None):
        app.state.redis = init_redis()
    yield


app = FastAPI(title="Active Defense", lifespan=lifespan)
app.add_middleware(AuthGatewayMiddleware)
app.include_router(auth_router)
app.include_router(mfa_router)
app.include_router(line_webhook_router)
app.include_router(oauth_router)
app.include_router(register_router)
app.include_router(admin_router)
app.include_router(pages_router)
if FRONTEND_ASSETS.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS), name="frontend-assets")


@app.get("/health")
def health():
    return {"status": "ok"}

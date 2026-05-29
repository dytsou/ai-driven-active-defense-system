from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.middleware.gateway import AuthGatewayMiddleware
from app.services.redis_client import init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not getattr(app.state, "redis", None):
        app.state.redis = init_redis()
    yield


app = FastAPI(title="Active Defense", lifespan=lifespan)
app.add_middleware(AuthGatewayMiddleware)
app.include_router(auth_router)


@app.get("/health")
def health():
    return {"status": "ok"}

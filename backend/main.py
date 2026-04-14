from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.interfaces import router as interfaces_router
from api.profiles import router as profiles_router
from api.rules import router as rules_router
from api.schedule import router as schedule_router
from api.websocket import router as websocket_router
from core.services import services
from core.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await services.startup()
    yield
    await services.shutdown()


app = FastAPI(
    title="NetEmu API",
    description="Linux traffic-control network emulator with a lightweight web UI.",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=settings.allow_credentials,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(interfaces_router, prefix="/api/interfaces", tags=["interfaces"])
app.include_router(rules_router, prefix="/api/rules", tags=["rules"])
app.include_router(profiles_router, prefix="/api/profiles", tags=["profiles"])
app.include_router(schedule_router, prefix="/api/schedule", tags=["schedule"])
app.include_router(websocket_router, prefix="/ws", tags=["websocket"])

frontend_root = os.path.join(os.path.dirname(__file__), "..", "frontend")
static_root = os.path.join(frontend_root, "static")
if os.path.isdir(static_root):
    app.mount("/static", StaticFiles(directory=static_root), name="static")


@app.get("/", include_in_schema=False)
async def index():
    index_path = os.path.join(frontend_root, "templates", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"service": settings.app_name, "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True, log_level="info")

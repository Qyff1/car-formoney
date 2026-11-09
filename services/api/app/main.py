# -*- coding: utf-8 -*-
"""FastAPI 应用入口。

启动：在项目根目录执行
    .venv\\Scripts\\python.exe -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import UPLOAD_DIR
from .db import Base, SessionLocal, engine
from .migrations import run_migrations
from .core.seed import seed_all
from .routers import admin, analyses, auth, cases, damages, images, models_admin, pricing, quotes, reports


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    with SessionLocal() as db:
        seed_all(db)
    yield


app = FastAPI(
    title="车辆损伤智能定损系统 API",
    version="1.0.0",
    description="图像分析 + 人工确认 + 规则定价",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/files", StaticFiles(directory=UPLOAD_DIR), name="files")

for module in (auth, admin, cases, images, analyses, damages, quotes, reports, pricing, models_admin):
    app.include_router(module.router)


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok"}

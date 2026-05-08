from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.collector.scheduler import PollScheduler
from app.config import get_settings
from app.db.postgres import engine
from app.models import Base

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await asyncio.to_thread(Base.metadata.create_all, bind=engine)
    scheduler = PollScheduler()
    task: asyncio.Task | None = None
    if settings.collector_enabled:
        task = asyncio.create_task(scheduler.run())
    try:
        yield
    finally:
        scheduler.stop()
        if task:
            await task


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.include_router(api_router)

web_dir = Path(__file__).parent / "web"
app.mount("/static", StaticFiles(directory=web_dir), name="static")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(web_dir / "index.html")

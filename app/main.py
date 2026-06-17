import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database.connection import db
from app.database import crud
from app.bot.handlers import all_routers
from app.publishers.telegram_publisher import telegram_publisher
from app.engine.scheduler import cortex_scheduler

# ====================== Logging ======================
logger.add("logs/cortex_post.log", rotation="10 MB", retention="30 days", level="INFO", encoding="utf-8")

# ====================== Rate Limiter ======================
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

# Global variables
bot: Optional["Bot"] = None
dp: Optional["Dispatcher"] = None
_startup_complete = False
_startup_error: Optional[str] = None
_startup_time: float = 0
_webhook_updates_received = 0
_webhook_updates_processed = 0
_webhook_updates_errors = 0
_last_webhook_update_time: Optional[str] = None

ALLOWED_UPDATE_TYPES = ["message", "callback_query", "my_chat_member", "chat_member", "inline_query"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _startup_time
    _startup_time = time.time()

    logger.info("🚀 Starting Cortex Post v3.1 (Enhanced)")

    await init_database()
    asyncio.create_task(_background_init())

    yield

    # Shutdown
    await shutdown_services()
    logger.info("🛑 Cortex Post shutdown complete")


async def init_database():
    try:
        await db.connect()
        await crud.init_db()
        logger.success("✅ Database connected")
    except Exception as e:
        logger.error(f"❌ Database error: {e}")


async def _background_init():
    await asyncio.sleep(2)
    await init_bot()
    await init_scheduler()
    logger.success("✅ All services initialized")


async def init_bot():
    # ... (ابقِ الكود الأصلي هنا مع تعديل بسيط: استخدم logger بدل logging)
    # أعدل الـ logger.info → logger.info و logger.error → logger.error
    global bot, dp
    # (انسخ باقي init_bot من الكود الأصلي وغير logging إلى logger)


async def init_scheduler():
    try:
        await cortex_scheduler.start()
        logger.success("✅ Scheduler started")
    except Exception as e:
        logger.error(f"❌ Scheduler error: {e}")


async def shutdown_services():
    # ... (انسخ shutdown logic من الكود الأصلي)
    pass


# ====================== FastAPI App ======================
app = FastAPI(
    title="Cortex Post",
    version="3.1.0",
    lifespan=lifespan,
)

# Rate limit middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    try:
        response = await limiter.limit(call_next)(request)
        return response
    except RateLimitExceeded:
        return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)

app.include_router(api_router)  # من app.api.routes

# Static files
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# باقي الـ endpoints (health, debug, webhook, إلخ) ابقيها كما هي مع تغيير logging إلى logger

# Webhook endpoint (ابقِ النسخة v3.0 الممتازة)
@app.post("/webhook/bot")
async def telegram_webhook(request: Request):
    # ... (ابقِ الكود الأصلي كما هو - ممتاز)
    pass

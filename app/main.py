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

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Update

from app.config import settings
from app.database.connection import db
from app.database import crud
from app.bot.handlers import all_routers
from app.publishers.telegram_publisher import telegram_publisher
from app.engine.scheduler import cortex_scheduler
from app.core.redis import get_redis, close_redis   # إذا أنشأت الملف

# ====================== Globals ======================
bot: Optional[Bot] = None
dp: Optional[Dispatcher] = None
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
    logger.info("🚀 Starting Cortex Post v3.1 Enhanced")

    await init_database()
    asyncio.create_task(_background_init())

    yield

    await shutdown_services()
    logger.info("🛑 Shutdown complete")


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
    logger.success("✅ All services ready")


async def init_bot():
    global bot, dp, _startup_complete, _startup_error
    if not settings.is_bot_configured:
        logger.warning("BOT_TOKEN not set")
        _startup_complete = True
        return

    try:
        bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        me = await bot.get_me()
        logger.info(f"✅ Bot connected: @{me.username}")

        dp = Dispatcher(storage=MemoryStorage())
        for router in all_routers:
            dp.include_router(router)

        telegram_publisher.set_bot(bot)

        # Webhook setup...
        if settings.use_webhook:
            # (انسخ باقي webhook setup logic من النسخة القديمة)
            pass

        _startup_complete = True
    except Exception as e:
        logger.error(f"Bot init failed: {e}")
        _startup_error = str(e)


async def init_scheduler():
    try:
        await cortex_scheduler.start()
        logger.success("✅ Scheduler started")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")


async def shutdown_services():
    if bot:
        await bot.session.close()
    await close_redis()
    try:
        await db.disconnect()
    except:
        pass


# ====================== FastAPI ======================
app = FastAPI(title="Cortex Post", version="3.1.0", lifespan=lifespan)

# Rate Limiting
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    try:
        return await limiter.limit(call_next)(request)
    except RateLimitExceeded:
        return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)

# Routes & Static
from app.api.routes import api_router
app.include_router(api_router)

static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# Health, Debug, Webhook endpoints (انسخ من النسخة الأصلية v3.0)
# ... (health, /debug, /webhook/bot, etc.)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.WEBAPP_HOST, port=settings.WEBAPP_PORT, reload=False)

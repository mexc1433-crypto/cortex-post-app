"""
Cortex Post - Main Application Entry Point
Runs FastAPI web server + Telegram Bot (Webhook mode) + APScheduler together.
Uses webhook mode for production on Railway - avoids polling conflicts.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database.connection import db
from app.database import crud
from app.bot.handlers import all_routers
from app.publishers.telegram_publisher import telegram_publisher
from app.engine.scheduler import cortex_scheduler

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global bot and dispatcher
bot: Bot = None
dp: Dispatcher = None

# Use webhook mode when WEBAPP_URL is set, otherwise fall back to polling
USE_WEBHOOK = bool(settings.WEBAPP_URL and settings.WEBAPP_URL.startswith("https://"))


async def on_startup():
    """Initialize all services on startup."""
    global bot, dp
    
    logger.info("Starting Cortex Post...")
    
    # Connect to database
    await db.connect()
    logger.info("Database connected")
    
    # Initialize database schema
    await crud.init_db()
    logger.info("Database schema initialized")
    
    # Initialize bot
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    
    # Initialize dispatcher
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register all bot routers
    for router in all_routers:
        dp.include_router(router)
    
    logger.info("Bot dispatcher configured")
    
    # Set bot instance in telegram publisher
    telegram_publisher.set_bot(bot)
    logger.info("Telegram publisher initialized")
    
    # Start scheduler
    await cortex_scheduler.start()
    logger.info("Scheduler started")
    
    # Set bot commands
    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="start", description="بدء البوت"),
        BotCommand(command="help", description="المساعدة"),
        BotCommand(command="panel", description="لوحة التحكم"),
        BotCommand(command="stats", description="الإحصائيات"),
    ])
    
    # Set up webhook or delete it for polling
    if USE_WEBHOOK:
        webhook_url = f"{settings.WEBAPP_URL}/webhook/bot"
        await bot.set_webhook(
            url=webhook_url,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True,
        )
        logger.info(f"Webhook set to: {webhook_url}")
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted - using polling mode")
    
    logger.info(f"Cortex Post started successfully! 🧠 (mode: {'webhook' if USE_WEBHOOK else 'polling'})")


async def on_shutdown():
    """Cleanup on shutdown."""
    global bot, dp
    
    logger.info("Shutting down Cortex Post...")
    
    # Stop scheduler
    await cortex_scheduler.stop()
    
    # Delete webhook if using webhook mode
    if bot:
        if USE_WEBHOOK:
            await bot.delete_webhook()
        await bot.session.close()
    
    # Disconnect database
    await db.disconnect()
    
    logger.info("Cortex Post shut down complete")


# Track the polling task
_polling_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler."""
    global _polling_task
    
    await on_startup()
    
    # If not using webhook, start polling in background
    if not USE_WEBHOOK:
        _polling_task = asyncio.create_task(start_bot_polling())
    
    yield
    
    # Cancel polling if running
    if _polling_task:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
    
    await on_shutdown()


async def start_bot_polling():
    """Start bot polling in background (fallback mode)."""
    global bot, dp
    
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except asyncio.CancelledError:
        logger.info("Bot polling cancelled")
    except Exception as e:
        logger.error(f"Bot polling error: {e}")


# Create FastAPI app
app = FastAPI(
    title="Cortex Post API",
    description="Automated content publishing platform API",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount API routes
from app.api.routes import api_router
app.include_router(api_router)

# Serve static files for Mini App
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.get("/")
async def root():
    """Root endpoint - serve Mini App."""
    index_path = os.path.join(static_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Cortex Post API", "version": "1.0.0"}


@app.get("/dashboard")
async def dashboard():
    """Dashboard endpoint - serve Mini App."""
    index_path = os.path.join(static_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Dashboard not available"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "database": "connected" if db.is_connected else "disconnected",
        "mode": "webhook" if USE_WEBHOOK else "polling",
    }


# Webhook endpoint for Telegram updates
@app.post("/webhook/bot")
async def telegram_webhook(request: Request):
    """
    Receive Telegram updates via webhook.
    This endpoint receives POST requests from Telegram servers.
    """
    global bot, dp
    
    if not USE_WEBHOOK:
        return Response(status_code=403, content="Webhook mode not enabled")
    
    try:
        body = await request.json()
        update = Update(**body)
        
        # Process the update through the dispatcher
        await dp._process_update(bot, update)
        
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return Response(status_code=200)  # Return 200 anyway to not retry


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.WEBAPP_HOST,
        port=settings.WEBAPP_PORT,
        reload=False,
        log_level="info",
    )

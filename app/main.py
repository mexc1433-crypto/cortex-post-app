"""
Cortex Post - Main Application Entry Point
Runs FastAPI web server + Telegram Bot + APScheduler together.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from fastapi import FastAPI
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
    
    logger.info("Cortex Post started successfully! 🧠")


async def on_shutdown():
    """Cleanup on shutdown."""
    global bot, dp
    
    logger.info("Shutting down Cortex Post...")
    
    # Stop scheduler
    await cortex_scheduler.stop()
    
    # Close bot session
    if bot:
        await bot.session.close()
    
    # Disconnect database
    await db.disconnect()
    
    logger.info("Cortex Post shut down complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler."""
    await on_startup()
    
    # Start bot polling in background
    polling_task = asyncio.create_task(start_bot_polling())
    
    yield
    
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass
    
    await on_shutdown()


async def start_bot_polling():
    """Start bot polling in background."""
    global bot, dp
    
    try:
        # Delete any existing webhook
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Start polling
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
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.WEBAPP_HOST,
        port=settings.WEBAPP_PORT,
        reload=False,
        log_level="info",
    )

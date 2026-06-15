"""
Cortex Post - Main Application Entry Point
Runs FastAPI web server + Telegram Bot (Webhook mode) + APScheduler together.
Uses webhook mode for production on Railway - avoids polling conflicts.
"""
import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware

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
bot: Bot | None = None
dp: Dispatcher | None = None

# Track startup state for healthcheck
_startup_complete = False
_startup_error: str | None = None
_startup_time: float = 0

# Track the polling task
_polling_task = None

# Webhook info for debugging
_webhook_info: dict = {}

# Request counter for diagnostics
_request_count = 0
_webhook_updates_received = 0


# ============================================================================
# HTTP Request Logging Middleware
# ============================================================================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log ALL incoming HTTP requests - critical for debugging webhook issues."""

    async def dispatch(self, request: Request, call_next):
        global _request_count
        _request_count += 1
        start = time.time()

        # Log the incoming request
        logger.info(
            f">>> REQUEST #{_request_count}: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )

        try:
            response = await call_next(request)
            duration = (time.time() - start) * 1000
            logger.info(
                f"<<< RESPONSE #{_request_count}: {request.method} {request.url.path} "
                f"-> {response.status_code} ({duration:.0f}ms)"
            )
            return response
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(
                f"!!! ERROR #{_request_count}: {request.method} {request.url.path} "
                f"-> {e} ({duration:.0f}ms)"
            )
            raise


# ============================================================================
# Initialization Functions
# ============================================================================

async def init_bot():
    """Initialize the Telegram bot - called separately so it doesn't block the web server."""
    global bot, dp, _startup_complete, _startup_error, _webhook_info, _startup_time

    if not settings.is_bot_configured:
        logger.warning("BOT_TOKEN not configured - bot functionality disabled.")
        _startup_complete = True
        return

    try:
        # Initialize bot
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

        # Test bot connection
        me = await bot.get_me()
        logger.info(f"Bot connected: @{me.username} (id={me.id})")

        # Initialize dispatcher
        dp = Dispatcher(storage=MemoryStorage())

        # Register all bot routers
        for router in all_routers:
            dp.include_router(router)

        logger.info(f"Bot dispatcher configured with {len(all_routers)} routers")

        # Set bot instance in telegram publisher
        telegram_publisher.set_bot(bot)
        logger.info("Telegram publisher initialized")

        # Set bot commands
        from aiogram.types import BotCommand
        await bot.set_my_commands([
            BotCommand(command="start", description="بدء البوت"),
            BotCommand(command="help", description="المساعدة"),
            BotCommand(command="panel", description="لوحة التحكم"),
            BotCommand(command="stats", description="الإحصائيات"),
            BotCommand(command="debug", description="حالة النظام"),
        ])

        # Set up webhook or delete it for polling
        if settings.use_webhook:
            webhook_url = f"{settings.WEBAPP_URL}/webhook/bot"

            # Delete previous webhook
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Deleted previous webhook")

            # Set new webhook
            result = await bot.set_webhook(
                url=webhook_url,
                allowed_updates=dp.resolve_used_update_types(),
                drop_pending_updates=True,
            )
            logger.info(f"set_webhook result: {result}")

            # Verify webhook
            webhook_info = await bot.get_webhook_info()
            _webhook_info = {
                "url": webhook_info.url,
                "has_custom_certificate": webhook_info.has_custom_certificate,
                "pending_update_count": webhook_info.pending_update_count,
                "last_error_date": str(webhook_info.last_error_date) if webhook_info.last_error_date else None,
                "last_error_message": webhook_info.last_error_message,
                "max_connections": webhook_info.max_connections,
            }
            logger.info(f"Webhook info: {json.dumps(_webhook_info, default=str)}")

            if webhook_info.url != webhook_url:
                logger.error(f"WEBHOOK MISMATCH! Expected: {webhook_url}, Got: {webhook_info.url}")
            else:
                logger.info(f"Webhook verified OK: {webhook_url}")
        else:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook deleted - using polling mode")

        _startup_time = time.time()
        logger.info(f"Cortex Post bot initialized! (mode: {'webhook' if settings.use_webhook else 'polling'})")

    except Exception as e:
        logger.error(f"Bot initialization error: {e}", exc_info=True)
        _startup_error = str(e)
        bot = None
        dp = None

    _startup_complete = True


async def init_database():
    """Initialize database connection and schema."""
    try:
        await db.connect()
        logger.info("Database connected")
        await crud.init_db()
        logger.info("Database schema initialized")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")


async def init_scheduler():
    """Start the APScheduler."""
    try:
        await cortex_scheduler.start()
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Scheduler initialization error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler - starts web server FIRST, then initializes services in background."""
    global _polling_task

    await init_database()
    asyncio.create_task(_background_init())

    yield

    if _polling_task:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass

    try:
        await cortex_scheduler.stop()
    except Exception:
        pass

    if bot:
        try:
            if settings.use_webhook:
                await bot.delete_webhook()
            await bot.session.close()
        except Exception:
            pass

    try:
        await db.disconnect()
    except Exception:
        pass

    logger.info("Cortex Post shut down complete")


async def _background_init():
    """Run bot init + scheduler init in background after the web server is up."""
    global _polling_task

    await asyncio.sleep(2)
    await init_bot()
    await init_scheduler()

    if not settings.use_webhook and bot and dp:
        _polling_task = asyncio.create_task(start_bot_polling())

    logger.info("All background initialization complete")


async def start_bot_polling():
    """Start bot polling in background (fallback mode)."""
    global bot, dp
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except asyncio.CancelledError:
        logger.info("Bot polling cancelled")
    except Exception as e:
        logger.error(f"Bot polling error: {e}")


# ============================================================================
# FastAPI App Setup
# ============================================================================

app = FastAPI(
    title="Cortex Post API",
    description="Automated content publishing platform API",
    version="1.1.0",
    lifespan=lifespan,
)

# Add request logging middleware FIRST
app.add_middleware(RequestLoggingMiddleware)

# Mount API routes
from app.api.routes import api_router
app.include_router(api_router)

# Serve static files for Mini App
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")


# ============================================================================
# Web Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint - HTML dashboard."""
    return HTMLResponse(content=_generate_dashboard_html())


@app.get("/api/status")
async def api_status():
    """JSON API status endpoint."""
    return JSONResponse(content=_get_status_dict())


@app.get("/health")
async def health():
    """Health check endpoint - always returns 200 for Railway."""
    return JSONResponse(content={
        "status": "healthy",
        "database": "connected" if db.is_connected else "disconnected",
        "bot": "configured" if bot else "not_configured",
        "mode": "webhook" if settings.use_webhook else "polling",
        "startup_complete": _startup_complete,
    })


@app.get("/debug")
async def debug_endpoint():
    """Comprehensive diagnostics endpoint."""
    status = _get_status_dict()

    # Get live webhook info from Telegram
    if bot:
        try:
            info = await bot.get_webhook_info()
            status["telegram_webhook_info"] = {
                "url": info.url,
                "pending_update_count": info.pending_update_count,
                "last_error_date": str(info.last_error_date) if info.last_error_date else None,
                "last_error_message": info.last_error_message,
                "max_connections": info.max_connections,
            }
        except Exception as e:
            status["telegram_webhook_info"] = {"error": str(e)}

    return JSONResponse(content=status, status_code=200)


@app.get("/webhook/info")
async def webhook_info():
    """Get webhook info from Telegram."""
    if not bot:
        return JSONResponse(content={"error": "Bot not initialized"})
    try:
        info = await bot.get_webhook_info()
        return JSONResponse(content={
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_date": str(info.last_error_date) if info.last_error_date else None,
            "last_error_message": info.last_error_message,
            "max_connections": info.max_connections,
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)})


@app.get("/webhook/test")
async def webhook_test_get():
    """Test endpoint - GET version to verify the webhook route is accessible."""
    return JSONResponse(content={
        "message": "Webhook endpoint is accessible!",
        "method": "GET",
        "bot_ready": bot is not None,
        "dp_ready": dp is not None,
        "webhook_url": f"{settings.WEBAPP_URL}/webhook/bot" if settings.use_webhook else "not configured",
        "updates_received": _webhook_updates_received,
        "note": "Telegram sends POST requests to /webhook/bot. This GET is for testing only.",
    })


@app.post("/webhook/bot")
async def telegram_webhook(request: Request):
    """Receive Telegram updates via webhook."""
    global bot, dp, _webhook_updates_received

    _webhook_updates_received += 1

    if not settings.use_webhook:
        logger.warning("Webhook POST received but webhook mode not enabled!")
        return Response(status_code=403, content="Webhook mode not enabled")

    if not bot or not dp:
        logger.warning("Webhook POST received but bot not initialized yet")
        return Response(status_code=200)

    try:
        # Read raw body first for debugging
        raw_body = await request.body()
        body = json.loads(raw_body)

        # Log update details
        update_type = "unknown"
        if "message" in body:
            msg = body["message"]
            update_type = f"message from {msg.get('from', {}).get('id', '?')} text={msg.get('text', '')[:80]}"
        elif "callback_query" in body:
            cb = body["callback_query"]
            update_type = f"callback from {cb.get('from', {}).get('id', '?')} data={cb.get('data', '')[:80]}"
        elif "my_chat_member" in body:
            update_type = "my_chat_member"
        logger.info(f"WEBHOOK UPDATE #{_webhook_updates_received}: {update_type}")

        # Parse and process
        update = Update.model_validate(body)
        await dp.feed_update(bot, update)

        logger.info(f"WEBHOOK UPDATE #{_webhook_updates_received} processed OK")
        return Response(status_code=200)

    except json.JSONDecodeError as e:
        logger.error(f"Webhook JSON parse error: {e}")
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        return Response(status_code=200)


# ============================================================================
# Helper Functions
# ============================================================================

def _get_status_dict() -> dict:
    """Get comprehensive status dictionary."""
    uptime = time.time() - _startup_time if _startup_time else 0
    return {
        "app": "Cortex Post",
        "version": "1.1.0",
        "status": "running",
        "uptime_seconds": round(uptime, 1),
        "database": "connected" if db.is_connected else "disconnected",
        "bot": {
            "configured": bot is not None,
            "username": f"@{(bot and bot.id) or 'N/A'}",
            "mode": "webhook" if settings.use_webhook else "polling",
        },
        "webhook": {
            "enabled": settings.use_webhook,
            "url": f"{settings.WEBAPP_URL}/webhook/bot" if settings.use_webhook else None,
            "updates_received": _webhook_updates_received,
            "info": _webhook_info,
        },
        "scheduler": {
            "running": cortex_scheduler._running if cortex_scheduler else False,
        },
        "startup": {
            "complete": _startup_complete,
            "error": _startup_error,
        },
        "environment": {
            "PORT": os.environ.get("PORT", "8000"),
            "WEBAPP_URL": settings.WEBAPP_URL or "(not set)",
            "BOT_TOKEN_set": bool(settings.BOT_TOKEN),
            "ADMIN_IDS": settings.ADMIN_IDS,
            "DATABASE_PATH": settings.DATABASE_PATH,
        },
        "requests_total": _request_count,
    }


def _generate_dashboard_html() -> str:
    """Generate a simple status dashboard HTML page."""
    status = _get_status_dict()
    bot_ok = status["bot"]["configured"]
    db_ok = status["database"] == "connected"
    webhook_ok = status["webhook"]["enabled"]
    updates = status["webhook"]["updates_received"]

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cortex Post - لوحة التحكم</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
            background: #0f0f1a;
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        h1 {{
            text-align: center;
            font-size: 2em;
            margin-bottom: 8px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .subtitle {{ text-align: center; color: #888; margin-bottom: 30px; }}
        .card {{
            background: #1a1a2e;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 16px;
            border: 1px solid #2a2a4a;
        }}
        .card h2 {{
            font-size: 1.2em;
            margin-bottom: 12px;
            color: #667eea;
        }}
        .status-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #2a2a4a;
        }}
        .status-row:last-child {{ border-bottom: none; }}
        .status-label {{ color: #aaa; }}
        .status-value {{ font-weight: bold; }}
        .ok {{ color: #4ade80; }}
        .err {{ color: #f87171; }}
        .warn {{ color: #fbbf24; }}
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: bold;
        }}
        .badge-ok {{ background: #064e3b; color: #4ade80; }}
        .badge-err {{ background: #450a0a; color: #f87171; }}
        .badge-warn {{ background: #451a03; color: #fbbf24; }}
        .debug-links {{
            margin-top: 20px;
            text-align: center;
        }}
        .debug-links a {{
            display: inline-block;
            margin: 6px;
            padding: 8px 20px;
            background: #2a2a4a;
            color: #667eea;
            text-decoration: none;
            border-radius: 8px;
            font-size: 0.9em;
        }}
        .debug-links a:hover {{ background: #3a3a5a; }}
        .footer {{ text-align: center; color: #555; margin-top: 30px; font-size: 0.85em; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Cortex Post</h1>
        <p class="subtitle">منصة النشر التلقائي الذكية</p>

        <div class="card">
            <h2>حالة النظام</h2>
            <div class="status-row">
                <span class="status-label">التطبيق</span>
                <span class="badge badge-ok">يعمل</span>
            </div>
            <div class="status-row">
                <span class="status-label">قاعدة البيانات</span>
                <span class="status-value {'ok' if db_ok else 'err'}">{'متصل' if db_ok else 'غير متصل'}</span>
            </div>
            <div class="status-row">
                <span class="status-label">البوت</span>
                <span class="status-value {'ok' if bot_ok else 'err'}">{'معد' if bot_ok else 'غير معد'}</span>
            </div>
            <div class="status-row">
                <span class="status-label">وضع الاتصال</span>
                <span class="status-value">{'Webhook' if webhook_ok else 'Polling'}</span>
            </div>
            <div class="status-row">
                <span class="status-label">تحديثات مستلمة</span>
                <span class="status-value {'ok' if updates > 0 else 'warn'}">{updates}</span>
            </div>
            <div class="status-row">
                <span class="status-label">مدة التشغيل</span>
                <span class="status-value">{status['uptime_seconds']} ثانية</span>
            </div>
        </div>

        <div class="card">
            <h2>معلومات الـ Webhook</h2>
            <div class="status-row">
                <span class="status-label">الرابط</span>
                <span class="status-value" style="font-size:0.8em;word-break:break-all;">{status['webhook']['url'] or 'غير معد'}</span>
            </div>
            <div class="status-row">
                <span class="status-label">آخر خطأ</span>
                <span class="status-value {'err' if _webhook_info.get('last_error_message') else 'ok'}">{_webhook_info.get('last_error_message') or 'لا يوجد'}</span>
            </div>
            <div class="status-row">
                <span class="status-label">تحديثات معلقة</span>
                <span class="status-value">{_webhook_info.get('pending_update_count', '?')}</span>
            </div>
        </div>

        {"<div class='card'><h2>خطأ بدء التشغيل</h2><p class='err'>" + str(_startup_error) + "</p></div>" if _startup_error else ""}

        <div class="debug-links">
            <a href="/debug">تشخيص كامل (JSON)</a>
            <a href="/webhook/info">معلومات الـ Webhook</a>
            <a href="/webhook/test">اختبار الـ Webhook</a>
            <a href="/health">Health Check</a>
            <a href="/api/status">API Status</a>
        </div>

        <p class="footer">Cortex Post v1.1.0 | Railway</p>
    </div>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.WEBAPP_HOST,
        port=settings.WEBAPP_PORT,
        reload=False,
        log_level="info",
    )

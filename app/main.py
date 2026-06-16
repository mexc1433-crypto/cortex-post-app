"""
Cortex Post - Main Application Entry Point
Runs FastAPI web server + Telegram Bot (Webhook mode) + APScheduler together.

v3.0 - BULLETPROOF WEBHOOK FIX:
- REMOVED custom ASGI middleware (was causing 502 Bad Gateway via send() interception)
- Using aiogram's built-in webhook handler via dp.feed_update()
- Webhook endpoint is as simple as possible: read body -> parse -> feed_update -> 200
- No middleware touches the request body at all
- Uvicorn access logs handle request logging instead of custom middleware
- Startup sequence is non-blocking and webhook-ready immediately
"""
import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse

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
bot: Optional[Bot] = None
dp: Optional[Dispatcher] = None

# Track startup state for healthcheck
_startup_complete = False
_startup_error: Optional[str] = None
_startup_time: float = 0
_init_start_time: float = 0

# Track the polling task
_polling_task = None

# Webhook diagnostics
_webhook_info: dict = {}
_webhook_updates_received = 0
_webhook_updates_processed = 0
_webhook_updates_errors = 0
_last_webhook_update_time: Optional[str] = None

# Explicitly define allowed update types for Telegram webhook
ALLOWED_UPDATE_TYPES = [
    "message",
    "callback_query",
    "my_chat_member",
    "chat_member",
    "inline_query",
]


# ============================================================================
# Initialization Functions
# ============================================================================

async def init_bot():
    """Initialize the Telegram bot."""
    global bot, dp, _startup_complete, _startup_error, _webhook_info, _startup_time, _init_start_time

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

        resolved_types = dp.resolve_used_update_types()
        logger.info(f"Dispatcher resolved update types: {resolved_types}")
        logger.info(f"Explicit allowed_updates: {ALLOWED_UPDATE_TYPES}")
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
            BotCommand(command="ping", description="فحص الاتصال"),
        ])

        # Set up webhook or delete it for polling
        if settings.use_webhook:
            webhook_url = f"{settings.WEBAPP_URL}/webhook/bot"

            # Delete previous webhook AND drop pending updates
            delete_result = await bot.delete_webhook(drop_pending_updates=True)
            logger.info(f"Deleted previous webhook: {delete_result}")

            # Small delay to ensure Telegram processes the deletion
            await asyncio.sleep(1)

            # Set new webhook with EXPLICIT allowed_updates
            result = await bot.set_webhook(
                url=webhook_url,
                allowed_updates=ALLOWED_UPDATE_TYPES,
                drop_pending_updates=True,
                max_connections=40,
            )
            logger.info(f"set_webhook result: {result}")
            logger.info(f"set_webhook allowed_updates: {ALLOWED_UPDATE_TYPES}")

            # Verify webhook
            webhook_info = await bot.get_webhook_info()
            _webhook_info = {
                "url": webhook_info.url,
                "has_custom_certificate": webhook_info.has_custom_certificate,
                "pending_update_count": webhook_info.pending_update_count,
                "last_error_date": str(webhook_info.last_error_date) if webhook_info.last_error_date else None,
                "last_error_message": webhook_info.last_error_message,
                "max_connections": webhook_info.max_connections,
                "allowed_updates": list(webhook_info.allowed_updates) if webhook_info.allowed_updates else [],
            }
            logger.info(f"Webhook info: {json.dumps(_webhook_info, default=str)}")

            if webhook_info.url != webhook_url:
                logger.error(f"WEBHOOK MISMATCH! Expected: {webhook_url}, Got: {webhook_info.url}")
            else:
                logger.info(f"Webhook verified OK: {webhook_url}")

            # Check if allowed_updates was set correctly
            if webhook_info.allowed_updates:
                logger.info(f"Telegram confirmed allowed_updates: {list(webhook_info.allowed_updates)}")
                missing = set(ALLOWED_UPDATE_TYPES) - set(webhook_info.allowed_updates)
                if missing:
                    logger.warning(f"Missing from Telegram allowed_updates: {missing}")

            # Send admin notification (non-blocking)
            asyncio.create_task(_notify_admins(
                "🟢 <b>Cortex Post Bot Started!</b>\n\n"
                f"Mode: Webhook\n"
                f"URL: <code>{webhook_url}</code>\n"
                f"Allowed updates: {', '.join(ALLOWED_UPDATE_TYPES)}\n"
                f"Version: 3.0\n"
                f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
            ))
        else:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook deleted - using polling mode")

            asyncio.create_task(_notify_admins(
                "🟢 <b>Cortex Post Bot Started!</b>\n\n"
                f"Mode: Polling\n"
                f"Version: 3.0\n"
                f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
            ))

        _startup_time = time.time()
        logger.info(f"Cortex Post bot initialized! (mode: {'webhook' if settings.use_webhook else 'polling'})")

    except Exception as e:
        logger.error(f"Bot initialization error: {e}", exc_info=True)
        _startup_error = str(e)
        bot = None
        dp = None

    _startup_complete = True


async def _notify_admins(text: str):
    """Send a notification message to all admin users."""
    if not bot or not settings.ADMIN_IDS:
        return
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Failed to notify admin {admin_id}: {e}")


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
    global _init_start_time
    _init_start_time = time.time()

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
        await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATE_TYPES)
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
    version="3.0.0",
    lifespan=lifespan,
)

# NO CUSTOM MIDDLEWARE! This was the root cause of 502 errors.
# The previous ASGI middleware intercepted send() which broke response flow.
# We rely on uvicorn's built-in access logging instead.

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
        "startup_error": _startup_error,
        "version": "3.0.0",
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
                "allowed_updates": list(info.allowed_updates) if info.allowed_updates else [],
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
            "allowed_updates": list(info.allowed_updates) if info.allowed_updates else [],
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
        "updates_processed": _webhook_updates_processed,
        "updates_errors": _webhook_updates_errors,
        "last_update_time": _last_webhook_update_time,
        "note": "Telegram sends POST requests to /webhook/bot. This GET is for testing only.",
        "allowed_updates": ALLOWED_UPDATE_TYPES,
        "version": "3.0.0",
    })


@app.post("/webhook/test")
async def webhook_test_post(request: Request):
    """
    Simulate a Telegram webhook update for testing.
    """
    global _webhook_updates_received, _last_webhook_update_time

    if not bot or not dp:
        return JSONResponse(content={"error": "Bot not initialized yet", "bot_ready": bot is not None, "dp_ready": dp is not None})

    try:
        body = await request.json()
        logger.info(f"WEBHOOK TEST: Received simulated update: {json.dumps(body)[:200]}")

        try:
            update = Update.model_validate(body)
            _webhook_updates_received += 1
            _last_webhook_update_time = datetime.utcnow().isoformat()
            await dp.feed_update(bot, update)
            _webhook_updates_processed += 1
            return JSONResponse(content={"status": "processed", "update_type": list(body.keys())})
        except Exception as e:
            _webhook_updates_errors += 1
            logger.error(f"WEBHOOK TEST: Error processing: {e}", exc_info=True)
            return JSONResponse(content={"status": "error", "error": str(e)})

    except json.JSONDecodeError as e:
        return JSONResponse(content={"error": f"Invalid JSON: {e}"})


@app.post("/webhook/reset")
async def webhook_reset():
    """Force re-register the webhook with Telegram."""
    if not bot:
        return JSONResponse(content={"error": "Bot not initialized"})

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted for reset")

        await asyncio.sleep(1)

        if settings.use_webhook:
            webhook_url = f"{settings.WEBAPP_URL}/webhook/bot"
            result = await bot.set_webhook(
                url=webhook_url,
                allowed_updates=ALLOWED_UPDATE_TYPES,
                drop_pending_updates=True,
                max_connections=40,
            )
            logger.info(f"Webhook re-set result: {result}")

            info = await bot.get_webhook_info()
            return JSONResponse(content={
                "status": "reset",
                "set_result": result,
                "webhook_url": info.url,
                "allowed_updates": list(info.allowed_updates) if info.allowed_updates else [],
                "pending_update_count": info.pending_update_count,
                "last_error_message": info.last_error_message,
            })
        else:
            return JSONResponse(content={"status": "webhook_mode_not_enabled"})

    except Exception as e:
        logger.error(f"Webhook reset error: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)})


# ============================================================================
# CRITICAL: Telegram Webhook Handler
# ============================================================================
# This is the endpoint that Telegram calls when it has updates.
# It MUST:
# 1. Return 200 ASAP (Telegram times out after 60 seconds)
# 2. NOT be interfered with by any middleware
# 3. Parse the JSON body correctly
# 4. Feed the update to aiogram's dispatcher
#
# v3.0 FIX: No middleware wraps this endpoint. The previous ASGI middleware
# was intercepting send() calls which caused 502 Bad Gateway errors on
# Railway's proxy. Now we use zero middleware and rely on uvicorn access logs.

@app.post("/webhook/bot")
async def telegram_webhook(request: Request):
    """
    Receive Telegram updates via webhook.

    This is called by Telegram's servers when users interact with the bot.
    We read the body, parse it as a Telegram Update, and feed it to the
    aiogram dispatcher for processing.
    """
    global _webhook_updates_received, _last_webhook_update_time

    # Increment counter immediately for diagnostics
    _webhook_updates_received += 1
    update_num = _webhook_updates_received
    _last_webhook_update_time = datetime.utcnow().isoformat()

    # If webhook mode is not enabled, reject
    if not settings.use_webhook:
        logger.warning(f"WEBHOOK #{update_num}: POST received but webhook mode not enabled!")
        return Response(status_code=403, content="Webhook mode not enabled")

    # If bot/dispatcher not ready yet, return 200 anyway to prevent Telegram retries
    if not bot or not dp:
        logger.warning(f"WEBHOOK #{update_num}: Bot not initialized yet, returning 200 to prevent retries")
        return Response(status_code=200)

    try:
        # Read the raw request body
        raw_body = await request.body()

        if not raw_body:
            logger.warning(f"WEBHOOK #{update_num}: Empty body received")
            return Response(status_code=200)

        # Parse JSON
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as e:
            logger.error(f"WEBHOOK #{update_num}: JSON parse error: {e}")
            _webhook_updates_errors += 1
            return Response(status_code=200)  # Still 200 to avoid Telegram retries

        # Log the update type for diagnostics
        update_type = "unknown"
        if "message" in body:
            msg = body["message"]
            text = msg.get("text", "")[:80]
            from_id = msg.get("from", {}).get("id", "?")
            update_type = f"message from={from_id} text={text}"
        elif "callback_query" in body:
            cb = body["callback_query"]
            data = cb.get("data", "")[:80]
            from_id = cb.get("from", {}).get("id", "?")
            update_type = f"callback from={from_id} data={data}"
        elif "my_chat_member" in body:
            mcm = body["my_chat_member"]
            from_id = mcm.get("from", {}).get("id", "?")
            update_type = f"my_chat_member from={from_id}"
        elif "chat_member" in body:
            update_type = "chat_member"
        else:
            update_type = f"other: {list(body.keys())}"

        logger.info(f"WEBHOOK #{update_num}: {update_type}")

        # Process the update - two options:
        # Option A: Process immediately (simple, but blocks the response)
        # Option B: Process in background (fast response, but update might fail silently)
        #
        # We use Option A because Telegram gives us 60 seconds before timeout,
        # and most updates process in under 1 second. This ensures we catch
        # any errors immediately and don't lose updates to silent task failures.

        try:
            update = Update.model_validate(body)
            await dp.feed_update(bot, update)
            _webhook_updates_processed += 1
            logger.info(f"WEBHOOK #{update_num}: Processed OK")
        except Exception as e:
            _webhook_updates_errors += 1
            logger.error(f"WEBHOOK #{update_num}: Processing error: {e}", exc_info=True)

        return Response(status_code=200)

    except Exception as e:
        logger.error(f"WEBHOOK #{update_num}: Unexpected error: {e}", exc_info=True)
        _webhook_updates_errors += 1
        # Always return 200 to prevent Telegram from retrying endlessly
        return Response(status_code=200)


# ============================================================================
# Helper Functions
# ============================================================================

def _get_status_dict() -> dict:
    """Get comprehensive status dictionary."""
    uptime = time.time() - _startup_time if _startup_time else 0
    init_time = time.time() - _init_start_time if _init_start_time else 0
    return {
        "app": "Cortex Post",
        "version": "3.0.0",
        "status": "running",
        "uptime_seconds": round(uptime, 1),
        "init_time_seconds": round(init_time, 1),
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
            "updates_processed": _webhook_updates_processed,
            "updates_errors": _webhook_updates_errors,
            "last_update_time": _last_webhook_update_time,
            "info": _webhook_info,
            "allowed_updates": ALLOWED_UPDATE_TYPES,
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
        "middleware": "None (v3.0 - removed ASGI middleware that caused 502)",
    }


def _generate_dashboard_html() -> str:
    """Generate a comprehensive status dashboard HTML page."""
    status = _get_status_dict()
    bot_ok = status["bot"]["configured"]
    db_ok = status["database"] == "connected"
    webhook_ok = status["webhook"]["enabled"]
    updates = status["webhook"]["updates_received"]
    processed = status["webhook"]["updates_processed"]
    errors = status["webhook"]["updates_errors"]
    last_update = status["webhook"]["last_update_time"] or "Never"
    allowed = status["webhook"]["allowed_updates"]

    # Determine health status
    if not bot_ok:
        health_color = "#f87171"
        health_text = "Bot Not Configured"
    elif updates == 0 and _startup_complete:
        health_color = "#fbbf24"
        health_text = "No Webhook Updates Yet"
    elif errors > processed and processed > 0:
        health_color = "#f87171"
        health_text = "Many Processing Errors"
    else:
        health_color = "#4ade80"
        health_text = "Healthy"

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
        .container {{ max-width: 900px; margin: 0 auto; }}
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
        .health-bar {{
            background: #2a2a4a;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .health-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: {health_color};
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        .health-text {{ font-weight: bold; color: {health_color}; }}
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
        .mono {{ font-family: monospace; font-size: 0.85em; word-break: break-all; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 12px;
            margin: 12px 0;
        }}
        .stat-box {{
            background: #2a2a4a;
            border-radius: 8px;
            padding: 12px;
            text-align: center;
        }}
        .stat-number {{ font-size: 1.5em; font-weight: bold; color: #667eea; }}
        .stat-label {{ font-size: 0.8em; color: #888; margin-top: 4px; }}
        .warning-box {{
            background: #451a03;
            border: 1px solid #92400e;
            border-radius: 8px;
            padding: 12px;
            margin: 12px 0;
            color: #fbbf24;
        }}
        .success-box {{
            background: #064e3b;
            border: 1px solid #065f46;
            border-radius: 8px;
            padding: 12px;
            margin: 12px 0;
            color: #4ade80;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Cortex Post</h1>
        <p class="subtitle">منصة النشر التلقائي الذكية v3.0</p>

        <div class="health-bar">
            <div class="health-dot"></div>
            <span class="health-text">{health_text}</span>
        </div>

        {"<div class='success-box'>Webhook updates are being received and processed! The bot is working correctly.</div>" if updates > 0 and _startup_complete and settings.use_webhook else ""}

        {"<div class='warning-box'>No webhook updates received yet. If the bot has been running for a while, check: 1) Telegram Bot API token is correct, 2) WEBAPP_URL is accessible from the internet, 3) Try /webhook/reset to re-register the webhook.</div>" if updates == 0 and _startup_complete and settings.use_webhook else ""}

        {"<div class='warning-box'>Startup error: " + str(_startup_error) + "</div>" if _startup_error else ""}

        <div class="card">
            <h2>الإحصائيات</h2>
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-number">{'0' if not _startup_time else str(round((time.time() - _startup_time) / 60, 1))}</div>
                    <div class="stat-label">دقيقة تشغيل</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{updates}</div>
                    <div class="stat-label">تحديثات مستلمة</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number {'ok' if errors == 0 else 'err'}">{errors}</div>
                    <div class="stat-label">أخطاء</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{processed}</div>
                    <div class="stat-label">تم المعالجة</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>حالة النظام</h2>
            <div class="status-row">
                <span class="status-label">التطبيق</span>
                <span class="badge badge-ok">يعمل v3.0</span>
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
                <span class="status-label">الميدلوير</span>
                <span class="status-value ok">لا يوجد (v3.0)</span>
            </div>
            <div class="status-row">
                <span class="status-label">بدء التشغيل</span>
                <span class="status-value {'ok' if _startup_complete else 'warn'}">{'مكتمل' if _startup_complete else 'جاري...'}</span>
            </div>
        </div>

        <div class="card">
            <h2>معلومات الـ Webhook</h2>
            <div class="status-row">
                <span class="status-label">الرابط</span>
                <span class="status-value mono">{status['webhook']['url'] or 'غير معد'}</span>
            </div>
            <div class="status-row">
                <span class="status-label">Allowed Updates</span>
                <span class="status-value mono" style="font-size:0.75em;">{', '.join(allowed)}</span>
            </div>
            <div class="status-row">
                <span class="status-label">تحديثات مستلمة</span>
                <span class="status-value {'ok' if updates > 0 else 'warn'}">{updates}</span>
            </div>
            <div class="status-row">
                <span class="status-label">تحديثات معالجة</span>
                <span class="status-value">{processed}</span>
            </div>
            <div class="status-row">
                <span class="status-label">أخطاء معالجة</span>
                <span class="status-value {'err' if errors > 0 else 'ok'}">{errors}</span>
            </div>
            <div class="status-row">
                <span class="status-label">آخر تحديث</span>
                <span class="status-value mono" style="font-size:0.8em;">{last_update}</span>
            </div>
            <div class="status-row">
                <span class="status-label">آخر خطأ Telegram</span>
                <span class="status-value {'err' if _webhook_info.get('last_error_message') else 'ok'}">{_webhook_info.get('last_error_message') or 'لا يوجد'}</span>
            </div>
            <div class="status-row">
                <span class="status-label">تحديثات معلقة</span>
                <span class="status-value {'warn' if _webhook_info.get('pending_update_count', 0) > 0 else 'ok'}">{_webhook_info.get('pending_update_count', '?')}</span>
            </div>
        </div>

        <div class="debug-links">
            <a href="/debug">تشخيص كامل (JSON)</a>
            <a href="/webhook/info">معلومات الـ Webhook</a>
            <a href="/webhook/test">اختبار GET</a>
            <a href="/health">Health Check</a>
            <a href="/api/status">API Status</a>
        </div>

        <p class="footer">Cortex Post v3.0.0 | No Middleware | Railway</p>
    </div>

    <script>
        // Auto-refresh every 10 seconds
        setTimeout(function() {{ location.reload(); }}, 10000);
    </script>
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

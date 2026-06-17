import redis.asyncio as redis
from loguru import logger
from app.config import settings

redis_client = None

async def init_redis():
    global redis_client
    try:
        redis_client = redis.from_url(
            "redis://localhost:6379",  # Railway هيدعم Redis addon
            decode_responses=True,
            socket_timeout=5
        )
        await redis_client.ping()
        logger.success("✅ Redis connected")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Redis not available: {e} (using in-memory fallback)")
        return False

async def get_redis():
    return redis_client

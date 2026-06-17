import os
import redis.asyncio as redis
from loguru import logger

redis_client = None

async def get_redis():
    global redis_client
    if redis_client is None:
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            redis_client = redis.from_url(redis_url, decode_responses=True, socket_timeout=5)
            await redis_client.ping()
            logger.success("✅ Redis connected")
        except Exception as e:
            logger.warning(f"⚠️ Redis failed: {e}")
            redis_client = None
    return redis_client

async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None

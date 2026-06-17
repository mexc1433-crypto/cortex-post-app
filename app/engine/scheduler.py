"""
Cortex Scheduler - Enhanced
Uses APScheduler + Redis caching for better performance.
"""
import asyncio
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app.config import settings
from app.database.connection import db
from app.database import crud
from app.engine.rules_engine import rules_engine
from app.engine.template_engine import template_engine
from app.core.redis import get_redis

class CortexScheduler:
    """Main scheduler with Redis caching and better error handling."""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._running = False
    
    async def start(self):
        if self._running:
            return
        
        # Main rules processing
        self.scheduler.add_job(
            self.process_all_rules,
            trigger=IntervalTrigger(seconds=settings.SCHEDULER_INTERVAL_SECONDS),
            id="process_rules",
            name="Process all active rules",
            replace_existing=True,
        )
        
        # Webhook processor
        self.scheduler.add_job(
            self.process_webhook_events,
            trigger=IntervalTrigger(seconds=30),
            id="process_webhooks",
            name="Process pending webhook events",
            replace_existing=True,
        )
        
        # Daily cleanup
        self.scheduler.add_job(
            self.cleanup_old_logs,
            trigger=IntervalTrigger(hours=24),
            id="cleanup_logs",
            name="Cleanup old post logs",
            replace_existing=True,
        )
        
        # Webhook health (every 5 min)
        self.scheduler.add_job(
            self.check_webhook_health,
            trigger=IntervalTrigger(minutes=5),
            id="webhook_health",
            name="Check webhook health",
            replace_existing=True,
        )
        
        self.scheduler.start()
        self._running = True
        logger.success("✅ Cortex Scheduler started successfully")


    async def stop(self):
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("🛑 Scheduler stopped")


    async def process_all_rules(self):
        """Main job - Process all active rules."""
        try:
            rules = await crud.get_active_rules()
            logger.info(f"Processing {len(rules)} active rules")

            for rule in rules:
                try:
                    await self.process_rule(rule)
                except Exception as e:
                    logger.error(f"Rule {rule.get('id')} failed: {e}")
        except Exception as e:
            logger.error(f"process_all_rules error: {e}")


    async def process_rule(self, rule: dict):
        """Process single rule with cooldown + Redis cache."""
        rule_id = rule["id"]
        
        # Cooldown check using Redis
        redis = await get_redis()
        if redis:
            last_triggered = await redis.get(f"rule_last:{rule_id}")
            if last_triggered:
                last = datetime.fromisoformat(last_triggered)
                if (datetime.utcnow() - last).total_seconds() < rule.get("cooldown_minutes", 30) * 60:
                    return

        # Get provider
        provider = await crud.get_provider_by_id(rule["provider_id"])
        if not provider:
            return

        # Fetch data
        data = await self._fetch_provider_data(provider)
        if not data:
            return

        # Evaluate conditions
        conditions = rule.get("conditions", [])
        if isinstance(conditions, str):
            conditions = json.loads(conditions)

        if not rules_engine.evaluate(data, conditions, rule.get("condition_logic", "AND")):
            return

        # Render & Publish
        template = await crud.get_template_by_id(rule["template_id"])
        channel = await crud.get_channel_by_id(rule["channel_id"])
        if not template or not channel:
            return

        content = template_engine.render(template["content"], data)
        await self._publish(rule, channel, content, provider["provider_type"])

        # Update last triggered
        await crud.update_last_triggered(rule_id)
        if redis:
            await redis.set(f"rule_last:{rule_id}", datetime.utcnow().isoformat(), ex=3600)

        logger.success(f"Rule {rule_id} executed successfully")


    async def _fetch_provider_data(self, provider: dict):
        try:
            from app.providers import get_provider
            provider_impl = get_provider(provider["provider_type"], provider["config"])
            if provider_impl:
                data = await provider_impl.fetch()
                await crud.update_last_fetched(provider["id"])
                return data
        except Exception as e:
            logger.error(f"Provider {provider.get('id')} fetch error: {e}")
        return None


    async def _publish(self, rule: dict, channel: dict, content: str, provider_type: str):
        """Publish to all platforms."""
        # Telegram
        try:
            from app.publishers.telegram_publisher import telegram_publisher
            msg_id = await telegram_publisher.publish(
                channel_telegram_id=channel["channel_telegram_id"],
                content=content,
                parse_mode=rule.get("parse_mode", "HTML")
            )
            await crud.create_post_log(
                rule_id=rule["id"], channel_id=channel["id"], provider_type=provider_type,
                content=content, status="sent", platform="telegram", telegram_message_id=msg_id
            )
        except Exception as e:
            logger.error(f"Telegram publish failed: {e}")
            await crud.create_post_log(...)  # failed log

        # Twitter (Premium only)
        # ... (ابقِ الكود القديم أو حدثه)


    # باقي الدوال (process_webhook_events, cleanup_old_logs, check_webhook_health, trigger_rule_now)
    # يمكن تحسينها بنفس الطريقة...

    async def check_webhook_health(self):
        """تحسين الـ health check بدون circular import"""
        if not settings.use_webhook:
            return
        try:
            # استخدم global bot من main إذا أمكن، أو أضف طريقة أفضل
            from app.main import bot as app_bot
            if app_bot:
                info = await app_bot.get_webhook_info()
                # ... باقي الكود
        except Exception as e:
            logger.error(f"Webhook health check failed: {e}")


cortex_scheduler = CortexScheduler()

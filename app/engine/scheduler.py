"""
Scheduler for Cortex Post
Uses APScheduler to periodically fetch data from providers,
evaluate rules, and publish content to channels.
"""
import asyncio
import json
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database.connection import db
from app.database import crud
from app.engine.rules_engine import rules_engine
from app.engine.template_engine import template_engine

logger = logging.getLogger(__name__)

class CortexScheduler:
    """Main scheduler that orchestrates the content pipeline."""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._running = False
    
    async def start(self):
        """Start the scheduler."""
        if self._running:
            return
        
        # Main processing job
        self.scheduler.add_job(
            self.process_all_rules,
            trigger=IntervalTrigger(seconds=settings.SCHEDULER_INTERVAL_SECONDS),
            id="process_rules",
            name="Process all active rules",
            replace_existing=True,
        )
        
        # Webhook event processor
        self.scheduler.add_job(
            self.process_webhook_events,
            trigger=IntervalTrigger(seconds=30),
            id="process_webhooks",
            name="Process pending webhook events",
            replace_existing=True,
        )
        
        # Cleanup old post logs (daily)
        self.scheduler.add_job(
            self.cleanup_old_logs,
            trigger=IntervalTrigger(hours=24),
            id="cleanup_logs",
            name="Cleanup old post logs",
            replace_existing=True,
        )
        
        self.scheduler.start()
        self._running = True
        logger.info("Scheduler started successfully")
    
    async def stop(self):
        """Stop the scheduler."""
        if self._running:
            self.scheduler.shutdown()
            self._running = False
            logger.info("Scheduler stopped")
    
    async def process_all_rules(self):
        """Process all active rules - main pipeline."""
        try:
            rules = await crud.get_active_rules()
            logger.info(f"Processing {len(rules)} active rules")
            
            for rule in rules:
                try:
                    await self.process_rule(rule)
                except Exception as e:
                    logger.error(f"Error processing rule {rule['id']}: {e}")
        except Exception as e:
            logger.error(f"Error in process_all_rules: {e}")
    
    async def process_rule(self, rule: dict):
        """Process a single rule: fetch data -> evaluate -> publish."""
        rule_id = rule["id"]
        
        # Check cooldown
        if not rules_engine.check_cooldown(rule.get("last_triggered_at"), rule.get("cooldown_minutes", 30)):
            return
        
        # Get provider
        provider = await crud.get_provider_by_id(rule["provider_id"])
        if not provider:
            logger.warning(f"Provider {rule['provider_id']} not found for rule {rule_id}")
            return
        
        # Fetch data from provider
        data = await self._fetch_provider_data(provider)
        if not data:
            return
        
        # Evaluate conditions
        conditions = rule.get("conditions", [])
        if isinstance(conditions, str):
            conditions = json.loads(conditions)
        
        logic = rule.get("condition_logic", "AND")
        if not rules_engine.evaluate(data, conditions, logic):
            return
        
        # Get template
        template = await crud.get_template_by_id(rule["template_id"])
        if not template:
            logger.warning(f"Template {rule['template_id']} not found for rule {rule_id}")
            return
        
        # Render content
        content = template_engine.render(template["content"], data)
        
        # Get channel
        channel = await crud.get_channel_by_id(rule["channel_id"])
        if not channel:
            logger.warning(f"Channel {rule['channel_id']} not found for rule {rule_id}")
            return
        
        # Publish
        await self._publish(rule, channel, content, provider["provider_type"])
        
        # Update last triggered
        await crud.update_last_triggered(rule_id)
        
        logger.info(f"Rule {rule_id} triggered and published successfully")
    
    async def _fetch_provider_data(self, provider: dict) -> dict | None:
        """Fetch data from a provider."""
        try:
            from app.providers import get_provider
            provider_impl = get_provider(provider["provider_type"], provider["config"])
            if provider_impl:
                data = await provider_impl.fetch()
                await crud.update_last_fetched(provider["id"])
                return data
        except Exception as e:
            logger.error(f"Error fetching from provider {provider['id']}: {e}")
        return None
    
    async def _publish(self, rule: dict, channel: dict, content: str, provider_type: str):
        """Publish content to channel via all configured publishers."""
        # Publish to Telegram
        try:
            from app.publishers.telegram_publisher import telegram_publisher
            msg_id = await telegram_publisher.publish(
                channel_telegram_id=channel["channel_telegram_id"],
                content=content,
                parse_mode=rule.get("parse_mode", "HTML")
            )
            await crud.create_post_log(
                rule_id=rule["id"],
                channel_id=channel["id"],
                provider_type=provider_type,
                content=content,
                status="sent",
                platform="telegram",
                telegram_message_id=msg_id,
            )
        except Exception as e:
            logger.error(f"Telegram publish error: {e}")
            await crud.create_post_log(
                rule_id=rule["id"],
                channel_id=channel["id"],
                provider_type=provider_type,
                content=content,
                status="failed",
                platform="telegram",
                error_message=str(e),
            )
        
        # Publish to Twitter (if user has premium and configured)
        try:
            rule_user = await crud.get_user_by_id(rule["user_id"])
            if rule_user and rule_user["tier"] == "premium" and settings.TWITTER_API_KEY:
                from app.publishers.twitter_publisher import twitter_publisher
                tweet_id = await twitter_publisher.publish(content=content)
                await crud.create_post_log(
                    rule_id=rule["id"],
                    channel_id=channel["id"],
                    provider_type=provider_type,
                    content=content[:280],  # Twitter limit
                    status="sent",
                    platform="twitter",
                )
        except Exception as e:
            logger.error(f"Twitter publish error: {e}")
            await crud.create_post_log(
                rule_id=rule["id"],
                channel_id=channel["id"],
                provider_type=provider_type,
                content=content[:280],
                status="failed",
                platform="twitter",
                error_message=str(e),
            )
    
    async def process_webhook_events(self):
        """Process unprocessed webhook events."""
        events = await crud.get_unprocessed_events()
        for event in events:
            try:
                # Find matching rules for this provider
                rules = await crud.get_active_rules()
                for rule in rules:
                    provider = await crud.get_provider_by_id(rule["provider_id"])
                    if provider and provider["provider_type"] == "webhook":
                        data = event["payload"]
                        conditions = rule.get("conditions", [])
                        if isinstance(conditions, str):
                            conditions = json.loads(conditions)
                        
                        if rules_engine.evaluate(data, conditions, rule.get("condition_logic", "AND")):
                            template = await crud.get_template_by_id(rule["template_id"])
                            channel = await crud.get_channel_by_id(rule["channel_id"])
                            if template and channel:
                                content = template_engine.render(template["content"], data)
                                await self._publish(rule, channel, content, "webhook")
                                await crud.update_last_triggered(rule["id"])
                
                await crud.mark_event_processed(event["id"])
            except Exception as e:
                logger.error(f"Error processing webhook event {event['id']}: {e}")
    
    async def cleanup_old_logs(self):
        """Remove post logs older than 30 days."""
        try:
            await db.execute(
                "DELETE FROM post_log WHERE created_at < datetime('now', '-30 days')"
            )
            logger.info("Old post logs cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up logs: {e}")
    
    async def trigger_rule_now(self, rule_id: int):
        """Manually trigger a rule immediately."""
        rule = await crud.get_rule_by_id(rule_id)
        if rule:
            await self.process_rule(rule)


cortex_scheduler = CortexScheduler()

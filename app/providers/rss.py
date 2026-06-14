"""RSS feed provider."""
import logging
from typing import Any

import httpx
import feedparser

from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class RSSProvider(BaseProvider):
    provider_type = "rss"
    
    async def fetch(self) -> dict[str, Any]:
        feed_url = self.config.get("feed_url")
        if not feed_url:
            raise ValueError("feed_url is required in RSS provider config")
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(feed_url)
            response.raise_for_status()
        
        feed = feedparser.parse(response.text)
        
        if not feed.entries:
            return {"title": "", "link": "", "summary": "", "published": ""}
        
        latest = feed.entries[0]
        
        return {
            "feed_title": feed.feed.get("title", ""),
            "feed_link": feed.feed.get("link", ""),
            "title": latest.get("title", ""),
            "link": latest.get("link", ""),
            "summary": latest.get("summary", ""),
            "author": latest.get("author", ""),
            "published": latest.get("published", ""),
            "tags": ", ".join(t.get("term", "") for t in latest.get("tags", [])),
            "entry_count": len(feed.entries),
        }
    
    async def fetch_recent(self, count: int = 5) -> list[dict]:
        """Fetch multiple recent entries."""
        feed_url = self.config.get("feed_url")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(feed_url)
            response.raise_for_status()
        
        feed = feedparser.parse(response.text)
        results = []
        for entry in feed.entries[:count]:
            results.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "author": entry.get("author", ""),
                "published": entry.get("published", ""),
            })
        return results
    
    async def validate_config(self) -> bool:
        return bool(self.config.get("feed_url"))
    
    def get_available_fields(self) -> list[str]:
        return ["feed_title", "title", "link", "summary", "author", "published", "tags"]

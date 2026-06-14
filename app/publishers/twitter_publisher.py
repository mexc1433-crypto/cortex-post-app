"""Twitter/X publisher using Tweepy."""
import logging
import asyncio
from typing import Optional

import tweepy

from app.publishers.base import BasePublisher
from app.config import settings

logger = logging.getLogger(__name__)


class TwitterPublisher(BasePublisher):
    platform = "twitter"
    
    def __init__(self):
        self._api: Optional[tweepy.API] = None
        self._client: Optional[tweepy.Client] = None
        self._initialized = False
    
    def _ensure_init(self):
        """Lazily initialize Twitter client."""
        if self._initialized:
            return
        
        if not all([settings.TWITTER_API_KEY, settings.TWITTER_API_SECRET,
                     settings.TWITTER_ACCESS_TOKEN, settings.TWITTER_ACCESS_SECRET]):
            logger.warning("Twitter API credentials not configured")
            return
        
        try:
            auth = tweepy.OAuth1UserHandler(
                consumer_key=settings.TWITTER_API_KEY,
                consumer_secret=settings.TWITTER_API_SECRET,
                access_token=settings.TWITTER_ACCESS_TOKEN,
                access_token_secret=settings.TWITTER_ACCESS_SECRET,
            )
            self._api = tweepy.API(auth)
            self._client = tweepy.Client(
                consumer_key=settings.TWITTER_API_KEY,
                consumer_secret=settings.TWITTER_API_SECRET,
                access_token=settings.TWITTER_ACCESS_TOKEN,
                access_token_secret=settings.TWITTER_ACCESS_SECRET,
            )
            self._initialized = True
            logger.info("Twitter client initialized successfully")
        except Exception as e:
            logger.error(f"Twitter init error: {e}")
    
    async def publish(self, content: str, **kwargs) -> str | None:
        """
        Publish a tweet.
        
        Args:
            content: Tweet text (max 280 chars)
        
        Returns:
            Tweet ID on success
        """
        self._ensure_init()
        
        if not self._client:
            raise RuntimeError("Twitter client not initialized. Check API credentials.")
        
        # Truncate to Twitter limit
        tweet_text = content[:280]
        
        try:
            # tweepy.Client.create_tweet is synchronous, run in thread
            response = await asyncio.to_thread(
                self._client.create_tweet,
                text=tweet_text,
            )
            
            tweet_id = response.data.get("id") if response.data else None
            logger.info(f"Tweet posted: {tweet_id}")
            return str(tweet_id) if tweet_id else None
        
        except Exception as e:
            logger.error(f"Twitter publish error: {e}")
            raise
    
    async def delete(self, message_id: str | int, **kwargs) -> bool:
        """Delete a tweet."""
        self._ensure_init()
        
        if not self._client:
            return False
        
        try:
            await asyncio.to_thread(
                self._client.delete_tweet,
                int(message_id),
            )
            return True
        except Exception as e:
            logger.error(f"Twitter delete error: {e}")
            return False


twitter_publisher = TwitterPublisher()

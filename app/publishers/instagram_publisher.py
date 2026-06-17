from loguru import logger
import httpx
from typing import Optional
from app.config import settings

class InstagramPublisher:
    def __init__(self):
        self.access_token: Optional[str] = settings.INSTAGRAM_ACCESS_TOKEN
        self.account_id: Optional[str] = settings.INSTAGRAM_ACCOUNT_ID
        self.api_version = "v20.0"

    async def publish(self, caption: str, image_url: Optional[str] = None, is_story: bool = False) -> bool:
        """نشر على إنستغرام (صور + كابشن)"""
        if not self.access_token or not self.account_id:
            logger.warning("⚠️ Instagram not configured (missing token or account_id)")
            return False

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if image_url:
                    # Create Media Container
                    container_url = f"https://graph.instagram.com/{self.account_id}/media"
                    params = {
                        "image_url": image_url,
                        "caption": caption,
                        "access_token": self.access_token
                    }

                    response = await client.post(container_url, params=params)
                    data = response.json()

                    if response.status_code != 200 or "id" not in data:
                        logger.error(f"Instagram container error: {data}")
                        return False

                    container_id = data["id"]

                    # Publish the container
                    publish_url = f"https://graph.instagram.com/{container_id}/media_publish"
                    publish_response = await client.post(publish_url, params={"access_token": self.access_token})

                    if publish_response.status_code == 200:
                        logger.success("✅ Posted successfully to Instagram Feed")
                        return True
                else:
                    # Text only (limited support)
                    logger.warning("Instagram text-only posting is limited")
                    return False

        except Exception as e:
            logger.error(f"❌ Instagram publish error: {e}")
            return False


# Singleton
instagram_publisher = InstagramPublisher()

"""Crypto price provider using CoinGecko API."""
import logging
from typing import Any

import httpx

from app.providers.base import BaseProvider
from app.config import settings

logger = logging.getLogger(__name__)


class CryptoProvider(BaseProvider):
    provider_type = "crypto"
    
    async def fetch(self) -> dict[str, Any]:
        coin_id = self.config.get("coin_id", "bitcoin")
        vs_currency = self.config.get("vs_currency", "usd")
        
        url = f"{settings.COINGECKO_API_URL}/simple/price"
        params = {
            "ids": coin_id,
            "vs_currencies": vs_currency,
            "include_24hr_change": "true",
            "include_24hr_vol": "true",
            "include_market_cap": "true",
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        coin_data = data.get(coin_id, {})
        
        return {
            "coin": coin_id.upper(),
            "coin_id": coin_id,
            "price": coin_data.get(vs_currency, 0),
            "price_change_24h": coin_data.get(f"{vs_currency}_24h_change", 0),
            "volume_24h": coin_data.get(f"{vs_currency}_24h_vol", 0),
            "market_cap": coin_data.get(f"{vs_currency}_market_cap", 0),
            "currency": vs_currency.upper(),
        }
    
    async def fetch_multiple(self, coin_ids: list[str]) -> list[dict]:
        """Fetch data for multiple coins at once."""
        vs_currency = self.config.get("vs_currency", "usd")
        url = f"{settings.COINGECKO_API_URL}/simple/price"
        params = {
            "ids": ",".join(coin_ids),
            "vs_currencies": vs_currency,
            "include_24hr_change": "true",
            "include_24hr_vol": "true",
            "include_market_cap": "true",
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        results = []
        for coin_id in coin_ids:
            coin_data = data.get(coin_id, {})
            results.append({
                "coin": coin_id.upper(),
                "coin_id": coin_id,
                "price": coin_data.get(vs_currency, 0),
                "price_change_24h": coin_data.get(f"{vs_currency}_24h_change", 0),
                "volume_24h": coin_data.get(f"{vs_currency}_24h_vol", 0),
                "market_cap": coin_data.get(f"{vs_currency}_market_cap", 0),
                "currency": vs_currency.upper(),
            })
        return results
    
    async def validate_config(self) -> bool:
        return bool(self.config.get("coin_id"))
    
    def get_available_fields(self) -> list[str]:
        return ["coin", "price", "price_change_24h", "volume_24h", "market_cap", "currency"]

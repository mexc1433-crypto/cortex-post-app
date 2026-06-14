"""Weather data provider using OpenWeatherMap API."""
import logging
from typing import Any

import httpx

from app.providers.base import BaseProvider
from app.config import settings

logger = logging.getLogger(__name__)


class WeatherProvider(BaseProvider):
    provider_type = "weather"
    
    async def fetch(self) -> dict[str, Any]:
        city = self.config.get("city", "Cairo")
        units = self.config.get("units", "metric")
        lang = self.config.get("lang", "ar")
        
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city,
            "appid": settings.WEATHER_API_KEY,
            "units": units,
            "lang": lang,
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        weather = data.get("weather", [{}])[0]
        main = data.get("main", {})
        wind = data.get("wind", {})
        
        return {
            "city": data.get("name", city),
            "country": data.get("sys", {}).get("country", ""),
            "temp": main.get("temp", 0),
            "feels_like": main.get("feels_like", 0),
            "temp_min": main.get("temp_min", 0),
            "temp_max": main.get("temp_max", 0),
            "humidity": main.get("humidity", 0),
            "pressure": main.get("pressure", 0),
            "description": weather.get("description", ""),
            "main_condition": weather.get("main", ""),
            "wind_speed": wind.get("speed", 0),
            "clouds": data.get("clouds", {}).get("all", 0),
            "visibility": data.get("visibility", 0),
            "units": units,
        }
    
    async def fetch_forecast(self, count: int = 5) -> list[dict]:
        """Fetch 5-day forecast."""
        city = self.config.get("city", "Cairo")
        units = self.config.get("units", "metric")
        
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            "q": city,
            "appid": settings.WEATHER_API_KEY,
            "units": units,
            "cnt": count,
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        results = []
        for item in data.get("list", []):
            weather = item.get("weather", [{}])[0]
            results.append({
                "temp": item["main"]["temp"],
                "description": weather.get("description", ""),
                "date": item.get("dt_txt", ""),
            })
        return results
    
    async def validate_config(self) -> bool:
        return bool(settings.WEATHER_API_KEY)
    
    def get_available_fields(self) -> list[str]:
        return ["city", "country", "temp", "feels_like", "temp_min", "temp_max", "humidity", "description", "wind_speed"]

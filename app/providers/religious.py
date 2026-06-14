"""Religious content provider - Prayer times using Aladhan API."""
import logging
import random
from typing import Any
from datetime import datetime

import httpx

from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class ReligiousProvider(BaseProvider):
    provider_type = "religious"
    
    async def fetch(self) -> dict[str, Any]:
        content_type = self.config.get("content_type", "prayer_times")
        
        if content_type == "prayer_times":
            return await self._fetch_prayer_times()
        elif content_type == "hijri_date":
            return await self._fetch_hijri_date()
        elif content_type == "quran_verse":
            return await self._fetch_quran_verse()
        else:
            return await self._fetch_prayer_times()
    
    async def _fetch_prayer_times(self) -> dict[str, Any]:
        city = self.config.get("city", "Cairo")
        country = self.config.get("country", "Egypt")
        method = self.config.get("method", 5)  # Egyptian General Authority
        
        url = "https://api.aladhan.com/v1/timingsByCity"
        params = {
            "city": city,
            "country": country,
            "method": method,
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        timings = data.get("data", {}).get("timings", {})
        hijri = data.get("data", {}).get("date", {}).get("hijri", {})
        
        return {
            "city": city,
            "country": country,
            "fajr": timings.get("Fajr", ""),
            "sunrise": timings.get("Sunrise", ""),
            "dhuhr": timings.get("Dhuhr", ""),
            "asr": timings.get("Asr", ""),
            "maghrib": timings.get("Maghrib", ""),
            "isha": timings.get("Isha", ""),
            "hijri_date": hijri.get("date", ""),
            "hijri_day": hijri.get("day", ""),
            "hijri_month_en": hijri.get("month", {}).get("en", ""),
            "hijri_month_ar": hijri.get("month", {}).get("ar", ""),
            "hijri_year": hijri.get("year", ""),
            "gregorian_date": datetime.now().strftime("%Y-%m-%d"),
            "content_type": "prayer_times",
        }
    
    async def _fetch_hijri_date(self) -> dict[str, Any]:
        # Use current date
        today = datetime.now().strftime("%d-%m-%Y")
        url = f"https://api.aladhan.com/v1/hpiAddress/{today}"
        params = {
            "method": 5,
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        hijri = data.get("data", {}).get("date", {}).get("hijri", {})
        
        return {
            "hijri_date": hijri.get("date", ""),
            "hijri_day": hijri.get("day", ""),
            "hijri_month_en": hijri.get("month", {}).get("en", ""),
            "hijri_month_ar": hijri.get("month", {}).get("ar", ""),
            "hijri_year": hijri.get("year", ""),
            "gregorian_date": today,
            "content_type": "hijri_date",
        }
    
    async def _fetch_quran_verse(self) -> dict[str, Any]:
        """Fetch a random Quran verse using Alquran Cloud API."""
        edition = self.config.get("edition", "ar.alafasy")
        
        # Get random verse number (1-6236)
        verse_num = random.randint(1, 6236)
        url = f"https://api.alquran.cloud/v1/ayah/{verse_num}/{edition}"
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        
        ayah = data.get("data", {})
        
        return {
            "verse_text": ayah.get("text", ""),
            "surah_name_ar": ayah.get("surah", {}).get("name", ""),
            "surah_name_en": ayah.get("surah", {}).get("englishName", ""),
            "ayah_number": ayah.get("numberInSurah", 0),
            "surah_number": ayah.get("surah", {}).get("number", 0),
            "total_ayahs": ayah.get("surah", {}).get("numberOfAyahs", 0),
            "juz": ayah.get("juz", 0),
            "page": ayah.get("page", 0),
            "content_type": "quran_verse",
        }
    
    async def validate_config(self) -> bool:
        return True  # No API key required for Aladhan
    
    def get_available_fields(self) -> list[str]:
        content_type = self.config.get("content_type", "prayer_times")
        if content_type == "prayer_times":
            return ["city", "fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha", "hijri_date", "hijri_month_ar"]
        elif content_type == "quran_verse":
            return ["verse_text", "surah_name_ar", "surah_name_en", "ayah_number", "surah_number"]
        return ["hijri_date", "hijri_day", "hijri_month_ar", "hijri_year"]

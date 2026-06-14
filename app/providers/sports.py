"""Sports/Football data provider using football-data.org API."""
import logging
from typing import Any

import httpx

from app.providers.base import BaseProvider
from app.config import settings

logger = logging.getLogger(__name__)


class SportsProvider(BaseProvider):
    provider_type = "sports"
    
    async def fetch(self) -> dict[str, Any]:
        endpoint = self.config.get("endpoint", "matches")
        
        if endpoint == "matches":
            return await self._fetch_matches()
        elif endpoint == "standings":
            return await self._fetch_standings()
        elif endpoint == "scorers":
            return await self._fetch_scorers()
        else:
            return await self._fetch_matches()
    
    async def _fetch_matches(self) -> dict[str, Any]:
        competition = self.config.get("competition", "PL")
        url = f"{settings.SPORTS_API_URL}/competitions/{competition}/matches"
        headers = {"X-Auth-Token": settings.SPORTS_API_KEY}
        
        params = {}
        matchday = self.config.get("matchday")
        if matchday:
            params["matchday"] = matchday
        status = self.config.get("status", "SCHEDULED")
        params["status"] = status
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
        
        matches = data.get("matches", [])
        if not matches:
            return {"competition": competition, "match_count": 0, "matches": []}
        
        result_matches = []
        for m in matches[:5]:
            result_matches.append({
                "home_team": m["homeTeam"]["shortName"],
                "away_team": m["awayTeam"]["shortName"],
                "status": m["status"],
                "date": m.get("utcDate", ""),
                "score_home": m["score"].get("fullTime", {}).get("homeTeam"),
                "score_away": m["score"].get("fullTime", {}).get("awayTeam"),
            })
        
        return {
            "competition": competition,
            "competition_name": data.get("competition", {}).get("name", ""),
            "match_count": len(matches),
            "matches": result_matches,
        }
    
    async def _fetch_standings(self) -> dict[str, Any]:
        competition = self.config.get("competition", "PL")
        url = f"{settings.SPORTS_API_URL}/competitions/{competition}/standings"
        headers = {"X-Auth-Token": settings.SPORTS_API_KEY}
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        standings = data.get("standings", [])
        if not standings:
            return {"competition": competition, "standings": []}
        
        table = standings[0].get("table", [])[:10]
        result_table = []
        for t in table:
            result_table.append({
                "position": t["position"],
                "team": t["team"]["shortName"],
                "points": t["points"],
                "won": t["won"],
                "draw": t["draw"],
                "lost": t["lost"],
                "goal_difference": t["goalDifference"],
            })
        
        return {
            "competition": competition,
            "standings": result_table,
        }
    
    async def _fetch_scorers(self) -> dict[str, Any]:
        competition = self.config.get("competition", "PL")
        url = f"{settings.SPORTS_API_URL}/competitions/{competition}/scorers"
        headers = {"X-Auth-Token": settings.SPORTS_API_KEY}
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        scorers = data.get("scorers", [])[:10]
        result_scorers = []
        for s in scorers:
            result_scorers.append({
                "player": s["player"]["name"],
                "team": s["team"]["shortName"],
                "goals": s.get("goals", 0),
                "assists": s.get("assists", 0),
            })
        
        return {
            "competition": competition,
            "scorers": result_scorers,
        }
    
    async def validate_config(self) -> bool:
        return bool(settings.SPORTS_API_KEY)
    
    def get_available_fields(self) -> list[str]:
        return ["competition", "match_count", "home_team", "away_team", "status", "score_home", "score_away"]

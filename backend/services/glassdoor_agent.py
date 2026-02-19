"""
Glassdoor Agent — Scrapes Glassdoor reviews for team health signals.

Scrapes via ScraperAPI, then uses LLM to extract:
- Overall rating, culture score, CEO approval
- Recent review themes (positive + negative)
- Work-life balance, compensation fairness
Used as a team health signal for scoring.
"""
import os
import re
import logging
from datetime import datetime, timezone

import httpx

import db as database
from services.llm_provider import llm

logger = logging.getLogger(__name__)


class GlassdoorAgent:
    """Scrapes Glassdoor via ScraperAPI and extracts team health signals."""

    def __init__(self):
        self.scraper_key = os.getenv("SCRAPER_API_KEY")

    async def analyze(self, company_id: str, company_name: str) -> dict:
        """Scrape Glassdoor and extract team health signals."""
        if not self.scraper_key:
            return {"error": "SCRAPER_API_KEY not set", "source": "glassdoor"}

        # Step 1: Scrape Glassdoor search results
        raw_html = await self._scrape_glassdoor(company_name)
        if not raw_html:
            return {
                "found": False,
                "company_name": company_name,
                "source": "glassdoor",
                "reason": "Could not find Glassdoor page",
            }

        # Step 2: LLM extraction from HTML
        extracted = await self._extract_signals(company_name, raw_html)

        # Store in DB
        try:
            enrichment_tbl = database.enrichment_collection()
            enrichment_tbl.insert({
                "company_id": company_id,
                "source_type": "glassdoor",
                "source_url": f"https://glassdoor.com/search?q={company_name}",
                "data": extracted,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "is_valid": True,
            })
        except Exception as e:
            logger.error(f"[Glassdoor] DB store failed: {e}")

        return extracted

    async def _scrape_glassdoor(self, company_name: str) -> str:
        """Scrape Glassdoor overview page via ScraperAPI."""
        search_query = f"{company_name} reviews site:glassdoor.com"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # First: search for the company's Glassdoor page
                resp = await client.get(
                    "http://api.scraperapi.com",
                    params={
                        "api_key": self.scraper_key,
                        "url": f"https://www.google.com/search?q={search_query}",
                        "render": "false",
                    },
                )

            if resp.status_code != 200:
                return ""

            # Find Glassdoor URL in search results
            glassdoor_url = self._find_glassdoor_url(resp.text, company_name)
            if not glassdoor_url:
                return ""

            # Scrape the actual Glassdoor page
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    "http://api.scraperapi.com",
                    params={
                        "api_key": self.scraper_key,
                        "url": glassdoor_url,
                        "render": "true",  # Glassdoor needs JS
                    },
                )

            if resp.status_code == 200:
                # Strip HTML to reduce token usage
                text = re.sub(r"<script[^>]*>.*?</script>", "", resp.text, flags=re.DOTALL)
                text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text).strip()
                return text[:8000]  # Cap for LLM

        except Exception as e:
            logger.error(f"[Glassdoor] Scrape failed: {e}")

        return ""

    def _find_glassdoor_url(self, html: str, company_name: str) -> str:
        """Extract Glassdoor company URL from Google search results."""
        patterns = [
            r'(https?://www\.glassdoor\.com/Overview/[^"&\s]+)',
            r'(https?://www\.glassdoor\.com/Reviews/[^"&\s]+)',
            r'(https?://www\.glassdoor\.co\.\w+/Overview/[^"&\s]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return ""

    async def _extract_signals(self, company_name: str, raw_text: str) -> dict:
        """Use LLM to extract structured team health signals from Glassdoor text."""
        prompt = f"""You are a VC analyst evaluating team health from Glassdoor data.

COMPANY: {company_name}

GLASSDOOR PAGE TEXT:
{raw_text[:6000]}

Extract the following signals. Use "not_mentioned" if not found.

Respond with JSON only:
{{
    "found": true,
    "company_name": "{company_name}",
    "source": "glassdoor",
    "overall_rating": number or null (out of 5.0),
    "total_reviews": number or null,
    "recommend_to_friend": "percentage or not_mentioned",
    "ceo_approval": "percentage or not_mentioned",
    "ceo_name": "string or not_mentioned",
    "culture_score": number or null (out of 5.0),
    "work_life_balance": number or null (out of 5.0),
    "compensation_benefits": number or null (out of 5.0),
    "career_opportunities": number or null (out of 5.0),
    "senior_management": number or null (out of 5.0),
    "positive_themes": ["top 3-5 positive themes from reviews"],
    "negative_themes": ["top 3-5 negative themes from reviews"],
    "recent_trend": "IMPROVING / STABLE / DECLINING / not_mentioned",
    "team_health_score": number (0-10, your assessment based on all signals),
    "team_health_summary": "2-3 sentence assessment of team health",
    "red_flags": ["specific concerns"],
    "green_flags": ["specific positives"]
}}"""

        result = await llm.generate_json(
            prompt,
            "You are a VC team health analyst. Extract ONLY data visible in the Glassdoor page. Never fabricate ratings."
        )
        return result

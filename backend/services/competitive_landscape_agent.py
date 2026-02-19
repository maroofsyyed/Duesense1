"""
Competitive Landscape Agent — Deep competitive intelligence.

Step 1: Discover competitors (SerpAPI + Firecrawl)
Step 2: Profile each competitor (funding, employees, traffic, features)
Step 3: Generate feature comparison matrix via LLM
Step 4: Assess competitive moat + differentiation
"""
import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

import db as database
from services.llm_provider import llm
from integrations.clients import SerpClient, ScraperClient, EnrichlyrClient

logger = logging.getLogger(__name__)


class CompetitiveLandscapeAgent:
    """Deep competitive intelligence analysis."""

    def __init__(self):
        self.serp = SerpClient()
        self.scraper = ScraperClient()
        self.enrichlyr = EnrichlyrClient()
        self.firecrawl_key = os.getenv("FIRECRAWL_API_KEY")

    async def analyze(
        self,
        company_id: str,
        company_name: str,
        product_description: str,
        industry: str,
        website: Optional[str] = None,
    ) -> dict:
        """Run full competitive landscape analysis."""
        # Step 1: Discover competitors
        competitors = await self._discover_competitors(company_name, product_description, industry)

        # Step 2: Profile top competitors (limit to 5)
        profiles = await self._profile_competitors(competitors[:5])

        # Step 3: Generate feature comparison matrix
        matrix = await self._generate_comparison_matrix(
            company_name, product_description, profiles
        )

        # Step 4: Assess competitive moat
        moat_assessment = await self._assess_moat(
            company_name, product_description, profiles, matrix
        )

        result = {
            "competitors_found": len(competitors),
            "competitors_profiled": len(profiles),
            "competitors": profiles,
            "comparison_matrix": matrix,
            "moat_assessment": moat_assessment,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Store in DB
        try:
            enrichment_tbl = database.enrichment_collection()
            enrichment_tbl.insert({
                "company_id": company_id,
                "source_type": "competitive_landscape",
                "source_url": "multi-source",
                "data": result,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "is_valid": True,
            })

            # Also store individual competitors
            competitors_tbl = database.competitors_collection()
            for comp in profiles:
                competitors_tbl.insert({
                    "company_id": company_id,
                    "name": comp.get("name", "Unknown"),
                    "url": comp.get("website", ""),
                    "description": comp.get("description", ""),
                    "funding": comp.get("funding"),
                    "employees": comp.get("employee_count"),
                    "source_query": "competitive_landscape_agent",
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            logger.error(f"[CompLandscape] DB store failed: {e}")

        return result

    # ─── Step 1: Discover ─────────────────────────────────────────────

    async def _discover_competitors(
        self, company_name: str, product_desc: str, industry: str
    ) -> list[dict]:
        """Discover competitors via SerpAPI + Firecrawl."""
        # SerpAPI search
        serp_results = await self.serp.find_competitors(company_name, product_desc)
        competitors = serp_results.get("competitors", [])

        # Additional search for alternatives
        try:
            alt_results = await self.serp.find_competitors(
                f"{industry} {product_desc[:50]}", ""
            )
            for comp in alt_results.get("competitors", []):
                if comp.get("url") not in [c.get("url") for c in competitors]:
                    competitors.append(comp)
        except Exception:
            pass

        # Firecrawl deep search if available
        if self.firecrawl_key:
            firecrawl_comps = await self._firecrawl_search(company_name, product_desc)
            for comp in firecrawl_comps:
                if comp.get("url") not in [c.get("url") for c in competitors]:
                    competitors.append(comp)

        return competitors[:10]

    async def _firecrawl_search(self, company_name: str, product_desc: str) -> list[dict]:
        """Use Firecrawl to search for competitor pages."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.firecrawl.dev/v1/search",
                    headers={
                        "Authorization": f"Bearer {self.firecrawl_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": f"competitors of {company_name} {product_desc[:100]}",
                        "limit": 5,
                    },
                )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("data", []):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("description", ""),
                        "source_query": "firecrawl",
                    })
                return results
        except Exception as e:
            logger.warning(f"[CompLandscape] Firecrawl search failed: {e}")
        return []

    # ─── Step 2: Profile ──────────────────────────────────────────────

    async def _profile_competitors(self, competitors: list[dict]) -> list[dict]:
        """Profile each competitor: scrape website + LinkedIn data."""
        tasks = [self._profile_single(comp) for comp in competitors]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        profiles = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"[CompLandscape] Profile failed: {result}")
                continue
            if result:
                profiles.append(result)

        return profiles

    async def _profile_single(self, competitor: dict) -> dict:
        """Profile a single competitor."""
        url = competitor.get("url", "")
        name = competitor.get("title", "Unknown")

        profile = {
            "name": name,
            "website": url,
            "description": competitor.get("snippet", ""),
            "source": competitor.get("source_query", "serp"),
        }

        # Scrape website for details
        if url:
            try:
                website_data = await self.scraper.scrape_website(url)
                if not website_data.get("error"):
                    profile["website_title"] = website_data.get("title", "")
                    profile["meta_description"] = website_data.get("meta_description", "")
                    profile["has_pricing"] = website_data.get("has_pricing", False)
                    profile["has_careers"] = website_data.get("has_careers", False)
                    profile["headings"] = website_data.get("headings", {})
            except Exception:
                pass

        # Firecrawl for richer content if available
        if url and self.firecrawl_key:
            try:
                rich_content = await self._firecrawl_scrape(url)
                if rich_content:
                    profile["rich_content"] = rich_content[:2000]
            except Exception:
                pass

        # LinkedIn company data if Enrichlyer available
        if self.enrichlyr.api_key and url:
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.replace("www.", "")
                if domain:
                    li_data = await self.enrichlyr.get_company_profile(domain)
                    if "error" not in li_data:
                        profile["employee_count"] = li_data.get("company_size_on_linkedin")
                        profile["follower_count"] = li_data.get("follower_count")
                        profile["industry"] = li_data.get("industry")
                        profile["founded_year"] = li_data.get("founded_year")
                        profile["funding"] = li_data.get("extra", {}).get("total_funding_amount") if li_data.get("extra") else None
            except Exception:
                pass

        return profile

    async def _firecrawl_scrape(self, url: str) -> Optional[str]:
        """Scrape a URL via Firecrawl for markdown content."""
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                resp = await client.post(
                    "https://api.firecrawl.dev/v1/scrape",
                    headers={
                        "Authorization": f"Bearer {self.firecrawl_key}",
                        "Content-Type": "application/json",
                    },
                    json={"url": url, "formats": ["markdown"]},
                )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", {}).get("markdown", "")
        except Exception:
            pass
        return None

    async def _get_linkedin_info(self, domain: str) -> Optional[dict]:
        """Get LinkedIn company info via Enrichlyer."""
        try:
            data = await self.enrichlyr.get_company_profile(domain)
            if "error" not in data:
                return data
        except Exception:
            pass
        return None

    # ─── Step 3: Comparison Matrix ────────────────────────────────────

    async def _generate_comparison_matrix(
        self, company_name: str, product_desc: str, profiles: list[dict]
    ) -> dict:
        """Generate feature comparison matrix via LLM."""
        if not profiles:
            return {"error": "No competitors profiled"}

        prompt = f"""You are a VC analyst creating a competitive comparison matrix.

TARGET COMPANY: {company_name}
PRODUCT: {product_desc[:1000]}

COMPETITORS:
{json.dumps(profiles, default=str)[:4000]}

Create a detailed feature comparison matrix:

Respond with JSON:
{{
    "features_compared": [
        "Feature 1", "Feature 2", "Feature 3", "Feature 4", "Feature 5",
        "Feature 6", "Feature 7", "Feature 8"
    ],
    "matrix": {{
        "{company_name}": {{
            "Feature 1": "YES / NO / PARTIAL / UNKNOWN",
            "Feature 2": "YES / NO / PARTIAL / UNKNOWN"
        }},
        "Competitor 1": {{
            "Feature 1": "YES / NO / PARTIAL / UNKNOWN"
        }}
    }},
    "differentiation_factors": [
        "string - what makes target company unique"
    ],
    "parity_areas": [
        "string - where target matches competitors"
    ],
    "gaps": [
        "string - where target lags behind"
    ]
}}"""

        return await llm.generate_json(
            prompt,
            "You are a VC competitive analyst. Build the matrix from available data only."
        )

    # ─── Step 4: Moat Assessment ──────────────────────────────────────

    async def _assess_moat(
        self, company_name: str, product_desc: str,
        profiles: list[dict], matrix: dict
    ) -> dict:
        """Assess competitive moat and differentiation."""
        prompt = f"""You are a VC analyst assessing competitive moat.

TARGET: {company_name}
PRODUCT: {product_desc[:800]}

COMPETITOR PROFILES:
{json.dumps(profiles, default=str)[:2000]}

COMPARISON MATRIX:
{json.dumps(matrix, default=str)[:1500]}

Assess the competitive moat:

Respond with JSON:
{{
    "moat_type": "NETWORK_EFFECTS / DATA / SWITCHING_COSTS / BRAND / TECHNOLOGY / REGULATORY / NONE",
    "moat_strength": "STRONG / MODERATE / WEAK / NONE",
    "moat_score": number (1-10),
    "defensibility_timeline": "string - how long the moat can hold",
    "competitive_threats": [
        {{
            "threat": "string",
            "severity": "HIGH / MEDIUM / LOW",
            "timeline": "string"
        }}
    ],
    "strategic_recommendations": [
        "string - how to strengthen moat"
    ],
    "winner_take_all": true/false,
    "market_consolidation_risk": "HIGH / MEDIUM / LOW",
    "summary": "3-4 sentence competitive moat assessment"
}}"""

        return await llm.generate_json(
            prompt,
            "You are a VC competitive moat analyst. Assess based on data only."
        )

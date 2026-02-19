"""
Milestone Tracker Agent — Product milestone timeline extraction.

Extracts product milestones from deck + news + blog posts.
Timeline: product launches, customer wins, funding events, team growth.
Outputs structured milestone list for the report.
"""
import json
import logging
from datetime import datetime, timezone

import db as database
from services.llm_provider import llm

logger = logging.getLogger(__name__)


class MilestoneTrackerAgent:
    """Extracts and structures company milestone timeline."""

    async def analyze(
        self,
        company_id: str,
        company_name: str,
        extracted: dict,
        enrichment: dict,
    ) -> dict:
        """
        Extract milestones from all available data sources.
        Returns structured timeline.
        """
        # Gather data from multiple sources
        deck_data = {
            "traction": extracted.get("traction", {}),
            "funding": extracted.get("funding", {}),
            "company": extracted.get("company", {}),
            "solution": extracted.get("solution", {}),
        }

        news_data = enrichment.get("news", {})
        github_data = enrichment.get("github", {})
        website_data = enrichment.get("website_intelligence", {})

        # LLM synthesis
        milestones = await self._extract_milestones(
            company_name, deck_data, news_data, github_data, website_data
        )

        milestones["analyzed_at"] = datetime.now(timezone.utc).isoformat()

        # Store in DB
        try:
            enrichment_tbl = database.enrichment_collection()
            enrichment_tbl.insert({
                "company_id": company_id,
                "source_type": "milestones",
                "source_url": "multi-source",
                "data": milestones,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "is_valid": True,
            })
        except Exception as e:
            logger.error(f"[Milestones] DB store failed: {e}")

        return milestones

    async def _extract_milestones(
        self,
        company_name: str,
        deck_data: dict,
        news_data: dict,
        github_data: dict,
        website_data: dict,
    ) -> dict:
        """Use LLM to extract and structure milestones from all sources."""
        prompt = f"""You are a VC analyst creating a milestone timeline for {company_name}.

DECK DATA:
{json.dumps(deck_data, default=str)[:2500]}

NEWS ARTICLES:
{json.dumps(news_data, default=str)[:2000]}

GITHUB DATA:
{json.dumps(github_data, default=str)[:800]}

WEBSITE INTELLIGENCE:
{json.dumps(website_data.get('product_intel', {}), default=str)[:800] if isinstance(website_data, dict) else 'N/A'}

Extract all milestones and events. For each, cite the source.
Use "not_mentioned" for dates you cannot determine.

Respond with JSON:
{{
    "milestones": [
        {{
            "date": "YYYY-MM or YYYY or not_mentioned",
            "category": "FOUNDING / PRODUCT_LAUNCH / FUNDING / CUSTOMER_WIN / PARTNERSHIP / TEAM / PIVOT / EXPANSION / AWARD / OTHER",
            "title": "string - brief milestone title",
            "description": "string - 1-2 sentence description",
            "impact": "HIGH / MEDIUM / LOW",
            "source": "deck / news / github / website / inferred",
            "citation": "[SOURCE: specific source]"
        }}
    ],
    "timeline_summary": {{
        "earliest_event": "date or not_mentioned",
        "latest_event": "date or not_mentioned",
        "total_milestones": number,
        "funding_rounds": number,
        "product_launches": number,
        "customer_wins": number
    }},
    "velocity_assessment": {{
        "execution_speed": "FAST / MODERATE / SLOW",
        "milestone_density": "HIGH / MEDIUM / LOW - milestones per year",
        "momentum": "ACCELERATING / STEADY / DECELERATING / not_enough_data",
        "assessment": "2-3 sentence assessment of execution velocity"
    }},
    "key_inflection_points": [
        "string - most significant milestones that changed trajectory"
    ],
    "missing_milestones": [
        "string - expected milestones for this stage that are missing"
    ]
}}"""

        return await llm.generate_json(
            prompt,
            "You are a VC milestone analyst. Extract ONLY milestones that are explicitly mentioned or strongly evidenced. Cite sources for everything."
        )

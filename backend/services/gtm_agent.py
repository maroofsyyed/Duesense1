"""
GTM Analysis Agent — Go-to-market strategy synthesis.

Synthesizes GTM strategy from website + deck data.
Identifies: sales motion (PLG vs SLG), target segments, channel mix.
Extracts pricing strategy, customer acquisition approach.
Outputs structured GTM section for the report.
"""
import json
import logging
from datetime import datetime, timezone

import db as database
from services.llm_provider import llm

logger = logging.getLogger(__name__)


class GTMAnalysisAgent:
    """Analyzes go-to-market strategy from available data."""

    async def analyze(
        self,
        company_id: str,
        extracted: dict,
        enrichment: dict,
    ) -> dict:
        """
        Synthesize GTM strategy analysis from all available data.
        Returns structured GTM assessment.
        """
        # Gather all relevant data
        website_data = enrichment.get("website", {})
        website_intel = enrichment.get("website_intelligence", {})
        competitors = enrichment.get("competitors", {})
        social = enrichment.get("social_signals", {})

        solution = extracted.get("solution", {})
        business_model = extracted.get("business_model", {})
        traction = extracted.get("traction", {})
        market = extracted.get("market", {})

        analysis = await self._synthesize_gtm(
            extracted, website_data, website_intel, competitors, social,
            solution, business_model, traction, market
        )

        analysis["analyzed_at"] = datetime.now(timezone.utc).isoformat()

        # Store in DB
        try:
            enrichment_tbl = database.enrichment_collection()
            enrichment_tbl.insert({
                "company_id": company_id,
                "source_type": "gtm_analysis",
                "source_url": "llm_synthesis",
                "data": analysis,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "is_valid": True,
            })
        except Exception as e:
            logger.error(f"[GTMAgent] DB store failed: {e}")

        return analysis

    async def _synthesize_gtm(
        self, extracted, website, website_intel, competitors, social,
        solution, business_model, traction, market
    ) -> dict:
        """LLM-powered GTM strategy synthesis."""
        prompt = f"""You are a VC analyst evaluating a startup's go-to-market strategy.

COMPANY SOLUTION:
{json.dumps(solution, default=str)[:1500]}

BUSINESS MODEL:
{json.dumps(business_model, default=str)[:1000]}

TRACTION DATA:
{json.dumps(traction, default=str)[:1000]}

MARKET:
{json.dumps(market, default=str)[:800]}

WEBSITE SIGNALS:
- Has pricing page: {website.get('has_pricing', 'unknown')}
- Has careers page: {website.get('has_careers', 'unknown')}
{json.dumps(website_intel.get('product_intel', {}), default=str)[:800] if isinstance(website_intel, dict) else 'N/A'}

COMPETITIVE DATA:
{json.dumps(competitors, default=str)[:800]}

SOCIAL PRESENCE:
{json.dumps(social.get('composite_score', {}), default=str)[:500] if isinstance(social, dict) else 'N/A'}

Analyze the GTM strategy comprehensively:

Respond with JSON:
{{
    "sales_motion": {{
        "primary": "PLG / SLG / HYBRID / MARKETPLACE / not_mentioned",
        "evidence": ["specific evidence for this classification"],
        "maturity": "EARLY / DEVELOPING / MATURE"
    }},
    "target_segments": {{
        "primary_icp": "string - ideal customer profile",
        "secondary_icp": "string or not_mentioned",
        "segment_size": "SMB / MID_MARKET / ENTERPRISE / CONSUMER / MIXED",
        "vertical_focus": ["specific verticals if any"]
    }},
    "channel_mix": {{
        "primary_channels": ["e.g. Direct Sales, Content Marketing, Product Virality"],
        "secondary_channels": ["e.g. Partnerships, Events"],
        "channel_effectiveness": "string - assessment of channel strategy"
    }},
    "pricing_strategy": {{
        "model": "FREEMIUM / SUBSCRIPTION / USAGE_BASED / ONE_TIME / HYBRID / not_mentioned",
        "tiers": ["tier names if visible"],
        "price_points": "string or not_mentioned",
        "competitive_positioning": "PREMIUM / MID / VALUE / not_mentioned"
    }},
    "customer_acquisition": {{
        "cac_efficiency": "HIGH / MEDIUM / LOW / unknown",
        "virality_coefficient": "string or not_mentioned",
        "key_growth_loops": ["identified growth loops"],
        "expansion_strategy": "string - how they expand within accounts"
    }},
    "gtm_maturity_score": number (1-10),
    "strengths": ["specific GTM strengths"],
    "weaknesses": ["specific GTM weaknesses"],
    "recommendations": ["actionable recommendations"],
    "comparable_gtm": "string - which successful company's GTM this resembles",
    "summary": "4-5 sentence GTM strategy assessment"
}}"""

        return await llm.generate_json(
            prompt,
            "You are a VC GTM strategy analyst. Analyze based on available data. Use 'not_mentioned' when data is missing."
        )

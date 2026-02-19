"""
Market Sizing Agent — TAM/SAM/SOM analysis with methodology.

Input: company industry + product description from deck
Process: searches market research sources (SerpAPI) + LLM synthesis
Output: TAM/SAM/SOM with methodology, CAGR, growth drivers
Validates/challenges deck's market size claims.
"""
import json
import logging
from datetime import datetime, timezone

import db as database
from services.llm_provider import llm
from integrations.clients import SerpClient

logger = logging.getLogger(__name__)


class MarketSizingAgent:
    """Researches and validates market size claims."""

    def __init__(self):
        self.serp = SerpClient()

    async def analyze(
        self,
        company_id: str,
        industry: str,
        product_description: str,
        deck_market_claims: dict,
    ) -> dict:
        """
        Research market size and validate deck claims.
        Returns structured TAM/SAM/SOM with methodology.
        """
        # Step 1: Search for market data
        research = await self._research_market(industry, product_description)

        # Step 2: LLM synthesis
        analysis = await self._synthesize(
            industry, product_description, deck_market_claims, research
        )

        analysis["research_sources"] = research.get("results", [])[:5]
        analysis["analyzed_at"] = datetime.now(timezone.utc).isoformat()

        # Store in DB
        try:
            enrichment_tbl = database.enrichment_collection()
            enrichment_tbl.insert({
                "company_id": company_id,
                "source_type": "market_sizing",
                "source_url": "serpapi+llm",
                "data": analysis,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "is_valid": True,
            })
        except Exception as e:
            logger.error(f"[MarketSizing] DB store failed: {e}")

        return analysis

    async def _research_market(self, industry: str, product_description: str) -> dict:
        """Search for market size data via SerpAPI."""
        queries = [
            f"{industry} market size 2024 2025",
            f"{industry} TAM SAM market opportunity",
            f"{industry} market growth CAGR forecast",
        ]

        all_results = []
        for query in queries:
            try:
                data = await self.serp.search_market(query)
                all_results.extend(data.get("results", []))
            except Exception as e:
                logger.warning(f"[MarketSizing] Search failed for '{query}': {e}")

        # Deduplicate
        seen = set()
        unique = []
        for r in all_results:
            url = r.get("url", "")
            if url not in seen:
                seen.add(url)
                unique.append(r)

        return {"results": unique[:10]}

    async def _synthesize(
        self,
        industry: str,
        product_description: str,
        deck_claims: dict,
        research: dict,
    ) -> dict:
        """LLM synthesis of market size data."""
        prompt = f"""You are a VC market analyst performing TAM/SAM/SOM analysis.

INDUSTRY: {industry}
PRODUCT: {product_description[:1500]}

DECK'S MARKET CLAIMS:
{json.dumps(deck_claims, default=str)[:2000]}

MARKET RESEARCH DATA:
{json.dumps(research.get('results', []), default=str)[:3000]}

Perform a comprehensive market sizing analysis:

1. Calculate TAM/SAM/SOM with clear methodology
2. Identify CAGR and growth trajectory
3. Validate or challenge the deck's market claims
4. Identify growth drivers and headwinds

Respond with JSON:
{{
    "tam": {{
        "value_usd": "string - e.g. '$50B'",
        "methodology": "string - how you calculated this",
        "confidence": "HIGH/MEDIUM/LOW",
        "source_citations": ["sources used"]
    }},
    "sam": {{
        "value_usd": "string",
        "methodology": "string",
        "confidence": "HIGH/MEDIUM/LOW",
        "geographic_scope": "string"
    }},
    "som": {{
        "value_usd": "string",
        "methodology": "string",
        "realistic_capture_timeline": "string - e.g. '3-5 years'"
    }},
    "cagr": {{
        "rate": "string - e.g. '15.2%'",
        "period": "string - e.g. '2024-2030'",
        "source": "string"
    }},
    "growth_drivers": [
        "string - key growth drivers"
    ],
    "headwinds": [
        "string - market risks or headwinds"
    ],
    "deck_validation": {{
        "claims_accurate": true/false,
        "discrepancies": ["specific issues with deck's market claims"],
        "notes": "string - overall assessment of deck's market narrative"
    }},
    "market_maturity": "EMERGING / GROWING / MATURE / DECLINING",
    "competitive_intensity": "LOW / MEDIUM / HIGH",
    "market_timing_score": number (1-10),
    "summary": "3-4 sentence market sizing summary"
}}"""

        return await llm.generate_json(
            prompt,
            "You are a VC market sizing specialist. Use data from research sources. When uncertain, state assumptions clearly. Never fabricate numbers."
        )

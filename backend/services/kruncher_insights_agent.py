"""
Kruncher Insights Agent — generates strengths, risks, questions & ice-breakers.

Runs LAST in the pipeline (Stage 5). Has access to ALL enrichment + scoring results.
Uses Z.ai via llm_provider for JSON generation.
Stores result in enrichment_sources with source_type="kruncher_insights".
"""
import json
import logging
import os
from datetime import datetime, timezone

import db as database

logger = logging.getLogger(__name__)


class KruncherInsightsAgent:
    """
    Generates investment insights — the "Kruncher Insights" section.

    4 sub-sections:
      A. Strengths (3-5 items)
      B. Risks (3-5 items)
      C. Investment Questions (5-7 items, data-gap-driven)
      D. Ice Breakers (3-5 items, grounded in founder LinkedIn data)
    """

    def __init__(self):
        pass

    async def analyze(
        self,
        company_id: str,
        extracted_deck_data: dict,
        all_enrichment_data: dict,
        investment_score: dict,
    ) -> dict:
        """
        Generate Kruncher Insights from complete pipeline data.

        Args:
            company_id: UUID of the company
            extracted_deck_data: Deck extraction output
            all_enrichment_data: Merged enrichment from all agents
            investment_score: Scoring result with total_score, tier, etc.
        """
        try:
            return await self._run(
                company_id, extracted_deck_data, all_enrichment_data, investment_score
            )
        except Exception as e:
            logger.error(f"[KruncherInsights] Failed for {company_id}: {e}")
            return {}

    async def _run(self, company_id, extracted, enrichment, score) -> dict:
        company_name = extracted.get("company", {}).get("name", "Unknown")
        logger.info(f"[KruncherInsights] Generating for {company_name} ({company_id})")

        # ── Build the comprehensive prompt ────────────────────────────────
        prompt = self._build_prompt(company_name, extracted, enrichment, score)

        # ── Call LLM (Z.ai via llm_provider) ────────────────────────────────
        insights = await self._call_llm(prompt)

        if not insights or "error" in insights:
            logger.warning(f"[KruncherInsights] LLM failed, returning minimal")
            insights = self._minimal_fallback(score)

        # ── Compute data completeness ─────────────────────────────────────
        completeness = self._data_completeness(enrichment)
        insights["data_completeness_score"] = completeness
        insights["confidence_level"] = (
            "HIGH" if completeness >= 70 else "MEDIUM" if completeness >= 40 else "LOW"
        )

        # ── Store in enrichment_sources ───────────────────────────────────
        try:
            database.enrichment_collection().insert({
                "company_id": company_id,
                "source_type": "kruncher_insights",
                "source_url": "kruncher_insights_agent",
                "data": insights,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "is_valid": True,
            })
        except Exception as e:
            logger.warning(f"[KruncherInsights] enrichment_sources write failed: {e}")

        # ── Also write to kruncher_insights table (fast API access) ───────
        try:
            ki_tbl = database.get_client().table("kruncher_insights")
            ki_tbl.upsert({
                "company_id": company_id,
                "strengths": insights.get("strengths", []),
                "risks": insights.get("risks", []),
                "investment_questions": insights.get("investment_questions", []),
                "ice_breakers": insights.get("ice_breakers", []),
                "confidence_level": insights.get("confidence_level"),
                "data_completeness_score": completeness,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
        except Exception as e:
            logger.warning(f"[KruncherInsights] kruncher_insights table write failed: {e}")

        logger.info(
            f"[KruncherInsights] Done for {company_id}: "
            f"{len(insights.get('strengths', []))} strengths, "
            f"{len(insights.get('risks', []))} risks, "
            f"completeness={completeness}%"
        )
        return insights

    # ── Prompt Builder ────────────────────────────────────────────────────

    def _build_prompt(self, name, extracted, enrichment, score) -> str:
        """Build a comprehensive prompt with all available data."""

        # Truncated JSON helpers
        def j(data, limit=800):
            try:
                return json.dumps(data, default=str)[:limit]
            except Exception:
                return str(data)[:limit]

        # Gather enrichment sections
        linkedin = enrichment.get("linkedin_enrichment", {})
        funding = enrichment.get("funding_history", {})
        market = enrichment.get("market_analysis", enrichment.get("market_sizing", {}))
        competitive = enrichment.get("competitive_landscape", {})
        social = enrichment.get("social_signals", {})
        web_traffic = enrichment.get("web_traffic", {})
        milestones = enrichment.get("milestones", {})
        founders = enrichment.get("founder_profiles", {})
        gtm = enrichment.get("gtm_analysis", {})

        return f"""You are a senior VC partner generating the "Kruncher Insights" section for {name}.

CONTEXT — COMPLETE DATA PICTURE:

INVESTMENT SCORE: {score.get('total_score', 'N/A')}/100 — {score.get('tier', 'N/A')}
Recommendation: {score.get('recommendation', 'N/A')}
Top Reasons: {j(score.get('top_reasons', []))}
Top Risks: {j(score.get('top_risks', []))}

DECK DATA: {j(extracted, 1200)}

LINKEDIN ENRICHMENT: {j(linkedin, 600)}
FOUNDER PROFILES: {j(founders, 600)}
FUNDING HISTORY: {j(funding, 600)}
MARKET ANALYSIS: {j(market, 600)}
COMPETITIVE LANDSCAPE: {j(competitive, 600)}
SOCIAL SIGNALS: {j(social, 400)}
WEB TRAFFIC: {j(web_traffic, 400)}
GTM ANALYSIS: {j(gtm, 400)}
MILESTONES: {j(milestones, 400)}

Generate a JSON response with EXACTLY this structure:
{{
  "strengths": [
    {{
      "title": "Concise strength title",
      "evidence": "SPECIFIC data point from the enrichment data above",
      "source": "agent_name that provided this data",
      "strength_score": 1-5
    }}
  ],
  "risks": [
    {{
      "title": "Concise risk title",
      "description": "Detailed description",
      "severity": "HIGH|MEDIUM|LOW",
      "mitigation": "What the company could do to address this",
      "evidence": "SPECIFIC data point showing this risk"
    }}
  ],
  "investment_questions": [
    {{
      "question": "Specific question grounded in data gaps",
      "rationale": "Why this matters based on what we found",
      "what_good_answer_looks_like": "What would be reassuring"
    }}
  ],
  "ice_breakers": [
    {{
      "specific_to": "founder_name",
      "opener": "Conversational opener referencing something specific",
      "context": "Why this works as an ice breaker"
    }}
  ]
}}

RULES:
1. Generate 3-5 STRENGTHS with real data evidence (not generic)
2. Generate 3-5 RISKS with severity ratings and mitigations
3. Generate 5-7 INVESTMENT QUESTIONS — must be specific to THIS company based on data gaps
4. Generate 3-5 ICE BREAKERS — must reference specific founder data (prior companies, schools, career moments)
5. Every item must cite actual data from the enrichment. No generic boilerplate.
6. If founder LinkedIn data is unavailable, make ice breakers based on deck data instead."""

    # ── LLM Call ──────────────────────────────────────────────────────────

    async def _call_llm(self, prompt: str) -> dict:
        """Call Z.ai via llm_provider for insight generation."""
        try:
            from services.llm_provider import llm

            return await llm.generate_json(
                prompt,
                "You are a world-class VC analyst. Generate specific, data-grounded investment insights.",
            )
        except Exception as e:
            logger.warning(f"[KruncherInsights] llm_provider failed: {e}")
            return {"error": str(e)}

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _data_completeness(enrichment: dict) -> float:
        """Score how complete our data picture is (0-100)."""
        sources = [
            "linkedin_enrichment", "funding_history", "web_traffic",
            "social_signals", "market_analysis", "market_sizing",
            "competitive_landscape", "milestones", "gtm_analysis",
            "website_intelligence", "github", "news",
            "founder_profiles", "glassdoor",
        ]
        available = 0
        for s in sources:
            data = enrichment.get(s, {})
            if data and isinstance(data, dict) and "error" not in data:
                available += 1
        return round(available / len(sources) * 100, 1)

    @staticmethod
    def _minimal_fallback(score: dict) -> dict:
        """Generate minimal insights when LLM fails."""
        return {
            "strengths": [
                {
                    "title": "Investment analysis completed",
                    "evidence": f"Score: {score.get('total_score', 'N/A')}/100",
                    "source": "scorer",
                    "strength_score": 3,
                }
            ],
            "risks": [
                {
                    "title": "Incomplete data analysis",
                    "description": "LLM analysis could not be completed for detailed insights",
                    "severity": "MEDIUM",
                    "mitigation": "Manual review recommended",
                    "evidence": "LLM call failed",
                }
            ],
            "investment_questions": [
                {
                    "question": "What is the company's current revenue run rate?",
                    "rationale": "Core metric for investment evaluation",
                    "what_good_answer_looks_like": "Growing ARR with positive unit economics",
                }
            ],
            "ice_breakers": [],
        }


async def run_kruncher_insights_agent(
    company_id: str,
    extracted_deck_data: dict,
    all_enrichment_data: dict,
    investment_score: dict,
) -> dict:
    """Module-level entry point matching spec signature."""
    agent = KruncherInsightsAgent()
    return await agent.analyze(
        company_id, extracted_deck_data, all_enrichment_data, investment_score
    )

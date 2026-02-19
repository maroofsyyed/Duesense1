"""
Web Traffic Agent — enriches company with web traffic estimates.

Uses EnrichlyrClient.get_web_traffic() for domain traffic data.
Stores result in enrichment_sources with source_type="web_traffic".
"""
import logging
from datetime import datetime, timezone

import db as database
from integrations.clients import EnrichlyrClient

logger = logging.getLogger(__name__)


class WebTrafficAgent:
    """Fetches web traffic estimates for a company domain."""

    def __init__(self):
        self.enrichlyr = EnrichlyrClient()

    async def analyze(self, company_id: str, website: str) -> dict:
        """
        Run the web traffic agent.

        Args:
            company_id: UUID of the company
            website: Company website URL or domain
        """
        try:
            return await self._run(company_id, website)
        except Exception as e:
            logger.error(f"[WebTrafficAgent] Failed for {company_id}: {e}")
            return {}

    async def _run(self, company_id: str, website: str) -> dict:
        domain = website.replace("https://", "").replace("http://", "").split("/")[0]
        logger.info(f"[WebTrafficAgent] Starting for {domain} ({company_id})")

        # ── Try Enrichlyer first ──────────────────────────────────────────
        data = await self.enrichlyr.get_web_traffic(domain)

        if "error" in data or data.get("found") is False:
            logger.warning(f"[WebTrafficAgent] Enrichlyr returned no data for {domain}")
            data = {}

        # ── Normalize response ────────────────────────────────────────────
        monthly_visits = data.get("monthly_visits", data.get("visits", None))
        if isinstance(monthly_visits, str):
            try:
                monthly_visits = int(monthly_visits.replace(",", ""))
            except ValueError:
                monthly_visits = None

        # Traffic trend
        trend_pct = data.get("trend_pct_3m", data.get("growth_pct", None))
        if trend_pct is not None:
            try:
                trend_pct = float(trend_pct)
                trend = "UP" if trend_pct > 5 else "DOWN" if trend_pct < -5 else "STABLE"
            except (ValueError, TypeError):
                trend = "STABLE"
                trend_pct = None
        else:
            trend = "STABLE"

        # Traffic sources
        sources = data.get("traffic_sources", data.get("sources", {}))
        if not isinstance(sources, dict):
            sources = {}

        # Keywords
        keywords = data.get("top_keywords", data.get("keywords", []))
        if not isinstance(keywords, list):
            keywords = []

        result = {
            "monthly_visits": monthly_visits,
            "monthly_visits_trend": trend,
            "trend_pct_3m": trend_pct,
            "traffic_sources": {
                "organic_search": sources.get("organic_search", sources.get("organic", None)),
                "direct": sources.get("direct", None),
                "referral": sources.get("referral", None),
                "social": sources.get("social", None),
                "paid": sources.get("paid", sources.get("paid_search", None)),
            },
            "top_keywords": keywords[:10],
            "domain_authority": data.get("domain_authority", data.get("authority_score", None)),
            "global_rank": data.get("global_rank", data.get("rank", None)),
            "status": "available" if monthly_visits else "unavailable",
            "source": "enrichlyr",
        }

        # ── Store in DB ───────────────────────────────────────────────────
        try:
            database.enrichment_collection().insert({
                "company_id": company_id,
                "source_type": "web_traffic",
                "source_url": domain,
                "data": result,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "is_valid": True,
            })
        except Exception as e:
            logger.warning(f"[WebTrafficAgent] DB write failed: {e}")

        # ── Update companies table ────────────────────────────────────────
        if monthly_visits:
            try:
                database.companies_collection().update(
                    {"id": company_id},
                    {
                        "monthly_web_visits": monthly_visits,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception as e:
                logger.warning(f"[WebTrafficAgent] Company update failed: {e}")

        logger.info(
            f"[WebTrafficAgent] Done for {company_id}: "
            f"{monthly_visits or 'N/A'} monthly visits ({result['status']})"
        )
        return result




async def run_web_traffic_agent(company_id: str, website: str) -> dict:
    """Module-level entry point matching spec signature."""
    agent = WebTrafficAgent()
    return await agent.analyze(company_id, website)

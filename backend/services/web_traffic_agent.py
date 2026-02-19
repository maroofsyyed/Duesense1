"""
Web Traffic Agent — enriches company with web traffic estimates.

Uses EnrichlyrClient.get_web_traffic() with SEMRUSH_API_KEY fallback.
Stores result in enrichment_sources with source_type="web_traffic".
"""
import logging
import os
from datetime import datetime, timezone

import httpx

import db as database
from integrations.clients import EnrichlyrClient

logger = logging.getLogger(__name__)


class WebTrafficAgent:
    """Fetches web traffic estimates for a company domain."""

    def __init__(self):
        self.enrichlyr = EnrichlyrClient()
        self.semrush_key = os.environ.get("SEMRUSH_API_KEY")

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
            logger.info(f"[WebTrafficAgent] Enrichlyer unavailable, trying fallback")
            data = await self._semrush_fallback(domain)

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
            "source": "enrichlyer" if "error" not in data else "semrush",
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

    async def _semrush_fallback(self, domain: str) -> dict:
        """Fallback to Semrush API if SEMRUSH_API_KEY is set."""
        if not self.semrush_key:
            return {"error": "No fallback available", "status": "unavailable"}

        try:
            url = (
                f"https://api.semrush.com/"
                f"?type=domain_rank&key={self.semrush_key}"
                f"&export_columns=Dn,Rk,Or,Ot,Oc,Ad,At,Ac"
                f"&domain={domain}"
            )
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url)

            if resp.status_code != 200:
                return {"error": f"Semrush HTTP {resp.status_code}"}

            lines = resp.text.strip().split("\n")
            if len(lines) < 2:
                return {"error": "Semrush returned no data"}

            headers = lines[0].split(";")
            values = lines[1].split(";")
            row = dict(zip(headers, values))

            return {
                "monthly_visits": self._safe_int(row.get("Ot", 0)) + self._safe_int(row.get("At", 0)),
                "domain_authority": self._safe_int(row.get("Rk")),
                "traffic_sources": {
                    "organic": self._safe_int(row.get("Ot", 0)),
                    "paid": self._safe_int(row.get("At", 0)),
                },
            }
        except Exception as e:
            logger.warning(f"[WebTrafficAgent] Semrush fallback failed: {e}")
            return {"error": str(e)}

    @staticmethod
    def _safe_int(val) -> int:
        try:
            return int(val)
        except (ValueError, TypeError):
            return 0


async def run_web_traffic_agent(company_id: str, website: str) -> dict:
    """Module-level entry point matching spec signature."""
    agent = WebTrafficAgent()
    return await agent.analyze(company_id, website)

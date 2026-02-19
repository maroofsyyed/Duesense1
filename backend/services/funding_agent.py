"""
Funding History Agent — enriches company with funding round data.

Uses EnrichlyrClient.get_funding_history() and cross-references with deck claims.
Stores result in enrichment_sources with source_type="funding_history".
"""
import logging
import os
from datetime import datetime, timezone

import db as database
from integrations.clients import EnrichlyrClient

logger = logging.getLogger(__name__)


class FundingHistoryAgent:
    """Fetches and validates funding history for a company."""

    def __init__(self):
        self.enrichlyr = EnrichlyrClient()

    async def analyze(
        self,
        company_id: str,
        company_name: str,
        website: str = None,
        deck_funding_data: dict = None,
    ) -> dict:
        """
        Run the funding history agent.

        Args:
            company_id: UUID of the company
            company_name: Company name for API lookup
            website: Company website for domain-based lookup
            deck_funding_data: Funding data extracted from the pitch deck
        """
        try:
            return await self._run(company_id, company_name, website, deck_funding_data or {})
        except Exception as e:
            logger.error(f"[FundingAgent] Failed for {company_id}: {e}")
            return {}

    async def _run(self, company_id, company_name, website, deck_funding) -> dict:
        logger.info(f"[FundingAgent] Starting for {company_name} ({company_id})")

        # ── Fetch from Enrichlayer ─────────────────────────────────────────
        api_data = await self.enrichlyr.get_funding_history(company_name, website)

        if "error" in api_data:
            logger.warning(f"[FundingAgent] API error: {api_data['error']}")
            # Fall back to deck data only
            return self._build_deck_only_result(company_id, deck_funding)

        # ── Parse rounds ──────────────────────────────────────────────────
        raw_rounds = api_data.get("rounds", api_data.get("funding_rounds", []))
        if not isinstance(raw_rounds, list):
            raw_rounds = []

        all_rounds = []
        total_raised = 0
        all_investors = set()

        for r in raw_rounds:
            amount = self._parse_amount(r.get("amount", r.get("amount_usd", 0)))
            round_entry = {
                "round_type": r.get("round_type", r.get("series", "Unknown")),
                "amount_usd": amount,
                "date": r.get("date", r.get("announced_date", "")),
                "lead_investors": r.get("lead_investors", []),
                "all_investors": r.get("investors", r.get("all_investors", [])),
                "post_money_valuation": r.get("post_money_valuation"),
            }
            all_rounds.append(round_entry)
            total_raised += amount
            for inv in round_entry["all_investors"]:
                if isinstance(inv, str):
                    all_investors.add(inv)

        # Sort by date (most recent first)
        all_rounds.sort(key=lambda x: x.get("date", ""), reverse=True)

        last_round = all_rounds[0] if all_rounds else {}

        # ── Compute days since last round ─────────────────────────────────
        days_since = None
        if last_round.get("date"):
            try:
                last_date = datetime.strptime(last_round["date"][:7], "%Y-%m")
                days_since = (datetime.now() - last_date).days
            except (ValueError, TypeError):
                pass

        # ── Notable investors ─────────────────────────────────────────────
        notable = self._identify_notable_investors(all_investors)

        # ── Cross-reference with deck ─────────────────────────────────────
        discrepancy, discrepancy_details = self._check_discrepancy(
            deck_funding, total_raised, all_rounds
        )

        # ── Investor tier score (0-10) ────────────────────────────────────
        tier_score = self._score_investors(notable, total_raised, len(all_rounds))

        result = {
            "all_rounds": all_rounds,
            "total_raised_usd": total_raised,
            "last_round_date": last_round.get("date", ""),
            "last_round_type": last_round.get("round_type", ""),
            "notable_investors": list(notable),
            "investor_tier_score": tier_score,
            "days_since_last_round": days_since,
            "discrepancy_with_deck": discrepancy,
            "discrepancy_details": discrepancy_details,
            "source": "enrichlayer",
        }

        # ── Store in DB ───────────────────────────────────────────────────
        self._store(company_id, result)

        # ── Update companies table ────────────────────────────────────────
        try:
            database.companies_collection().update(
                {"id": company_id},
                {
                    "total_funding_usd": total_raised if total_raised else None,
                    "last_funding_date": last_round.get("date", ""),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            logger.warning(f"[FundingAgent] Company update failed: {e}")

        logger.info(
            f"[FundingAgent] Done for {company_id}: "
            f"${total_raised:,.0f} raised across {len(all_rounds)} rounds"
        )
        return result

    # ── Helpers ────────────────────────────────────────────────────────────

    def _build_deck_only_result(self, company_id, deck_funding) -> dict:
        """Build a result from deck data only when API is unavailable."""
        amount = self._parse_amount(deck_funding.get("total_raised", 0))
        result = {
            "all_rounds": [],
            "total_raised_usd": amount,
            "last_round_date": deck_funding.get("last_round_date", ""),
            "last_round_type": deck_funding.get("current_round", ""),
            "notable_investors": [],
            "investor_tier_score": 0,
            "days_since_last_round": None,
            "discrepancy_with_deck": False,
            "discrepancy_details": None,
            "source": "deck_only",
        }
        self._store(company_id, result)
        return result

    def _store(self, company_id, data):
        try:
            database.enrichment_collection().insert({
                "company_id": company_id,
                "source_type": "funding_history",
                "source_url": "enrichlayer",
                "data": data,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "is_valid": True,
            })
        except Exception as e:
            logger.warning(f"[FundingAgent] DB write failed: {e}")

    @staticmethod
    def _parse_amount(raw) -> int:
        if isinstance(raw, (int, float)):
            return int(raw)
        if isinstance(raw, str):
            raw = raw.replace("$", "").replace(",", "").strip()
            try:
                multiplier = 1
                if raw.lower().endswith("m"):
                    multiplier = 1_000_000
                    raw = raw[:-1]
                elif raw.lower().endswith("b"):
                    multiplier = 1_000_000_000
                    raw = raw[:-1]
                elif raw.lower().endswith("k"):
                    multiplier = 1_000
                    raw = raw[:-1]
                return int(float(raw) * multiplier)
            except (ValueError, TypeError):
                return 0
        return 0

    TIER_1_INVESTORS = {
        "sequoia", "a16z", "andreessen horowitz", "benchmark", "accel",
        "greylock", "lightspeed", "general catalyst", "tiger global",
        "insight partners", "bessemer", "founders fund", "khosla",
        "index ventures", "ggv capital", "softbank", "coatue",
        "y combinator", "yc", "500 startups", "techstars",
    }

    def _identify_notable_investors(self, investors: set) -> set:
        notable = set()
        for inv in investors:
            if inv.lower() in self.TIER_1_INVESTORS:
                notable.add(inv)
        return notable

    def _check_discrepancy(self, deck_funding, api_total, api_rounds) -> tuple:
        deck_total = self._parse_amount(deck_funding.get("total_raised", 0))
        if not deck_total or not api_total:
            return False, None

        diff_pct = abs(api_total - deck_total) / max(deck_total, 1) * 100
        if diff_pct > 30:
            return True, (
                f"Deck claims ${deck_total:,.0f} raised, "
                f"Enrichlayer shows ${api_total:,.0f} ({diff_pct:.0f}% difference)"
            )
        return False, None

    @staticmethod
    def _score_investors(notable, total_raised, num_rounds) -> float:
        score = 0.0
        # Notable investor bonus (up to 4 pts)
        score += min(4.0, len(notable) * 1.5)
        # Total raised bonus (up to 3 pts)
        if total_raised >= 50_000_000:
            score += 3.0
        elif total_raised >= 10_000_000:
            score += 2.0
        elif total_raised >= 1_000_000:
            score += 1.0
        # Multiple rounds signal (up to 3 pts)
        if num_rounds >= 4:
            score += 3.0
        elif num_rounds >= 2:
            score += 2.0
        elif num_rounds >= 1:
            score += 1.0
        return min(10.0, round(score, 1))


async def run_funding_agent(
    company_id: str,
    company_name: str,
    website: str = None,
    deck_funding_data: dict = None,
) -> dict:
    """Module-level entry point matching spec signature."""
    agent = FundingHistoryAgent()
    return await agent.analyze(company_id, company_name, website, deck_funding_data)

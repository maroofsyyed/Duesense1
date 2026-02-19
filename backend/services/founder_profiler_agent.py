"""
Founder Profiler Agent — Deep founder dossier generation.

Input: founder names from deck
Process: Proxycurl LinkedIn → education, work history, prior exits, board roles
Output: structured founder dossiers with credibility score (0-100)
Enhances existing agent_founder_quality() with real data.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import db as database
from services.llm_provider import llm
from services.linkedin_agent import LinkedInEnrichmentAgent

logger = logging.getLogger(__name__)


class FounderProfilerAgent:
    """Builds structured founder dossiers from LinkedIn data + LLM analysis."""

    def __init__(self):
        self.linkedin = LinkedInEnrichmentAgent()

    async def profile_founders(
        self,
        company_id: str,
        founders: list[dict],
        company_domain: Optional[str] = None,
    ) -> dict:
        """
        Build comprehensive dossiers for all founders.
        Returns structured profiles with credibility scores.
        """
        if not founders:
            return {"founders": [], "team_credibility_score": 0}

        dossiers = []
        tasks = []

        for founder in founders[:5]:  # Cap at 5 founders
            linkedin_url = founder.get("linkedin")
            if linkedin_url and linkedin_url != "not_mentioned" and "linkedin.com" in linkedin_url:
                tasks.append(self._build_dossier(company_id, founder, linkedin_url))
            else:
                # Try name-based lookup via domain
                tasks.append(self._build_dossier_from_name(
                    company_id, founder, company_domain
                ))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"[FounderProfiler] Dossier failed: {result}")
                continue
            if result:
                dossiers.append(result)

        # Calculate team credibility score
        team_score = self._calculate_team_score(dossiers)

        output = {
            "founders": dossiers,
            "team_credibility_score": team_score,
            "team_size": len(dossiers),
            "profiled_at": datetime.now(timezone.utc).isoformat(),
        }

        # Store in DB
        try:
            enrichment_tbl = database.enrichment_collection()
            enrichment_tbl.insert({
                "company_id": company_id,
                "source_type": "founder_profiles",
                "source_url": "enrichlayer",
                "data": output,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "is_valid": True,
            })
        except Exception as e:
            logger.error(f"[FounderProfiler] DB store failed: {e}")

        return output

    async def _build_dossier(self, company_id: str, founder: dict, linkedin_url: str) -> dict:
        """Build founder dossier from LinkedIn profile."""
        # Get LinkedIn data
        profile = await self.linkedin._enrich_person(company_id, linkedin_url)
        if "error" in profile:
            return self._basic_dossier(founder, profile)

        # LLM synthesis for credibility scoring
        credibility = await self._assess_credibility(founder, profile)

        return {
            "name": profile.get("full_name") or founder.get("name"),
            "role": founder.get("role", "Founder"),
            "linkedin_url": linkedin_url,
            "headline": profile.get("headline"),
            "location": f"{profile.get('city', '')}, {profile.get('country', '')}".strip(", "),
            "connections": profile.get("connections"),
            "current_company": profile.get("current_company"),
            "experience": {
                "total_years": profile.get("vc_signals", {}).get("total_experience_years", 0),
                "num_companies": profile.get("vc_signals", {}).get("num_companies", 0),
                "has_faang": profile.get("vc_signals", {}).get("has_faang", False),
                "has_prior_startup": profile.get("vc_signals", {}).get("has_prior_startup", False),
                "key_roles": [
                    {
                        "company": exp.get("company"),
                        "title": exp.get("title"),
                        "duration": exp.get("starts_at"),
                    }
                    for exp in (profile.get("experiences") or [])[:5]
                ],
            },
            "education": {
                "tier": profile.get("vc_signals", {}).get("education_tier", "unknown"),
                "degrees": [
                    {
                        "school": edu.get("school"),
                        "degree": edu.get("degree"),
                        "field": edu.get("field"),
                    }
                    for edu in (profile.get("education") or [])[:3]
                ],
            },
            "skills": (profile.get("skills") or [])[:10],
            "credibility_score": credibility.get("credibility_score", 50),
            "credibility_breakdown": credibility,
            "prior_exits": credibility.get("prior_exits", []),
            "board_roles": credibility.get("board_roles", []),
            "red_flags": credibility.get("red_flags", []),
            "green_flags": credibility.get("green_flags", []),
        }

    async def _build_dossier_from_name(
        self, company_id: str, founder: dict, company_domain: Optional[str]
    ) -> dict:
        """Build basic dossier when no LinkedIn URL available."""
        name = founder.get("name", "Unknown")

        # Try Enrichlayer person lookup if we have domain
        if company_domain:
            try:
                from integrations.clients import EnrichlyrClient
                enrichlyr = EnrichlyrClient()
                if enrichlyr.api_key:
                    result = await enrichlyr.resolve_person(
                        first_name=name.split()[0] if name else "",
                        company_domain=company_domain,
                    )
                    profile_url = result.get("url")
                    if profile_url and "error" not in result:
                        return await self._build_dossier(company_id, founder, profile_url)
            except Exception as e:
                logger.warning(f"[FounderProfiler] Lookup failed for {name}: {e}")

        return self._basic_dossier(founder, {})

    def _basic_dossier(self, founder: dict, extra: dict) -> dict:
        """Minimal dossier when LinkedIn data unavailable."""
        return {
            "name": founder.get("name", "Unknown"),
            "role": founder.get("role", "Founder"),
            "linkedin_url": founder.get("linkedin"),
            "headline": None,
            "location": None,
            "connections": None,
            "current_company": None,
            "experience": {
                "total_years": founder.get("years_in_industry"),
                "num_companies": len(founder.get("previous_companies", [])),
                "has_faang": False,
                "has_prior_startup": False,
                "key_roles": [
                    {"company": c, "title": None, "duration": None}
                    for c in founder.get("previous_companies", [])[:3]
                ],
            },
            "education": {"tier": "unknown", "degrees": []},
            "skills": [],
            "credibility_score": 30,  # Low confidence without LinkedIn data
            "credibility_breakdown": {"note": "Limited data — no LinkedIn profile found"},
            "prior_exits": [],
            "board_roles": [],
            "red_flags": ["No LinkedIn profile found"],
            "green_flags": [],
            "data_source": "deck_only",
        }

    async def _assess_credibility(self, founder: dict, linkedin_profile: dict) -> dict:
        """LLM-powered credibility assessment from LinkedIn data."""
        import json

        experiences = linkedin_profile.get("experiences", [])
        education = linkedin_profile.get("education", [])
        vc_signals = linkedin_profile.get("vc_signals", {})

        prompt = f"""You are a VC analyst assessing founder credibility.

FOUNDER: {founder.get('name', 'Unknown')} — {founder.get('role', 'Founder')}

LINKEDIN DATA:
- Headline: {linkedin_profile.get('headline', 'N/A')}
- Connections: {linkedin_profile.get('connections', 'N/A')}
- Total Experience Years: {vc_signals.get('total_experience_years', 'N/A')}
- Has FAANG: {vc_signals.get('has_faang', False)}
- Has Prior Startup: {vc_signals.get('has_prior_startup', False)}
- Education Tier: {vc_signals.get('education_tier', 'unknown')}

EXPERIENCE (last 5 roles):
{json.dumps(experiences[:5], default=str)[:2000]}

EDUCATION:
{json.dumps(education[:3], default=str)[:500]}

Score this founder's credibility (0-100) and identify:
1. Prior exits (companies they founded/co-founded that were acquired/IPO'd)
2. Board roles
3. Red flags (gaps, short tenures, inconsistencies)
4. Green flags (strong trajectory, domain expertise, repeat founder)

Respond with JSON:
{{
    "credibility_score": number (0-100),
    "domain_expertise_score": number (0-25),
    "leadership_score": number (0-25),
    "track_record_score": number (0-25),
    "network_score": number (0-25),
    "prior_exits": ["company names if any"],
    "board_roles": ["company names if any"],
    "red_flags": ["specific concerns"],
    "green_flags": ["specific strengths"],
    "summary": "2-3 sentence assessment"
}}"""

        return await llm.generate_json(
            prompt,
            "You are a VC founder credibility analyst. Assess strictly based on provided data. Never fabricate."
        )

    def _calculate_team_score(self, dossiers: list[dict]) -> int:
        """Calculate aggregate team credibility score."""
        if not dossiers:
            return 0
        scores = [d.get("credibility_score", 0) for d in dossiers]
        # Weighted: CEO/lead founder counts more
        if len(scores) == 1:
            return scores[0]
        # Lead founder = 60%, others split 40%
        lead = scores[0]
        others_avg = sum(scores[1:]) / len(scores[1:]) if len(scores) > 1 else 0
        return int(lead * 0.6 + others_avg * 0.4)

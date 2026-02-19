"""
LinkedIn Enrichment Agent — Enrichlyer API

Fetches founder LinkedIn profiles and company LinkedIn data.
Extracts:
  - Founder: current role, past companies, education, connections, skills
  - Company: employee count, follower growth, job postings, specialties

Uses Enrichlyer API (api.enrichlyer.com) — ENRICHLYER_API_KEY required.
"""
import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

import db as database
from integrations.clients import EnrichlyrClient

logger = logging.getLogger(__name__)


class LinkedInEnrichmentAgent:
    """Fetches and structures LinkedIn data via Enrichlyer API."""

    def __init__(self):
        self.client = EnrichlyrClient()
        self.api_key = self.client.api_key
        if not self.api_key:
            logger.warning("[LinkedIn] ENRICHLYER_API_KEY not set — LinkedIn enrichment disabled")

    # ─── Public Entry Point ───────────────────────────────────────────

    async def enrich(
        self,
        company_id: str,
        company_name: str,
        company_domain: Optional[str] = None,
        founder_linkedin_urls: Optional[list[str]] = None,
    ) -> dict:
        """
        Run full LinkedIn enrichment for a company and its founders.
        Returns combined dict; stores each piece in enrichment_sources.
        """
        if not self.api_key:
            return {"error": "ENRICHLYER_API_KEY not configured", "source": "linkedin"}

        tasks = {}

        # Company LinkedIn enrichment
        if company_domain:
            tasks["company_linkedin"] = self._enrich_company(
                company_id, company_name, company_domain
            )

        # Founder LinkedIn profiles
        if founder_linkedin_urls:
            for i, url in enumerate(founder_linkedin_urls[:5]):  # Cap at 5 founders
                if url and url != "not_mentioned" and "linkedin.com" in url:
                    tasks[f"founder_{i}"] = self._enrich_person(company_id, url)

        # If no LinkedIn URLs, try to resolve founders by name + domain
        if not founder_linkedin_urls and company_domain:
            tasks["founder_lookup"] = self._lookup_key_people(
                company_id, company_name, company_domain
            )

        if not tasks:
            return {"skipped": True, "reason": "No LinkedIn URLs or domain provided"}

        # Run all in parallel
        names = list(tasks.keys())
        coros = list(tasks.values())
        gathered = await asyncio.gather(*coros, return_exceptions=True)

        results = {}
        for name, result in zip(names, gathered):
            if isinstance(result, Exception):
                logger.error(f"[LinkedIn] {name} failed: {result}")
                results[name] = {"error": str(result)}
            else:
                results[name] = result

        return results

    # ─── Person Profile ───────────────────────────────────────────────

    async def _enrich_person(self, company_id: str, linkedin_url: str) -> dict:
        """Fetch a founder's LinkedIn profile via Enrichlyer Person Profile API."""
        logger.info(f"[LinkedIn] Fetching person profile: {linkedin_url}")

        raw = await self.client.get_person_profile(linkedin_url)

        if "error" in raw:
            logger.warning(f"[LinkedIn] Person API error: {raw['error']}")
            return {"error": f"Enrichlyer person API error: {raw.get('error')}"}

        # Structure the output — extract what matters for VC scoring
        profile = {
            "full_name": raw.get("full_name"),
            "headline": raw.get("headline"),
            "summary": raw.get("summary"),
            "city": raw.get("city"),
            "country": raw.get("country_full_name"),
            "linkedin_url": linkedin_url,
            "connections": raw.get("connections"),
            "follower_count": raw.get("follower_count"),
            "current_company": None,
            "experiences": [],
            "education": [],
            "skills": raw.get("skills", []),
            "certifications": [],
            "languages": [l.get("name") for l in raw.get("languages", []) if l.get("name")],
        }

        # Current role
        experiences = raw.get("experiences", [])
        for exp in experiences:
            entry = {
                "company": exp.get("company"),
                "title": exp.get("title"),
                "starts_at": _format_date(exp.get("starts_at")),
                "ends_at": _format_date(exp.get("ends_at")),
                "description": (exp.get("description") or "")[:500],
                "company_linkedin_url": exp.get("company_linkedin_profile_url"),
            }
            profile["experiences"].append(entry)
            if not exp.get("ends_at"):  # Current role
                profile["current_company"] = exp.get("company")

        # Education
        for edu in raw.get("education", []):
            profile["education"].append({
                "school": edu.get("school"),
                "degree": edu.get("degree_name"),
                "field": edu.get("field_of_study"),
                "starts_at": _format_date(edu.get("starts_at")),
                "ends_at": _format_date(edu.get("ends_at")),
            })

        # Certifications
        for cert in raw.get("certifications", []):
            profile["certifications"].append({
                "name": cert.get("name"),
                "authority": cert.get("authority"),
            })

        # VC-relevant signals
        profile["vc_signals"] = {
            "total_experience_years": _calc_experience_years(experiences),
            "num_companies": len(set(e.get("company") for e in experiences if e.get("company"))),
            "has_faang": _has_faang(experiences),
            "has_prior_startup": _has_startup_signal(experiences),
            "education_tier": _classify_education(raw.get("education", [])),
            "connection_strength": _classify_connections(raw.get("connections")),
        }

        # Store in DB
        _store_enrichment(company_id, "linkedin_founder", linkedin_url, profile)

        return profile

    # ─── Company Profile ──────────────────────────────────────────────

    async def _enrich_company(
        self, company_id: str, company_name: str, company_domain: str
    ) -> dict:
        """Fetch company LinkedIn data via Enrichlyer Company Profile API."""
        logger.info(f"[LinkedIn] Fetching company profile: {company_domain}")

        raw = await self.client.get_company_profile(company_domain)
        if "error" in raw:
            return {"error": f"Could not resolve LinkedIn page for {company_domain}: {raw.get('error')}"}

        profile = {
            "name": raw.get("name"),
            "linkedin_url": raw.get("linkedin_internal_id"),
            "description": raw.get("description"),
            "website": raw.get("website"),
            "industry": raw.get("industry"),
            "company_size": raw.get("company_size_on_linkedin"),
            "company_size_range": _parse_company_size(raw.get("company_size")),
            "follower_count": raw.get("follower_count"),
            "founded_year": raw.get("founded_year"),
            "hq_city": raw.get("hq", {}).get("city") if raw.get("hq") else None,
            "hq_country": raw.get("hq", {}).get("country") if raw.get("hq") else None,
            "specialities": raw.get("specialities", []),
            "tagline": raw.get("tagline"),
            "company_type": raw.get("company_type"),
            "funding_data": raw.get("funding_data"),
            "exit_data": raw.get("exit_data"),
            "extra": {
                "total_funding": raw.get("extra", {}).get("total_funding_amount")
                if raw.get("extra") else None,
                "latest_funding_round": raw.get("extra", {}).get("latest_funding_stage")
                if raw.get("extra") else None,
                "ipo_status": raw.get("extra", {}).get("ipo_status")
                if raw.get("extra") else None,
            },
        }

        # Employee count signals for VC
        profile["growth_signals"] = {
            "employee_count": raw.get("company_size_on_linkedin"),
            "follower_count": raw.get("follower_count"),
            "is_hiring": bool(raw.get("hiring_state")),
        }

        # Store in DB
        _store_enrichment(company_id, "linkedin_company", profile.get("linkedin_url", "enrichlyer"), profile)

        return profile

    # ─── Person Lookup (by name + domain) ─────────────────────────────

    async def _lookup_key_people(
        self, company_id: str, company_name: str, company_domain: str
    ) -> dict:
        """Try to find founder/CEO profiles by searching name + domain."""
        titles_to_find = ["CEO", "Founder", "CTO", "Co-Founder"]
        found_profiles = []

        for title in titles_to_find:
            try:
                data = await self.client.search_employees(
                    f"https://linkedin.com/company/{company_domain.replace('.', '-')}",
                    title,
                )
                if "error" not in data:
                    for emp in data.get("employees", []):
                        profile_url = emp.get("profile_url")
                        if profile_url and profile_url not in [p.get("linkedin_url") for p in found_profiles]:
                            profile = await self._enrich_person(company_id, profile_url)
                            if "error" not in profile:
                                found_profiles.append(profile)
                        if len(found_profiles) >= 3:
                            break
            except Exception as e:
                logger.warning(f"[LinkedIn] Key people lookup for '{title}' failed: {e}")

            if len(found_profiles) >= 3:
                break
            await asyncio.sleep(0.5)  # Rate limit courtesy

        return {"found_profiles": found_profiles, "total_found": len(found_profiles)}


# ─── Helper Functions ─────────────────────────────────────────────────


def _format_date(date_obj: Optional[dict]) -> Optional[str]:
    """Convert date dict {day, month, year} to ISO string."""
    if not date_obj or not isinstance(date_obj, dict):
        return None
    year = date_obj.get("year")
    month = date_obj.get("month", 1)
    day = date_obj.get("day", 1)
    if year:
        return f"{year}-{month:02d}-{day:02d}"
    return None


def _calc_experience_years(experiences: list) -> int:
    """Estimate total years of professional experience."""
    if not experiences:
        return 0
    earliest_year = None
    for exp in experiences:
        start = exp.get("starts_at")
        if start and isinstance(start, dict) and start.get("year"):
            yr = start["year"]
            if earliest_year is None or yr < earliest_year:
                earliest_year = yr
    if earliest_year:
        return datetime.now().year - earliest_year
    return 0


def _has_faang(experiences: list) -> bool:
    """Check if founder has FAANG/big-tech experience."""
    faang = {"google", "meta", "facebook", "amazon", "apple", "netflix", "microsoft",
             "alphabet", "uber", "stripe", "airbnb", "salesforce", "oracle", "tesla"}
    for exp in experiences:
        company = (exp.get("company") or "").lower()
        if any(f in company for f in faang):
            return True
    return False


def _has_startup_signal(experiences: list) -> bool:
    """Check if founder has prior startup experience."""
    startup_titles = {"founder", "co-founder", "cofounder", "ceo", "cto"}
    for exp in experiences:
        title = (exp.get("title") or "").lower()
        if any(t in title for t in startup_titles):
            if exp.get("ends_at"):  # A previous startup role (ended)
                return True
    return False


def _classify_education(education: list) -> str:
    """Classify education tier for VC scoring."""
    tier1 = {"stanford", "harvard", "mit", "princeton", "yale", "caltech", "columbia",
             "oxford", "cambridge", "berkeley", "carnegie mellon", "wharton", "iit"}
    for edu in education:
        school = (edu.get("school") or "").lower()
        if any(t in school for t in tier1):
            return "tier_1"
    if education:
        return "standard"
    return "unknown"


def _classify_connections(connections: Optional[int]) -> str:
    """Classify LinkedIn connection count."""
    if connections is None:
        return "unknown"
    if connections >= 500:
        return "strong"
    if connections >= 200:
        return "moderate"
    return "limited"


def _parse_company_size(size_range: Optional[list]) -> Optional[str]:
    """Parse company size range to human-readable string."""
    if not size_range or not isinstance(size_range, list) or len(size_range) < 2:
        return None
    return f"{size_range[0]}-{size_range[1]}"


def _store_enrichment(company_id: str, source_type: str, source_url: str, data: dict):
    """Store enrichment data in Supabase via centralized db module."""
    try:
        col = database.enrichment_collection()
        col.insert({
            "company_id": company_id,
            "source_type": source_type,
            "source_url": source_url,
            "data": data,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "is_valid": True,
        })
    except Exception as e:
        logger.error(f"[LinkedIn] Failed to store {source_type} enrichment: {e}")

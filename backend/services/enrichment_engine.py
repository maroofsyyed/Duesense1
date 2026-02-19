"""
Enrichment Engine - Gathers external data to enrich company analysis.

Uses centralized database connection from db module.
"""
import os
import asyncio
from datetime import datetime, timezone
import logging

# Use centralized database module
import db as database

from integrations.clients import GitHubClient, NewsClient, SerpClient, ScraperClient
from services.linkedin_agent import LinkedInEnrichmentAgent
from services.founder_profiler_agent import FounderProfilerAgent
from services.social_signals_agent import SocialSignalsAgent
from services.glassdoor_agent import GlassdoorAgent

logger = logging.getLogger(__name__)


def get_enrichment_col():
    """Get enrichment sources table (lazy)."""
    return database.enrichment_collection()


def get_competitors_col():
    """Get competitors table (lazy)."""
    return database.competitors_collection()


async def enrich_company(company_id: str, extracted_data: dict) -> dict:
    """Enrich company data from multiple sources in parallel."""
    company_info = extracted_data.get("company", {})
    company_name = company_info.get("name", "")
    website = company_info.get("website")
    industry = company_info.get("industry", "")
    product_desc = extracted_data.get("solution", {}).get("product_description", "")

    # Extract founder LinkedIn URLs from extracted data
    founders = extracted_data.get("founders", [])
    founder_linkedin_urls = [
        f.get("linkedin") for f in founders
        if f.get("linkedin") and f.get("linkedin") != "not_mentioned"
    ]

    # Extract company domain from website URL
    company_domain = None
    if website:
        from urllib.parse import urlparse
        parsed = urlparse(website if "://" in website else f"https://{website}")
        company_domain = parsed.netloc.replace("www.", "")

    tasks = {
        "github": _enrich_github(company_id, company_name),
        "news": _enrich_news(company_id, company_name),
        "competitors": _enrich_competitors(company_id, company_name, product_desc),
        "market": _enrich_market(company_id, industry),
        "linkedin": _enrich_linkedin(
            company_id, company_name, company_domain, founder_linkedin_urls
        ),
        "founder_profiles": _enrich_founder_profiles(
            company_id, founders, company_domain
        ),
        "social_signals": _enrich_social_signals(
            company_id, company_name, company_domain
        ),
        "glassdoor": _enrich_glassdoor(company_id, company_name),
        "company_profile": _enrich_company_profile(
            company_id, company_name, company_domain, extracted_data
        ),
    }

    if website:
        tasks["website"] = _enrich_website(company_id, website)
        tasks["website_intelligence"] = _enrich_website_deep(company_id, website)

    results = {}
    task_items = list(tasks.items())
    coros = [t[1] for t in task_items]
    names = [t[0] for t in task_items]

    gathered = await asyncio.gather(*coros, return_exceptions=True)

    for name, result in zip(names, gathered):
        if isinstance(result, Exception):
            results[name] = {"error": str(result), "source": name}
        else:
            results[name] = result

    return results


async def _enrich_linkedin(
    company_id: str,
    company_name: str,
    company_domain: str | None,
    founder_linkedin_urls: list[str],
) -> dict:
    """LinkedIn enrichment via Proxycurl — founder profiles + company data."""
    agent = LinkedInEnrichmentAgent()
    return await agent.enrich(
        company_id=company_id,
        company_name=company_name,
        company_domain=company_domain,
        founder_linkedin_urls=founder_linkedin_urls or None,
    )


async def _enrich_github(company_id: str, company_name: str) -> dict:
    gh = GitHubClient()
    org = await gh.find_organization(company_name)

    data = {"organization": org}
    if org.get("found") and org.get("login"):
        repos = await gh.analyze_repositories(org["login"])
        data["repositories"] = repos

    get_enrichment_col().insert({
        "company_id": company_id,
        "source_type": "github",
        "source_url": org.get("html_url", "https://github.com"),
        "data": data,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "is_valid": True,
    })
    return data


async def _enrich_news(company_id: str, company_name: str) -> dict:
    news = NewsClient()
    data = await news.search_company_news(company_name)

    get_enrichment_col().insert({
        "company_id": company_id,
        "source_type": "news",
        "source_url": "https://newsapi.org",
        "data": data,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "is_valid": True,
    })
    return data


async def _enrich_competitors(company_id: str, company_name: str, product_desc: str) -> dict:
    serp = SerpClient()
    data = await serp.find_competitors(company_name, product_desc)

    for comp in data.get("competitors", []):
        get_competitors_col().insert({
            "company_id": company_id,
            "name": comp.get("title", ""),
            "url": comp.get("url", ""),
            "description": comp.get("snippet", ""),
            "source_query": comp.get("source_query", ""),
            "discovered_at": datetime.now(timezone.utc).isoformat(),
        })

    get_enrichment_col().insert({
        "company_id": company_id,
        "source_type": "competitors",
        "source_url": "https://serpapi.com",
        "data": data,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "is_valid": True,
    })
    return data


async def _enrich_market(company_id: str, industry: str) -> dict:
    serp = SerpClient()
    data = await serp.search_market(industry)

    get_enrichment_col().insert({
        "company_id": company_id,
        "source_type": "market_research",
        "source_url": "https://serpapi.com",
        "data": data,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "is_valid": True,
    })
    return data


async def _enrich_website(company_id: str, website: str) -> dict:
    scraper = ScraperClient()
    data = await scraper.scrape_website(website)

    get_enrichment_col().insert({
        "company_id": company_id,
        "source_type": "website",
        "source_url": website,
        "data": data,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "is_valid": True,
    })
    return data


async def _enrich_website_deep(company_id: str, website: str) -> dict:
    """Deep website intelligence extraction - crawls 30+ pages and runs 7 AI agents."""
    from services.website_intelligence import WebsiteIntelligenceEngine

    engine = WebsiteIntelligenceEngine()

    # Step 1: Deep crawl all pages
    crawl_results = await engine.deep_crawl(website)

    # Step 2: Detect tech stack (no LLM needed)
    tech_stack = engine.detect_tech_stack(crawl_results)

    # Step 3: Extract sales signals (no LLM needed)
    sales_signals = engine.extract_sales_signals(crawl_results)

    # Step 4: Run all 7 AI agents in parallel
    agent_results = await asyncio.gather(
        engine.extract_product_intelligence(crawl_results),
        engine.analyze_revenue_model(crawl_results),
        engine.extract_customer_validation(crawl_results),
        engine.extract_team_intelligence(crawl_results),
        engine.analyze_technical_depth(crawl_results),
        engine.extract_traction_signals(crawl_results),
        engine.extract_compliance_signals(crawl_results),
        return_exceptions=True,
    )

    product_intel = agent_results[0] if not isinstance(agent_results[0], Exception) else {"error": str(agent_results[0])}
    revenue_model = agent_results[1] if not isinstance(agent_results[1], Exception) else {"error": str(agent_results[1])}
    customer_validation = agent_results[2] if not isinstance(agent_results[2], Exception) else {"error": str(agent_results[2])}
    team_intel = agent_results[3] if not isinstance(agent_results[3], Exception) else {"error": str(agent_results[3])}
    technical_depth = agent_results[4] if not isinstance(agent_results[4], Exception) else {"error": str(agent_results[4])}
    traction_signals = agent_results[5] if not isinstance(agent_results[5], Exception) else {"error": str(agent_results[5])}
    compliance = agent_results[6] if not isinstance(agent_results[6], Exception) else {"error": str(agent_results[6])}

    # Step 5: AI synthesis
    intelligence_summary = await engine.generate_intelligence_summary({
        "crawl_results": crawl_results,
        "tech_stack": tech_stack,
        "sales_signals": sales_signals,
        "product_intel": product_intel,
        "revenue_model": revenue_model,
        "customer_validation": customer_validation,
        "team_intel": team_intel,
        "technical_depth": technical_depth,
        "traction_signals": traction_signals,
        "compliance": compliance,
    })

    full_data = {
        "intelligence_summary": intelligence_summary,
        "crawl_meta": {
            "pages_crawled": crawl_results.get("pages_crawled", 0),
            "pages_attempted": crawl_results.get("pages_attempted", 0),
            "base_url": crawl_results.get("base_url"),
        },
        "product_intel": product_intel,
        "revenue_model": revenue_model,
        "customer_validation": customer_validation,
        "team_intel": team_intel,
        "technical_depth": technical_depth,
        "traction_signals": traction_signals,
        "compliance": compliance,
        "tech_stack": tech_stack,
        "sales_signals": sales_signals,
        "crawl_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    get_enrichment_col().insert({
        "company_id": company_id,
        "source_type": "website_intelligence",
        "source_url": website,
        "data": full_data,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "is_valid": True,
    })

    return full_data


async def _enrich_founder_profiles(
    company_id: str, founders: list, company_domain: str | None
) -> dict:
    """Deep founder profiling via Proxycurl + LLM credibility scoring."""
    agent = FounderProfilerAgent()
    return await agent.profile_founders(company_id, founders, company_domain)


async def _enrich_social_signals(
    company_id: str, company_name: str, company_domain: str | None
) -> dict:
    """Aggregate social signals from GitHub, Twitter, LinkedIn, YouTube."""
    agent = SocialSignalsAgent()
    return await agent.gather_signals(company_id, company_name, company_domain)


async def _enrich_glassdoor(company_id: str, company_name: str) -> dict:
    """Scrape Glassdoor for team health signals."""
    agent = GlassdoorAgent()
    return await agent.analyze(company_id, company_name)


async def _enrich_company_profile(
    company_id: str,
    company_name: str,
    company_domain: str | None,
    extracted_data: dict,
) -> dict:
    """Build verified company profile from Crunchbase + LinkedIn + website + deck."""
    from services.llm_provider import llm
    import json

    # Gather raw data from multiple sources
    company_info = extracted_data.get("company", {})
    funding_info = extracted_data.get("funding", {})

    # Enrichlayer company data (if available)
    linkedin_data = {}
    try:
        from integrations.clients import EnrichlyrClient
        enrichlyr = EnrichlyrClient()
        if enrichlyr.api_key and company_domain:
            enrichlyr_result = await enrichlyr.get_company_profile(company_domain)
            if "error" not in enrichlyr_result:
                linkedin_data = enrichlyr_result
    except Exception as e:
        logger.warning(f"[CompanyProfile] Enrichlayer lookup failed: {e}")

    # LLM synthesis to build verified profile
    prompt = f"""You are a VC analyst building a verified company profile.

DECK DATA:
{json.dumps(company_info, default=str)[:1500]}

FUNDING DATA:
{json.dumps(funding_info, default=str)[:500]}

LINKEDIN COMPANY DATA:
{json.dumps(linkedin_data, default=str)[:1500]}

Build a verified company profile. Cross-reference sources.

Respond with JSON:
{{
    "verified_name": "string",
    "founded_date": "string or not_mentioned",
    "hq_location": "string or not_mentioned",
    "headcount": number or null,
    "headcount_source": "linkedin / deck / inferred",
    "business_model": "B2B_SAAS / B2C / MARKETPLACE / PLATFORM / HARDWARE / OTHER",
    "industry_classification": "string",
    "sub_industry": "string",
    "funding_stage": "string or not_mentioned",
    "total_raised": "string or not_mentioned",
    "key_investors": ["string"],
    "linkedin_url": "string or not_mentioned",
    "linkedin_followers": number or null,
    "is_hiring": true/false,
    "specialities": ["string"],
    "data_confidence": "HIGH / MEDIUM / LOW",
    "cross_reference_notes": "string - discrepancies between sources"
}}"""

    result = await llm.generate_json(
        prompt,
        "You are a VC company profiler. Cross-reference all sources. Flag discrepancies."
    )

    # Store
    get_enrichment_col().insert({
        "company_id": company_id,
        "source_type": "company_profile",
        "source_url": "multi-source",
        "data": result,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "is_valid": True,
    })

    return result

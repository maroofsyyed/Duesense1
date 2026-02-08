import asyncio
from datetime import datetime, timezone
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import os

load_dotenv()

client = MongoClient(os.environ.get("MONGO_URL"))
db = client[os.environ.get("DB_NAME")]
enrichment_col = db["enrichment_sources"]
competitors_col = db["competitors"]

from integrations.clients import GitHubClient, NewsClient, SerpClient, ScraperClient


async def enrich_company(company_id: str, extracted_data: dict) -> dict:
    """Enrich company data from multiple sources in parallel."""
    company_info = extracted_data.get("company", {})
    company_name = company_info.get("name", "")
    website = company_info.get("website")
    industry = company_info.get("industry", "")
    product_desc = extracted_data.get("solution", {}).get("product_description", "")

    tasks = {
        "github": _enrich_github(company_id, company_name),
        "news": _enrich_news(company_id, company_name),
        "competitors": _enrich_competitors(company_id, company_name, product_desc),
        "market": _enrich_market(company_id, industry),
    }

    if website:
        tasks["website"] = _enrich_website(company_id, website)

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


async def _enrich_github(company_id: str, company_name: str) -> dict:
    gh = GitHubClient()
    org = await gh.find_organization(company_name)

    data = {"organization": org}
    if org.get("found") and org.get("login"):
        repos = await gh.analyze_repositories(org["login"])
        data["repositories"] = repos

    enrichment_col.insert_one({
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

    enrichment_col.insert_one({
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

    # Store each competitor
    for comp in data.get("competitors", []):
        competitors_col.insert_one({
            "company_id": company_id,
            "name": comp.get("title", ""),
            "url": comp.get("url", ""),
            "description": comp.get("snippet", ""),
            "source_query": comp.get("source_query", ""),
            "discovered_at": datetime.now(timezone.utc).isoformat(),
        })

    enrichment_col.insert_one({
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

    enrichment_col.insert_one({
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

    enrichment_col.insert_one({
        "company_id": company_id,
        "source_type": "website",
        "source_url": website,
        "data": data,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "is_valid": True,
    })
    return data

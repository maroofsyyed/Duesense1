"""Website Due Diligence Pipeline - runs at upload time, focused on citation-heavy extraction."""
import asyncio
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

client = MongoClient(os.environ.get("MONGO_URL"))
db = client[os.environ.get("DB_NAME")]
enrichment_col = db["enrichment_sources"]

from integrations.clients import ScraperClient
from services.llm_provider import llm

CORE_PAGES = [
    "/", "/about", "/about-us", "/team", "/our-team",
    "/product", "/products", "/features", "/solutions",
    "/pricing", "/plans", "/enterprise",
    "/customers", "/case-studies", "/testimonials",
    "/blog", "/news", "/press", "/careers", "/jobs",
    "/docs", "/api", "/security", "/privacy", "/compliance",
]


async def run_website_due_diligence(company_id: str, website_url: str) -> dict:
    """
    Full website due diligence pipeline.
    Crawls core pages, extracts structured intelligence with citations,
    and stores everything as a `website_due_diligence` enrichment record.
    Gracefully handles failures — never fails the upload.
    """
    website_url = website_url.rstrip("/")
    if not website_url.startswith("http"):
        website_url = "https://" + website_url

    scraper = ScraperClient()

    # Step 1: Crawl all core pages (batched, max 3 concurrent)
    crawl_results = {}
    citations = []

    for batch in _chunks(CORE_PAGES, 3):
        tasks = []
        for path in batch:
            tasks.append(_safe_scrape(scraper, website_url, path))
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for path, result in zip(batch, results):
            if isinstance(result, Exception):
                continue
            if result and not result.get("error"):
                crawl_results[path] = result
                citations.append({
                    "page": path,
                    "url": f"{website_url}{path}",
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                })

    if not crawl_results:
        # Website unreachable — store incomplete record, don't fail
        incomplete = {
            "status": "incomplete",
            "reason": "Website unreachable or blocked",
            "website_url": website_url,
        }
        enrichment_col.insert_one({
            "company_id": company_id,
            "source_type": "website_due_diligence",
            "source_url": website_url,
            "data": incomplete,
            "citations": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "is_valid": False,
        })
        return incomplete

    # Step 2: Run LLM extraction with zero-hallucination rules
    extraction = await _extract_intelligence(website_url, crawl_results, citations)

    # Step 3: Store
    full_data = {
        "status": "completed",
        "website_url": website_url,
        "pages_crawled": len(crawl_results),
        "pages_attempted": len(CORE_PAGES),
        "extraction": extraction,
        "crawl_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    enrichment_col.insert_one({
        "company_id": company_id,
        "source_type": "website_due_diligence",
        "source_url": website_url,
        "data": full_data,
        "citations": citations,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "is_valid": True,
    })

    return full_data


async def _safe_scrape(scraper, base_url: str, path: str) -> dict:
    try:
        from urllib.parse import urljoin
        url = urljoin(base_url, path)
        return await scraper.scrape_website(url)
    except Exception:
        return {"error": f"Failed to scrape {path}"}


async def _extract_intelligence(website_url: str, crawl_results: dict, citations: list) -> dict:
    """LLM-guided extraction with mandatory citations."""

    # Build page summaries for the prompt
    page_summaries = []
    for path, data in crawl_results.items():
        title = data.get("title", "")
        text = data.get("text_content", "")[:1500]
        headings = data.get("headings", {})
        h1s = ", ".join(headings.get("h1", [])[:3]) if isinstance(headings, dict) else ""
        h2s = ", ".join(headings.get("h2", [])[:5]) if isinstance(headings, dict) else ""
        page_summaries.append(
            f"--- PAGE: {path} ({website_url}{path}) ---\n"
            f"Title: {title}\nH1: {h1s}\nH2: {h2s}\nContent: {text}"
        )

    combined = "\n\n".join(page_summaries)[:8000]
    pages_found = list(crawl_results.keys())

    prompt = f"""You are a VC analyst performing website-based due diligence on a company.

CRITICAL ZERO-HALLUCINATION RULES:
1. ONLY extract information EXPLICITLY stated on the pages below
2. For ANY field where data is NOT explicitly present, use "not_mentioned"
3. Every piece of data MUST include a [SOURCE: /page_path] citation
4. NEVER infer, guess, or hallucinate any information

WEBSITE: {website_url}
PAGES FOUND: {pages_found}

PAGE CONTENT:
{combined}

Extract the following structured JSON:
{{
  "product_intelligence": {{
    "product_description": "string with [SOURCE: /path] or not_mentioned",
    "key_features": ["feature [SOURCE: /path]"],
    "use_cases": ["use case [SOURCE: /path]"],
    "differentiation_claims": ["claim [SOURCE: /path]"],
    "api_available": "true/false/not_mentioned [SOURCE: /path]"
  }},
  "business_model": {{
    "pricing_model": "subscription | usage | enterprise | freemium | unknown [SOURCE: /path]",
    "price_points": ["tier: $X/mo [SOURCE: /pricing]"],
    "free_trial": "true/false/not_mentioned [SOURCE: /path]"
  }},
  "customer_validation": {{
    "customer_logos_count": "number or not_mentioned [SOURCE: /path]",
    "case_study_count": "number or not_mentioned [SOURCE: /path]",
    "industries_served": ["industry [SOURCE: /path]"],
    "notable_customers": ["name [SOURCE: /path]"],
    "quantified_results": ["result [SOURCE: /path]"]
  }},
  "team_signals": {{
    "team_size_estimate": "number or not_mentioned [SOURCE: /path]",
    "open_roles_count": "number or not_mentioned [SOURCE: /path]",
    "engineering_roles_ratio": "high | medium | low | not_mentioned [SOURCE: /path]",
    "leadership_mentioned": ["name - role [SOURCE: /path]"],
    "notable_backgrounds": ["background [SOURCE: /path]"]
  }},
  "technical_signals": {{
    "tech_stack_mentions": ["tech [SOURCE: /path]"],
    "security_certifications": ["cert [SOURCE: /path]"],
    "docs_quality": "high | medium | low | none [SOURCE: /path]",
    "api_type": "REST | GraphQL | SDK | not_mentioned [SOURCE: /path]"
  }},
  "traction_signals": {{
    "blog_activity": "active | stale | none [SOURCE: /path]",
    "recent_announcements": ["announcement [SOURCE: /path]"],
    "user_volume_claims": "string or not_mentioned [SOURCE: /path]",
    "growth_metrics": ["metric [SOURCE: /path]"]
  }},
  "sales_motion": {{
    "primary_cta": "string [SOURCE: /path]",
    "demo_available": "true/false [SOURCE: /path]",
    "self_serve_signup": "true/false [SOURCE: /path]",
    "motion_type": "Product-Led | Sales-Led | Hybrid [SOURCE: /path]"
  }},
  "compliance": {{
    "certifications": ["cert [SOURCE: /path]"],
    "privacy_policy": "exists/not_found",
    "terms_of_service": "exists/not_found"
  }},
  "red_flags": ["flag with [SOURCE: /path]"],
  "green_flags": ["flag with [SOURCE: /path]"],
  "overall_assessment": "1-2 sentence summary of website maturity"
}}"""

    system = (
        "You are a VC due diligence analyst. Extract ONLY explicitly stated facts from website pages. "
        "Every single data point MUST have a [SOURCE: /page_path] citation. "
        "Use 'not_mentioned' for anything not explicitly found. NEVER guess."
    )

    try:
        return await llm.generate_json(prompt, system)
    except Exception as e:
        return {"error": str(e), "status": "extraction_failed"}


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

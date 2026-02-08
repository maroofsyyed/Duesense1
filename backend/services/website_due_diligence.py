"""Website Due Diligence Pipeline - runs at upload time, focused on citation-heavy extraction."""
import asyncio
from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv
import os
import certifi

load_dotenv()

# MongoDB client with proper SSL/TLS configuration
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

if not MONGO_URL or not DB_NAME:
    raise ValueError("MONGO_URL and DB_NAME environment variables are required")

client = MongoClient(
    MONGO_URL,
    tls=True,
    tlsAllowInvalidCertificates=False,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=10000,
    connectTimeoutMS=10000,
    socketTimeoutMS=10000,
    maxPoolSize=50,
    minPoolSize=10,
    retryWrites=True,
    retryReads=True
)
db = client[DB_NAME]
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
    """LLM-guided extraction with mandatory citations - structured for VC due diligence."""

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

Extract the following structured JSON (EXACT FORMAT REQUIRED):
{{
  "product_signals": {{
    "product_description": "string with [SOURCE: /path] or not_mentioned",
    "key_features": ["feature [SOURCE: /path]"],
    "api_available": "true | false | not_mentioned",
    "integrations": ["integration name [SOURCE: /path]"],
    "platform_mentions": ["platform [SOURCE: /path]"]
  }},
  "business_model_signals": {{
    "pricing_model": "subscription | usage | enterprise | not_mentioned",
    "price_points": ["tier: $X/mo [SOURCE: /pricing]"],
    "free_trial": "true | false | not_mentioned",
    "sales_motion": "self_serve | sales_led | not_mentioned"
  }},
  "customer_validation_signals": {{
    "customer_logos_count": "number or not_mentioned",
    "case_study_count": "number or not_mentioned",
    "named_customers": ["customer name [SOURCE: /path]"],
    "quantified_outcomes": ["outcome [SOURCE: /path]"]
  }},
  "traction_signals": {{
    "blog_last_post_date": "YYYY-MM-DD or not_mentioned",
    "press_mentions_count": "number or not_mentioned",
    "announcements": ["announcement [SOURCE: /path]"]
  }},
  "team_hiring_signals": {{
    "team_page_exists": true | false,
    "open_roles_count": "number or not_mentioned",
    "engineering_roles_present": "true | false | not_mentioned"
  }},
  "trust_compliance_signals": {{
    "security_page_exists": true | false,
    "certifications": ["cert [SOURCE: /path]"],
    "privacy_policy_exists": true | false
  }},
  "red_flags": ["flag with [SOURCE: /path]"],
  "green_flags": ["flag with [SOURCE: /path]"]
}}

IMPORTANT RULES:
- For boolean fields, use true/false/not_mentioned (no quotes for booleans)
- For count fields, use number or "not_mentioned" string
- Every list item must include [SOURCE: /page_path]
- If a page doesn't exist, mark existence as false
- If pricing page exists but no pricing shown, mark pricing_model as "not_mentioned"
"""

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

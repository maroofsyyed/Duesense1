"""Deep Website Intelligence Engine - Extracts 50-100+ business signals from company websites."""
import asyncio
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
import os

load_dotenv()

from integrations.clients import ScraperClient
from services.llm_provider import llm

CRAWL_MAP = {
    "/": "homepage_analysis",
    "/about": "company_story",
    "/about-us": "company_story",
    "/team": "team_composition",
    "/our-team": "team_composition",
    "/product": "product_details",
    "/products": "product_catalog",
    "/features": "feature_analysis",
    "/solutions": "solution_offerings",
    "/platform": "platform_architecture",
    "/technology": "tech_stack_hints",
    "/api": "api_documentation",
    "/docs": "technical_documentation",
    "/integrations": "ecosystem_partnerships",
    "/pricing": "revenue_model",
    "/plans": "revenue_model",
    "/enterprise": "enterprise_focus",
    "/contact-sales": "sales_motion",
    "/customers": "customer_logos",
    "/case-studies": "success_stories",
    "/testimonials": "social_proof",
    "/blog": "content_frequency",
    "/news": "press_mentions",
    "/press": "media_coverage",
    "/newsroom": "announcement_velocity",
    "/careers": "hiring_velocity",
    "/jobs": "open_positions",
    "/culture": "team_values",
    "/leadership": "executive_team",
    "/security": "compliance_standards",
    "/privacy": "data_practices",
    "/compliance": "certifications",
    "/community": "user_engagement",
    "/partners": "partnership_network",
    "/investors": "funding_history",
}

# Tech stack detection patterns
TECH_PATTERNS = {
    "frontend": {
        "React": [r"react", r"__next", r"_next/static", r"reactDOM"],
        "Vue": [r"vue\.js", r"vuejs", r"__vue"],
        "Angular": [r"angular", r"ng-version"],
        "Next.js": [r"__next", r"_next/", r"next\.js"],
        "Gatsby": [r"gatsby", r"___gatsby"],
        "Svelte": [r"svelte"],
        "Tailwind": [r"tailwind"],
        "Bootstrap": [r"bootstrap"],
    },
    "infrastructure": {
        "Cloudflare": [r"cloudflare", r"cf-ray"],
        "AWS": [r"amazonaws", r"aws", r"cloudfront"],
        "Vercel": [r"vercel", r"\.vercel\.app"],
        "Netlify": [r"netlify"],
        "Heroku": [r"heroku"],
        "GCP": [r"googleapis", r"google-cloud"],
    },
    "analytics": {
        "Google Analytics": [r"google-analytics", r"gtag", r"ga\(", r"googletagmanager"],
        "Mixpanel": [r"mixpanel"],
        "Amplitude": [r"amplitude"],
        "Segment": [r"segment\.com", r"analytics\.js"],
        "Hotjar": [r"hotjar"],
        "PostHog": [r"posthog"],
    },
    "marketing": {
        "HubSpot": [r"hubspot", r"hs-scripts"],
        "Intercom": [r"intercom", r"intercomSettings"],
        "Drift": [r"drift"],
        "Zendesk": [r"zendesk", r"zdassets"],
        "Crisp": [r"crisp\.chat"],
    },
    "payments": {
        "Stripe": [r"stripe\.com", r"stripe\.js"],
        "PayPal": [r"paypal"],
        "Braintree": [r"braintree"],
    },
}


class WebsiteIntelligenceEngine:
    def __init__(self):
        self.scraper = ScraperClient()

    async def deep_crawl(self, base_url: str) -> dict:
        """Crawl all pages from the CRAWL_MAP, returning page data by category."""
        if not base_url:
            return {"error": "No website URL provided"}

        base_url = base_url.rstrip("/")
        if not base_url.startswith("http"):
            base_url = "https://" + base_url

        # Batch crawl: prioritize high-value pages, limit concurrency
        high_priority = ["/", "/about", "/about-us", "/product", "/features", "/pricing",
                         "/customers", "/team", "/careers", "/blog", "/security"]
        medium_priority = [p for p in CRAWL_MAP if p not in high_priority]

        crawl_results = {}

        # Crawl high-priority pages (parallel, max 3 at a time)
        for batch in _chunks(high_priority, 3):
            tasks = [self._safe_scrape(base_url, path) for path in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for path, result in zip(batch, results):
                if isinstance(result, Exception):
                    continue
                if result and not result.get("error"):
                    crawl_results[path] = {
                        "category": CRAWL_MAP.get(path, "unknown"),
                        "data": result,
                    }

        # Crawl medium-priority pages
        for batch in _chunks(medium_priority, 3):
            tasks = [self._safe_scrape(base_url, path) for path in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for path, result in zip(batch, results):
                if isinstance(result, Exception):
                    continue
                if result and not result.get("error"):
                    crawl_results[path] = {
                        "category": CRAWL_MAP.get(path, "unknown"),
                        "data": result,
                    }

        return {
            "base_url": base_url,
            "pages_crawled": len(crawl_results),
            "pages_attempted": len(CRAWL_MAP),
            "results": crawl_results,
        }

    async def _safe_scrape(self, base_url: str, path: str) -> dict:
        try:
            url = urljoin(base_url, path)
            return await self.scraper.scrape_website(url)
        except Exception:
            return {"error": f"Failed to scrape {path}"}

    def detect_tech_stack(self, crawl_results: dict) -> dict:
        """Detect technology stack from HTML content patterns."""
        detected = {"frontend": [], "infrastructure": [], "analytics": [], "marketing": [], "payments": []}

        all_text = ""
        for path_data in crawl_results.get("results", {}).values():
            content = path_data.get("data", {}).get("text_content", "")
            all_text += content + " "

        for category, tools in TECH_PATTERNS.items():
            for tool_name, patterns in tools.items():
                for pattern in patterns:
                    if re.search(pattern, all_text, re.IGNORECASE):
                        if tool_name not in detected.get(category, []):
                            detected[category].append(tool_name)
                        break

        return detected

    async def extract_product_intelligence(self, crawl_results: dict) -> dict:
        """Agent 1: Product Intelligence Extractor."""
        pages = _get_pages_by_category(crawl_results, ["homepage_analysis", "product_details", "product_catalog",
                                                         "feature_analysis", "solution_offerings", "platform_architecture"])
        if not pages:
            return {"extracted": False, "reason": "No product pages found"}

        prompt = f"""Analyze these product-related website pages and extract structured intelligence.

PAGE CONTENT:
{_truncate_pages(pages, 4000)}

Return JSON:
{{
  "product_positioning": "string - one-line positioning",
  "value_propositions": ["string - each core value prop"],
  "key_features": ["string - each feature mentioned"],
  "target_personas": ["string - each target customer type"],
  "use_cases": ["string"],
  "differentiation_claims": ["string - how they say they're different"],
  "technology_mentions": ["string - AI/ML, blockchain, etc."],
  "integration_count": "number or null",
  "has_api": true/false,
  "has_interactive_demo": true/false,
  "product_maturity_score": "number 0-10 with reasoning"
}}"""
        return await llm.generate_json(prompt, "Extract product intelligence from website data. Only report what is explicitly stated.")

    async def analyze_revenue_model(self, crawl_results: dict) -> dict:
        """Agent 2: Revenue Model Analyzer."""
        pages = _get_pages_by_category(crawl_results, ["revenue_model", "enterprise_focus", "sales_motion", "homepage_analysis"])
        if not pages:
            return {"extracted": False, "reason": "No pricing pages found"}

        prompt = f"""Analyze pricing/revenue pages to extract business model intelligence.

PAGE CONTENT:
{_truncate_pages(pages, 3000)}

Return JSON:
{{
  "pricing_model": "SaaS | Usage-based | Freemium | Enterprise | Marketplace | null",
  "price_points": ["string - each tier/price mentioned"],
  "plan_tiers": ["string - tier names like Free, Pro, Enterprise"],
  "target_segments": ["SMB | Mid-Market | Enterprise"],
  "free_trial": true/false,
  "pricing_transparency": "HIGH | MEDIUM | LOW",
  "payment_frequency": "monthly | annual | both | null",
  "acv_estimate": "string or null",
  "sales_motion": "Product-Led | Sales-Led | Hybrid",
  "contact_sales_cta": true/false,
  "revenue_model_score": "number 0-10"
}}"""
        return await llm.generate_json(prompt, "Extract revenue model intelligence. Only report explicitly stated pricing info.")

    async def extract_customer_validation(self, crawl_results: dict) -> dict:
        """Agent 3: Customer Validation Extractor."""
        pages = _get_pages_by_category(crawl_results, ["customer_logos", "success_stories", "social_proof", "homepage_analysis"])
        if not pages:
            return {"extracted": False, "reason": "No customer pages found"}

        prompt = f"""Analyze customer-related pages to extract validation signals.

PAGE CONTENT:
{_truncate_pages(pages, 3000)}

Return JSON:
{{
  "customer_logo_count": "number or null",
  "fortune_500_customers": ["string - names if identifiable"],
  "case_study_count": "number or null",
  "customer_segments": ["SMB | Mid-Market | Enterprise"],
  "industry_verticals": ["string"],
  "quantified_results": ["string - ROI, time savings, etc."],
  "customer_quotes_sentiment": "positive | mixed | negative | none",
  "notable_customers": ["string"],
  "customer_validation_score": "number 0-10"
}}"""
        return await llm.generate_json(prompt, "Extract customer validation signals. Only report what is explicitly mentioned.")

    async def extract_team_intelligence(self, crawl_results: dict) -> dict:
        """Agent 4: Team & Hiring Intelligence."""
        pages = _get_pages_by_category(crawl_results, ["team_composition", "company_story", "hiring_velocity",
                                                         "open_positions", "executive_team", "team_values"])
        if not pages:
            return {"extracted": False, "reason": "No team pages found"}

        prompt = f"""Analyze team/careers pages to extract team intelligence.

PAGE CONTENT:
{_truncate_pages(pages, 3000)}

Return JSON:
{{
  "team_size_estimate": "number or null",
  "leadership_team": [{{ "name": "string", "role": "string", "notable_background": "string or null" }}],
  "notable_alumni": ["string - FAANG, unicorn backgrounds"],
  "advisors": ["string"],
  "open_positions_count": "number or null",
  "engineering_roles_count": "number or null",
  "senior_roles_ratio": "HIGH | MEDIUM | LOW | null",
  "remote_friendly": true/false/null,
  "office_locations": ["string"],
  "hiring_velocity": "HIGH | MEDIUM | LOW | null",
  "team_quality_score": "number 0-10"
}}"""
        return await llm.generate_json(prompt, "Extract team and hiring intelligence. Only report explicit information.")

    async def analyze_technical_depth(self, crawl_results: dict) -> dict:
        """Agent 5: Technical Depth Analyzer."""
        pages = _get_pages_by_category(crawl_results, ["api_documentation", "technical_documentation", "tech_stack_hints",
                                                         "content_frequency", "compliance_standards"])
        if not pages:
            return {"extracted": False, "reason": "No technical pages found"}

        prompt = f"""Analyze technical pages to assess engineering depth and credibility.

PAGE CONTENT:
{_truncate_pages(pages, 3000)}

Return JSON:
{{
  "api_available": true/false,
  "api_type": "REST | GraphQL | SDK | null",
  "documentation_quality": "Comprehensive | Basic | None",
  "tech_blog_active": true/false,
  "tech_blog_frequency": "string or null",
  "open_source_mentions": true/false,
  "security_certifications": ["SOC 2 | ISO 27001 | HIPAA | GDPR | PCI-DSS"],
  "infrastructure_signals": ["string - cloud, scalability mentions"],
  "technical_credibility_score": "number 0-10"
}}"""
        return await llm.generate_json(prompt, "Extract technical depth signals. Only report what is explicitly stated.")

    async def extract_traction_signals(self, crawl_results: dict) -> dict:
        """Agent 6: Traction & Growth Signals."""
        pages = _get_pages_by_category(crawl_results, ["content_frequency", "press_mentions", "media_coverage",
                                                         "announcement_velocity", "homepage_analysis"])
        if not pages:
            return {"extracted": False, "reason": "No traction pages found"}

        prompt = f"""Analyze blog/news/press pages to extract traction and growth signals.

PAGE CONTENT:
{_truncate_pages(pages, 3000)}

Return JSON:
{{
  "blog_post_frequency": "string - posts per month estimate or null",
  "latest_content_date": "string or null",
  "content_freshness": "ACTIVE | STALE | DEAD | null",
  "press_mentions": ["string - publication names"],
  "recent_announcements": ["string - funding, partnerships, launches"],
  "user_volume_claims": "string or null",
  "growth_metrics_mentioned": ["string"],
  "version_numbers": "string or null",
  "traction_signals_score": "number 0-10"
}}"""
        return await llm.generate_json(prompt, "Extract traction signals. Only report explicitly stated metrics.")

    async def extract_compliance_signals(self, crawl_results: dict) -> dict:
        """Agent 7: Compliance & Trust Signals."""
        pages = _get_pages_by_category(crawl_results, ["compliance_standards", "data_practices", "certifications"])
        if not pages:
            return {"extracted": False, "reason": "No compliance pages found"}

        prompt = f"""Analyze security/compliance pages to extract trust signals.

PAGE CONTENT:
{_truncate_pages(pages, 2000)}

Return JSON:
{{
  "security_certifications": ["string"],
  "compliance_standards": ["HIPAA | GDPR | CCPA | PCI-DSS | SOX"],
  "data_residency_options": true/false,
  "uptime_sla": "string or null",
  "bug_bounty": true/false,
  "privacy_policy_quality": "Comprehensive | Basic | Missing",
  "trust_score": "number 0-10"
}}"""
        return await llm.generate_json(prompt, "Extract compliance and trust signals only from provided data.")

    def extract_sales_signals(self, crawl_results: dict) -> dict:
        """Extract sales motion signals from crawled pages (no LLM needed)."""
        all_text = ""
        for path_data in crawl_results.get("results", {}).values():
            content = path_data.get("data", {}).get("text_content", "")
            all_text += content.lower() + " "

        return {
            "has_contact_form": "contact" in all_text and ("form" in all_text or "reach" in all_text),
            "has_demo_cta": any(s in all_text for s in ["request demo", "book demo", "schedule demo", "get a demo"]),
            "has_talk_to_sales": any(s in all_text for s in ["talk to sales", "contact sales", "sales team"]),
            "has_free_trial": any(s in all_text for s in ["free trial", "start free", "try free", "get started free"]),
            "has_phone_number": bool(re.search(r'\+?\d[\d\-\(\)\s]{8,}\d', all_text)),
            "has_live_chat": any(s in all_text for s in ["intercom", "drift", "zendesk", "crisp", "live chat", "chat with us"]),
            "has_calendly": "calendly" in all_text,
            "has_newsletter": any(s in all_text for s in ["newsletter", "subscribe", "email updates"]),
            "sales_motion": _detect_sales_motion(all_text),
        }

    async def generate_intelligence_summary(self, all_data: dict) -> dict:
        """AI synthesis: generate comprehensive website intelligence report."""
        import json

        prompt = f"""You are analyzing a company's website to generate VC due diligence insights.

CRAWL SUMMARY: {all_data.get('crawl_results', {}).get('pages_crawled', 0)} pages analyzed from {all_data.get('crawl_results', {}).get('base_url', 'unknown')}

PRODUCT INTELLIGENCE:
{json.dumps(all_data.get('product_intel', {}), default=str)[:800]}

REVENUE MODEL:
{json.dumps(all_data.get('revenue_model', {}), default=str)[:600]}

CUSTOMER VALIDATION:
{json.dumps(all_data.get('customer_validation', {}), default=str)[:600]}

TEAM INTELLIGENCE:
{json.dumps(all_data.get('team_intel', {}), default=str)[:600]}

TECHNICAL DEPTH:
{json.dumps(all_data.get('technical_depth', {}), default=str)[:600]}

TRACTION SIGNALS:
{json.dumps(all_data.get('traction_signals', {}), default=str)[:600]}

COMPLIANCE:
{json.dumps(all_data.get('compliance', {}), default=str)[:400]}

TECH STACK DETECTED:
{json.dumps(all_data.get('tech_stack', {}), default=str)[:400]}

SALES SIGNALS:
{json.dumps(all_data.get('sales_signals', {}), default=str)[:400]}

Generate a comprehensive intelligence report as JSON:
{{
  "overall_score": "number 0-100",
  "score_breakdown": {{
    "design_ux": "number 0-20",
    "content_quality": "number 0-20",
    "technical_execution": "number 0-20",
    "traction_signals": "number 0-20",
    "trust_signals": "number 0-20"
  }},
  "product_maturity": {{ "score": "0-10", "verdict": "string" }},
  "gtm_motion": {{
    "type": "Product-Led | Sales-Led | Hybrid",
    "target": "SMB | Mid-Market | Enterprise | Mixed",
    "pricing_transparency": "HIGH | MEDIUM | LOW",
    "evidence": ["string"]
  }},
  "market_positioning": {{
    "category": "string",
    "positioning": "string",
    "unique_angle": "string",
    "competitors_mentioned": ["string"]
  }},
  "traction_assessment": {{ "score": "0-10", "key_signals": ["string"] }},
  "technical_credibility": {{ "score": "0-10", "key_signals": ["string"] }},
  "team_quality": {{ "score": "0-10", "key_signals": ["string"] }},
  "red_flags": ["string - concerning signals"],
  "green_flags": ["string - strong positive signals"],
  "revenue_model_assessment": {{
    "model": "string",
    "pricing_strategy": "string",
    "deal_size_estimate": "string or null",
    "sales_complexity": "Low-touch | Medium-touch | High-touch"
  }},
  "one_line_verdict": "string"
}}

IMPORTANT: Base all assessments ONLY on evidence found. Mark unknowns as null. Cite [SOURCE: page_path] for each finding."""

        return await llm.generate_json(prompt, "You are a VC website intelligence analyst. Generate insights only from provided data. Never fabricate signals.")


def _get_pages_by_category(crawl_results: dict, categories: list) -> list:
    """Get page data for given categories."""
    pages = []
    for path, data in crawl_results.get("results", {}).items():
        if data.get("category") in categories:
            pages.append({"path": path, "category": data["category"], "content": data.get("data", {})})
    return pages


def _truncate_pages(pages: list, max_chars: int) -> str:
    """Combine page content with truncation."""
    parts = []
    per_page = max_chars // max(len(pages), 1)
    for p in pages:
        content = p.get("content", {})
        text = content.get("text_content", "")[:per_page]
        title = content.get("title", "")
        headings = content.get("headings", {})
        h1s = ", ".join(headings.get("h1", [])[:3]) if headings else ""
        parts.append(f"--- PAGE: {p['path']} ({p['category']}) ---\nTitle: {title}\nH1: {h1s}\nContent: {text}")
    return "\n\n".join(parts)[:max_chars]


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _detect_sales_motion(text: str) -> str:
    plg_signals = sum(1 for s in ["free trial", "start free", "sign up", "get started", "self-serve"] if s in text)
    sales_signals = sum(1 for s in ["request demo", "talk to sales", "contact sales", "enterprise", "custom pricing"] if s in text)
    if plg_signals > sales_signals:
        return "Product-Led Growth"
    elif sales_signals > plg_signals:
        return "Sales-Led"
    return "Hybrid"

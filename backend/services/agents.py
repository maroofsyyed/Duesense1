"""5 Specialized AI Agents + Investment Scoring System"""
from services.llm_provider import llm


async def agent_founder_quality(extracted: dict, enrichment: dict) -> dict:
    """Agent 1: Founder Quality Evaluator (30 points max)"""
    founders = extracted.get("founders", [])
    github_data = enrichment.get("github", {})

    prompt = f"""You are a VC analyst evaluating founder quality. Score out of 30 points.

SCORING RUBRIC:
- Domain Expertise (0-10): Years in industry, relevant experience, previous companies
- Track Record (0-10): Prior exits, companies built, leadership experience
- Technical Credibility (0-10): Technical skills, GitHub presence, engineering background

FOUNDER DATA:
{_safe_json(founders)}

GITHUB DATA:
{_safe_json(github_data)}

COMPANY SOLUTION:
{_safe_json(extracted.get('solution', {}))}

Respond with JSON only:
{{
  "domain_expertise_score": number (0-10),
  "track_record_score": number (0-10),
  "technical_credibility_score": number (0-10),
  "total_founder_score": number (0-30),
  "reasoning": "string - explain each score with citations from provided data",
  "strengths": ["string"],
  "weaknesses": ["string"],
  "confidence": "HIGH | MEDIUM | LOW"
}}"""

    return await llm.generate_json(prompt, "You are a VC founder evaluation specialist. Score ONLY based on provided data. Never hallucinate.")


async def agent_market_opportunity(extracted: dict, enrichment: dict) -> dict:
    """Agent 2: Market Opportunity Evaluator (20 points max)"""
    market = extracted.get("market", {})
    market_research = enrichment.get("market", {})
    news = enrichment.get("news", {})

    prompt = f"""You are a VC analyst evaluating market opportunity. Score out of 20 points.

SCORING RUBRIC:
- Market Size (0-7): TAM/SAM/SOM validation, growth rate
- Market Timing (0-7): Technology readiness, behavior shifts, regulatory environment
- Competition Landscape (0-6): Market saturation, barriers to entry

MARKET DATA FROM DECK:
{_safe_json(market)}

MARKET RESEARCH:
{_safe_json(market_research)}

NEWS:
{_safe_json(news)}

PROBLEM STATEMENT:
{_safe_json(extracted.get('problem', {}))}

Respond with JSON only:
{{
  "market_size_score": number (0-7),
  "market_timing_score": number (0-7),
  "competition_score": number (0-6),
  "total_market_score": number (0-20),
  "reasoning": "string",
  "market_signals": ["string - key signals found"],
  "confidence": "HIGH | MEDIUM | LOW"
}}"""

    return await llm.generate_json(prompt, "You are a VC market analysis specialist. Analyze based only on provided data.")


async def agent_technical_moat(extracted: dict, enrichment: dict) -> dict:
    """Agent 3: Technical Moat Evaluator (20 points max)"""
    solution = extracted.get("solution", {})
    github_data = enrichment.get("github", {})
    competitors = enrichment.get("competitors", {})

    prompt = f"""You are a VC analyst evaluating technical moat/defensibility. Score out of 20 points.

SCORING RUBRIC:
- Proprietary Technology (0-7): Unique algorithms, patents, proprietary data
- Engineering Velocity (0-7): GitHub activity, tech stack, development pace
- Network Effects/Data Moat (0-6): Data flywheel, network effects, switching costs

SOLUTION DATA:
{_safe_json(solution)}

GITHUB DATA:
{_safe_json(github_data)}

COMPETITOR DATA:
{_safe_json(competitors)}

COMPETITIVE ADVANTAGES:
{_safe_json(extracted.get('competitive_advantages', []))}

Respond with JSON only:
{{
  "proprietary_tech_score": number (0-7),
  "engineering_velocity_score": number (0-7),
  "network_effects_score": number (0-6),
  "total_moat_score": number (0-20),
  "reasoning": "string",
  "moat_type": "string - primary moat type",
  "defensibility_rating": "STRONG | MODERATE | WEAK",
  "confidence": "HIGH | MEDIUM | LOW"
}}"""

    return await llm.generate_json(prompt, "You are a VC technical moat evaluator. Assess only based on provided data.")


async def agent_traction(extracted: dict, enrichment: dict) -> dict:
    """Agent 4: Traction & Metrics Evaluator (20 points max)"""
    traction = extracted.get("traction", {})
    biz_model = extracted.get("business_model", {})
    website = enrichment.get("website", {})

    prompt = f"""You are a VC analyst evaluating traction and metrics. Score out of 20 points.

SCORING RUBRIC:
- Revenue Growth (0-7): >200% YoY=7, >100%=5, >50%=3, any=1
- Unit Economics (0-6): LTV/CAC>3=6, payback<12mo, margins
- Customer Quality (0-4): Enterprise customers, retention, logos
- Product Metrics (0-3): DAU/MAU, activation, engagement

TRACTION DATA:
{_safe_json(traction)}

BUSINESS MODEL:
{_safe_json(biz_model)}

WEBSITE SIGNALS:
{_safe_json(website)}

Respond with JSON only:
{{
  "revenue_growth_score": number (0-7),
  "unit_economics_score": number (0-6),
  "customer_quality_score": number (0-4),
  "product_metrics_score": number (0-3),
  "total_traction_score": number (0-20),
  "reasoning": "string",
  "key_metrics_found": {{}},
  "confidence": "HIGH | MEDIUM | LOW"
}}"""

    return await llm.generate_json(prompt, "You are a VC traction analyst. Score strictly based on available data.")


async def agent_business_model(extracted: dict, enrichment: dict) -> dict:
    """Agent 5: Business Model & Scaling Economics (10 points max)"""
    biz_model = extracted.get("business_model", {})
    funding = extracted.get("funding", {})
    traction = extracted.get("traction", {})

    prompt = f"""You are a VC analyst evaluating business model scalability. Score out of 10 points.

SCORING RUBRIC:
- Revenue Model Clarity (0-4): Clear pricing, monetization strategy
- Scalability (0-3): Path to $100M ARR, capital efficiency
- Capital Efficiency (0-3): Burn rate, runway, efficiency metrics

BUSINESS MODEL:
{_safe_json(biz_model)}

FUNDING:
{_safe_json(funding)}

TRACTION:
{_safe_json(traction)}

Respond with JSON only:
{{
  "revenue_model_score": number (0-4),
  "scalability_score": number (0-3),
  "capital_efficiency_score": number (0-3),
  "total_model_score": number (0-10),
  "reasoning": "string",
  "path_to_100m": "string or null",
  "confidence": "HIGH | MEDIUM | LOW"
}}"""

    return await llm.generate_json(prompt, "You are a VC business model analyst. Score based on provided data only.")


def _safe_json(data) -> str:
    import json
    try:
        if data is None:
            return "No data available"
        return json.dumps(data, indent=2, default=str)[:3000]
    except Exception:
        return str(data)[:3000]

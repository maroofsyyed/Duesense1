"""
Investment Scoring System - compiles all agent scores including website intelligence.

Uses centralized database connection from db module.
"""
import asyncio
from datetime import datetime, timezone
import logging

# Use centralized database module
import db as database

from services.agents import (
    agent_founder_quality,
    agent_market_opportunity,
    agent_technical_moat,
    agent_traction,
    agent_business_model,
)
from services.llm_provider import llm

logger = logging.getLogger(__name__)


def get_scores_col():
    """Get investment scores table (lazy)."""
    return database.scores_collection()


def get_enrichment_col():
    """Get enrichment sources table (lazy)."""
    return database.enrichment_collection()

# v2.0 scoring weights (9 dimensions, total = 100)
SCORING_WEIGHTS = {
    "founder_quality": 22,
    "market_opportunity": 18,
    "technical_moat": 18,
    "traction": 13,
    "business_model": 9,
    "website_intelligence": 8,
    "linkedin_enrichment": 5,
    "funding_quality": 4,
    "web_growth_signals": 3,
}


def _classify_tier(total: float) -> str:
    if total >= 85:
        return "TIER_1"
    elif total >= 70:
        return "TIER_2"
    elif total >= 55:
        return "TIER_3"
    return "PASS"


def _tier_label(tier: str) -> str:
    labels = {
        "TIER_1": "Generational Company (85-100)",
        "TIER_2": "Strong Investment (70-84)",
        "TIER_3": "Consider (55-69)",
        "PASS": "Pass (<55)",
    }
    return labels.get(tier, tier)


async def _agent_website_intelligence(enrichment: dict) -> dict:
    """Score website intelligence from deep crawl data."""
    wi_data = enrichment.get("website_intelligence", {})
    summary = wi_data.get("intelligence_summary", {})

    if not summary or summary.get("error"):
        return {
            "total_website_score": 5,
            "reasoning": "Website intelligence data not available or incomplete",
            "confidence": "LOW",
        }

    # Extract sub-scores from the AI summary
    score_breakdown = summary.get("score_breakdown", {})
    overall = summary.get("overall_score", 50)

    # Normalize to 0-10 scale
    normalized = min(10, max(0, round(overall / 10)))

    return {
        "total_website_score": normalized,
        "overall_raw_score": overall,
        "score_breakdown": score_breakdown,
        "product_maturity": summary.get("product_maturity", {}),
        "gtm_motion": summary.get("gtm_motion", {}),
        "market_positioning": summary.get("market_positioning", {}),
        "traction_assessment": summary.get("traction_assessment", {}),
        "technical_credibility": summary.get("technical_credibility", {}),
        "team_quality": summary.get("team_quality", {}),
        "red_flags": summary.get("red_flags", []),
        "green_flags": summary.get("green_flags", []),
        "revenue_model_assessment": summary.get("revenue_model_assessment", {}),
        "one_line_verdict": summary.get("one_line_verdict", ""),
        "reasoning": summary.get("one_line_verdict", ""),
        "confidence": "HIGH" if overall > 70 else "MEDIUM" if overall > 40 else "LOW",
    }


async def _agent_linkedin_enrichment(enrichment: dict) -> dict:
    """Score LinkedIn enrichment quality (0-5)."""
    # Accept both key names: enrichment engine stores as "linkedin",
    # but scorer historically expected "linkedin_enrichment"
    li_data = enrichment.get("linkedin_enrichment") or enrichment.get("linkedin", {})
    if not li_data or "error" in li_data:
        return {"total_linkedin_score": 0, "reasoning": "No LinkedIn data", "confidence": "LOW"}

    score = 0.0
    reasons = []

    # Founder prior exits (up to 2 pts)
    founders = li_data.get("founders", li_data.get("found_profiles", []))
    if isinstance(founders, list):
        exits = sum(1 for f in founders if isinstance(f, dict) and f.get("prior_exits"))
        if exits > 0:
            score += min(2.0, exits * 1.0)
            reasons.append(f"{exits} founder(s) with prior exits")

    # Connections / network strength (up to 1 pt)
    company_followers = li_data.get("follower_count", 0)
    if company_followers and company_followers > 10000:
        score += 1.0
        reasons.append(f"{company_followers:,} LinkedIn followers")
    elif company_followers and company_followers > 1000:
        score += 0.5

    # Education quality (up to 1 pt)
    top_tier = sum(1 for f in (founders if isinstance(founders, list) else [])
                   if isinstance(f, dict) and f.get("education_top_tier"))
    if top_tier > 0:
        score += 1.0
        reasons.append(f"{top_tier} founder(s) with top-tier education")

    # Employee count / growth (up to 1 pt)
    emp_count = li_data.get("employee_count", 0)
    if emp_count and emp_count > 50:
        score += 1.0
        reasons.append(f"{emp_count} employees on LinkedIn")
    elif emp_count and emp_count > 10:
        score += 0.5

    return {
        "total_linkedin_score": min(5.0, round(score, 1)),
        "reasoning": "; ".join(reasons) if reasons else "LinkedIn data available but limited signals",
        "confidence": "HIGH" if score >= 3 else "MEDIUM" if score >= 1 else "LOW",
    }


async def _agent_funding_quality(enrichment: dict) -> dict:
    """Score funding quality from investor tier and round history (0-4)."""
    funding = enrichment.get("funding_history", {})
    if not funding or "error" in funding:
        return {"total_funding_score": 0, "reasoning": "No funding data", "confidence": "LOW"}

    score = 0.0
    reasons = []

    # Investor tier score (up to 2 pts, scaled from 0-10)
    tier_score = funding.get("investor_tier_score", 0)
    if tier_score:
        score += min(2.0, tier_score / 5.0)
        if tier_score >= 5:
            reasons.append(f"High-quality investors (tier {tier_score}/10)")

    # Total raised (up to 1 pt)
    total = funding.get("total_raised_usd", 0)
    if total >= 10_000_000:
        score += 1.0
        reasons.append(f"${total:,.0f} total raised")
    elif total >= 1_000_000:
        score += 0.5

    # Funding velocity — multiple rounds (up to 1 pt)
    rounds = funding.get("all_rounds", [])
    if len(rounds) >= 3:
        score += 1.0
        reasons.append(f"{len(rounds)} funding rounds")
    elif len(rounds) >= 2:
        score += 0.5

    return {
        "total_funding_score": min(4.0, round(score, 1)),
        "reasoning": "; ".join(reasons) if reasons else "Funding data available",
        "confidence": "HIGH" if score >= 2.5 else "MEDIUM" if score >= 1 else "LOW",
    }


async def _agent_web_growth_signals(enrichment: dict) -> dict:
    """Score web and social growth signals (0-3)."""
    traffic = enrichment.get("web_traffic", {})
    # Accept both flat and nested social_signals structures
    social = enrichment.get("social_signals", {})
    if isinstance(social, dict) and "data" in social:
        social = social["data"]

    score = 0.0
    reasons = []

    # Web traffic trend (up to 1.5 pts)
    visits = traffic.get("monthly_visits")
    if visits and visits > 100_000:
        score += 1.5
        reasons.append(f"{visits:,} monthly visits")
    elif visits and visits > 10_000:
        score += 1.0
        reasons.append(f"{visits:,} monthly visits")
    elif visits and visits > 1_000:
        score += 0.5

    trend = traffic.get("monthly_visits_trend")
    if trend == "UP":
        score += 0.5
        reasons.append("Traffic trending up")

    # Social presence (up to 1 pt)
    social_score = social.get("social_presence_score", 0)
    if social_score and social_score >= 7:
        score += 1.0
        reasons.append(f"Strong social presence ({social_score}/10)")
    elif social_score and social_score >= 4:
        score += 0.5

    return {
        "total_web_growth_score": min(3.0, round(score, 1)),
        "reasoning": "; ".join(reasons) if reasons else "Limited web/social data",
        "confidence": "HIGH" if score >= 2 else "MEDIUM" if score >= 1 else "LOW",
    }


async def _agent_website_due_diligence(enrichment: dict) -> dict:
    """
    Score Website Due Diligence signals (0-10 scale).
    
    Scoring Rubric:
    - Product clarity: 3pts
    - Pricing & GTM clarity: 2pts
    - Customer proof: 2pts
    - Technical credibility: 2pts
    - Trust & compliance: 1pt
    Total: 10pts
    """
    # Find website_due_diligence enrichment
    dd_data = None
    if isinstance(enrichment, dict):
        if "website_due_diligence" in enrichment:
            dd_data = enrichment["website_due_diligence"]
        elif "data" in enrichment:
            dd_data = enrichment.get("data", {})
    
    if not dd_data or dd_data.get("status") == "incomplete":
        return {
            "total_website_dd_score": 0,
            "reasoning": "Website due diligence not available or incomplete",
            "confidence": "LOW",
            "breakdown": {
                "product_clarity": 0,
                "pricing_gtm_clarity": 0,
                "customer_proof": 0,
                "technical_credibility": 0,
                "trust_compliance": 0,
            },
            "red_flags": ["Website data unavailable"],
            "green_flags": [],
        }
    
    extraction = dd_data.get("extraction", {})
    
    # Extract signals
    product_signals = extraction.get("product_signals", {})
    business_signals = extraction.get("business_model_signals", {})
    customer_signals = extraction.get("customer_validation_signals", {})
    trust_signals = extraction.get("trust_compliance_signals", {})
    
    # Initialize scores
    product_score = 0
    pricing_gtm_score = 0
    customer_score = 0
    technical_score = 0
    trust_score = 0
    
    red_flags = []
    green_flags = []
    
    # 1. PRODUCT CLARITY (0-3 points)
    if product_signals.get("product_description") and product_signals["product_description"] != "not_mentioned":
        product_score += 1.5
        green_flags.append("Clear product description")
    else:
        red_flags.append("No clear product description")
    
    if product_signals.get("key_features") and len(product_signals["key_features"]) > 0:
        product_score += 1
        green_flags.append(f"{len(product_signals['key_features'])} key features documented")
    else:
        red_flags.append("No key features listed")
    
    api_available = product_signals.get("api_available", "not_mentioned")
    if api_available in ("true", True):
        product_score += 0.5
        green_flags.append("API available")
    
    # 2. PRICING & GTM CLARITY (0-2 points)
    pricing_model = business_signals.get("pricing_model", "not_mentioned")
    if pricing_model not in ["not_mentioned", "unknown", None]:
        pricing_gtm_score += 1
        green_flags.append(f"Pricing model: {pricing_model}")
    else:
        red_flags.append("No clear pricing model")
    
    price_points = business_signals.get("price_points", [])
    if price_points and len(price_points) > 0:
        pricing_gtm_score += 0.5
        green_flags.append("Pricing tiers visible")
    else:
        red_flags.append("No pricing information")
    
    sales_motion = business_signals.get("sales_motion", "not_mentioned")
    if sales_motion != "not_mentioned":
        pricing_gtm_score += 0.5
        green_flags.append(f"Sales motion: {sales_motion}")
    
    # 3. CUSTOMER PROOF (0-2 points)
    logos_count = customer_signals.get("customer_logos_count", "not_mentioned")
    if logos_count != "not_mentioned" and logos_count not in [None, 0, "0"]:
        try:
            count = int(logos_count) if isinstance(logos_count, (int, str)) else 0
            if count > 0:
                customer_score += 1
                green_flags.append(f"{count} customer logos displayed")
        except (ValueError, TypeError):
            pass
    else:
        red_flags.append("No customer logos")
    
    case_studies = customer_signals.get("case_study_count", "not_mentioned")
    if case_studies != "not_mentioned" and case_studies not in [None, 0, "0"]:
        try:
            count = int(case_studies) if isinstance(case_studies, (int, str)) else 0
            if count > 0:
                customer_score += 0.5
                green_flags.append(f"{count} case studies")
        except (ValueError, TypeError):
            pass
    
    named_customers = customer_signals.get("named_customers", [])
    if named_customers and len(named_customers) > 0:
        customer_score += 0.5
        green_flags.append(f"{len(named_customers)} named customers")
    
    # 4. TECHNICAL CREDIBILITY (0-2 points)
    api_available = product_signals.get("api_available", "not_mentioned")
    if api_available in ("true", True):
        technical_score += 1
    
    integrations = product_signals.get("integrations", [])
    if integrations and len(integrations) > 0:
        technical_score += 0.5
        green_flags.append(f"{len(integrations)} integrations")
    
    certifications = trust_signals.get("certifications", [])
    if certifications and len(certifications) > 0:
        technical_score += 0.5
    
    # 5. TRUST & COMPLIANCE (0-1 point)
    security_page = trust_signals.get("security_page_exists", False)
    if security_page:
        trust_score += 0.5
        green_flags.append("Security page exists")
    else:
        red_flags.append("No security page")
    
    privacy_policy = trust_signals.get("privacy_policy_exists", False)
    if privacy_policy:
        trust_score += 0.25
        green_flags.append("Privacy policy exists")
    
    if certifications and len(certifications) > 0:
        trust_score += 0.25
        green_flags.append(f"Certifications: {', '.join(certifications[:3])}")
    
    # Add extracted red/green flags
    extracted_red = extraction.get("red_flags", [])
    extracted_green = extraction.get("green_flags", [])
    
    if extracted_red:
        red_flags.extend(extracted_red[:3])
    if extracted_green:
        green_flags.extend(extracted_green[:3])
    
    # Calculate total (capped at 10)
    total = min(10, product_score + pricing_gtm_score + customer_score + technical_score + trust_score)
    
    # Confidence based on data availability
    pages_crawled = dd_data.get("pages_crawled", 0)
    confidence = "HIGH" if pages_crawled >= 10 else "MEDIUM" if pages_crawled >= 5 else "LOW"
    
    return {
        "total_website_dd_score": round(total, 1),
        "breakdown": {
            "product_clarity": round(product_score, 1),
            "pricing_gtm_clarity": round(pricing_gtm_score, 1),
            "customer_proof": round(customer_score, 1),
            "technical_credibility": round(technical_score, 1),
            "trust_compliance": round(trust_score, 1),
        },
        "red_flags": list(set(red_flags))[:5],
        "green_flags": list(set(green_flags))[:8],
        "reasoning": f"Website DD Score: {round(total, 1)}/10 based on {pages_crawled} pages crawled",
        "confidence": confidence,
        "pages_analyzed": pages_crawled,
    }



async def calculate_investment_score(company_id: str, extracted: dict, enrichment: dict) -> dict:
    """Run all scoring agents in parallel and compile final score (9 dimensions)."""

    # Fetch website DD enrichment from Supabase
    website_dd_enrichment = None
    website_dd_row = get_enrichment_col().find_one(
        {"company_id": company_id, "source_type": "website_due_diligence"}
    )
    if website_dd_row:
        website_dd_enrichment = website_dd_row.get("data", {})

    results = await asyncio.gather(
        agent_founder_quality(extracted, enrichment),           # 0
        agent_market_opportunity(extracted, enrichment),        # 1
        agent_technical_moat(extracted, enrichment),            # 2
        agent_traction(extracted, enrichment),                  # 3
        agent_business_model(extracted, enrichment),            # 4
        _agent_website_intelligence(enrichment),                # 5
        _agent_website_due_diligence(website_dd_enrichment if website_dd_enrichment else {}),  # 6
        _agent_linkedin_enrichment(enrichment),                 # 7
        _agent_funding_quality(enrichment),                     # 8
        _agent_web_growth_signals(enrichment),                  # 9
        return_exceptions=True,
    )

    def _safe(idx): return results[idx] if not isinstance(results[idx], Exception) else {}

    founder_result = _safe(0)
    market_result = _safe(1)
    moat_result = _safe(2)
    traction_result = _safe(3)
    model_result = _safe(4)
    website_result = _safe(5)
    website_dd_result = _safe(6)
    linkedin_result = _safe(7)
    funding_result = _safe(8)
    web_growth_result = _safe(9)

    # Apply v2.0 weights (22/18/18/13/9/8/5/4/3 = 100)
    founder_score = min(22, max(0, float(founder_result.get("total_founder_score", 11)) * (22 / 30)))
    market_score = min(18, max(0, float(market_result.get("total_market_score", 9)) * (18 / 20)))
    moat_score = min(18, max(0, float(moat_result.get("total_moat_score", 9)) * (18 / 20)))
    traction_score = min(13, max(0, float(traction_result.get("total_traction_score", 7)) * (13 / 20)))
    model_score_val = min(9, max(0, float(model_result.get("total_model_score", 5)) * (9 / 10)))
    website_score = min(8, max(0, float(website_result.get("total_website_score", 4)) * (8 / 10)))
    linkedin_score = min(5, max(0, float(linkedin_result.get("total_linkedin_score", 0))))
    funding_score = min(4, max(0, float(funding_result.get("total_funding_score", 0))))
    web_growth_score = min(3, max(0, float(web_growth_result.get("total_web_growth_score", 0))))

    total = (
        founder_score + market_score + moat_score + traction_score
        + model_score_val + website_score + linkedin_score
        + funding_score + web_growth_score
    )
    tier = _classify_tier(total)

    def _conf(d): return d.get("confidence", "MEDIUM") if isinstance(d, dict) else "MEDIUM"

    confidences = [
        _conf(founder_result),
        _conf(market_result),
        _conf(moat_result),
        _conf(traction_result),
        _conf(model_result),
        _conf(website_result),
        _conf(website_dd_result),
        _conf(linkedin_result),
        _conf(funding_result),
        _conf(web_growth_result),
    ]
    high_count = confidences.count("HIGH")
    confidence = "HIGH" if high_count >= 5 else "LOW" if high_count <= 1 else "MEDIUM"

    try:
        thesis = await _generate_thesis(extracted, total, tier, founder_result, market_result, moat_result, traction_result, model_result, website_result, website_dd_result)
    except Exception as thesis_err:
        logger.error(f"Thesis generation failed (scoring will still save): {thesis_err}")
        thesis = {
            "recommendation": "HOLD",
            "investment_thesis": "Thesis generation failed due to an LLM error. Numeric scores are still valid.",
            "top_reasons": [],
            "top_risks": ["Thesis could not be generated — manual review recommended"],
            "expected_return": "N/A",
        }

    score_data = {
        "company_id": company_id,
        "total_score": round(total, 1),
        "tier": tier,
        "tier_label": _tier_label(tier),
        "confidence_level": confidence,
        "founder_score": round(founder_score, 1),
        "market_score": round(market_score, 1),
        "moat_score": round(moat_score, 1),
        "traction_score": round(traction_score, 1),
        "model_score": round(model_score_val, 1),
        "website_score": round(website_score, 1),
        "website_dd_score": round(float(website_dd_result.get("total_website_dd_score", 0)), 1),
        "linkedin_score": round(linkedin_score, 1),
        "funding_quality_score": round(funding_score, 1),
        "web_growth_score": round(web_growth_score, 1),
        "social_presence_score": round(
            float(enrichment.get("social_signals", {}).get("social_presence_score", 0)), 1
        ),
        "scoring_weights": SCORING_WEIGHTS,
        "agent_details": {
            "founder": founder_result,
            "market": market_result,
            "moat": moat_result,
            "traction": traction_result,
            "business_model": model_result,
            "website_intelligence": website_result,
            "website_due_diligence": website_dd_result,
            "linkedin_enrichment": linkedin_result,
            "funding_quality": funding_result,
            "web_growth_signals": web_growth_result,
        },
        "recommendation": thesis.get("recommendation", ""),
        "investment_thesis": thesis.get("investment_thesis", ""),
        "top_reasons": thesis.get("top_reasons", []),
        "top_risks": thesis.get("top_risks", []),
        "expected_return": thesis.get("expected_return", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    get_scores_col().upsert(score_data, conflict_column="company_id")

    return score_data


async def _generate_thesis(extracted, total, tier, founder, market, moat, traction, model, website, website_dd) -> dict:
    company_name = extracted.get("company", {}).get("name", "the company")

    # Collect website red/green flags for thesis
    red_flags = website.get("red_flags", [])
    green_flags = website.get("green_flags", [])
    
    # Add website DD flags
    dd_red_flags = website_dd.get("red_flags", [])
    dd_green_flags = website_dd.get("green_flags", [])
    
    all_red_flags = (red_flags + dd_red_flags)[:5]
    all_green_flags = (green_flags + dd_green_flags)[:5]

    prompt = f"""Based on the investment analysis of {company_name}, generate:

SCORES:
- Total: {total}/100 ({tier})
- Founders: {founder.get('total_founder_score', 'N/A')}/25 - {str(founder.get('reasoning', 'N/A'))[:150]}
- Market: {market.get('total_market_score', 'N/A')}/20 - {str(market.get('reasoning', 'N/A'))[:150]}
- Moat: {moat.get('total_moat_score', 'N/A')}/20 - {str(moat.get('reasoning', 'N/A'))[:150]}
- Traction: {traction.get('total_traction_score', 'N/A')}/15 - {str(traction.get('reasoning', 'N/A'))[:150]}
- Business Model: {model.get('total_model_score', 'N/A')}/10 - {str(model.get('reasoning', 'N/A'))[:150]}
- Website Intelligence: {website.get('total_website_score', 'N/A')}/10 - {str(website.get('one_line_verdict', 'N/A'))[:150]}
- Website Due Diligence: {website_dd.get('total_website_dd_score', 'N/A')}/10 - {str(website_dd.get('reasoning', 'N/A'))[:150]}

WEBSITE RED FLAGS: {all_red_flags}
WEBSITE GREEN FLAGS: {all_green_flags}

COMPANY: {_safe_json(extracted.get('company', {}))}

Respond with JSON:
{{
  "recommendation": "STRONG BUY | BUY | HOLD | PASS",
  "investment_thesis": "2-3 paragraph thesis incorporating website intelligence and due diligence insights",
  "top_reasons": ["reason 1", "reason 2", "reason 3"],
  "top_risks": ["risk 1", "risk 2", "risk 3"],
  "expected_return": "Nx in Y years"
}}"""

    return await llm.generate_json(prompt, "You are a senior VC partner. Include website intelligence findings in your recommendation.")


def _safe_json(data) -> str:
    import json
    try:
        return json.dumps(data, default=str)[:2000]
    except Exception:
        return str(data)[:2000]

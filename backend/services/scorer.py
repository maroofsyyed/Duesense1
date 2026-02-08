"""Investment Scoring System - compiles all agent scores including website intelligence."""
import asyncio
from datetime import datetime, timezone
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import os

from services.agents import (
    agent_founder_quality,
    agent_market_opportunity,
    agent_technical_moat,
    agent_traction,
    agent_business_model,
)
from services.llm_provider import llm

load_dotenv()
client = MongoClient(os.environ.get("MONGO_URL"))
db = client[os.environ.get("DB_NAME")]
scores_col = db["investment_scores"]
enrichment_col = db["enrichment_sources"]

# Updated scoring weights
SCORING_WEIGHTS = {
    "founder_quality": 25,
    "market_opportunity": 20,
    "technical_moat": 20,
    "traction": 15,
    "business_model": 10,
    "website_intelligence": 10,
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


async def calculate_investment_score(company_id: str, extracted: dict, enrichment: dict) -> dict:
    """Run all 6 agents in parallel and compile final score."""

    results = await asyncio.gather(
        agent_founder_quality(extracted, enrichment),
        agent_market_opportunity(extracted, enrichment),
        agent_technical_moat(extracted, enrichment),
        agent_traction(extracted, enrichment),
        agent_business_model(extracted, enrichment),
        _agent_website_intelligence(enrichment),
        return_exceptions=True,
    )

    founder_result = results[0] if not isinstance(results[0], Exception) else {}
    market_result = results[1] if not isinstance(results[1], Exception) else {}
    moat_result = results[2] if not isinstance(results[2], Exception) else {}
    traction_result = results[3] if not isinstance(results[3], Exception) else {}
    model_result = results[4] if not isinstance(results[4], Exception) else {}
    website_result = results[5] if not isinstance(results[5], Exception) else {}

    # Apply updated weights
    founder_score = min(25, max(0, float(founder_result.get("total_founder_score", 12)) * (25 / 30)))
    market_score = min(20, max(0, float(market_result.get("total_market_score", 10))))
    moat_score = min(20, max(0, float(moat_result.get("total_moat_score", 10))))
    traction_score = min(15, max(0, float(traction_result.get("total_traction_score", 8)) * (15 / 20)))
    model_score_val = min(10, max(0, float(model_result.get("total_model_score", 5))))
    website_score = min(10, max(0, float(website_result.get("total_website_score", 5))))

    total = founder_score + market_score + moat_score + traction_score + model_score_val + website_score
    tier = _classify_tier(total)

    confidences = [
        founder_result.get("confidence", "MEDIUM"),
        market_result.get("confidence", "MEDIUM"),
        moat_result.get("confidence", "MEDIUM"),
        traction_result.get("confidence", "MEDIUM"),
        model_result.get("confidence", "MEDIUM"),
        website_result.get("confidence", "MEDIUM"),
    ]
    high_count = confidences.count("HIGH")
    confidence = "HIGH" if high_count >= 3 else "LOW" if high_count == 0 else "MEDIUM"

    thesis = await _generate_thesis(extracted, total, tier, founder_result, market_result, moat_result, traction_result, model_result, website_result)

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
        "scoring_weights": SCORING_WEIGHTS,
        "agent_details": {
            "founder": founder_result,
            "market": market_result,
            "moat": moat_result,
            "traction": traction_result,
            "business_model": model_result,
            "website_intelligence": website_result,
        },
        "recommendation": thesis.get("recommendation", ""),
        "investment_thesis": thesis.get("investment_thesis", ""),
        "top_reasons": thesis.get("top_reasons", []),
        "top_risks": thesis.get("top_risks", []),
        "expected_return": thesis.get("expected_return", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    scores_col.update_one(
        {"company_id": company_id},
        {"$set": score_data},
        upsert=True,
    )

    return score_data


async def _generate_thesis(extracted, total, tier, founder, market, moat, traction, model, website) -> dict:
    company_name = extracted.get("company", {}).get("name", "the company")

    # Collect website red/green flags for thesis
    red_flags = website.get("red_flags", [])
    green_flags = website.get("green_flags", [])

    prompt = f"""Based on the investment analysis of {company_name}, generate:

SCORES:
- Total: {total}/100 ({tier})
- Founders: {founder.get('total_founder_score', 'N/A')}/25 - {str(founder.get('reasoning', 'N/A'))[:150]}
- Market: {market.get('total_market_score', 'N/A')}/20 - {str(market.get('reasoning', 'N/A'))[:150]}
- Moat: {moat.get('total_moat_score', 'N/A')}/20 - {str(moat.get('reasoning', 'N/A'))[:150]}
- Traction: {traction.get('total_traction_score', 'N/A')}/15 - {str(traction.get('reasoning', 'N/A'))[:150]}
- Business Model: {model.get('total_model_score', 'N/A')}/10 - {str(model.get('reasoning', 'N/A'))[:150]}
- Website Intelligence: {website.get('total_website_score', 'N/A')}/10 - {str(website.get('one_line_verdict', 'N/A'))[:150]}

WEBSITE RED FLAGS: {red_flags[:3]}
WEBSITE GREEN FLAGS: {green_flags[:3]}

COMPANY: {_safe_json(extracted.get('company', {}))}

Respond with JSON:
{{
  "recommendation": "STRONG BUY | BUY | HOLD | PASS",
  "investment_thesis": "2-3 paragraph thesis incorporating website intelligence insights",
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

"""
Investment Memo Generator - creates comprehensive investment report.

Uses centralized database connection from db module.
"""
import json
from datetime import datetime, timezone
import logging

# Use centralized database module
import db as database

from services.llm_provider import llm

logger = logging.getLogger(__name__)


def get_memos_col():
    """Get investment memos collection (lazy)."""
    return database.memos_collection()


def get_enrichment_col():
    """Get enrichment sources collection (lazy)."""
    return database.enrichment_collection()



async def generate_memo(company_id: str, extracted: dict, enrichment: dict, score: dict) -> dict:
    """Generate a comprehensive investment memo."""

    company_name = extracted.get("company", {}).get("name", "Unknown")
    
    # Fetch Website DD data
    website_dd_data = None
    website_dd_score = score.get("website_dd_score", 0)
    website_dd_details = score.get("agent_details", {}).get("website_due_diligence", {})
    
    # Try to get the raw website DD data from enrichment
    website_dd_enrichment = get_enrichment_col().find_one(
        {"company_id": company_id, "source_type": "website_due_diligence"}
    )
    if website_dd_enrichment:
        website_dd_data = website_dd_enrichment.get("data", {})

    prompt = f"""You are a senior VC analyst writing a comprehensive investment memo for {company_name}.

Write a detailed investment memo covering all sections below. Each fact MUST be sourced from the provided data.
Use [SOURCE: section_name] citations for every claim.

EXTRACTED DECK DATA:
{json.dumps(extracted, default=str)[:4000]}

ENRICHMENT DATA:
{json.dumps(enrichment, default=str)[:3000]}

WEBSITE DUE DILIGENCE DATA:
{json.dumps(website_dd_data, default=str)[:2000] if website_dd_data else "Not available"}

INVESTMENT SCORE:
Total: {score.get('total_score')}/100 - {score.get('tier')}
Founders: {score.get('founder_score')}/25
Market: {score.get('market_score')}/20
Moat: {score.get('moat_score')}/20
Traction: {score.get('traction_score')}/15
Business Model: {score.get('model_score')}/10
Website Intelligence: {score.get('website_score')}/10
Website Due Diligence: {website_dd_score}/10
Recommendation: {score.get('recommendation')}
Thesis: {score.get('investment_thesis', '')[:500]}
Top Reasons: {json.dumps(score.get('top_reasons', []))}
Top Risks: {json.dumps(score.get('top_risks', []))}

Write the memo in this structure (respond with JSON):
{{
  "title": "Investment Memo: {company_name}",
  "date": "{datetime.now().strftime('%B %d, %Y')}",
  "sections": [
    {{
      "title": "Executive Summary",
      "content": "2-3 paragraphs summarizing the investment opportunity"
    }},
    {{
      "title": "Company Overview",
      "content": "Company description, product, founding story"
    }},
    {{
      "title": "Founders & Team",
      "content": "Founder backgrounds, strengths, concerns"
    }},
    {{
      "title": "Market Opportunity",
      "content": "TAM/SAM/SOM, market trends, timing analysis"
    }},
    {{
      "title": "Competitive Landscape",
      "content": "Key competitors, differentiation, moat analysis"
    }},
    {{
      "title": "Technical Moat & Product",
      "content": "Technology stack, proprietary advantages, IP"
    }},
    {{
      "title": "Traction & Metrics",
      "content": "Revenue, growth, unit economics, customers"
    }},
    {{
      "title": "Business Model & Scalability",
      "content": "Revenue model, pricing, path to scale"
    }},
    {{
      "title": "Website Due Diligence",
      "content": "Website DD Score: {website_dd_score}/10. Analyze product clarity, pricing transparency, customer validation, technical credibility, and trust signals found on the website. For each signal category, explicitly state what was found or 'Not mentioned on website' if absent. Include source URLs for all claims. Red flags: {json.dumps(website_dd_details.get('red_flags', []))}. Green flags: {json.dumps(website_dd_details.get('green_flags', []))}."
    }},
    {{
      "title": "Investment Thesis",
      "content": "Why invest, expected returns, timeline"
    }},
    {{
      "title": "Risks & Mitigations",
      "content": "Key risks with proposed mitigations"
    }},
    {{
      "title": "Due Diligence Roadmap",
      "content": "Next steps for deeper diligence"
    }}
  ],
  "score_summary": {{
    "total": {score.get('total_score', 0)},
    "tier": "{score.get('tier', 'N/A')}",
    "recommendation": "{score.get('recommendation', 'N/A')}"
  }}
}}

IMPORTANT: Every factual claim must have a [SOURCE: ...] citation."""

    memo_data = await llm.generate_json(prompt, "You are a world-class VC investment analyst. Write clear, data-driven memos with mandatory source citations.")

    memo_data["company_id"] = company_id
    memo_data["created_at"] = datetime.now(timezone.utc).isoformat()
    memo_data["status"] = "completed"

    # Upsert memo
    get_memos_col().update_one(
        {"company_id": company_id},
        {"$set": memo_data},
        upsert=True,
    )

    return memo_data

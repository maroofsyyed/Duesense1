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
    """Get investment memos table (lazy)."""
    return database.memos_collection()


def get_enrichment_col():
    """Get enrichment sources table (lazy)."""
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

    # Gather data from new agents
    gtm_data = enrichment.get("gtm_analysis", {})
    market_sizing = enrichment.get("market_sizing", {})
    competitive = enrichment.get("competitive_landscape", {})
    milestones = enrichment.get("milestones", {})
    social_signals = enrichment.get("social_signals", {})
    glassdoor = enrichment.get("glassdoor", {})
    founder_profiles = enrichment.get("founder_profiles", {})
    company_profile = enrichment.get("company_profile", {})

    prompt = f"""You are a senior VC analyst writing a comprehensive investment memo for {company_name}.

Write a detailed investment memo covering ALL sections below. Each fact MUST be sourced from the provided data.
Use [SOURCE: section_name] citations for every claim.

EXTRACTED DECK DATA:
{json.dumps(extracted, default=str)[:3500]}

ENRICHMENT DATA:
{json.dumps(enrichment, default=str)[:2000]}

WEBSITE DUE DILIGENCE DATA:
{json.dumps(website_dd_data, default=str)[:1500] if website_dd_data else "Not available"}

GTM ANALYSIS:
{json.dumps(gtm_data, default=str)[:1000]}

MARKET SIZING:
{json.dumps(market_sizing, default=str)[:1000]}

COMPETITIVE LANDSCAPE:
{json.dumps(competitive.get('moat_assessment', {}), default=str)[:800]}

MILESTONE TIMELINE:
{json.dumps(milestones.get('milestones', [])[:5], default=str)[:800]}

SOCIAL SIGNALS:
{json.dumps(social_signals.get('composite_score', {}), default=str)[:500]}

GLASSDOOR / TEAM HEALTH:
{json.dumps(glassdoor, default=str)[:500]}

FOUNDER PROFILES:
{json.dumps(founder_profiles.get('founders', [])[:2], default=str)[:800]}

COMPANY PROFILE:
{json.dumps(company_profile, default=str)[:500]}

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
      "content": "Company description, product, founding story, verified profile data"
    }},
    {{
      "title": "Founders & Team",
      "content": "Founder backgrounds from LinkedIn dossiers, credibility scores, Glassdoor team health, strengths and concerns"
    }},
    {{
      "title": "Market Opportunity & Sizing",
      "content": "TAM/SAM/SOM from market sizing agent, CAGR, growth drivers, deck claim validation"
    }},
    {{
      "title": "Go-to-Market Strategy",
      "content": "Sales motion (PLG vs SLG), target segments, channel mix, pricing strategy, GTM maturity assessment"
    }},
    {{
      "title": "Competitive Landscape",
      "content": "Key competitors with profiles, feature comparison matrix, moat type and strength, competitive threats"
    }},
    {{
      "title": "Technical Moat & Product",
      "content": "Technology stack, proprietary advantages, IP, engineering velocity"
    }},
    {{
      "title": "Traction & Metrics",
      "content": "Revenue, growth, unit economics, customers"
    }},
    {{
      "title": "Funding History & Cap Table",
      "content": "Previous rounds, investors, total raised, current raise, valuation context"
    }},
    {{
      "title": "Growth Indicators & Social Signals",
      "content": "LinkedIn followers, Twitter presence, GitHub activity, YouTube stats if applicable, social signal composite score"
    }},
    {{
      "title": "Business Model & Scalability",
      "content": "Revenue model, pricing, path to scale"
    }},
    {{
      "title": "Key Milestones",
      "content": "Product launches, customer wins, funding events, execution velocity assessment from milestone tracker"
    }},
    {{
      "title": "Website Due Diligence",
      "content": "Website DD Score: {website_dd_score}/10. Product clarity, pricing transparency, customer validation, technical credibility, trust signals. Red flags: {json.dumps(website_dd_details.get('red_flags', []))}. Green flags: {json.dumps(website_dd_details.get('green_flags', []))}."
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
    get_memos_col().upsert(memo_data, conflict_column="company_id")

    return memo_data

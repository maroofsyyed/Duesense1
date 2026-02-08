import io
from pypdf import PdfReader
from pptx import Presentation
from services.llm_provider import llm


async def extract_deck(file_path: str, file_ext: str) -> dict:
    """Extract structured data from a pitch deck file."""
    with open(file_path, "rb") as f:
        content = f.read()

    if file_ext == "pdf":
        text = _extract_pdf(content)
    else:
        text = _extract_pptx(content)

    if not text or len(text.strip()) < 50:
        raise ValueError("Could not extract meaningful text from the file")

    structured = await _structure_with_llm(text)
    return structured


def _extract_pdf(content: bytes) -> str:
    pdf_file = io.BytesIO(content)
    reader = PdfReader(pdf_file)
    parts = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            parts.append(t)
    return "\n\n".join(parts)


def _extract_pptx(content: bytes) -> str:
    pptx_file = io.BytesIO(content)
    prs = Presentation(pptx_file)
    parts = []
    for slide_num, slide in enumerate(prs.slides, 1):
        slide_text = [f"--- Slide {slide_num} ---"]
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                slide_text.append(shape.text)
        parts.append("\n".join(slide_text))
    return "\n\n".join(parts)


async def _structure_with_llm(text: str) -> dict:
    prompt = f"""You are an expert at extracting structured data from startup pitch decks.

CRITICAL RULES:
1. ONLY extract information EXPLICITLY stated in the text
2. Use null for any missing fields - NEVER guess or hallucinate
3. Quote exact numbers - no rounding
4. Be precise about what the company does

Extract the following JSON structure from the pitch deck text below:

{{
  "company": {{
    "name": "string - company name",
    "tagline": "string - one-line description",
    "founded": "string - year or null",
    "hq_location": "string or null",
    "website": "string or null",
    "stage": "pre-seed | seed | series-a | series-b | series-c+ | null",
    "industry": "string - primary industry"
  }},
  "founders": [
    {{
      "name": "string",
      "role": "string - CEO/CTO/etc",
      "linkedin": "string or null",
      "github": "string or null",
      "previous_companies": ["string"],
      "years_in_industry": "number or null",
      "education": "string or null"
    }}
  ],
  "problem": {{
    "statement": "string - QUOTE from deck if possible",
    "market_pain": "string",
    "current_solutions": ["string"]
  }},
  "solution": {{
    "product_description": "string - what the product does",
    "key_features": ["string"],
    "technology_stack": ["string"],
    "ai_usage": {{
      "is_ai_core": true/false,
      "ai_description": "string or null",
      "proprietary_data": true/false,
      "model_architecture": "string or null"
    }}
  }},
  "market": {{
    "tam": "string with $ amount or null",
    "sam": "string with $ amount or null",
    "som": "string with $ amount or null",
    "growth_rate": "string or null",
    "target_customers": "string"
  }},
  "traction": {{
    "revenue": "string with $ amount or null",
    "mrr": "string or null",
    "customers": "number or null",
    "growth_rate": "string or null",
    "key_metrics": {{}}
  }},
  "business_model": {{
    "type": "SaaS | Marketplace | Enterprise | etc",
    "pricing": "string or null",
    "unit_economics": "string or null"
  }},
  "funding": {{
    "seeking": "string with $ amount or null",
    "previous_rounds": ["string"],
    "total_raised": "string or null",
    "valuation": "string or null"
  }},
  "competitive_advantages": ["string"],
  "risks": ["string"]
}}

PITCH DECK TEXT:
{text[:12000]}

Return ONLY valid JSON. No markdown formatting, no explanations."""

    system = "You are a precise data extraction assistant for venture capital due diligence. Extract ONLY factual information. Never hallucinate or guess. Use null for missing data."

    result = await llm.generate_json(prompt, system)
    return result

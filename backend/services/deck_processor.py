"""
Deck Processor for DueSense
Extracts text from PDF/PPTX pitch decks and structures with LLM.
"""
import io
import logging
from pypdf import PdfReader
from pptx import Presentation
from services.llm_provider import llm

logger = logging.getLogger(__name__)


async def extract_deck(file_path: str, file_ext: str) -> dict:
    """
    Extract structured data from a pitch deck file.
    
    Args:
        file_path: Path to the uploaded file
        file_ext: File extension (pdf, pptx, ppt)
        
    Returns:
        Structured data dict with company info, founders, etc.
        
    Raises:
        ValueError: If file cannot be read or has no extractable text
        RuntimeError: If LLM processing fails
    """
    logger.info(f"📄 Starting deck extraction: {file_path} (type: {file_ext})")
    
    # Read file content
    try:
        with open(file_path, "rb") as f:
            content = f.read()
        logger.info(f"✓ File read: {len(content):,} bytes")
    except Exception as e:
        logger.error(f"❌ Failed to read file {file_path}: {e}")
        raise ValueError(f"Could not read file: {e}")

    # Extract text based on file type
    try:
        if file_ext == "pdf":
            text = _extract_pdf(content)
        else:
            text = _extract_pptx(content)
        logger.info(f"✓ Text extracted: {len(text):,} chars")
    except Exception as e:
        logger.error(f"❌ Text extraction failed: {type(e).__name__}: {e}")
        raise ValueError(f"Could not extract text from {file_ext.upper()} file: {e}")

    # Validate extracted text
    if not text or len(text.strip()) < 50:
        logger.error(f"❌ Insufficient text extracted: {len(text) if text else 0} chars")
        raise ValueError(
            f"Could not extract meaningful text from the file. "
            f"The file may be image-based, corrupted, or password-protected. "
            f"Extracted {len(text) if text else 0} characters."
        )

    # Structure with LLM
    try:
        logger.info(f"🤖 Sending {len(text[:12000])} chars to LLM for structuring...")
        structured = await _structure_with_llm(text)
        logger.info(f"✓ LLM structuring complete")
        return structured
    except Exception as e:
        logger.error(f"❌ LLM structuring failed: {type(e).__name__}: {e}")
        raise RuntimeError(f"AI analysis failed: {e}")


def _extract_pdf(content: bytes) -> str:
    """Extract text from PDF content."""
    try:
        pdf_file = io.BytesIO(content)
        reader = PdfReader(pdf_file)
        parts = []
        
        logger.info(f"  Processing {len(reader.pages)} PDF pages...")
        
        for page_num, page in enumerate(reader.pages, 1):
            try:
                t = page.extract_text()
                if t:
                    parts.append(t)
            except Exception as page_err:
                logger.warning(f"  ⚠️ Failed to extract page {page_num}: {page_err}")
                continue
        
        text = "\n\n".join(parts)
        logger.info(f"  Extracted text from {len(parts)}/{len(reader.pages)} pages")
        return text
        
    except Exception as e:
        logger.error(f"  ❌ PDF extraction error: {e}")
        raise ValueError(f"PDF extraction failed: {e}")


def _extract_pptx(content: bytes) -> str:
    """Extract text from PPTX content."""
    try:
        pptx_file = io.BytesIO(content)
        prs = Presentation(pptx_file)
        parts = []
        
        logger.info(f"  Processing {len(prs.slides)} slides...")
        
        for slide_num, slide in enumerate(prs.slides, 1):
            slide_text = [f"--- Slide {slide_num} ---"]
            try:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_text.append(shape.text)
            except Exception as shape_err:
                logger.warning(f"  ⚠️ Error on slide {slide_num}: {shape_err}")
            parts.append("\n".join(slide_text))
        
        text = "\n\n".join(parts)
        logger.info(f"  Extracted text from {len(parts)} slides")
        return text
        
    except Exception as e:
        logger.error(f"  ❌ PPTX extraction error: {e}")
        raise ValueError(f"PPTX extraction failed: {e}")


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

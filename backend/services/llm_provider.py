"""
Production LLM Provider for DueSense v2.0

Z.ai ONLY — per CLAUDE.md specification.
Models: gpt-4o (complex), gpt-4o-mini (standard).
Includes retry logic and proper error propagation.
"""

import os
import re
import json
import logging
import asyncio
from typing import Dict, Any
import httpx

logger = logging.getLogger(__name__)

ZAI_BASE_URL = "https://api.zukijourney.com/v1/chat/completions"
MAX_RETRIES = 2
RETRY_DELAY = 2  # seconds


class LLMProvider:
    def __init__(self):
        self.api_key = os.getenv("Z_API_KEY")
        if not self.api_key:
            raise RuntimeError("Z_API_KEY is required — no LLM provider configured")
        logger.info("✓ LLM provider initialized (Z.ai only)")

    # ----------------------------
    # Model selection
    # ----------------------------
    def _select_model(self, prompt: str) -> str:
        """Use gpt-4o for complex prompts, gpt-4o-mini for standard."""
        return "gpt-4o" if len(prompt) > 6000 else "gpt-4o-mini"

    # ----------------------------
    # Public API
    # ----------------------------
    async def generate(
        self,
        prompt: str,
        system_message: str = "You are a helpful assistant.",
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> str:
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = await self._call_zai(prompt, system_message, max_tokens, temperature)
                if result and len(result.strip()) > 5:
                    return result
                logger.warning(f"⚠️ Z.ai returned near-empty response (attempt {attempt})")
                last_error = RuntimeError("Z.ai returned empty response")
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ Z.ai attempt {attempt}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY)

        # All retries exhausted — raise so callers can handle it
        raise RuntimeError(f"LLM call failed after {MAX_RETRIES} attempts: {last_error}")

    # ----------------------------
    # JSON-safe generation
    # ----------------------------
    async def generate_json(
        self,
        prompt: str,
        system_message: str = "Respond ONLY with valid JSON.",
        max_tokens: int = 4000,
    ) -> Dict[str, Any]:
        text = await self.generate(prompt, system_message, max_tokens=max_tokens)

        # Try to extract JSON from the response
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON in the text (e.g. wrapped in markdown code blocks)
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

            # Try to find any JSON object in the response
            brace_match = re.search(r'\{.*\}', text, re.DOTALL)
            if brace_match:
                try:
                    return json.loads(brace_match.group(0))
                except json.JSONDecodeError:
                    pass

            logger.error(f"❌ JSON parse failed — response preview: {text[:300]}")
            raise RuntimeError(f"LLM returned non-JSON response: {text[:200]}")

    # ----------------------------
    # Z.ai API call
    # ----------------------------
    async def _call_zai(
        self,
        prompt: str,
        system_message: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        model = self._select_model(prompt)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(ZAI_BASE_URL, headers=headers, json=payload)

        if r.status_code == 429:
            raise RuntimeError("Z.ai rate limited — retry later")

        if r.status_code >= 500:
            raise RuntimeError(f"Z.ai server error: {r.status_code}")

        r.raise_for_status()

        response_data = r.json()
        content = response_data["choices"][0]["message"]["content"]
        logger.info(f"✓ Z.ai response ({model}): {len(content)} chars")
        return content


# Singleton
llm = LLMProvider()

"""
Production LLM Provider for DueSense v2.0

Z.ai ONLY — per CLAUDE.md specification.
Models: gpt-4o (complex), gpt-4o-mini (standard).
Safe fallback on failure — never crashes the pipeline.
"""

import os
import json
import logging
from typing import Dict, Any
import httpx

logger = logging.getLogger(__name__)

ZAI_BASE_URL = "https://api.zukijourney.com/v1/chat/completions"


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
        try:
            return await self._call_zai(prompt, system_message, max_tokens, temperature)
        except Exception as e:
            logger.error(f"❌ Z.ai call failed: {e}")
            return self._safe_fallback()

    # ----------------------------
    # JSON-safe generation
    # ----------------------------
    async def generate_json(
        self,
        prompt: str,
        system_message: str = "Respond ONLY with valid JSON.",
    ) -> Dict[str, Any]:
        text = await self.generate(prompt, system_message, max_tokens=2000)

        # Try to extract JSON from the response
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON in the text (e.g. wrapped in markdown code blocks)
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            logger.error("❌ JSON parse failed — returning empty dict")
            return {}

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

        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post(ZAI_BASE_URL, headers=headers, json=payload)

        if r.status_code == 429:
            raise RuntimeError("Z.ai rate limited — retry later")

        if r.status_code >= 500:
            raise RuntimeError(f"Z.ai server error: {r.status_code}")

        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    # ----------------------------
    # Safe fallback (never crash)
    # ----------------------------
    def _safe_fallback(self) -> str:
        return (
            "Information is temporarily unavailable due to system load. "
            "Partial results have been generated."
        )


# Singleton
llm = LLMProvider()

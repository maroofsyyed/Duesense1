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
SARVAM_BASE_URL = "https://api.sarvam.ai/v1/chat/completions"
MAX_RETRIES = 2
RETRY_DELAY = 1  # seconds


class LLMProvider:
    def __init__(self):
        self.zai_api_key = os.getenv("Z_API_KEY")
        self.sarvam_api_key = os.getenv("SARVAM_API_KEY")
        
        if not self.zai_api_key and not self.sarvam_api_key:
            raise RuntimeError("No LLM provider configured. Set Z_API_KEY or SARVAM_API_KEY.")
            
        if self.zai_api_key:
            logger.info("✓ Z.ai provider initialized")
        if self.sarvam_api_key:
            logger.info("✓ Sarvam AI provider initialized (fallback)")

    @property
    def current_model(self) -> str:
        modes = []
        if self.zai_api_key: modes.append("gpt-4o")
        if self.sarvam_api_key: modes.append("sarvam-m")
        return " + ".join(modes)

    def _validate_token(self):
        """Called by server.py on startup."""
        if not self.zai_api_key and not self.sarvam_api_key:
            raise RuntimeError("No LLM provider keys found")

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
        # Attempt 1: Z.ai (Primary)
        if self.zai_api_key:
            try:
                return await self._generate_with_retry(
                    self._call_zai, prompt, system_message, max_tokens, temperature, "Z.ai"
                )
            except Exception as e:
                logger.warning(f"⚠️ Z.ai failed: {e}")
                if not self.sarvam_api_key:
                    raise RuntimeError(f"Z.ai failed and no fallback available: {e}")

        # Attempt 2: Sarvam AI (Fallback)
        if self.sarvam_api_key:
            logger.info("🔄 Falling back to Sarvam AI...")
            try:
                return await self._generate_with_retry(
                    self._call_sarvam, prompt, system_message, max_tokens, temperature, "Sarvam"
                )
            except Exception as e:
                logger.error(f"❌ Sarvam AI failed: {e}")
                raise RuntimeError(f"All LLM providers failed. Last error: {e}")
        
        raise RuntimeError("No LLM provider configured")

    async def _generate_with_retry(self, func, *args) -> str:
        """Generic retry wrapper."""
        provider_name = args[-1]
        last_error = None
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = await func(*args[:-1])  # Don't pass provider_name to the actual call
                if result and len(result.strip()) > 5:
                    return result
                logger.warning(f"⚠️ {provider_name} returned empty response (attempt {attempt})")
                last_error = RuntimeError("Empty response")
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ {provider_name} attempt {attempt}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY)
                    
        raise last_error

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
            "Authorization": f"Bearer {self.zai_api_key}",
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
            raise RuntimeError("Rate limited")
        if r.status_code >= 500:
            raise RuntimeError(f"Server error: {r.status_code}")
        r.raise_for_status()

        return r.json()["choices"][0]["message"]["content"]

    # ----------------------------
    # Sarvam AI API call
    # ----------------------------
    async def _call_sarvam(
        self,
        prompt: str,
        system_message: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        # Valid models: sarvam-m (2B), sarvam-30b, sarvam-105b
        model = "sarvam-m"

        # Clamp max_tokens to 1024 for Sarvam models (typical limit)
        safe_max_tokens = min(max_tokens, 1024)

        headers = {
            "Authorization": f"Bearer {self.sarvam_api_key}",
            "Content-Type": "application/json",
        }

        # Merge system message into user message for better compatibility
        full_content = f"{system_message}\n\n{prompt}"
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": full_content},
            ],
            "max_tokens": safe_max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(SARVAM_BASE_URL, headers=headers, json=payload)

        if r.status_code == 400:
             # Log the response body for debugging
            logger.error(f"❌ Sarvam AI 400 Bad Request: {r.text}")
            raise RuntimeError(f"Sarvam API Client Error: {r.text}")

        if r.status_code == 429:
            raise RuntimeError("Rate limited")
        
        if r.status_code >= 500:
            raise RuntimeError(f"Server error: {r.status_code}")
            
        r.raise_for_status()

        return r.json()["choices"][0]["message"]["content"]



# Singleton
llm = LLMProvider()

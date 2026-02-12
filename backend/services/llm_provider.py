"""
Production-grade LLM Provider for DueSense
- Proactive load balancing (Groq / Z.ai)
- Circuit breaker on rate limits
- Safe fallbacks (never crash pipeline)
"""

import os
import json
import time
import random
import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

# ----------------------------
# Provider circuit state
# ----------------------------
PROVIDER_STATE = {
    "groq": {"failures": 0, "disabled_until": 0},
    "zai": {"failures": 0, "disabled_until": 0},
}

FAILURE_THRESHOLD = 3       # failures before cooldown
COOLDOWN_SECONDS = 60       # provider cooldown time


def provider_available(name: str) -> bool:
    return time.time() > PROVIDER_STATE[name]["disabled_until"]


def mark_failure(name: str):
    PROVIDER_STATE[name]["failures"] += 1
    if PROVIDER_STATE[name]["failures"] >= FAILURE_THRESHOLD:
        PROVIDER_STATE[name]["disabled_until"] = time.time() + COOLDOWN_SECONDS
        PROVIDER_STATE[name]["failures"] = 0
        logger.warning(f"🚫 Provider {name} disabled for {COOLDOWN_SECONDS}s")


# ----------------------------
# LLM Provider
# ----------------------------
class LLMProvider:
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.zai_key = os.getenv("Z_API_KEY")

        if not self.groq_key and not self.zai_key:
            raise RuntimeError("No LLM providers configured")

        logger.info("✓ LLM providers initialized (Groq / Z.ai)")

    # ----------------------------
    # Provider selection (60/40)
    # ----------------------------
    def _choose_provider(self) -> Optional[str]:
        candidates = []

        if self.groq_key and provider_available("groq"):
            candidates += ["groq"] * 6  # 60%
        if self.zai_key and provider_available("zai"):
            candidates += ["zai"] * 4   # 40%

        return random.choice(candidates) if candidates else None

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

        provider = self._choose_provider()

        if not provider:
            logger.error("❌ No LLM providers available")
            return self._safe_fallback()

        try:
            if provider == "groq":
                return await self._call_groq(
                    prompt, system_message, max_tokens, temperature
                )
            else:
                return await self._call_zai(
                    prompt, system_message, max_tokens, temperature
                )

        except Exception as e:
            logger.warning(f"⚠️ {provider} failed: {e}")
            mark_failure(provider)
            return self._safe_fallback()

    # ----------------------------
    # JSON-safe generation
    # ----------------------------
    async def generate_json(
        self,
        prompt: str,
        system_message: str = "Respond ONLY with valid JSON.",
    ) -> Dict[str, Any]:

        text = await self.generate(prompt, system_message)

        try:
            return json.loads(text)
        except Exception:
            logger.error("❌ JSON parse failed")
            return {}

    # ----------------------------
    # Groq (primary)
    # ----------------------------
    async def _call_groq(
        self,
        prompt: str,
        system_message: str,
        max_tokens: int,
        temperature: float,
    ) -> str:

        # Use small model unless explicitly large prompt
        model = (
            "llama-3.3-70b-versatile"
            if len(prompt) > 4000
            else "llama-3.1-8b-instant"
        )

        headers = {
            "Authorization": f"Bearer {self.groq_key}",
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

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
            )

        if r.status_code == 429:
            raise RuntimeError("Groq rate limited")

        if r.status_code >= 500:
            raise RuntimeError("Groq server error")

        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    # ----------------------------
    # Z.ai (secondary)
    # ----------------------------
    async def _call_zai(
        self,
        prompt: str,
        system_message: str,
        max_tokens: int,
        temperature: float,
    ) -> str:

        headers = {
            "Authorization": f"Bearer {self.zai_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.zukijourney.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )

        if r.status_code == 429:
            raise RuntimeError("Z.ai rate limited")

        if r.status_code >= 500:
            raise RuntimeError("Z.ai server error")

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

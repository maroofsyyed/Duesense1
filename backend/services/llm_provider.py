"""
LLM Provider for DueSense
Production-safe multi-provider LLM with graceful degradation.

Provider priority:
1. GROQ (primary)
2. Z.ai (secondary)

Design goals:
- Never crash production
- Never spam retries
- Never rely on unstable free HF models
- Always return deterministic output
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List

import httpx

logger = logging.getLogger(__name__)


class LLMProvider:
    def __init__(self):
        # Load API keys
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.z_api_key = os.getenv("Z_API_KEY")

        self.providers: List[Dict[str, Any]] = []

        # --- GROQ (PRIMARY) ---
        if self.groq_api_key:
            self.providers.append({
                "name": "groq",
                "type": "openai",
                "api_key": self.groq_api_key,
                "base_url": "https://api.groq.com/openai/v1",
                "model": "llama-3.3-70b-versatile",
                "fallback_models": ["llama-3.1-8b-instant"],
            })
            logger.info("✓ GROQ provider configured")

        # --- Z.AI (SECONDARY) ---
        if self.z_api_key:
            self.providers.append({
                "name": "z.ai",
                "type": "openai",
                "api_key": self.z_api_key,
                "base_url": "https://api.zukijourney.com/v1",
                "model": "gpt-4o-mini",
            })
            logger.info("✓ Z.ai provider configured")

        if not self.providers:
            logger.error("❌ No LLM providers configured")
            raise RuntimeError(
                "Set at least one of GROQ_API_KEY or Z_API_KEY"
            )

        self.current_provider = self.providers[0]
        self.current_model = self.current_provider["model"]

        logger.info(
            "✓ LLM configured with providers: %s",
            ", ".join(p["name"] for p in self.providers),
        )

    # ------------------------------------------------------------------
    # Backward compatibility (server.py expects this)
    # ------------------------------------------------------------------
    def _validate_token(self):
        return True

    # ------------------------------------------------------------------
    # TEXT GENERATION
    # ------------------------------------------------------------------
    async def generate(
        self,
        prompt: str,
        system_message: str = "You are a helpful assistant.",
        model: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
        timeout: float = 60.0,
    ) -> str:
        """
        Generate text with strict retry limits and graceful fallback.
        """
        last_error: Optional[Exception] = None
        attempts = 0
        MAX_ATTEMPTS = 2

        for provider in self.providers:
            models = [model or provider["model"]]
            models += provider.get("fallback_models", [])

            for m in models:
                attempts += 1
                if attempts > MAX_ATTEMPTS:
                    break

                try:
                    logger.info(f"🤖 LLM call via {provider['name']} ({m})")
                    result = await self._call_openai_compatible(
                        provider=provider,
                        model=m,
                        prompt=prompt,
                        system_message=system_message,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=timeout,
                    )

                    self.current_provider = provider
                    self.current_model = m
                    logger.info(f"✓ LLM response from {provider['name']} ({len(result)} chars)")
                    return result

                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"⚠️ {provider['name']} ({m}) failed: {type(e).__name__}: {str(e)[:200]}"
                    )
                    break  # move to next provider

        logger.error(f"❌ All LLM providers failed. Last error: {last_error}")
        return self._safe_text_fallback()

    # ------------------------------------------------------------------
    # OPENAI-COMPATIBLE CALL (Groq / Z.ai)
    # ------------------------------------------------------------------
    async def _call_openai_compatible(
        self,
        provider: Dict[str, Any],
        model: str,
        prompt: str,
        system_message: str,
        max_tokens: int,
        temperature: float,
        timeout: float,
    ) -> str:
        url = f"{provider['base_url']}/chat/completions"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        headers = {
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 429:
                raise RuntimeError("Rate limited")
            if response.status_code >= 500:
                raise RuntimeError("Provider server error")
            if response.status_code == 401:
                raise RuntimeError("Invalid API key")

            response.raise_for_status()
            data = response.json()

            try:
                return data["choices"][0]["message"]["content"]
            except Exception:
                raise RuntimeError("Malformed LLM response")

    # ------------------------------------------------------------------
    # JSON GENERATION (SAFE)
    # ------------------------------------------------------------------
    async def generate_json(
        self,
        prompt: str,
        system_message: str = "Respond with valid JSON only.",
        model: Optional[str] = None,
    ) -> dict:
        text = await self.generate(
            prompt=prompt,
            system_message=system_message,
            model=model,
        )

        try:
            return json.loads(self._extract_json(text))
        except Exception:
            logger.error("❌ JSON parse failed – returning safe defaults")
            return {
                "status": "partial",
                "reason": "llm_unavailable",
            }

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    def _extract_json(self, text: str) -> str:
        text = text.strip()

        if text.startswith("```"):
            text = text.strip("```").strip()

        start = text.find("{")
        end = text.rfind("}") + 1

        if start != -1 and end > start:
            return text[start:end]

        raise ValueError("No JSON object found")

    def _safe_text_fallback(self) -> str:
        return (
            "The analysis could not be fully completed due to temporary "
            "LLM unavailability. Partial results may be shown."
        )


# Global singleton
llm = LLMProvider()

"""
LLM Provider for DueSense
Production-safe multi-provider LLM with graceful fallback.

Provider priority:
1. GROQ (primary – fast, reliable)
2. Z.ai (secondary – unstable but useful)
3. HuggingFace Inference API (last-resort fallback)
"""

import os
import json
import asyncio
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# HARD concurrency limit to avoid rate-limit storms
LLM_SEMAPHORE = asyncio.Semaphore(2)


class LLMProvider:
    """
    Production-safe multi-provider LLM with automatic fallback.

    Guarantees:
    - No fatal crashes
    - No invalid HF models
    - Rate-limit safe
    - Deterministic provider order
    """

    def __init__(self):
        self.z_api_key = os.getenv("Z_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.hf_token = os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_TOKEN")

        self.providers = []

        # 1️⃣ GROQ (PRIMARY)
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

        # 2️⃣ Z.ai (SECONDARY)
        if self.z_api_key:
            self.providers.append({
                "name": "z.ai",
                "type": "openai",
                "api_key": self.z_api_key,
                "base_url": "https://api.zukijourney.com/v1",
                "model": "gpt-4o-mini",
            })
            logger.info("✓ Z.ai provider configured")

        # 3️⃣ HuggingFace (LAST RESORT – SAFE MODELS ONLY)
        if self.hf_token:
            self.providers.append({
                "name": "huggingface",
                "type": "huggingface",
                "api_key": self.hf_token,
                "base_url": "https://api-inference.huggingface.co/models",
                "model": "google/flan-t5-xl",
                "fallback_models": ["google/flan-t5-large"],
            })
            logger.info("✓ HuggingFace provider configured")

        if not self.providers:
            raise RuntimeError(
                "No LLM providers configured. Set GROQ_API_KEY, Z_API_KEY, or HUGGINGFACE_API_KEY."
            )

        self.current_provider = self.providers[0]
        self.current_model = self.current_provider["model"]

        logger.info(
            f"✓ LLM configured with providers: {', '.join(p['name'] for p in self.providers)}"
        )

    # ------------------------------------------------------------------
    # PUBLIC API
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
        Generate text with automatic fallback.
        NEVER throws fatal errors in production.
        """

        last_error = None

        for provider in self.providers:
            models = [model or provider["model"]]
            models += provider.get("fallback_models", [])

            for m in models:
                try:
                    async with LLM_SEMAPHORE:
                        logger.info(f"🤖 LLM call via {provider['name']} ({m})")

                        if provider["type"] == "openai":
                            result = await self._call_openai(
                                provider, prompt, system_message, m,
                                max_tokens, temperature, timeout
                            )
                        else:
                            result = await self._call_huggingface(
                                provider, prompt, system_message, m,
                                max_tokens, temperature, timeout
                            )

                    if result:
                        self.current_provider = provider
                        self.current_model = m
                        logger.info(f"✓ LLM response from {provider['name']} ({len(result)} chars)")
                        return result

                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"⚠️ {provider['name']} ({m}) failed: {type(e).__name__}: {str(e)[:120]}"
                    )
                    # model-specific failure → try next model
                    if "model" in str(e).lower() or "404" in str(e):
                        continue
                    # provider-level failure → move to next provider
                    break

        logger.error(f"❌ All LLM providers failed. Last error: {last_error}")
        return "LLM temporarily unavailable. Proceeding with partial analysis."

    async def generate_json(
        self,
        prompt: str,
        system_message: str = "Return ONLY valid JSON.",
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate JSON safely with repair logic.
        """

        system_message += (
            "\n\nRULES:\n"
            "- JSON only\n"
            "- Use null for missing values\n"
            "- No markdown\n"
            "- No trailing commas"
        )

        text = await self.generate(prompt, system_message, model)

        try:
            return json.loads(self._repair_json(text))
        except Exception:
            logger.error("❌ JSON parse failed")
            return {}

    # ------------------------------------------------------------------
    # PROVIDER IMPLEMENTATIONS
    # ------------------------------------------------------------------

    async def _call_openai(
        self,
        provider: Dict[str, Any],
        prompt: str,
        system_message: str,
        model: str,
        max_tokens: int,
        temperature: float,
        timeout: float,
    ) -> str:
        import httpx

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

        url = f"{provider['base_url']}/chat/completions"

        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, headers=headers, json=payload)

            if r.status_code == 429:
                raise RuntimeError("Rate limited")
            if r.status_code >= 500:
                raise RuntimeError("Provider server error")

            r.raise_for_status()
            data = r.json()

            return data["choices"][0]["message"]["content"]

    async def _call_huggingface(
        self,
        provider: Dict[str, Any],
        prompt: str,
        system_message: str,
        model: str,
        max_tokens: int,
        temperature: float,
        timeout: float,
    ) -> str:
        import httpx

        full_prompt = f"{system_message}\n\nUser: {prompt}\n\nAssistant:"

        payload = {
            "inputs": full_prompt,
            "parameters": {
                "max_new_tokens": min(max_tokens, 1024),
                "temperature": temperature,
                "return_full_text": False,
            },
        }

        headers = {
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json",
        }

        url = f"{provider['base_url']}/{model}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, headers=headers, json=payload)

            if r.status_code in (404, 410):
                raise RuntimeError("Model not available")
            if r.status_code == 429:
                raise RuntimeError("HF rate limited")
            if r.status_code >= 500:
                raise RuntimeError("HF server error")

            r.raise_for_status()
            data = r.json()

            if isinstance(data, list) and "generated_text" in data[0]:
                return data[0]["generated_text"]

            raise RuntimeError("Invalid HF response")

    # ------------------------------------------------------------------
    # JSON REPAIR
    # ------------------------------------------------------------------

    def _repair_json(self, text: str) -> str:
        import re

        text = text.strip()
        text = re.sub(r",\s*([}\]])", r"\1", text)
        text = re.sub(r":\s*None", ": null", text)
        text = re.sub(r":\s*True", ": true", text)
        text = re.sub(r":\s*False", ": false", text)

        return text


# Global singleton
llm = LLMProvider()

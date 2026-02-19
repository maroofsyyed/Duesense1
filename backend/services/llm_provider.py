import os
import json
import re
import logging
import asyncio
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

# ---- API Endpoints ----
ZAI_API_URL = "https://api.z.ai/api/paas/v4/chat/completions"
SARVAM_API_URL = "https://api.sarvam.ai/v1/chat/completions"

MAX_RETRIES = 2
RETRY_DELAY = 1  # seconds


class LLMProvider:
    def __init__(self):
        self.zai_api_key = os.getenv("Z_API_KEY") or os.getenv("ZAI_API_KEY")
        self.sarvam_api_key = os.getenv("SARVAM_API_KEY")

        if not self.zai_api_key and not self.sarvam_api_key:
            raise RuntimeError("No API keys configured for Z.ai or Sarvam AI.")

        logger.info("LLMProvider initialized with providers: %s", self.current_providers)

    @property
    def current_providers(self) -> str:
        return ", ".join(k for k in ["Z.ai" if self.zai_api_key else "", "Sarvam AI" if self.sarvam_api_key else ""] if k)
    
    @property
    def current_model(self) -> str:
        # Backward compatibility for server.py which accesses llm.current_model
        return self.current_providers

    def _validate_token(self):
        # Backward compatibility for server.py startup check
        if not self.zai_api_key and not self.sarvam_api_key:
            raise RuntimeError("No LLM provider keys found")

    def _select_model(self, prompt: str) -> str:
        return "gpt-4o" if len(prompt) > 6000 else "gpt-4o-mini"

    async def generate(
        self,
        prompt: str,
        system_message: str = "You are a helpful assistant.",
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> str:
        if self.zai_api_key:
            try:
                return await self._retry_call(
                    self._call_zai, prompt, system_message, max_tokens, temperature
                )
            except Exception as e:
                logger.warning(f"Z.ai error: {e}")
                if not self.sarvam_api_key:
                    raise RuntimeError(f"Z.ai failed; no fallback available. Error: {e}")

        if self.sarvam_api_key:
            logger.info("Falling back to Sarvam AI...")
            return await self._retry_call(
                self._call_sarvam, prompt, system_message, max_tokens, temperature
            )

        raise RuntimeError("No LLM available.")

    async def generate_json(
        self,
        prompt: str,
        system_message: str = "Respond ONLY with valid JSON.",
        max_tokens: int = 4000,
    ) -> Dict[str, Any]:
        raw = await self.generate(prompt, system_message, max_tokens=max_tokens)

        # Step 1: Direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Step 2: Strip markdown code fences
        stripped = re.sub(r"```(?:json)?\s*", "", raw)
        stripped = re.sub(r"```\s*$", "", stripped).strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        # Step 3: Repair common LLM JSON errors then parse
        repaired = self._repair_json(stripped)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # Step 4: Extract outermost {...} using balanced-brace counting
        extracted = self._extract_largest_json(raw)
        if extracted:
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                # Try repair on extracted text too
                try:
                    return json.loads(self._repair_json(extracted))
                except json.JSONDecodeError:
                    pass

        logger.error("JSON parse error after all recovery attempts, raw output: %s", raw[:500])
        raise RuntimeError("Received invalid JSON from LLM")

    @staticmethod
    def _repair_json(text: str) -> str:
        """Fix common LLM JSON errors: trailing commas, single quotes, Python booleans."""
        # Python True/False/None → JSON true/false/null
        text = re.sub(r'\bTrue\b', 'true', text)
        text = re.sub(r'\bFalse\b', 'false', text)
        text = re.sub(r'\bNone\b', 'null', text)
        # Trailing commas before } or ]
        text = re.sub(r',\s*([}\]])', r'\1', text)
        # Single quotes → double quotes (only around keys/values, not inside strings)
        # Simple approach: replace single-quoted strings
        text = re.sub(r"'([^']*?)'", r'"\1"', text)
        return text

    @staticmethod
    def _extract_largest_json(text: str) -> str | None:
        """Extract the outermost {...} block using brace-depth counting."""
        start = text.find('{')
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == '\\':
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        # Unbalanced — return from start to last } as best effort
        last_brace = text.rfind('}')
        if last_brace > start:
            return text[start:last_brace + 1]
        return None

    async def _retry_call(self, func, *args):
        last_err = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                text = await func(*args)
                if text and text.strip():
                    return text
            except Exception as e:
                last_err = e
                logger.warning(f"Attempt {attempt}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY)
        raise last_err

    async def _call_zai(
        self,
        prompt: str,
        system_message: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        model = self._select_model(prompt)
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
            "Authorization": f"Bearer {self.zai_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(ZAI_API_URL, json=payload, headers=headers)

        if resp.status_code >= 400:
            raise RuntimeError(f"Z.ai returned {resp.status_code}: {resp.text}")

        return resp.json()["choices"][0]["message"]["content"]

    async def _call_sarvam(
        self,
        prompt: str,
        system_message: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        payload = {
            "model": "sarvam-m",
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": min(max_tokens, 4096),
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.sarvam_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(SARVAM_API_URL, headers=headers, json=payload)

        if resp.status_code >= 400:
            logger.error("Sarvam API error (%s): %s", resp.status_code, resp.text)
            raise RuntimeError(f"Sarvam returned {resp.status_code}: {resp.text}")

        return resp.json()["choices"][0]["message"]["content"]


# Singleton instance
llm = LLMProvider()

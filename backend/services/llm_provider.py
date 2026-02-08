import os
import json
import asyncio
from dotenv import load_dotenv

load_dotenv()


class LLMProvider:
    """Abstraction layer for LLM providers - swap between Emergent, Ollama, and Groq."""

    def __init__(self, provider="emergent"):
        self.provider = provider
        self.api_key = os.environ.get("EMERGENT_LLM_KEY")
        self.ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.groq_api_key = os.environ.get("GROQ_API_KEY")

    async def generate(self, prompt: str, system_message: str = "You are a helpful assistant.", model: str = "gpt-4o") -> str:
        if self.provider == "emergent":
            return await self._call_emergent(prompt, system_message, model)
        elif self.provider == "ollama":
            return await self._call_ollama(prompt, system_message, model)
        elif self.provider == "groq":
            return await self._call_groq(prompt, system_message, model)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def generate_json(self, prompt: str, system_message: str = "You are a helpful assistant. Always respond with valid JSON only.", model: str = "gpt-4o") -> dict:
        response = await self.generate(prompt, system_message, model)
        # Clean JSON from response
        text = response.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
            raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}")

    async def _call_emergent(self, prompt: str, system_message: str, model: str) -> str:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import uuid

        chat = LlmChat(
            api_key=self.api_key,
            session_id=str(uuid.uuid4()),
            system_message=system_message,
        )
        chat.with_model("openai", model)

        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        return response

    async def _call_ollama(self, prompt: str, system_message: str, model: str) -> str:
        import httpx
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model,
                    "system": system_message,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 4000},
                },
            )
            response.raise_for_status()
            return response.json()["response"]


# Singleton instance
llm = LLMProvider(provider="emergent")

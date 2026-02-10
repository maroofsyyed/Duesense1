"""
LLM Provider for DueSense
Uses HuggingFace Inference API with open-source models.

Supported models (in order of recommendation):
- meta-llama/Meta-Llama-3.1-70B-Instruct (best quality, may have rate limits)
- mistralai/Mixtral-8x7B-Instruct-v0.1 (fast, good quality)
- meta-llama/Meta-Llama-3.1-8B-Instruct (faster, lighter)
- HuggingFaceH4/zephyr-7b-beta (lightweight fallback)
"""
import os
import json
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Default model - Llama 3.1 70B is best for structured output
DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-70B-Instruct"
# Fallback models in order of preference
FALLBACK_MODELS = [
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "HuggingFaceH4/zephyr-7b-beta",
]


class LLMProvider:
    """
    LLM provider using HuggingFace Inference API (open-source models).
    
    Supports automatic fallback to alternative models on rate limits or errors.
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        self.hf_token = os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN")
        self.model = model
        self._validated = False
        
    def _validate_token(self):
        """Validate HuggingFace token exists (lazy validation)."""
        if self._validated:
            return
        if not self.hf_token:
            raise ValueError(
                "HuggingFace API key not configured. "
                "Set HUGGINGFACE_API_KEY or HF_TOKEN environment variable."
            )
        self._validated = True
        logger.info(f"✓ HuggingFace API key configured: {self.hf_token[:8]}...")

    async def generate(
        self, 
        prompt: str, 
        system_message: str = "You are a helpful assistant.", 
        model: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.1
    ) -> str:
        """
        Generate text using HuggingFace Inference API.
        
        Args:
            prompt: User prompt
            system_message: System instructions
            model: Model to use (defaults to self.model)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)
            
        Returns:
            Generated text response
        """
        self._validate_token()
        use_model = model or self.model
        
        # Try primary model, then fallbacks
        models_to_try = [use_model] + [m for m in FALLBACK_MODELS if m != use_model]
        last_error = None
        
        for attempt_model in models_to_try:
            try:
                return await self._call_huggingface(
                    prompt=prompt,
                    system_message=system_message,
                    model=attempt_model,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
            except Exception as e:
                error_str = str(e).lower()
                # Check if it's a rate limit or model unavailable error
                if "rate" in error_str or "429" in error_str or "503" in error_str or "unavailable" in error_str:
                    logger.warning(f"Model {attempt_model} unavailable, trying fallback: {e}")
                    last_error = e
                    continue
                else:
                    # For other errors, don't try fallbacks
                    raise
        
        # All models failed
        raise RuntimeError(f"All models failed. Last error: {last_error}")

    async def _call_huggingface(
        self,
        prompt: str,
        system_message: str,
        model: str,
        max_tokens: int,
        temperature: float
    ) -> str:
        """Call HuggingFace Inference API."""
        import httpx
        
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        # HuggingFace Inference API endpoint
        url = f"https://api-inference.huggingface.co/models/{model}/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.hf_token}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            logger.debug(f"Calling HuggingFace API with model: {model}")
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code == 429:
                raise RuntimeError(f"Rate limited on model {model}")
            if response.status_code == 503:
                raise RuntimeError(f"Model {model} is currently loading or unavailable")
            
            response.raise_for_status()
            result = response.json()
            
            # Extract content from response
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            elif "generated_text" in result:
                return result["generated_text"]
            else:
                raise ValueError(f"Unexpected response format from HuggingFace: {result}")

    async def generate_json(
        self, 
        prompt: str, 
        system_message: str = "You are a helpful assistant. Always respond with valid JSON only.",
        model: Optional[str] = None
    ) -> dict:
        """
        Generate JSON response using HuggingFace.
        
        Automatically cleans markdown code blocks and extracts JSON.
        """
        response = await self.generate(prompt, system_message, model)
        
        # Clean JSON from response (handle markdown code blocks)
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
            # Try to find JSON object in the response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            
            # Try to find JSON array
            start = text.find("[")
            end = text.rfind("]") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            
            raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}...")


# Singleton instance - uses HuggingFace with Llama 3.1 70B
llm = LLMProvider(model=DEFAULT_MODEL)

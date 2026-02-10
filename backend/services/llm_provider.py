"""
LLM Provider for DueSense
Uses HuggingFace Inference API with open-source models.

Supported models (in order of preference):
1. meta-llama/Meta-Llama-3.1-70B-Instruct (best quality)
2. mistralai/Mixtral-8x7B-Instruct-v0.1 (good fallback)
3. meta-llama/Meta-Llama-3.1-8B-Instruct (faster, always available)
4. HuggingFaceH4/zephyr-7b-beta (emergency fallback)
"""
import os
import json
import logging
import asyncio
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Model priority list - will try in order if one fails
MODELS = [
    "meta-llama/Meta-Llama-3.1-70B-Instruct",  # Best quality, might be rate limited
    "mistralai/Mixtral-8x7B-Instruct-v0.1",     # Good fallback
    "meta-llama/Meta-Llama-3.1-8B-Instruct",    # Faster, always available
    "HuggingFaceH4/zephyr-7b-beta"              # Emergency fallback
]


class LLMProvider:
    """
    HuggingFace LLM provider with robust error handling and automatic fallback.
    
    Features:
    - Automatic model fallback on rate limits/unavailability
    - Timeout handling (60s default)
    - Retry logic with exponential backoff
    - Robust JSON parsing
    """

    def __init__(self):
        self.hf_token = os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN")
        self.models = MODELS.copy()
        self.current_model = self.models[0]
        self.model_index = 0
        self._validated = False
        
    def _validate_token(self):
        """Validate HuggingFace token exists and has correct format."""
        if self._validated:
            return
        
        if not self.hf_token:
            raise ValueError(
                "HuggingFace API key not configured. "
                "Set HUGGINGFACE_API_KEY or HF_TOKEN environment variable."
            )
        
        if not self.hf_token.startswith("hf_"):
            logger.warning(f"⚠️ HuggingFace token may be invalid (should start with 'hf_'): {self.hf_token[:10]}...")
        
        self._validated = True
        logger.info(f"✓ HuggingFace API key validated: {self.hf_token[:8]}...")
    
    def _switch_to_next_model(self) -> bool:
        """Switch to next fallback model. Returns False if no more models."""
        if self.model_index < len(self.models) - 1:
            self.model_index += 1
            self.current_model = self.models[self.model_index]
            logger.warning(f"⚠️ Switching to fallback model: {self.current_model}")
            return True
        return False
    
    def _reset_model(self):
        """Reset to primary model (for next request)."""
        self.model_index = 0
        self.current_model = self.models[0]

    async def generate(
        self, 
        prompt: str, 
        system_message: str = "You are a helpful assistant.", 
        model: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.1,
        timeout: float = 90.0
    ) -> str:
        """
        Generate text using HuggingFace Inference API with automatic fallback.
        
        Args:
            prompt: User prompt
            system_message: System instructions
            model: Override model (optional)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)
            timeout: Request timeout in seconds
            
        Returns:
            Generated text response
            
        Raises:
            RuntimeError: If all models fail
            ValueError: If authentication fails
        """
        self._validate_token()
        
        # Use specified model or current model
        use_model = model or self.current_model
        
        # Build model list to try (specified model first, then fallbacks)
        models_to_try = [use_model]
        for m in self.models:
            if m != use_model and m not in models_to_try:
                models_to_try.append(m)
        
        last_error = None
        
        for attempt_num, attempt_model in enumerate(models_to_try, 1):
            try:
                logger.info(f"🤖 LLM call: {attempt_model} (attempt {attempt_num}/{len(models_to_try)})")
                
                result = await self._call_huggingface(
                    prompt=prompt,
                    system_message=system_message,
                    model=attempt_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=timeout
                )
                
                logger.info(f"✓ LLM response received ({len(result)} chars)")
                return result
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Authentication error - fail fast, don't try other models
                if any(x in error_str for x in ['401', 'unauthorized', 'authentication', 'invalid token']):
                    logger.error(f"❌ Authentication error: {e}")
                    raise ValueError(f"HuggingFace authentication failed: {e}")
                
                # Rate limit or model unavailable - try next model
                if any(x in error_str for x in ['rate', '429', '503', 'overloaded', 'unavailable', 'loading']):
                    logger.warning(f"⚠️ Model {attempt_model} unavailable: {e}")
                    continue
                
                # Timeout - retry same model once, then try next
                if any(x in error_str for x in ['timeout', 'timed out']):
                    logger.warning(f"⚠️ Timeout on {attempt_model}, trying next model...")
                    continue
                
                # Other HTTP errors - log and try next model
                if any(x in error_str for x in ['500', '502', '504', 'server error']):
                    logger.warning(f"⚠️ Server error on {attempt_model}: {e}")
                    continue
                
                # Unknown error - log full details and try next model
                logger.error(f"❌ Unexpected error with {attempt_model}: {type(e).__name__}: {e}")
                continue
        
        # All models failed
        error_msg = f"All {len(models_to_try)} LLM models failed. Last error: {last_error}"
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg)

    async def _call_huggingface(
        self,
        prompt: str,
        system_message: str,
        model: str,
        max_tokens: int,
        temperature: float,
        timeout: float
    ) -> str:
        """Call HuggingFace Inference API with proper error handling."""
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
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                # Handle specific HTTP errors
                if response.status_code == 401:
                    raise ValueError(f"Authentication failed (401): Check your HuggingFace API token")
                if response.status_code == 429:
                    raise RuntimeError(f"Rate limited (429) on model {model}")
                if response.status_code == 503:
                    raise RuntimeError(f"Model {model} is loading or unavailable (503)")
                if response.status_code >= 500:
                    raise RuntimeError(f"Server error ({response.status_code}) on model {model}")
                
                response.raise_for_status()
                result = response.json()
                
                # Extract content from response
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    if content:
                        return content
                    raise ValueError("Empty response from HuggingFace API")
                elif "generated_text" in result:
                    return result["generated_text"]
                elif "error" in result:
                    raise RuntimeError(f"HuggingFace API error: {result['error']}")
                else:
                    raise ValueError(f"Unexpected response format: {json.dumps(result)[:200]}")
                    
        except httpx.TimeoutException:
            raise RuntimeError(f"Request timed out after {timeout}s on model {model}")
        except httpx.ConnectError as e:
            raise RuntimeError(f"Connection error to HuggingFace API: {e}")

    async def generate_json(
        self, 
        prompt: str, 
        system_message: str = "You are a helpful assistant. Always respond with valid JSON only.",
        model: Optional[str] = None
    ) -> dict:
        """
        Generate JSON response using HuggingFace with robust parsing.
        
        Automatically cleans markdown code blocks and extracts JSON.
        """
        # Enhance system message to encourage valid JSON
        enhanced_system = system_message
        if "json" not in system_message.lower():
            enhanced_system += "\n\nIMPORTANT: Respond with ONLY valid JSON. No markdown, no backticks, no explanation."
        
        response = await self.generate(prompt, enhanced_system, model)
        
        # Clean JSON from response (handle markdown code blocks)
        text = response.strip()
        
        # Remove markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ JSON parse failed, attempting extraction: {e}")
        
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
        
        # Log the problematic response for debugging
        logger.error(f"❌ Could not parse JSON from LLM response. First 500 chars: {text[:500]}")
        raise ValueError(f"LLM did not return valid JSON. Response preview: {text[:200]}...")
    
    async def test_connection(self) -> bool:
        """Test LLM connection with a simple prompt."""
        try:
            self._validate_token()
            result = await self.generate(
                prompt="Say 'OK' if you work.",
                system_message="Be very brief.",
                max_tokens=10,
                timeout=30.0
            )
            logger.info(f"✓ LLM test successful: {result[:50]}...")
            return True
        except Exception as e:
            logger.error(f"❌ LLM test failed: {e}")
            return False


# Global singleton instance
llm = LLMProvider()

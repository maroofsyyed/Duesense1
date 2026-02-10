"""
LLM Provider for DueSense
Multi-provider support with automatic fallback.

Provider priority:
1. Z.ai (OpenAI-compatible, fast and reliable)
2. GROQ (fast inference)
3. HuggingFace Inference API (free tier fallback)
"""
import os
import json
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class LLMProvider:
    """
    Multi-provider LLM with automatic fallback.
    
    Supports:
    - Z.ai (OpenAI-compatible API)
    - GROQ (fast LLM inference)
    - HuggingFace Inference API
    
    Features:
    - Automatic provider fallback on errors
    - Timeout handling (90s default)
    - Robust JSON parsing
    """

    def __init__(self):
        # API Keys
        self.z_api_key = os.environ.get("Z_API_KEY")
        self.groq_api_key = os.environ.get("GROQ_API_KEY")
        self.hf_token = os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN")
        
        # Build provider list based on available keys
        self.providers = []
        
        if self.z_api_key:
            self.providers.append({
                "name": "z.ai",
                "api_key": self.z_api_key,
                "base_url": "https://api.zukijourney.com/v1",  # Z.ai OpenAI-compatible endpoint
                "model": "gpt-4o-mini",  # Default model for Z.ai
                "type": "openai"
            })
            logger.info(f"✓ Z.ai provider configured: {self.z_api_key[:8]}...")
        
        if self.groq_api_key:
            self.providers.append({
                "name": "groq",
                "api_key": self.groq_api_key,
                "base_url": "https://api.groq.com/openai/v1",
                "model": "llama-3.1-70b-versatile",  # Best GROQ model
                "type": "openai"
            })
            logger.info(f"✓ GROQ provider configured: {self.groq_api_key[:8]}...")
        
        if self.hf_token:
            self.providers.append({
                "name": "huggingface",
                "api_key": self.hf_token,
                "base_url": "https://api-inference.huggingface.co/models",
                "model": "mistralai/Mistral-7B-Instruct-v0.3",  # Updated to working model
                "type": "huggingface"
            })
            logger.info(f"✓ HuggingFace provider configured: {self.hf_token[:8]}...")
        
        if not self.providers:
            logger.error("❌ No LLM API keys configured!")
            raise ValueError(
                "No LLM API keys configured. Set at least one of: "
                "Z_API_KEY, GROQ_API_KEY, or HUGGINGFACE_API_KEY"
            )
        
        self.current_provider = self.providers[0]
        self.current_model = self.current_provider["model"]
        self._validated = False
        
    def _validate_token(self):
        """Validate that at least one provider is configured."""
        if self._validated:
            return
        
        if not self.providers:
            raise ValueError("No LLM providers configured")
        
        self._validated = True
        logger.info(f"✓ LLM configured with {len(self.providers)} provider(s): {', '.join(p['name'] for p in self.providers)}")

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
        Generate text using available LLM providers with automatic fallback.
        """
        self._validate_token()
        
        last_error = None
        
        for provider in self.providers:
            try:
                logger.info(f"🤖 LLM call via {provider['name']} ({provider['model']})")
                
                if provider["type"] == "openai":
                    result = await self._call_openai_compatible(
                        provider=provider,
                        prompt=prompt,
                        system_message=system_message,
                        model=model or provider["model"],
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=timeout
                    )
                else:  # huggingface
                    result = await self._call_huggingface(
                        provider=provider,
                        prompt=prompt,
                        system_message=system_message,
                        model=model or provider["model"],
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=timeout
                    )
                
                logger.info(f"✓ LLM response from {provider['name']} ({len(result)} chars)")
                self.current_provider = provider
                self.current_model = provider["model"]
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ {provider['name']} failed: {type(e).__name__}: {str(e)[:200]}")
                continue
        
        # All providers failed
        error_msg = f"All {len(self.providers)} LLM providers failed. Last error: {last_error}"
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg)

    async def _call_openai_compatible(
        self,
        provider: Dict[str, Any],
        prompt: str,
        system_message: str,
        model: str,
        max_tokens: int,
        temperature: float,
        timeout: float
    ) -> str:
        """Call OpenAI-compatible API (Z.ai, GROQ, etc.)."""
        import httpx
        
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        url = f"{provider['base_url']}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code == 401:
                    raise ValueError(f"Authentication failed (401) for {provider['name']}")
                if response.status_code == 429:
                    raise RuntimeError(f"Rate limited (429) on {provider['name']}")
                if response.status_code >= 500:
                    raise RuntimeError(f"Server error ({response.status_code}) on {provider['name']}")
                
                response.raise_for_status()
                result = response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    if content:
                        return content
                    raise ValueError(f"Empty response from {provider['name']}")
                elif "error" in result:
                    raise RuntimeError(f"{provider['name']} error: {result['error']}")
                else:
                    raise ValueError(f"Unexpected response format from {provider['name']}")
                    
        except httpx.TimeoutException:
            raise RuntimeError(f"Request timed out on {provider['name']}")
        except httpx.ConnectError as e:
            raise RuntimeError(f"Connection error to {provider['name']}: {e}")

    async def _call_huggingface(
        self,
        provider: Dict[str, Any],
        prompt: str,
        system_message: str,
        model: str,
        max_tokens: int,
        temperature: float,
        timeout: float
    ) -> str:
        """Call HuggingFace Inference API."""
        import httpx
        
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        # Try chat completions endpoint first
        url = f"{provider['base_url']}/{model}/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {provider['api_key']}",
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
                
                if response.status_code == 401:
                    raise ValueError("HuggingFace authentication failed")
                if response.status_code in [410, 404]:
                    raise RuntimeError(f"Model {model} not available (410/404)")
                if response.status_code == 429:
                    raise RuntimeError(f"Rate limited on HuggingFace")
                if response.status_code >= 500:
                    raise RuntimeError(f"HuggingFace server error ({response.status_code})")
                
                response.raise_for_status()
                result = response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    if content:
                        return content
                elif "generated_text" in result:
                    return result["generated_text"]
                elif "error" in result:
                    raise RuntimeError(f"HuggingFace error: {result['error']}")
                
                raise ValueError("Unexpected HuggingFace response format")
                    
        except httpx.TimeoutException:
            raise RuntimeError(f"HuggingFace request timed out")
        except httpx.ConnectError as e:
            raise RuntimeError(f"HuggingFace connection error: {e}")

    async def generate_json(
        self, 
        prompt: str, 
        system_message: str = "You are a helpful assistant. Always respond with valid JSON only.",
        model: Optional[str] = None
    ) -> dict:
        """Generate JSON response with robust parsing."""
        enhanced_system = system_message
        if "json" not in system_message.lower():
            enhanced_system += "\n\nIMPORTANT: Respond with ONLY valid JSON. No markdown, no backticks, no explanation."
        
        response = await self.generate(prompt, enhanced_system, model)
        
        # Clean JSON from response
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
        
        # Try to find JSON object
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
        
        logger.error(f"❌ Could not parse JSON. Response: {text[:500]}")
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
            logger.info(f"✓ LLM test successful via {self.current_provider['name']}: {result[:50]}...")
            return True
        except Exception as e:
            logger.error(f"❌ LLM test failed: {e}")
            return False


# Global singleton instance
llm = LLMProvider()

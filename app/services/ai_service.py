import requests
import time
from typing import Dict, Any, Optional, List
from app.core.config import settings
from app.models.schemas import Question

class AIService:
    def __init__(self):
        self.providers = {
            "openrouter": {
                "api_key": settings.OPENROUTER_API_KEY,
                "endpoint": "https://openrouter.ai/api/v1/chat/completions"
            },
            "openai": {
                "api_key": settings.OPENAI_API_KEY,
                "endpoint": "https://api.openai.com/v1/chat/completions"
            },
            "anthropic": {
                "api_key": settings.ANTHROPIC_API_KEY,
                "endpoint": "https://api.anthropic.com/v1/messages"
            }
        }
    
    def _get_provider_from_model(self, model: str) -> str:
        """Determine provider based on model name
        
        Supports:
        - Direct models: "gpt-3.5-turbo", "claude-3-sonnet", etc.
        - OpenRouter format: "openai/gpt-3.5-turbo", "anthropic/claude-3", etc.
        """
        model_lower = model.lower()
        
        # Check for OpenRouter format (provider/model)
        if "/" in model:
            prefix = model_lower.split("/")[0]
            if prefix in ["openai", "anthropic", "meta-llama", "mistral", "neural-chat", "nous", "teknium", "openrouter"]:
                return "openrouter"
        
        # Check direct model names
        if "gpt" in model_lower:
            return "openai"
        elif "claude" in model_lower:
            return "anthropic"
        else:
            return "openrouter"
    
    def _resolve_provider(self, model: str) -> Optional[str]:
        """Choose a provider that has a configured API key"""
        provider = self._get_provider_from_model(model)
        api_key = self.providers.get(provider, {}).get("api_key")

        if api_key:
            return provider

        # Fallback order - prioritize providers with configured keys
        fallback_order = ["openrouter", "openai", "anthropic"]

        for fallback in fallback_order:
            if self.providers.get(fallback, {}).get("api_key"):
                return fallback

        return None

    def _prepare_headers(self, provider: str) -> Dict[str, str]:
        """Prepare headers for API request"""
        headers = {
            "Content-Type": "application/json"
        }
        
        if provider == "openrouter":
            headers["Authorization"] = f"Bearer {self.providers['openrouter']['api_key']}"
            headers["HTTP-Referer"] = "http://localhost"
            headers["X-Title"] = "Chatbot Backend"
        elif provider == "openai":
            headers["Authorization"] = f"Bearer {self.providers['openai']['api_key']}"
        elif provider == "anthropic":
            headers["x-api-key"] = self.providers['anthropic']['api_key']
            headers["anthropic-version"] = "2023-06-01"
            
        return headers
    
    def _prepare_payload(self, provider: str, model: str, messages: List[Dict[str, str]], max_tokens: int = 1500, temperature: float = 0.3) -> Dict[str, Any]:
        """Prepare payload for API request"""
        if provider == "anthropic":
            return {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
        else:
            return {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
    
    def generate_response(self, question: Question, context: str = "", persona_prompt: str = "") -> Dict[str, Any]:
        """Generate response using the specified model with retry logic for rate limiting"""
        provider = self._resolve_provider(question.model)
        if not provider:
            return {
                "answer": "Error generating response: No valid AI provider configured. Please set an API key for OpenRouter, OpenAI, or Anthropic.",
                "tokens_used": 0
            }

        # 1. Prepare the system message with the persona
        system_message = persona_prompt or "Anda adalah asisten virtual dari emasjid.id. Jawab pertanyaan berikut dengan jelas dan akurat."

        # 2. Prepare the user message, including context if available
        if context:
            user_message = f"""
            Berdasarkan KONTEKS berikut, jawab pertanyaan user.
            Jika jawaban tidak ada di dalam konteks, katakan dengan jujur bahwa informasi tidak ditemukan.
            Jangan menambah fakta dari luar konteks.

            KONTEKS:
            {context}

            PERTANYAAN: {question.question}
            """
        else:
            user_message = question.question

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

        headers = self._prepare_headers(provider)
        payload = self._prepare_payload(provider, question.model, messages)
        
        # Retry logic with exponential backoff
        max_retries = 3
        retry_delay = 1  # Start with 1 second delay
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.providers[provider]["endpoint"],
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                # Handle rate limiting (429 Too Many Requests)
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            retry_delay = int(retry_after)
                        except ValueError:
                            pass
                    
                    if attempt < max_retries - 1:
                        print(f"Rate limited (429). Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        return {
                            "answer": f"API rate limit exceeded. Please try again later. (429 Too Many Requests)",
                            "tokens_used": 0
                        }
                
                response.raise_for_status()
                resp_json = response.json()
                
                if provider == "anthropic":
                    content = resp_json.get("content", [{}])[0].get("text", "")
                    return {
                        "answer": content,
                        "tokens_used": resp_json.get("usage", {}).get("total_tokens", 0)
                    }
                else:
                    content = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "")
                    usage = resp_json.get("usage", {})
                    tokens_used = usage.get("total_tokens", 0) or (
                        usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
                    )
                    return {
                        "answer": content,
                        "tokens_used": tokens_used
                    }
                    
            except requests.exceptions.RequestException as e:
                error_msg = str(e)
                if "429" in error_msg and attempt < max_retries - 1:
                    print(f"Rate limited. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return {
                    "answer": f"Error generating response: {error_msg}",
                    "tokens_used": 0
                }
            except Exception as e:
                return {
                    "answer": f"Unexpected error: {str(e)}",
                    "tokens_used": 0
                }

# Initialize the AI service
ai_service = AIService()
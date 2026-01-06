"""
API Client for CuES-WebArena
Supports OpenAI, Azure OpenAI, and other compatible APIs
"""
import os
import time
from typing import List, Dict, Any, Optional
import json

from ..utils.logger import get_logger

logger = get_logger(__name__)


class APIClient:
    """Unified API client supporting multiple providers"""
    
    def __init__(
        self,
        api_key: str = None,
        model_name: str = "openai/gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        azure_endpoint: str = None,
        api_version: str = "2024-02-15-preview"
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.azure_endpoint = azure_endpoint
        self.api_version = api_version
        
        # Parse provider and model
        if "/" in model_name:
            self.provider, self.model = model_name.split("/", 1)
        else:
            self.provider = "openai"
            self.model = model_name
        
        self._client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize the appropriate client based on provider"""
        if self.provider in ["openai", "azure"]:
            try:
                from openai import OpenAI, AzureOpenAI
                
                if self.provider == "azure" and self.azure_endpoint:
                    self._client = AzureOpenAI(
                        api_key=self.api_key,
                        azure_endpoint=self.azure_endpoint,
                        api_version=self.api_version
                    )
                else:
                    self._client = OpenAI(api_key=self.api_key)
                    
            except ImportError:
                logger.error("OpenAI package not installed. Run: pip install openai")
                raise
        
        elif self.provider == "glm":
            # GLM uses OpenAI-compatible API
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url="https://open.bigmodel.cn/api/paas/v4/"
                )
            except ImportError:
                logger.error("OpenAI package not installed. Run: pip install openai")
                raise
        
        elif self.provider == "kimi":
            # Kimi uses OpenAI-compatible API
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url="https://api.moonshot.cn/v1"
                )
            except ImportError:
                logger.error("OpenAI package not installed. Run: pip install openai")
                raise
        
        else:
            # Default to OpenAI-compatible API
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.error("OpenAI package not installed. Run: pip install openai")
                raise
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """Make a chat completion request"""
        try:
            # Merge parameters
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get("temperature", self.temperature),
                "max_tokens": kwargs.get("max_tokens", self.max_tokens)
            }
            
            response = self._client.chat.completions.create(**params)
            
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content.strip()
            else:
                logger.error("Empty response from API")
                return ""
                
        except Exception as e:
            logger.error(f"API request failed: {e}")
            return ""
    
    def chat_with_retry(
        self,
        messages: List[Dict[str, str]],
        max_retries: int = 3,
        retry_delay: float = 1.0,
        **kwargs
    ) -> str:
        """Chat completion with retry mechanism"""
        for attempt in range(max_retries):
            try:
                result = self.chat_completion(messages, **kwargs)
                if result:
                    return result
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
        
        logger.error(f"All {max_retries} attempts failed")
        return ""
    
    def has_vision(self) -> bool:
        """Check if the model supports vision"""
        vision_models = [
            "gpt-4o", "gpt-4-vision", "gpt-4-turbo",
            "glm-4v", "moonshot-v1-128k"
        ]
        return any(vm in self.model.lower() for vm in vision_models)


class PromptManager:
    """Prompt manager for formatting messages"""
    
    @staticmethod
    def format_system_message(content: str) -> Dict[str, str]:
        """Format a system message"""
        return {"role": "system", "content": content}
    
    @staticmethod
    def format_user_message(content: str) -> Dict[str, str]:
        """Format a user message"""
        return {"role": "user", "content": content}
    
    @staticmethod
    def format_assistant_message(content: str) -> Dict[str, str]:
        """Format an assistant message"""
        return {"role": "assistant", "content": content}
    
    @staticmethod
    def build_conversation(
        system_prompt: str,
        user_inputs: List[str],
        assistant_responses: List[str] = None
    ) -> List[Dict[str, str]]:
        """Build a full conversation"""
        messages = [PromptManager.format_system_message(system_prompt)]
        
        assistant_responses = assistant_responses or []
        
        for i, user_input in enumerate(user_inputs):
            messages.append(PromptManager.format_user_message(user_input))
            if i < len(assistant_responses):
                messages.append(PromptManager.format_assistant_message(assistant_responses[i]))
        
        return messages

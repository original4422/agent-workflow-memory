import os
import json
import base64
import logging
import openai
import numpy as np
from PIL import Image
from typing import Union, Optional, Tuple
from openai import OpenAI, ChatCompletion

CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
)

openai.api_key = os.environ.get("OPENAI_API_KEY")
openai.organization = os.environ.get("OPENAI_ORGANIZATION", "")
# client = OpenAI()


def _extract_provider(model_name: str) -> Optional[str]:
    """Infer provider prefix from model name."""
    if "/" in model_name:
        return model_name.split("/", 1)[0]
    lower_name = model_name.lower()
    if lower_name.startswith("glm"):
        return "glm"
    if lower_name.startswith("kimi"):
        return "kimi"
    return None


def _load_config(provider: Optional[str]) -> dict:
    """Load provider config from config/config.json."""
    if provider is None:
        return {}
    if not os.path.exists(CONFIG_PATH):
        logging.warning("Config file not found at %s", CONFIG_PATH)
        return {}

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config_list = json.load(f)
            if not isinstance(config_list, list):
                return {}
            for cfg in config_list:
                if cfg.get("model_provider") == provider:
                    return cfg
            return {}
    except json.JSONDecodeError as e:
        logging.warning("Failed to parse config file at %s: %s", CONFIG_PATH, e)
        return {}


def _resolve_model_name(cfg: dict) -> Tuple[str, Optional[str], Optional[str]]:
    """Return (final_model_name, base_url, api_key)."""
    base_url = cfg.get("base_url")
    api_key = cfg.get("api_key")
    final_model = cfg.get("model_name")

    return final_model, base_url, api_key


class LM_Client:
    def __init__(self, model_name: str = "gpt-3.5-turbo") -> None:
        self.model_name = model_name

    def chat(self, messages, json_mode: bool = False) -> tuple[str, ChatCompletion]:
        """
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "hi"},
        ])
        """
        chat_completion = client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            response_format={"type": "json_object"} if json_mode else None,
            temperature=0,
        )
        response = chat_completion.choices[0].message.content
        return response, chat_completion

    def one_step_chat(
        self, text, system_msg: str = None, json_mode=False
    ) -> tuple[str, ChatCompletion]:
        messages = []
        if system_msg is not None:
            messages.append({"role": "system", "content": system_msg})
        messages.append({"role": "user", "content": text})
        return self.chat(messages, json_mode=json_mode)


class GPT4V_Client:
    def __init__(self, model_name: str = "gpt-4o", max_tokens: int = 512):
        self.model_name = model_name
        self.max_tokens = max_tokens

    def encode_image(self, path: str):
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
                         
    def one_step_chat(
        self, text, image: Union[Image.Image, np.ndarray], 
        system_msg: Optional[str] = None,
    ) -> tuple[str, ChatCompletion]:
        jpg_base64_str = self.encode_image(image)
        messages = []
        if system_msg is not None:
            messages.append({"role": "system", "content": system_msg})
        messages += [{
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    {"type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{jpg_base64_str}"},},
                ],
        }]
        response = client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content, response


class CustomBaseClient:
    """Base client that allows custom base_url and api_key."""

    def __init__(self, model_name: str):
        provider = _extract_provider(model_name)
        cfg = _load_config(provider)
        final_model, base_url, api_key = _resolve_model_name(cfg)

        if not api_key:
            raise ValueError(f"api_key is missing for provider {provider}. Please set it in config/config.json")
        if not base_url:
            raise ValueError(f"base_url is missing for provider {provider}. Please set it in config/config.json")

        # Create a scoped OpenAI client pointing to provider's endpoint.
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = final_model

    def chat(self, messages, json_mode: bool = False, temperature: float = 0.0, max_tokens: Optional[int] = None) -> tuple[str, ChatCompletion]:
        chat_completion = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            response_format={"type": "json_object"} if json_mode else None,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        response = chat_completion.choices[0].message.content
        return response, chat_completion


class GLM_Client(CustomBaseClient):
    def __init__(self, model_name: str = "glm/glm-4.6") -> None:
        super().__init__(model_name=model_name)

    def one_step_chat(
        self, text, system_msg: str = None, json_mode: bool = False, max_tokens: Optional[int] = None
    ) -> tuple[str, ChatCompletion]:
        messages = []
        if system_msg is not None:
            messages.append({"role": "system", "content": system_msg})
        messages.append({"role": "user", "content": text})
        return self.chat(messages, json_mode=json_mode, max_tokens=max_tokens)


class KIMI_Client(CustomBaseClient):
    def __init__(self, model_name: str = "kimi/kimi-chat") -> None:
        super().__init__(model_name=model_name)

    def one_step_chat(
        self, text, system_msg: str = None, json_mode: bool = False, max_tokens: Optional[int] = None
    ) -> tuple[str, ChatCompletion]:
        messages = []
        if system_msg is not None:
            messages.append({"role": "system", "content": system_msg})
        messages.append({"role": "user", "content": text})
        return self.chat(messages, json_mode=json_mode, max_tokens=max_tokens)


CLIENT_DICT = {
    "gpt-3.5-turbo": LM_Client,
    "gpt-4": LM_Client,
    "gpt-4o": GPT4V_Client,
    "glm-4.6": GLM_Client,
    "kimi-chat": KIMI_Client,
}
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class LLMConfig:
    api_type: str  # "azure" | "openai" | "kimi" | "glm"
    model: str
    temperature: float = 0.2
    max_tokens: Optional[int] = 1024

    # OpenAI-compatible settings (for kimi, etc.)
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg
        self.client = None
        self._init_client()

    def _init_client(self) -> None:
        api_type = (self.cfg.api_type or "").lower().strip()
        if api_type == "azure":
            from cloudgpt_aoai import cloudgpt_aoai

            self.client = cloudgpt_aoai.get_openai_client()
        elif api_type in {"openai", "kimi", "glm"}:
            from openai import OpenAI

            if not self.cfg.api_key:
                raise ValueError("api_key is required for api_type!=azure")

            kwargs: Dict[str, Any] = {"api_key": self.cfg.api_key}
            if self.cfg.base_url:
                kwargs["base_url"] = self.cfg.base_url

            self.client = OpenAI(**kwargs)
        else:
            raise ValueError(f"Unknown api_type: {self.cfg.api_type}")

    def chat(self, messages: List[Dict[str, str]]) -> str:
        if self.client is None:
            raise RuntimeError("Client not initialized")

        request_kwargs: Dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": self.cfg.temperature,
        }

        if self.cfg.max_tokens is not None:
            model_lower = str(self.cfg.model).lower()
            # Azure + GPT-5 family uses max_completion_tokens
            if (str(self.cfg.api_type).lower().strip() == "azure") and (
                ("gpt-5" in model_lower) or model_lower.startswith("gpt5")
            ):
                request_kwargs["max_completion_tokens"] = self.cfg.max_tokens
            else:
                request_kwargs["max_tokens"] = self.cfg.max_tokens

        resp = self.client.chat.completions.create(**request_kwargs)
        return (resp.choices[0].message.content or "").strip()


def build_config(
    *,
    api_type: str,
    model: str,
    temperature: float = 0.2,
    max_tokens: Optional[int] = 1024,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> LLMConfig:
    if not isinstance(api_type, str):
        raise TypeError("api_type must be a string")
    if not isinstance(model, str):
        raise TypeError("model must be a string")

    api_type = api_type.strip().lower()
    if api_type not in {"azure", "openai", "kimi", "glm"}:
        raise ValueError(f"Unknown api_type: {api_type}")

    model = model.strip()
    if not model:
        raise ValueError("model is required (pass --model)")

    if api_type != "azure" and not api_key:
        raise ValueError("api_key is required for api_type!=azure")

    return LLMConfig(
        api_type=api_type,
        model=model,
        temperature=float(temperature),
        max_tokens=max_tokens,
        api_key=api_key,
        base_url=base_url,
    )

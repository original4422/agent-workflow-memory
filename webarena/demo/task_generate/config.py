""" 
================================================================================
config.py - Configuration
================================================================================
This module provides configuration for the CuES-lite implementation on WebArena.

[Mapping to CuES]
In the original CuES implementation, configuration is managed via config.yaml
(API settings, environment config, etc.). Here we simplify it into Python
dataclasses for direct use without additional YAML parsing dependencies.

[What is configured]
- API: Azure OpenAI (cloudgpt) or standard OpenAI-compatible API
- WebArena: basic target site information
- Generation: controls the amount of generation and related behaviors
================================================================================
"""

from dataclasses import dataclass, field
from typing import Optional, List
import os


@dataclass
class APIConfig:
    """
    API configuration.

    Supported API types:
    1) Azure OpenAI (cloudgpt): authenticated via azure.identity
    2) OpenAI: authenticated via API key
    3) Other OpenAI-compatible services
    """
    # API type: "azure" (cloudgpt) or "openai"
    api_type: str = "azure"
    
    # OpenAI API key (used when api_type="openai")
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    
    # OpenAI API base URL (optional, for custom endpoints)
    openai_api_base: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_BASE"))
    
    # Model name
    model_name: str = "gpt-4o-20241120-2"
    
    # Generation parameters
    temperature: float = 0.7
    max_tokens: int = 16384


@dataclass 
class WebArenaConfig:
    """
    WebArena configuration.

    Fields:
    - sites: target site list, e.g. ["shopping_admin", "reddit", "gitlab"]
    - base_url: base URL
    - require_login: whether login is required
    - storage_state: path to the stored login state
    """
    # Target sites
    sites: List[str] = field(default_factory=lambda: ["shopping_admin"])
    
    # Base URL
    base_url: str = "http://166.111.53.249:7780/admin"
    
    # Whether login is required
    require_login: bool = True
    
    # Storage state path
    storage_state: str = "./.auth/shopping_admin_state.json"


@dataclass
class GenerationConfig:
    """
    Generation configuration.

    Mapping to CuES stages:
    - num_intents: similar to the number of tasks generated per batch in CuES Stage 2
    - num_variants: similar to the number of query rewrite variants per task
    - min_confidence: confidence threshold used for filtering
    """
    # Number of intents to generate per run
    num_intents: int = 5
    
    # Variants per intent (for diversity)
    num_variants: int = 1
    
    # Minimum confidence threshold (0.0-1.0)
    min_confidence: float = 0.7
    
    # Maximum retries
    max_retries: int = 3
    
    # Output directory (base path)
    output_dir: str = "./generated_task"
    
    # Whether to create a timestamp subfolder for each run
    use_timestamp_folder: bool = True
    
    # Output filename (tasks.json)
    output_filename: str = "tasks.json"
    
    # Conversation history filename (conversation_history.json)
    conversation_history_filename: str = "conversation_history.json"


@dataclass
class Config:
    """
    Top-level config that aggregates all sub-configs.

    Example:
    ```python
    from config import Config
    
    # Use defaults
    config = Config()
    
    # Customize
    config = Config(
        api=APIConfig(api_type="openai", openai_api_key="sk-xxx"),
        webarena=WebArenaConfig(sites=["shopping_admin"]),
        generation=GenerationConfig(num_intents=10)
    )
    ```
    """
    api: APIConfig = field(default_factory=APIConfig)
    webarena: WebArenaConfig = field(default_factory=WebArenaConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)


# ================================================================================
# Preset configuration templates
# ================================================================================

def get_shopping_admin_config() -> Config:
    """Get the preset config for the Shopping Admin site."""
    return Config(
        webarena=WebArenaConfig(
            sites=["shopping_admin"],
            base_url="http://166.111.53.249:7780/admin",
            require_login=True,
            storage_state="./.auth/shopping_admin_state.json"
        )
    )


def get_reddit_config() -> Config:
    """Get the preset config for the Reddit site."""
    return Config(
        webarena=WebArenaConfig(
            sites=["reddit"],
            base_url="http://166.111.53.249:9999",
            require_login=True,
            storage_state="./.auth/reddit_state.json"
        )
    )


def get_gitlab_config() -> Config:
    """Get the preset config for the GitLab site."""
    return Config(
        webarena=WebArenaConfig(
            sites=["gitlab"],
            base_url="http://166.111.53.249:8023",
            require_login=True,
            storage_state="./.auth/gitlab_state.json"
        )
    )

""" 
WebArena Task Generator (CuES-Lite)
===================================

A CuES-inspired lightweight implementation that generates WebArena-format task
data.

Exports:
- Config: configuration container
- TaskGenerationPipeline: main pipeline
- IntentGenerator: intent generator
- AnswerAnnotator: answer annotator/validator
- generate_tasks_from_html: convenience helper
- generate_tasks_from_url: convenience helper

Example:
```python
from task_generate import Config, TaskGenerationPipeline

config = Config()
pipeline = TaskGenerationPipeline(config)
tasks = pipeline.run(html_content="<html>...</html>")
```
"""

from .config import (
    Config,
    APIConfig,
    WebArenaConfig,
    GenerationConfig,
    get_shopping_admin_config,
    get_reddit_config,
    get_gitlab_config,
)

from .generator import (
    LLMClient,
    IntentGenerator,
    AnswerAnnotator,
    TaskGenerationPipeline,
    generate_tasks_from_html,
    generate_tasks_from_url,
)

from .utils import (
    JSONHandler,
    HTMLProcessor,
    PromptBuilder,
    TaskFormatter,
    WebArenaTask,
)

__all__ = [
    # Config
    "Config",
    "APIConfig", 
    "WebArenaConfig",
    "GenerationConfig",
    "get_shopping_admin_config",
    "get_reddit_config",
    "get_gitlab_config",
    # Generator
    "LLMClient",
    "IntentGenerator",
    "AnswerAnnotator",
    "TaskGenerationPipeline",
    "generate_tasks_from_html",
    "generate_tasks_from_url",
    # Utils
    "JSONHandler",
    "HTMLProcessor",
    "PromptBuilder",
    "TaskFormatter",
    "WebArenaTask",
]

__version__ = "0.1.0"

"""
WebArena Task Generator (CuES-Lite)
====================================

基于 CuES 方法的轻量级实现，自动生成符合 WebArena 格式的 Task 数据。

【模块导出】
- Config: 配置类
- TaskGenerationPipeline: 主 Pipeline
- IntentGenerator: Intent 生成器
- AnswerAnnotator: 答案标注器
- generate_tasks_from_html: 便捷函数
- generate_tasks_from_url: 便捷函数

【使用示例】
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

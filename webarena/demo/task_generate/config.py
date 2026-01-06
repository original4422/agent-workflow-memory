"""
================================================================================
config.py - 配置文件
================================================================================
这是 CuES 轻量版在 WebArena 上的配置模块。

【CuES 设计理念映射】
在 CuES 原始实现中，配置通过 config.yaml 管理，包含 API 设置、环境配置等。
本模块简化为 Python dataclass，便于直接使用，无需额外的 YAML 解析依赖。

【配置项说明】
- API 配置: 使用 Azure OpenAI (cloudgpt) 或标准 OpenAI API
- WebArena 配置: 目标网站的基础信息
- 生成配置: 控制生成数量和行为
================================================================================
"""

from dataclasses import dataclass, field
from typing import Optional, List
import os


@dataclass
class APIConfig:
    """
    API 配置类
    
    【支持的 API 类型】
    1. Azure OpenAI (cloudgpt): 使用 azure.identity 认证
    2. OpenAI: 使用 API Key 认证
    3. 其他兼容 OpenAI 接口的服务
    """
    # API 类型: "azure" (cloudgpt) 或 "openai"
    api_type: str = "azure"
    
    # OpenAI API Key (当 api_type="openai" 时使用)
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    
    # OpenAI API Base URL (可选，用于自定义端点)
    openai_api_base: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_BASE"))
    
    # 模型名称
    model_name: str = "gpt-4o-20241120-2"
    
    # 生成参数
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass 
class WebArenaConfig:
    """
    WebArena 配置类
    
    【字段说明】
    - sites: 目标网站列表，如 ["shopping_admin", "reddit", "gitlab"]
    - base_url: 网站基础 URL
    - require_login: 是否需要登录
    - storage_state: 登录状态存储路径
    """
    # 目标网站
    sites: List[str] = field(default_factory=lambda: ["shopping_admin"])
    
    # 网站基础 URL
    base_url: str = "http://166.111.53.249:7780/admin"
    
    # 是否需要登录
    require_login: bool = True
    
    # 登录状态存储路径
    storage_state: str = "./.auth/shopping_admin_state.json"


@dataclass
class GenerationConfig:
    """
    生成配置类
    
    【CuES 阶段映射】
    - num_intents: 对应 CuES Stage 2 中每批次生成的任务数量
    - num_variants: 对应 CuES Query Rewrite 中每个任务的变体数量
    - min_confidence: 对应 CuES 的置信度过滤阈值
    """
    # 每次生成的 Intent 数量
    num_intents: int = 5
    
    # 每个 Intent 的变体数量 (用于多样性)
    num_variants: int = 1
    
    # 最低置信度阈值 (0.0-1.0)
    min_confidence: float = 0.7
    
    # 最大重试次数
    max_retries: int = 3
    
    # 输出文件夹路径
    output_dir: str = "./generated_task"
    
    # 输出文件名模板 (会自动添加时间戳)
    output_filename: str = "tasks_{timestamp}.json"


@dataclass
class Config:
    """
    主配置类 - 聚合所有子配置
    
    【使用示例】
    ```python
    from config import Config
    
    # 使用默认配置
    config = Config()
    
    # 自定义配置
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
# 预定义配置模板
# ================================================================================

def get_shopping_admin_config() -> Config:
    """获取 Shopping Admin 网站的预设配置"""
    return Config(
        webarena=WebArenaConfig(
            sites=["shopping_admin"],
            base_url="http://166.111.53.249:7780/admin",
            require_login=True,
            storage_state="./.auth/shopping_admin_state.json"
        )
    )


def get_reddit_config() -> Config:
    """获取 Reddit 网站的预设配置"""
    return Config(
        webarena=WebArenaConfig(
            sites=["reddit"],
            base_url="http://166.111.53.249:9999",
            require_login=True,
            storage_state="./.auth/reddit_state.json"
        )
    )


def get_gitlab_config() -> Config:
    """获取 GitLab 网站的预设配置"""
    return Config(
        webarena=WebArenaConfig(
            sites=["gitlab"],
            base_url="http://166.111.53.249:8023",
            require_login=True,
            storage_state="./.auth/gitlab_state.json"
        )
    )

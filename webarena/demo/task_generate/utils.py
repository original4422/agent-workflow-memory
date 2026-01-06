"""
================================================================================
utils.py - 工具函数模块
================================================================================
提供 JSON 读写、Prompt 构造、HTML 处理等通用工具函数。

【CuES 设计理念映射】
- PromptBuilder: 对应 CuES prompts/ 目录下的各种 Prompt 构造器
- JSONHandler: 对应 CuES data/storage.py 中的数据持久化逻辑
- HTMLProcessor: 简化版的环境状态提取器
================================================================================
"""

import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict


# ================================================================================
# JSON 处理工具
# ================================================================================

class JSONHandler:
    """
    JSON 文件读写处理器
    
    【功能说明】
    - 读取现有任务配置文件
    - 保存生成的任务到 JSON 文件
    - 支持增量追加模式
    """
    
    @staticmethod
    def load(filepath: str) -> List[Dict[str, Any]]:
        """
        加载 JSON 文件
        
        Args:
            filepath: JSON 文件路径
            
        Returns:
            解析后的数据列表
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else [data]
        except FileNotFoundError:
            print(f"[警告] 文件不存在: {filepath}")
            return []
        except json.JSONDecodeError as e:
            print(f"[错误] JSON 解析失败: {e}")
            return []
    
    @staticmethod
    def save(data: List[Dict[str, Any]], filepath: str, indent: int = 2) -> bool:
        """
        保存数据到 JSON 文件
        
        Args:
            data: 要保存的数据
            filepath: 目标文件路径
            indent: 缩进空格数
            
        Returns:
            是否保存成功
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=indent)
            return True
        except Exception as e:
            print(f"[错误] 保存文件失败: {e}")
            return False
    
    @staticmethod
    def append(task: Dict[str, Any], filepath: str) -> bool:
        """
        追加单个任务到现有 JSON 文件
        
        Args:
            task: 要追加的任务
            filepath: 目标文件路径
            
        Returns:
            是否追加成功
        """
        existing = JSONHandler.load(filepath)
        existing.append(task)
        return JSONHandler.save(existing, filepath)


# ================================================================================
# HTML 处理工具
# ================================================================================

class HTMLProcessor:
    """
    HTML 内容处理器
    
    【功能说明】
    从 HTML 中提取关键信息，为 LLM 提供结构化的页面描述。
    
    【CuES 对应】
    类似于 CuES Stage 1 中的环境状态观察，但简化为静态 HTML 解析。
    """
    
    @staticmethod
    def extract_text(html: str, max_length: int = 4000) -> str:
        """
        从 HTML 中提取纯文本内容
        
        Args:
            html: HTML 字符串
            max_length: 最大返回长度
            
        Returns:
            提取的文本内容
        """
        # 移除 script 和 style 标签及其内容
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # 移除所有 HTML 标签
        text = re.sub(r'<[^>]+>', ' ', html)
        
        # 清理多余空白
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 截断到最大长度
        if len(text) > max_length:
            text = text[:max_length] + "..."
        
        return text
    
    @staticmethod
    def extract_interactive_elements(html: str) -> List[Dict[str, str]]:
        """
        提取页面中的可交互元素 (按钮、链接、输入框等)
        
        【用途】
        帮助 LLM 理解页面上可以执行的操作，从而生成更合理的任务。
        
        Args:
            html: HTML 字符串
            
        Returns:
            可交互元素列表
        """
        elements = []
        
        # 提取链接
        links = re.findall(r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
        for href, text in links[:20]:  # 限制数量
            clean_text = re.sub(r'<[^>]+>', '', text).strip()
            if clean_text:
                elements.append({"type": "link", "text": clean_text[:100], "href": href})
        
        # 提取按钮
        buttons = re.findall(r'<button[^>]*>(.*?)</button>', html, re.IGNORECASE | re.DOTALL)
        for btn_text in buttons[:10]:
            clean_text = re.sub(r'<[^>]+>', '', btn_text).strip()
            if clean_text:
                elements.append({"type": "button", "text": clean_text[:100]})
        
        # 提取输入框
        inputs = re.findall(r'<input[^>]*(?:placeholder=["\']([^"\']*)["\']|name=["\']([^"\']*)["\'])[^>]*>', html, re.IGNORECASE)
        for placeholder, name in inputs[:10]:
            elements.append({"type": "input", "placeholder": placeholder, "name": name})
        
        return elements
    
    @staticmethod
    def extract_page_title(html: str) -> str:
        """提取页面标题"""
        match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else "Unknown Page"
    
    @staticmethod
    def summarize_page(html: str) -> Dict[str, Any]:
        """
        生成页面摘要信息
        
        【输出格式】
        返回一个字典，包含：
        - title: 页面标题
        - text_content: 文本内容 (截断)
        - interactive_elements: 可交互元素列表
        """
        return {
            "title": HTMLProcessor.extract_page_title(html),
            "text_content": HTMLProcessor.extract_text(html, max_length=3000),
            "interactive_elements": HTMLProcessor.extract_interactive_elements(html)
        }


# ================================================================================
# Prompt 构造器
# ================================================================================

class PromptBuilder:
    """
    Prompt 构造器
    
    【CuES 设计理念映射】
    对应 CuES prompts/ 目录下的各种 Prompt 模板，但简化为单一类管理。
    
    【Pipeline 阶段】
    1. Intent Generation Prompt: 生成任务意图 (对应 CuES Stage 2: Task Abstraction)
    2. Answer Validation Prompt: 验证并生成答案 (对应 CuES Stage 3: Quality Control)
    """
    
    @staticmethod
    def build_intent_generation_prompt(
        page_summary: Dict[str, Any],
        site_name: str,
        num_intents: int = 5
    ) -> str:
        """
        构造 Intent 生成的 Prompt
        
        【CuES 对应】
        这对应于 CuES Stage 2 中的 Task Abstraction，从环境状态中抽取可执行的任务。
        
        【关键差异】
        - CuES 从 triplet (state, action, observation) 序列中抽取任务
        - 本实现从静态 HTML 页面中推断可能的任务
        
        Args:
            page_summary: HTMLProcessor.summarize_page() 的输出
            site_name: 网站名称 (如 "shopping_admin")
            num_intents: 需要生成的 Intent 数量
            
        Returns:
            格式化的 Prompt 字符串
        """
        # 格式化交互元素列表
        elements_text = ""
        for elem in page_summary.get("interactive_elements", [])[:15]:
            if elem["type"] == "link":
                elements_text += f"  - [链接] {elem['text']}\n"
            elif elem["type"] == "button":
                elements_text += f"  - [按钮] {elem['text']}\n"
            elif elem["type"] == "input":
                elements_text += f"  - [输入框] {elem.get('placeholder', elem.get('name', ''))}\n"
        
        prompt = f"""你是一个 WebArena 任务生成专家。你需要根据给定的网页信息，生成合理的任务意图 (intent)。

## 页面信息

**网站类型**: {site_name}
**页面标题**: {page_summary.get('title', 'Unknown')}

**页面内容摘要**:
{page_summary.get('text_content', '')[:2000]}

**可交互元素**:
{elements_text if elements_text else "  (无法识别的交互元素)"}

## 任务要求

请根据上述页面信息，生成 {num_intents} 个合理的任务意图 (intent)。

任务应该满足以下条件：
1. **可执行性**: 任务必须是在该页面上可以完成的操作
2. **明确性**: 任务描述要清晰，有明确的目标
3. **多样性**: 任务类型应该多样化（查询、修改、导航等）
4. **可验证性**: 任务完成后应该有可检验的结果

## 任务类型参考

对于 **shopping_admin** (电商后台管理系统)，常见任务包括:
- 查询类: "What is the top-1 best-selling product in 2022?"
- 统计类: "How many orders were placed in January 2023?"
- 查找类: "Find the customer with the highest total order value"
- 修改类: "Update the price of product X to $99.99"

## 输出格式

请按以下 JSON 格式输出，每个任务包含:
- intent: 任务意图描述 (英文)
- task_type: 任务类型 (query/modification/navigation)
- difficulty: 难度等级 (easy/medium/hard)
- reasoning: 为什么这个任务是合理的 (中文简述)

```json
[
  {{
    "intent": "What is the top-3 best-selling products in January 2023?",
    "task_type": "query",
    "difficulty": "medium",
    "reasoning": "页面包含销售数据，可以查询销售排名"
  }},
  ...
]
```

请直接输出 JSON，不要添加其他解释文字。
"""
        return prompt
    
    @staticmethod
    def build_answer_validation_prompt(
        intent: str,
        page_summary: Dict[str, Any],
        site_name: str
    ) -> str:
        """
        构造答案验证/生成的 Prompt
        
        【CuES 对应】
        这对应于 CuES Stage 3 中的 Quality Control，验证任务的可执行性并生成参考答案。
        
        【工作原理】
        由于没有真实的浏览器执行环境，我们使用 LLM 来：
        1. 推断该任务在给定页面上是否可执行
        2. 基于页面内容推断可能的参考答案
        3. 确定答案的验证方式 (exact_match, must_include 等)
        
        Args:
            intent: 要验证的任务意图
            page_summary: 页面摘要
            site_name: 网站名称
            
        Returns:
            格式化的 Prompt 字符串
        """
        prompt = f"""你是一个 WebArena 任务验证专家。你需要评估给定的任务是否可以在网页上执行，并生成参考答案。

## 任务意图

**Intent**: {intent}

## 页面信息

**网站类型**: {site_name}
**页面标题**: {page_summary.get('title', 'Unknown')}

**页面内容摘要**:
{page_summary.get('text_content', '')[:2500]}

## 验证任务

请完成以下评估：

1. **可执行性评估**: 这个任务能在该页面（或通过该页面导航）完成吗？
2. **参考答案推断**: 如果可执行，基于页面内容推断可能的答案
3. **验证方式选择**: 选择合适的答案匹配方式

## 输出格式

请按以下 JSON 格式输出：

```json
{{
  "is_executable": true,
  "confidence": 0.85,
  "eval_type": "string_match",
  "reference_answers": {{
    "must_include": ["关键词1", "关键词2"],
    "exact_match": "完整答案(如果适用)"
  }},
  "reasoning": "解释为什么这个任务是可执行的，以及答案是如何推断的"
}}
```

**eval_type 选项说明**:
- `string_match`: 答案包含特定字符串
- `url_match`: 最终 URL 匹配特定模式  
- `program_html`: 需要检查 HTML 元素

**reference_answers 字段说明**:
- `must_include`: 答案必须包含的关键词列表
- `exact_match`: 答案必须完全匹配的字符串
- `fuzzy_match`: 模糊匹配的字符串

如果任务不可执行，请设置:
```json
{{
  "is_executable": false,
  "confidence": 0.1,
  "reasoning": "解释为什么不可执行"
}}
```

请直接输出 JSON，不要添加其他解释文字。
"""
        return prompt


# ================================================================================
# WebArena Task 格式化器
# ================================================================================

@dataclass
class WebArenaTask:
    """
    WebArena 任务数据结构
    
    【字段说明】
    这是 WebArena 标准任务格式的 Python 表示。
    
    【CuES 字段映射】
    - intent: 对应 CuES Task 的 Query 字段
    - reference_answers: 对应 CuES 验证阶段的输出
    """
    # 目标网站列表
    sites: List[str]
    
    # 任务 ID
    task_id: int
    
    # 是否需要登录
    require_login: bool
    
    # 登录状态存储路径
    storage_state: str
    
    # 起始 URL
    start_url: str
    
    # 任务意图 (核心字段)
    intent: str
    
    # 评估配置
    eval: Dict[str, Any]
    
    # 可选字段
    geolocation: Optional[str] = None
    require_reset: bool = False
    intent_template: Optional[str] = None
    instantiation_dict: Optional[Dict[str, Any]] = None
    intent_template_id: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = asdict(self)
        # 移除 None 值的可选字段
        return {k: v for k, v in result.items() if v is not None}


class TaskFormatter:
    """
    任务格式化器
    
    【功能说明】
    将生成的 Intent 和 Answer 封装为 WebArena 标准 JSON 格式。
    
    【CuES 对应】
    类似于 CuES data/models.py 中的数据模型转换逻辑。
    """
    
    def __init__(self, config):
        """
        初始化格式化器
        
        Args:
            config: Config 对象，包含 WebArena 配置
        """
        self.config = config
        self.task_counter = 0
    
    def format_task(
        self,
        intent: str,
        reference_answers: Dict[str, Any],
        eval_type: str = "string_match",
        task_id: Optional[int] = None
    ) -> WebArenaTask:
        """
        将 Intent 和 Answer 格式化为 WebArena 任务
        
        【处理流程】
        1. 分配任务 ID (自动递增或指定)
        2. 组装评估配置
        3. 合并 WebArena 配置
        
        Args:
            intent: 任务意图
            reference_answers: 参考答案字典
            eval_type: 评估类型
            task_id: 任务 ID (可选)
            
        Returns:
            WebArenaTask 对象
        """
        if task_id is None:
            task_id = self.task_counter
            self.task_counter += 1
        
        # 构造评估配置
        eval_config = {
            "eval_types": [eval_type],
            "reference_answers": reference_answers,
            "reference_url": "",
            "program_html": [],
            "string_note": ""
        }
        
        return WebArenaTask(
            sites=self.config.webarena.sites,
            task_id=task_id,
            require_login=self.config.webarena.require_login,
            storage_state=self.config.webarena.storage_state,
            start_url=self.config.webarena.base_url,
            intent=intent,
            eval=eval_config
        )
    
    def format_tasks(
        self,
        generated_data: List[Dict[str, Any]],
        start_id: int = 0
    ) -> List[Dict[str, Any]]:
        """
        批量格式化任务
        
        Args:
            generated_data: 包含 intent 和验证结果的数据列表
            start_id: 起始任务 ID
            
        Returns:
            WebArena 格式的任务列表
        """
        self.task_counter = start_id
        tasks = []
        
        for item in generated_data:
            if not item.get("is_executable", False):
                continue
            
            task = self.format_task(
                intent=item["intent"],
                reference_answers=item.get("reference_answers", {}),
                eval_type=item.get("eval_type", "string_match")
            )
            tasks.append(task.to_dict())
        
        return tasks

"""
================================================================================
generator.py - 核心生成模块
================================================================================
实现 CuES 思想的轻量级版本，包含完整的 Task 生成 Pipeline。

【CuES 三阶段映射】
┌─────────────────────────────────────────────────────────────────────────────┐
│  CuES 原始流程              │  本模块简化实现                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  Stage 1: Triplet Gen       │  HTMLProcessor.summarize_page()               │
│  (好奇心驱动的环境探索)       │  (静态 HTML 页面分析，提取关键信息)             │
├─────────────────────────────────────────────────────────────────────────────┤
│  Stage 2: Task Abstraction  │  IntentGenerator.generate()                   │
│  (从轨迹中抽象任务)          │  (LLM 根据页面信息生成 Intent)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  Stage 3: Quality Control   │  AnswerAnnotator.validate_and_solve()         │
│  (验证和答案生成)            │  (LLM 验证可执行性并推断答案)                   │
└─────────────────────────────────────────────────────────────────────────────┘

【Pipeline 数据流】
HTML Input → Page Summary → LLM (Intent Gen) → Intents 
           → LLM (Validation) → Reference Answers → WebArena JSON
================================================================================
"""

import json
import re
import sys
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# 添加父目录到路径以导入 cloudgpt_aoai
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from config import Config, APIConfig
from utils import HTMLProcessor, PromptBuilder, TaskFormatter, JSONHandler


# ================================================================================
# LLM 客户端封装
# ================================================================================

class LLMClient:
    """
    LLM 客户端封装类
    
    【支持的后端】
    1. Azure OpenAI (cloudgpt): 使用 azure.identity 认证
    2. OpenAI: 使用标准 API Key 认证
    
    【CuES 对应】
    类似于 CuES core/api_client.py 中的 DashScopeClient，但适配 Azure/OpenAI。
    """
    
    def __init__(self, api_config: APIConfig):
        """
        初始化 LLM 客户端
        
        Args:
            api_config: API 配置对象
        """
        self.config = api_config
        self.client = None
        self.conversation_history = []  # 记录所有对话历史
        self._init_client()
    
    def _init_client(self):
        """根据配置初始化对应的客户端"""
        if self.config.api_type == "azure":
            self._init_azure_client()
        else:
            self._init_openai_client()
    
    def _init_azure_client(self):
        """初始化 Azure OpenAI (cloudgpt) 客户端"""
        try:
            from cloudgpt_aoai import cloudgpt_aoai
            self.client = cloudgpt_aoai.get_openai_client()
            self.model_name=self.config.model_name
            print("[INFO] 已初始化 Azure OpenAI (cloudgpt) 客户端")
            print(f"[INFO] 使用模型: {self.model_name}")
        except ImportError:
            print("[警告] cloudgpt_aoai 模块不可用，尝试使用 OpenAI 客户端")
            self._init_openai_client()
        except Exception as e:
            print(f"[错误] Azure 客户端初始化失败: {e}")
            self._init_openai_client()
    
    def _init_openai_client(self):
        """初始化标准 OpenAI 客户端"""
        try:
            from openai import OpenAI
            
            if self.config.openai_api_key:
                kwargs = {"api_key": self.config.openai_api_key}
                if self.config.openai_api_base:
                    kwargs["base_url"] = self.config.openai_api_base
                self.client = OpenAI(**kwargs)
                print("[INFO] 已初始化 OpenAI 客户端")
            else:
                raise ValueError("OpenAI API Key 未设置")
        except Exception as e:
            print(f"[错误] OpenAI 客户端初始化失败: {e}")
            raise
    
    def chat(
        self, 
        messages: List[Dict[str, str]], 
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 采样温度 (可选)
            max_tokens: 最大输出 token 数 (可选)
            
        Returns:
            LLM 的响应内容
        """
        if self.client is None:
            raise RuntimeError("LLM 客户端未正确初始化")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens
            )
            response_content = response.choices[0].message.content.strip()
            
            # 记录对话历史
            conversation_entry = {
                "messages": messages,
                "response": response_content,
                "model": self.model_name,
                "temperature": temperature or self.config.temperature,
                "max_tokens": max_tokens or self.config.max_tokens
            }
            self.conversation_history.append(conversation_entry)
            
            return response_content
        except Exception as e:
            print(f"[错误] LLM 请求失败: {e}")
            return ""
    
    def chat_with_retry(
        self,
        messages: List[Dict[str, str]],
        max_retries: int = 3,
        **kwargs
    ) -> str:
        """
        带重试机制的聊天请求
        
        【CuES 对应】
        类似于 CuES api_client.py 中的 chat_with_retry 方法。
        
        Args:
            messages: 消息列表
            max_retries: 最大重试次数
            **kwargs: 其他参数
            
        Returns:
            LLM 的响应内容
        """
        import time
        
        for attempt in range(max_retries):
            try:
                result = self.chat(messages, **kwargs)
                if result:
                    return result
            except Exception as e:
                print(f"[警告] 第 {attempt + 1} 次尝试失败: {e}")
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数退避
                print(f"[INFO] 等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
        
        print(f"[错误] 所有 {max_retries} 次尝试均失败")
        return ""
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        获取完整的对话历史记录
        
        Returns:
            对话历史记录列表
        """
        return self.conversation_history
    
    def clear_conversation_history(self):
        """清空对话历史记录"""
        self.conversation_history = []


# ================================================================================
# Intent 生成器 (对应 CuES Stage 2: Task Abstraction)
# ================================================================================

class IntentGenerator:
    """
    Intent 生成器
    
    【CuES 设计理念】
    在 CuES 中，Stage 2 (Task Abstraction) 从 Agent 的交互轨迹中抽象出具体任务。
    本模块简化为：从静态 HTML 页面信息中，由 LLM 推断可能的任务意图。
    
    【核心思想】
    1. 分析页面结构和内容
    2. 识别可执行的操作类型
    3. 生成多样化、可验证的任务意图
    """
    
    def __init__(self, client: LLMClient, config: Config):
        """
        初始化 Intent 生成器
        
        Args:
            client: LLM 客户端
            config: 配置对象
        """
        self.client = client
        self.config = config
    
    def generate(
        self,
        html_content: str,
        num_intents: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        从 HTML 内容生成任务意图
        
        【处理流程】
        1. 使用 HTMLProcessor 提取页面摘要
        2. 构造 Prompt 并调用 LLM
        3. 解析 LLM 输出为结构化数据
        
        Args:
            html_content: HTML 页面内容
            num_intents: 要生成的 Intent 数量 (可选)
            
        Returns:
            Intent 列表，每个 Intent 包含:
            - intent: 任务描述
            - task_type: 任务类型
            - difficulty: 难度等级
            - reasoning: 生成理由
        """
        # 1. 提取页面摘要
        page_summary = HTMLProcessor.summarize_page(html_content)
        print(f"[INFO] 页面标题: {page_summary['title']}")
        print(f"[INFO] 识别到 {len(page_summary['interactive_elements'])} 个交互元素")
        
        # 2. 构造 Prompt
        site_name = self.config.webarena.sites[0] if self.config.webarena.sites else "unknown"
        num = num_intents or self.config.generation.num_intents
        
        prompt = PromptBuilder.build_intent_generation_prompt(
            page_summary=page_summary,
            site_name=site_name,
            num_intents=num
        )
        
        # 3. 调用 LLM
        messages = [{"role": "user", "content": prompt}]
        response = self.client.chat_with_retry(messages)
        
        # 4. 解析响应
        intents = self._parse_intents(response)
        print(f"[INFO] 成功生成 {len(intents)} 个 Intent")
        
        return intents
    
    def _parse_intents(self, response: str) -> List[Dict[str, Any]]:
        """
        解析 LLM 响应，提取 Intent 列表
        
        Args:
            response: LLM 的原始响应
            
        Returns:
            解析后的 Intent 列表
        """
        try:
            # 尝试直接解析 JSON
            # 首先尝试提取 ```json ... ``` 块
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试找到 JSON 数组
                json_match = re.search(r'\[[\s\S]*\]', response)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    print(f"[警告] 无法在响应中找到 JSON: {response[:200]}...")
                    return []
            
            intents = json.loads(json_str)
            
            # 验证格式
            valid_intents = []
            for intent in intents:
                if isinstance(intent, dict) and "intent" in intent:
                    valid_intents.append(intent)
            
            return valid_intents
            
        except json.JSONDecodeError as e:
            print(f"[错误] JSON 解析失败: {e}")
            print(f"[DEBUG] 原始响应: {response[:500]}...")
            return []


# ================================================================================
# 答案标注器 (对应 CuES Stage 3: Quality Control)
# ================================================================================

class AnswerAnnotator:
    """
    答案标注器/验证器
    
    【CuES 设计理念】
    在 CuES 中，Stage 3 (Quality Control) 通过重新执行任务来验证其可执行性。
    本模块简化为：使用 LLM 来推断任务是否可执行，并生成参考答案。
    
    【核心功能】
    1. 验证 Intent 在给定页面上是否可执行
    2. 推断任务完成后的参考答案
    3. 确定答案的验证方式 (exact_match, must_include 等)
    
    【局限性说明】
    由于没有真实的浏览器执行环境，答案是基于 LLM 推理生成的，
    可能需要人工验证或通过实际执行来校正。
    """
    
    def __init__(self, client: LLMClient, config: Config):
        """
        初始化答案标注器
        
        Args:
            client: LLM 客户端
            config: 配置对象
        """
        self.client = client
        self.config = config
    
    def validate_and_solve(
        self,
        intent: str,
        html_content: str
    ) -> Dict[str, Any]:
        """
        验证 Intent 并生成参考答案
        
        【处理流程】
        1. 提取页面摘要
        2. 构造验证 Prompt
        3. 调用 LLM 进行推理
        4. 解析并返回结果
        
        Args:
            intent: 要验证的任务意图
            html_content: HTML 页面内容
            
        Returns:
            验证结果字典，包含:
            - is_executable: 是否可执行
            - confidence: 置信度
            - eval_type: 评估类型
            - reference_answers: 参考答案
            - reasoning: 推理过程
        """
        # 1. 提取页面摘要
        page_summary = HTMLProcessor.summarize_page(html_content)
        
        # 2. 构造 Prompt
        site_name = self.config.webarena.sites[0] if self.config.webarena.sites else "unknown"
        prompt = PromptBuilder.build_answer_validation_prompt(
            intent=intent,
            page_summary=page_summary,
            site_name=site_name
        )
        
        # 3. 调用 LLM
        messages = [{"role": "user", "content": prompt}]
        response = self.client.chat_with_retry(messages)
        
        # 4. 解析响应
        result = self._parse_validation_result(response, intent)
        
        return result
    
    def _parse_validation_result(
        self,
        response: str,
        intent: str
    ) -> Dict[str, Any]:
        """
        解析验证结果
        
        Args:
            response: LLM 的原始响应
            intent: 原始 Intent (用于填充结果)
            
        Returns:
            解析后的验证结果
        """
        default_result = {
            "intent": intent,
            "is_executable": False,
            "confidence": 0.0,
            "eval_type": "string_match",
            "reference_answers": {},
            "reasoning": "解析失败"
        }
        
        try:
            # 提取 JSON
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    print(f"[警告] 无法解析验证结果: {response[:200]}...")
                    return default_result
            
            result = json.loads(json_str)
            result["intent"] = intent
            
            # 确保必要字段存在
            result.setdefault("is_executable", False)
            result.setdefault("confidence", 0.0)
            result.setdefault("eval_type", "string_match")
            result.setdefault("reference_answers", {})
            result.setdefault("reasoning", "")
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"[错误] 验证结果 JSON 解析失败: {e}")
            return default_result
    
    def batch_validate(
        self,
        intents: List[Dict[str, Any]],
        html_content: str
    ) -> List[Dict[str, Any]]:
        """
        批量验证多个 Intent
        
        Args:
            intents: Intent 列表
            html_content: HTML 页面内容
            
        Returns:
            验证结果列表
        """
        results = []
        total = len(intents)
        
        for i, intent_data in enumerate(intents, 1):
            intent_text = intent_data.get("intent", "")
            print(f"[INFO] 验证 Intent ({i}/{total}): {intent_text[:50]}...")
            
            result = self.validate_and_solve(intent_text, html_content)
            
            # 合并原始 Intent 数据
            result.update({
                "task_type": intent_data.get("task_type", "query"),
                "difficulty": intent_data.get("difficulty", "medium"),
                "generation_reasoning": intent_data.get("reasoning", "")
            })
            
            results.append(result)
            
            # 过滤低置信度的结果
            if result.get("confidence", 0) < self.config.generation.min_confidence:
                print(f"    [跳过] 置信度 {result.get('confidence', 0):.2f} 低于阈值")
        
        return results


# ================================================================================
# 主 Pipeline (整合 Generator + Annotator + Formatter)
# ================================================================================

class TaskGenerationPipeline:
    """
    任务生成主 Pipeline
    
    【CuES 设计理念整合】
    本类整合了 CuES 的核心思想，实现了一个简化的线性 Pipeline：
    
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │   HTML      │ ──> │  Generator  │ ──> │  Annotator  │ ──> │  Formatter  │
    │   Input     │     │  (Intent)   │     │  (Answer)   │     │  (JSON)     │
    └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
    
    【对应 CuES 阶段】
    - HTML Input: 类似 Stage 1 的环境观察
    - Generator: 对应 Stage 2 的 Task Abstraction
    - Annotator: 对应 Stage 3 的 Quality Control
    - Formatter: 输出标准化的 WebArena Task
    """
    
    def __init__(self, config: Config):
        """
        初始化 Pipeline
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.client = LLMClient(config.api)
        self.generator = IntentGenerator(self.client, config)
        self.annotator = AnswerAnnotator(self.client, config)
        self.formatter = TaskFormatter(config)
    
    def run(
        self,
        html_content: str,
        num_intents: Optional[int] = None,
        start_task_id: int = 0
    ) -> List[Dict[str, Any]]:
        """
        运行完整的任务生成 Pipeline
        
        【执行流程】
        1. Intent 生成: 从 HTML 中提取可能的任务意图
        2. 答案验证: 验证每个 Intent 并生成参考答案
        3. 格式化: 将结果转换为 WebArena JSON 格式
        4. 过滤: 移除低置信度的任务
        
        Args:
            html_content: HTML 页面内容
            num_intents: 要生成的 Intent 数量 (可选)
            start_task_id: 起始任务 ID
            
        Returns:
            WebArena 格式的任务列表
        """
        print("=" * 60)
        print("【阶段 1】Intent 生成 (对应 CuES Stage 2: Task Abstraction)")
        print("=" * 60)
        
        # 1. 生成 Intent
        intents = self.generator.generate(html_content, num_intents)
        
        if not intents:
            print("[错误] 未能生成任何 Intent")
            return []
        
        print("\n" + "=" * 60)
        print("【阶段 2】答案验证 (对应 CuES Stage 3: Quality Control)")
        print("=" * 60)
        
        # 2. 验证并生成答案
        validated_results = self.annotator.batch_validate(intents, html_content)
        
        # 3. 过滤低置信度结果
        min_conf = self.config.generation.min_confidence
        filtered_results = [
            r for r in validated_results 
            if r.get("is_executable", False) and r.get("confidence", 0) >= min_conf
        ]
        
        print(f"\n[INFO] 过滤后保留 {len(filtered_results)}/{len(validated_results)} 个任务")
        
        print("\n" + "=" * 60)
        print("【阶段 3】格式化输出 (WebArena JSON)")
        print("=" * 60)
        
        # 4. 格式化为 WebArena 任务
        tasks = self.formatter.format_tasks(filtered_results, start_task_id)
        
        print(f"[INFO] 成功生成 {len(tasks)} 个 WebArena 任务")
        
        return tasks
    
    def run_from_url(
        self,
        url: str,
        num_intents: Optional[int] = None,
        start_task_id: int = 0
    ) -> List[Dict[str, Any]]:
        """
        从 URL 获取页面并生成任务
        
        Args:
            url: 目标页面 URL
            num_intents: 要生成的 Intent 数量 (可选)
            start_task_id: 起始任务 ID
            
        Returns:
            WebArena 格式的任务列表
        """
        print(f"[INFO] 正在获取页面: {url}")
        
        try:
            import requests
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            html_content = response.text
            print(f"[INFO] 成功获取页面，大小: {len(html_content)} 字节")
        except Exception as e:
            print(f"[错误] 获取页面失败: {e}")
            return []
        
        return self.run(html_content, num_intents, start_task_id)
    
    def run_from_file(
        self,
        file_path: str,
        num_intents: Optional[int] = None,
        start_task_id: int = 0
    ) -> List[Dict[str, Any]]:
        """
        从本地 HTML 文件生成任务
        
        Args:
            file_path: HTML 文件路径
            num_intents: 要生成的 Intent 数量 (可选)
            start_task_id: 起始任务 ID
            
        Returns:
            WebArena 格式的任务列表
        """
        print(f"[INFO] 正在读取文件: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            print(f"[INFO] 成功读取文件，大小: {len(html_content)} 字节")
        except Exception as e:
            print(f"[错误] 读取文件失败: {e}")
            return []
        
        return self.run(html_content, num_intents, start_task_id)
    
    def get_conversation_history(self) -> Dict[str, Any]:
        """
        获取完整的对话历史记录
        
        Returns:
            包含对话历史的字典
        """
        return {
            "conversation_history": self.client.get_conversation_history()
        }
    
    def save_conversation_history(self, output_path: str):
        """
        保存对话历史到JSON文件
        
        Args:
            output_path: 输出文件路径
        """
        history_data = self.get_conversation_history()
        JSONHandler.save(history_data, output_path)
        print(f"[INFO] 对话历史已保存到: {output_path}")


# ================================================================================
# 便捷函数
# ================================================================================

def generate_tasks_from_html(
    html_content: str,
    config: Optional[Config] = None,
    num_intents: int = 5
) -> List[Dict[str, Any]]:
    """
    便捷函数：从 HTML 内容直接生成任务
    
    Args:
        html_content: HTML 页面内容
        config: 配置对象 (可选)
        num_intents: 要生成的 Intent 数量
        
    Returns:
        WebArena 格式的任务列表
    """
    config = config or Config()
    pipeline = TaskGenerationPipeline(config)
    return pipeline.run(html_content, num_intents)


def generate_tasks_from_url(
    url: str,
    config: Optional[Config] = None,
    num_intents: int = 5
) -> List[Dict[str, Any]]:
    """
    便捷函数：从 URL 直接生成任务
    
    Args:
        url: 目标页面 URL
        config: 配置对象 (可选)
        num_intents: 要生成的 Intent 数量
        
    Returns:
        WebArena 格式的任务列表
    """
    config = config or Config()
    pipeline = TaskGenerationPipeline(config)
    return pipeline.run_from_url(url, num_intents)

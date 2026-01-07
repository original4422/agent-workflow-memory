"""
================================================================================
generator.py - Core generation pipeline
================================================================================
A CuES-inspired lightweight implementation with a full task-generation pipeline.

[Mapping to the 3 CuES stages]
┌─────────────────────────────────────────────────────────────────────────────┐
│  CuES original flow            │  This module (simplified)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  Stage 1: Triplet Gen          │  HTMLProcessor.summarize_page()            │
│  (curiosity-driven exploration)│  (static HTML analysis, extract signals)   │
├─────────────────────────────────────────────────────────────────────────────┤
│  Stage 2: Task Abstraction     │  IntentGenerator.generate()                │
│  (abstract tasks from traces)  │  (LLM infers intents from page info)       │
├─────────────────────────────────────────────────────────────────────────────┤
│  Stage 3: Quality Control      │  AnswerAnnotator.validate_and_solve()      │
│  (validation + answer gen)     │  (LLM validates + infers reference answers)│
└─────────────────────────────────────────────────────────────────────────────┘

[Pipeline data flow]
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

# Add parent dirs to import cloudgpt_aoai
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from config import Config, APIConfig
from utils import HTMLProcessor, PromptBuilder, TaskFormatter, JSONHandler


# ================================================================================
# LLM client wrapper
# ================================================================================

class LLMClient:
    """
    Lightweight LLM client wrapper.

    Supported backends:
    1) Azure OpenAI (cloudgpt): authenticated via azure.identity
    2) OpenAI: authenticated via standard API key

    Mapping to CuES:
    Similar to CuES core/api_client.py (e.g., DashScopeClient), but adapted for
    Azure/OpenAI.
    """
    
    def __init__(self, api_config: APIConfig):
        """
        Initialize the LLM client.
        
        Args:
            api_config: API configuration object
        """
        self.config = api_config
        self.client = None
        self.conversation_history = []  # Record all requests/responses
        self._init_client()
    
    def _init_client(self):
        """Initialize the backend client based on configuration."""
        if self.config.api_type == "azure":
            self._init_azure_client()
        else:
            self._init_openai_client()
    
    def _init_azure_client(self):
        """Initialize Azure OpenAI (cloudgpt) client."""
        try:
            from cloudgpt_aoai import cloudgpt_aoai
            self.client = cloudgpt_aoai.get_openai_client()
            self.model_name=self.config.model_name
            print("[INFO] Initialized Azure OpenAI (cloudgpt) client")
            print(f"[INFO] Model: {self.model_name}")
        except ImportError:
            print("[WARN] cloudgpt_aoai is unavailable; falling back to OpenAI client")
            self._init_openai_client()
        except Exception as e:
            print(f"[ERROR] Failed to initialize Azure client: {e}")
            self._init_openai_client()
    
    def _init_openai_client(self):
        """Initialize standard OpenAI client."""
        try:
            from openai import OpenAI
            
            if self.config.openai_api_key:
                kwargs = {"api_key": self.config.openai_api_key}
                if self.config.openai_api_base:
                    kwargs["base_url"] = self.config.openai_api_base
                self.client = OpenAI(**kwargs)
                print("[INFO] Initialized OpenAI client")
            else:
                raise ValueError("OpenAI API key is not set")
        except Exception as e:
            print(f"[ERROR] Failed to initialize OpenAI client: {e}")
            raise
    
    def chat(
        self, 
        messages: List[Dict[str, str]], 
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Send a chat completion request.
        
        Args:
            messages: Message list [{"role": "user", "content": "..."}]
            temperature: Sampling temperature (optional)
            max_tokens: Max output tokens (optional)
            
        Returns:
            LLM response content
        """
        if self.client is None:
            raise RuntimeError("LLM client is not initialized")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens
            )
            response_content = response.choices[0].message.content.strip()
            
            # Record conversation history
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
            print(f"[ERROR] LLM request failed: {e}")
            return ""
    
    def chat_with_retry(
        self,
        messages: List[Dict[str, str]],
        max_retries: int = 3,
        **kwargs
    ) -> str:
        """
        Chat request with retries.

        Mapping to CuES:
        Similar to chat_with_retry in CuES api_client.py.
        
        Args:
            messages: Message list
            max_retries: Max retry attempts
            **kwargs: Other parameters
            
        Returns:
            LLM response content
        """
        import time
        
        for attempt in range(max_retries):
            try:
                result = self.chat(messages, **kwargs)
                if result:
                    return result
            except Exception as e:
                print(f"[WARN] Attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"[INFO] Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        
        print(f"[ERROR] All {max_retries} attempts failed")
        return ""
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Get the full conversation history.
        
        Returns:
            Conversation history entries
        """
        return self.conversation_history
    
    def clear_conversation_history(self):
        """Clear conversation history."""
        self.conversation_history = []


# ================================================================================
# Intent generator (CuES Stage 2: Task Abstraction)
# ================================================================================

class IntentGenerator:
    """
    Intent generator.

    Mapping to CuES:
    In CuES, Stage 2 (Task Abstraction) abstracts tasks from agent interaction
    traces. Here we simplify it: infer plausible task intents from a static HTML
    page.

    Core idea:
    1) analyze page structure/content
    2) identify executable action types
    3) generate diverse, verifiable intents
    """
    
    def __init__(self, client: LLMClient, config: Config):
        """
        Initialize the intent generator.
        
        Args:
            client: LLM client
            config: Configuration object
        """
        self.client = client
        self.config = config
    
    def generate(
        self,
        html_content: str,
        num_intents: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate task intents from HTML.

        Steps:
        1) summarize the page via HTMLProcessor
        2) build a prompt and call the LLM
        3) parse the LLM output into structured data
        
        Args:
            html_content: HTML page content
            num_intents: Number of intents to generate (optional)
            
        Returns:
            A list of intents. Each intent includes:
            - intent: task description
            - task_type: task type
            - difficulty: difficulty level
            - reasoning: generation rationale
        """
        # 1) Page summary
        page_summary = HTMLProcessor.summarize_page(html_content)
        print(f"[INFO] Page title: {page_summary['title']}")
        print(f"[INFO] Found {len(page_summary['interactive_elements'])} interactive elements")
        
        # 2) Prompt
        site_name = self.config.webarena.sites[0] if self.config.webarena.sites else "unknown"
        num = num_intents or self.config.generation.num_intents
        
        prompt = PromptBuilder.build_intent_generation_prompt(
            page_summary=page_summary,
            site_name=site_name,
            num_intents=num
        )
        
        # 3) LLM call
        messages = [{"role": "user", "content": prompt}]
        response = self.client.chat_with_retry(messages)
        
        # 4) Parse
        intents = self._parse_intents(response)
        print(f"[INFO] Generated {len(intents)} intents")
        
        return intents
    
    def _parse_intents(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse LLM response into a list of intents.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Parsed intent list
        """
        try:
            # Try parsing JSON. First, extract a ```json ...``` block.
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Otherwise, try to find a JSON array.
                json_match = re.search(r'\[[\s\S]*\]', response)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    print(f"[WARN] Could not find JSON in response: {response[:200]}...")
                    return []
            
            intents = json.loads(json_str)
            
            # Validate format
            valid_intents = []
            for intent in intents:
                if isinstance(intent, dict) and "intent" in intent:
                    valid_intents.append(intent)
            
            return valid_intents
            
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse JSON: {e}")
            print(f"[DEBUG] Raw response: {response[:500]}...")
            return []


# ================================================================================
# Answer annotator (CuES Stage 3: Quality Control)
# ================================================================================

class AnswerAnnotator:
    """
    Answer annotator / validator.

    Mapping to CuES:
    In CuES, Stage 3 (Quality Control) re-executes tasks to validate
    executability. Here we simplify it: use the LLM to judge executability and
    infer reference answers.

    Core responsibilities:
    1) validate whether an intent is executable on the page
    2) infer reference answers for evaluation
    3) decide the evaluation type (exact_match, must_include, etc.)

    Limitations:
    Without a real browser execution environment, answers are LLM-inferred and
    may require manual verification or correction via real execution.
    """
    
    def __init__(self, client: LLMClient, config: Config):
        """
        Initialize the annotator.
        
        Args:
            client: LLM client
            config: Configuration object
        """
        self.client = client
        self.config = config
    
    def validate_and_solve(
        self,
        intent: str,
        html_content: str
    ) -> Dict[str, Any]:
        """
        Validate an intent and generate reference answers.

        Steps:
        1) summarize the page
        2) build a validation prompt
        3) call the LLM
        4) parse and return
        
        Args:
            intent: Task intent to validate
            html_content: HTML page content
            
        Returns:
            Validation result dict including:
            - is_executable: whether executable
            - confidence: confidence score
            - eval_type: evaluation type
            - reference_answers: reference answers
            - reasoning: reasoning text
        """
        # 1) Page summary
        page_summary = HTMLProcessor.summarize_page(html_content)
        
        # 2) Prompt
        site_name = self.config.webarena.sites[0] if self.config.webarena.sites else "unknown"
        prompt = PromptBuilder.build_answer_validation_prompt(
            intent=intent,
            page_summary=page_summary,
            site_name=site_name
        )
        
        # 3) LLM call
        messages = [{"role": "user", "content": prompt}]
        response = self.client.chat_with_retry(messages)
        
        # 4) Parse
        result = self._parse_validation_result(response, intent)
        
        return result
    
    def _parse_validation_result(
        self,
        response: str,
        intent: str
    ) -> Dict[str, Any]:
        """
        Parse the validation result.
        
        Args:
            response: Raw LLM response
            intent: Original intent (for filling the result)
            
        Returns:
            Parsed validation result
        """
        default_result = {
            "intent": intent,
            "is_executable": False,
            "confidence": 0.0,
            "eval_type": "string_match",
            "reference_answers": {},
            "reasoning": "Parse failed"
        }
        
        try:
            # Extract JSON
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    print(f"[WARN] Could not parse validation result: {response[:200]}...")
                    return default_result
            
            result = json.loads(json_str)
            result["intent"] = intent
            
            # Ensure required fields exist
            result.setdefault("is_executable", False)
            result.setdefault("confidence", 0.0)
            result.setdefault("eval_type", "string_match")
            result.setdefault("reference_answers", {})
            result.setdefault("reasoning", "")
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse validation JSON: {e}")
            return default_result
    
    def batch_validate(
        self,
        intents: List[Dict[str, Any]],
        html_content: str
    ) -> List[Dict[str, Any]]:
        """
        Validate multiple intents in a batch.
        
        Args:
            intents: Intent list
            html_content: HTML page content
            
        Returns:
            Validation result list
        """
        results = []
        total = len(intents)
        
        for i, intent_data in enumerate(intents, 1):
            intent_text = intent_data.get("intent", "")
            print(f"[INFO] Validating intent ({i}/{total}): {intent_text[:50]}...")
            
            result = self.validate_and_solve(intent_text, html_content)
            
            # Merge original intent fields
            result.update({
                "task_type": intent_data.get("task_type", "query"),
                "difficulty": intent_data.get("difficulty", "medium"),
                "generation_reasoning": intent_data.get("reasoning", "")
            })
            
            results.append(result)
            
            # Filter low-confidence results
            if result.get("confidence", 0) < self.config.generation.min_confidence:
                print(f"    [SKIP] Confidence {result.get('confidence', 0):.2f} is below threshold")
        
        return results


# ================================================================================
# Main pipeline (Generator + Annotator + Formatter)
# ================================================================================

class TaskGenerationPipeline:
    """
    Main task-generation pipeline.

    This class integrates the key CuES ideas into a simplified linear pipeline:
    
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │   HTML      │ ──> │  Generator  │ ──> │  Annotator  │ ──> │  Formatter  │
    │   Input     │     │  (Intent)   │     │  (Answer)   │     │  (JSON)     │
    └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
    
    Mapping to CuES stages:
    - HTML Input: analogous to Stage 1 observation
    - Generator: Stage 2 task abstraction
    - Annotator: Stage 3 quality control
    - Formatter: standardized WebArena task output
    """
    
    def __init__(self, config: Config):
        """
        Initialize the pipeline.
        
        Args:
            config: Configuration object
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
        Run the full task-generation pipeline.

        Steps:
        1) intent generation
        2) answer validation / reference-answer inference
        3) formatting into WebArena JSON
        4) filtering by confidence
        
        Args:
            html_content: HTML page content
            num_intents: Number of intents to generate (optional)
            start_task_id: Starting task ID
            
        Returns:
            WebArena-formatted task list
        """
        print("=" * 60)
        print("[Stage 1] Intent generation (CuES Stage 2: Task Abstraction)")
        print("=" * 60)
        
        # 1. Generate intents
        intents = self.generator.generate(html_content, num_intents)
        
        if not intents:
            print("[ERROR] No intents were generated")
            return []
        
        print("\n" + "=" * 60)
        print("[Stage 2] Answer validation (CuES Stage 3: Quality Control)")
        print("=" * 60)
        
        # 2. Validate and infer reference answers
        validated_results = self.annotator.batch_validate(intents, html_content)
        
        # 3. Filter low-confidence results
        min_conf = self.config.generation.min_confidence
        filtered_results = [
            r for r in validated_results 
            if r.get("is_executable", False) and r.get("confidence", 0) >= min_conf
        ]
        
        print(f"\n[INFO] Kept {len(filtered_results)}/{len(validated_results)} tasks after filtering")
        
        print("\n" + "=" * 60)
        print("[Stage 3] Format output (WebArena JSON)")
        print("=" * 60)
        
        # 4. Format into WebArena tasks
        tasks = self.formatter.format_tasks(filtered_results, start_task_id)
        
        print(f"[INFO] Generated {len(tasks)} WebArena tasks")
        
        return tasks
    
    def run_from_url(
        self,
        url: str,
        num_intents: Optional[int] = None,
        start_task_id: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Fetch a page from URL and generate tasks.
        
        Args:
            url: Target page URL
            num_intents: Number of intents to generate (optional)
            start_task_id: Starting task ID
            
        Returns:
            WebArena-formatted task list
        """
        print(f"[INFO] Fetching page: {url}")
        
        try:
            import requests
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            html_content = response.text
            print(f"[INFO] Page fetched, size: {len(html_content)} bytes")
        except Exception as e:
            print(f"[ERROR] Failed to fetch page: {e}")
            return []
        
        return self.run(html_content, num_intents, start_task_id)
    
    def run_from_file(
        self,
        file_path: str,
        num_intents: Optional[int] = None,
        start_task_id: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Load a local HTML file and generate tasks.
        
        Args:
            file_path: HTML file path
            num_intents: Number of intents to generate (optional)
            start_task_id: Starting task ID
            
        Returns:
            WebArena-formatted task list
        """
        print(f"[INFO] Reading file: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            print(f"[INFO] File read, size: {len(html_content)} bytes")
        except Exception as e:
            print(f"[ERROR] Failed to read file: {e}")
            return []
        
        return self.run(html_content, num_intents, start_task_id)
    
    def get_conversation_history(self) -> Dict[str, Any]:
        """
        Get full conversation history.
        
        Returns:
            Dict containing conversation history
        """
        return {
            "conversation_history": self.client.get_conversation_history()
        }
    
    def save_conversation_history(self, output_path: str):
        """
        Save conversation history to a JSON file.
        
        Args:
            output_path: Output file path
        """
        history_data = self.get_conversation_history()
        JSONHandler.save(history_data, output_path)
        print(f"[INFO] Conversation history saved to: {output_path}")


# ================================================================================
# Convenience functions
# ================================================================================

def generate_tasks_from_html(
    html_content: str,
    config: Optional[Config] = None,
    num_intents: int = 5
) -> List[Dict[str, Any]]:
    """
    Convenience: generate tasks directly from HTML content.
    
    Args:
        html_content: HTML page content
        config: Configuration object (optional)
        num_intents: Number of intents to generate
        
    Returns:
        WebArena-formatted task list
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
    Convenience: generate tasks directly from a URL.
    
    Args:
        url: Target page URL
        config: Configuration object (optional)
        num_intents: Number of intents to generate
        
    Returns:
        WebArena-formatted task list
    """
    config = config or Config()
    pipeline = TaskGenerationPipeline(config)
    return pipeline.run_from_url(url, num_intents)
